import csv
import re

from accounts.models import Profile
from blog.models import Category as BlogCategory
from blog.models import Comment as BlogComment
from blog.models import Post as BlogPost
from contact.models import ContactMessage
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from order.models import Order
from order.services.cancellation import cancel_order
from order.services.state_machine import is_valid_transition
from promotions.models import Coupon
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from shop.models import Brand, Category, Product, ProductVariant, Review, StockMovement

from . import services
from .filters import (
    AdminCategoryFilter,
    AdminCommentFilter,
    AdminOrderFilter,
    AdminPostFilter,
    AdminProductFilter,
    AdminUserFilter,
    UserOrderFilter,
)
from .models import Address, Wishlist
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
    ChangePasswordSerializer,
    NotificationSettingsSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    UserOrderDetailSerializer,
    UserOrderListSerializer,
    UserReviewSerializer,
    WishlistSerializer,
)

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
        return Response({"detail": "Password changed successfully."})


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
    Wishlist management.
    GET    /dashboard/wishlist/
    POST   /dashboard/wishlist/         body: { product_id: <int> }
    DELETE /dashboard/wishlist/{id}/
    """

    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).select_related(
            "product", "product__category", "product__brand"
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_object(self):
        obj = get_object_or_404(Wishlist, pk=self.kwargs["pk"], user=self.request.user)
        return obj


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
    """GET /dashboard/admin/overview/ — full analytics overview."""

    permission_classes = [IsAdminOrSuperuser]

    def get(self, request):
        period = request.query_params.get("period", "30d")
        data = services.get_admin_overview(period)
        data["order_status_distribution"] = services.get_order_status_distribution()
        data["monthly_revenue"] = services.get_monthly_revenue()
        data["top_products"] = services.get_top_products()
        data["user_stats"] = services.get_user_stats()
        data["product_stats"] = services.get_product_stats()
        data["recent_orders"] = services.get_recent_orders(8)
        return Response(data)


class AdminRevenueStatsView(APIView):
    """GET /dashboard/admin/revenue-stats/ — detailed revenue chart data."""

    permission_classes = [IsAdminOrSuperuser]

    def get(self, request):
        months = int(request.query_params.get("months", 12))
        return Response(
            {
                "monthly_revenue": services.get_monthly_revenue(months),
                "top_products": services.get_top_products(10),
            }
        )


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

        def row_generator():
            writer = csv.writer(Echo())
            # BOM so Excel reads the UTF-8 file correctly (Persian names).
            yield "\ufeff" + writer.writerow(fields)
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
    """Admin review moderation — list and delete only."""

    permission_classes = [IsAdminOrSuperuser]
    pagination_class = DashboardPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["name", "comment", "headline", "product__name"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]
    serializer_class = AdminReviewSerializer
    http_method_names = ["get", "delete", "head", "options"]

    def get_queryset(self):
        return Review.objects.select_related("product")


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
