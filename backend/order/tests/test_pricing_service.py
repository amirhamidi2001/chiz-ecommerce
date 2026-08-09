"""
Tests for order.services.pricing.PricingService.

This is a standalone unit for order total calculation, extracted out of
OrderCreateSerializer.create() (not yet wired back in — that's a separate
task). The smoke test below exists specifically to prove the extraction
introduced zero behavior change versus the formula it replaced:

    subtotal = Decimal(str(cart.subtotal))
    tax = (subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
    total = (subtotal + Decimal("9.99") + tax - discount).quantize(Decimal("0.01"))

Full, exhaustive test coverage of this service is Task 1.1.2.3; this file
covers the smoke test plus the validation behavior called out explicitly
in this task's requirements.
"""

from decimal import Decimal

from django.test import SimpleTestCase
from order.services.pricing import PricingError, PricingService


class PricingServiceSmokeTest(SimpleTestCase):
    """Proves the extraction is byte-for-byte identical to the old inline math."""

    def test_matches_old_inline_formula_for_100_dollar_subtotal(self):
        subtotal = Decimal("100.00")

        # The exact formula OrderCreateSerializer.create() used before
        # extraction, for comparison.
        expected_tax = (subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
        expected_total = (
            subtotal + Decimal("9.99") + expected_tax - Decimal("0")
        ).quantize(Decimal("0.01"))

        result = PricingService.calculate_order_totals(subtotal)

        self.assertEqual(result["subtotal"], subtotal)
        self.assertEqual(result["shipping_cost"], Decimal("9.99"))
        self.assertEqual(result["tax"], expected_tax)
        self.assertEqual(result["tax"], Decimal("10.00"))
        self.assertEqual(result["discount"], Decimal("0"))
        self.assertEqual(result["total"], expected_total)
        self.assertEqual(result["total"], Decimal("119.99"))


class PricingServiceCalculationTests(SimpleTestCase):
    def test_zero_subtotal(self):
        result = PricingService.calculate_order_totals(Decimal("0.00"))
        self.assertEqual(result["tax"], Decimal("0.00"))
        self.assertEqual(result["total"], Decimal("9.99"))  # just shipping

    def test_discount_reduces_total(self):
        result = PricingService.calculate_order_totals(
            Decimal("100.00"), discount=Decimal("20.00")
        )
        self.assertEqual(result["total"], Decimal("99.99"))  # 119.99 - 20.00

    def test_discount_equal_to_max_allowed_is_valid(self):
        subtotal = Decimal("50.00")
        tax = (subtotal * PricingService.TAX_RATE).quantize(Decimal("0.01"))
        max_discount = subtotal + PricingService.SHIPPING_COST + tax

        result = PricingService.calculate_order_totals(
            subtotal, discount=max_discount
        )
        self.assertEqual(result["total"], Decimal("0.00"))

    def test_tax_rounds_to_two_decimal_places(self):
        # 33.33 * 0.10 = 3.333 -> quantized to 3.33
        result = PricingService.calculate_order_totals(Decimal("33.33"))
        self.assertEqual(result["tax"], Decimal("3.33"))


class PricingServiceValidationTests(SimpleTestCase):
    def test_negative_subtotal_raises(self):
        with self.assertRaises(PricingError):
            PricingService.calculate_order_totals(Decimal("-0.01"))

    def test_negative_discount_raises(self):
        with self.assertRaises(PricingError):
            PricingService.calculate_order_totals(
                Decimal("100.00"), discount=Decimal("-1.00")
            )

    def test_discount_exceeding_subtotal_plus_shipping_plus_tax_raises(self):
        subtotal = Decimal("50.00")
        tax = (subtotal * PricingService.TAX_RATE).quantize(Decimal("0.01"))
        max_discount = subtotal + PricingService.SHIPPING_COST + tax

        with self.assertRaises(PricingError):
            PricingService.calculate_order_totals(
                subtotal, discount=max_discount + Decimal("0.01")
            )

    def test_pricing_error_is_a_value_error(self):
        # So callers doing broad `except ValueError` continue to work.
        self.assertTrue(issubclass(PricingError, ValueError))
