from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from order.models import Order, OrderItem
from rest_framework import filters, generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .filters import ProductFilter
from .models import Brand, Category, Color, Product
from .pagination import StandardResultsPagination
from .serializers import (
    BrandSerializer,
    CategorySerializer,
    ColorSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ReviewCreateSerializer,
    ReviewSerializer,
)


# ─── Categories ────────────────────────────────────────────────────────────────
class CategoryListView(generics.ListAPIView):
    """Return top-level categories with nested children."""

    permission_classes = [AllowAny]
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.filter(parent__isnull=True).prefetch_related("children")


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
class ProductListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ProductFilter
    search_fields = [
        "name",
        "short_description",
        "description",
        "brand__name",
        "category__name",
    ]
    ordering_fields = ["price", "rating", "created_at", "reviews_count"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Product.objects.select_related("category", "brand")
            .prefetch_related("colors__color")
            .all()
        )


# ─── Product detail ────────────────────────────────────────────────────────────
class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Product.objects.select_related("category", "brand").prefetch_related(
            "images", "colors__color", "reviews"
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
            .order_by("-rating")[:8]
        )


# ─── Product reviews — create ──────────────────────────────────────────────────
class ProductReviewCreateView(generics.CreateAPIView):
    """
    POST /api/products/<slug>/reviews/

    Create a new review for the product identified by slug.
    After saving the review, the product's denormalised `rating` and
    `reviews_count` fields are recalculated from the full review set so
    that all aggregated values stay consistent without a separate cron job.

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

    def _refresh_product_stats(self, product: Product) -> None:
        """
        Recompute and persist the product's aggregate rating and review count.
        Uses a single DB query against the already-saved reviews relation.
        """
        stats = product.reviews.aggregate(
            avg_rating=Avg("rating"),
            total=Count("id"),
        )
        product.rating = round(stats["avg_rating"] or 0.0, 1)
        product.reviews_count = stats["total"] or 0
        product.save(update_fields=["rating", "reviews_count"])

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
        """Attach the product FK, authenticated user, and verified-purchase
        status, then update aggregate fields."""
        product = self._get_product()
        serializer.save(
            product=product,
            user=self.request.user,
            is_verified_purchase=self._is_verified_purchase(self.request.user, product),
        )
        self._refresh_product_stats(product)

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
        response_data = ReviewSerializer(serializer.instance).data
        headers = self.get_success_headers(response_data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)
