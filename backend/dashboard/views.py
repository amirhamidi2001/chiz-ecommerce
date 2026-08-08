from accounts.models import Profile
from blog.models import Category as BlogCategory
from blog.models import Comment as BlogComment
from blog.models import Post as BlogPost
from contact.models import ContactMessage
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from order.models import Order
from rest_framework import filters, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from shop.models import Brand, Category, Product, Review

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
    AdminBrandSerializer,
    AdminCategorySerializer,
    AdminCommentSerializer,
    AdminContactMessageSerializer,
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
