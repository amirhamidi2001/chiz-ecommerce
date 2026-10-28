"""
GET /api/products/facet-counts/

The test catalogue is small enough to count by hand:

    name  skin         hair     gender  vegan  c-free  organic  category  spf  price
    A     oily         -        female   yes    yes     no      skincare   30   10
    B     oily         -        unisex   no     yes     no      skincare   -    20
    C     dry          -        female   yes    no      yes     skincare   50   30
    D     dry          -        male     no     no      no      haircare   -    40
    E     combination  -        unisex   yes    no      no      skincare   15   50
    F     -            curly    female   yes    yes     yes     haircare   -    60
    G     -            wavy     unisex   no     no      no      haircare   -    70
    H     -            -        male     no     no      no      haircare   -    80

    skin_type: oily 2, dry 2, combination 1            (H/F/G have none set)
    hair_type: curly 1, wavy 1
    gender:    unisex 3 (B,E,G), female 3 (A,C,F), male 2 (D,H)
    vegan 4 (A,C,E,F)   cruelty-free 3 (A,B,F)   organic 2 (C,F)
"""

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from shop.models import HairType, Product, ProductGender, SkinType
from shop.signals import invalidate_product_list_cache
from shop.tests.factories import (
    CategoryFactory,
    ColorFactory,
    ProductColorFactory,
    ProductFactory,
)

SKIN_VALUES = [v for v, _ in SkinType.choices]
HAIR_VALUES = [v for v, _ in HairType.choices]
GENDER_VALUES = [v for v, _ in ProductGender.choices]


def facets(client, **params):
    res = client.get(reverse("product-facet-counts"), params)
    assert res.status_code == status.HTTP_200_OK, res.data
    return res.data


def zeros(values, **nonzero):
    return {v: nonzero.get(v, 0) for v in values}


def skin(**n):
    return zeros(SKIN_VALUES, **n)


def hair(**n):
    return zeros(HAIR_VALUES, **n)


def gender(**n):
    return zeros(GENDER_VALUES, **n)


@pytest.fixture
def catalog(db):
    skincare = CategoryFactory(name="Skincare", slug="skincare")
    haircare = CategoryFactory(name="Haircare", slug="haircare")

    def mk(
        name,
        *,
        skin_type="",
        hair_type="",
        gender_="unisex",
        vegan=False,
        cf=False,
        organic=False,
        category=skincare,
        spf=None,
        price=100_000,
    ):
        return ProductFactory(
            name=name,
            skin_type=skin_type,
            hair_type=hair_type,
            gender=gender_,
            is_vegan=vegan,
            is_cruelty_free=cf,
            is_organic=organic,
            category=category,
            spf=spf,
            price=price,
            short_description="",
            description="",
        )

    return {
        "A": mk(
            "Rose Cream",
            skin_type="oily",
            gender_="female",
            vegan=True,
            cf=True,
            spf=30,
            price=100_000,
        ),
        "B": mk("Plain Gel", skin_type="oily", cf=True, price=200_000),
        "C": mk(
            "Rose Serum",
            skin_type="dry",
            gender_="female",
            vegan=True,
            organic=True,
            spf=50,
            price=300_000,
        ),
        "D": mk(
            "Dry Balm",
            skin_type="dry",
            gender_="male",
            category=haircare,
            price=400_000,
        ),
        "E": mk(
            "Combo Lotion", skin_type="combination", vegan=True, spf=15, price=500_000
        ),
        "F": mk(
            "Curl Cream",
            hair_type="curly",
            gender_="female",
            vegan=True,
            cf=True,
            organic=True,
            category=haircare,
            price=600_000,
        ),
        "G": mk("Wave Spray", hair_type="wavy", category=haircare, price=700_000),
        "H": mk("Plain Wash", gender_="male", category=haircare, price=800_000),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Endpoint basics
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestEndpoint:

    def test_url_and_not_swallowed_by_the_product_slug_route(self, api_client, catalog):
        """'facet-counts' is a valid <slug>; the route must be listed before it."""
        assert reverse("product-facet-counts") == "/api/products/facet-counts/"
        assert "skin_type" in facets(api_client)

    def test_is_public(self, api_client, catalog):
        res = api_client.get(reverse("product-facet-counts"))
        assert res.status_code == status.HTTP_200_OK

    def test_response_shape(self, api_client, catalog):
        data = facets(api_client)
        assert set(data) == {
            "skin_type",
            "hair_type",
            "gender",
            "is_cruelty_free",
            "is_vegan",
            "is_organic",
        }  # no SPF: a range has no per-value counts
        assert set(data["skin_type"]) == set(SKIN_VALUES)
        assert set(data["hair_type"]) == set(HAIR_VALUES)
        assert set(data["gender"]) == set(GENDER_VALUES)
        assert all(isinstance(n, int) for n in data["gender"].values())
        assert all(
            isinstance(data[k], int)
            for k in ("is_vegan", "is_organic", "is_cruelty_free")
        )

    def test_empty_catalog_returns_all_zeros(self, api_client, db):
        data = facets(api_client)
        assert data["skin_type"] == skin()
        assert data["hair_type"] == hair()
        assert data["gender"] == gender()
        assert (data["is_vegan"], data["is_organic"], data["is_cruelty_free"]) == (
            0,
            0,
            0,
        )

    def test_invalid_filter_value_is_a_400_like_the_list_endpoint(
        self, api_client, catalog
    ):
        res = api_client.get(reverse("product-facet-counts"), {"min_spf": "abc"})
        listed = api_client.get(reverse("product-list"), {"min_spf": "abc"})
        assert res.status_code == listed.status_code == status.HTTP_400_BAD_REQUEST
        assert "min_spf" in res.data


# ═════════════════════════════════════════════════════════════════════════════
# 1. No filters -> the whole catalogue's distribution
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestUnfiltered:

    def test_skin_type_distribution(self, api_client, catalog):
        assert facets(api_client)["skin_type"] == skin(oily=2, dry=2, combination=1)

    def test_hair_type_distribution(self, api_client, catalog):
        assert facets(api_client)["hair_type"] == hair(curly=1, wavy=1)

    def test_gender_distribution(self, api_client, catalog):
        assert facets(api_client)["gender"] == gender(unisex=3, female=3, male=2)

    def test_boolean_flag_counts(self, api_client, catalog):
        data = facets(api_client)
        assert data["is_vegan"] == 4
        assert data["is_cruelty_free"] == 3
        assert data["is_organic"] == 2

    def test_products_with_no_skin_or_hair_type_are_not_counted_in_those_facets(
        self, api_client, catalog
    ):
        data = facets(api_client)
        assert sum(data["skin_type"].values()) == 5  # A-E; F, G, H have none
        assert sum(data["hair_type"].values()) == 2  # F, G only
        assert sum(data["gender"].values()) == 8  # every product has a gender


# ═════════════════════════════════════════════════════════════════════════════
# 2. One active filter: other facets narrow, its OWN facet does not
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestExcludeSelf:

    def test_other_facets_reflect_only_products_matching_the_active_filter(
        self, api_client, catalog
    ):
        data = facets(api_client, gender="female")  # A, C, F
        assert data["skin_type"] == skin(oily=1, dry=1)  # not 2 / 2 / combination 1
        assert data["hair_type"] == hair(curly=1)  # wavy (unisex) drops out
        assert data["is_vegan"] == 3  # A, C, F
        assert data["is_cruelty_free"] == 2  # A, F
        assert data["is_organic"] == 2  # C, F

    def test_the_active_facet_itself_still_shows_every_option_unfiltered(
        self, api_client, catalog
    ):
        data = facets(api_client, gender="female")
        # As if gender weren't filtered: what picking 'male' or 'unisex' would give.
        assert data["gender"] == gender(unisex=3, female=3, male=2)

    def test_skin_type_multi_select_does_not_narrow_its_own_counts(
        self, api_client, catalog
    ):
        data = facets(api_client, skin_type="oily,dry")  # A, B, C, D
        assert data["skin_type"] == skin(
            oily=2, dry=2, combination=1
        )  # incl. 'combination'
        assert data["hair_type"] == hair()  # none of A-D has a hair type
        assert data["gender"] == gender(unisex=1, female=2, male=1)

    def test_a_boolean_facet_does_not_narrow_its_own_count(self, api_client, catalog):
        data = facets(api_client, is_vegan="true")  # A, C, E, F
        assert data["is_vegan"] == 4  # unchanged
        assert data["skin_type"] == skin(oily=1, dry=1, combination=1)
        assert data["gender"] == gender(unisex=1, female=3)
        assert data["is_cruelty_free"] == 2  # A, F
        assert data["is_organic"] == 2  # C, F

    def test_each_facet_excludes_only_itself_when_several_are_active(
        self, api_client, catalog
    ):
        # oily AND female AND vegan  ->  only A satisfies all three
        data = facets(api_client, skin_type="oily", gender="female", is_vegan="true")
        # skin: counted under female+vegan (A, C, F)
        assert data["skin_type"] == skin(oily=1, dry=1)
        # gender: counted under oily+vegan (A)
        assert data["gender"] == gender(female=1)
        # vegan: counted under oily+female (A)
        assert data["is_vegan"] == 1
        # the other flags: under all three active filters (A)
        assert data["is_cruelty_free"] == 1
        assert data["is_organic"] == 0
        assert data["hair_type"] == hair()


# ═════════════════════════════════════════════════════════════════════════════
# 3. Booleans respect the other active filters
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestBooleanFacets:

    def test_counts_only_products_where_the_flag_is_true(self, api_client, catalog):
        assert facets(api_client)["is_vegan"] == 4  # not 8

    def test_respects_a_facet_filter(self, api_client, catalog):
        assert (
            facets(api_client, skin_type="oily")["is_vegan"] == 1
        )  # A (B isn't vegan)
        assert facets(api_client, skin_type="dry")["is_vegan"] == 1  # C

    def test_respects_other_boolean_filters(self, api_client, catalog):
        # vegan count while 'organic' is active: vegan AND organic = C, F
        assert facets(api_client, is_organic="true")["is_vegan"] == 2

    def test_a_single_integer_not_a_list(self, api_client, catalog):
        assert isinstance(facets(api_client)["is_organic"], int)


# ═════════════════════════════════════════════════════════════════════════════
# Every other filter and the search term apply too
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestOtherFiltersApply:

    def test_category(self, api_client, catalog):
        data = facets(api_client, category="haircare")  # D, F, G, H
        assert data["skin_type"] == skin(dry=1)
        assert data["hair_type"] == hair(curly=1, wavy=1)
        assert data["gender"] == gender(unisex=1, female=1, male=2)
        assert data["is_vegan"] == 1

    def test_price_range(self, api_client, catalog):
        data = facets(api_client, min_price=300_000, max_price=500_000)  # C, D, E
        assert data["skin_type"] == skin(dry=2, combination=1)

    def test_spf_range(self, api_client, catalog):
        data = facets(api_client, min_spf=30)  # A (30), C (50)
        assert data["skin_type"] == skin(oily=1, dry=1)
        assert data["gender"] == gender(female=2)

    def test_search_term(self, api_client, catalog):
        """?search= narrows the counts — otherwise /search would show catalogue-wide numbers."""
        data = facets(api_client, search="rose")  # A, C
        assert data["skin_type"] == skin(oily=1, dry=1)
        assert data["gender"] == gender(female=2)
        assert data["is_vegan"] == 2

    def test_search_term_combined_with_a_facet(self, api_client, catalog):
        data = facets(api_client, search="rose", skin_type="oily")  # A only
        assert data["skin_type"] == skin(oily=1, dry=1)  # excludes its own filter
        assert data["gender"] == gender(female=1)

    def test_search_with_no_matches_zeroes_everything(self, api_client, catalog):
        data = facets(api_client, search="zzzqqq")
        assert data["skin_type"] == skin()
        assert data["is_vegan"] == 0

    def test_blank_search_is_no_search(self, api_client, catalog):
        assert facets(api_client, search="  ") == facets(api_client)

    def test_unknown_facet_value_matches_nothing_but_leaves_its_own_counts(
        self, api_client, catalog
    ):
        data = facets(api_client, skin_type="bogus")
        assert data["skin_type"] == skin(oily=2, dry=2, combination=1)
        assert data["gender"] == gender()  # nothing has skin_type 'bogus'

    def test_paging_and_ordering_params_are_ignored(self, api_client, catalog):
        assert facets(api_client, page=2, page_size=1, ordering="-price") == facets(
            api_client
        )


# ═════════════════════════════════════════════════════════════════════════════
# Joins must not inflate counts
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestNoDoubleCounting:

    def test_a_product_matching_two_selected_colours_is_counted_once(
        self, api_client, catalog
    ):
        red, blue = ColorFactory(name="Red"), ColorFactory(name="Blue")
        ProductColorFactory(product=catalog["A"], color=red)
        ProductColorFactory(product=catalog["A"], color=blue)

        data = facets(api_client, color=f"{red.id},{blue.id}")

        # The colour filter JOINs, so A appears twice in the filtered rows.
        assert data["skin_type"] == skin(oily=1)
        assert data["gender"] == gender(female=1)
        assert data["is_vegan"] == 1
        assert data["is_cruelty_free"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# The definition: a count == what the list endpoint would return
# ═════════════════════════════════════════════════════════════════════════════
def list_count(client, **params):
    res = client.get(reverse("product-list"), {**params, "page_size": 1})
    assert res.status_code == status.HTTP_200_OK
    return res.data["count"]


@pytest.mark.django_db
class TestMatchesTheListEndpoint:
    """
    For every option of every facet: the count reported must equal the `count`
    the product-list endpoint returns when that option is added to the OTHER
    active filters. This is the property that makes the numbers trustworthy
    ("Oily (2)" means exactly 2 results), and it ties the facet logic to the
    real filters so the two can't drift apart.
    """

    CONTEXTS = [
        {},
        {"gender": "female"},
        {"skin_type": "oily,dry"},
        {"is_vegan": "true"},
        {"skin_type": "oily", "gender": "female", "is_vegan": "true"},
        {"category": "haircare"},
        {"min_price": 200_000, "max_price": 600_000},
        {"min_spf": 15, "is_cruelty_free": "true"},
        {"search": "rose"},
        {"search": "cream", "gender": "female"},
    ]

    @pytest.mark.parametrize(
        "ctx",
        CONTEXTS,
        ids=lambda c: "&".join(f"{k}={v}" for k, v in c.items()) or "none",
    )
    def test_every_count_equals_the_list_count(self, api_client, catalog, ctx):
        data = facets(api_client, **ctx)

        for facet, values in (
            ("skin_type", SKIN_VALUES),
            ("hair_type", HAIR_VALUES),
            ("gender", GENDER_VALUES),
        ):
            others = {k: v for k, v in ctx.items() if k != facet}
            for value in values:
                expected = list_count(api_client, **others, **{facet: value})
                assert data[facet][value] == expected, (facet, value, ctx)

        for flag in ("is_cruelty_free", "is_vegan", "is_organic"):
            others = {k: v for k, v in ctx.items() if k != flag}
            expected = list_count(api_client, **others, **{flag: "true"})
            assert data[flag] == expected, (flag, ctx)


# ═════════════════════════════════════════════════════════════════════════════
# Query cost and caching
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestQueryCostAndCache:

    def test_uncached_request_is_one_query_per_facet(
        self, api_client, catalog, django_assert_num_queries
    ):
        # 3 list facets (GROUP BY) + 3 boolean facets (COUNT) — and nothing
        # per product / per option.
        with django_assert_num_queries(6):
            facets(api_client, skin_type="oily", gender="female")

    def test_repeat_request_is_served_from_cache_with_no_queries(
        self, api_client, catalog, django_assert_num_queries
    ):
        first = facets(api_client, gender="female")
        with django_assert_num_queries(0):
            second = facets(api_client, gender="female")
        assert second == first

    def test_param_order_does_not_change_the_cache_key(
        self, api_client, catalog, django_assert_num_queries
    ):
        facets(api_client, skin_type="oily", gender="female")
        with django_assert_num_queries(0):
            facets(api_client, gender="female", skin_type="oily")

    def test_paging_and_ordering_share_one_cache_entry(
        self, api_client, catalog, django_assert_num_queries
    ):
        facets(api_client, gender="female")
        with django_assert_num_queries(0):
            facets(api_client, gender="female", page=3, ordering="price")

    def test_different_filters_are_cached_separately(self, api_client, catalog):
        assert facets(api_client, gender="female") != facets(api_client, gender="male")

    def test_invalid_requests_are_not_cached(self, api_client, catalog):
        api_client.get(reverse("product-facet-counts"), {"min_spf": "abc"})
        # nothing under the facets namespace was written
        from django_redis import get_redis_connection

        assert get_redis_connection("default").keys("*product_list_v1:facets:*") == []

    def test_clearing_the_product_list_cache_also_clears_facet_counts(
        self, api_client, catalog, django_assert_num_queries
    ):
        """Facet counts live in the product_list_v1 namespace so they are
        invalidated together with the cached list pages."""
        facets(api_client)
        invalidate_product_list_cache()
        with CaptureQueriesContext(connection) as ctx:
            facets(api_client)
        assert len(ctx) == 6  # recomputed, not served from cache

    def test_saving_a_product_refreshes_the_counts(self, api_client, catalog):
        assert facets(api_client)["skin_type"]["oily"] == 2  # warm the cache

        catalog["B"].skin_type = "sensitive"
        catalog["B"].save()  # post_save signal invalidates the cache

        data = facets(api_client)
        assert data["skin_type"]["oily"] == 1
        assert data["skin_type"]["sensitive"] == 1
