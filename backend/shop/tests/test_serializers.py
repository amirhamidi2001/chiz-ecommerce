from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from promotions.models import FlashSale
from rest_framework import serializers
from shop.models import ProductGender
from shop.serializers import (
    BrandSerializer,
    CategoryMinimalSerializer,
    CategorySerializer,
    ColorSerializer,
    ProductColorSerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductListSerializer,
    ProductVariantSerializer,
    ReviewSerializer,
)
from shop.tests.factories import (
    BrandFactory,
    CategoryFactory,
    ColorFactory,
    ProductColorFactory,
    ProductFactory,
    ProductImageFactory,
    ProductVariantFactory,
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
        for field in (
            "id",
            "user_id",
            "name",
            "rating",
            "headline",
            "comment",
            "is_verified_purchase",
            "created_at",
        ):
            assert field in data

    def test_rating_value_in_1_to_5(self):
        review = ReviewFactory(rating=4)
        data = ReviewSerializer(review).data
        assert data["rating"] == 4

    def test_is_verified_purchase_defaults_to_false(self):
        """
        Task 1.3.1.2: this task only adds and exposes the field — no
        logic computes/sets it yet (that's Task 1.3.1.5), so a freshly
        created Review with no explicit value must default to False.
        """
        review = ReviewFactory()
        assert review.is_verified_purchase is False

        data = ReviewSerializer(review).data
        assert data["is_verified_purchase"] is False

    def test_is_verified_purchase_reflects_true_when_explicitly_set(self):
        # Belt-and-suspenders: confirm the serializer actually reads the
        # field's real value rather than hardcoding False.
        review = ReviewFactory(is_verified_purchase=True)
        data = ReviewSerializer(review).data
        assert data["is_verified_purchase"] is True

    def test_user_id_is_null_when_no_user_attached(self):
        review = ReviewFactory(user=None)
        data = ReviewSerializer(review).data
        assert data["user_id"] is None

    def test_user_id_reflects_attached_user_without_leaking_pii(self):
        User = get_user_model()
        user = User.objects.create_user(
            email="reviewer-serializer@example.com", password="TestPass123!"
        )
        review = ReviewFactory(user=user)
        data = ReviewSerializer(review).data

        assert data["user_id"] == user.id
        # Only the id is exposed — no nested user object (and therefore
        # no email or other PII) in the public review output.
        assert "user" not in data
        assert "email" not in data


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

    # ── Browse-relevant new fields (Tasks 3.2.1.1–3.2.1.13) ──────────────────

    def test_browse_relevant_new_fields_present(self):
        """
        The 6 fields that drive badges/filter chips on product cards
        must be exposed on the lightweight list serializer.
        """
        product = ProductFactory(
            skin_type="oily",
            hair_type="curly",
            gender=ProductGender.FEMALE,
            is_cruelty_free=True,
            is_vegan=True,
            is_organic=True,
        )
        data = ProductListSerializer(product, context={"request": make_request()}).data
        assert data["skin_type"] == "oily"
        assert data["hair_type"] == "curly"
        assert data["gender"] == "female"
        assert data["is_cruelty_free"] is True
        assert data["is_vegan"] is True
        assert data["is_organic"] is True

    def test_detail_only_fields_absent_from_list_serializer(self):
        """
        Detail-page-only fields must NOT bloat the list/grid payload —
        ingredients, usage_instructions, warnings, country_of_origin,
        irc_regulatory_code, regulatory_verified have no browse-page
        use case.
        """
        product = ProductFactory(
            ingredients="Aqua, Glycerin",
            usage_instructions="Apply nightly.",
            warnings="Patch test recommended.",
            country_of_origin="South Korea",
            irc_regulatory_code="IRC-1404-00281773",
            regulatory_verified=True,
        )
        data = ProductListSerializer(product, context={"request": make_request()}).data
        for field in (
            "ingredients",
            "usage_instructions",
            "warnings",
            "country_of_origin",
            "irc_regulatory_code",
            "regulatory_verified",
        ):
            assert (
                field not in data
            ), f"Unexpected detail-only field in list output: {field}"


# ═══════════════════════════════════════════════════════════════════════════════
# ProductListSerializer — flash-sale card fields
# ═══════════════════════════════════════════════════════════════════════════════
FLASH_FIELDS = {
    "is_on_flash_sale",
    "flash_sale_price",
    "flash_sale_original_price",
    "flash_sale_price_varies",
    "flash_sale_discount_percent",
    "flash_sale_ends_at",
}


@pytest.mark.django_db
class TestProductListSerializerFlashSale:
    def _data(self, product):
        return ProductListSerializer(product, context={"request": make_request()}).data

    def test_flash_fields_are_present(self):
        assert FLASH_FIELDS <= set(self._data(ProductFactory()).keys())

    def test_product_not_on_sale(self):
        variant = ProductVariantFactory(price=Decimal("80.00"))
        data = self._data(variant.product)
        assert data["is_on_flash_sale"] is False
        assert data["flash_sale_price"] is None
        assert data["flash_sale_original_price"] is None
        assert data["flash_sale_price_varies"] is False
        assert data["flash_sale_discount_percent"] is None
        assert data["flash_sale_ends_at"] is None

    def test_product_on_sale_shows_starting_at_price(self):
        variant = ProductVariantFactory(price=Decimal("80.00"))
        ProductVariantFactory(product=variant.product, price=Decimal("120.00"))
        sale = _serializer_sale(variant.product, percent="25.00")

        data = self._data(variant.product)

        assert data["is_on_flash_sale"] is True
        assert str(data["flash_sale_price"]) == "60.00"
        assert str(data["flash_sale_original_price"]) == "80.00"
        assert data["flash_sale_price_varies"] is True
        assert Decimal(str(data["flash_sale_discount_percent"])) == Decimal("25.00")
        assert parse_datetime(data["flash_sale_ends_at"]) == sale.ends_at

    def test_plain_product_price_fields_are_untouched_by_a_sale(self):
        variant = ProductVariantFactory(price=Decimal("80.00"))
        variant.product.price = Decimal("90.00")
        variant.product.save()
        _serializer_sale(variant.product, percent="25.00")
        data = self._data(variant.product)
        assert Decimal(str(data["price"])) == Decimal("90.00")

    @pytest.mark.parametrize(
        "kwargs",
        [{"start_h": 1, "end_h": 2}, {"start_h": -2, "end_h": -1}, {"active": False}],
        ids=["upcoming", "ended", "deactivated"],
    )
    def test_sale_that_is_not_current_is_not_on_sale(self, kwargs):
        variant = ProductVariantFactory(price=Decimal("80.00"))
        _serializer_sale(variant.product, **kwargs)
        data = self._data(variant.product)
        assert data["is_on_flash_sale"] is False
        assert data["flash_sale_price"] is None

    def test_resolves_the_sale_once_per_product_not_once_per_field(self):
        variant = ProductVariantFactory(price=Decimal("80.00"))
        _serializer_sale(variant.product)
        serializer = ProductListSerializer(
            variant.product, context={"request": make_request()}
        )
        with patch.object(
            type(variant.product),
            "flash_sale_card_pricing",
            autospec=True,
            side_effect=type(variant.product).flash_sale_card_pricing,
        ) as spy:
            serializer.data
        assert spy.call_count == 1

    def test_many_products_in_a_list_each_get_their_own_pricing(self):
        a = ProductVariantFactory(price=Decimal("100.00"))
        b = ProductVariantFactory(price=Decimal("40.00"))
        c = ProductVariantFactory(price=Decimal("10.00"))
        _serializer_sale(a.product, percent="50.00")
        _serializer_sale(b.product, percent="25.00")
        data = ProductListSerializer(
            [a.product, b.product, c.product],
            many=True,
            context={"request": make_request()},
        ).data
        assert [
            str(d["flash_sale_price"]) if d["flash_sale_price"] else None for d in data
        ] == [
            "50.00",
            "30.00",
            None,
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# ProductVariantSerializer
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductVariantSerializer:

    def test_contains_expected_fields(self):
        variant = ProductVariantFactory()
        data = ProductVariantSerializer(variant).data
        expected = {
            "id",
            "sku",
            "barcode",
            "color",
            "price",
            "original_price",
            "effective_price",
            "is_on_flash_sale",
            "flash_sale_ends_at",
            "stock",
            "volume_ml",
            "weight_g",
            "manufacture_date",
            "expiration_date",
            "batch_number",
            "is_active",
        }
        assert set(data.keys()) == expected

    def test_color_is_nested(self):
        color = ColorFactory(name="Ruby Red", hex_code="#E0115F")
        variant = ProductVariantFactory(color=color)
        data = ProductVariantSerializer(variant).data
        assert data["color"]["name"] == "Ruby Red"
        assert data["color"]["hex_code"] == "#E0115F"

    def test_color_is_null_when_variant_has_no_color(self):
        variant = ProductVariantFactory(color=None)
        data = ProductVariantSerializer(variant).data
        assert data["color"] is None

    def test_volume_ml_and_weight_g_serialize_correctly(self):
        variant = ProductVariantFactory(volume_ml=30, weight_g=None)
        data = ProductVariantSerializer(variant).data
        assert data["volume_ml"] == 30
        assert data["weight_g"] is None

    def test_dates_and_batch_number_serialize_correctly(self):
        import datetime

        variant = ProductVariantFactory(
            manufacture_date=datetime.date(2026, 1, 1),
            expiration_date=datetime.date(2028, 1, 1),
            batch_number="LOT-2026-0472",
        )
        data = ProductVariantSerializer(variant).data
        assert data["manufacture_date"] == "2026-01-01"
        assert data["expiration_date"] == "2028-01-01"
        assert data["batch_number"] == "LOT-2026-0472"

    def test_sku_and_barcode_present(self):
        variant = ProductVariantFactory(sku="FOUND-320", barcode="4006381333931")
        data = ProductVariantSerializer(variant).data
        assert data["sku"] == "FOUND-320"
        assert data["barcode"] == "4006381333931"


# ═══════════════════════════════════════════════════════════════════════════════
# ProductVariantSerializer — flash-sale-aware price fields
# ═══════════════════════════════════════════════════════════════════════════════
def _serializer_sale(*products, percent="25.00", start_h=-1, end_h=1, active=True):
    now = timezone.now()
    sale = FlashSale.objects.create(
        name="Sale",
        discount_percent=Decimal(percent),
        starts_at=now + timedelta(hours=start_h),
        ends_at=now + timedelta(hours=end_h),
        is_active=active,
    )
    sale.products.add(*products)
    return sale


@pytest.mark.django_db
class TestProductVariantSerializerFlashSale:
    def test_active_sale_exposes_discounted_price_flag_and_end_time(self):
        variant = ProductVariantFactory(price=Decimal("80.00"))
        sale = _serializer_sale(variant.product, percent="25.00")

        data = ProductVariantSerializer(variant).data

        assert Decimal(str(data["effective_price"])) == Decimal("60.00")
        assert data["is_on_flash_sale"] is True
        assert data[
            "flash_sale_ends_at"
        ] == serializers.DateTimeField().to_representation(sale.ends_at)
        # ...and the string round-trips to the exact stored instant.
        assert parse_datetime(data["flash_sale_ends_at"]) == sale.ends_at

    def test_plain_price_fields_are_not_altered_by_a_sale(self):
        variant = ProductVariantFactory(
            price=Decimal("80.00"), original_price=Decimal("100.00")
        )
        _serializer_sale(variant.product, percent="25.00")

        data = ProductVariantSerializer(variant).data

        assert Decimal(str(data["price"])) == Decimal("80.00")
        assert Decimal(str(data["original_price"])) == Decimal("100.00")

    def test_effective_price_is_formatted_to_two_decimal_places(self):
        variant = ProductVariantFactory(price=Decimal("80.00"))
        _serializer_sale(variant.product, percent="25.00")
        assert str(ProductVariantSerializer(variant).data["effective_price"]) == "60.00"

    @pytest.mark.parametrize(
        "kwargs",
        [
            pytest.param(None, id="no-sale-exists"),
            pytest.param({"start_h": 1, "end_h": 2}, id="upcoming"),
            pytest.param({"start_h": -2, "end_h": -1}, id="ended"),
            pytest.param({"active": False}, id="deactivated"),
        ],
    )
    def test_no_current_sale_leaves_price_unchanged(self, kwargs):
        variant = ProductVariantFactory(price=Decimal("80.00"))
        if kwargs is not None:
            _serializer_sale(variant.product, **kwargs)

        data = ProductVariantSerializer(variant).data

        assert Decimal(str(data["effective_price"])) == Decimal("80.00")
        assert Decimal(str(data["effective_price"])) == Decimal(str(data["price"]))
        assert data["is_on_flash_sale"] is False
        assert data["flash_sale_ends_at"] is None

    def test_upcoming_sale_is_treated_as_not_on_sale_even_alongside_a_current_one_elsewhere(
        self,
    ):
        variant = ProductVariantFactory(price=Decimal("80.00"))
        other = ProductVariantFactory(price=Decimal("80.00"))
        _serializer_sale(variant.product, start_h=2, end_h=3)  # upcoming
        _serializer_sale(other.product)  # current, different product

        data = ProductVariantSerializer(variant).data

        assert data["is_on_flash_sale"] is False
        assert Decimal(str(data["effective_price"])) == Decimal("80.00")

    def test_overlapping_sales_report_the_winning_sales_end_time(self):
        variant = ProductVariantFactory(price=Decimal("100.00"))
        _serializer_sale(variant.product, percent="50.00", start_h=-5, end_h=9)
        newer = _serializer_sale(variant.product, percent="10.00", start_h=-1, end_h=3)

        data = ProductVariantSerializer(variant).data

        # Most recently STARTED wins (not the biggest discount): 10% off.
        assert Decimal(str(data["effective_price"])) == Decimal("90.00")
        assert parse_datetime(data["flash_sale_ends_at"]) == newer.ends_at

    def test_nested_in_the_product_detail_serializer(self):
        variant = ProductVariantFactory(price=Decimal("80.00"))
        _serializer_sale(variant.product, percent="25.00")

        data = ProductDetailSerializer(variant.product).data

        nested = data["variants"][0]
        assert Decimal(str(nested["effective_price"])) == Decimal("60.00")
        assert nested["is_on_flash_sale"] is True


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

    # ── All new Product fields (Tasks 3.2.1.1–3.2.1.13) ──────────────────────

    def test_all_new_product_fields_present(self):
        product = ProductFactory(
            skin_type="dry",
            hair_type="wavy",
            spf=30,
            ingredients="Aqua/Water/Eau, Glycerin, Niacinamide",
            country_of_origin="France",
            usage_instructions="Apply a thin layer every morning.",
            warnings="Discontinue use if irritation occurs.",
            gender=ProductGender.MALE,
            is_cruelty_free=True,
            is_vegan=False,
            is_organic=True,
            irc_regulatory_code="IRC-1404-00281773",
            regulatory_verified=True,
        )
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data

        assert data["skin_type"] == "dry"
        assert data["hair_type"] == "wavy"
        assert data["spf"] == 30
        assert data["ingredients"] == "Aqua/Water/Eau, Glycerin, Niacinamide"
        assert data["country_of_origin"] == "France"
        assert data["usage_instructions"] == "Apply a thin layer every morning."
        assert data["warnings"] == "Discontinue use if irritation occurs."
        assert data["gender"] == "male"
        assert data["is_cruelty_free"] is True
        assert data["is_vegan"] is False
        assert data["is_organic"] is True
        assert data["irc_regulatory_code"] == "IRC-1404-00281773"
        assert data["regulatory_verified"] is True

    def test_new_fields_default_values_present_when_not_set(self):
        """
        Fields not explicitly set on the factory must still be present
        in the output with their model defaults (blank string / False /
        None), not silently omitted.
        """
        product = ProductFactory()
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert data["skin_type"] == ""
        assert data["hair_type"] == ""
        assert data["spf"] is None
        assert data["ingredients"] == ""
        assert data["country_of_origin"] == ""
        assert data["usage_instructions"] == ""
        assert data["warnings"] == ""
        assert data["gender"] == "unisex"
        assert data["is_cruelty_free"] is False
        assert data["is_vegan"] is False
        assert data["is_organic"] is False
        assert data["irc_regulatory_code"] == ""
        assert data["regulatory_verified"] is False

    # ── variants (this task) ──────────────────────────────────────────────────

    def test_variants_field_present(self):
        product = ProductFactory()
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert "variants" in data

    def test_empty_variants_returns_empty_list(self):
        product = ProductFactory()
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert data["variants"] == []

    def test_variants_list_populated_with_nested_attributes(self):
        import datetime

        product = ProductFactory()
        color = ColorFactory(name="Shade 320 - Warm Beige")
        ProductVariantFactory(
            product=product,
            sku="FOUND-320",
            barcode="4006381333931",
            color=color,
            price="35.00",
            stock=12,
            volume_ml=30,
            weight_g=None,
            manufacture_date=datetime.date(2026, 1, 1),
            expiration_date=datetime.date(2028, 1, 1),
            batch_number="LOT-2026-0472",
            is_active=True,
        )
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data

        assert len(data["variants"]) == 1
        variant_data = data["variants"][0]
        assert variant_data["sku"] == "FOUND-320"
        assert variant_data["barcode"] == "4006381333931"
        assert variant_data["color"]["name"] == "Shade 320 - Warm Beige"
        assert str(variant_data["price"]) == "35.00"
        assert variant_data["stock"] == 12
        assert variant_data["volume_ml"] == 30
        assert variant_data["weight_g"] is None
        assert variant_data["manufacture_date"] == "2026-01-01"
        assert variant_data["expiration_date"] == "2028-01-01"
        assert variant_data["batch_number"] == "LOT-2026-0472"
        assert variant_data["is_active"] is True

    def test_multiple_variants_all_serialized(self):
        product = ProductFactory()
        ProductVariantFactory(product=product, sku="SHADE-A")
        ProductVariantFactory(product=product, sku="SHADE-B")
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert len(data["variants"]) == 2
        skus = {v["sku"] for v in data["variants"]}
        assert skus == {"SHADE-A", "SHADE-B"}

    def test_colors_and_variants_coexist(self):
        """
        Both `colors` (legacy) and `variants` (authoritative) must be
        present simultaneously — colors is deliberately kept in place
        for now (see TODO in serializers.py) rather than removed as a
        silent side effect of this task.
        """
        product = ProductFactory()
        ProductColorFactory(product=product)
        ProductVariantFactory(product=product)
        data = ProductDetailSerializer(
            product, context={"request": make_request()}
        ).data
        assert "colors" in data
        assert "variants" in data
        assert len(data["colors"]) == 1
        assert len(data["variants"]) == 1
