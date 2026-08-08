from unittest.mock import MagicMock

import pytest
from django.test import RequestFactory
from shop.serializers import (
    BrandSerializer,
    CategoryMinimalSerializer,
    CategorySerializer,
    ColorSerializer,
    ProductColorSerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    ReviewSerializer,
)
from shop.tests.factories import (
    BrandFactory,
    CategoryFactory,
    ColorFactory,
    ProductColorFactory,
    ProductFactory,
    ProductImageFactory,
    ReviewFactory,
)


def make_request():
    """Return a mock request with a working build_absolute_uri."""
    rf = RequestFactory()
    request = rf.get("/")
    return request


# ═══════════════════════════════════════════════════════════════════════════════
# CategorySerializer
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestCategorySerializer:

    def test_contains_expected_fields(self):
        cat = CategoryFactory()
        data = CategorySerializer(cat).data
        for field in (
            "id",
            "name",
            "slug",
            "parent",
            "image",
            "children",
            "created_at",
        ):
            assert field in data, f"Missing field: {field}"

    def test_children_are_nested(self):
        parent = CategoryFactory(name="Electronics")
        child = CategoryFactory(name="Smartphones", parent=parent)
        data = CategorySerializer(parent).data
        assert len(data["children"]) == 1
        assert data["children"][0]["name"] == "Smartphones"

    def test_root_category_has_no_parent(self):
        cat = CategoryFactory()
        data = CategorySerializer(cat).data
        assert data["parent"] is None

    def test_minimal_serializer_only_has_id_name_slug(self):
        cat = CategoryFactory()
        data = CategoryMinimalSerializer(cat).data
        assert set(data.keys()) == {"id", "name", "slug"}


# ═══════════════════════════════════════════════════════════════════════════════
# BrandSerializer
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestBrandSerializer:

    def test_contains_expected_fields(self):
        brand = BrandFactory()
        data = BrandSerializer(brand).data
        for field in ("id", "name", "slug", "logo"):
            assert field in data

    def test_slug_value_matches(self):
        brand = BrandFactory(name="Nike", slug="nike")
        data = BrandSerializer(brand).data
        assert data["slug"] == "nike"


# ═══════════════════════════════════════════════════════════════════════════════
# ColorSerializer
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestColorSerializer:

    def test_contains_expected_fields(self):
        color = ColorFactory(name="Black", hex_code="#000000")
        data = ColorSerializer(color).data
        assert data["name"] == "Black"
        assert data["hex_code"] == "#000000"


# ═══════════════════════════════════════════════════════════════════════════════
# ReviewSerializer
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestReviewSerializer:

    def test_contains_expected_fields(self):
        review = ReviewFactory()
        data = ReviewSerializer(review).data
        for field in ("id", "name", "rating", "headline", "comment", "created_at"):
            assert field in data

    def test_rating_value_in_1_to_5(self):
        review = ReviewFactory(rating=4)
        data = ReviewSerializer(review).data
        assert data["rating"] == 4


# ═══════════════════════════════════════════════════════════════════════════════
# ProductListSerializer
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductListSerializer:

    def test_expected_fields_present(self):
        product = ProductFactory()
        request = make_request()
        data = ProductListSerializer(product, context={"request": request}).data
        expected = {
            "id",
            "name",
            "slug",
            "short_description",
            "price",
            "original_price",
            "discount_percent",
            "stock",
            "rating",
            "reviews_count",
            "is_new",
            "is_sale",
            "thumbnail_url",
            "category",
            "brand",
            "created_at",
        }
        assert expected.issubset(set(data.keys()))

    def test_reviews_not_in_list_serializer(self):
        product = ProductFactory()
        data = ProductListSerializer(product).data
        assert "reviews" not in data

    def test_discount_percent_calculated(self):
        product = ProductFactory(price=80, original_price=100)
        data = ProductListSerializer(product, context={"request": make_request()}).data
        assert data["discount_percent"] == 20

    def test_thumbnail_url_built_with_request(self):
        """When a request is in context, thumbnail_url is an absolute URL."""
        product = ProductFactory()
        # thumbnail is None so thumbnail_url should be None
        data = ProductListSerializer(product, context={"request": make_request()}).data
        assert data["thumbnail_url"] is None

    def test_category_is_nested_minimal(self):
        product = ProductFactory()
        data = ProductListSerializer(product).data
        assert set(data["category"].keys()) == {"id", "name", "slug"}

    def test_brand_is_nested(self):
        product = ProductFactory()
        data = ProductListSerializer(product).data
        assert "name" in data["brand"]
        assert "slug" in data["brand"]


# ═══════════════════════════════════════════════════════════════════════════════
# ProductDetailSerializer
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductDetailSerializer:

    def test_contains_images_colors_reviews(self):
        product = ProductFactory()
        ProductImageFactory(product=product)
        ProductColorFactory(product=product)
        ReviewFactory.create_batch(2, product=product)
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert "images" in data
        assert "colors" in data
        assert "reviews" in data

    def test_images_list_populated(self):
        product = ProductFactory()
        ProductImageFactory(product=product)
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert len(data["images"]) == 1

    def test_colors_list_populated(self):
        product = ProductFactory()
        color = ColorFactory(name="Red", hex_code="#ff0000")
        ProductColorFactory(product=product, color=color)
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert len(data["colors"]) == 1
        assert data["colors"][0]["color"]["name"] == "Red"

    def test_reviews_list_populated(self):
        product = ProductFactory()
        ReviewFactory.create_batch(3, product=product)
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert len(data["reviews"]) == 3

    def test_description_present(self):
        product = ProductFactory(description="Detailed description here.")
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert data["description"] == "Detailed description here."

    def test_empty_images_returns_empty_list(self):
        product = ProductFactory()
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert data["images"] == []

    def test_price_as_string_decimal(self):
        """DRF serializes DecimalField as a string to preserve precision."""
        product = ProductFactory(price="29.99")
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert str(data["price"]) == "29.99"
