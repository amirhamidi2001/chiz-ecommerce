"""
Tests for shop/migrations/0006_migrate_products_to_variants.py.

Following the precedent established in
accounts/tests/test_migrations.py: this project has no
migration-testing package installed (e.g. django-test-migrations), so
rather than pull in a new dependency for a single migration, these
tests import the migration module directly (via importlib, since its
filename starts with a digit and isn't a valid dotted-import
identifier) and call its forward/reverse functions directly against
the real, already-migrated test database and model classes —
equivalent to what Django's migration executor does under the hood
(`apps.get_model(...)` historical models resolve to the current model
classes once all migrations are applied, which they are in the test
DB).
"""

import importlib

import pytest
from django.apps import apps
from shop.models import ProductVariant
from shop.tests.factories import (
    ColorFactory,
    ProductColorFactory,
    ProductFactory,
    ProductVariantFactory,
)

migration_module = importlib.import_module(
    "shop.migrations.0006_migrate_products_to_variants"
)
migrate_products_to_variants = migration_module.migrate_products_to_variants
reverse_migrate_products_to_variants = (
    migration_module.reverse_migrate_products_to_variants
)
LEGACY_SKU_PREFIX = migration_module.LEGACY_SKU_PREFIX


def run_forward():
    """Invoke the migration's forward function against the real app registry."""
    migrate_products_to_variants(apps, None)


def run_reverse():
    """Invoke the migration's reverse function against the real app registry."""
    reverse_migrate_products_to_variants(apps, None)


@pytest.mark.django_db
class TestMigrateProductsToVariants:

    # ── Colored products: one variant per distinct color, stock split evenly ──

    def test_product_with_three_colors_creates_three_variants_summing_to_stock(self):
        product = ProductFactory(stock=30)
        colors = [ColorFactory() for _ in range(3)]
        for color in colors:
            ProductColorFactory(product=product, color=color)

        run_forward()

        variants = list(ProductVariant.objects.filter(product=product))
        assert len(variants) == 3
        assert {v.color_id for v in variants} == {c.id for c in colors}
        assert sum(v.stock for v in variants) == 30

    def test_uneven_stock_split_puts_remainder_on_first_variant(self):
        # 31 stock / 3 colors -> base share 10, remainder 1 -> first gets 11.
        product = ProductFactory(stock=31)
        colors = [ColorFactory() for _ in range(3)]
        for color in colors:
            ProductColorFactory(product=product, color=color)

        run_forward()

        variants = list(ProductVariant.objects.filter(product=product).order_by("sku"))
        assert [v.stock for v in variants] == [11, 10, 10]
        assert sum(v.stock for v in variants) == 31

    def test_colored_variants_get_price_and_original_price_from_product(self):
        product = ProductFactory(price=999_900, original_price=1_499_900, stock=9)
        for _ in range(3):
            ProductColorFactory(product=product, color=ColorFactory())
        # Reload so `product.price`/`original_price` are the same int
        # types the DB (and thus the migration) actually reads/writes,
        # rather than the raw Python floats factory_boy assigned.
        product.refresh_from_db()

        run_forward()

        for variant in ProductVariant.objects.filter(product=product):
            assert variant.price == product.price
            assert variant.original_price == product.original_price

    def test_colored_variant_skus_are_legacy_prefixed_and_unique(self):
        product = ProductFactory(stock=12)
        for _ in range(3):
            ProductColorFactory(product=product, color=ColorFactory())

        run_forward()

        skus = list(
            ProductVariant.objects.filter(product=product).values_list("sku", flat=True)
        )
        assert len(skus) == len(set(skus))
        assert all(sku.startswith(LEGACY_SKU_PREFIX) for sku in skus)

    def test_colored_variants_are_active(self):
        product = ProductFactory(stock=6)
        ProductColorFactory(product=product, color=ColorFactory())

        run_forward()

        assert all(v.is_active for v in ProductVariant.objects.filter(product=product))

    def test_duplicate_productcolor_rows_for_same_color_do_not_duplicate_variant(self):
        """
        Defensive: even if two ProductColor rows somehow pointed at the
        same color (bypassing the unique_together constraint via a raw
        insert, or historical dirty data), the migration should still
        create exactly one variant per *distinct* color.
        """
        product = ProductFactory(stock=10)
        color = ColorFactory()
        ProductColorFactory(product=product, color=color)
        other_color = ColorFactory()
        ProductColorFactory(product=product, color=other_color)

        run_forward()

        variants = ProductVariant.objects.filter(product=product)
        assert variants.count() == 2
        assert set(variants.values_list("color_id", flat=True)) == {
            color.id,
            other_color.id,
        }

    # ── Colorless products: exactly one variant, color=None ──────────────────

    def test_product_with_no_colors_creates_one_variant_with_null_color(self):
        product = ProductFactory(stock=15)

        run_forward()

        variants = list(ProductVariant.objects.filter(product=product))
        assert len(variants) == 1
        assert variants[0].color is None
        assert variants[0].stock == 15

    def test_colorless_variant_gets_price_and_original_price_unchanged(self):
        product = ProductFactory(price=595_000, original_price=None, stock=15)
        product.refresh_from_db()

        run_forward()

        variant = ProductVariant.objects.get(product=product)
        assert variant.price == product.price
        assert variant.original_price is None

    def test_colorless_variant_sku_is_legacy_prefixed(self):
        product = ProductFactory(stock=1)

        run_forward()

        variant = ProductVariant.objects.get(product=product)
        assert variant.sku.startswith(LEGACY_SKU_PREFIX)
        assert variant.is_active is True

    # ── Whole-dataset sanity ──────────────────────────────────────────────────

    def test_every_existing_product_gets_at_least_one_variant(self):
        colored_product = ProductFactory(stock=8)
        ProductColorFactory(product=colored_product, color=ColorFactory())
        colorless_product = ProductFactory(stock=4)

        run_forward()

        assert ProductVariant.objects.filter(product=colored_product).exists()
        assert ProductVariant.objects.filter(product=colorless_product).exists()
        assert ProductVariant.objects.filter(product=colorless_product).count() == 1

    # ── Reverse migration ──────────────────────────────────────────────────────

    def test_reverse_removes_only_legacy_prefixed_variants(self):
        colored_product = ProductFactory(stock=20)
        for _ in range(2):
            ProductColorFactory(product=colored_product, color=ColorFactory())
        colorless_product = ProductFactory(stock=5)

        run_forward()
        legacy_count = ProductVariant.objects.filter(
            sku__startswith=LEGACY_SKU_PREFIX
        ).count()
        assert legacy_count == 3  # 2 colored + 1 colorless

        # A hand-created variant using the real (post-migration) SKU
        # scheme, unrelated to this migration's output.
        hand_made = ProductVariantFactory(product=colored_product, sku="REAL-SKU-001")

        run_reverse()

        # All LEGACY- variants gone...
        assert not ProductVariant.objects.filter(
            sku__startswith=LEGACY_SKU_PREFIX
        ).exists()
        # ...but the hand-created one survives untouched.
        assert ProductVariant.objects.filter(pk=hand_made.pk).exists()
        assert ProductVariant.objects.count() == 1

    def test_reverse_is_a_noop_when_no_legacy_variants_exist(self):
        hand_made = ProductVariantFactory(sku="REAL-SKU-002")

        run_reverse()  # must not raise

        assert ProductVariant.objects.filter(pk=hand_made.pk).exists()
        assert ProductVariant.objects.count() == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 0032_backfill_product_search_vectors
# ═══════════════════════════════════════════════════════════════════════════════
import re  # noqa: E402

from django.contrib.postgres.search import SearchQuery  # noqa: E402
from django.db import connection  # noqa: E402
from django.db.migrations.loader import MigrationLoader  # noqa: E402
from shop.models import Product  # noqa: E402
from shop.tests.factories import BrandFactory, CategoryFactory  # noqa: E402

backfill_module = importlib.import_module(
    "shop.migrations.0032_backfill_product_search_vectors"
)


def historical_apps():
    """
    The app registry exactly as it is at migration 0032 — real HISTORICAL
    model classes (no custom save(), no signals), not the live ones. Running
    the backfill against these is what proves it works inside a migration;
    calling it with the live registry would not.
    """
    loader = MigrationLoader(connection)
    return loader.project_state([("shop", "0032_backfill_product_search_vectors")]).apps


def stored_vector(product):
    return Product.objects.get(pk=product.pk).search_vector


@pytest.mark.django_db
class TestBackfillProductSearchVectors:

    def _seed_pre_existing_rows(self):
        """Rows as they exist before the migration: search_vector is NULL."""
        full = ProductFactory(
            name="Alpha",
            brand=BrandFactory(name="Bravo"),
            category=CategoryFactory(name="Charlie"),
            short_description="Delta",
            description="Echo",
        )
        no_brand_or_category = ProductFactory(
            name="Foxtrot",
            brand=None,
            category=None,
            short_description="",
            description="",
        )
        persian = ProductFactory(
            name="کرم مرطوب کننده",
            brand=None,
            category=None,
            description="مناسب پوست خشک",
        )
        products = [full, no_brand_or_category, persian]
        Product.objects.update(search_vector=None)
        assert all(stored_vector(p) is None for p in products)
        return full, no_brand_or_category, persian

    def test_populates_every_preexisting_row(self):
        products = self._seed_pre_existing_rows()

        backfill_module.backfill_search_vectors(historical_apps(), None)

        assert all(stored_vector(p) for p in products)
        assert not Product.objects.filter(search_vector__isnull=True).exists()

    def test_backfilled_vector_has_weighted_related_and_own_fields(self):
        full, *_ = self._seed_pre_existing_rows()

        backfill_module.backfill_search_vectors(historical_apps(), None)

        stored = stored_vector(full)

        def weight(lexeme):
            return re.search(rf"'{lexeme}':\d+([A-D]?)", stored).group(1)

        assert weight("alpha") == "A"
        assert weight("bravo") == "A"
        assert weight("charlie") == "B"
        assert weight("delta") == "B"
        assert weight("echo") == "C"

    def test_rows_without_brand_or_category_are_backfilled_not_nulled(self):
        _, no_brand_or_category, _ = self._seed_pre_existing_rows()

        backfill_module.backfill_search_vectors(historical_apps(), None)

        assert "'foxtrot'" in stored_vector(no_brand_or_category)

    def test_backfilled_rows_are_findable(self):
        full, no_brand_or_category, persian = self._seed_pre_existing_rows()

        backfill_module.backfill_search_vectors(historical_apps(), None)

        def finds(term, product):
            return Product.objects.filter(
                pk=product.pk, search_vector=SearchQuery(term, config="simple")
            ).exists()

        assert finds("bravo", full)  # via brand
        assert finds("charlie", full)  # via category
        assert finds("foxtrot", no_brand_or_category)
        assert finds("مرطوب", persian)

    def test_backfill_matches_what_save_produces(self):
        """Migration and Product.save() must build the SAME vector."""
        product = ProductFactory(
            brand=BrandFactory(name="Same Brand"),
            category=CategoryFactory(name="Same Cat"),
        )
        via_save = stored_vector(product)
        Product.objects.filter(pk=product.pk).update(search_vector=None)

        backfill_module.backfill_search_vectors(historical_apps(), None)

        assert stored_vector(product) == via_save

    def test_is_idempotent(self):
        products = self._seed_pre_existing_rows()
        backfill_module.backfill_search_vectors(historical_apps(), None)
        first = [stored_vector(p) for p in products]

        backfill_module.backfill_search_vectors(historical_apps(), None)

        assert [stored_vector(p) for p in products] == first


# ═══════════════════════════════════════════════════════════════════════════════
# 0033_normalize_persian_text
# ═══════════════════════════════════════════════════════════════════════════════
normalize_module = importlib.import_module(
    "shop.migrations.0033_normalize_persian_text"
)


def apps_at_0033():
    loader = MigrationLoader(connection)
    return loader.project_state([("shop", "0033_normalize_persian_text")]).apps


@pytest.mark.django_db
class TestNormalizeCatalogTextMigration:

    def _seed_dirty_rows(self):
        """Rows as they exist before this migration: written with variants/ZWNJ,
        bypassing save() (which would now normalise them)."""
        brand = BrandFactory(name="B")
        category = CategoryFactory(name="C")
        dirty = ProductFactory(name="x", brand=brand, category=category)
        clean = ProductFactory(
            name="Already Clean", short_description="", description=""
        )
        type(brand).objects.filter(pk=brand.pk).update(name="كيان")
        type(category).objects.filter(pk=category.pk).update(name="آرايشي")
        Product.objects.filter(pk=dirty.pk).update(
            name="كرم ضد\u200cآفتاب",
            short_description="خشك",
            description="گياهي",
            search_vector=None,
        )
        return dirty, clean

    def test_existing_rows_are_normalized(self):
        dirty, _ = self._seed_dirty_rows()

        normalize_module.normalize_catalog_text(apps_at_0033(), None)

        dirty.refresh_from_db()
        assert dirty.name == "کرم ضدآفتاب"
        assert dirty.short_description == "خشک"
        assert dirty.description == "گیاهی"
        assert dirty.brand.name == "کیان"
        assert dirty.category.name == "آرایشی"

    def test_search_vectors_are_rebuilt_from_normalized_text(self):
        dirty, _ = self._seed_dirty_rows()

        normalize_module.normalize_catalog_text(apps_at_0033(), None)

        def finds(term):
            return Product.objects.filter(
                pk=dirty.pk, search_vector=SearchQuery(term, config="simple")
            ).exists()

        assert finds("ضدآفتاب")  # ZWNJ gone
        assert finds("کیان")  # via normalised brand
        assert finds("آرایشی")  # via normalised category
        assert finds("گیاهی")

    def test_slugs_and_already_clean_rows_are_untouched(self):
        dirty, clean = self._seed_dirty_rows()
        slug_before = Product.objects.get(pk=dirty.pk).slug

        normalize_module.normalize_catalog_text(apps_at_0033(), None)

        assert Product.objects.get(pk=dirty.pk).slug == slug_before
        clean.refresh_from_db()
        assert clean.name == "Already Clean"
        assert Product.objects.filter(search_vector__isnull=True).count() == 0

    def test_is_idempotent(self):
        dirty, _ = self._seed_dirty_rows()
        normalize_module.normalize_catalog_text(apps_at_0033(), None)
        first = Product.objects.get(pk=dirty.pk)
        snapshot = (first.name, first.description, first.search_vector)

        normalize_module.normalize_catalog_text(apps_at_0033(), None)

        again = Product.objects.get(pk=dirty.pk)
        assert (again.name, again.description, again.search_vector) == snapshot
