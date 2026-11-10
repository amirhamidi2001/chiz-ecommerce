"""
Task 14.4.1.2 - model-level behaviour of Persian-name slugs (ADR 0002).

Before this task Product/Category/Brand used Django's slugify(), which deletes
every non-ASCII character. Observed against a real database:

    Product   "سرم ویتامین سی", ...  ->  '', '-1', '-2', 'spf50', 'spf50-1'
    Brand     two Persian names      ->  '' then IntegrityError (no collision loop)
    Category  two Persian names      ->  '' then IntegrityError

TestTheReproducedBugIsFixed asserts exactly that scenario no longer happens.
"""

import re

import pytest
from shop.models import Brand, Category, Product

ZWNJ = "\u200c"
VALID = re.compile(r"^[a-z0-9_]+(-[a-z0-9_]+)*$")


def make_product(name, **kw):
    return Product.objects.create(name=name, price=990_000, stock=5, **kw)


@pytest.mark.django_db
class TestPersianNamedProducts:
    def test_purely_persian_name_gets_a_readable_slug(self):
        assert make_product("سرم ویتامین سی").slug == "serum-vitamin-c"

    def test_mixed_script_name_keeps_the_latin_letter(self):
        assert make_product("سرم ویتامین C").slug == "serum-vitamin-c"

    def test_collision_loop_is_unchanged_identical_names(self):
        slugs = [make_product("سرم ویتامین سی").slug for _ in range(3)]
        assert slugs == ["serum-vitamin-c", "serum-vitamin-c-1", "serum-vitamin-c-2"]

    def test_names_that_transliterate_to_the_same_slug_do_not_collide(self):
        a = make_product("سرم ویتامین سی")
        b = make_product("سرم ویتامین C")
        assert (a.slug, b.slug) == ("serum-vitamin-c", "serum-vitamin-c-1")

    def test_zwnj_in_the_raw_name_becomes_a_word_boundary(self):
        # save() normalises the stored name (ZWNJ stripped) but must slug the
        # RAW name; otherwise this would be the single glued word "mrtubknnde".
        p = make_product("مرطوب" + ZWNJ + "کننده")
        assert ZWNJ not in p.name
        assert p.slug == "mrtub-knnde"

    def test_explicit_slug_is_respected(self):
        assert (
            make_product("سرم ویتامین سی", slug="my-custom-slug").slug
            == "my-custom-slug"
        )

    def test_slug_is_stable_when_the_name_changes(self):
        p = make_product("سرم ویتامین سی")
        p.name = "کرم مرطوب کننده"
        p.save()
        p.refresh_from_db()
        assert p.slug == "serum-vitamin-c"

    def test_name_with_nothing_transliterable_falls_back(self):
        assert make_product("!!!").slug == "product"
        assert make_product("???").slug == "product-1"

    def test_latin_behaviour_is_unchanged(self):
        a = make_product("Cool Shoes")
        b = make_product("Cool Shoes")
        assert (a.slug, b.slug) == ("cool-shoes", "cool-shoes-1")


@pytest.mark.django_db
class TestPersianNamedCategoriesAndBrands:
    def test_category_and_brand_slugs(self):
        assert (
            Category.objects.create(name="کرم مرطوب کننده").slug == "cream-mrtub-knnde"
        )
        assert Brand.objects.create(name="لورآل").slug == "loreal"

    def test_brands_that_transliterate_identically_get_distinct_slugs(self):
        # Brand/Category had NO collision handling: this raised IntegrityError.
        a = Brand.objects.create(name="نیوآ")
        b = Brand.objects.create(name="نیویا")
        assert (a.slug, b.slug) == ("nivea", "nivea-1")

    def test_categories_that_transliterate_identically_get_distinct_slugs(self):
        a = Category.objects.create(name="شامپو")
        b = Category.objects.create(
            name="شامپو "
        )  # trailing space: distinct name, same slug
        assert (a.slug, b.slug) == ("shampoo", "shampoo-1")

    def test_fallbacks(self):
        assert Category.objects.create(name="!!!").slug == "category"
        assert Brand.objects.create(name="???").slug == "brand"

    def test_explicit_slug_is_respected(self):
        assert Brand.objects.create(name="لورآل", slug="custom").slug == "custom"


@pytest.mark.django_db
class TestTheReproducedBugIsFixed:
    NAMES = [
        "سرم ویتامین سی",
        "کرم مرطوب" + ZWNJ + "کننده",
        "رژ لب مات",
        "ضدآفتاب SPF50+",
        "ضدآفتاب SPF50 بی" + ZWNJ + "رنگ",
    ]

    def test_products_no_longer_get_empty_or_hyphen_prefixed_slugs(self):
        # Old behaviour for exactly these names: ['', '-1', '-2', 'spf50', 'spf50-1']
        slugs = [make_product(n).slug for n in self.NAMES]
        assert slugs == [
            "serum-vitamin-c",
            "cream-mrtub-knnde",
            "rzh-lb-mat",
            "zdaftab-spf50",
            "zdaftab-spf50-bi-rng",
        ]
        assert all(VALID.match(s) for s in slugs)
        assert len(set(slugs)) == len(slugs)

    def test_a_second_persian_brand_and_category_no_longer_crash(self):
        Brand.objects.create(name="لورآل پاریس")
        Brand.objects.create(name="گلدن رز")  # was IntegrityError (both slugs '')
        Category.objects.create(name="مراقبت از پوست")
        Category.objects.create(name="آرایش")  # was IntegrityError
        assert Brand.objects.filter(slug="").count() == 0
        assert Category.objects.filter(slug="").count() == 0


@pytest.mark.django_db
class TestSlugLengthSafety:
    def test_very_long_persian_name_fits_the_column_even_with_collision_suffixes(self):
        # Persian letters expand (ش -> sh): 200 letters would overflow a 220 slug.
        name = "شخچ" * 66  # 198 chars -> ~ 400 transliterated
        first = Brand.objects.create(name=name)
        second = Brand.objects.create(name=name + "ا")
        max_len = Brand._meta.get_field("slug").max_length
        assert len(first.slug) <= max_len - 8
        assert len(second.slug) <= max_len
        assert first.slug != second.slug


class TestNoPlainSlugifyInModels:
    """Regression guard: Django's slugify() is what caused the bug (ADR 0002, I-3)."""

    @pytest.mark.parametrize("path", ["shop/models.py", "blog/models.py"])
    def test_models_do_not_use_djangos_slugify(self, path):
        source = open(path, encoding="utf8").read()
        assert "django.utils.text import slugify" not in source
        assert re.search(r"(?<!persian_)slugify\(", source) is None

    def test_every_slug_generating_model_uses_persian_slugify(self):
        for path in ("shop/models.py", "blog/models.py"):
            assert "persian_slugify(" in open(path, encoding="utf8").read()


class TestAdminDoesNotPrepopulateSlugs:
    """The admin's JS slugifier is ASCII-only; it would pre-fill a lossy slug (ADR 0002)."""

    def test_no_model_admin_prepopulates_a_slug(self):
        from blog.models import Category as BlogCategory
        from blog.models import Post
        from django.contrib import admin
        from shop.models import Brand, Category, Product

        for model in (Category, Brand, Product, BlogCategory, Post):
            assert "slug" not in admin.site._registry[model].prepopulated_fields, model
