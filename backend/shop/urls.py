from django.urls import path

from .views import (
    BrandListView,
    CategoryListView,
    ColorListView,
    FrequentlyBoughtTogetherView,
    HomeRecommendationsView,
    ProductDetailView,
    ProductFacetCountsView,
    ProductListView,
    ProductReviewCreateView,
    ProductSuggestView,
    RelatedProductsView,
    ReviewReportCreateView,
    StockAlertSubscriptionView,
)

urlpatterns = [
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("brands/", BrandListView.as_view(), name="brand-list"),
    path("colors/", ColorListView.as_view(), name="color-list"),
    path("products/", ProductListView.as_view(), name="product-list"),
    # MUST stay above products/<slug:slug>/ — "suggest" is a valid slug, so
    # listed after it the detail view would swallow this URL and 404.
    path("products/suggest/", ProductSuggestView.as_view(), name="product-suggest"),
    path(
        "products/facet-counts/",
        ProductFacetCountsView.as_view(),
        name="product-facet-counts",
    ),
    # MUST stay above products/<slug:slug>/ — "home-recommendations" is a valid
    # slug, so listed after it the detail view would swallow this URL (405 on POST).
    path(
        "products/home-recommendations/",
        HomeRecommendationsView.as_view(),
        name="home-recommendations",
    ),
    path("products/<slug:slug>/", ProductDetailView.as_view(), name="product-detail"),
    path(
        "products/<slug:slug>/related/",
        RelatedProductsView.as_view(),
        name="product-related",
    ),
    path(
        "products/<slug:slug>/frequently-bought-together/",
        FrequentlyBoughtTogetherView.as_view(),
        name="product-fbt",
    ),
    # POST a new review for a specific product
    path(
        "products/<slug:slug>/reviews/",
        ProductReviewCreateView.as_view(),
        name="product-review-create",
    ),
    # POST to report a published review (spam / offensive / irrelevant / other)
    path(
        "reviews/<int:review_id>/report/",
        ReviewReportCreateView.as_view(),
        name="review-report",
    ),
    # POST to subscribe / DELETE to unsubscribe from a variant's restock alert
    path(
        "products/variants/<int:variant_id>/notify-me/",
        StockAlertSubscriptionView.as_view(),
        name="stock-alert-subscription",
    ),
]
