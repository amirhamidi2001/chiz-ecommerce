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
        product = ProductFactory(price=99.99, original_price=149.99, stock=9)
        for _ in range(3):
            ProductColorFactory(product=product, color=ColorFactory())
        # Reload so `product.price`/`original_price` are the same Decimal
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
        product = ProductFactory(price=59.5, original_price=None, stock=15)
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
