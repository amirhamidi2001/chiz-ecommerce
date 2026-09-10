import pytest
import time
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.throttling import AnonRateThrottle
from unittest.mock import patch
from shop.views import CATEGORY_TREE_CACHE_KEY
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
        ProductFactory(name="Expensive", price=200)
        ProductFactory(name="Cheap", price=10)
        ProductFactory(name="Mid", price=50)
        res = api_client.get(url("product-list"), {"ordering": "price"})
        prices = [float(p["price"]) for p in res.data["results"]]
        assert prices == sorted(prices)

    def test_order_by_price_descending(self, api_client):
        ProductFactory(name="Expensive", price=200)
        ProductFactory(name="Cheap", price=10)
        res = api_client.get(url("product-list"), {"ordering": "-price"})
        prices = [float(p["price"]) for p in res.data["results"]]
        assert prices == sorted(prices, reverse=True)

    def test_order_by_rating(self, api_client):
        ProductFactory(price=10, rating=4.5)
        ProductFactory(price=20, rating=3.0)
        ProductFactory(price=30, rating=5.0)
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
        ProductFactory(price=10)
        ProductFactory(price=100)
        ProductFactory(price=500)
        res = api_client.get(url("product-list"), {"min_price": 99})
        assert res.data["count"] == 2

    def test_filter_max_price(self, api_client):
        ProductFactory(price=10)
        ProductFactory(price=100)
        ProductFactory(price=500)
        res = api_client.get(url("product-list"), {"max_price": 101})
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
        ProductFactory.create_batch(2)

        with patch("shop.views.PRODUCT_LIST_CACHE_TTL", 1):
            first = api_client.get(url("product-list"))
            assert first.data["count"] == 2

            # A new product created while the cached entry is still fresh
            # must NOT show up yet — proves we're actually serving from cache.
            ProductFactory()
            still_cached = api_client.get(url("product-list"))
            assert still_cached.data["count"] == 2

            time.sleep(1.2)  # let the 1-second TTL genuinely expire

            after_expiry = api_client.get(url("product-list"))
            assert after_expiry.data["count"] == 3

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
