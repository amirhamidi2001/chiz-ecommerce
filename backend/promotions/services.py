from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from .models import Coupon, CouponRedemption


@dataclass
class CouponValidationResult:
    valid: bool
    coupon: Coupon | None = None
    discount_amount: Decimal = Decimal("0")
    error: str = ""


@dataclass(frozen=True)
class CouponLine:
    """
    One priced line of a cart, reduced to what coupon eligibility needs:
    which product / category it belongs to and its line amount
    (unit price x quantity).
    """

    product_id: int | None
    category_id: int | None
    amount: Decimal


def cart_lines(cart) -> list[CouponLine]:
    """Build CouponLines from the cart's current items (live prices)."""
    return [
        CouponLine(
            product_id=item.variant.product_id,
            category_id=item.variant.product.category_id,
            amount=item.subtotal,
        )
        for item in cart.items.select_related("variant__product")
    ]


def validate_coupon(
    code: str, user, cart, *, lines: list[CouponLine] | None = None
) -> CouponValidationResult:
    """
    Check `code` against every Coupon constraint for `user` and `cart`.

    Returns a CouponValidationResult: valid=True with the coupon and the
    computed discount_amount, or valid=False with a specific `error`.

    Restrictions: if the coupon has categories and/or products set, only
    cart lines whose product is in `products` OR whose product's category
    is in `categories` are eligible, and the discount and
    min_order_amount are evaluated against the ELIGIBLE subtotal only.
    Category matching is exact — sub-categories are not included
    implicitly. With no restrictions, every line is eligible.

    `lines` is for checkout: order creation prices every item once, from
    the locked variant rows, and derives the whole order from that single
    snapshot. It passes that same snapshot here so the discount can't
    disagree with Order.subtotal because of a second, independent read of
    prices or cart items. Everywhere else leave it None and the lines are
    read from `cart`.

    Design notes:
    - Only COMPLETED redemptions (order__isnull=False) count toward
      max_uses / uses_per_user. An "applied to cart but never checked out"
      redemption row must not permanently consume a use.
    - Coupon redemption is authenticated-only (decision recorded on
      CouponRedemption, Task 9.1.1.3): uses_per_user has no meaning for an
      anonymous user, so guests are rejected here rather than given a
      limit that is trivially bypassable.
    - Fixed-amount discounts are capped at the eligible subtotal so a
      coupon can never discount more than the items it applies to.
    - This is a read-only pre-check and is NOT sufficient on its own to
      enforce the usage limits under concurrency: two checkouts can both
      pass this check before either records its redemption. The code that
      creates the completed redemption (order creation) locks the Coupon
      row (select_for_update) and re-runs this validation inside the same
      transaction.
    """
    try:
        coupon = Coupon.objects.get(code=code.upper().strip())
    except Coupon.DoesNotExist:
        return CouponValidationResult(valid=False, error="Invalid coupon code.")

    if not coupon.is_active:
        return CouponValidationResult(
            valid=False, error="This coupon is no longer active."
        )

    now = timezone.now()
    if now < coupon.valid_from:
        return CouponValidationResult(
            valid=False, error="This coupon is not yet valid."
        )
    if now > coupon.valid_until:
        return CouponValidationResult(valid=False, error="This coupon has expired.")

    if coupon.max_uses is not None:
        total_redemptions = CouponRedemption.objects.filter(
            coupon=coupon, order__isnull=False
        ).count()
        if total_redemptions >= coupon.max_uses:
            return CouponValidationResult(
                valid=False, error="This coupon has reached its usage limit."
            )

    if user is None or not user.is_authenticated:
        return CouponValidationResult(
            valid=False, error="Please log in to use a coupon code."
        )

    user_redemptions = CouponRedemption.objects.filter(
        coupon=coupon, user=user, order__isnull=False
    ).count()
    if user_redemptions >= coupon.uses_per_user:
        return CouponValidationResult(
            valid=False, error="You have already used this coupon."
        )

    # ── Eligible portion of the cart ─────────────────────────────────────
    if lines is None:
        lines = cart_lines(cart)

    category_ids = set(coupon.categories.values_list("pk", flat=True))
    product_ids = set(coupon.products.values_list("pk", flat=True))
    restricted = bool(category_ids or product_ids)

    # `or` (not `and`): a line matching EITHER restriction is eligible, and
    # a line matching both is still counted once.
    eligible_subtotal = sum(
        (
            line.amount
            for line in lines
            if not restricted
            or line.product_id in product_ids
            or line.category_id in category_ids
        ),
        Decimal("0"),
    )

    if eligible_subtotal == 0:
        return CouponValidationResult(
            valid=False, error="This coupon does not apply to any items in your cart."
        )

    if eligible_subtotal < coupon.min_order_amount:
        # "eligible" only means something to the customer when the coupon
        # is actually restricted.
        kind = "minimum eligible order" if restricted else "minimum order"
        return CouponValidationResult(
            valid=False,
            error=f"This coupon requires a {kind} of {coupon.min_order_amount}.",
        )

    if coupon.discount_type == Coupon.DiscountType.PERCENT:
        discount_amount = (eligible_subtotal * coupon.value / Decimal("100")).quantize(
            Decimal("0.01")
        )
    else:
        # Never discount more than the eligible items themselves.
        discount_amount = min(coupon.value, eligible_subtotal)

    return CouponValidationResult(
        valid=True, coupon=coupon, discount_amount=discount_amount
    )
