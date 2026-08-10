"""
Comprehensive unit tests for order.services.pricing.calculate_order_totals().

This is the single most financially sensitive piece of code in the
codebase — every dollar amount charged to any customer flows through it.
It is a pure function with no ORM/Django dependency, so these tests use
plain `unittest.TestCase` rather than Django's `TestCase` (or even
`SimpleTestCase`): no database is touched, no Django test-client
machinery is spun up, and the whole file runs in milliseconds. Per
backend/pytest.ini, `DJANGO_SETTINGS_MODULE` is still configured
project-wide (pytest-django needs a settings module to even start), but
that's unrelated to whether any individual test hits the database — none
of these do.

Rounding note (see RoundingBehaviorTests below): `Decimal.quantize()`
without an explicit rounding mode uses the *current decimal context's*
rounding, and Python's default decimal context rounding mode is
`ROUND_HALF_EVEN` ("banker's rounding") — not the "round half away from
zero" behavior a lot of people instinctively expect from money math. The
pricing service relies on this default implicitly (it never sets a
rounding mode explicitly). That's a deliberate, tested-and-locked-in
choice here, not an oversight — if the business ever wants "round half
up" behavior instead (e.g. to match a specific payment processor's
rounding rules), that would be a conscious, visible change to
`pricing.py`, and RoundingBehaviorTests.test_exact_half_cent_tax_rounds_half_even
would need to be updated alongside it.
"""

import unittest
from decimal import Decimal

from order.services.pricing import PricingError, calculate_order_totals

TWO_PLACES = Decimal("0.01")
DEFAULT_SHIPPING = Decimal("9.99")
DEFAULT_TAX_RATE = Decimal("0.10")


def _hand_calculate(subtotal, discount=Decimal("0")):
    """
    Independent reimplementation of the expected formula, used as an
    oracle in a couple of tests so the test suite isn't just restating
    the same arithmetic the implementation performs.
    """
    tax = (subtotal * DEFAULT_TAX_RATE).quantize(TWO_PLACES)
    total = (subtotal + DEFAULT_SHIPPING + tax - discount).quantize(TWO_PLACES)
    return tax, total


class StandardCaseTests(unittest.TestCase):
    """Case 1: known subtotal, zero discount — exact hand-calculated values."""

    def test_100_dollar_subtotal_zero_discount(self):
        result = calculate_order_totals(Decimal("100.00"))

        self.assertEqual(result["subtotal"], Decimal("100.00"))
        self.assertEqual(result["shipping_cost"], Decimal("9.99"))
        self.assertEqual(result["tax"], Decimal("10.00"))  # 100.00 * 0.10
        self.assertEqual(result["discount"], Decimal("0"))
        self.assertEqual(result["total"], Decimal("119.99"))  # 100 + 9.99 + 10.00

    def test_250_dollar_subtotal_zero_discount(self):
        result = calculate_order_totals(Decimal("250.00"))

        self.assertEqual(result["tax"], Decimal("25.00"))
        self.assertEqual(result["total"], Decimal("284.99"))  # 250 + 9.99 + 25.00

    def test_result_keys_are_exactly_the_five_expected_fields(self):
        result = calculate_order_totals(Decimal("10.00"))
        self.assertEqual(
            set(result.keys()),
            {"subtotal", "shipping_cost", "tax", "discount", "total"},
        )

    def test_all_result_values_are_decimal_instances(self):
        result = calculate_order_totals(Decimal("10.00"), discount=Decimal("1.00"))
        for key, value in result.items():
            self.assertIsInstance(value, Decimal, f"{key} was {type(value)!r}")


class DiscountAppliesCorrectlyTests(unittest.TestCase):
    """Case 2: discount reduces total, result still rounded to 2 places."""

    def test_discount_subtracted_from_total(self):
        result = calculate_order_totals(Decimal("100.00"), discount=Decimal("20.00"))
        # subtotal(100) + shipping(9.99) + tax(10.00) - discount(20.00)
        self.assertEqual(result["total"], Decimal("99.99"))
        self.assertEqual(result["discount"], Decimal("20.00"))

    def test_discount_does_not_affect_subtotal_tax_or_shipping(self):
        no_discount = calculate_order_totals(Decimal("100.00"))
        with_discount = calculate_order_totals(
            Decimal("100.00"), discount=Decimal("15.00")
        )
        self.assertEqual(no_discount["subtotal"], with_discount["subtotal"])
        self.assertEqual(no_discount["tax"], with_discount["tax"])
        self.assertEqual(no_discount["shipping_cost"], with_discount["shipping_cost"])

    def test_discounted_total_is_quantized_to_two_decimal_places(self):
        # subtotal 100 -> tax 10.00, total before discount = 119.99;
        # subtracting a discount with only whole cents keeps 2dp, but this
        # asserts the *shape* (exponent) of the returned Decimal explicitly,
        # not just its numeric value, since a stray Decimal("99.9900") would
        # still compare equal to Decimal("99.99") with assertEqual.
        result = calculate_order_totals(Decimal("100.00"), discount=Decimal("20.00"))
        self.assertEqual(result["total"].as_tuple().exponent, -2)


class ZeroSubtotalTests(unittest.TestCase):
    """
    Case 3: zero subtotal is an edge case worth deciding on explicitly.

    Chosen/locked-in behavior: a $0.00 subtotal is ALLOWED (e.g. a
    100%-off order, or a free digital item) and simply produces zero tax
    plus the flat shipping cost as the total — it does not raise. Only
    *negative* subtotal is rejected (see NegativeInputValidationTests).
    """

    def test_zero_subtotal_computes_cleanly_not_raises(self):
        result = calculate_order_totals(Decimal("0.00"))
        self.assertEqual(result["tax"], Decimal("0.00"))
        self.assertEqual(result["shipping_cost"], Decimal("9.99"))
        self.assertEqual(result["total"], Decimal("9.99"))  # just shipping

    def test_zero_subtotal_with_zero_discount(self):
        result = calculate_order_totals(Decimal("0.00"), discount=Decimal("0.00"))
        self.assertEqual(result["total"], Decimal("9.99"))

    def test_zero_subtotal_with_discount_covering_shipping(self):
        # subtotal 0 + shipping 9.99 + tax 0.00 = 9.99 max discount
        result = calculate_order_totals(Decimal("0.00"), discount=Decimal("9.99"))
        self.assertEqual(result["total"], Decimal("0.00"))


class NegativeInputValidationTests(unittest.TestCase):
    """Cases 4 & 5: negative subtotal / negative discount both raise."""

    def test_negative_subtotal_raises_pricing_error(self):
        with self.assertRaises(PricingError):
            calculate_order_totals(Decimal("-0.01"))

    def test_negative_subtotal_error_message_mentions_subtotal(self):
        with self.assertRaises(PricingError) as ctx:
            calculate_order_totals(Decimal("-50.00"))
        self.assertIn("subtotal", str(ctx.exception).lower())

    def test_negative_discount_raises_pricing_error(self):
        with self.assertRaises(PricingError):
            calculate_order_totals(Decimal("100.00"), discount=Decimal("-1.00"))

    def test_negative_discount_error_message_mentions_discount(self):
        with self.assertRaises(PricingError) as ctx:
            calculate_order_totals(Decimal("100.00"), discount=Decimal("-0.01"))
        self.assertIn("discount", str(ctx.exception).lower())

    def test_pricing_error_is_a_value_error_subclass(self):
        # So existing/future callers doing a broad `except ValueError`
        # continue to work without knowing about PricingError specifically.
        self.assertTrue(issubclass(PricingError, ValueError))


class DiscountBoundaryTests(unittest.TestCase):
    """Cases 6 & 7: discount exactly at, and just over, the allowed max."""

    def _max_discount_for(self, subtotal):
        tax = (subtotal * DEFAULT_TAX_RATE).quantize(TWO_PLACES)
        return subtotal + DEFAULT_SHIPPING + tax

    def test_discount_equal_to_subtotal_plus_shipping_plus_tax_gives_zero_total(self):
        subtotal = Decimal("50.00")
        max_discount = self._max_discount_for(subtotal)  # 50 + 9.99 + 5.00 = 64.99

        result = calculate_order_totals(subtotal, discount=max_discount)

        self.assertEqual(result["total"], Decimal("0.00"))
        # Explicitly not negative, and not merely "close to zero".
        self.assertGreaterEqual(result["total"], Decimal("0.00"))

    def test_discount_one_cent_over_max_raises(self):
        subtotal = Decimal("50.00")
        max_discount = self._max_discount_for(subtotal)

        with self.assertRaises(PricingError):
            calculate_order_totals(subtotal, discount=max_discount + Decimal("0.01"))

    def test_discount_far_over_max_raises(self):
        subtotal = Decimal("50.00")
        with self.assertRaises(PricingError):
            calculate_order_totals(subtotal, discount=Decimal("999.00"))

    def test_over_max_discount_error_never_produces_a_negative_total(self):
        # Belt-and-suspenders: confirm the exception path is taken instead
        # of ever returning a dict with a negative "total".
        subtotal = Decimal("50.00")
        max_discount = self._max_discount_for(subtotal)
        try:
            calculate_order_totals(subtotal, discount=max_discount + Decimal("50.00"))
            self.fail("Expected PricingError to be raised")
        except PricingError:
            pass  # expected — no dict was ever constructed/returned


class RoundingBehaviorTests(unittest.TestCase):
    """
    Case 8: explicit verification of `.quantize(Decimal("0.01"))` rounding,
    including a genuine half-cent tie to pin down which rounding mode is
    in effect.
    """

    def test_non_round_subtotal_tax_truncates_down_correctly(self):
        # 33.33 * 0.10 = 3.333 -> the third decimal digit (3) is below 5,
        # so every rounding mode agrees this rounds down to 3.33. This is
        # a sanity check before the genuine tie-breaking case below.
        result = calculate_order_totals(Decimal("33.33"))
        self.assertEqual(result["tax"], Decimal("3.33"))

    def test_exact_half_cent_tax_rounds_half_even(self):
        # 12.25 * 0.10 = 1.225 exactly (no floating-point error, since
        # Decimal arithmetic on exact decimal literals is exact). The
        # third decimal digit is exactly 5 — a genuine rounding tie
        # between 1.22 and 1.23.
        #
        # Python's Decimal.quantize(), with no rounding mode passed
        # explicitly, uses the ambient decimal context's rounding mode,
        # which defaults to ROUND_HALF_EVEN ("banker's rounding"): ties
        # round to whichever neighbor has an even final digit. 1.22 ends
        # in an even digit (2), so ROUND_HALF_EVEN produces 1.22 here —
        # NOT 1.23, which is what "round half up" (the more commonly
        # assumed default for money) would produce.
        #
        # This test locks in the service's actual, current behavior. It
        # is not asserting this is the "correct" business behavior in
        # some absolute sense — only that it's the behavior actually
        # implemented, so a future change to the rounding mode is a
        # deliberate, visible diff here rather than a silent regression.
        subtotal = Decimal("12.25")
        expected_tax = subtotal * DEFAULT_TAX_RATE
        self.assertEqual(expected_tax, Decimal("1.225"))  # confirm exact tie

        result = calculate_order_totals(subtotal)
        self.assertEqual(result["tax"], Decimal("1.22"))  # banker's rounding

    def test_another_half_cent_tie_rounds_to_even_neighbor(self):
        # 15.25 * 0.10 = 1.525 -> ties between 1.52 (even) and 1.53 (odd).
        # ROUND_HALF_EVEN picks 1.52.
        subtotal = Decimal("15.25")
        expected_tax = subtotal * DEFAULT_TAX_RATE
        self.assertEqual(expected_tax, Decimal("1.525"))

        result = calculate_order_totals(subtotal)
        self.assertEqual(result["tax"], Decimal("1.52"))

    def test_half_cent_tie_that_rounds_up_to_even_neighbor(self):
        # 32.75 * 0.10 = 3.275 -> ties between 3.27 (odd) and 3.28 (even).
        # ROUND_HALF_EVEN picks 3.28 — included so the pattern isn't
        # mistaken for "ties always round down"; it depends on which
        # neighbor happens to be even.
        subtotal = Decimal("32.75")
        expected_tax = subtotal * DEFAULT_TAX_RATE
        self.assertEqual(expected_tax, Decimal("3.275"))

        result = calculate_order_totals(subtotal)
        self.assertEqual(result["tax"], Decimal("3.28"))

    def test_total_is_quantized_even_when_inputs_combine_to_extra_places(self):
        result = calculate_order_totals(
            Decimal("12.25"), discount=Decimal("0.005").quantize(Decimal("0.01"))
        )
        # discount got quantized to 0.01 by the caller before being passed
        # in (as OrderCreateSerializer's DecimalField would do); confirm
        # the service's own output is still cleanly 2dp regardless.
        self.assertEqual(result["total"].as_tuple().exponent, -2)


class OracleComparisonTests(unittest.TestCase):
    """
    Cross-check calculate_order_totals against an independently written
    reimplementation of the formula, across a range of inputs, so the
    test suite isn't purely restating the implementation's own math.
    """

    def test_matches_independent_reimplementation_across_several_inputs(self):
        cases = [
            (Decimal("19.99"), Decimal("0")),
            (Decimal("100.00"), Decimal("10.00")),
            (Decimal("0.01"), Decimal("0")),
            (Decimal("9999.99"), Decimal("500.00")),
            (Decimal("12.25"), Decimal("0")),
        ]
        for subtotal, discount in cases:
            with self.subTest(subtotal=subtotal, discount=discount):
                expected_tax, expected_total = _hand_calculate(subtotal, discount)
                result = calculate_order_totals(subtotal, discount=discount)
                self.assertEqual(result["tax"], expected_tax)
                self.assertEqual(result["total"], expected_total)


if __name__ == "__main__":
    unittest.main()
