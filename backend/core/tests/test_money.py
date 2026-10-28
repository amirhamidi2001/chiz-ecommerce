"""
core/tests/test_money.py
────────────────────────
ADR 0001 (docs/adr/0001-currency-storage.md): money primitives, the pricing
service's integer invariants, and the self-verifying field registry.

DB-free. The golden vectors are IDENTICAL to
frontend/src/utils/tests/money.test.js — change both together.
"""

import random
from decimal import Decimal

import pytest
from core.fields import RialField
from core.money import (
    MAX_RIAL_AMOUNT,
    format_rial,
    percent_of,
    rial_to_toman,
    to_whole_toman_rial,
    toman_to_rial,
    validate_max_rial,
    validate_whole_toman,
)
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.template import Context, Template
from django.test import SimpleTestCase
from order.services.pricing import PricingError, PricingService, calculate_order_totals

GOLDEN_ROUNDING = [
    (0, 0),
    (4, 0),
    (5, 10),
    (14, 10),
    (15, 20),
    (125, 130),
    (123_456, 123_460),
    (185_184, 185_180),
]


class GoldenVectorTests(SimpleTestCase):
    def test_to_whole_toman_rial_golden_vectors(self):
        for value, expected in GOLDEN_ROUNDING:
            with self.subTest(value=value):
                self.assertEqual(to_whole_toman_rial(value), expected)

    def test_adr_worked_checkout(self):
        subtotal, shipping = 1_234_560, 500_000
        tax = percent_of(subtotal, Decimal("10"))
        self.assertEqual(tax, 123_460)
        self.assertEqual(subtotal + shipping + tax, 1_858_020)
        self.assertEqual(rial_to_toman(1_858_020), 185_802)
        self.assertEqual(percent_of(subtotal, Decimal("15")), 185_180)

    def test_ties_round_up_not_to_even(self):
        # ROUND_HALF_EVEN would give 120 for 125 -> 12.5 Toman; ROUND_HALF_UP gives 130.
        self.assertEqual(to_whole_toman_rial(125), 130)
        self.assertEqual(to_whole_toman_rial(135), 140)

    def test_decimal_input_is_rounded_exactly_once(self):
        self.assertEqual(to_whole_toman_rial(Decimal("123456.0")), 123_460)
        self.assertEqual(percent_of(1_000_000, Decimal("12.50")), 125_000)

    def test_result_is_always_a_python_int(self):
        self.assertIs(type(to_whole_toman_rial(Decimal("5"))), int)
        self.assertIs(type(percent_of(10, Decimal("50"))), int)


class RoundingPropertyTests(SimpleTestCase):
    """No fractional/precision bug can exist in the integer arithmetic."""

    def test_percent_results_are_whole_toman_and_never_exceed_the_base(self):
        rng = random.Random(14122)
        for _ in range(20_000):
            amount = rng.randint(0, MAX_RIAL_AMOUNT // 10) * 10
            percent = Decimal(rng.randint(1, 10_000)) / 100  # 0.01 .. 100.00
            result = percent_of(amount, percent)
            self.assertIs(type(result), int)
            self.assertEqual(result % 10, 0, (amount, percent))
            self.assertLessEqual(result, amount, (amount, percent))
            # within half a Toman (5 Rial) of the exact value
            exact = Decimal(amount) * percent / 100
            self.assertLessEqual(abs(Decimal(result) - exact), 5, (amount, percent))

    def test_conversion_round_trip(self):
        rng = random.Random(7)
        for _ in range(2_000):
            toman = rng.randint(0, MAX_RIAL_AMOUNT // 10)
            self.assertEqual(rial_to_toman(toman_to_rial(toman)), toman)

    def test_rial_to_toman_refuses_a_non_multiple_of_ten(self):
        with self.assertRaises(ValueError):
            rial_to_toman(123_456)


class ValidatorTests(SimpleTestCase):
    def test_whole_toman_validator(self):
        validate_whole_toman(0)
        validate_whole_toman(1_250_000)
        validate_whole_toman(None)  # nullable columns
        with self.assertRaises(ValidationError) as ctx:
            validate_whole_toman(1_250_005)
        self.assertEqual(ctx.exception.code, "not_whole_toman")

    def test_max_amount_validator(self):
        validate_max_rial(MAX_RIAL_AMOUNT)
        with self.assertRaises(ValidationError) as ctx:
            validate_max_rial(MAX_RIAL_AMOUNT + 10)
        self.assertEqual(ctx.exception.code, "amount_too_large")

    def test_max_amount_keeps_basis_point_math_inside_js_safe_integers(self):
        self.assertLess(MAX_RIAL_AMOUNT * 10_000, 2**53 - 1)

    def test_rial_field_carries_both_validators(self):
        field = RialField()
        self.assertIn(validate_whole_toman, field.validators)
        self.assertIn(validate_max_rial, field.validators)
        self.assertIsInstance(field, models.PositiveBigIntegerField)


class TemplateFilterTests(SimpleTestCase):
    def render(self, source, **ctx):
        return Template("{% load money %}" + source).render(Context(ctx))

    def test_rial_and_toman_filters(self):
        self.assertEqual(self.render("{{ v|rial }}", v=1_858_020), "1,858,020")
        self.assertEqual(self.render("{{ v|toman }}", v=1_858_020), "185,802")
        self.assertEqual(self.render("{{ v|toman }}", v=0), "0")

    def test_toman_filter_refuses_invariant_violation(self):
        with self.assertRaises(ValueError):
            self.render("{{ v|toman }}", v=123_456)

    def test_format_rial_helper(self):
        self.assertEqual(format_rial(1_858_020), "1,858,020 Rial")


class PricingServiceTests(SimpleTestCase):
    def test_returns_pure_ints_that_add_up_exactly(self):
        totals = calculate_order_totals(subtotal=1_234_560, shipping_cost=500_000)
        self.assertEqual(
            totals,
            {
                "subtotal": 1_234_560,
                "shipping_cost": 500_000,
                "tax": 123_460,
                "discount": 0,
                "total": 1_858_020,
            },
        )
        for key, value in totals.items():
            self.assertIs(type(value), int, key)
            self.assertEqual(value % 10, 0, key)

    def test_total_identity_holds_for_random_carts(self):
        rng = random.Random(99)
        for _ in range(5_000):
            subtotal = rng.randint(0, 10**9) * 10
            shipping = rng.randint(0, 10**6) * 10
            tax = percent_of(subtotal, PricingService.TAX_PERCENT)
            discount = rng.randint(0, (subtotal + shipping + tax) // 10) * 10
            t = calculate_order_totals(subtotal, shipping, discount)
            self.assertEqual(
                t["total"],
                t["subtotal"] + t["shipping_cost"] + t["tax"] - t["discount"],
            )
            self.assertEqual(t["total"] % 10, 0)
            self.assertGreaterEqual(t["total"], 0)

    def test_a_percentage_discount_gives_a_whole_rounded_total(self):
        # 15% coupon on 1,234,560: exact 185,184 -> 185,180 (rounded once, here).
        discount = percent_of(1_234_560, Decimal("15"))
        t = calculate_order_totals(1_234_560, 500_000, discount)
        self.assertEqual(discount, 185_180)
        self.assertEqual(t["total"], 1_858_020 - 185_180)
        self.assertEqual(t["total"] % 10, 0)

    def test_rejects_decimals_floats_and_bools(self):
        for bad in (Decimal("100000"), 100000.0, "100000", True, None):
            with self.subTest(bad=bad), self.assertRaises(PricingError):
                calculate_order_totals(bad, 0)

    def test_rejects_non_whole_toman_and_negative_amounts(self):
        with self.assertRaises(PricingError):
            calculate_order_totals(1_234_565, 0)
        with self.assertRaises(PricingError):
            calculate_order_totals(100_000, -10)
        with self.assertRaises(PricingError):
            calculate_order_totals(100_000, 0, 10**9)  # discount > everything


# ── The self-verifying enumeration from ADR 0001 §7.1 / §7.4 ──────────────────

EXPECTED_RIAL_FIELDS = {
    "shop.Product.price",
    "shop.Product.original_price",
    "shop.ProductVariant.price",
    "shop.ProductVariant.original_price",
    "shop.ProductPriceSnapshot.price",
    "order.Order.subtotal",
    "order.Order.shipping_cost",
    "order.Order.tax",
    "order.Order.discount",
    "order.Order.total",
    "order.OrderItem.unit_price",
    "payments.PaymentTransaction.amount",
    "payments.RefundRequest.amount",
    "shipping.ShippingRate.price",
    "promotions.Coupon.min_order_amount",
    "promotions.Coupon.fixed_amount",
    "promotions.CouponRedemption.discount_amount",
}
EXPECTED_DECIMAL_FIELDS = {  # percentages / ratings — NOT currency (ADR §7.2)
    "shop.Product.rating",
    "promotions.FlashSale.discount_percent",
    "promotions.Coupon.percent_off",
}
MONEY_FIELD_NAMES = {
    "price",
    "original_price",
    "amount",
    "subtotal",
    "tax",
    "discount",
    "total",
    "shipping_cost",
    "unit_price",
    "discount_amount",
    "min_order_amount",
    "fixed_amount",
}
PROJECT_APPS = {
    "accounts", "blog", "cart", "chat", "contact", "dashboard",
    "order", "payments", "promotions", "shipping", "shop",
}  # fmt: skip


def _project_fields():
    for model in apps.get_models():
        if model._meta.app_label in PROJECT_APPS:
            for field in model._meta.get_fields():
                if getattr(field, "concrete", False) and not field.auto_created:
                    yield model, field


def _label(model, field):
    return f"{model._meta.app_label}.{model.__name__}.{field.name}"


class MoneyFieldRegistryTests(SimpleTestCase):
    def test_rial_fields_are_exactly_the_adr_enumeration(self):
        found = {_label(m, f) for m, f in _project_fields() if isinstance(f, RialField)}
        self.assertEqual(found, EXPECTED_RIAL_FIELDS)

    def test_only_percentages_and_ratings_remain_decimal(self):
        found = {
            _label(m, f)
            for m, f in _project_fields()
            if isinstance(f, models.DecimalField)
        }
        self.assertEqual(found, EXPECTED_DECIMAL_FIELDS)

    def test_no_money_named_field_is_anything_but_a_rial_field(self):
        offenders = [
            _label(m, f)
            for m, f in _project_fields()
            if f.name in MONEY_FIELD_NAMES
            and not isinstance(f, RialField)
            and _label(m, f) not in EXPECTED_DECIMAL_FIELDS
        ]
        self.assertEqual(offenders, [])

    def test_every_rial_field_has_a_whole_toman_db_constraint(self):
        missing = []
        for model, field in _project_fields():
            if not isinstance(field, RialField):
                continue
            wanted = f"{model._meta.app_label}_{model.__name__.lower()}_{field.name}_whole_toman"
            names = {
                c.name
                % {"app_label": model._meta.app_label, "class": model.__name__.lower()}
                for c in model._meta.constraints
            }
            if wanted not in names:
                missing.append(_label(model, field))
        self.assertEqual(missing, [])

    def test_every_rial_field_is_unsigned_bigint(self):
        for model, field in _project_fields():
            if isinstance(field, RialField):
                self.assertEqual(field.get_internal_type(), "PositiveBigIntegerField")


@pytest.mark.parametrize("amount", [-10, 5, MAX_RIAL_AMOUNT + 10])
def test_rial_field_full_clean_rejects_bad_values(amount):
    from order.models import OrderItem

    field = OrderItem._meta.get_field("unit_price")
    with pytest.raises(ValidationError):
        field.clean(amount, None)
