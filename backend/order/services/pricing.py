"""
Order pricing logic.

Extracted out of OrderCreateSerializer.create() so that total calculation
is a standalone, independently testable unit rather than logic buried
inside a serializer. This is expected to grow (coupon-based discounts,
real shipping-rate lookups, region-specific tax rules) — keeping it here
means future changes don't have to touch the serializer at all.

Wired into OrderCreateSerializer.create() (Epic 1), with shipping_cost as
an explicit caller-supplied argument as of Task 7.1.1.4 — see that
serializer's create() for how the destination/weight-based ShippingRate
lookup resolves the value passed in here.

MONEY (Task 14.1.2.2, ADR 0001): every amount here is a plain ``int`` of
Rial and a multiple of 10 (whole Toman). The only fractional calculation is
the tax percentage, which is rounded exactly once through
``core.money.percent_of`` (nearest whole Toman, ties up). Nothing is ever
rounded again afterwards, so ``total`` is always exact integer arithmetic.
"""

from decimal import Decimal
from typing import Dict

from core.money import RIAL_PER_TOMAN, percent_of


class PricingError(ValueError):
    """Raised when pricing inputs are invalid (negative amounts, a discount
    that would make the total negative, non-integer or non-whole-Toman
    amounts, etc.)."""


def _check_amount(name: str, value) -> None:
    # bool is an int subclass; True/False are never a valid money amount.
    if isinstance(value, bool) or not isinstance(value, int):
        raise PricingError(
            f"{name} must be an int number of Rial (got {value!r}, "
            f"{type(value).__name__})."
        )
    if value < 0:
        raise PricingError(f"{name} cannot be negative (got {value!r}).")
    if value % RIAL_PER_TOMAN:
        raise PricingError(
            f"{name} must be a whole number of Toman, i.e. a multiple of "
            f"{RIAL_PER_TOMAN} Rial (got {value!r})."
        )


class PricingService:
    """
    Owns order total calculation: tax rate, shipping cost, and the
    subtotal/tax/discount/total formula.

    Kept as a class (rather than bare module-level functions) so that
    future variations — e.g. a region-specific subclass overriding
    TAX_PERCENT for Iranian tax rules, or overriding `calculate_order_totals`
    entirely for coupon-based discounts — have an obvious place to live
    without changing every call site.
    """

    # A PERCENT (not a 0.10 multiplier): ``percent_of`` takes percentages, and
    # percentages never touch the money type (ADR 0001, I-6).
    TAX_PERCENT: Decimal = Decimal("10")  # 10%

    @classmethod
    def calculate_order_totals(
        cls,
        subtotal: int,
        shipping_cost: int,
        discount: int = 0,
    ) -> Dict[str, int]:
        """
        Compute the full set of order totals for a given cart subtotal.

        `shipping_cost` (Task 7.1.1.4) is an explicit, caller-supplied input
        rather than an internal flat constant — real shipping cost varies by
        carrier, destination, and weight, resolved by the ShippingRate lookup
        (shipping.models.ShippingRate.find_rate) before this function is ever
        called. This function has no opinion on HOW shipping_cost was
        derived; it just needs a non-negative whole-Toman int.

        Returns a dict with keys "subtotal", "shipping_cost", "tax",
        "discount", "total" — all ``int`` Rial, all multiples of 10:

            tax   = percent_of(subtotal, TAX_PERCENT)      # the ONLY rounding
            total = subtotal + shipping_cost + tax - discount

        Raises:
            PricingError: if any input is not an int, is negative, is not a
                whole number of Toman, or if `discount` exceeds
                subtotal + shipping_cost + tax (which would make the total
                negative).
        """
        _check_amount("subtotal", subtotal)
        _check_amount("shipping_cost", shipping_cost)
        _check_amount("discount", discount)

        tax = percent_of(subtotal, cls.TAX_PERCENT)

        max_discount = subtotal + shipping_cost + tax
        if discount > max_discount:
            raise PricingError(
                f"discount ({discount!r}) cannot exceed subtotal + shipping_cost "
                f"+ tax ({max_discount!r}); it would make the total negative."
            )

        total = subtotal + shipping_cost + tax - discount

        return {
            "subtotal": subtotal,
            "shipping_cost": shipping_cost,
            "tax": tax,
            "discount": discount,
            "total": total,
        }


def calculate_order_totals(
    subtotal: int,
    shipping_cost: int,
    discount: int = 0,
) -> Dict[str, int]:
    """
    Module-level convenience wrapper around
    `PricingService.calculate_order_totals`, so callers can do
    `from order.services.pricing import calculate_order_totals` without
    referencing the class directly. See PricingService.calculate_order_totals
    for the full behavior/contract.
    """
    return PricingService.calculate_order_totals(subtotal, shipping_cost, discount)
