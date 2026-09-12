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
