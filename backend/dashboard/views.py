import csv
import re
from types import SimpleNamespace

from accounts.models import Profile
from blog.models import Category as BlogCategory
from blog.models import Comment as BlogComment
from blog.models import Post as BlogPost
from cart.views import get_or_create_cart
from contact.models import ContactMessage
from core.money import MAX_RIAL_AMOUNT
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from order.models import Order
from order.services.cancellation import cancel_order
from order.services.state_machine import is_valid_transition
from promotions.models import Coupon
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from shop.models import Brand, Category, Product, ProductVariant, Review, StockMovement
from shop.serializers import ProductVariantSerializer
from shop.services import refresh_product_review_stats

from . import product_import, services
from .filters import (
    AdminCategoryFilter,
    AdminCommentFilter,
    AdminOrderFilter,
    AdminPostFilter,
    AdminProductFilter,
    AdminUserFilter,
    AdminVariantExportFilter,
    UserOrderFilter,
)
from .models import Address, PriceAdjustmentLog, Wishlist
from .permissions import IsAdminOrSuperuser
from .serializers import (
    AddressSerializer,
    AdjustStockSerializer,
    AdminBrandSerializer,
    AdminCategorySerializer,
    AdminCommentSerializer,
    AdminContactMessageSerializer,
    AdminCouponSerializer,
    AdminOrderDetailSerializer,
    AdminOrderListSerializer,
    AdminOrderStatusSerializer,
    AdminPostSerializer,
    AdminProductSerializer,
    AdminReviewSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    AvatarUploadSerializer,
    BlogCategorySerializer,
    BulkPriceUpdateSerializer,
    BulkProductImportSerializer,
    ChangePasswordSerializer,
    NotificationSettingsSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    UserOrderDetailSerializer,
    UserOrderListSerializer,
    UserReviewSerializer,
    WishlistSerializer,
)
from .services import get_wishlist_owner_kwargs

User = get_user_model()


# ─── Shared Pagination ───────────────────────────────────────────────────────


class DashboardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


# ═══════════════════════════════════════════════════════════════════════════════
# USER DASHBOARD VIEWS
# ═══════════════════════════════════════════════════════════════════════════════


class ProfileView(APIView):
    """
    GET  /dashboard/profile/  — return the authenticated user's profile.
    PATCH /dashboard/profile/ — update name / phone.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        serializer = ProfileSerializer(profile, context={"request": request})
        return Response(serializer.data)

    def patch(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        serializer = ProfileUpdateSerializer(
            profile, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProfileSerializer(profile, context={"request": request}).data)


class AvatarUploadView(APIView):
    """POST /dashboard/profile/upload-avatar/ — replace the user's avatar."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        serializer = AvatarUploadSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"avatar_url": request.build_absolute_uri(profile.image.url)},
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    """POST /dashboard/change-password/ — change the authenticated user's password."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": _("Password changed successfully.")})


class NotificationSettingsView(APIView):
    """
    GET   /dashboard/notifications/ — get notification preferences.
    PATCH /dashboard/notifications/ — update notification preferences.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        return Response(NotificationSettingsSerializer(profile).data)

    def patch(self, request):
        profile = get_object_or_404(Profile, user=request.user)
        serializer = NotificationSettingsSerializer(
            profile, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserSummaryView(APIView):
    """GET /dashboard/summary/ — dashboard summary cards."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.get_user_summary(request.user))


class AddressViewSet(viewsets.ModelViewSet):
    """
    CRUD for the authenticated user's saved addresses.
    GET    /dashboard/addresses/
    POST   /dashboard/addresses/
    PATCH  /dashboard/addresses/{id}/
    DELETE /dashboard/addresses/{id}/
    """

    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_object(self):
        obj = get_object_or_404(Address, pk=self.kwargs["pk"], user=self.request.user)
        self.check_object_permissions(self.request, obj)
        return obj


class WishlistViewSet(viewsets.ModelViewSet):
    """
    Wishlist management — open to guests (session-based) as well as
    authenticated users; ownership is resolved by
    get_wishlist_owner_kwargs(), so a visitor only ever sees/removes
    their own session's items.

    GET    /dashboard/wishlist/
    POST   /dashboard/wishlist/         body: { product_id: <int> }
    DELETE /dashboard/wishlist/{id}/
    """

    serializer_class = WishlistSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return Wishlist.objects.filter(
            **get_wishlist_owner_kwargs(self.request)
        ).select_related("product", "product__category", "product__brand")

    def perform_create(self, serializer):
        # validate() already rejects duplicates; this catches the race
        # where two identical POSTs (double-clicked heart) both pass
        # validate() and one hits the unique constraint.
        try:
            with transaction.atomic():
                serializer.save(**get_wishlist_owner_kwargs(self.request))
        except IntegrityError:
            raise ValidationError(
                {"product_id": _("Product is already in your wishlist.")}
            ) from None

    def get_object(self):
        obj = get_object_or_404(
            Wishlist,
            pk=self.kwargs["pk"],
            **get_wishlist_owner_kwargs(self.request),
        )
        return obj

    # ── Move to cart ─────────────────────────────────────────────────────────
    # The cart holds a specific ProductVariant but a wishlist item is a
    # Product, so a move has to resolve WHICH variant:
    #   0 purchasable variants -> 400 (nothing to move)
    #   1                      -> moved automatically
    #   2+                     -> the client must choose; see below.
    #
    # Status-code decision: "needs a choice" is 300 Multiple Choices, not
    # 200 or 400. It is a legitimate intermediate state rather than a client
    # error, and — the practical reason — it can't be mistaken for success:
    # axios (like most clients) rejects non-2xx, so a caller that just
    # checks "did it resolve?" can never remove the wishlist item from its
    # UI on the strength of a response that moved nothing. The body also
    # carries `needs_selection: true` so clients needn't key off the status
    # alone. Bulk "move all" is different by design: it always partly
    # succeeds, so it returns 200 with a `needs_selection` bucket.

    @action(detail=True, methods=["post"], url_path="move-to-cart")
    def move_to_cart(self, request, pk=None):
        """
        POST /dashboard/wishlist/{id}/move-to-cart/   body: { variant_id? }

        200 moved · 300 needs `variant_id` (body lists the choices) ·
        400 unavailable / invalid variant_id · 404 not your item (or gone).
        """
        wishlist_item = self.get_object()
        variants = services.get_purchasable_variants(wishlist_item.product)

        if not variants:
            return Response(
                {"detail": _("This product is currently unavailable.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested = request.data.get("variant_id")
        if requested not in (None, ""):
            # Validated even when only one variant is left: a client that
            # picked shade B must not silently get shade A because B sold
            # out while its picker was open.
            try:
                requested = int(requested)
            except (TypeError, ValueError):
                requested = None
            variant = next((v for v in variants if v.id == requested), None)
            if variant is None:
                return Response(
                    {"variant_id": _("Invalid variant for this product.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif len(variants) == 1:
            variant = variants[0]
        else:
            return Response(
                {
                    "detail": _(
                        "This product has multiple options — please choose one."
                    ),
                    "needs_selection": True,
                    "variants": ProductVariantSerializer(variants, many=True).data,
                },
                status=status.HTTP_300_MULTIPLE_CHOICES,
            )

        cart = get_or_create_cart(request)
        if not services.move_wishlist_item_to_cart(cart, wishlist_item, variant):
            return Response(
                {"detail": _("This wishlist item is no longer on your wishlist.")},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"detail": _("Moved to cart.")}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="move-all-to-cart")
    def move_all_to_cart(self, request):
        """
        POST /dashboard/wishlist/move-all-to-cart/

        Moves every unambiguous item in one pass and reports the rest, so
        one multi-shade product never blocks the whole wishlist and nothing
        is skipped silently. Always 200:
          moved           [product name]
          needs_selection [{wishlist_item_id, product, variants}] — finish
                          each with move-to-cart + a variant_id
          unavailable     [{wishlist_item_id, product}]
        """
        moved, needs_selection, unavailable = [], [], []
        cart = None  # resolved lazily, once — and not at all if nothing moves

        for item in list(self.get_queryset()):
            variants = services.get_purchasable_variants(item.product)
            if not variants:
                unavailable.append(
                    {"wishlist_item_id": item.id, "product": item.product.name}
                )
            elif len(variants) > 1:
                needs_selection.append(
                    {
                        "wishlist_item_id": item.id,
                        "product": item.product.name,
                        "variants": ProductVariantSerializer(variants, many=True).data,
                    }
                )
            else:
                if cart is None:
                    cart = get_or_create_cart(request)
                if services.move_wishlist_item_to_cart(cart, item, variants[0]):
                    moved.append(item.product.name)

        return Response(
            {
                "moved": moved,
                "needs_selection": needs_selection,
                "unavailable": unavailable,
            },
            status=status.HTTP_200_OK,
        )


class UserOrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only order history for the authenticated user.
    GET /dashboard/orders/
    GET /dashboard/orders/{id}/
    """

    permission_classes = [IsAuthenticated]
    pagination_class = DashboardPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = UserOrderFilter
    search_fields = ["order_number", "items__product_name"]
    ordering_fields = ["created_at", "total", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .select_related("shipment")
            .prefetch_related("items")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return UserOrderDetailSerializer
        return UserOrderListSerializer


class UserReviewViewSet(viewsets.ModelViewSet):
    """
    User's own reviews — list, edit headline/comment/rating, delete.
    Reviews are matched by profile full_name since the Review model
    stores name as a plain string (no FK to User).
    """

    serializer_class = UserReviewSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = DashboardPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        try:
            full_name = self.request.user.profile.get_fullname()
        except Exception:
            return Review.objects.none()
        return Review.objects.filter(name=full_name).select_related("product")


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD VIEWS
# ═══════════════════════════════════════════════════════════════════════════════


class AdminOverviewView(APIView):
    """
    GET /dashboard/admin/overview/ — full analytics overview.

    ?period=7d|30d|90d|1y (default 30d), or
    ?period=custom&start=YYYY-MM-DD&end=YYYY-MM-DD (inclusive; ISO datetimes
    also accepted). A bad custom range returns 400 {"detail": ...}.
    """

    permission_classes = [IsAdminOrSuperuser]

    def get(self, request):
        period = request.query_params.get("period", "30d")
        try:
            data = services.get_admin_overview(
                period,
                request.query_params.get("start"),
                request.query_params.get("end"),
            )
        except services.InvalidDateRange as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        data["order_status_distribution"] = services.get_order_status_distribution()
        data["monthly_revenue"] = services.get_monthly_revenue()
        # Same window as the KPIs above (already validated by the call above).
        start, end = services.get_date_range(
            period,
            request.query_params.get("start"),
            request.query_params.get("end"),
        )
        data["top_products"] = services.get_top_products(start=start, end=end)
        data["user_stats"] = services.get_user_stats()
        data["product_stats"] = services.get_product_stats()
        data["recent_orders"] = services.get_recent_orders(8)
        return Response(data)


def _report_range(request):
    """
    (start, end) for a reporting endpoint from ?period=…&start=…&end=….

    Same params as the overview endpoint (7d/30d/90d/1y/custom). Unlike the
    overview, no `period` — or period=all — means all-time: (None, None).
    Raises services.InvalidDateRange for a bad custom range.
    """
    period = request.query_params.get("period")
    if period in (None, "", "all"):
        return None, None
    return services.get_date_range(
        period,
        request.query_params.get("start"),
        request.query_params.get("end"),
    )


class AdminRevenueStatsView(APIView):
    """
    GET /dashboard/admin/revenue-stats/ — detailed revenue chart data.

    top_products is all-time unless ?period=… (see _report_range) is given.
    """

    permission_classes = [IsAdminOrSuperuser]

    def get(self, request):
        months = int(request.query_params.get("months", 12))
        try:
            start, end = _report_range(request)
        except services.InvalidDateRange as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "monthly_revenue": services.get_monthly_revenue(months),
                "top_products": services.get_top_products(10, start, end),
            }
        )


def _parse_limit(request, default=10, maximum=100):
    """?limit=N as an int in [1, maximum]; ValueError (with message) otherwise."""
    raw = request.query_params.get("limit", str(default))
    try:
        limit = int(raw)
    except ValueError:
        limit = 0
    if not 1 <= limit <= maximum:
        raise ValueError(f"'limit' must be an integer between 1 and {maximum}.")
    return limit


class _AdminTopReportView(APIView):
    """
    Shared GET handling for the top-products / top-variants reports:
    ?limit=N (1–100, default 10) plus the period params of _report_range.
    Bad input returns 400 {"detail": …}.
    """

    permission_classes = [IsAdminOrSuperuser]
    result_key = ""

    def report(self, limit, start, end):  # pragma: no cover - abstract
        raise NotImplementedError

    def get(self, request):
        try:
            limit = _parse_limit(request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            start, end = _report_range(request)
        except services.InvalidDateRange as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({self.result_key: self.report(limit, start, end)})


class AdminTopProductsView(_AdminTopReportView):
    """GET /dashboard/admin/top-products/ — best sellers by product."""

    result_key = "top_products"

    def report(self, limit, start, end):
        return services.get_top_products(limit, start, end)


class AdminTopVariantsView(_AdminTopReportView):
    """GET /dashboard/admin/top-variants/ — best sellers by variant (SKU)."""

    result_key = "top_variants"

    def report(self, limit, start, end):
        return services.get_top_variants(limit, start, end)


class AdminUserStatsView(APIView):
    """GET /dashboard/admin/user-stats/ — user analytics."""

    permission_classes = [IsAdminOrSuperuser]

    def get(self, request):
        return Response(services.get_user_stats())


class AdminProductStatsView(APIView):
    """GET /dashboard/admin/product-stats/ — product analytics."""

    permission_classes = [IsAdminOrSuperuser]

    def get(self, request):
        return Response(services.get_product_stats())


class _AdminInventoryListView(APIView):
    """
    Shared GET handling for the actionable inventory lists.

    Response: {"count": <all matching variants>, **echoed params,
    "results": [...]}, where `results` is capped by ?limit=N (1–200,
    default 50) and `count` is the uncapped total — for stock lists the same
    number the overview's low_stock/out_of_stock summary shows — so the UI
    can say "showing 50 of 120".

    Each row carries `admin_url`: an absolute link to that variant's edit
    form in Django admin (ProductVariantAdmin) so it can be restocked or
    corrected directly; `product_id` is included for the React product admin
    page. (Restocking over the API is
    POST admin/variants/<variant_id>/adjust-stock/.)

    Subclasses may declare extra query params via extra_params(); they are
    passed to queryset()/rows() and echoed in the response. A ValueError
    from any parsing becomes a 400.
    """

    permission_classes = [IsAdminOrSuperuser]

    def extra_params(self, request) -> dict:
        return {}

    def queryset(self, **extra):  # pragma: no cover - abstract
        raise NotImplementedError

    def rows(self, limit, **extra):  # pragma: no cover - abstract
        raise NotImplementedError

    def get(self, request):
        try:
            limit = _parse_limit(request, default=50, maximum=200)
            extra = self.extra_params(request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        rows = self.rows(limit, **extra)
        for row in rows:
            row["admin_url"] = request.build_absolute_uri(
                reverse("admin:shop_productvariant_change", args=[row["variant_id"]])
            )
        return Response(
            {"count": self.queryset(**extra).count(), **extra, "results": rows}
        )


class AdminLowStockView(_AdminInventoryListView):
    """GET /dashboard/admin/inventory/low-stock/"""

    def queryset(self, **extra):
        return services.low_stock_variants_qs()

    def rows(self, limit, **extra):
        return services.get_low_stock_variants(limit)


class AdminOutOfStockView(_AdminInventoryListView):
    """GET /dashboard/admin/inventory/out-of-stock/"""

    def queryset(self, **extra):
        return services.out_of_stock_variants_qs()

    def rows(self, limit, **extra):
        return services.get_out_of_stock_variants(limit)


class AdminNearExpiryView(_AdminInventoryListView):
    """
    GET /dashboard/admin/inventory/near-expiry/?days=90

    Active variants expiring within `days` days (0–365, default 90 — the same
    window as the Django-admin "expiring within 90 days" filter), soonest
    first. Already-expired variants are NOT here; see AdminExpiredView.
    """

    def extra_params(self, request):
        raw = request.query_params.get("days", "90")
        try:
            days = int(raw)
        except ValueError:
            days = -1
        if not 0 <= days <= 365:
            raise ValueError("'days' must be an integer between 0 and 365.")
        return {"days": days}

    def queryset(self, days=90, **extra):
        return services.near_expiry_variants_qs(days)

    def rows(self, limit, days=90, **extra):
        return services.get_near_expiry_variants(days, limit)


class AdminExpiredView(_AdminInventoryListView):
    """
    GET /dashboard/admin/inventory/expired/

    Variants already past expiration_date but still is_active=True: stock the
    nightly sweep hasn't deactivated (yet). Rows overdue by more than a day
    or so suggest the sweep isn't running — the frontend should present this
    report as a warning, unlike the routine near-expiry list.
    """

    def queryset(self, **extra):
        return services.expired_still_active_variants_qs()

    def rows(self, limit, **extra):
        return services.get_expired_still_active_variants(limit)


class AdminCouponUsageView(APIView):
    """
    GET /dashboard/admin/promotions/coupon-usage/?limit=50

    Coupon performance report (see services.get_coupon_usage_report):
    {"count": <all coupons>, "results": [...]}, most-redeemed first, with
    `results` capped by ?limit=N (1–200, default 50). usage_rate_pct is null
    for unlimited coupons — display "Unlimited".
    """

    permission_classes = [IsAdminOrSuperuser]

    def get(self, request):
        try:
            limit = _parse_limit(request, default=50, maximum=200)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "count": services.coupon_usage_qs().count(),
                "results": services.get_coupon_usage_report(limit),
            }
        )


class BulkPriceUpdateView(APIView):
    """
    POST /dashboard/admin/products/bulk-price-update/

    Adjust ProductVariant.price (the real price since Epic 3 — not
    Product.price) by a percentage or fixed Rial amount across the active
    variants matching category_id AND brand_id AND variant_ids (whichever are
    given; at least one is required).

    dry_run defaults to TRUE: the response previews the change (affected_count
    is the true number of variants in scope; `preview` is capped at 50 rows)
    and nothing is written. Only an explicit dry_run=false commits.

    Commit behaviour:
    * Rows are locked, re-read and recomputed inside one transaction, so the
      result reflects the prices at commit time and all-or-nothing applies.
    * Each variant is saved through save() — NOT queryset.update() — so the
      existing ProductVariant signals run: the product-list cache is
      invalidated, ProductPriceSnapshot baselines stay current, and
      wishlist price-drop notifications are queued exactly as for any other
      price change. A bulk update() would silently skip all of that.
    * Variants whose price would not change are skipped (no save, no signal).
    * One PriceAdjustmentLog row records actor, parameters and counts.
    * If any new price would exceed MAX_RIAL_AMOUNT the request is rejected
      (400), in dry-run too, so a preview never promises what a commit
      can't do.
    """

    permission_classes = [IsAdminOrSuperuser]
    PREVIEW_LIMIT = 50

    @staticmethod
    def _scoped_variants(data):
        qs = ProductVariant.objects.filter(is_active=True)
        if data.get("category_id"):
            qs = qs.filter(product__category_id=data["category_id"])
        if data.get("brand_id"):
            qs = qs.filter(product__brand_id=data["brand_id"])
        if data.get("variant_ids"):
            qs = qs.filter(id__in=data["variant_ids"])
        return qs.select_related("product").order_by("id")

    @staticmethod
    def _too_expensive(plan):
        return [v.id for v, new_price in plan if new_price > MAX_RIAL_AMOUNT]

    def post(self, request):
        serializer = BulkPriceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data["dry_run"]:
            plan = services.plan_price_adjustment(
                self._scoped_variants(data), data["adjustment_type"], data["value"]
            )
            return self._respond_if_too_expensive(plan) or Response(
                {
                    "dry_run": True,
                    "affected_count": len(plan),
                    "changed_count": sum(1 for v, n in plan if n != v.price),
                    "preview": [
                        {
                            "variant_id": v.id,
                            "sku": v.sku,
                            "product_name": v.product.name,
                            "old_price": v.price,
                            "new_price": new_price,
                        }
                        for v, new_price in plan[: self.PREVIEW_LIMIT]
                    ],
                }
            )

        with transaction.atomic():
            # Lock in id order (orders lock variants the same way), then
            # recompute from the locked, current prices.
            locked = self._scoped_variants(data).select_for_update(of=("self",))
            plan = services.plan_price_adjustment(
                locked, data["adjustment_type"], data["value"]
            )
            too_expensive = self._respond_if_too_expensive(plan)
            if too_expensive:
                return too_expensive

            changes = []
            for variant, new_price in plan:
                if new_price == variant.price:
                    continue
                changes.append([variant.id, variant.price, new_price])
                variant.price = new_price
                variant.save(update_fields=["price", "updated_at"])

            log = PriceAdjustmentLog.objects.create(
                actor=request.user,
                adjustment_type=data["adjustment_type"],
                value=data["value"],
                category_id=data.get("category_id") or None,
                brand_id=data.get("brand_id") or None,
                variant_ids=data.get("variant_ids") or [],
                matched_count=len(plan),
                affected_count=len(changes),
                changes=changes,
            )
        return Response(
            {
                "dry_run": False,
                "matched_count": len(plan),
                "updated_count": len(changes),
                "log_id": log.id,
            }
        )

    def _respond_if_too_expensive(self, plan):
        offenders = self._too_expensive(plan)
        if not offenders:
            return None
        return Response(
            {
                "detail": (
                    f"{len(offenders)} variant(s) would exceed the maximum price "
                    f"of {MAX_RIAL_AMOUNT} Rial. Narrow the selection or reduce "
                    "the adjustment."
                ),
                "variant_ids": offenders[:20],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class BulkProductImportView(APIView):
    """
    POST /dashboard/admin/products/bulk-import/   (multipart: file, dry_run)

    Import products and variants from a .csv or .xlsx (schema, lookup rules
    and units: dashboard/product_import.py and docs/bulk-product-import.md;
    a ready-made file: GET admin/products/import-template/).

    Per-row, not all-or-nothing: rows that fail are reported with their
    spreadsheet row number while every valid row still goes through. A file
    that cannot be used at all (bad format, missing/unknown columns, too
    large) is a 400 on `file`.

    dry_run defaults to TRUE. The same code runs either way; a dry run rolls
    the transaction back at the end, so the preview shows exactly what a
    real import would do (including generated SKUs, which a rolled-back
    preview will not keep). Response: counts, `errors` (first 100) and
    `preview` (first 50 successful rows).
    """

    permission_classes = [IsAdminOrSuperuser]
    parser_classes = [MultiPartParser]
    ERROR_LIMIT = 100
    PREVIEW_LIMIT = 50

    def post(self, request):
        serializer = BulkProductImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dry_run = serializer.validated_data["dry_run"]

        try:
            rows = product_import.parse_import_file(serializer.validated_data["file"])
        except product_import.FileError as exc:
            return Response({"file": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)

        results = product_import.run_import(rows, request.user, dry_run)
        succeeded = results["succeeded"]
        errors = results["errors"]
        return Response(
            {
                "dry_run": dry_run,
                "total_rows": len(rows),
                "created_count": sum(1 for r in succeeded if r["action"] == "created"),
                "updated_count": sum(1 for r in succeeded if r["action"] == "updated"),
                "products_created_count": sum(
                    1 for r in succeeded if r["product_created"]
                ),
                "error_count": len(errors),
                "errors": errors[: self.ERROR_LIMIT],
                "preview": succeeded[: self.PREVIEW_LIMIT],
            }
        )


class ProductImportTemplateView(APIView):
    """
    GET /dashboard/admin/products/import-template/?file_type=csv|xlsx

    A blank import file: the exact header row (generated from the same
    IMPORT_COLUMNS the importer validates against) plus one example row.
    The .xlsx also carries an "instructions" sheet; only its first sheet is
    imported. (Not `?format=` — DRF reserves that for renderer selection.)
    """

    permission_classes = [IsAdminOrSuperuser]

    FILES = {
        "csv": (
            "text/csv; charset=utf-8",
            "product-import-template.csv",
            product_import.build_template_csv,
        ),
        "xlsx": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "product-import-template.xlsx",
            product_import.build_template_xlsx,
        ),
    }

    def get(self, request):
        file_type = request.query_params.get("file_type", "csv").lower()
        if file_type not in self.FILES:
            return Response(
                {"file_type": "Must be 'csv' or 'xlsx'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        content_type, filename, build = self.FILES[file_type]
        response = HttpResponse(build(), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class AdminVariantAdjustStockView(APIView):
    """POST /dashboard/admin/variants/{id}/adjust-stock/"""

    permission_classes = [IsAdminOrSuperuser]

    def post(self, request, pk):
        variant = get_object_or_404(ProductVariant, pk=pk)
        serializer = AdjustStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delta = serializer.validated_data["quantity_delta"]
        reason = serializer.validated_data["reason"]
        note = serializer.validated_data.get("note", "")

        with transaction.atomic():
            locked_variant = ProductVariant.objects.select_for_update().get(
                pk=variant.pk
            )
            new_stock = locked_variant.stock + delta
            if new_stock < 0:
                return Response(
                    {
                        "quantity_delta": "This adjustment would result in negative stock."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            locked_variant.stock = new_stock
            locked_variant.save(update_fields=["stock"])
            StockMovement.objects.create(
                variant=locked_variant,
                reason=reason,
                quantity_delta=delta,
                stock_after=locked_variant.stock,
                actor=request.user,
                note=note,
            )
        return Response(
            {"id": locked_variant.id, "stock": locked_variant.stock},
            status=status.HTTP_200_OK,
        )


class AdminUserViewSet(viewsets.ModelViewSet):
    """
    Admin user management.
    GET   /dashboard/admin/users/
    GET   /dashboard/admin/users/{id}/
    PATCH /dashboard/admin/users/{id}/ — toggle is_active / type
    """

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = AdminUserFilter
    search_fields = ["email", "profile__first_name", "profile__last_name"]
    ordering_fields = ["created_date", "email", "type"]
    ordering = ["-created_date"]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return User.objects.select_related("profile").all()

    def get_serializer_class(self):
        if self.action in ("partial_update", "update"):
            return AdminUserUpdateSerializer
        return AdminUserSerializer

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class AdminProductViewSet(viewsets.ModelViewSet):
    """Admin CRUD for products."""

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = AdminProductFilter
    search_fields = ["name", "short_description", "brand__name", "category__name"]
    ordering_fields = [
        "name",
        "price",
        "stock",
        "rating",
        "created_at",
        "reviews_count",
    ]
    ordering = ["-created_at"]
    serializer_class = AdminProductSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Product.objects.select_related("category", "brand").prefetch_related(
            "images", "order_items"
        )


class AdminCategoryViewSet(viewsets.ModelViewSet):
    """Admin CRUD for categories."""

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
    serializer_class = AdminCategorySerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Category.objects.select_related("parent").prefetch_related("products")


class AdminBrandViewSet(viewsets.ModelViewSet):
    """Admin CRUD for brands."""

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name"]
    ordering = ["name"]
    serializer_class = AdminBrandSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Brand.objects.prefetch_related("products")


class Echo:
    """Write-target that just returns what it's given, for streaming CSV."""

    def write(self, value):
        return value


class CSVPassthroughRenderer(BaseRenderer):
    """
    Exists only so DRF's content negotiation accepts `Accept: text/csv` on the
    export action (otherwise scripted clients asking for CSV get a 406). The
    CSV itself is a StreamingHttpResponse and never goes through a renderer;
    this only ever renders error responses (403, 400...), as JSON.
    """

    media_type = "text/csv"
    format = "csv"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return JSONRenderer().render(data, accepted_media_type, renderer_context)


# Spreadsheet apps execute cells that start with these as formulas. Customer
# names/emails are user-supplied, so such cells are prefixed with a quote.
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
# ...but a plain number/phone like "+989121234567" or "-12.50" is not a formula.
_PLAIN_NUMBER_RE = re.compile(r"[+-]?[\d\s().-]+")


def _csv_safe(value):
    if isinstance(value, str) and value.startswith(_CSV_FORMULA_PREFIXES):
        if not _PLAIN_NUMBER_RE.fullmatch(value):
            return "'" + value
    return value


class XLSXPassthroughRenderer(BaseRenderer):
    """
    Lets `?format=xlsx` / `Accept: …spreadsheetml.sheet` pass DRF's content
    negotiation on the catalog export (same idea as CSVPassthroughRenderer).
    The workbook itself is returned as a plain HttpResponse; this only ever
    renders error responses, as JSON.
    """

    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    format = "xlsx"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return JSONRenderer().render(data, accepted_media_type, renderer_context)


class BulkProductExportView(APIView):
    """
    GET /dashboard/admin/products/bulk-export/?format=csv|xlsx   (default csv)

    The catalog as a spreadsheet in EXACTLY the schema the bulk importer
    expects (product_import.IMPORT_COLUMNS), so export → edit in Excel →
    re-import round-trips: one row per VARIANT, each carrying its SKU (so a
    re-import updates it instead of duplicating it) and repeating its
    product's shared attributes. (`?file_type=` is accepted too, matching the
    import-template endpoint.)

    Filters — the same params as the admin product list:
      category, brand, is_sale, is_new      (AdminProductFilter, on the product)
      search                                 (the list's SearchFilter fields)
      min_price, max_price, in_stock         applied to the VARIANTS — see
                                             AdminVariantExportFilter for why
                                             not the product-list versions.
    A malformed filter is a 400, never a silent "export everything".
    Inactive variants are included (a backup/edit round trip must not drop
    them). Rows are ordered by product name, then id, so a product's variants
    sit together.

    CSV is streamed (UTF-8 with BOM for Excel) in chunks, so catalog size is
    not a memory concern; cells starting with = + - @ are quote-prefixed like
    the order export, and the importer strips that prefix again.
    XLSX is built in memory — a known limit: past MAX_XLSX_EXPORT_ROWS the
    request is refused with a pointer to CSV (or to a narrower filter).
    Note the importer accepts at most MAX_IMPORT_ROWS (1,000) rows per file:
    a bigger export has to be filtered into pieces to be re-imported.
    """

    permission_classes = [IsAdminOrSuperuser]
    renderer_classes = [JSONRenderer, CSVPassthroughRenderer, XLSXPassthroughRenderer]
    VARIANT_LEVEL_PARAMS = ("min_price", "max_price", "in_stock")
    BOOLEAN_PARAMS = ("is_sale", "is_new", "in_stock")
    XLSX_TYPE = XLSXPassthroughRenderer.media_type

    def get(self, request):
        # Explicit ?file_type= wins; otherwise whatever ?format= / Accept
        # negotiated (a renderer only exists for csv and xlsx); default CSV.
        fmt = request.query_params.get("file_type")
        if fmt is None:
            negotiated = getattr(request.accepted_renderer, "format", "")
            fmt = negotiated if negotiated in ("csv", "xlsx") else "csv"
        fmt = fmt.lower()
        if fmt not in ("csv", "xlsx"):
            return Response(
                {"file_type": "Must be 'csv' or 'xlsx'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        variants = self._filtered_variants(request)
        labels = product_import.export_category_labels()
        stamp = timezone.now().strftime("%Y-%m-%d")
        if fmt == "xlsx":
            return self._export_xlsx(variants, labels, stamp)
        return self._export_csv(variants, labels, stamp)

    def _filtered_variants(self, request):
        # Product-level filters. The variant-level params are removed first:
        # AdminProductFilter would apply them to the legacy Product fields.
        params = request.query_params.copy()
        # django-filter silently ignores a boolean it doesn't recognise, which
        # here would mean "ture" → the WHOLE catalog. Be strict instead.
        for name in self.BOOLEAN_PARAMS:
            if name in params:
                value = params[name].strip().lower()
                if value not in ("true", "false"):
                    raise ValidationError({name: ["Must be 'true' or 'false'."]})
                params[name] = value
        variant_params = params.copy()
        for name in self.VARIANT_LEVEL_PARAMS:
            params.pop(name, None)

        product_filter = AdminProductFilter(params, queryset=Product.objects.all())
        if not product_filter.is_valid():
            raise ValidationError(
                {k: list(v) for k, v in product_filter.errors.items()}
            )
        products = filters.SearchFilter().filter_queryset(
            request,
            product_filter.qs,
            SimpleNamespace(search_fields=AdminProductViewSet.search_fields),
        )

        variants = ProductVariant.objects.filter(product__in=products.values("pk"))
        variant_filter = AdminVariantExportFilter(variant_params, queryset=variants)
        if not variant_filter.is_valid():
            raise ValidationError(
                {k: list(v) for k, v in variant_filter.errors.items()}
            )
        return variant_filter.qs.select_related(
            "product", "product__brand", "color"
        ).order_by("product__name", "product_id", "id")

    def _export_csv(self, variants, labels, stamp):
        names = product_import.IMPORT_COLUMN_NAMES

        def row_generator():
            writer = csv.writer(Echo())
            # BOM so Excel reads the UTF-8 file correctly (Persian text).
            yield "\ufeff" + writer.writerow(names)
            for variant in variants.iterator(chunk_size=500):
                cells = product_import.export_row(variant, labels)
                yield writer.writerow(
                    [_csv_safe(product_import.csv_text(cells[name])) for name in names]
                )

        response = StreamingHttpResponse(
            row_generator(), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="catalog_export_{stamp}.csv"'
        )
        return response

    def _export_xlsx(self, variants, labels, stamp):
        count = variants.count()
        if count > product_import.MAX_XLSX_EXPORT_ROWS:
            return Response(
                {
                    "detail": (
                        f"{count} variants is too many for an Excel export (limit "
                        f"{product_import.MAX_XLSX_EXPORT_ROWS}). Use format=csv, "
                        "which streams, or narrow the export with filters."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = product_import.build_export_xlsx(
            product_import.export_row(v, labels)
            for v in variants.iterator(chunk_size=500)
        )
        response = HttpResponse(data, content_type=self.XLSX_TYPE)
        response["Content-Disposition"] = (
            f'attachment; filename="catalog_export_{stamp}.xlsx"'
        )
        return response


class AdminOrderViewSet(viewsets.ModelViewSet):
    """
    Admin order management.
    Supports listing, detail, status update.
    DELETE is intentionally disabled (orders should not be hard-deleted).
    """

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = AdminOrderFilter
    search_fields = ["order_number", "email", "first_name", "last_name", "phone"]
    ordering_fields = ["created_at", "total", "status"]
    ordering = ["-created_at"]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return Order.objects.select_related("user", "user__profile").prefetch_related(
            "items"
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminOrderDetailSerializer
        if self.action in ("partial_update", "update"):
            return AdminOrderStatusSerializer
        return AdminOrderListSerializer

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def perform_update(self, serializer):
        """
        Cancelling must go through the shared cancel_order() service so an
        admin cancellation restores stock exactly like the customer path
        (a bare serializer.save() would flip the status with no stock
        consequence). Every other transition is re-validated under a row
        lock, so a concurrent change can't be silently overwritten.
        """
        order = serializer.instance
        new_status = serializer.validated_data.get("status")

        if (
            new_status == Order.Status.CANCELLED
            and order.status != Order.Status.CANCELLED
        ):
            try:
                cancel_order(
                    order,
                    actor=self.request.user,
                    note=f"Cancelled by admin: order {order.order_number}",
                )
            except ValueError as exc:
                raise ValidationError({"status": [str(exc)]})
            return

        with transaction.atomic():
            locked = Order.objects.select_for_update().get(pk=order.pk)
            if new_status is not None and not is_valid_transition(
                locked.status, new_status
            ):
                raise ValidationError(
                    {
                        "status": [
                            f"Cannot change status from '{locked.status}' to '{new_status}'."
                        ]
                    }
                )
            serializer.save()

    CSV_MONEY_FIELDS = frozenset(
        {"subtotal", "shipping_cost", "tax", "discount", "total"}
    )

    CSV_EXPORT_FIELDS = [
        "order_number",
        "created_at",
        "status",
        "first_name",
        "last_name",
        "email",
        "phone",
        "shipping_city",
        "shipping_state",
        "shipping_country",
        "payment_method",
        "subtotal",
        "shipping_cost",
        "tax",
        "discount",
        "total",
    ]

    @action(
        detail=False,
        methods=["get"],
        renderer_classes=[JSONRenderer, CSVPassthroughRenderer],
    )
    def export_csv(self, request):
        """
        Stream the orders matching the list endpoint's filters/search/ordering
        as a CSV download (no pagination: the whole filtered set).
        """
        # filter_queryset runs eagerly, so a bad query param is a normal 400
        # before any streaming starts. The list view's joins/prefetches
        # (user, profile, items) aren't used by the CSV, so drop them.
        queryset = (
            self.filter_queryset(self.get_queryset())
            .select_related(None)
            .prefetch_related(None)
        )
        fields = self.CSV_EXPORT_FIELDS
        # Money columns carry their unit in the header (ADR 0001, I-8): a
        # spreadsheet user must never have to guess whether 3141660 is Rial,
        # Toman or dollars. Values are the stored integers, untouched.
        header = [
            f"{name}_rial" if name in self.CSV_MONEY_FIELDS else name for name in fields
        ]

        def row_generator():
            writer = csv.writer(Echo())
            # BOM so Excel reads the UTF-8 file correctly (Persian names).
            yield "\ufeff" + writer.writerow(header)
            for order in queryset.only(*fields).iterator(chunk_size=500):
                row = []
                for name in fields:
                    value = getattr(order, name)
                    if name == "created_at":
                        value = value.isoformat()
                    row.append(_csv_safe(value))
                yield writer.writerow(row)

        filename = f"orders_export_{timezone.now().strftime('%Y-%m-%d')}.csv"
        response = StreamingHttpResponse(
            row_generator(), content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class AdminReviewViewSet(viewsets.ModelViewSet):
    """
    Admin review moderation queue.

    GET    /admin/reviews/?status=pending|approved   — list (all when omitted)
    GET    /admin/reviews/?has_reports=true          — only reviews with
                                                       unresolved customer reports
    PATCH  /admin/reviews/<id>/  {"is_approved": bool} — approve / unapprove
    PATCH  /admin/reviews/<id>/  {"store_response": str} — post / edit / clear the
                                 store's public reply (stamps store_response_at)
    POST   /admin/reviews/<id>/resolve-reports/        — mark its reports resolved
    DELETE /admin/reviews/<id>/                        — remove spam/abuse

    Only `is_approved` and `store_response` are writable (see AdminReviewSerializer). Every change
    that affects which reviews are public also refreshes the product's
    denormalised rating/reviews_count.
    """

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "comment", "headline", "product__name", "user__email"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]
    serializer_class = AdminReviewSerializer
    # No create/PUT via the admin API. POST is enabled only for the
    # resolve-reports action; create() below rejects it on the collection.
    # DELETE stays (spam removal; the admin reviews page already uses it).
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Review.objects.select_related("product", "user").annotate(
            unresolved_report_count=Count(
                "reports", filter=Q(reports__resolved=False), distinct=True
            )
        )
        params = self.request.query_params
        status_param = params.get("status")
        if status_param == "pending":
            qs = qs.filter(is_approved=False)
        elif status_param == "approved":
            qs = qs.filter(is_approved=True)
        if params.get("has_reports", "").lower() == "true":
            qs = qs.filter(unresolved_report_count__gt=0)
        return qs

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed(request.method)

    def perform_update(self, serializer):
        extra = {}
        if "store_response" in serializer.validated_data:
            new_response = serializer.validated_data["store_response"]
            # Only a real change re-stamps the response time; re-saving the
            # same text must not make an old reply look freshly posted.
            # Clearing the response clears its timestamp.
            if new_response != serializer.instance.store_response:
                extra["store_response_at"] = timezone.now() if new_response else None
        instance = serializer.save(**extra)
        refresh_product_review_stats(instance.product)

    def perform_destroy(self, instance):
        product = instance.product
        instance.delete()
        refresh_product_review_stats(product)

    @action(detail=True, methods=["post"], url_path="resolve-reports")
    def resolve_reports(self, request, pk=None):
        """
        Mark every unresolved report on this review as resolved, i.e. an admin
        has looked at them. Deliberately does NOT touch `is_approved`: a review
        can be reported and still deserve to stay hidden, and re-approving is
        an explicit separate PATCH.
        """
        review = self.get_object()
        resolved = review.reports.filter(resolved=False).update(resolved=True)
        return Response({"resolved": resolved}, status=status.HTTP_200_OK)


class AdminContactMessageViewSet(viewsets.ModelViewSet):
    """Admin contact-message inbox — list and delete only."""

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "email", "subject", "message"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
    serializer_class = AdminContactMessageSerializer
    http_method_names = ["get", "delete", "head", "options"]

    def get_queryset(self):
        return ContactMessage.objects.all()


# ─── Admin: Blog Categories ────────────────────────────────────────────────────


class AdminBlogCategoryViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD for blog categories.
    GET    /dashboard/admin/blog/categories/
    POST   /dashboard/admin/blog/categories/
    PATCH  /dashboard/admin/blog/categories/{id}/
    DELETE /dashboard/admin/blog/categories/{id}/
    """

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AdminCategoryFilter
    search_fields = ["name"]
    ordering_fields = ["name"]
    ordering = ["name"]
    serializer_class = BlogCategorySerializer

    def get_queryset(self):
        return BlogCategory.objects.prefetch_related("posts").all()


# ─── Admin: Blog Posts ─────────────────────────────────────────────────────────


class AdminBlogPostViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD for blog posts.
    GET    /dashboard/admin/blog/posts/
    POST   /dashboard/admin/blog/posts/
    PATCH  /dashboard/admin/blog/posts/{id}/
    DELETE /dashboard/admin/blog/posts/{id}/
    """

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = AdminPostFilter
    search_fields = ["title", "excerpt", "content", "author__email", "category__name"]
    ordering_fields = [
        "created_at",
        "updated_at",
        "published_at",
        "views_count",
        "read_time",
        "title",
    ]
    ordering = ["-created_at"]
    serializer_class = AdminPostSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return BlogPost.objects.select_related(
            "author", "author__profile", "category"
        ).prefetch_related("comments")

    def perform_create(self, serializer):
        # Auto-set author to current admin user
        serializer.save(author=self.request.user)


# ─── Admin: Blog Comments ──────────────────────────────────────────────────────


class AdminBlogCommentViewSet(viewsets.ModelViewSet):
    """
    Admin comment moderation — list, approve/disapprove, delete.
    GET    /dashboard/admin/blog/comments/
    PATCH  /dashboard/admin/blog/comments/{id}/   (update is_approved)
    DELETE /dashboard/admin/blog/comments/{id}/
    """

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = AdminCommentFilter
    search_fields = ["name", "email", "body", "post__title"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
    serializer_class = AdminCommentSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return BlogComment.objects.select_related("post", "parent").prefetch_related(
            "replies"
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


# ─── Admin: Coupons ────────────────────────────────────────────────────────────


class AdminCouponViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD for coupons.
    GET    /dashboard/admin/coupons/
    POST   /dashboard/admin/coupons/
    GET    /dashboard/admin/coupons/{id}/
    PATCH  /dashboard/admin/coupons/{id}/   (PATCH {"is_active": false} deactivates)
    DELETE /dashboard/admin/coupons/{id}/   (only if the coupon was never redeemed)
    """

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    serializer_class = AdminCouponSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["code"]
    ordering_fields = ["created_at", "valid_from", "valid_until"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Coupon.objects.prefetch_related("categories", "products")

    def destroy(self, request, *args, **kwargs):
        coupon = self.get_object()
        # CouponRedemption.coupon is on_delete=CASCADE, so deleting a used
        # coupon would silently erase its usage history (and with it the
        # max_uses / uses_per_user counts and the order <-> coupon link).
        # Deactivating is the way to retire a coupon that has been used.
        if coupon.redemptions.exists():
            return Response(
                {
                    "detail": (
                        "This coupon has been redeemed and can't be deleted "
                        "without erasing its usage history. Deactivate it instead."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        self.perform_destroy(coupon)
        return Response(status=status.HTTP_204_NO_CONTENT)
