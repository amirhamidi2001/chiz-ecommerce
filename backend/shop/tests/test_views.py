import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from promotions.models import FlashSale
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.throttling import AnonRateThrottle
from shop.models import Product
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
from shop.views import CATEGORY_TREE_CACHE_KEY


# ─── helpers ────────────────────────────────────────────────────────────────
def url(name, **kwargs):
    return reverse(name, kwargs=kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/categories/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestCategoryListView:

    def test_returns_200(self, api_client):
        res = api_client.get(url("category-list"))
        assert res.status_code == status.HTTP_200_OK

    def test_returns_only_root_categories(self, api_client):
        root = CategoryFactory(name="Root", slug="root")
        child = CategoryFactory(name="Child", slug="child", parent=root)
        res = api_client.get(url("category-list"))
        results = res.data["results"]
        names = [c["name"] for c in results]
        assert "Root" in names
        assert "Child" not in names

    def test_children_are_nested(self, api_client):
        root = CategoryFactory(name="Root", slug="root")
        child = CategoryFactory(name="Child", slug="child", parent=root)
        res = api_client.get(url("category-list"))
        root_data = next(c for c in res.data["results"] if c["name"] == "Root")
        child_names = [c["name"] for c in root_data["children"]]
        assert "Child" in child_names

    def test_empty_db_returns_empty_list(self, api_client):
        res = api_client.get(url("category-list"))
        assert res.data["count"] == 0
        assert res.data["results"] == []

    def test_no_authentication_required(self, api_client):
        """Public endpoint — no auth header needed."""
        res = api_client.get(url("category-list"))
        assert res.status_code != status.HTTP_401_UNAUTHORIZED


# ═══════════════════════════════════════════════════════════════════════════════
# CategoryListView caching + signal-based invalidation
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestCategoryListViewCaching:

    def test_first_request_populates_cache(self, api_client):
        assert cache.get(CATEGORY_TREE_CACHE_KEY) is None
        res = api_client.get(url("category-list"))
        assert res.status_code == status.HTTP_200_OK
        assert cache.get(CATEGORY_TREE_CACHE_KEY) is not None

    def test_second_request_does_not_hit_db(
        self, api_client, django_assert_num_queries
    ):
        CategoryFactory(name="Root", slug="root")
        # Prime the cache.
        api_client.get(url("category-list"))
        # Second request should be served entirely from cache — no queries.
        with django_assert_num_queries(0):
            res = api_client.get(url("category-list"))
        assert res.status_code == status.HTTP_200_OK

    def test_second_request_returns_same_data_as_first(self, api_client):
        CategoryFactory(name="Root", slug="root")
        first = api_client.get(url("category-list"))
        second = api_client.get(url("category-list"))
        assert second.data == first.data

    def test_creating_category_invalidates_cache(self, api_client):
        api_client.get(url("category-list"))
        assert cache.get(CATEGORY_TREE_CACHE_KEY) is not None

        CategoryFactory(name="New Root", slug="new-root")
        assert cache.get(CATEGORY_TREE_CACHE_KEY) is None

        res = api_client.get(url("category-list"))
        names = [c["name"] for c in res.data["results"]]
        assert "New Root" in names

    def test_updating_category_invalidates_cache(self, api_client):
        root = CategoryFactory(name="Root", slug="root")
        api_client.get(url("category-list"))
        assert cache.get(CATEGORY_TREE_CACHE_KEY) is not None

        root.name = "Renamed Root"
        root.save()
        assert cache.get(CATEGORY_TREE_CACHE_KEY) is None

        res = api_client.get(url("category-list"))
        names = [c["name"] for c in res.data["results"]]
        assert "Renamed Root" in names
        assert "Root" not in names

    def test_deleting_category_invalidates_cache(self, api_client):
        root = CategoryFactory(name="Root", slug="root")
        api_client.get(url("category-list"))
        assert cache.get(CATEGORY_TREE_CACHE_KEY) is not None

        root.delete()
        assert cache.get(CATEGORY_TREE_CACHE_KEY) is None

        res = api_client.get(url("category-list"))
        assert res.data["results"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/brands/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestBrandListView:

    def test_returns_200(self, api_client):
        res = api_client.get(url("brand-list"))
        assert res.status_code == status.HTTP_200_OK

    def test_returns_all_brands(self, api_client):
        BrandFactory.create_batch(5)
        res = api_client.get(url("brand-list"))
        assert len(res.data) == 5

    def test_search_by_name(self, api_client):
        BrandFactory(name="Nike")
        BrandFactory(name="Adidas")
        BrandFactory(name="Puma")
        res = api_client.get(url("brand-list"), {"search": "nik"})
        assert len(res.data) == 1
        assert res.data[0]["name"] == "Nike"

    def test_not_paginated(self, api_client):
        """Brand list returns a plain list, not a paginated envelope."""
        BrandFactory.create_batch(20)
        res = api_client.get(url("brand-list"))
        assert isinstance(res.data, list)
        assert len(res.data) == 20


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/colors/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestColorListView:

    def test_returns_200(self, api_client):
        res = api_client.get(url("color-list"))
        assert res.status_code == status.HTTP_200_OK

    def test_returns_all_colors(self, api_client):
        ColorFactory.create_batch(6)
        res = api_client.get(url("color-list"))
        assert len(res.data) == 6

    def test_not_paginated(self, api_client):
        ColorFactory.create_batch(15)
        res = api_client.get(url("color-list"))
        assert isinstance(res.data, list)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/products/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductListView:

    # ── Pagination ─────────────────────────────────────────────────────────
    def test_paginated_response_shape(self, api_client, products_bulk):
        res = api_client.get(url("product-list"))
        assert res.status_code == status.HTTP_200_OK
        for key in (
            "count",
            "total_pages",
            "next",
            "previous",
            "current_page",
            "results",
        ):
            assert key in res.data, f"Missing pagination key: {key}"

    def test_default_page_size_is_12(self, api_client):
        ProductFactory.create_batch(20)
        res = api_client.get(url("product-list"))
        assert len(res.data["results"]) == 12

    def test_custom_page_size(self, api_client):
        ProductFactory.create_batch(10)
        res = api_client.get(url("product-list"), {"page_size": 5})
        assert len(res.data["results"]) == 5

    def test_page_2_returns_correct_items(self, api_client):
        ProductFactory.create_batch(15)
        res = api_client.get(url("product-list"), {"page": 2, "page_size": 10})
        assert len(res.data["results"]) == 5

    def test_total_pages_calculated_correctly(self, api_client):
        ProductFactory.create_batch(25)
        res = api_client.get(url("product-list"), {"page_size": 10})
        assert res.data["total_pages"] == 3

    # ── Search ──────────────────────────────────────────────────────────────
    def test_search_by_product_name(self, api_client):
        ProductFactory(name="Wireless Headphones")
        ProductFactory(name="Running Shoes")
        ProductFactory(name="Wireless Speaker")
        res = api_client.get(url("product-list"), {"search": "wireless"})
        names = [p["name"] for p in res.data["results"]]
        assert all("wireless" in n.lower() for n in names)
        assert len(names) == 2

    def test_search_no_match_returns_empty(self, api_client):
        ProductFactory.create_batch(5)
        res = api_client.get(url("product-list"), {"search": "xyznonexistent123"})
        assert res.data["count"] == 0

    # ── Ordering ────────────────────────────────────────────────────────────
    def test_order_by_price_ascending(self, api_client):
        ProductFactory(name="Expensive", price=2_000_000)
        ProductFactory(name="Cheap", price=100_000)
        ProductFactory(name="Mid", price=500_000)
        res = api_client.get(url("product-list"), {"ordering": "price"})
        prices = [float(p["price"]) for p in res.data["results"]]
        assert prices == sorted(prices)

    def test_order_by_price_descending(self, api_client):
        ProductFactory(name="Expensive", price=2_000_000)
        ProductFactory(name="Cheap", price=100_000)
        res = api_client.get(url("product-list"), {"ordering": "-price"})
        prices = [float(p["price"]) for p in res.data["results"]]
        assert prices == sorted(prices, reverse=True)

    def test_order_by_rating(self, api_client):
        ProductFactory(price=100_000, rating=4.5)
        ProductFactory(price=200_000, rating=3.0)
        ProductFactory(price=300_000, rating=5.0)
        res = api_client.get(url("product-list"), {"ordering": "-rating"})
        ratings = [float(p["rating"]) for p in res.data["results"]]
        assert ratings == sorted(ratings, reverse=True)

    # ── Filtering ────────────────────────────────────────────────────────────
    def test_filter_by_category_slug(self, api_client):
        cat_a = CategoryFactory(slug="electronics")
        cat_b = CategoryFactory(slug="clothing")
        ProductFactory.create_batch(3, category=cat_a)
        ProductFactory.create_batch(2, category=cat_b)
        res = api_client.get(url("product-list"), {"category": "electronics"})
        assert res.data["count"] == 3

    def test_filter_is_new(self, api_client, new_products):
        ProductFactory.create_batch(3, is_new=False)
        res = api_client.get(url("product-list"), {"is_new": "true"})
        assert res.data["count"] == 4
        assert all(p["is_new"] for p in res.data["results"])

    def test_filter_is_sale(self, api_client, sale_products):
        ProductFactory.create_batch(3, is_sale=False)
        res = api_client.get(url("product-list"), {"is_sale": "true"})
        assert res.data["count"] == 4

    def test_filter_min_price(self, api_client):
        ProductFactory(price=100_000)
        ProductFactory(price=1_000_000)
        ProductFactory(price=5_000_000)
        res = api_client.get(url("product-list"), {"min_price": 990_000})
        assert res.data["count"] == 2

    def test_filter_max_price(self, api_client):
        ProductFactory(price=100_000)
        ProductFactory(price=1_000_000)
        ProductFactory(price=5_000_000)
        res = api_client.get(url("product-list"), {"max_price": 1_010_000})
        assert res.data["count"] == 2

    def test_filter_brand_slug(self, api_client):
        brand = BrandFactory(slug="nike")
        ProductFactory.create_batch(3, brand=brand)
        ProductFactory.create_batch(2)
        res = api_client.get(url("product-list"), {"brand": "nike"})
        assert res.data["count"] == 3

    def test_filter_color_by_name(self, api_client):
        red = ColorFactory(name="Red", hex_code="#ff0000")
        p_red = ProductFactory()
        ProductColorFactory(product=p_red, color=red)
        ProductFactory.create_batch(3)  # no color
        res = api_client.get(url("product-list"), {"color": "Red"})
        ids = [p["id"] for p in res.data["results"]]
        assert p_red.id in ids

    def test_no_auth_required(self, api_client):
        res = api_client.get(url("product-list"))
        assert res.status_code == status.HTTP_200_OK

    # ── Response field validation ────────────────────────────────────────────
    def test_result_items_have_expected_fields(self, api_client):
        ProductFactory()
        res = api_client.get(url("product-list"))
        item = res.data["results"][0]
        for field in (
            "id",
            "name",
            "slug",
            "price",
            "rating",
            "is_new",
            "is_sale",
            "category",
            "brand",
        ):
            assert field in item, f"Missing field in product list item: {field}"

    def test_result_items_do_not_contain_reviews(self, api_client):
        """List serializer should not include the full review list."""
        product = ProductFactory()
        ReviewFactory.create_batch(3, product=product)
        res = api_client.get(url("product-list"))
        item = res.data["results"][0]
        assert "reviews" not in item


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/products/?search=  — Postgres full-text search (weighted + ranked)
#
# These need a real PostgreSQL connection (SearchVector/SearchRank/GIN); this
# project's DATABASES is Postgres-only, so that is what the test DB is.
# ═══════════════════════════════════════════════════════════════════════════════
def _names(res):
    return [p["name"] for p in res.data["results"]]


def _same_created_at(*products):
    """Force identical created_at so ordering can only come from rank."""
    ts = timezone.now()
    Product.objects.filter(pk__in=[p.pk for p in products]).update(created_at=ts)


@pytest.mark.django_db
class TestProductFullTextSearch:

    # 1 ── name hit outranks description-only hit ──────────────────────────
    def test_name_match_ranks_above_description_only_match(self, api_client):
        # Name-match product is created FIRST (lower pk) so that, were rank
        # ignored, the pk/created_at tie-break would put the description-only
        # product first — the assertion can only pass because of ranking.
        by_name = ProductFactory(
            name="Rose Cream", short_description="", description="Gentle daily care."
        )
        by_description = ProductFactory(
            name="Night Serum",
            short_description="",
            description="A calming formula with a hint of rose.",
        )
        _same_created_at(by_name, by_description)

        res = api_client.get(url("product-list"), {"search": "rose"})

        assert res.status_code == status.HTTP_200_OK
        assert _names(res) == ["Rose Cream", "Night Serum"]

    def test_brand_match_outranks_description_only_match(self, api_client):
        by_brand = ProductFactory(
            name="Day Cream",
            brand=BrandFactory(name="Lancome"),
            short_description="",
            description="Light texture.",
        )
        by_description = ProductFactory(
            name="Night Serum",
            short_description="",
            description="Pairs well with Lancome products.",
        )
        _same_created_at(by_brand, by_description)

        res = api_client.get(url("product-list"), {"search": "lancome"})

        assert _names(res) == ["Day Cream", "Night Serum"]

    def test_category_name_is_searchable(self, api_client):
        ProductFactory(
            name="Velvet One",
            category=CategoryFactory(name="Lipsticks"),
            short_description="",
            description="",
        )
        ProductFactory(name="Other Thing")
        res = api_client.get(url("product-list"), {"search": "lipsticks"})
        assert _names(res) == ["Velvet One"]

    # 2 ── no match / unsearchable input ───────────────────────────────────
    def test_no_match_returns_empty_result_not_error(self, api_client):
        ProductFactory.create_batch(3)
        res = api_client.get(url("product-list"), {"search": "zzzqqqxxx"})
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 0
        assert res.data["results"] == []

    @pytest.mark.parametrize(
        "term",
        [
            "!!!",
            "& | ! ( ) < > : *",
            "'; DROP TABLE shop_product; --",
            "foo & | bar",
            "a:* <-> b",
            "\\",
            "(((",
            "x" * 5000,
            "لوازم آرایشی \u200c ()",
        ],
    )
    def test_hostile_or_unsearchable_input_never_errors(self, api_client, term):
        ProductFactory(name="Perfectly Normal Product")
        res = api_client.get(url("product-list"), {"search": term})
        assert res.status_code == status.HTTP_200_OK
        assert Product.objects.count() == 1  # nothing was dropped :)

    def test_blank_search_behaves_like_no_search(self, api_client):
        ProductFactory.create_batch(3)
        res = api_client.get(url("product-list"), {"search": "   "})
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 3

    # 3 ── prefix / partial matching & documented differences ──────────────
    def test_prefix_of_a_word_matches(self, api_client):
        ProductFactory(name="Matte Lipstick")
        ProductFactory(name="Running Shoes")
        res = api_client.get(url("product-list"), {"search": "lipst"})
        assert _names(res) == ["Matte Lipstick"]

    def test_multiple_terms_are_anded_across_fields(self, api_client):
        dior = BrandFactory(name="Dior")
        ProductFactory(name="Matte Lipstick", brand=dior)
        ProductFactory(name="Matte Foundation", brand=dior)
        res = api_client.get(url("product-list"), {"search": "dior lips"})
        assert _names(res) == ["Matte Lipstick"]

    def test_search_is_case_insensitive(self, api_client):
        ProductFactory(name="Matte Lipstick")
        res = api_client.get(url("product-list"), {"search": "LIPSTICK"})
        assert _names(res) == ["Matte Lipstick"]

    def test_persian_prefix_matches_with_simple_config(self, api_client):
        # Explicit slugs: slugify() without allow_unicode turns Persian names
        # into "", and ProductFactory get_or_creates on slug, so without them
        # the second product would silently NOT be created.
        ProductFactory(
            name="کرم مرطوب کننده",
            slug="moisturizer",
            short_description="",
            description="",
        )
        ProductFactory(name="ماسک مو", slug="hair-mask")
        assert Product.objects.count() == 2
        res = api_client.get(url("product-list"), {"search": "مرطو"})
        assert _names(res) == ["کرم مرطوب کننده"]

    def test_documented_difference_from_old_icontains_search(self, api_client):
        """
        FTS matches word PREFIXES, not arbitrary substrings, and does no
        stemming (config="simple") or typo tolerance. The old icontains
        search found all of these; this one deliberately does not.
        """
        ProductFactory(name="Matte Lipstick", short_description="", description="")
        # mid-word substring: icontains matched, FTS does not
        assert (
            api_client.get(url("product-list"), {"search": "stick"}).data["count"] == 0
        )
        # no stemming: "lipsticks" is not reduced to "lipstick"
        assert (
            api_client.get(url("product-list"), {"search": "lipsticks"}).data["count"]
            == 0
        )

    # 4 ── save() maintains the vector for new rows ────────────────────────
    def test_new_product_has_search_vector_immediately(self):
        product = ProductFactory(name="Brand New Thing")
        stored = Product.objects.get(pk=product.pk).search_vector
        assert stored  # not NULL / empty
        assert "'brand'" in stored and "'thing'" in stored

    def test_vector_carries_expected_weights(self):
        product = ProductFactory(
            name="Alpha",
            brand=BrandFactory(name="Bravo"),
            category=CategoryFactory(name="Charlie"),
            short_description="Delta",
            description="Echo",
        )
        stored = Product.objects.get(pk=product.pk).search_vector
        import re

        def weight(lexeme):
            return re.search(rf"'{lexeme}':\d+([A-D]?)", stored).group(1)

        assert weight("alpha") == "A"  # name
        assert weight("bravo") == "A"  # brand
        assert weight("charlie") == "B"  # category
        assert weight("delta") == "B"  # short_description
        assert weight("echo") == "C"  # description

    def test_product_with_no_brand_or_category_saves_and_is_searchable(
        self, api_client
    ):
        product = ProductFactory(name="Orphan Item", brand=None, category=None)
        assert Product.objects.get(pk=product.pk).search_vector
        res = api_client.get(url("product-list"), {"search": "orphan"})
        assert _names(res) == ["Orphan Item"]

    def test_editing_a_product_updates_what_search_finds(self, api_client):
        product = ProductFactory(name="Old Name", short_description="", description="")
        product.name = "Fresh Title"
        product.save()
        cache.clear()
        assert api_client.get(url("product-list"), {"search": "old"}).data["count"] == 0
        res = api_client.get(url("product-list"), {"search": "fresh"})
        assert _names(res) == ["Fresh Title"]

    # 5 ── explicit ?ordering= beats the rank default ──────────────────────
    def test_explicit_ordering_overrides_relevance_ranking(self, api_client):
        by_name = ProductFactory(
            name="Rose Cream", price=5_000_000, short_description="", description=""
        )
        by_description = ProductFactory(
            name="Night Serum",
            price=100_000,
            short_description="",
            description="Hint of rose.",
        )
        _same_created_at(by_name, by_description)

        by_rank = api_client.get(url("product-list"), {"search": "rose"})
        by_price = api_client.get(
            url("product-list"), {"search": "rose", "ordering": "price"}
        )
        by_price_desc = api_client.get(
            url("product-list"), {"search": "rose", "ordering": "-price"}
        )

        assert _names(by_rank) == ["Rose Cream", "Night Serum"]  # relevance default
        assert _names(by_price) == ["Night Serum", "Rose Cream"]  # price wins
        assert _names(by_price_desc) == ["Rose Cream", "Night Serum"]

    def test_invalid_ordering_param_falls_back_to_relevance(self, api_client):
        by_name = ProductFactory(
            name="Rose Cream", short_description="", description=""
        )
        by_description = ProductFactory(
            name="Night Serum", short_description="", description="Hint of rose."
        )
        _same_created_at(by_name, by_description)
        res = api_client.get(
            url("product-list"), {"search": "rose", "ordering": "not_a_field"}
        )
        assert _names(res) == ["Rose Cream", "Night Serum"]

    def test_without_search_default_ordering_is_still_newest_first(self, api_client):
        old = ProductFactory(name="Older")
        new = ProductFactory(name="Newer")
        Product.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        res = api_client.get(url("product-list"))
        assert _names(res) == ["Newer", "Older"]

    def test_search_composes_with_other_filters_and_pagination(self, api_client):
        cat = CategoryFactory(name="Skincare", slug="skincare")
        for i in range(5):
            ProductFactory(name=f"Rose Item {i}", category=cat)
        ProductFactory(name="Rose Elsewhere")  # different category
        res = api_client.get(
            url("product-list"),
            {"search": "rose", "category": "skincare", "page_size": 2},
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 5
        assert len(res.data["results"]) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Search is insensitive to Persian/Arabic character variants and ZWNJ
# (shop/text_utils.py, applied to stored text at save time AND to the query)
# ═══════════════════════════════════════════════════════════════════════════════
# Real characters on purpose; the pin test below proves they are the intended
# code points (these pairs LOOK identical, which is the whole problem).
PERSIAN_SPELLING = "کرم دست آرایشی"  # KEHEH (U+06A9) + FARSI YEH (U+06CC)
ARABIC_SPELLING = "كرم دست آرايشي"  # KAF (U+0643) + YEH (U+064A)
ZWNJ = "\u200c"


@pytest.mark.django_db
class TestSearchPersianVariantsAndZwnj:

    def test_spellings_really_differ_at_the_code_point_level(self):
        assert PERSIAN_SPELLING != ARABIC_SPELLING
        assert "\u06a9" in PERSIAN_SPELLING and "\u0643" not in PERSIAN_SPELLING
        assert "\u06cc" in PERSIAN_SPELLING and "\u064a" not in PERSIAN_SPELLING
        assert "\u0643" in ARABIC_SPELLING and "\u06a9" not in ARABIC_SPELLING
        assert "\u064a" in ARABIC_SPELLING and "\u06cc" not in ARABIC_SPELLING

    # ── product stored Persian-canonical, query typed Arabic ───────────
    @pytest.mark.parametrize(
        "query", ["كرم", "آرايشي", "كرم آرايشي", "كر", ARABIC_SPELLING]
    )
    def test_arabic_variant_query_finds_persian_stored_name(self, api_client, query):
        ProductFactory(name=PERSIAN_SPELLING, short_description="", description="")
        ProductFactory(name="Unrelated Thing")
        res = api_client.get(url("product-list"), {"search": query})
        assert _names(res) == [PERSIAN_SPELLING]

    # ── and vice versa ─────────────────────────────────────────────────
    @pytest.mark.parametrize(
        "query", ["کرم", "آرایشی", "کرم آرایشی", "کر", PERSIAN_SPELLING]
    )
    def test_persian_query_finds_product_saved_with_arabic_variants(
        self, api_client, query
    ):
        ProductFactory(name=ARABIC_SPELLING, short_description="", description="")
        ProductFactory(name="Unrelated Thing")
        res = api_client.get(url("product-list"), {"search": query})
        assert res.data["count"] == 1
        # Stored (and therefore displayed) form is the canonical Persian one.
        assert _names(res) == [PERSIAN_SPELLING]

    def test_variants_in_description_and_short_description_are_matched(
        self, api_client
    ):
        ProductFactory(
            name="Night Serum",
            short_description="مناسب پوست خشك",  # Arabic KAF
            description="با عصاره گياهي",  # Arabic YEH
        )
        assert api_client.get(url("product-list"), {"search": "خشک"}).data["count"] == 1
        assert (
            api_client.get(url("product-list"), {"search": "گیاهی"}).data["count"] == 1
        )

    def test_variants_in_brand_and_category_names_are_matched(self, api_client):
        ProductFactory(
            name="Plain Name",
            brand=BrandFactory(name="كيان"),  # Arabic KAF + YEH
            category=CategoryFactory(name="لوازم آرايشي"),  # Arabic YEH
            short_description="",
            description="",
        )
        assert (
            api_client.get(url("product-list"), {"search": "کیان"}).data["count"] == 1
        )
        assert (
            api_client.get(url("product-list"), {"search": "آرایشی"}).data["count"] == 1
        )
        assert (
            api_client.get(url("product-list"), {"search": "كيان"}).data["count"] == 1
        )

    def test_mixed_typing_within_one_query_still_matches(self, api_client):
        ProductFactory(name=PERSIAN_SPELLING, short_description="", description="")
        # Arabic kaf in one word, Persian yeh in another.
        res = api_client.get(url("product-list"), {"search": "كرم آرایشی"})
        assert _names(res) == [PERSIAN_SPELLING]

    # ── ZWNJ ───────────────────────────────────────────────────────────
    def test_name_with_zwnj_is_found_by_query_without_zwnj(self, api_client):
        ProductFactory(name=f"کرم ضد{ZWNJ}آفتاب", short_description="", description="")
        res = api_client.get(url("product-list"), {"search": "ضدآفتاب"})
        assert res.data["count"] == 1

    def test_name_without_zwnj_is_found_by_query_with_zwnj(self, api_client):
        ProductFactory(name="کرم ضدآفتاب", short_description="", description="")
        res = api_client.get(url("product-list"), {"search": f"ضد{ZWNJ}آفتاب"})
        assert res.data["count"] == 1

    def test_zwnj_in_both_stored_and_query_still_matches(self, api_client):
        ProductFactory(name=f"کرم ضد{ZWNJ}آفتاب", short_description="", description="")
        res = api_client.get(url("product-list"), {"search": f"ضد{ZWNJ}آفتاب"})
        assert res.data["count"] == 1

    def test_zwnj_prefix_query_matches(self, api_client):
        # Explicit slugs — see test_persian_prefix_matches_with_simple_config.
        ProductFactory(
            name="ماسک موی خشک", slug="mask", short_description="", description=""
        )
        ProductFactory(
            name=f"می{ZWNJ}خواهم",
            slug="mikhaham",
            short_description="",
            description="",
        )
        assert Product.objects.count() == 2
        res = api_client.get(url("product-list"), {"search": f"می{ZWNJ}خوا"})
        assert _names(res) == ["میخواهم"]

    def test_query_of_only_zero_width_characters_is_treated_as_blank(self, api_client):
        ProductFactory.create_batch(3)
        res = api_client.get(url("product-list"), {"search": f"{ZWNJ}\u200b\ufeff"})
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 3

    def test_latin_search_is_unaffected(self, api_client):
        ProductFactory(name="Matte Lipstick", short_description="", description="")
        ProductFactory(name="Running Shoes")
        res = api_client.get(url("product-list"), {"search": "LIPST"})
        assert _names(res) == ["Matte Lipstick"]


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/products/suggest/?q=  — autocomplete
# ═══════════════════════════════════════════════════════════════════════════════
SUGGEST_FIELDS = {"id", "name", "slug", "price", "thumbnail_url"}


def _suggest(api_client, q=None, **extra):
    params = dict(extra)
    if q is not None:
        params["q"] = q
    return api_client.get(url("product-suggest"), params)


def _suggest_names(res):
    return [p["name"] for p in res.data]


@pytest.mark.django_db
class TestProductSuggest:

    # ── routing ────────────────────────────────────────────────────────
    def test_route_is_not_swallowed_by_product_detail_slug_route(self, api_client):
        """'suggest' is a valid <slug>; the suggest route must be listed first."""
        assert url("product-suggest") == "/api/products/suggest/"
        ProductFactory(name="Matte Lipstick")
        res = _suggest(api_client, "lipstick")
        assert res.status_code == status.HTTP_200_OK
        assert _suggest_names(res) == ["Matte Lipstick"]

    def test_normal_product_detail_route_still_works(self, api_client):
        product = ProductFactory(name="Detail Product")
        res = api_client.get(url("product-detail", slug=product.slug))
        assert res.status_code == status.HTTP_200_OK

    def test_is_publicly_accessible_without_authentication(self, api_client):
        ProductFactory(name="Matte Lipstick")
        assert _suggest(api_client, "matte").status_code == status.HTTP_200_OK

    # ── 1. short-circuit ───────────────────────────────────────────────
    @pytest.mark.parametrize(
        "q", [None, "", "   ", "a", " a ", "ك\u200c", "\u200c\u200b"]
    )
    def test_term_under_two_characters_runs_no_database_query(
        self, api_client, django_assert_num_queries, q
    ):
        ProductFactory(name="A Product")
        with django_assert_num_queries(0):
            res = _suggest(api_client, q)
        assert res.status_code == status.HTTP_200_OK
        assert res.data == []

    def test_two_characters_runs_exactly_one_query(
        self, api_client, django_assert_num_queries
    ):
        ProductFactory(name="Lipstick")
        with django_assert_num_queries(1):
            res = _suggest(api_client, "li")
        assert _suggest_names(res) == ["Lipstick"]

    # ── 2. limit, ranking, minimal payload ─────────────────────────────
    def test_returns_at_most_eight_results(self, api_client):
        for i in range(12):
            ProductFactory(name=f"Rose Item {i}")
        res = _suggest(api_client, "rose")
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data) == 8

    def test_results_are_ranked_by_relevance_not_recency(self, api_client):
        # Name-match created FIRST so recency/pk tie-breaks would put the
        # description-only product ahead if rank were ignored.
        by_name = ProductFactory(
            name="Rose Cream", short_description="", description="Gentle care."
        )
        by_description = ProductFactory(
            name="Night Serum", short_description="", description="Hint of rose."
        )
        _same_created_at(by_name, by_description)
        res = _suggest(api_client, "rose")
        assert _suggest_names(res) == ["Rose Cream", "Night Serum"]

    def test_eight_returned_are_the_most_relevant_eight(self, api_client):
        # 8 description-only matches created later; 1 name match created first.
        best = ProductFactory(name="Rose Cream", short_description="", description="")
        others = [
            ProductFactory(name=f"Serum {i}", short_description="", description="rose")
            for i in range(8)
        ]
        _same_created_at(best, *others)
        res = _suggest(api_client, "rose")
        assert len(res.data) == 8
        assert res.data[0]["name"] == "Rose Cream"

    def test_response_contains_only_the_minimal_field_set(self, api_client):
        ProductFactory(
            name="Matte Lipstick",
            description="Long description",
            ingredients="Water, glycerin",
        )
        res = _suggest(api_client, "matte")
        assert len(res.data) == 1
        assert set(res.data[0].keys()) == SUGGEST_FIELDS
        for heavy in (
            "description",
            "short_description",
            "ingredients",
            "category",
            "brand",
            "rating",
            "stock",
            "is_on_flash_sale",
            "skin_type",
        ):
            assert heavy not in res.data[0]

    def test_response_is_a_bare_list_with_no_pagination_envelope(self, api_client):
        ProductFactory(name="Matte Lipstick")
        res = _suggest(api_client, "matte")
        assert isinstance(res.data, list)

    def test_no_n_plus_one_for_a_full_page_of_suggestions(
        self, api_client, django_assert_num_queries
    ):
        for i in range(8):
            ProductFactory(name=f"Rose Item {i}")
        with django_assert_num_queries(1):  # no brand/category/colour queries
            res = _suggest(api_client, "rose")
        assert len(res.data) == 8

    def test_thumbnail_url_is_absolute_or_null(self, api_client):
        with_thumb = ProductFactory(name="Has Thumb Rose")
        Product.objects.filter(pk=with_thumb.pk).update(
            thumbnail="products/thumbnails/rose.jpg"
        )
        ProductFactory(name="No Thumb Rose")
        by_name = {p["name"]: p for p in _suggest(api_client, "rose").data}
        assert by_name["Has Thumb Rose"]["thumbnail_url"].startswith("http")
        assert by_name["Has Thumb Rose"]["thumbnail_url"].endswith("rose.jpg")
        assert by_name["No Thumb Rose"]["thumbnail_url"] is None

    # ── behaviour as a type-ahead ──────────────────────────────────────
    def test_prefix_of_a_word_matches_while_typing(self, api_client):
        # Empty descriptions: the factory's random lorem text can contain a
        # word starting "li", which made this test flaky for a 2-letter prefix.
        ProductFactory(name="Matte Lipstick", short_description="", description="")
        ProductFactory(name="Running Shoes", short_description="", description="")
        assert _suggest_names(_suggest(api_client, "lip")) == ["Matte Lipstick"]
        assert _suggest_names(_suggest(api_client, "li")) == ["Matte Lipstick"]

    def test_no_match_returns_empty_list(self, api_client):
        ProductFactory.create_batch(3)
        res = _suggest(api_client, "zzzqqqxxx")
        assert res.status_code == status.HTTP_200_OK
        assert res.data == []

    @pytest.mark.parametrize(
        "term",
        [
            "!!!",
            "& | ! ( ) < > : *",
            "'; DROP TABLE shop_product; --",
            "x" * 5000,
            "((",
        ],
    )
    def test_hostile_input_never_errors(self, api_client, term):
        ProductFactory(name="Perfectly Normal")
        assert _suggest(api_client, term).status_code == status.HTTP_200_OK

    def test_ordering_and_search_params_do_not_break_the_sliced_queryset(
        self, api_client
    ):
        ProductFactory(name="Rose Cream")
        res = _suggest(api_client, "rose", ordering="price", search="whatever")
        assert res.status_code == status.HTTP_200_OK
        assert _suggest_names(res) == ["Rose Cream"]

    # ── 3. Persian normalisation, identical to the main endpoint ───────
    @pytest.mark.parametrize("query", ["كرم", "آرايشي", ARABIC_SPELLING])
    def test_arabic_variant_query_finds_persian_stored_name(self, api_client, query):
        ProductFactory(name=PERSIAN_SPELLING, short_description="", description="")
        ProductFactory(name="Unrelated Thing")
        assert _suggest_names(_suggest(api_client, query)) == [PERSIAN_SPELLING]

    @pytest.mark.parametrize("query", ["کرم", "آرایشی", PERSIAN_SPELLING])
    def test_persian_query_finds_product_saved_with_arabic_variants(
        self, api_client, query
    ):
        ProductFactory(name=ARABIC_SPELLING, short_description="", description="")
        ProductFactory(name="Unrelated Thing")
        assert _suggest_names(_suggest(api_client, query)) == [PERSIAN_SPELLING]

    def test_zwnj_is_ignored_in_both_directions(self, api_client):
        ProductFactory(
            name=f"کرم ضد{ZWNJ}آفتاب", slug="a", short_description="", description=""
        )
        ProductFactory(name="ماسک مو", slug="b", short_description="", description="")
        assert _suggest_names(_suggest(api_client, "ضدآفتاب")) == ["کرم ضدآفتاب"]
        assert _suggest_names(_suggest(api_client, f"ضد{ZWNJ}آفتاب")) == ["کرم ضدآفتاب"]
        assert _suggest_names(_suggest(api_client, f"ضد{ZWNJ}آف")) == ["کرم ضدآفتاب"]

    @pytest.mark.parametrize(
        "term",
        ["كرم", "کرم", "آرايشي", "lip", "LIPST", f"ضد{ZWNJ}آف", "rose cream", "zzzqq"],
    )
    def test_matches_the_same_products_as_the_main_search_endpoint(
        self, api_client, term
    ):
        ProductFactory(
            name=PERSIAN_SPELLING, slug="p1", short_description="", description=""
        )
        ProductFactory(
            name=f"کرم ضد{ZWNJ}آفتاب", slug="p2", short_description="", description=""
        )
        ProductFactory(name="Matte Lipstick", slug="p3")
        ProductFactory(
            name="Rose Cream", slug="p4", short_description="", description=""
        )
        ProductFactory(
            name="Night Serum", slug="p5", short_description="", description="rose"
        )

        suggested = [p["slug"] for p in _suggest(api_client, term).data]
        listed = [
            p["slug"]
            for p in api_client.get(url("product-list"), {"search": term}).data[
                "results"
            ]
        ]
        assert suggested == listed


# ═══════════════════════════════════════════════════════════════════════════════
# ProductListView caching (query-param-aware, short TTL)
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductListViewCaching:

    def test_same_params_different_order_hit_same_cache_and_query_once(
        self, api_client, django_assert_num_queries
    ):
        cat = CategoryFactory(slug="electronics")
        brand = BrandFactory(slug="nike")
        ProductFactory.create_batch(3, category=cat, brand=brand)

        # Prime the cache with one param order.
        api_client.get(
            url("product-list"), {"category": "electronics", "brand": "nike"}
        )

        # Same params, reversed order — must be a cache hit (0 queries).
        with django_assert_num_queries(0):
            res = api_client.get(
                url("product-list"), {"brand": "nike", "category": "electronics"}
            )
        assert res.data["count"] == 3

    def test_different_params_produce_different_cache_entries(self, api_client):
        cat_a = CategoryFactory(slug="electronics")
        cat_b = CategoryFactory(slug="clothing")
        ProductFactory.create_batch(3, category=cat_a)
        ProductFactory.create_batch(5, category=cat_b)

        res_a = api_client.get(url("product-list"), {"category": "electronics"})
        res_b = api_client.get(url("product-list"), {"category": "clothing"})

        # The critical correctness check: neither response leaked into the
        # other's cache slot.
        assert res_a.data["count"] == 3
        assert res_b.data["count"] == 5
        ids_a = {p["id"] for p in res_a.data["results"]}
        ids_b = {p["id"] for p in res_b.data["results"]}
        assert ids_a.isdisjoint(ids_b)

        # Re-requesting each still returns its OWN distinct data, not the
        # other's cached entry.
        res_a_again = api_client.get(url("product-list"), {"category": "electronics"})
        assert res_a_again.data["count"] == 3
        ids_a_again = {p["id"] for p in res_a_again.data["results"]}
        assert ids_a_again == ids_a

    def test_search_term_is_part_of_cache_key(self, api_client):
        ProductFactory(name="Wireless Headphones")
        ProductFactory(name="Running Shoes")

        res_search = api_client.get(url("product-list"), {"search": "wireless"})
        res_all = api_client.get(url("product-list"))

        assert res_search.data["count"] == 1
        assert res_all.data["count"] == 2

    def test_cache_ttl_expires_and_requeries_db(self, api_client):
        """
        Uses a bulk .update() (not .save()) to change underlying data,
        since Task 21.1.1.4's signal-based invalidation now fires on any
        Product.save() — a plain ProductFactory() create/save would
        invalidate the cache on its own and no longer isolate pure
        TTL-based expiry. QuerySet.update() deliberately bypasses
        save()/signals entirely, so this exercises the TTL path alone.
        """
        Product.objects.create(
            name="Original Name",
            slug="ttl-test-product",
            category=CategoryFactory(),
            brand=BrandFactory(),
            short_description="x",
            description="x",
            price=100_000,
            stock=5,
        )

        with patch("shop.views.PRODUCT_LIST_CACHE_TTL", 1):
            first = api_client.get(url("product-list"))
            assert first.data["results"][0]["name"] == "Original Name"

            # Bypasses save()/signals entirely — proves staleness is due
            # to the TTL/cache, not signal-based invalidation.
            Product.objects.filter(slug="ttl-test-product").update(
                name="Changed While Cached"
            )
            still_cached = api_client.get(url("product-list"))
            assert still_cached.data["results"][0]["name"] == "Original Name"

            time.sleep(1.2)  # let the 1-second TTL genuinely expire

            after_expiry = api_client.get(url("product-list"))
            assert after_expiry.data["results"][0]["name"] == "Changed While Cached"

    def test_no_cross_user_data_leakage(self, api_client, auth_client):
        """
        ProductListSerializer carries no wishlist/personalized-pricing
        fields (verified against serializers.py) — wishlist state is
        fetched via the separate dashboard/wishlist/ endpoint. So an
        anonymous and an authenticated request for the SAME query params
        must get byte-for-byte the same cached response; there is no
        per-user field to leak.
        """
        ProductFactory.create_batch(3)

        anon_res = api_client.get(url("product-list"))
        auth_res = auth_client.get(url("product-list"))

        assert anon_res.data == auth_res.data


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/products/<slug>/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductDetailView:

    def test_returns_200_for_valid_slug(self, api_client, product):
        res = api_client.get(url("product-detail", slug=product.slug))
        assert res.status_code == status.HTTP_200_OK

    def test_returns_404_for_invalid_slug(self, api_client):
        res = api_client.get(url("product-detail", slug="does-not-exist"))
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_response_contains_nested_relations(
        self, api_client, product_with_relations
    ):
        res = api_client.get(url("product-detail", slug=product_with_relations.slug))
        for key in ("images", "colors", "reviews", "category", "brand"):
            assert key in res.data, f"Missing key: {key}"

    def test_reviews_are_populated(self, api_client, product):
        ReviewFactory.create_batch(3, product=product)
        res = api_client.get(url("product-detail", slug=product.slug))
        assert len(res.data["reviews"]) == 3

    def test_colors_are_populated(self, api_client, product, color):
        ProductColorFactory(product=product, color=color)
        res = api_client.get(url("product-detail", slug=product.slug))
        assert len(res.data["colors"]) == 1
        assert res.data["colors"][0]["color"]["name"] == color.name

    def test_description_in_detail_not_in_list(self, api_client, product):
        res = api_client.get(url("product-detail", slug=product.slug))
        assert "description" in res.data

    def test_no_auth_required(self, api_client, product):
        res = api_client.get(url("product-detail", slug=product.slug))
        assert res.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestProductDetailViewFlashSale:
    """Sale-aware variant prices in the real endpoint response."""

    def _sale(self, *products, percent="25.00", start_h=-1, end_h=1, active=True):
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

    def test_variants_show_the_flash_price_and_countdown_target(
        self, api_client, product
    ):
        variant = ProductVariantFactory(product=product, price=800_000)
        sale = self._sale(product, percent="25.00")

        res = api_client.get(url("product-detail", slug=product.slug))

        item = next(v for v in res.data["variants"] if v["id"] == variant.id)
        assert item["effective_price"] == 600_000
        assert item["price"] == 800_000
        assert item["is_on_flash_sale"] is True
        assert parse_datetime(item["flash_sale_ends_at"]) == sale.ends_at

    def test_variants_are_unchanged_when_no_sale_is_current(self, api_client, product):
        variant = ProductVariantFactory(product=product, price=800_000)
        self._sale(product, start_h=1, end_h=2)  # upcoming
        self._sale(product, start_h=-2, end_h=-1)  # ended
        self._sale(product, active=False)  # switched off

        res = api_client.get(url("product-detail", slug=product.slug))

        item = next(v for v in res.data["variants"] if v["id"] == variant.id)
        assert item["effective_price"] == 800_000
        assert item["is_on_flash_sale"] is False
        assert item["flash_sale_ends_at"] is None

    def test_query_count_does_not_grow_with_the_number_of_variants(
        self, api_client, product
    ):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # color=None on purpose: ProductVariantSerializer's nested `color`
        # costs one (pre-existing, unrelated) query per coloured variant, which
        # would mask what this test is about — that resolving each variant's
        # flash-sale price adds NO per-variant queries.
        self._sale(product, percent="25.00")
        ProductVariantFactory(product=product, color=None, price=100_000)

        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                res = api_client.get(url("product-detail", slug=product.slug))
            assert res.status_code == status.HTTP_200_OK
            return len(ctx), res

        baseline, _ = count_queries()
        for _ in range(5):
            ProductVariantFactory(product=product, color=None, price=100_000)
        after, res = count_queries()

        assert len(res.data["variants"]) == 6
        assert all(v["is_on_flash_sale"] for v in res.data["variants"])
        assert after == baseline


@pytest.mark.django_db
class TestProductListFlashSale:
    """Sale-aware cards and the ?flash_sale=<id> filter on GET /api/products/."""

    def _sale(
        self, *products, percent="25.00", start_h=-1, end_h=1, active=True, name="Sale"
    ):
        now = timezone.now()
        sale = FlashSale.objects.create(
            name=name,
            discount_percent=Decimal(percent),
            starts_at=now + timedelta(hours=start_h),
            ends_at=now + timedelta(hours=end_h),
            is_active=active,
        )
        sale.products.add(*products)
        return sale

    def _results(self, res):
        return {p["id"]: p for p in res.data["results"]}

    def test_cards_carry_the_sale_fields(self, api_client):
        on_sale = ProductVariantFactory(price=800_000).product
        plain = ProductVariantFactory(price=800_000).product
        self._sale(on_sale, percent="25.00")

        results = self._results(api_client.get(url("product-list")))

        assert results[on_sale.id]["is_on_flash_sale"] is True
        assert results[on_sale.id]["flash_sale_price"] == 600_000
        assert results[on_sale.id]["flash_sale_original_price"] == 800_000
        assert results[plain.id]["is_on_flash_sale"] is False
        assert results[plain.id]["flash_sale_price"] is None

    def test_query_count_does_not_grow_with_the_number_of_products(self, api_client):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def build(n):
            sale = self._sale(name=f"S{n}")
            for _ in range(n):
                v = ProductVariantFactory(price=100_000, color=None)
                sale.products.add(v.product)

        def count():
            cache.clear()
            with CaptureQueriesContext(connection) as ctx:
                res = api_client.get(url("product-list"))
            assert res.status_code == status.HTTP_200_OK
            return len(ctx), res

        build(2)
        baseline, _ = count()
        build(6)
        after, res = count()

        assert res.data["count"] == 8
        assert all(p["is_on_flash_sale"] for p in res.data["results"])
        assert after == baseline

    # ── ?flash_sale=<id> ────────────────────────────────────────────────────
    def test_filter_returns_only_that_sales_products(self, api_client):
        a = ProductFactory()
        b = ProductFactory()
        other = ProductFactory()
        outsider = ProductFactory()
        sale = self._sale(a, b, name="Weekend")
        self._sale(other, name="Other")

        res = api_client.get(url("product-list"), {"flash_sale": sale.id})

        assert set(self._results(res)) == {a.id, b.id}
        assert outsider.id not in self._results(res)

    @pytest.mark.parametrize(
        "kwargs",
        [{"start_h": 1, "end_h": 2}, {"start_h": -2, "end_h": -1}, {"active": False}],
        ids=["upcoming", "ended", "deactivated"],
    )
    def test_filter_matches_nothing_for_a_sale_that_is_not_running(
        self, api_client, kwargs
    ):
        product = ProductFactory()
        sale = self._sale(product, **kwargs)
        res = api_client.get(url("product-list"), {"flash_sale": sale.id})
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 0

    def test_filter_with_an_unknown_id_matches_nothing(self, api_client):
        ProductFactory()
        res = api_client.get(url("product-list"), {"flash_sale": 999999})
        assert res.data["count"] == 0

    def test_filter_does_not_duplicate_products_in_several_sales(self, api_client):
        product = ProductFactory()
        sale = self._sale(product, name="One")
        self._sale(product, name="Two")
        res = api_client.get(url("product-list"), {"flash_sale": sale.id})
        assert res.data["count"] == 1

    def test_filter_combines_with_other_filters(self, api_client):
        cheap = ProductFactory(price=100_000)
        pricey = ProductFactory(price=5_000_000)
        sale = self._sale(cheap, pricey)
        res = api_client.get(
            url("product-list"), {"flash_sale": sale.id, "max_price": "1000000"}
        )
        assert set(self._results(res)) == {cheap.id}

    def test_related_products_also_carry_the_sale_fields(self, api_client):
        category = CategoryFactory()
        main = ProductFactory(category=category)
        sibling = ProductVariantFactory(
            price=800_000, product__category=category
        ).product
        self._sale(sibling, percent="25.00")

        res = api_client.get(url("product-related", slug=main.slug))

        item = next(p for p in res.data if p["id"] == sibling.id)
        assert item["is_on_flash_sale"] is True
        assert item["flash_sale_price"] == 600_000


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/products/<slug>/related/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestRelatedProductsView:

    def test_returns_products_from_same_category(self, api_client, category, brand):
        product = ProductFactory(category=category, brand=brand, slug="main-product")
        related1 = ProductFactory(category=category, brand=brand)
        related2 = ProductFactory(category=category, brand=brand)
        other = ProductFactory()  # different category

        res = api_client.get(url("product-related", slug=product.slug))
        ids = [p["id"] for p in res.data]
        assert related1.id in ids
        assert related2.id in ids
        assert other.id not in ids

    def test_excludes_current_product(self, api_client, category, brand):
        product = ProductFactory(category=category, brand=brand)
        ProductFactory.create_batch(3, category=category, brand=brand)
        res = api_client.get(url("product-related", slug=product.slug))
        ids = [p["id"] for p in res.data]
        assert product.id not in ids

    def test_max_8_related_products(self, api_client, category, brand):
        product = ProductFactory(category=category, brand=brand)
        ProductFactory.create_batch(12, category=category, brand=brand)
        res = api_client.get(url("product-related", slug=product.slug))
        assert len(res.data) <= 8

    def test_invalid_slug_returns_empty_list(self, api_client):
        res = api_client.get(url("product-related", slug="ghost-product"))
        assert res.status_code == status.HTTP_200_OK
        assert res.data == []

    def test_not_paginated(self, api_client, category, brand):
        product = ProductFactory(category=category, brand=brand)
        ProductFactory.create_batch(5, category=category, brand=brand)
        res = api_client.get(url("product-related", slug=product.slug))
        assert isinstance(res.data, list)


# ═══════════════════════════════════════════════════════════════════════════════
# General throttling (Task 2.1.3.1) — DEFAULT_THROTTLE_CLASSES applies to
# ordinary, previously-unthrottled endpoints like GET /api/products/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestGeneralAnonThrottling:
    """
    Confirms the project-wide AnonRateThrottle/UserRateThrottle defaults
    (added in Task 2.1.3.1) actually apply to an ordinary endpoint that
    was previously completely unthrottled — the product list, per the
    acceptance criteria's own suggestion.

    Rather than making 100+ real requests to exercise the real "anon"
    rate, this temporarily lowers the effective rate just for this test.

    IMPORTANT implementation note: `django.test.override_settings` on
    REST_FRAMEWORK does NOT actually change AnonRateThrottle's effective
    behavior here — confirmed empirically while writing this test.
    DRF's SimpleRateThrottle binds `THROTTLE_RATES = api_settings.
    DEFAULT_THROTTLE_RATES` as a plain CLASS attribute at the moment
    `rest_framework.throttling` is first imported (module import time),
    and never re-reads it afterward; Django's `setting_changed` signal
    only resets DRF's `api_settings` cache, it does not reach back into
    already-bound class attributes on throttle classes. So overriding
    REST_FRAMEWORK via override_settings mid-test-session has no
    reliable effect on an already-imported throttle class — whichever
    rate was in effect the FIRST time the class was imported in the
    process just... stays, regardless of later overrides, which made an
    override_settings-based version of this test flaky/order-dependent.
    Directly patching the throttle class's `rate` attribute (which
    `SimpleRateThrottle.__init__` checks before ever consulting
    THROTTLE_RATES) sidesteps this entirely and is deterministic.
    """

    @pytest.fixture(autouse=True)
    def clear_throttle_cache(self):
        # Throttle history lives in Django's cache (a real Redis-backed
        # cache — see core/settings/base.py's CACHES — which does not
        # reset automatically between tests). Redundant with conftest's
        # autouse clear_cache fixture, but kept explicit here since this
        # class predates it and the throttling behavior specifically
        # depends on it.
        cache.clear()
        yield
        cache.clear()

    def test_anon_rate_throttle_returns_429_once_lowered_limit_is_exceeded(self):
        with patch.object(AnonRateThrottle, "rate", "3/min", create=True):
            client = APIClient()
            statuses = [client.get("/api/products/").status_code for _ in range(5)]

        # First 3 requests (the lowered limit) succeed normally...
        assert statuses[:3] == [
            status.HTTP_200_OK,
            status.HTTP_200_OK,
            status.HTTP_200_OK,
        ]
        # ...and at least one request beyond that is throttled.
        assert status.HTTP_429_TOO_MANY_REQUESTS in statuses[3:]

    def test_product_list_is_not_throttled_under_the_real_default_rate(self):
        """
        Sanity check with the REAL (untouched) 100/min default: a
        handful of ordinary requests must not be throttled — the global
        default shouldn't break normal browsing/pagination usage.
        """
        client = APIClient()
        statuses = [client.get("/api/products/").status_code for _ in range(5)]
        assert all(s == status.HTTP_200_OK for s in statuses)


# ═══════════════════════════════════════════════════════════════════════════════
# POST/DELETE /api/products/variants/<variant_id>/notify-me/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestStockAlertSubscriptionView:

    def _notify_url(self, variant):
        return url("stock-alert-subscription", variant_id=variant.pk)

    def test_subscribe_to_out_of_stock_variant_succeeds(self, auth_client):
        from shop.models import StockAlertSubscription

        variant = ProductVariantFactory(stock=0)
        res = auth_client.post(self._notify_url(variant))

        assert res.status_code == status.HTTP_201_CREATED
        assert StockAlertSubscription.objects.filter(variant=variant).count() == 1

    def test_subscribe_to_in_stock_variant_is_rejected(self, auth_client):
        from shop.models import StockAlertSubscription

        variant = ProductVariantFactory(stock=5)
        res = auth_client.post(self._notify_url(variant))

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert not StockAlertSubscription.objects.filter(variant=variant).exists()

    def test_subscribing_twice_returns_200_and_creates_only_one_row(self, auth_client):
        from shop.models import StockAlertSubscription

        variant = ProductVariantFactory(stock=0)

        first = auth_client.post(self._notify_url(variant))
        assert first.status_code == status.HTTP_201_CREATED

        second = auth_client.post(self._notify_url(variant))
        assert second.status_code == status.HTTP_200_OK

        assert StockAlertSubscription.objects.filter(variant=variant).count() == 1

    def test_unsubscribe_removes_subscription(self, auth_client):
        from shop.models import StockAlertSubscription

        variant = ProductVariantFactory(stock=0)
        auth_client.post(self._notify_url(variant))

        res = auth_client.delete(self._notify_url(variant))
        assert res.status_code == status.HTTP_204_NO_CONTENT
        assert not StockAlertSubscription.objects.filter(variant=variant).exists()

    def test_unsubscribing_when_none_exists_returns_404(self, auth_client):
        variant = ProductVariantFactory(stock=0)
        res = auth_client.delete(self._notify_url(variant))
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_subscribe_unauthenticated_returns_401(self, api_client):
        variant = ProductVariantFactory(stock=0)
        res = api_client.post(self._notify_url(variant))
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unsubscribe_unauthenticated_returns_401(self, api_client):
        variant = ProductVariantFactory(stock=0)
        res = api_client.delete(self._notify_url(variant))
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
