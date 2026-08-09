"""
Order pricing logic.

Extracted out of OrderCreateSerializer.create() so that total calculation
is a standalone, independently testable unit rather than logic buried
inside a serializer. This is expected to grow (coupon-based discounts,
real shipping-rate lookups, region-specific tax rules) — keeping it here
means future changes don't have to touch the serializer at all.

Note: this module is not yet wired into OrderCreateSerializer — that's a
separate follow-up task. As of now it's a standalone, unit-tested service.
"""

from decimal import Decimal
from typing import Dict

TWO_PLACES = Decimal("0.01")


class PricingError(ValueError):
    """Raised when pricing inputs are invalid (negative amounts, a discount
    that would make the total negative, etc.)."""


class PricingService:
    """
    Owns order total calculation: tax rate, shipping cost, and the
    subtotal/tax/discount/total formula.

    Kept as a class (rather than bare module-level functions) so that
    future variations — e.g. a region-specific subclass overriding
    TAX_RATE for Iranian tax rules, or overriding `calculate_order_totals`
    entirely for coupon-based discounts — have an obvious place to live
    without changing every call site.
    """

    TAX_RATE: Decimal = Decimal("0.10")  # 10%
    SHIPPING_COST: Decimal = Decimal("9.99")

    @classmethod
    def calculate_order_totals(
        cls,
        subtotal: Decimal,
        discount: Decimal = Decimal("0"),
    ) -> Dict[str, Decimal]:
        """
        Compute the full set of order totals for a given cart subtotal.

        Returns a dict with keys: "subtotal", "shipping_cost", "tax",
        "discount", "total" — all Decimal, quantized to 2 decimal places
        where rounding applies (tax and total), matching the exact
        formula previously inlined in OrderCreateSerializer.create():

            tax = (subtotal * TAX_RATE).quantize(Decimal("0.01"))
            total = (subtotal + SHIPPING_COST + tax - discount).quantize(Decimal("0.01"))

        Raises:
            PricingError: if `subtotal` is negative, `discount` is
                negative, or `discount` exceeds subtotal + shipping_cost +
                tax (which would make the total negative).
        """
        if subtotal < 0:
            raise PricingError(f"subtotal cannot be negative (got {subtotal!r}).")
        if discount < 0:
            raise PricingError(f"discount cannot be negative (got {discount!r}).")

        shipping_cost = cls.SHIPPING_COST
        tax = (subtotal * cls.TAX_RATE).quantize(TWO_PLACES)

        max_discount = subtotal + shipping_cost + tax
        if discount > max_discount:
            raise PricingError(
                f"discount ({discount!r}) cannot exceed subtotal + shipping_cost "
                f"+ tax ({max_discount!r}); it would make the total negative."
            )

        total = (subtotal + shipping_cost + tax - discount).quantize(TWO_PLACES)

        return {
            "subtotal": subtotal,
            "shipping_cost": shipping_cost,
            "tax": tax,
            "discount": discount,
            "total": total,
        }
