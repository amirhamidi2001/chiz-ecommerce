import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, F, Prefetch, prefetch_related_objects
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from django_filters import utils as filter_utils
from django_filters.rest_framework import DjangoFilterBackend
from order.models import Order, OrderItem
from promotions.models import FlashSale
from rest_framework import filters, generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import ProductFilter, RelevanceOrderingFilter
from .models import (
    Brand,
    Category,
    Color,
    HairType,
    Product,
    ProductGender,
    ProductVariant,
    Review,
    ReviewImage,
    ReviewReport,
    SkinType,
    StockAlertSubscription,
)
from .pagination import StandardResultsPagination
from .recommendations import (
    get_category_affinity_recommendations,
    get_frequently_bought_together,
)
from .search import apply_product_search, filter_products_by_search, search_log_term
from .serializers import (
    BrandSerializer,
    CategorySerializer,
    ColorSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ProductSuggestSerializer,
    ReviewCreateSerializer,
    ReviewReportCreateSerializer,
    ReviewSerializer,
    StockAlertSubscriptionSerializer,
)
from .services import refresh_product_review_stats
from .tasks import log_search_query
from .text_utils import normalize_persian_text

logger = logging.getLogger(__name__)

# ─── Categories ────────────────────────────────────────────────────────────────
# Cache key carries an explicit version suffix: if CategorySerializer's output
# shape ever changes (fields added/removed), bump this to _v2 so old,
# differently-shaped cached data is never accidentally served post-deploy.
CATEGORY_TREE_CACHE_KEY = "category_tree_v1"
CATEGORY_TREE_CACHE_TTL = (
    60 * 60
)  # 1 hour — long TTL is fine given signal-based invalidation handles real changes promptly


class CategoryListView(generics.ListAPIView):
    """Return top-level categories with nested children."""

    permission_classes = [AllowAny]
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.filter(parent__isnull=True).prefetch_related("children")

    def list(self, request, *args, **kwargs):
        cached = cache.get(CATEGORY_TREE_CACHE_KEY)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache.set(
            CATEGORY_TREE_CACHE_KEY, response.data, timeout=CATEGORY_TREE_CACHE_TTL
        )
        return response


# ─── Brands ────────────────────────────────────────────────────────────────────
class BrandListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = BrandSerializer
    queryset = Brand.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]
    pagination_class = None


# ─── Colors ────────────────────────────────────────────────────────────────────
class ColorListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ColorSerializer
    queryset = Color.objects.all()
    pagination_class = None


# ─── Products list ─────────────────────────────────────────────────────────────
# Short TTL — unlike the category tree (Task 21.1.1.2), product data (stock,
# price, sale flags) changes frequently enough that signal-based invalidation
# per-field would be brittle to maintain; a short TTL bounds staleness instead.
PRODUCT_LIST_CACHE_TTL = 60  # seconds

# NOTE: ProductListSerializer's thumbnail_url (and nested category/brand image
# fields) are built via request.build_absolute_uri(), so a cached response
# bakes in the HOST of whichever request populated the cache. Not a
# user-identity leak (ProductListSerializer carries no wishlist/personalized-
# pricing fields — wishlist state lives in dashboard/wishlist/, a separate
# endpoint), so caching is safe across anonymous/authenticated visitors alike.
# It WOULD misbehave if this backend were ever served under multiple hostnames
# — a pre-existing consideration that also applies to the category cache.


def _current_flash_sale_prefetches():
    """Prefetches that let ProductListSerializer resolve each product's current
    flash sale and its cheapest active variant without a query per product."""
    now = timezone.now()
    return [
        Prefetch(
            "flash_sales",
            queryset=FlashSale.objects.filter(
                is_active=True, starts_at__lte=now, ends_at__gte=now
            ),
        ),
        Prefetch("variants", queryset=ProductVariant.objects.filter(is_active=True)),
    ]


class ProductListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = StandardResultsPagination
    # Search is no longer a DRF SearchFilter: ?search= is handled in
    # get_queryset() with Postgres full-text search (weighted, ranked, GIN
    # indexed — see shop/search.py). RelevanceOrderingFilter makes relevance
    # the default order while searching; an explicit ?ordering= still wins.
    filter_backends = [DjangoFilterBackend, RelevanceOrderingFilter]
    filterset_class = ProductFilter
    ordering_fields = ["price", "rating", "created_at", "reviews_count"]
    ordering = ["-created_at"]
    # Set by get_queryset(); read by RelevanceOrderingFilter.
    is_ranked_search = False

    def get_queryset(self):
        queryset = (
            Product.objects.select_related("category", "brand").prefetch_related(
                "colors__color", *_current_flash_sale_prefetches()
            )
            # The tsvector is only ever used inside SQL; don't ship it to
            # Python for every row of every list page.
            .defer("search_vector")
        )
        request = getattr(self, "request", None)  # None during schema generation
        raw_term = request.query_params.get("search", "") if request else ""
        queryset, self.is_ranked_search = apply_product_search(queryset, raw_term)
        return queryset

    def list(self, request, *args, **kwargs):
        cache_key = self._build_cache_key(request)
        cached = cache.get(cache_key)
        if cached is not None:
            # Cache hits are real searches too: without this, a popular term
            # would be logged once per TTL instead of once per search.
            self._log_search(request, cached)
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=PRODUCT_LIST_CACHE_TTL)
        self._log_search(request, response.data)
        return response

    def _log_search(self, request, data):
        """
        Record a customer search for analytics, without slowing it down.

        Runs AFTER the response data exists (this is why it lives in list(),
        not get_queryset(), which runs before any query) and reads the match
        count straight out of that data: DRF's paginator has already done the
        COUNT for the response's `count` field, so logging adds no database
        query to the search request — only a Celery enqueue.

        Not logged: normal browsing (no/blank ?search=), and pages after the
        first (paging through one result set is not a new search).
        """
        term = search_log_term(request.query_params.get("search"))
        if not term:
            return
        if request.query_params.get("page") not in (None, "", "1"):
            return
        count = data.get("count") if isinstance(data, dict) else len(data)
        user = request.user
        try:
            log_search_query.delay(
                term, count, user.id if user.is_authenticated else None
            )
        except Exception:  # broker down etc. — analytics must never break search
            logger.warning("Could not enqueue search-query log", exc_info=True)

    def _build_cache_key(self, request):
        # Sort query params for a stable, order-independent key — ?category=1&
        # brand=2 and ?brand=2&category=1 are semantically identical requests
        # and must produce the SAME cache key.
        #
        # NOTE: request.query_params.items() returns only the LAST value for
        # any repeated key (QueryDict semantics) — this is safe ONLY because
        # ProductFilter's multi-select filters (brand/color/skin_type/
        # hair_type) are all single comma-separated values (?brand=a,b), never
        # repeated-key params (?brand=a&brand=b). If a future filter ever
        # adopts repeated-key semantics, this must switch to
        # request.query_params.lists() or it will silently collide keys.
        params = sorted(request.query_params.items())
        params_str = "&".join(f"{k}={v}" for k, v in params)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()
        return f"product_list_v1:{params_hash}"


# ─── Product autocomplete ──────────────────────────────────────────────────────
SUGGEST_MIN_LENGTH = 2
SUGGEST_LIMIT = 8


class ProductSuggestView(generics.ListAPIView):
    """
    GET /api/products/suggest/?q=<term> — a handful of top matches for a
    search-box dropdown: id, name, slug, price, thumbnail_url only.

    Uses apply_product_search() — the same normalisation, prefix tsquery
    and weighted ranking as ProductListView's ?search= — so "lip" finds
    "Lipstick" while typing and Arabic/Persian character variants and ZWNJ
    behave identically in both places.
    """

    permission_classes = [AllowAny]
    serializer_class = ProductSuggestSerializer
    pagination_class = None  # a dropdown, not a results page
    # No DRF default backends: OrderingFilter would try to re-order the
    # sliced queryset on ?ordering= (AssertionError -> 500) and nothing here
    # is user-filterable anyway.
    filter_backends = []

    def get_queryset(self):
        # Normalise BEFORE measuring: "ك" + ZWNJ is 2 characters typed but
        # 1 searchable character.
        term = normalize_persian_text(self.request.query_params.get("q", "")).strip()
        if len(term) < SUGGEST_MIN_LENGTH:
            # Short-circuit: no database query at all for a single keystroke.
            return Product.objects.none()
        queryset, is_ranked = apply_product_search(
            Product.objects.only("id", "name", "slug", "price", "thumbnail"), term
        )
        if not is_ranked:
            # Long enough but nothing searchable (e.g. "!!!"): already
            # .none(), and has no `rank` annotation to order by.
            return queryset
        return queryset.order_by("-rank", "-created_at", "-pk")[:SUGGEST_LIMIT]


# ─── Facet counts ──────────────────────────────────────────────────────────────
class ProductFacetCountsView(APIView):
    """
    GET /api/products/facet-counts/?<the same filter params as /products/>

    For each cosmetics facet, how many products match each of its options
    GIVEN the other active filters. Each facet is counted against every
    active filter EXCEPT ITS OWN, so a customer who has picked "Oily" still
    sees what "Dry" or "Normal" would yield — the standard faceted-search
    behaviour. (Within one facet the options are OR-ed, so each count is "what
    selecting just this option would give", not "on top of my current ones".)

        {
          "skin_type": {"oily": 12, "dry": 3, ..., "all": 0},   # every option, zeros included
          "hair_type": {...},
          "gender":    {"unisex": 10, "female": 4, "male": 1},
          "is_cruelty_free": 8, "is_vegan": 5, "is_organic": 2   # products with the flag
        }

    Every filter the list endpoint understands applies — category, brand,
    colour, price, SPF, flash sale AND ?search= (a facet count that ignored
    the search term would be catalogue-wide, not "of these results").
    SPF is a range, not a list of discrete options, so it has no counts.
    paging/ordering params are accepted and ignored.
    """

    permission_classes = [AllowAny]

    LIST_FACETS = {
        "skin_type": SkinType,
        "hair_type": HairType,
        "gender": ProductGender,
    }
    BOOLEAN_FACETS = ("is_cruelty_free", "is_vegan", "is_organic")
    # Don't affect counts, and must not fragment the cache key.
    IGNORED_PARAMS = frozenset({"page", "page_size", "ordering"})

    def get(self, request):
        params = {
            k: v
            for k, v in request.query_params.items()
            if k not in self.IGNORED_PARAMS
        }

        # Same validation (and the same 400 body) the list endpoint gives for
        # e.g. ?min_spf=abc — rather than quietly counting an empty set.
        filterset = ProductFilter(params, queryset=Product.objects.none())
        if not filterset.is_valid():
            raise filter_utils.translate_validation(filterset.errors)

        cache_key = self._build_cache_key(params)
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        counts = {}
        for facet, choices in self.LIST_FACETS.items():
            counts[facet] = self._list_facet_counts(params, facet, choices)
        for facet in self.BOOLEAN_FACETS:
            counts[facet] = (
                self._filtered(params, exclude=facet)
                .filter(**{facet: True})
                .aggregate(n=Count("id", distinct=True))["n"]
            )

        cache.set(cache_key, counts, timeout=PRODUCT_LIST_CACHE_TTL)
        return Response(counts)

    def _filtered(self, params, exclude):
        """
        Products matching every active filter except `exclude` — built with
        the SAME ProductFilter and search the list endpoint uses, so these
        counts can't drift from what the list would actually return.
        """
        data = {k: v for k, v in params.items() if k != exclude}
        queryset = ProductFilter(data, queryset=Product.objects.all()).qs
        return filter_products_by_search(queryset, params.get("search"))

    def _list_facet_counts(self, params, facet, choices):
        values = [value for value, _label in choices.choices]
        rows = (
            self._filtered(params, exclude=facet)
            .filter(**{f"{facet}__in": values})  # drops the blank "not set" value
            .order_by()  # no default -created_at in the GROUP BY
            .values(facet)
            # distinct=True: filters that JOIN (colour, flash sale) can repeat
            # a product's row, and a plain COUNT would count it twice.
            .annotate(n=Count("id", distinct=True))
        )
        found = {row[facet]: row["n"] for row in rows}
        # Every option is present, zeros included, so a client never has to
        # guess whether a missing value means "none" or "unknown".
        return {value: found.get(value, 0) for value in values}

    def _build_cache_key(self, params):
        # Deliberately inside the "product_list_v1:" namespace:
        # signals.invalidate_product_list_cache() deletes "*product_list_v1:*",
        # so product / flash-sale / stock changes clear these counts together
        # with the cached list pages, with no separate invalidation to keep in
        # sync. (test_facet_counts.py locks this in.)
        # Sorted + order-independent like ProductListView._build_cache_key; see
        # the note there about repeated query keys.
        params_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"product_list_v1:facets:{hashlib.md5(params_str.encode()).hexdigest()}"


# ─── Product detail ────────────────────────────────────────────────────────────
class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        # Prefetch only the flash sales that are current right now, so
        # resolving each variant's sale-aware price (ProductVariantSerializer)
        # costs no extra query per variant.
        now = timezone.now()
        current_sales = FlashSale.objects.filter(
            is_active=True, starts_at__lte=now, ends_at__gte=now
        )
        return Product.objects.select_related("category", "brand").prefetch_related(
            "images",
            "colors__color",
            # Public storefront: unapproved (pending/rejected) reviews are
            # never exposed here.
            Prefetch(
                "reviews",
                queryset=Review.objects.filter(is_approved=True).prefetch_related(
                    "images"
                ),
            ),
            Prefetch("flash_sales", queryset=current_sales),
        )


# ─── Related products ──────────────────────────────────────────────────────────
class RelatedProductsView(generics.ListAPIView):
    """Return up to 8 products from the same category, excluding the current one."""

    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = None

    def get_queryset(self):
        slug = self.kwargs.get("slug")
        try:
            product = Product.objects.get(slug=slug)
        except Product.DoesNotExist:
            return Product.objects.none()

        return (
            Product.objects.filter(category=product.category)
            .exclude(slug=slug)
            .select_related("category", "brand")
            .prefetch_related(*_current_flash_sale_prefetches())
            .order_by("-rating")[:8]
        )


# ─── Frequently bought together ────────────────────────────────────────────────
class FrequentlyBoughtTogetherView(generics.ListAPIView):
    """
    GET /api/products/<slug>/frequently-bought-together/

    Products most often purchased in the same (completed) order as this one,
    ranked by co-occurrence. See shop.recommendations. Unknown slug -> 404;
    a product with no co-purchase history -> 200 with [].
    """

    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = None
    # get_queryset() returns a ranked list, not a QuerySet, so the project-wide
    # default filter backends (DjangoFilter/Search/Ordering) must not run on it
    # — and ?ordering= would silently discard the co-occurrence ranking anyway.
    filter_backends = []

    def get_queryset(self):
        slug = self.kwargs.get("slug")
        product = get_object_or_404(Product, slug=slug)
        products = get_frequently_bought_together(product.id)
        # The service returns an ordered list (not a queryset); attach the
        # prefetches ProductListSerializer needs without disturbing the order.
        prefetch_related_objects(products, *_current_flash_sale_prefetches())
        return products


# ─── Homepage recommendations (category affinity) ──────────────────────────────
MAX_VIEWED_IDS = 20


def _clean_id_list(raw, max_items=MAX_VIEWED_IDS):
    """Client-supplied list -> de-duplicated positive ints, order kept, capped.

    The list comes straight from the browser's localStorage, so it can be
    anything. Junk is dropped silently rather than raising: a bad entry must
    never turn a harmless homepage widget into a 400/500.
    """
    if not isinstance(raw, list):
        return []
    cleaned = []
    for item in raw:
        if isinstance(item, bool):
            continue
        if isinstance(item, str) and item.isdigit():
            item = int(item)
        if isinstance(item, int) and 0 < item < 2**31 and item not in cleaned:
            cleaned.append(item)
        if len(cleaned) >= max_items:
            break
    return cleaned


class HomeRecommendationsView(APIView):
    """
    POST /api/products/home-recommendations/   body: {"viewed_product_ids": [..]}

    Lightweight category-affinity recommendations for the homepage (see
    shop.recommendations.get_category_affinity_recommendations — a simple
    heuristic, not ML).

    Why POST for a read-only endpoint: the viewing history lives only in the
    visitor's localStorage (Task 13.1.1.2, Option A), so the client has to send
    it, and a list of up to 20 ids is awkward in a query string and risks URL
    length limits. A JSON body is the practical tool, at the cost of REST
    purity. Nothing is stored server-side.

    Anonymous visitors rely entirely on the supplied ids. Authenticated users
    additionally get the categories they have purchased from (completed
    orders only), which works even when no ids are supplied.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        viewed_product_ids = _clean_id_list(data.get("viewed_product_ids"))

        purchased_category_ids = None
        if request.user.is_authenticated:
            purchased_category_ids = list(
                OrderItem.objects.filter(
                    order__user=request.user,
                    order__status__in=[
                        Order.Status.PROCESSING,
                        Order.Status.SHIPPED,
                        Order.Status.DELIVERED,
                    ],
                    product__category_id__isnull=False,
                )
                .values_list("product__category_id", flat=True)
                .distinct()
            )

        products = get_category_affinity_recommendations(
            viewed_product_ids, purchased_category_ids
        )
        # The service returns a ranked list; attach the prefetches
        # ProductListSerializer needs without disturbing the order.
        prefetch_related_objects(products, *_current_flash_sale_prefetches())
        return Response(
            ProductListSerializer(
                products, many=True, context={"request": request}
            ).data
        )


# ─── Product reviews — create ──────────────────────────────────────────────────
class ProductReviewCreateView(generics.CreateAPIView):
    """
    POST /api/products/<slug>/reviews/

    Create a new review for the product identified by slug.
    After saving the review, the product's denormalised `rating` and
    `reviews_count` fields are recalculated from the APPROVED reviews only
    (see shop.services.refresh_product_review_stats). Verified purchasers may
    also attach up to 5 photos (multipart `images`); anyone else sending
    photos gets a 400 and nothing is saved. A review is approved
    immediately only for verified purchasers while
    REVIEW_AUTO_APPROVE_VERIFIED_PURCHASES is on; otherwise it stays pending
    until an admin approves it.

    Permissions: IsAuthenticated — reviews are now tied to a real `user`
    FK (Task 1.3.1.1) rather than a free-text `name` field, so anonymous
    submission is no longer allowed. The reviewer's display name is
    derived server-side from their profile rather than accepted as
    client input, and the review's `user` is always the requesting
    account — never client-controlled.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ReviewCreateSerializer

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get_product(self) -> Product:
        """Fetch the product or return 404. Cached on the request for reuse."""
        if not hasattr(self, "_product"):
            self._product = get_object_or_404(Product, slug=self.kwargs["slug"])
        return self._product

    def _is_verified_purchase(self, user, product: Product) -> bool:
        """
        True iff `user` has a DELIVERED order containing `product`.

        Deliberately requires DELIVERED specifically (not merely placed,
        pending, or processing) — a "verified purchase" badge should mean
        the customer genuinely received the item, not just that they
        checked out.
        """
        return OrderItem.objects.filter(
            order__user=user,
            order__status=Order.Status.DELIVERED,
            product=product,
        ).exists()

    # ── DRF hooks ─────────────────────────────────────────────────────────────

    def get_serializer_context(self):
        """
        Make the target product available to the serializer at validation
        time (not just at save() time via perform_create) so
        ReviewCreateSerializer.validate() can check for an existing
        review by this user on this product before attempting to save.
        """
        context = super().get_serializer_context()
        context["product"] = self._get_product()
        return context

    def perform_create(self, serializer) -> None:
        """Attach the product FK, authenticated user, verified-purchase status
        and moderation status, store any photos, then update aggregate fields."""
        product = self._get_product()
        is_verified = self._is_verified_purchase(self.request.user, product)

        # `images` is a write-only input, not a Review column: it must come out
        # of validated_data before save() (Review.objects.create() would choke
        # on the unknown kwarg) and is stored as ReviewImage rows below.
        images = serializer.validated_data.pop("images", [])
        if images and not is_verified:
            # Rejected before ANY write: no Review row, no files on disk.
            raise serializers.ValidationError(
                {
                    "images": [
                        _("Only verified purchasers can attach photos to a review.")
                    ]
                }
            )

        auto_approve = is_verified and settings.REVIEW_AUTO_APPROVE_VERIFIED_PURCHASES
        # One transaction so a failure while storing a photo doesn't leave a
        # published review that is silently missing its photos.
        with transaction.atomic():
            review = serializer.save(
                product=product,
                user=self.request.user,
                is_verified_purchase=is_verified,
                is_approved=auto_approve,
            )
            for image in images:
                ReviewImage.objects.create(review=review, image=image)
        # A pending review doesn't change the public stats, but recomputing is
        # cheap and keeps this path correct if the approval rules ever change.
        refresh_product_review_stats(product)

    def create(self, request, *args, **kwargs) -> Response:
        """
        Override to:
        1. Validate the product exists before parsing the body.
        2. Return the full ReviewSerializer representation (including `id` and
           `created_at`) so the frontend can optimistically prepend the new
           review without a second GET.
        """
        self._get_product()  # raises 404 early if slug is wrong

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Respond with the read serializer so the client gets all fields back.
        response_data = ReviewSerializer(
            serializer.instance, context={"request": request}
        ).data
        headers = self.get_success_headers(response_data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)


# ─── Product reviews — report ──────────────────────────────────────────────────
# Unresolved reports at which a published review is pulled from public view
# (is_approved -> False) until an admin looks at it.
REVIEW_REPORT_AUTO_HIDE_THRESHOLD = 3


class ReviewReportCreateView(APIView):
    """
    POST /api/reviews/<review_id>/report/

    Flag a published review as spam/offensive/irrelevant. One report per user
    per review: a repeat is a no-op answered with 200. Only approved (i.e.
    publicly visible) reviews can be reported; anything else is a 404 so
    pending reviews can't be probed by id.

    Safety net: once a review has REVIEW_REPORT_AUTO_HIDE_THRESHOLD or more
    unresolved reports it is un-approved automatically and the product's
    rating/count are recomputed without it. Re-approving is an explicit admin
    action (and admins should resolve the reports first — see
    AdminReviewViewSet.resolve_reports).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, review_id):
        review = get_object_or_404(
            Review.objects.select_related("product"), pk=review_id, is_approved=True
        )
        serializer = ReviewReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        report, created = ReviewReport.objects.get_or_create(
            review=review,
            reported_by=request.user,
            defaults=serializer.validated_data,
        )

        if created:
            unresolved = review.reports.filter(resolved=False).count()
            if unresolved >= REVIEW_REPORT_AUTO_HIDE_THRESHOLD and review.is_approved:
                review.is_approved = False
                review.save(update_fields=["is_approved"])
                refresh_product_review_stats(review.product)

        return Response(
            {
                "detail": (
                    _("Report submitted.")
                    if created
                    else _("You have already reported this review.")
                )
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ─── Stock alert subscriptions ─────────────────────────────────────────────────
class StockAlertSubscriptionView(APIView):
    """
    POST   /api/products/variants/<variant_id>/notify-me/  — subscribe
    DELETE /api/products/variants/<variant_id>/notify-me/  — unsubscribe

    Combined into a single view rather than two separate generics views
    registered at the same URL: Django's URL resolver maps one path to
    one view, so two distinct view classes can't share an identical
    path()/re_path() entry — the second registration would simply never
    be reached. A single APIView with both post() and delete() defined
    (DRF's normal per-HTTP-method dispatch) is the correct way to serve
    different actions at the same URL.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, variant_id):
        variant = get_object_or_404(ProductVariant, pk=variant_id)
        if variant.stock > 0:
            return Response(
                {"detail": _("This item is currently in stock.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        subscription, created = StockAlertSubscription.objects.get_or_create(
            user=request.user, variant=variant
        )
        serializer = StockAlertSubscriptionSerializer(subscription)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, variant_id):
        subscription = get_object_or_404(
            StockAlertSubscription, user=request.user, variant_id=variant_id
        )
        subscription.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
