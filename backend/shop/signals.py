"""
shop/signals.py
────────────────
Signal receivers for the shop app. Wired via ShopConfig.ready()
(shop/apps.py) so they're registered when Django starts.
"""

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django_redis import get_redis_connection

from .models import Category, Product, ProductVariant, StockMovement
from .tasks import notify_stock_alert_subscribers
from .views import CATEGORY_TREE_CACHE_KEY


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_tree_cache(sender, **kwargs):
    """
    Invalidate the cached category tree on any Category create, update,
    or delete. Fires on every save regardless of which field changed —
    Category writes are infrequent enough that this coarser approach
    costs essentially nothing and avoids the complexity of precise
    field-change detection.
    """
    cache.delete(CATEGORY_TREE_CACHE_KEY)


# ─── Product list cache invalidation ───────────────────────────────────────────
def invalidate_product_list_cache():
    """
    Clear ALL cached product-list responses (every filter-parameter
    combination) — a blunt but simple and correct approach, given
    there's no cheap way to know exactly which cached filter
    combinations a given product change might affect. This is a
    deliberate simplicity-over-precision tradeoff: fine-grained
    per-filter-combination tracking would add real complexity for
    uncertain benefit, since the cache repopulates on the next request
    to each combination and the 60s TTL (Task 21.1.1.3) already bounds
    staleness for anything this signal doesn't catch.

    Verified real key format in this project's Redis (KEY_PREFIX="chiz",
    default cache version 1): "chiz:1:product_list_v1:<hash>". The
    leading wildcard below matches that regardless of prefix/version.
    """
    redis_conn = get_redis_connection("default")
    keys = redis_conn.keys("*product_list_v1:*")
    if keys:
        redis_conn.delete(*keys)


@receiver(post_save, sender=Product)
def invalidate_cache_on_product_save(sender, **kwargs):
    """
    Any Product field change (name, description, category, price-adjacent
    fields, active/inactive status, etc.) can affect what appears in, or
    how it's displayed on, cached product-list pages — invalidate
    unconditionally. Product saves are far less frequent than
    ProductVariant stock decrements, so there's no cache-effectiveness
    concern here worth a field-change check.
    """
    invalidate_product_list_cache()


@receiver(pre_save, sender=ProductVariant)
def _capture_previous_variant_state(sender, instance, **kwargs):
    """
    Capture the pre-save price so post_save can tell whether it actually
    changed. Stock is deliberately NOT captured here — see
    invalidate_cache_on_variant_save's docstring for why stock-only
    changes don't trigger invalidation.
    """
    if instance.pk:
        try:
            instance._previous = ProductVariant.objects.only("price").get(
                pk=instance.pk
            )
        except ProductVariant.DoesNotExist:
            instance._previous = None
    else:
        instance._previous = None


@receiver(post_save, sender=ProductVariant)
def invalidate_cache_on_variant_save(sender, instance, created, **kwargs):
    """
    Invalidate on ProductVariant PRICE changes (and on brand-new
    variants), but deliberately NOT on stock-only changes.

    Rationale: ProductVariant.stock changes on every single order
    (Epic 1/3's decrement-on-purchase logic). If this signal fired a
    full cache wipe on every stock decrement, the product-list cache
    would rarely survive long enough to serve a hit under real order
    volume — defeating the point of Task 21.1.1.3's caching. A customer
    seeing "in stock" for up to 60 seconds after the last unit sold is
    an accepted, common e-commerce UX tradeoff; the existing short TTL
    is the staleness bound for stock specifically. Price changes (e.g.
    an admin activating a flash sale, Epic 9) get invalidated
    immediately instead, since stale pricing is a worse experience than
    stale stock and price changes are comparatively rare.
    """
    previous = getattr(instance, "_previous", None)
    price_changed = created or previous is None or previous.price != instance.price
    if price_changed:
        invalidate_product_list_cache()


@receiver(post_delete, sender=ProductVariant)
def invalidate_cache_on_variant_delete(sender, **kwargs):
    """A deleted variant can remove a product from listings entirely (if
    it was the last active variant) or change displayed price/stock —
    always invalidate."""
    invalidate_product_list_cache()


# ─── Stock-alert notifications ─────────────────────────────────────────────────
@receiver(post_save, sender=StockMovement)
def handle_stock_increase(sender, instance, created, **kwargs):
    """
    Detect a variant's stock going from 0 (or less) to positive, and
    queue notify_stock_alert_subscribers for it.

    Hooks into StockMovement creation rather than adding ad-hoc
    "was this a restock" checks separately into both real code paths
    that increase stock (order-cancellation restoration in
    order/views.py, and admin manual adjustment in
    dashboard/views.py's AdminVariantAdjustStockView) — both already
    create a StockMovement with a positive quantity_delta (verified
    against both call sites), so this single handler catches both
    without touching either view again.

    Uses the StockMovement's own recorded stock_after/quantity_delta
    to compute stock_before, rather than re-querying the variant's
    current stock — the variant's live value could have changed again
    by the time this handler runs, so the movement's own snapshot is
    the correct source of truth for "what was stock immediately before
    THIS movement".
    """
    if not created or instance.quantity_delta <= 0:
        return
    variant = instance.variant
    stock_before = instance.stock_after - instance.quantity_delta
    # Only notify if the variant actually WENT FROM zero (or negative,
    # though stock shouldn't go negative in practice) — a restock from
    # e.g. 3 to 8 units was never "out of stock" from the subscriber's
    # perspective and shouldn't spam anyone.
    if stock_before <= 0 and instance.stock_after > 0:
        notify_stock_alert_subscribers.delay(variant.id)
