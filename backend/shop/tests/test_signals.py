"""
shop/tests/test_signals.py
────────────────────────────
Tests for shop/signals.py's product-list cache invalidation
(Task 21.1.1.4), which sits on top of Task 21.1.1.3's short-TTL,
query-param-hashed ProductListView cache.

No dedicated signals-test file existed anywhere in this project before
this task, so these are integration-style tests that go through the
real ProductListView endpoint (to populate genuine `product_list_v1:*`
cache entries against real Redis) rather than calling the receivers
directly — this exercises the actual key-pattern match, not just the
Python logic.

IMPORTANT: Product has its own top-level price/stock fields, separate
from ProductVariant.price/stock — ProductListSerializer only ever
reflects Product-level values, never a variant's. So these tests check
Redis cache-key presence/absence directly (via django_redis's
get_redis_connection) rather than inferring invalidation from list
content, which would otherwise be confounded by the fact that creating
a brand-new Product is ITSELF an invalidating event (Product post_save
fires unconditionally).
"""

import pytest
from django.urls import reverse
from django_redis import get_redis_connection
from unittest.mock import patch

from shop.tests.factories import (
    ProductFactory,
    ProductVariantFactory,
    StockMovementFactory,
)
from shop.models import StockMovement


def url(name, **kwargs):
    return reverse(name, kwargs=kwargs)


def _product_list_cache_keys():
    redis_conn = get_redis_connection("default")
    return redis_conn.keys("*product_list_v1:*")


def _populate_several_cached_filter_combinations(api_client):
    """Prime several distinct cache entries for later invalidation checks."""
    api_client.get(url("product-list"))
    api_client.get(url("product-list"), {"ordering": "price"})
    api_client.get(url("product-list"), {"search": "widget"})


@pytest.mark.django_db
class TestProductListCacheInvalidation:

    def test_variant_price_change_clears_all_cached_entries(self, api_client):
        product = ProductFactory()
        variant = ProductVariantFactory(product=product, price=10, stock=5)
        _populate_several_cached_filter_combinations(api_client)

        assert len(_product_list_cache_keys()) == 3, (
            "Setup problem: expected 3 distinct cached filter combinations "
            "before the change."
        )

        variant.price = 25
        variant.save()

        assert _product_list_cache_keys() == [], (
            "A ProductVariant price change must clear EVERY cached "
            "product-list entry, not just some."
        )

    def test_variant_stock_only_change_does_not_clear_cache(self, api_client):
        product = ProductFactory()
        variant = ProductVariantFactory(product=product, price=10, stock=5)
        _populate_several_cached_filter_combinations(api_client)

        assert len(_product_list_cache_keys()) == 3

        variant.stock = 1
        variant.save()

        assert len(_product_list_cache_keys()) == 3, (
            "A stock-only change must NOT invalidate the cache — this is "
            "the deliberate documented exception (see signals.py)."
        )

    def test_product_field_change_invalidates_cache(self, api_client):
        product = ProductFactory(name="Original Name")
        _populate_several_cached_filter_combinations(api_client)
        assert len(_product_list_cache_keys()) == 3

        product.name = "Renamed Product"
        product.save()

        assert _product_list_cache_keys() == []

        # Confirm the NEXT request reflects the change, not stale data.
        res = api_client.get(url("product-list"))
        names = [p["name"] for p in res.data["results"]]
        assert "Renamed Product" in names
        assert "Original Name" not in names

    def test_deleting_variant_invalidates_cache(self, api_client):
        product = ProductFactory()
        variant = ProductVariantFactory(product=product, price=10, stock=5)
        _populate_several_cached_filter_combinations(api_client)
        assert len(_product_list_cache_keys()) == 3

        variant.delete()

        assert _product_list_cache_keys() == []

    def test_creating_new_variant_invalidates_cache(self, api_client):
        product = ProductFactory()
        _populate_several_cached_filter_combinations(api_client)
        assert len(_product_list_cache_keys()) == 3

        ProductVariantFactory(product=product, price=15, stock=3)

        assert _product_list_cache_keys() == []


# ═══════════════════════════════════════════════════════════════════════════════
# Stock-alert notification on 0→positive transitions (Task 4.1.2.3)
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestHandleStockIncreaseSignal:
    """
    Mocks notify_stock_alert_subscribers.delay directly — no real
    Celery worker/broker needed, per the acceptance criteria. These
    tests exercise the real StockMovement model (via the factory), so
    they genuinely test the post_save receiver's own detection logic,
    not just a hand-written call to it.
    """

    def test_restock_from_zero_triggers_notification(self):
        variant = ProductVariantFactory(stock=0)
        with patch("shop.signals.notify_stock_alert_subscribers.delay") as mock_delay:
            StockMovementFactory(
                variant=variant,
                reason=StockMovement.Reason.RESTOCK,
                quantity_delta=5,
                stock_after=5,
            )
        mock_delay.assert_called_once_with(variant.id)

    def test_restock_from_nonzero_does_not_trigger_notification(self):
        variant = ProductVariantFactory(stock=3)
        with patch("shop.signals.notify_stock_alert_subscribers.delay") as mock_delay:
            StockMovementFactory(
                variant=variant,
                reason=StockMovement.Reason.RESTOCK,
                quantity_delta=5,
                stock_after=8,  # 3 -> 8, never actually hit zero
            )
        mock_delay.assert_not_called()

    def test_sale_negative_delta_never_triggers_notification(self):
        variant = ProductVariantFactory(stock=5)
        with patch("shop.signals.notify_stock_alert_subscribers.delay") as mock_delay:
            StockMovementFactory(
                variant=variant,
                reason=StockMovement.Reason.SALE,
                quantity_delta=-5,
                stock_after=0,  # went TO zero, not FROM zero — not a restock
            )
        mock_delay.assert_not_called()
