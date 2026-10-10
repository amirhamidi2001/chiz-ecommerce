"""
Coupon-redemption release shared by every code path that cancels an order.

Mirrors order.services.stock.release_reserved_stock: cancellation has more
than one entry point (cancel_order() for customer/admin cancellation, and
payments.services.finalize_transaction_failure() for a failed/abandoned
payment), and each must undo the coupon use the same way, so that logic
lives in exactly one place.

Import direction: order -> promotions (promotions.models refers to
"order.Order" only by string, and promotions.services imports nothing from
order), so there is no import cycle.
"""

from promotions.models import CouponRedemption


def release_coupon_redemption(order):
    """
    Delete any CouponRedemption attached to `order`.

    Deleting the row (rather than flagging it) is what makes the cancelled
    order stop counting toward Coupon.max_uses / uses_per_user:
    promotions.services.validate_coupon() counts only existing redemptions
    that are tied to an order, so a deleted row simply can't be counted.

    Idempotent and safe on orders with no coupon. Call it inside the same
    atomic block that sets the order's terminal status.

    Returns the number of redemption rows deleted (0 or 1).
    """
    deleted, _ = CouponRedemption.objects.filter(order=order).delete()
    return deleted
