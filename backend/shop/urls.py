from django.urls import path

from .views import (
    BrandListView,
    CategoryListView,
    ColorListView,
    ProductDetailView,
    ProductListView,
    ProductReviewCreateView,
    RelatedProductsView,
)

urlpatterns = [
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("brands/", BrandListView.as_view(), name="brand-list"),
    path("colors/", ColorListView.as_view(), name="color-list"),
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/<slug:slug>/", ProductDetailView.as_view(), name="product-detail"),
    path(
        "products/<slug:slug>/related/",
        RelatedProductsView.as_view(),
        name="product-related",
    ),
    # POST a new review for a specific product
    path(
        "products/<slug:slug>/reviews/",
        ProductReviewCreateView.as_view(),
        name="product-review-create",
    ),
]
