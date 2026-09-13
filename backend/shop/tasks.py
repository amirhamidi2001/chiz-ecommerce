from celery import shared_task
from django.utils import timezone

from .models import ProductVariant


@shared_task
def deactivate_expired_variants():
    """
    Nightly task: deactivate ProductVariant rows whose expiration_date
    has passed but are still is_active=True. Task 3.3.1.2 already
    blocks NEW purchases of expired variants at add-to-cart/checkout,
    but doesn't remove them from browse/search/listing pages — this
    task handles that so an expired variant stops appearing at all,
    rather than appearing but silently being unpurchasable.

    Uses a bulk .update() deliberately — this does NOT trigger save()
    or model signals (including shop/signals.py's price-change cache
    invalidation, which only fires on save()). That's acceptable here:
    deactivation doesn't need any side effects (e.g. admin
    notifications) at this point in the project. If a future task adds
    a "notify admin when stock is auto-deactivated" requirement, that
    would need individual .save() calls or an explicit signal dispatch
    instead — out of scope for this task.

    NOTE: this also means the product-list cache (Tasks 21.1.1.3/
    21.1.1.4) is NOT invalidated when this runs, since that
    invalidation is signal-based and tied to .save()/.delete(). A
    deactivated variant could keep appearing on cached listings for up
    to the existing 60s TTL after this task runs — an acceptable
    staleness window given the same tradeoff already accepted
    elsewhere for stock-only changes, but worth knowing about if that
    changes.
    """
    today = timezone.now().date()
    updated = ProductVariant.objects.filter(
        expiration_date__isnull=False,
        expiration_date__lt=today,
        is_active=True,
    ).update(is_active=False)
    return f"Deactivated {updated} expired variant(s)."


@shared_task
def notify_stock_alert_subscribers(variant_id):
    """
    Notify pending StockAlertSubscriptions that a variant is back in
    stock, and mark them as notified. Queued by
    shop/signals.py's handle_stock_increase whenever a StockMovement
    records a genuine 0→positive stock transition (order-cancellation
    restoration or admin manual adjustment — see that signal for the
    detection logic).
    """
    from .models import ProductVariant, StockAlertSubscription

    try:
        variant = ProductVariant.objects.get(pk=variant_id)
    except ProductVariant.DoesNotExist:
        return "Variant no longer exists."

    subscriptions = StockAlertSubscription.objects.filter(
        variant=variant, notified_at__isnull=True
    ).select_related("user")

    count = 0
    for sub in subscriptions:
        # Actual email/SMS dispatch is Epic 16's notification system —
        # this task only marks subscribers as notified and is
        # deliberately structured so Epic 16 can plug in the real
        # send() call at the marked location below without touching
        # this detection/dedup logic.
        # TODO: Epic 16 — replace this comment with a real
        # notify(user, event="back_in_stock", context={"variant": variant})
        # call once the unified notification service exists.
        sub.notified_at = timezone.now()
        sub.save(update_fields=["notified_at"])
        count += 1
    return f"Notified {count} subscriber(s) for variant {variant_id}."
