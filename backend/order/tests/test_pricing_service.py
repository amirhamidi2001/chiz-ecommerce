"""
Tests for order/services/pricing.py (Task 1.2.1.1; money semantics rewritten in
Task 14.1.2.2 per ADR 0001, docs/adr/0001-currency-storage.md).

Money is a plain ``int`` of Rial and every amount is a whole number of Toman (a
multiple of 10). The one fractional calculation — the tax percentage — rounds
exactly once, to the nearest whole Toman, ties UP. Everything else is exact
integer arithmetic, so ``total`` never needs rounding at display time.

No database or Django state needed: plain unittest, as before.
"""

import random
import unittest
from decimal import Decimal

from order.services.pricing import PricingError, PricingService, calculate_order_totals

DEFAULT_SHIPPING = 99_900  # an arbitrary caller-supplied shipping cost (Rial)


def _oracle(subtotal, shipping_cost=DEFAULT_SHIPPING, discount=0):
    """
    Independent re-implementation using integer arithmetic ONLY (no Decimal, no
    shared code): tax is 10% of subtotal = subtotal/10 Rial = subtotal/100 Toman,
    rounded half-up with integer floor division, then back to Rial.
    """
    tax = ((subtotal + 50) // 100) * 10
    return {
        "subtotal": subtotal,
        "shipping_cost": shipping_cost,
        "tax": tax,
        "discount": discount,
        "total": subtotal + shipping_cost + tax - discount,
    }


class StandardCaseTests(unittest.TestCase):
    def test_1m_rial_subtotal_zero_discount(self):
        result = calculate_order_totals(
            subtotal=1_000_000, shipping_cost=DEFAULT_SHIPPING
        )
        self.assertEqual(result["subtotal"], 1_000_000)
        self.assertEqual(result["shipping_cost"], 99_900)
        self.assertEqual(result["tax"], 100_000)  # 10%
        self.assertEqual(result["discount"], 0)
        self.assertEqual(result["total"], 1_199_900)

    def test_2_5m_rial_subtotal_zero_discount(self):
        result = calculate_order_totals(
            subtotal=2_500_000, shipping_cost=DEFAULT_SHIPPING
        )
        self.assertEqual(result["tax"], 250_000)
        self.assertEqual(result["total"], 2_849_900)

    def test_result_keys_are_exactly_the_five_expected_fields(self):
        result = calculate_order_totals(100_000, DEFAULT_SHIPPING)
        self.assertEqual(
            set(result), {"subtotal", "shipping_cost", "tax", "discount", "total"}
        )

    def test_all_result_values_are_plain_ints_and_whole_toman(self):
        result = calculate_order_totals(1_234_560, DEFAULT_SHIPPING, 50_000)
        for key, value in result.items():
            with self.subTest(key=key):
                self.assertIs(type(value), int)  # not Decimal, not float, not bool
                self.assertEqual(value % 10, 0)

    def test_module_level_wrapper_matches_the_class_method(self):
        self.assertEqual(
            calculate_order_totals(777_770, 55_000, 10_000),
            PricingService.calculate_order_totals(777_770, 55_000, 10_000),
        )


class ShippingCostIsJustAnInputTests(unittest.TestCase):
    """shipping_cost is a plain caller-supplied argument (Task 7.1.1.4)."""

    def test_arbitrary_shipping_cost_flows_through_to_result(self):
        result = calculate_order_totals(1_000_000, 345_000)
        self.assertEqual(result["shipping_cost"], 345_000)
        self.assertEqual(result["total"], 1_000_000 + 345_000 + 100_000)

    def test_zero_shipping_cost_is_allowed(self):
        result = calculate_order_totals(1_000_000, 0)
        self.assertEqual(result["shipping_cost"], 0)
        self.assertEqual(result["total"], 1_100_000)

    def test_shipping_cost_is_a_required_argument(self):
        with self.assertRaises(TypeError):
            calculate_order_totals(1_000_000)  # type: ignore[call-arg]


class DiscountAppliesCorrectlyTests(unittest.TestCase):
    def test_discount_subtracted_from_total(self):
        result = calculate_order_totals(1_000_000, DEFAULT_SHIPPING, 200_000)
        self.assertEqual(result["discount"], 200_000)
        self.assertEqual(result["total"], 1_199_900 - 200_000)

    def test_discount_does_not_affect_subtotal_tax_or_shipping(self):
        base = calculate_order_totals(1_000_000, DEFAULT_SHIPPING)
        discounted = calculate_order_totals(1_000_000, DEFAULT_SHIPPING, 300_000)
        for key in ("subtotal", "shipping_cost", "tax"):
            self.assertEqual(base[key], discounted[key], key)

    def test_discounted_total_is_a_whole_toman_with_nothing_left_to_round(self):
        result = calculate_order_totals(1_234_560, DEFAULT_SHIPPING, 185_180)
        self.assertEqual(result["total"], 1_234_560 + 99_900 + 123_460 - 185_180)
        self.assertEqual(result["total"] % 10, 0)


class ZeroSubtotalTests(unittest.TestCase):
    """A zero subtotal is ALLOWED (e.g. a fully-discounted cart's own lines)."""

    def test_zero_subtotal_computes_cleanly_not_raises(self):
        result = calculate_order_totals(0, DEFAULT_SHIPPING)
        self.assertEqual(result["tax"], 0)
        self.assertEqual(result["total"], DEFAULT_SHIPPING)

    def test_zero_subtotal_with_zero_discount(self):
        self.assertEqual(calculate_order_totals(0, 0, 0)["total"], 0)

    def test_zero_subtotal_with_discount_covering_shipping(self):
        self.assertEqual(calculate_order_totals(0, 100_000, 100_000)["total"], 0)


class NegativeInputValidationTests(unittest.TestCase):
    def test_negative_subtotal_raises_pricing_error(self):
        with self.assertRaises(PricingError) as ctx:
            calculate_order_totals(-10, DEFAULT_SHIPPING)
        self.assertIn("subtotal", str(ctx.exception))

    def test_negative_discount_raises_pricing_error(self):
        with self.assertRaises(PricingError) as ctx:
            calculate_order_totals(1_000_000, DEFAULT_SHIPPING, -10)
        self.assertIn("discount", str(ctx.exception))

    def test_negative_shipping_cost_raises_pricing_error(self):
        with self.assertRaises(PricingError) as ctx:
            calculate_order_totals(1_000_000, -10)
        self.assertIn("shipping_cost", str(ctx.exception))

    def test_pricing_error_is_a_value_error_subclass(self):
        self.assertTrue(issubclass(PricingError, ValueError))


class MoneyTypeAndGranularityValidationTests(unittest.TestCase):
    """ADR 0001 I-1 / I-2: ints only, and only whole Toman."""

    def test_non_int_amounts_are_rejected_not_coerced(self):
        for bad in (Decimal("1000000"), 1_000_000.0, "1000000", True, None):
            for position in range(3):
                args = [1_000_000, DEFAULT_SHIPPING, 0]
                args[position] = bad
                with self.subTest(bad=bad, position=position):
                    with self.assertRaises(PricingError):
                        calculate_order_totals(*args)

    def test_amounts_that_are_not_a_whole_toman_are_rejected(self):
        for position, bad in ((0, 1_234_565), (1, 99_905), (2, 5)):
            args = [1_000_000, DEFAULT_SHIPPING, 0]
            args[position] = bad
            with self.subTest(position=position, bad=bad):
                with self.assertRaises(PricingError) as ctx:
                    calculate_order_totals(*args)
                self.assertIn("whole number of Toman", str(ctx.exception))


class DiscountBoundaryTests(unittest.TestCase):
    def _max_discount(self, subtotal, shipping=DEFAULT_SHIPPING):
        return subtotal + shipping + _oracle(subtotal, shipping)["tax"]

    def test_discount_equal_to_subtotal_plus_shipping_plus_tax_gives_zero_total(self):
        subtotal = 500_000
        result = calculate_order_totals(
            subtotal, DEFAULT_SHIPPING, self._max_discount(subtotal)
        )
        self.assertEqual(result["total"], 0)

    def test_discount_one_toman_over_max_raises(self):
        subtotal = 500_000
        with self.assertRaises(PricingError):
            calculate_order_totals(
                subtotal, DEFAULT_SHIPPING, self._max_discount(subtotal) + 10
            )

    def test_discount_far_over_max_raises(self):
        with self.assertRaises(PricingError):
            calculate_order_totals(500_000, DEFAULT_SHIPPING, 500_000_000)

    def test_over_max_discount_never_produces_a_negative_total(self):
        for over in (10, 100, 10_000, 1_000_000):
            with self.subTest(over=over):
                with self.assertRaises(PricingError):
                    calculate_order_totals(
                        500_000, DEFAULT_SHIPPING, self._max_discount(500_000) + over
                    )


class RoundingBehaviorTests(unittest.TestCase):
    """
    The tax is the ONLY fractional step. It rounds to the nearest whole Toman
    (multiple of 10 Rial), ties UP — Decimal.quantize's old default was
    ROUND_HALF_EVEN, which would pick 123,450 for the tie below.
    """

    def test_tax_above_half_a_toman_rounds_up(self):
        # 10% of 1,234,560 = 123,456 Rial = 12,345.6 Toman -> 12,346 Toman
        self.assertEqual(calculate_order_totals(1_234_560, 0)["tax"], 123_460)

    def test_tax_below_half_a_toman_rounds_down(self):
        # 123,454 Rial = 12,345.4 Toman -> 12,345 Toman
        self.assertEqual(calculate_order_totals(1_234_540, 0)["tax"], 123_450)

    def test_exact_half_toman_tie_rounds_up_not_to_even(self):
        # 123,455 Rial = 12,345.5 Toman. HALF_UP -> 12,346; HALF_EVEN -> 12,346
        # here (even), so also pin the case where they DISAGREE:
        self.assertEqual(calculate_order_totals(1_234_550, 0)["tax"], 123_460)
        # 123,445 Rial = 12,344.5 Toman: HALF_UP -> 12,345, HALF_EVEN -> 12,344.
        self.assertEqual(calculate_order_totals(1_234_450, 0)["tax"], 123_450)

    def test_total_never_needs_further_rounding(self):
        rng = random.Random(1402)
        for _ in range(5_000):
            subtotal = rng.randint(0, 10**9) * 10
            result = calculate_order_totals(subtotal, DEFAULT_SHIPPING)
            self.assertEqual(result["total"] % 10, 0)
            self.assertEqual(
                result["total"],
                result["subtotal"] + result["shipping_cost"] + result["tax"],
            )


class CustomTaxPercentTests(unittest.TestCase):
    def test_a_subclass_can_override_the_tax_percent(self):
        class NinePercent(PricingService):
            TAX_PERCENT = Decimal("9")

        # 9% of 1,234,560 = 111,110.4 Rial = 11,111.04 Toman -> 11,111 -> 111,110
        result = NinePercent.calculate_order_totals(1_234_560, 0)
        self.assertEqual(result["tax"], 111_110)
        self.assertEqual(result["total"], 1_234_560 + 111_110)

    def test_default_tax_percent_is_ten(self):
        self.assertEqual(PricingService.TAX_PERCENT, Decimal("10"))


class OracleComparisonTests(unittest.TestCase):
    def test_matches_independent_integer_reimplementation_across_inputs(self):
        for subtotal in (0, 10, 40, 50, 100, 990, 1_000_000, 1_234_550, 99_999_990):
            with self.subTest(subtotal=subtotal):
                self.assertEqual(
                    calculate_order_totals(subtotal, DEFAULT_SHIPPING),
                    _oracle(subtotal, DEFAULT_SHIPPING),
                )

    def test_matches_oracle_with_varied_shipping_and_discount(self):
        rng = random.Random(2026)
        for _ in range(3_000):
            subtotal = rng.randint(0, 10**9) * 10
            shipping = rng.randint(0, 10**7) * 10
            discount = rng.randint(0, (subtotal + shipping) // 10) * 10
            self.assertEqual(
                calculate_order_totals(subtotal, shipping, discount),
                _oracle(subtotal, shipping, discount),
            )


if __name__ == "__main__":
    unittest.main()
