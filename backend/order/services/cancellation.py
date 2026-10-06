"""
The one authoritative implementation of "cancel an order".

Used by both the customer-facing cancellation endpoint
(order.views.OrderDetailView.patch) and the admin status endpoint
(dashboard.views.AdminOrderViewSet), so cancelling behaves identically
-- same transition rule, same atomic stock restoration, same audit
trail -- whichever path triggers it.

Stock restoration itself lives in order.services.stock.release_reserved_stock
(also shared with the payment-failure path); this function adds the
status transition, locking and idempotency around it.
"""

from django.db import transaction
from order.models import Order

from .state_machine import is_valid_transition
from .stock import release_reserved_stock


def cancel_order(order, actor=None, *, note=None):
    """
    Cancel `order`: set status to CANCELLED and restore stock for every
    item, atomically.

    * Raises ValueError if the order's status cannot move to CANCELLED
      (SHIPPED / DELIVERED).
    * Idempotent: an already-CANCELLED order is returned untouched, so
      stock can never be restored twice (e.g. customer and admin
      cancelling at the same moment, or a double-submitted request).
    * Locks the order row and re-checks its status under the lock, so the
      decision is made on the current DB state, not a stale in-memory copy.

    `actor` is the User performing the cancellation (stored on each
    StockMovement); `note` overrides the default audit note.

    The passed-in `order` instance is updated in place and returned.
    """
    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)

        if locked.status == Order.Status.CANCELLED:
            order.status = locked.status
            return order

        if not is_valid_transition(locked.status, Order.Status.CANCELLED):
            raise ValueError(f"Order in status '{locked.status}' cannot be cancelled.")

        locked.status = Order.Status.CANCELLED
        locked.save(update_fields=["status", "updated_at"])

        release_reserved_stock(
            locked,
            actor=actor,
            note=note or f"Cancellation of order {locked.order_number}",
        )

    order.status = locked.status
    order.updated_at = locked.updated_at
    return order
