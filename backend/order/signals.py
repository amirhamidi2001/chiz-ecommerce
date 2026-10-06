"""
order/signals.py
────────────────
The single hook point for "an order's status changed". Wired via
OrderConfig.ready() (order/apps.py), same pattern as shop/signals.py.

HOW TO ATTACH REAL NOTIFICATIONS (Epic 16)
    Add another receiver for `order_status_changed` anywhere in your own
    app -- no change to any order-mutating code path (checkout, payment
    callbacks, customer/admin cancellation, shipping polling) is needed,
    because they all go through Order.save():

        @receiver(order_status_changed)
        def notify_customer(sender, order, previous_status, **kwargs):
            transaction.on_commit(lambda: notify(order.user, ...))

    Use `transaction.on_commit` in real receivers: this signal fires
    synchronously inside Order.save(), which several callers
    (cancel_order, payment finalisation) run inside `transaction.atomic()`.
    If that transaction later rolls back, a notification sent directly
    from the receiver would already have gone out for a change that never
    happened.

`order_status_changed` kwargs
    sender           -- the Order class
    order            -- the saved Order instance (new status on .status)
    previous_status  -- the status before this save, or None when the order
                        was just created

Known limit: `QuerySet.update()` / `bulk_update()` bypass save() and
therefore this signal. Nothing in the codebase updates Order.status that
way today; keep it that way (or send the signal explicitly) if that changes.
"""

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal, receiver

from .models import Order

logger = logging.getLogger("order.notifications")

order_status_changed = Signal()


@receiver(pre_save, sender=Order)
def _capture_previous_status(sender, instance, raw=False, update_fields=None, **kwargs):
    """Remember the status currently in the DB so post_save can compare."""
    instance._previous_status = None

    if raw or not instance.pk:
        return  # fixture load, or a brand-new row: nothing to compare against
    if update_fields is not None and "status" not in update_fields:
        return  # this save can't change status; skip the extra query

    try:
        instance._previous_status = (
            sender.objects.only("status").get(pk=instance.pk).status
        )
    except sender.DoesNotExist:
        instance._previous_status = None


@receiver(post_save, sender=Order)
def _handle_status_change(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    previous = getattr(instance, "_previous_status", None)
    # Reset so a stale value can never leak into a later save of this
    # same instance (pre_save re-captures on every save anyway).
    instance._previous_status = None

    if created or (previous is not None and previous != instance.status):
        order_status_changed.send(
            sender=Order, order=instance, previous_status=previous
        )


@receiver(order_status_changed)
def _log_status_change_for_now(sender, order, previous_status, **kwargs):
    # PLACEHOLDER -- real customer notification dispatch is Epic 16's job.
    logger.info(
        "Order %s status changed: %s -> %s "
        "(TODO: Epic 16 — dispatch real customer notification here)",
        order.order_number,
        previous_status,
        order.status,
    )
