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
router.register(r"admin/coupons", views.AdminCouponViewSet, basename="admin-coupon")
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
    path(
        "customer/payment-history/",
        views.UserPaymentHistoryView.as_view(),
        name="payment-history",
    ),
    # ── Admin analytics ───────────────────────────────────────────────────────
    path("admin/overview/", views.AdminOverviewView.as_view(), name="admin-overview"),
    path(
        "admin/revenue-stats/",
        views.AdminRevenueStatsView.as_view(),
        name="admin-revenue",
    ),
    path(
        "admin/top-products/",
        views.AdminTopProductsView.as_view(),
        name="admin-top-products",
    ),
    path(
        "admin/top-variants/",
        views.AdminTopVariantsView.as_view(),
        name="admin-top-variants",
    ),
    path(
        "admin/user-stats/", views.AdminUserStatsView.as_view(), name="admin-user-stats"
    ),
    path(
        "admin/product-stats/",
        views.AdminProductStatsView.as_view(),
        name="admin-product-stats",
    ),
    path(
        "admin/inventory/low-stock/",
        views.AdminLowStockView.as_view(),
        name="admin-inventory-low-stock",
    ),
    path(
        "admin/inventory/out-of-stock/",
        views.AdminOutOfStockView.as_view(),
        name="admin-inventory-out-of-stock",
    ),
    path(
        "admin/inventory/near-expiry/",
        views.AdminNearExpiryView.as_view(),
        name="admin-inventory-near-expiry",
    ),
    path(
        "admin/inventory/expired/",
        views.AdminExpiredView.as_view(),
        name="admin-inventory-expired",
    ),
    path(
        "admin/promotions/coupon-usage/",
        views.AdminCouponUsageView.as_view(),
        name="admin-coupon-usage",
    ),
    path(
        "admin/products/bulk-price-update/",
        views.BulkPriceUpdateView.as_view(),
        name="admin-bulk-price-update",
    ),
    path(
        "admin/products/bulk-import/",
        views.BulkProductImportView.as_view(),
        name="admin-product-bulk-import",
    ),
    path(
        "admin/products/bulk-export/",
        views.BulkProductExportView.as_view(),
        name="admin-product-bulk-export",
    ),
    path(
        "admin/products/import-template/",
        views.ProductImportTemplateView.as_view(),
        name="admin-product-import-template",
    ),
    path(
        "admin/variants/<int:pk>/adjust-stock/",
        views.AdminVariantAdjustStockView.as_view(),
        name="admin-variant-adjust-stock",
    ),
    path("", include(router.urls)),
]
