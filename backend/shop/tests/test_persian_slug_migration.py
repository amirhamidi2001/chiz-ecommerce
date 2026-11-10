"""
Tests for shop/migrations/0038_regenerate_persian_slugs.py (Task 14.4.1.2).

This is the FIX VERIFICATION for the live bug: rows are stored exactly as the OLD
generator (Django slugify, no allow_unicode) stored them, the migration runs, and
the slugs are compared before/after. Following the precedent in
dashboard/tests/test_migrations.py, the migration module is imported with
importlib (digit-leading filename) and its function is called against the real,
already-migrated test database.
"""

import importlib

import pytest
from django.apps import apps
from django.utils.text import slugify
from shop.models import Brand, Category, Product
from shop.text_utils import regenerate_legacy_slugs

ZWNJ = "\u200c"
migration = importlib.import_module("shop.migrations.0038_regenerate_persian_slugs")


def run_migration():
    migration.regenerate_slugs(apps, None)


def legacy(model, slug="", **kw):
    """Create a row, then force the slug the OLD code would have stored."""
    obj = model.objects.create(**kw)
    model.objects.filter(pk=obj.pk).update(slug=slug)
    return obj


def slug_of(obj):
    return type(obj).objects.get(pk=obj.pk).slug


def product(name, slug="", **kw):
    return legacy(Product, slug, name=name, price=990_000, stock=5, **kw)


@pytest.mark.django_db
class TestBeforeAfter:
    # (name, slug the old generator stored, slug after the migration)
    CASES = [
        ("سرم ویتامین سی", "", "serum-vitamin-c"),
        (
            "سرم ویتامین C",
            "c",
            "serum-vitamin-c-1",
        ),  # transliterates identically -> loop
        ("ضدآفتاب SPF50+", "spf50", "zdaftab-spf50"),
        ("ضدآفتاب SPF50 مات", "spf50-1", "zdaftab-spf50-mat"),
        ("کرم مرطوب" + ZWNJ + "کننده", "-1", "cream-mrtubknnde"),  # ZWNJ already lost
        ("رژ لب مات", "-2", "rzh-lb-mat"),
        ("L'Oréal کرم پودر", "loreal", "loreal-cream-powder"),
    ]

    def test_old_generator_output_is_what_the_cases_claim(self):
        # The "before" column really is what Django's slugify produced.
        from shop.text_utils import normalize_persian_text

        for name, before, _ in self.CASES:
            base = slugify(normalize_persian_text(name))
            assert (
                before == base
                or before.startswith(base + "-")
                or before == "-1"
                and base == ""
            )

    def test_slugs_before_and_after(self):
        rows = [(product(name, before), after) for name, before, after in self.CASES]
        before = {p.pk: slug_of(p) for p, _ in rows}
        assert [before[p.pk] for p, _ in rows] == [b for _, b, _ in self.CASES]
        assert "" in before.values() and "-1" in before.values()  # the confirmed bug

        run_migration()

        assert [slug_of(p) for p, _ in rows] == [a for *_, a in self.CASES]
        assert all(slug_of(p) and not slug_of(p).startswith("-") for p, _ in rows)

    def test_brand_and_category_with_empty_slugs(self):
        brand = legacy(Brand, name="لورآل پاریس")
        category = legacy(Category, name="مراقبت از پوست")
        assert (slug_of(brand), slug_of(category)) == ("", "")

        run_migration()

        assert slug_of(brand) == "loreal-paris"
        assert slug_of(category) == "mraqbt-az-pust"


@pytest.mark.django_db
class TestOnlyLegacyGeneratedSlugsAreTouched:
    def test_hand_set_slug_on_a_persian_product_is_untouched(self):
        p = product("سرم ویتامین سی", slug="my-hand-picked-slug")
        run_migration()
        assert slug_of(p) == "my-hand-picked-slug"

    def test_latin_named_products_are_untouched(self):
        p = product("Smart Watch Pro", slug="smart-watch-pro")
        run_migration()
        assert slug_of(p) == "smart-watch-pro"

    def test_a_suffixed_slug_that_does_not_match_the_old_pattern_is_untouched(self):
        p = product(
            "رژ لب مات", slug="rouge-3"
        )  # old base would be "" -> "-3", not "rouge-3"
        run_migration()
        assert slug_of(p) == "rouge-3"

    def test_new_slugs_never_collide_with_hand_set_slugs(self):
        taken = product("Anything", slug="serum-vitamin-c")
        broken = product("سرم ویتامین سی", slug="")
        run_migration()
        assert slug_of(taken) == "serum-vitamin-c"
        assert slug_of(broken) == "serum-vitamin-c-1"

    def test_second_run_changes_nothing(self):
        for name, slug in [("سرم ویتامین سی", ""), ("رژ لب مات", "-1")]:
            product(name, slug)
        run_migration()
        after_first = sorted(Product.objects.values_list("pk", "slug"))
        assert regenerate_legacy_slugs(Product, "name", fallback="product") == []
        run_migration()
        assert sorted(Product.objects.values_list("pk", "slug")) == after_first

    def test_only_the_slug_column_changes(self):
        p = product("سرم ویتامین سی", slug="")
        before = (
            Product.objects.filter(pk=p.pk)
            .values("name", "price", "stock", "search_vector")
            .get()
        )
        run_migration()
        after = (
            Product.objects.filter(pk=p.pk)
            .values("name", "price", "stock", "search_vector")
            .get()
        )
        assert (
            after == before
        )  # .update() on slug only: no save(), so no search_vector refresh either

    def test_returns_old_and_new_for_every_change(self):
        p = product("سرم ویتامین سی", slug="")
        changed = regenerate_legacy_slugs(Product, "name", fallback="product")
        assert changed == [(p.pk, "", "serum-vitamin-c")]
