"""
order/signals.py
────────────────
The single hook point for "an order's status changed". Wired via
OrderConfig.ready() (order/apps.py), same pattern as shop/signals.py.

CUSTOMER NOTIFICATION (Epic 16)
    `_notify_customer_of_status_change` below is the receiver that routes a
    status change through `notifications.services.notify()`. Any further
    reaction can be attached the same way: add another receiver for
    `order_status_changed` -- no change to any order-mutating code path
    (checkout, payment callbacks, customer/admin cancellation, shipping
    polling) is needed, because they all go through Order.save().

    The receiver defers the send with `transaction.on_commit`: this signal
    fires synchronously inside Order.save(), which several callers
    (cancel_order, payment finalisation) run inside `transaction.atomic()`.
    If that transaction later rolls back, a notification sent directly from
    the receiver would already have gone out for a change that never
    happened. (Outside a transaction, on_commit runs immediately.)

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
from contextlib import contextmanager

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal, receiver
from django.utils import translation
from notifications.models import NotificationTemplate
from notifications.services import notify

from .models import Order

logger = logging.getLogger("order.notifications")

order_status_changed = Signal()


@contextmanager
def suppress_status_notification(order):
    """
    Save `order` without the generic "status changed" customer notification.

    For a transition that already sends its own, more specific message — the
    payment-success transition (PENDING -> PROCESSING) sends ORDER_CONFIRMED
    (see payments.services.finalize_transaction_success), and the generic
    status SMS on top would be a second text for the same moment. Scoped to
    the one instance and the `with` block, so an admin moving an order
    PENDING -> PROCESSING by hand still notifies the customer as usual.
    """
    order._suppress_status_notification = True
    try:
        yield
    finally:
        order._suppress_status_notification = False


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


def _status_label(status):
    """Customer-facing (Persian) label for a status code, whatever the
    active request language happens to be."""
    with translation.override(settings.LANGUAGE_CODE):
        return str(Order.Status(status).label)


@receiver(order_status_changed)
def _log_status_change_for_now(sender, order, previous_status, **kwargs):
    logger.info(
        "Order %s status changed: %s -> %s",
        order.order_number,
        previous_status,
        order.status,
    )


@receiver(order_status_changed)
def _notify_customer_of_status_change(sender, order, previous_status, **kwargs):
    # A brand-new order (previous_status is None) isn't a *change*; the
    # customer hears about it through the order-confirmed event instead.
    if previous_status is None:
        return
    # The caller sends its own message for this transition.
    if getattr(order, "_suppress_status_notification", False):
        return

    # Snapshot everything now: `order` is the live instance and may be mutated
    # (or re-saved) before the transaction commits.
    context = {
        "order_number": order.order_number,
        "old_status": previous_status,
        "new_status": order.status,
        # Persian label for the message text ({status} in the templates).
        "status": _status_label(order.status),
        # Checkout contact details: the only way to reach a guest order
        # (order.user is None), and what the customer entered otherwise.
        "customer_name": order.first_name,
        "email": order.email,
        "phone_number": order.phone,
    }
    user = order.user

    transaction.on_commit(
        lambda: notify(user, NotificationTemplate.Event.ORDER_STATUS_CHANGED, context)
    )
