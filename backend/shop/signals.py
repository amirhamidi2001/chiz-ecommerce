"""
shop/signals.py
────────────────
Signal receivers for the shop app. Wired via ShopConfig.ready()
(shop/apps.py) so they're registered when Django starts.
"""

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver
from django_redis import get_redis_connection
from promotions.models import FlashSale

from .models import (
    Brand,
    Category,
    Product,
    ProductPriceSnapshot,
    ProductVariant,
    StockMovement,
)
from .search import refresh_product_search_vectors
from .tasks import notify_price_drop_subscribers, notify_stock_alert_subscribers
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


@receiver([post_save, post_delete], sender=FlashSale)
def invalidate_cache_on_flash_sale_change(sender, **kwargs):
    """
    Cached list pages carry each product's flash-sale fields, so creating,
    editing (discount, dates, is_active) or deleting a sale must clear them —
    same reasoning as a variant price change above. A sale simply STARTING or
    ENDING on schedule fires no signal; that is bounded by the 60s TTL.
    """
    invalidate_product_list_cache()


@receiver(m2m_changed, sender=FlashSale.products.through)
def invalidate_cache_on_flash_sale_products_change(sender, action, **kwargs):
    """Adding/removing products to a sale changes which cards show the sale
    (fires from either side: sale.products.add(...) or product.flash_sales.add(...))."""
    if action in ("post_add", "post_remove", "post_clear"):
        invalidate_product_list_cache()


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


@receiver(post_save, sender=Brand)
@receiver(post_save, sender=Category)
def refresh_search_vectors_on_brand_or_category_save(
    sender, instance, created, **kwargs
):
    """
    Brand and category names are part of each product's search_vector, so
    renaming one must refresh its products' vectors — Product.save() never
    runs for them. A brand-new brand/category has no products yet.
    """
    if created:
        return
    field = "brand" if sender is Brand else "category"
    refreshed = refresh_product_search_vectors(
        Product.objects.filter(**{field: instance})
    )
    if refreshed:
        invalidate_product_list_cache()


@receiver(pre_save, sender=ProductVariant)
def _capture_previous_variant_state(sender, instance, **kwargs):
    """
    Capture the pre-save price and active flag so post_save can tell
    whether either actually changed (is_active matters to the price-drop
    detection below: it decides which variants count toward a product's
    lowest price). Stock is deliberately NOT captured here — see
    invalidate_cache_on_variant_save's docstring for why stock-only
    changes don't trigger invalidation.
    """
    if instance.pk:
        try:
            instance._previous = ProductVariant.objects.only("price", "is_active").get(
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


# ─── Price-drop notifications ──────────────────────────────────────────────────
@receiver(post_save, sender=ProductVariant)
def handle_variant_price_change(sender, instance, created, **kwargs):
    """
    Keep the product's ProductPriceSnapshot baseline current and, when a
    variant change genuinely LOWERS the product's lowest_active_price,
    queue notify_price_drop_subscribers.

    "The price" of a multi-variant product is its lowest active variant
    price (Product.lowest_active_price, the storefront's "starting at"),
    so what matters is whether THAT figure fell relative to the newest
    snapshot — not whether this particular variant got cheaper. Cutting a
    variant that is still dearer than the cheapest one is no drop at all.

    Behaviours worth knowing:
    - Saves that change neither price nor is_active (every order line's
      stock decrement, every restock) return immediately. Besides saving
      work on the order path, this is what keeps a restock from ever
      looking like a price change.
    - A newly CREATED variant never notifies ("a product having a price
      for the first time" is not a drop), but it does record a baseline
      if there is none / the lowest price moved, so the product's NEXT
      real change has something to be compared against.
    - Increases (or any other change) record the new baseline silently.
    - Not detected: bulk .update() / bulk_create (no signals fire), and
      flash-sale discounts (time-windowed; no variant save).
    - The task is queued via transaction.on_commit so a rolled-back save
      (e.g. a later admin inline error) can't announce a drop that never
      persisted. Prices go as decimal strings: task args are JSON.
    """
    previous = getattr(instance, "_previous", None)
    if (
        not created
        and previous is not None
        and previous.price == instance.price
        and previous.is_active == instance.is_active
    ):
        return

    product = instance.product
    current_lowest = product.lowest_active_price
    if current_lowest is None:
        return

    last_snapshot = product.price_snapshots.first()
    if last_snapshot is None:
        # First time we've seen a price for this product: baseline only.
        ProductPriceSnapshot.objects.create(product=product, price=current_lowest)
        return
    if current_lowest == last_snapshot.price:
        return

    ProductPriceSnapshot.objects.create(product=product, price=current_lowest)
    if current_lowest < last_snapshot.price and not created:
        product_id = product.id
        old_price, new_price = str(last_snapshot.price), str(current_lowest)
        transaction.on_commit(
            lambda: notify_price_drop_subscribers.delay(
                product_id, old_price, new_price
            )
        )
