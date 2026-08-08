from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "dashboard"

router = DefaultRouter()

# ── User-facing viewsets ──────────────────────────────────────────────────────
router.register(r"addresses", views.AddressViewSet, basename="address")
router.register(r"wishlist", views.WishlistViewSet, basename="wishlist")
router.register(r"orders", views.UserOrderViewSet, basename="user-order")
router.register(r"reviews", views.UserReviewViewSet, basename="user-review")

# ── Admin viewsets ────────────────────────────────────────────────────────────
router.register(r"admin/users", views.AdminUserViewSet, basename="admin-user")
router.register(r"admin/products", views.AdminProductViewSet, basename="admin-product")
router.register(
    r"admin/categories", views.AdminCategoryViewSet, basename="admin-category"
)
router.register(r"admin/brands", views.AdminBrandViewSet, basename="admin-brand")
router.register(r"admin/orders", views.AdminOrderViewSet, basename="admin-order")
router.register(r"admin/reviews", views.AdminReviewViewSet, basename="admin-review")
router.register(
    r"admin/messages", views.AdminContactMessageViewSet, basename="admin-message"
)
router.register(
    r"admin/blog/categories",
    views.AdminBlogCategoryViewSet,
    basename="admin-blog-category",
)
router.register(
    r"admin/blog/posts", views.AdminBlogPostViewSet, basename="admin-blog-post"
)
router.register(
    r"admin/blog/comments", views.AdminBlogCommentViewSet, basename="admin-blog-comment"
)

urlpatterns = [
    # ── User dashboard ────────────────────────────────────────────────────────
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path(
        "profile/upload-avatar/", views.AvatarUploadView.as_view(), name="avatar-upload"
    ),
    path(
        "change-password/", views.ChangePasswordView.as_view(), name="change-password"
    ),
    path(
        "notifications/", views.NotificationSettingsView.as_view(), name="notifications"
    ),
    path("summary/", views.UserSummaryView.as_view(), name="summary"),
    # ── Admin analytics ───────────────────────────────────────────────────────
    path("admin/overview/", views.AdminOverviewView.as_view(), name="admin-overview"),
    path(
        "admin/revenue-stats/",
        views.AdminRevenueStatsView.as_view(),
        name="admin-revenue",
    ),
    path(
        "admin/user-stats/", views.AdminUserStatsView.as_view(), name="admin-user-stats"
    ),
    path(
        "admin/product-stats/",
        views.AdminProductStatsView.as_view(),
        name="admin-product-stats",
    ),
    path("", include(router.urls)),
]
