import datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.text import slugify
from shop.models import (
    Brand,
    Category,
    Color,
    HairType,
    Product,
    ProductColor,
    ProductVariant,
    Review,
    SkinType,
)
from shop.tests.factories import (
    BrandFactory,
    CategoryFactory,
    ColorFactory,
    ProductColorFactory,
    ProductFactory,
    ProductVariantFactory,
    ReviewFactory,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Category
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestCategoryModel:

    def test_str_returns_name(self):
        cat = CategoryFactory.build(name="Electronics")
        assert str(cat) == "Electronics"

    def test_slug_auto_generated_from_name(self, db):
        cat = CategoryFactory(name="Home & Kitchen")
        assert cat.slug == slugify("Home & Kitchen")

    def test_explicit_slug_is_respected(self, db):
        cat = CategoryFactory(name="Electronics", slug="my-custom-slug")
        assert cat.slug == "my-custom-slug"

    def test_parent_child_relationship(self, db):
        parent = CategoryFactory(name="Electronics")
        child = CategoryFactory(name="Smartphones", parent=parent)

        assert child.parent == parent
        assert child in parent.children.all()

    def test_parent_is_nullable(self, db):
        cat = CategoryFactory()
        assert cat.parent is None

    def test_ordering_is_alphabetical(self, db):
        CategoryFactory(name="Zebra")
        CategoryFactory(name="Apple")
        CategoryFactory(name="Mango")
        names = list(Category.objects.values_list("name", flat=True))
        assert names == sorted(names)

    def test_created_at_is_set(self, db):
        cat = CategoryFactory()
        assert cat.created_at is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Brand
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestBrandModel:

    def test_str_returns_name(self):
        brand = BrandFactory.build(name="Nike")
        assert str(brand) == "Nike"

    def test_slug_auto_generated(self, db):
        brand = BrandFactory(name="Under Armour")
        assert brand.slug == "under-armour"

    def test_slug_uniqueness_enforced_at_db(self, db):
        BrandFactory(name="Nike", slug="nike")
        with pytest.raises(Exception):
            BrandFactory(name="Nike2", slug="nike")  # duplicate slug → DB error


# ═══════════════════════════════════════════════════════════════════════════════
# Color
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestColorModel:

    def test_str_includes_name_and_hex(self, db):
        color = ColorFactory(name="Black", hex_code="#000000")
        assert str(color) == "Black (#000000)"

    def test_ordering_is_alphabetical(self, db):
        ColorFactory(name="Yellow")
        ColorFactory(name="Blue")
        names = list(Color.objects.values_list("name", flat=True))
        assert names == sorted(names)


# ═══════════════════════════════════════════════════════════════════════════════
# Product
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductModel:

    def test_str_returns_name(self):
        product = ProductFactory.build(name="Wireless Headphones")
        assert str(product) == "Wireless Headphones"

    def test_slug_auto_generated(self, db):
        product = ProductFactory(name="Smart Watch Pro")
        assert product.slug == "smart-watch-pro"

    def test_slug_collision_resolved_with_counter(self, db):
        p1 = ProductFactory(name="Cool Shoes")
        # Force a second product with the same base slug
        p2 = Product.objects.create(
            name="Cool Shoes",
            price=99,
            stock=10,
        )
        assert p2.slug == "cool-shoes-1"

        p3 = Product.objects.create(name="Cool Shoes", price=99, stock=5)
        assert p3.slug == "cool-shoes-2"

    def test_discount_percent_when_on_sale(self, db):
        product = ProductFactory(price=80, original_price=100)
        assert product.discount_percent == 20

    def test_discount_percent_zero_when_no_original_price(self, db):
        product = ProductFactory(price=80, original_price=None)
        assert product.discount_percent == 0

    def test_discount_percent_zero_when_price_equals_original(self, db):
        product = ProductFactory(price=100, original_price=100)
        assert product.discount_percent == 0

    def test_ordering_newest_first(self, db):
        p1 = ProductFactory(name="Old Product")
        p2 = ProductFactory(name="New Product")
        products = list(Product.objects.all())
        assert products[0] == p2  # newest first

    def test_is_new_default_false(self, db):
        product = ProductFactory()
        assert product.is_new is False

    def test_is_sale_default_false(self, db):
        product = ProductFactory()
        assert product.is_sale is False

    def test_stock_can_be_zero(self, db):
        product = ProductFactory(stock=0)
        assert product.stock == 0

    # ── ingredients ──────────────────────────────────────────────────────────

    def test_ingredients_stores_and_retrieves_long_inci_list_without_truncation(
        self, db
    ):
        """
        A realistic INCI (International Nomenclature of Cosmetic
        Ingredients) list: a long, comma-separated technical ingredient
        list, well over a few hundred characters. Must round-trip
        through the DB exactly, with no truncation — this is plain
        storage/display only (no structured parsing, no search
        indexing) per this task's scope.
        """
        inci_list = (
            "Aqua/Water/Eau, Glycerin, Butylene Glycol, Niacinamide, "
            "1,2-Hexanediol, Panthenol, Sodium Hyaluronate, Betaine, "
            "Centella Asiatica Leaf Water, Camellia Sinensis Leaf Extract, "
            "Sodium Polyacrylate, Ethylhexylglycerin, Carbomer, "
            "Polysorbate 20, Disodium EDTA, Allantoin, Tocopherol, "
            "Adenosine, Sodium Hydroxide, Madecassoside, "
            "Zinc PCA, Panax Ginseng Root Extract, Portulaca Oleracea Extract, "
            "Houttuynia Cordata Extract, Hydrolyzed Hyaluronic Acid, "
            "Sodium Hyaluronate Crosspolymer, Fragrance/Parfum, Citric Acid, "
            "Sodium Citrate, Xanthan Gum, Caprylyl Glycol, "
            "1,2-Hexanediol, Beta-Glucan, Arginine, Serine, Threonine, "
            "Glutamic Acid, Lysine HCl, Aspartic Acid, Alanine, "
            "Trisodium Ethylenediamine Disuccinate."
        )
        assert len(inci_list) > 500  # confirm this is genuinely long

        product = ProductFactory(ingredients=inci_list)
        product.refresh_from_db()

        assert product.ingredients == inci_list
        assert len(product.ingredients) == len(inci_list)

    def test_ingredients_blank_is_valid(self, db):
        product = ProductFactory(ingredients="")
        product.full_clean()  # must not raise
        assert product.ingredients == ""

    # ── country_of_origin ────────────────────────────────────────────────────

    def test_country_of_origin_saves_and_retrieves(self, db):
        product = ProductFactory(country_of_origin="South Korea")
        product.full_clean()  # must not raise
        product.refresh_from_db()
        assert product.country_of_origin == "South Korea"

    def test_country_of_origin_blank_is_valid(self, db):
        """
        Free text, no choices list, no default — plenty of products
        (or admins who haven't gotten to it yet) legitimately have no
        recorded origin.
        """
        product = ProductFactory(country_of_origin="")
        product.full_clean()  # must not raise
        assert product.country_of_origin == ""

    # ── usage_instructions / warnings ────────────────────────────────────────

    def test_usage_instructions_and_warnings_save_and_retrieve_independently(self, db):
        """
        Two separate fields, not one combined field — confirm they
        store/retrieve independently without interfering with each
        other (e.g. one overwriting or concatenating into the other).
        """
        usage_text = (
            "Apply a thin layer to clean, dry skin every morning and evening. "
            "Follow with moisturizer and, during the day, sunscreen."
        )
        warning_text = (
            "For external use only. Perform a patch test 24 hours before first "
            "use. Discontinue use if irritation, redness, or itching occurs. "
            "Avoid contact with eyes. Keep out of reach of children."
        )

        product = ProductFactory(usage_instructions=usage_text, warnings=warning_text)
        product.full_clean()  # must not raise
        product.refresh_from_db()

        assert product.usage_instructions == usage_text
        assert product.warnings == warning_text
        # The two fields must not bleed into each other.
        assert product.usage_instructions != product.warnings
        assert "patch test" not in product.usage_instructions
        assert "moisturizer" not in product.warnings

    def test_usage_instructions_and_warnings_blank_is_valid(self, db):
        product = ProductFactory(usage_instructions="", warnings="")
        product.full_clean()  # must not raise
        assert product.usage_instructions == ""
        assert product.warnings == ""

    def test_one_field_set_other_blank_is_valid(self, db):
        """A product may have only one of the two populated, not both."""
        product = ProductFactory(usage_instructions="Apply nightly.", warnings="")
        product.full_clean()  # must not raise
        product.refresh_from_db()
        assert product.usage_instructions == "Apply nightly."
        assert product.warnings == ""

    # ── skin_type ────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("choice", [c.value for c in SkinType])
    def test_saves_with_each_valid_skin_type_choice(self, db, choice):
        product = ProductFactory(skin_type=choice)
        product.full_clean()  # must not raise
        product.refresh_from_db()
        assert product.skin_type == choice

    def test_blank_skin_type_is_valid(self, db):
        """
        skin_type has no default and blank=True on purpose — not every
        category (haircare, fragrance, tools) has a meaningful skin
        type, so leaving it unset must be valid, not force an
        arbitrary "all" default.
        """
        product = ProductFactory(skin_type="")
        product.full_clean()  # must not raise
        assert product.skin_type == ""

    def test_invalid_skin_type_fails_full_clean(self, db):
        product = ProductFactory(skin_type="glowing")  # not a real choice
        with pytest.raises(ValidationError):
            product.full_clean()

    # ── hair_type ────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("choice", [c.value for c in HairType])
    def test_saves_with_each_valid_hair_type_choice(self, db, choice):
        product = ProductFactory(hair_type=choice)
        product.full_clean()  # must not raise
        product.refresh_from_db()
        assert product.hair_type == choice

    def test_blank_hair_type_is_valid(self, db):
        """
        Same rationale as skin_type: no default, blank=True — most
        categories (skincare, fragrance, tools) have no meaningful
        hair type, so leaving it unset must be valid.
        """
        product = ProductFactory(hair_type="")
        product.full_clean()  # must not raise
        assert product.hair_type == ""

    def test_invalid_hair_type_fails_full_clean(self, db):
        product = ProductFactory(hair_type="frizzy")  # not a real choice
        with pytest.raises(ValidationError):
            product.full_clean()

    # ── spf ──────────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("value", [0, 15, 30, 50, 100])
    def test_saves_with_valid_spf_values(self, db, value):
        product = ProductFactory(spf=value)
        product.full_clean()  # must not raise
        product.refresh_from_db()
        assert product.spf == value

    def test_spf_none_is_valid(self, db):
        """
        spf is nullable (not just blank) since it's numeric: None means
        genuinely "not applicable" (most makeup remover, most
        haircare), distinct from 0 which would mean "SPF 0 / no
        protection".
        """
        product = ProductFactory(spf=None)
        product.full_clean()  # must not raise
        assert product.spf is None

    def test_spf_above_max_bound_fails_full_clean(self, db):
        product = ProductFactory(spf=101)  # over the MaxValueValidator(100) bound
        with pytest.raises(ValidationError):
            product.full_clean()


# ═══════════════════════════════════════════════════════════════════════════════
# ProductColor
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductColorModel:

    def test_str_representation(self, db):
        pc = ProductColorFactory()
        assert pc.product.name in str(pc)
        assert pc.color.name in str(pc)

    def test_unique_together_enforced(self, db):
        pc = ProductColorFactory()
        with pytest.raises(Exception):
            ProductColorFactory(product=pc.product, color=pc.color)


# ═══════════════════════════════════════════════════════════════════════════════
# ProductVariant
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductVariantModel:

    def test_variant_can_be_created_linked_to_existing_product(self, db):
        product = ProductFactory(name="Matte Foundation")
        variant = ProductVariantFactory(
            product=product, sku="FOUND-SHADE-30", price=25, stock=15
        )

        assert variant.pk is not None
        assert variant.product_id == product.id
        assert variant.sku == "FOUND-SHADE-30"
        assert variant.price == 25
        assert variant.stock == 15

    def test_str_representation_includes_product_name_and_sku(self, db):
        product = ProductFactory(name="Hydrating Serum")
        variant = ProductVariantFactory(product=product, sku="SERUM-50ML")
        assert str(variant) == "Hydrating Serum — SERUM-50ML"

    def test_str_representation_falls_back_when_sku_blank(self, db):
        product = ProductFactory(name="Lip Tint")
        variant = ProductVariant(product=product, price=10, stock=5)
        assert str(variant) == "Lip Tint — unsaved"

    def test_reverse_accessor_via_related_name_variants(self, db):
        product = ProductFactory(name="Setting Powder")
        v1 = ProductVariantFactory(product=product)
        v2 = ProductVariantFactory(product=product)

        fetched_product = Product.objects.get(pk=product.pk)
        variant_ids = set(fetched_product.variants.all().values_list("id", flat=True))
        assert variant_ids == {v1.id, v2.id}

    def test_color_is_optional(self, db):
        variant = ProductVariantFactory(color=None)
        assert variant.color is None

    def test_deleting_color_sets_variant_color_to_null(self, db):
        color = ColorFactory()
        variant = ProductVariantFactory(color=color)
        color.delete()
        variant.refresh_from_db()
        assert variant.color is None

    def test_deleting_product_cascades_to_variant(self, db):
        product = ProductFactory()
        variant = ProductVariantFactory(product=product)
        variant_id = variant.id
        product.delete()
        assert ProductVariant.objects.filter(id=variant_id).count() == 0

    def test_is_active_defaults_to_true(self, db):
        variant = ProductVariantFactory()
        assert variant.is_active is True

    def test_sku_uniqueness_enforced_at_db(self, db):
        ProductVariantFactory(sku="UNIQUE-SKU-1")
        with pytest.raises(Exception):
            ProductVariantFactory(sku="UNIQUE-SKU-1")

    def test_sku_auto_generated_when_blank(self, db):
        product = ProductFactory(name="Auto SKU Product")
        variant = ProductVariantFactory(product=product, sku="")
        assert variant.sku != ""
        assert variant.sku is not None

    def test_explicit_sku_is_respected(self, db):
        variant = ProductVariantFactory(sku="MY-CUSTOM-SKU")
        assert variant.sku == "MY-CUSTOM-SKU"

    def test_sku_auto_generated_format_uses_category_brand_and_product_id(self, db):
        category = CategoryFactory(name="Cosmetics")
        brand = BrandFactory(name="Glow")
        product = ProductFactory(category=category, brand=brand)
        variant = ProductVariantFactory(product=product, sku="")
        assert variant.sku == f"COS-GLO-{product.id}"

    def test_sku_auto_generated_falls_back_when_no_category_or_brand(self, db):
        product = ProductFactory(category=None, brand=None)
        variant = ProductVariantFactory(product=product, sku="")
        assert variant.sku == f"GEN-UNK-{product.id}"

    def test_sku_collision_resolved_with_counter(self, db):
        """
        Two variants generated for the SAME product (and therefore the
        same base category/brand/product-id SKU) must resolve their
        collision via the same counter-suffix pattern already used by
        Product.slug generation.
        """
        category = CategoryFactory(name="Skincare")
        brand = BrandFactory(name="Luxe")
        product = ProductFactory(category=category, brand=brand)

        v1 = ProductVariantFactory(product=product, sku="")
        assert v1.sku == f"SKI-LUX-{product.id}"

        # Force a second variant for the SAME product (so it would
        # naturally generate the identical base SKU) to prove the
        # collision-avoidance loop kicks in.
        v2 = ProductVariant.objects.create(product=product, price=15, stock=5)
        assert v2.sku == f"SKI-LUX-{product.id}-1"

        v3 = ProductVariant.objects.create(product=product, price=20, stock=3)
        assert v3.sku == f"SKI-LUX-{product.id}-2"

    def test_sku_not_regenerated_on_subsequent_save(self, db):
        """Saving an already-SKU'd variant again must not change its SKU."""
        variant = ProductVariantFactory(sku="")
        original_sku = variant.sku
        variant.stock = variant.stock + 1
        variant.save()
        assert variant.sku == original_sku

    # ── barcode: EAN-13 validation ──────────────────────────────────────────

    def test_valid_ean13_barcode_passes_full_clean(self, db):
        variant = ProductVariantFactory(barcode="4006381333931")
        variant.full_clean()  # must not raise

    def test_ean13_barcode_with_wrong_checksum_fails_full_clean(self, db):
        variant = ProductVariantFactory(barcode="4006381333932")  # bad check digit
        with pytest.raises(ValidationError):
            variant.full_clean()

    def test_non_13_digit_barcode_fails_full_clean(self, db):
        for bad_value in ["12345", "400638133393112", "40063813393a1"]:
            variant = ProductVariantFactory(barcode=bad_value)
            with pytest.raises(ValidationError):
                variant.full_clean()

    def test_blank_barcode_passes_full_clean(self, db):
        variant = ProductVariantFactory(barcode="")
        variant.full_clean()  # must not raise — barcode remains optional

    def test_barcode_validator_does_not_run_on_bare_save(self, db):
        """
        Field validators (including validate_ean13) only run via
        full_clean(), never on a bare .save()/.objects.create() — this
        is standard Django behavior, not a bug. A malformed barcode
        written directly via .save() is NOT rejected; only ModelForm
        (Django admin) / DRF serializer / explicit full_clean() paths
        enforce it.
        """
        variant = ProductVariantFactory(barcode="not-a-valid-barcode")
        variant.save()  # must NOT raise, unlike full_clean() above
        variant.refresh_from_db()
        assert variant.barcode == "not-a-valid-barcode"

    # ── volume_ml / weight_g ─────────────────────────────────────────────────

    def test_volume_ml_set_weight_g_null(self, db):
        """The common liquid case: a 30ml serum has volume, no weight."""
        variant = ProductVariantFactory(volume_ml=30, weight_g=None)
        variant.full_clean()  # must not raise
        variant.refresh_from_db()
        assert variant.volume_ml == 30
        assert variant.weight_g is None

    def test_weight_g_set_volume_ml_null(self, db):
        """The common solid case: a pressed powder has weight, no volume."""
        variant = ProductVariantFactory(volume_ml=None, weight_g=12)
        variant.full_clean()  # must not raise
        variant.refresh_from_db()
        assert variant.volume_ml is None
        assert variant.weight_g == 12

    def test_both_volume_ml_and_weight_g_null(self, db):
        """
        Deliberately permissive: a color-only variant (e.g. an
        eyeshadow palette shade with no size variation) may need
        neither dimension recorded — this must remain valid, not be
        forced into picking one.
        """
        variant = ProductVariantFactory(volume_ml=None, weight_g=None)
        variant.full_clean()  # must not raise
        variant.refresh_from_db()
        assert variant.volume_ml is None
        assert variant.weight_g is None

    def test_both_volume_ml_and_weight_g_set(self, db):
        """
        No "exactly one must be set" constraint exists on purpose — a
        variant with both dimensions recorded must also be valid.
        """
        variant = ProductVariantFactory(volume_ml=50, weight_g=75)
        variant.full_clean()  # must not raise
        variant.refresh_from_db()
        assert variant.volume_ml == 50
        assert variant.weight_g == 75

    # ── manufacture_date / expiration_date ──────────────────────────────────

    def test_expiration_after_manufacture_date_passes_full_clean(self, db):
        variant = ProductVariantFactory(
            manufacture_date=datetime.date(2026, 1, 1),
            expiration_date=datetime.date(2028, 1, 1),
        )
        variant.full_clean()  # must not raise
        variant.refresh_from_db()
        assert variant.manufacture_date == datetime.date(2026, 1, 1)
        assert variant.expiration_date == datetime.date(2028, 1, 1)

    def test_expiration_before_manufacture_date_fails_full_clean(self, db):
        variant = ProductVariantFactory(
            manufacture_date=datetime.date(2026, 1, 1),
            expiration_date=datetime.date(2025, 1, 1),  # before manufacture
        )
        with pytest.raises(ValidationError) as exc_info:
            variant.full_clean()
        assert "expiration_date" in exc_info.value.message_dict

    def test_expiration_equal_to_manufacture_date_fails_full_clean(self):
        """
        "After" means strictly after — same-day manufacture and
        expiration doesn't make sense for a real product, so equal
        dates must also be rejected, not just earlier ones.
        """
        variant = ProductVariantFactory.build(
            manufacture_date=datetime.date(2026, 1, 1),
            expiration_date=datetime.date(2026, 1, 1),
        )
        with pytest.raises(ValidationError) as exc_info:
            variant.clean()
        assert "expiration_date" in exc_info.value.message_dict

    def test_only_manufacture_date_set_passes_full_clean(self, db):
        """Only one of the two dates set — comparison must be skipped entirely."""
        variant = ProductVariantFactory(
            manufacture_date=datetime.date(2026, 1, 1), expiration_date=None
        )
        variant.full_clean()  # must not raise

    def test_only_expiration_date_set_passes_full_clean(self, db):
        variant = ProductVariantFactory(
            manufacture_date=None, expiration_date=datetime.date(2028, 1, 1)
        )
        variant.full_clean()  # must not raise

    def test_neither_date_set_passes_full_clean(self, db):
        variant = ProductVariantFactory(manufacture_date=None, expiration_date=None)
        variant.full_clean()  # must not raise

    # ── batch_number ─────────────────────────────────────────────────────────

    def test_batch_number_saves_and_retrieves(self, db):
        variant = ProductVariantFactory(batch_number="LOT-2026-0472")
        variant.full_clean()  # must not raise
        variant.refresh_from_db()
        assert variant.batch_number == "LOT-2026-0472"

    def test_batch_number_blank_is_valid(self, db):
        variant = ProductVariantFactory(batch_number="")
        variant.full_clean()  # must not raise
        assert variant.batch_number == ""


# ═══════════════════════════════════════════════════════════════════════════════
# Review
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestReviewModel:

    def test_str_includes_reviewer_product_and_rating(self, db):
        review = ReviewFactory(name="Alice", rating=5)
        text = str(review)
        assert "Alice" in text
        assert review.product.name in text
        assert "5" in text

    def test_ordering_newest_first(self, db):
        product = ProductFactory()
        r1 = ReviewFactory(product=product)
        r2 = ReviewFactory(product=product)
        reviews = list(Review.objects.filter(product=product))
        assert reviews[0] == r2

    def test_rating_choices_1_to_5(self, db):
        for rating in range(1, 6):
            r = ReviewFactory(rating=rating)
            assert r.rating == rating

    def test_cascade_delete_with_product(self, db):
        review = ReviewFactory()
        product_id = review.product.id
        review.product.delete()
        assert Review.objects.filter(id=review.id).count() == 0

    # ── user FK (Task 1.3.1.2 — nullable, backward-compatible) ──────────────

    def test_review_can_be_created_with_user_none(self, db):
        """
        Backward compatibility: any existing code path that hasn't been
        updated yet (and all pre-migration historical rows) must still be
        able to create/hold a Review with no associated user.
        """
        review = ReviewFactory(user=None)
        assert review.user is None
        assert review.user_id is None
        # `name` (the denormalized display cache) is unaffected by user
        # being absent.
        assert review.name

    def test_review_can_be_created_with_a_real_user(self, db):
        User = get_user_model()
        user = User.objects.create_user(
            email="reviewer@example.com", password="TestPass123!"
        )
        review = ReviewFactory(user=user, name="Reviewer Name")

        assert review.user_id == user.id
        assert review.user == user
        # name is still stored independently of the linked user (kept as
        # a denormalized display cache per this task's requirements).
        assert review.name == "Reviewer Name"

    def test_deleting_user_sets_review_user_to_null_not_cascade(self, db):
        """
        on_delete=SET_NULL: deleting the linked User must not delete the
        Review itself (unlike `product`, which cascades) — the review
        (and its denormalized `name`) should survive with user=None.
        """
        User = get_user_model()
        user = User.objects.create_user(
            email="departing-user@example.com", password="TestPass123!"
        )
        review = ReviewFactory(user=user, name="Someone")
        review_id = review.id

        user.delete()

        review.refresh_from_db()
        assert Review.objects.filter(id=review_id).exists()
        assert review.user is None
        assert review.name == "Someone"  # unaffected — still denormalized

    # ── is_verified_purchase (Task 1.3.1.2 — field only, no logic yet) ──────

    def test_is_verified_purchase_defaults_to_false(self, db):
        review = ReviewFactory()
        assert review.is_verified_purchase is False

    def test_is_verified_purchase_can_be_set_true(self, db):
        # No computation logic exists yet (Task 1.3.1.5) — just confirming
        # the field itself is a normal, settable boolean.
        review = ReviewFactory(is_verified_purchase=True)
        assert review.is_verified_purchase is True

    # ── unique_together (product, user) — Task 1.3.1.4 ──────────────────────

    def test_duplicate_product_user_review_raises_integrity_error(self, db):
        """
        DB-level enforcement: the unique_together constraint itself,
        independent of the serializer-layer check (which is covered
        separately in shop/tests/test_views.py). This is the last line
        of defense against duplicate reviews if the application layer is
        ever bypassed (e.g. a management command, a future internal
        endpoint, a bug in the serializer check).
        """
        User = get_user_model()
        user = User.objects.create_user(
            email="dupe-checker@example.com", password="TestPass123!"
        )
        product = ProductFactory()
        ReviewFactory(product=product, user=user)

        # Wrapped in its own atomic() block: on Postgres, an IntegrityError
        # aborts the enclosing transaction until a ROLLBACK — nesting this
        # in its own savepoint keeps the rest of the test (and pytest-django's
        # transaction-per-test teardown) usable afterward.
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ReviewFactory(product=product, user=user)

    def test_multiple_null_user_reviews_on_same_product_do_not_conflict(self, db):
        """
        Confirms the documented NULL-handling caveat in Review.Meta: on
        this project's PostgreSQL backend, a UNIQUE constraint treats
        NULL as distinct from every other NULL, so multiple historical
        `user=None` reviews on the same product remain valid and do NOT
        trip the (product, user) uniqueness constraint.
        """
        product = ProductFactory()
        review_one = ReviewFactory(product=product, user=None, name="Anon One")
        review_two = ReviewFactory(product=product, user=None, name="Anon Two")

        assert review_one.pk is not None
        assert review_two.pk is not None
        assert Review.objects.filter(product=product, user__isnull=True).count() == 2

    def test_same_user_can_review_different_products(self, db):
        User = get_user_model()
        user = User.objects.create_user(
            email="multi-product-reviewer@example.com", password="TestPass123!"
        )
        product_a = ProductFactory()
        product_b = ProductFactory()

        ReviewFactory(product=product_a, user=user)
        ReviewFactory(product=product_b, user=user)

        assert Review.objects.filter(user=user).count() == 2
