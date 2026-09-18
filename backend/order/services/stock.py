"""
Stock-restoration logic shared by every code path that undoes an order's
already-reserved stock.

Extracted out of OrderDetailView.patch() (Epic 1 Task 1.1.1.4 / Epic 3
Task 3.1.1.5 / Epic 4 Task 4.1.1.3's cancellation flow) so that
Task 6.2.1.4's payment-failure path doesn't carry its own independently-
maintained copy of this logic. Both call sites now share one function —
financially/inventory-important logic like this should have exactly one
place to fix if a bug is ever found in it.
"""

from django.db import transaction
from shop.models import ProductVariant, StockMovement


def release_reserved_stock(order, *, actor=None, note=""):
    """
    Restore stock for every item on `order` back to its variant, logging
    a StockMovement per item.

    Must be called from within the same atomic block that also updates
    `order.status` (or wrapped in its own `transaction.atomic()` if the
    caller isn't already inside one) — this function itself opens one to
    guarantee the read-lock/increment/log sequence per item is atomic.

    Args:
        order: the Order whose reserved stock should be released. The
            caller is responsible for having already set `order.status`
            to its terminal value (e.g. CANCELLED) before or after
            calling this — this function only touches variant stock and
            StockMovement rows, never Order itself.
        actor: the User who triggered this release (e.g. the customer
            cancelling their own order), or None for a system-triggered
            release (e.g. a failed/abandoned payment) — mirrors
            StockMovement.actor's existing "null for system-triggered
            movements" semantics.
        note: free-text note stored on each StockMovement row for audit
            purposes (e.g. "Cancellation of order ..." or "Payment failed
            for order ...").
    """
    with transaction.atomic():
        for order_item in order.items.all():
            if order_item.variant_id is None:
                # Variant was deleted after the order was placed
                # (OrderItem.variant is SET_NULL) — nothing to restore.
                continue

            variant = ProductVariant.objects.select_for_update().get(
                pk=order_item.variant_id
            )
            variant.stock += order_item.quantity
            variant.save(update_fields=["stock"])

            StockMovement.objects.create(
                variant=variant,
                reason=StockMovement.Reason.CANCELLATION,
                quantity_delta=order_item.quantity,
                stock_after=variant.stock,
                actor=actor,
                related_order=order,
                note=note,
            )
