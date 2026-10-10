from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.utils import timezone
from promotions.models import Coupon
from promotions.services import CouponLine, CouponValidationResult, validate_coupon

from .factories import (
    make_cart,
    make_category,
    make_completed_redemption,
    make_in_progress_redemption,
    make_priced_cart,
    make_saved_coupon,
    make_user,
    make_variant,
)

SUBTOTAL = Decimal("100.00")


class ValidateCouponTestBase(TestCase):
    def setUp(self):
        self.user = make_user()
        # Default cart: one item, subtotal SUBTOTAL (100.00).
        self.cart = make_priced_cart(self.user, SUBTOTAL)

    def cart_of(self, amount):
        """Rebuild the user's cart as a single item worth exactly `amount`."""
        return make_priced_cart(self.user, amount)


class RejectionTests(ValidateCouponTestBase):
    def assertRejected(self, result, error):
        self.assertIsInstance(result, CouponValidationResult)
        self.assertFalse(result.valid)
        self.assertEqual(result.error, error)
        self.assertEqual(result.discount_amount, Decimal("0"))
        self.assertIsNone(result.coupon)

    def test_nonexistent_code(self):
        result = validate_coupon("NOPE", self.user, self.cart)
        self.assertRejected(result, "Invalid coupon code.")

    def test_inactive_coupon(self):
        make_saved_coupon(is_active=False)
        result = validate_coupon("SUMMER20", self.user, self.cart)
        self.assertRejected(result, "This coupon is no longer active.")

    def test_not_yet_valid(self):
        now = timezone.now()
        make_saved_coupon(
            valid_from=now + timedelta(days=1), valid_until=now + timedelta(days=10)
        )
        result = validate_coupon("SUMMER20", self.user, self.cart)
        self.assertRejected(result, "This coupon is not yet valid.")

    def test_expired(self):
        now = timezone.now()
        make_saved_coupon(
            valid_from=now - timedelta(days=10), valid_until=now - timedelta(days=1)
        )
        result = validate_coupon("SUMMER20", self.user, self.cart)
        self.assertRejected(result, "This coupon has expired.")

    def test_subtotal_below_min_order_amount(self):
        make_saved_coupon(min_order_amount=Decimal("150.00"))
        result = validate_coupon("SUMMER20", self.user, self.cart_of("149.99"))
        self.assertRejected(result, "This coupon requires a minimum order of 150.00.")

    def test_subtotal_exactly_at_min_order_amount_is_accepted(self):
        make_saved_coupon(min_order_amount=Decimal("150.00"))
        result = validate_coupon("SUMMER20", self.user, self.cart_of("150.00"))
        self.assertTrue(result.valid)

    def test_max_uses_reached_by_completed_redemptions(self):
        coupon = make_saved_coupon(max_uses=2, uses_per_user=5)
        make_completed_redemption(coupon, self.user)
        make_completed_redemption(coupon, make_user(email="other@example.com"))
        result = validate_coupon("SUMMER20", self.user, self.cart)
        self.assertRejected(result, "This coupon has reached its usage limit.")

    def test_in_progress_redemptions_do_not_count_toward_max_uses(self):
        coupon = make_saved_coupon(max_uses=1)
        make_in_progress_redemption(coupon, make_user(email="other@example.com"))
        make_in_progress_redemption(coupon, make_user(email="third@example.com"))
        result = validate_coupon("SUMMER20", self.user, self.cart)
        self.assertTrue(result.valid)

    def test_max_uses_none_means_unlimited(self):
        coupon = make_saved_coupon(max_uses=None, uses_per_user=100)
        for _ in range(3):
            make_completed_redemption(coupon, self.user)
        result = validate_coupon("SUMMER20", self.user, self.cart)
        self.assertTrue(result.valid)

    def test_user_none_requires_login(self):
        make_saved_coupon()
        result = validate_coupon("SUMMER20", None, self.cart)
        self.assertRejected(result, "Please log in to use a coupon code.")

    def test_anonymous_user_requires_login(self):
        make_saved_coupon()
        result = validate_coupon("SUMMER20", AnonymousUser(), self.cart)
        self.assertRejected(result, "Please log in to use a coupon code.")

    def test_uses_per_user_reached(self):
        coupon = make_saved_coupon(uses_per_user=1)
        make_completed_redemption(coupon, self.user)
        result = validate_coupon("SUMMER20", self.user, self.cart)
        self.assertRejected(result, "You have already used this coupon.")

    def test_a_different_user_can_still_use_the_coupon(self):
        coupon = make_saved_coupon(uses_per_user=1)
        make_completed_redemption(coupon, self.user)
        other = make_user(email="other@example.com")
        result = validate_coupon("SUMMER20", other, self.cart)
        self.assertTrue(result.valid)

    def test_in_progress_redemption_does_not_consume_users_single_use(self):
        coupon = make_saved_coupon(uses_per_user=1)
        make_in_progress_redemption(coupon, self.user)
        result = validate_coupon("SUMMER20", self.user, self.cart)
        self.assertTrue(result.valid)


class SuccessTests(ValidateCouponTestBase):
    def test_success_returns_coupon_and_empty_error(self):
        coupon = make_saved_coupon()
        result = validate_coupon("SUMMER20", self.user, self.cart)
        self.assertTrue(result.valid)
        self.assertEqual(result.coupon, coupon)
        self.assertEqual(result.error, "")

    def test_code_lookup_is_case_and_whitespace_insensitive(self):
        make_saved_coupon(code="SUMMER20")
        result = validate_coupon("  summer20 ", self.user, self.cart)
        self.assertTrue(result.valid)

    def test_percent_discount_is_rounded_to_two_places(self):
        make_saved_coupon(
            discount_type=Coupon.DiscountType.PERCENT, value=Decimal("15.00")
        )
        # 99.99 * 15% = 14.9985 -> 15.00
        result = validate_coupon("SUMMER20", self.user, self.cart_of("99.99"))
        self.assertTrue(result.valid)
        self.assertEqual(result.discount_amount, Decimal("15.00"))
        # exponent is exactly two places, not just numerically equal
        self.assertEqual(result.discount_amount.as_tuple().exponent, -2)

    def test_percent_discount_rounds_down_when_below_half_cent(self):
        make_saved_coupon(
            discount_type=Coupon.DiscountType.PERCENT, value=Decimal("10.00")
        )
        # 33.33 * 10% = 3.333 -> 3.33
        result = validate_coupon("SUMMER20", self.user, self.cart_of("33.33"))
        self.assertEqual(result.discount_amount, Decimal("3.33"))

    def test_fixed_discount_below_subtotal(self):
        make_saved_coupon(
            discount_type=Coupon.DiscountType.FIXED, value=Decimal("10.00")
        )
        result = validate_coupon("SUMMER20", self.user, self.cart_of("100.00"))
        self.assertTrue(result.valid)
        self.assertEqual(result.discount_amount, Decimal("10.00"))

    def test_fixed_discount_is_capped_at_subtotal(self):
        make_saved_coupon(
            discount_type=Coupon.DiscountType.FIXED, value=Decimal("50.00")
        )
        result = validate_coupon("SUMMER20", self.user, self.cart_of("20.00"))
        self.assertTrue(result.valid)
        self.assertEqual(result.discount_amount, Decimal("20.00"))


class RestrictedCouponTests(TestCase):
    """
    Category / product restrictions (Task 9.1.1.7).

    Shared cart (total 130.00):
        serum     (Skincare)  20.00 x 1 = 20.00
        cleanser  (Skincare)  30.00 x 2 = 60.00   -> Skincare subtotal 80.00
        lipstick  (Makeup)    50.00 x 1 = 50.00
    """

    def setUp(self):
        self.user = make_user()
        self.skincare = make_category("Skincare")
        self.makeup = make_category("Makeup")
        self.haircare = make_category("Haircare")
        self.serum = make_variant("20.00", self.skincare, name="Serum")
        self.cleanser = make_variant("30.00", self.skincare, name="Cleanser")
        self.lipstick = make_variant("50.00", self.makeup, name="Lipstick")
        self.cart = make_cart(
            self.user, (self.serum, 1), (self.cleanser, 2), (self.lipstick, 1)
        )

    def percent_coupon(self, value="20.00", **overrides):
        return make_saved_coupon(
            discount_type=Coupon.DiscountType.PERCENT,
            value=Decimal(value),
            **overrides,
        )

    def validate(self, **kwargs):
        return validate_coupon("SUMMER20", self.user, self.cart, **kwargs)

    # 1. Regression: no restriction still discounts the full cart.
    def test_unrestricted_coupon_discounts_the_full_cart(self):
        self.percent_coupon()
        result = self.validate()
        self.assertTrue(result.valid)
        self.assertEqual(result.discount_amount, Decimal("26.00"))  # 20% of 130.00

    # 2. Category restriction: only matching items count (mixed cart).
    def test_category_restricted_coupon_discounts_only_matching_items(self):
        coupon = self.percent_coupon()
        coupon.categories.add(self.skincare)

        result = self.validate()

        self.assertTrue(result.valid)
        # 20% of the Skincare items (20 + 60 = 80.00), NOT of 130.00.
        self.assertEqual(result.discount_amount, Decimal("16.00"))

    # 3. Category the cart has nothing in.
    def test_category_with_no_items_in_cart_is_rejected(self):
        coupon = self.percent_coupon()
        coupon.categories.add(self.haircare)

        result = self.validate()

        self.assertFalse(result.valid)
        self.assertEqual(
            result.error, "This coupon does not apply to any items in your cart."
        )
        self.assertIsNone(result.coupon)
        self.assertEqual(result.discount_amount, Decimal("0"))

    # 4. Product restriction, independent of the category path.
    def test_product_restricted_coupon_discounts_only_those_products(self):
        coupon = self.percent_coupon()
        coupon.products.add(self.lipstick.product)  # no categories set

        result = self.validate()

        self.assertTrue(result.valid)
        self.assertEqual(result.discount_amount, Decimal("10.00"))  # 20% of 50.00

    def test_product_restriction_with_product_not_in_cart_is_rejected(self):
        other = make_variant("99.00", self.haircare, name="Shampoo")
        coupon = self.percent_coupon()
        coupon.products.add(other.product)

        result = self.validate()

        self.assertFalse(result.valid)
        self.assertEqual(
            result.error, "This coupon does not apply to any items in your cart."
        )

    # 5. Both restrictions: an item matching EITHER is eligible.
    def test_category_and_product_restrictions_are_a_union(self):
        coupon = self.percent_coupon()
        coupon.categories.add(self.skincare)  # serum + cleanser = 80.00
        coupon.products.add(self.lipstick.product)  # + 50.00 (via product)

        result = self.validate()

        self.assertTrue(result.valid)
        self.assertEqual(result.discount_amount, Decimal("26.00"))  # 20% of 130.00

    def test_item_matching_both_restrictions_is_counted_once(self):
        coupon = self.percent_coupon()
        coupon.categories.add(self.skincare)  # includes the serum
        coupon.products.add(self.serum.product)  # ...which is also listed here

        result = self.validate()

        # Skincare only (80.00); the serum is not double-counted.
        self.assertEqual(result.discount_amount, Decimal("16.00"))

    # ── Amount rules apply to the ELIGIBLE portion ───────────────────────────
    def test_fixed_discount_is_capped_at_the_eligible_subtotal(self):
        coupon = make_saved_coupon(
            discount_type=Coupon.DiscountType.FIXED, value=Decimal("100.00")
        )
        coupon.categories.add(self.skincare)  # eligible 80.00 of a 130.00 cart

        result = self.validate()

        self.assertTrue(result.valid)
        self.assertEqual(result.discount_amount, Decimal("80.00"))

    def test_min_order_amount_is_checked_against_the_eligible_subtotal(self):
        # Whole cart (130.00) clears the 100.00 minimum; Skincare (80.00) doesn't.
        coupon = self.percent_coupon(min_order_amount=Decimal("100.00"))
        coupon.categories.add(self.skincare)

        result = self.validate()

        self.assertFalse(result.valid)
        self.assertEqual(
            result.error, "This coupon requires a minimum eligible order of 100.00."
        )

    def test_min_order_amount_met_by_the_eligible_subtotal_is_accepted(self):
        coupon = self.percent_coupon(min_order_amount=Decimal("80.00"))
        coupon.categories.add(self.skincare)
        self.assertTrue(self.validate().valid)

    def test_unrestricted_min_order_message_keeps_the_plain_wording(self):
        self.percent_coupon(min_order_amount=Decimal("500.00"))
        result = self.validate()
        self.assertEqual(
            result.error, "This coupon requires a minimum order of 500.00."
        )

    # ── Matching semantics worth pinning down ───────────────────────────────
    def test_category_match_is_exact_and_does_not_include_subcategories(self):
        beauty = make_category("Beauty")
        eyes = make_category("Eyes", parent=beauty)
        mascara = make_variant("15.00", eyes, name="Mascara")
        self.cart = make_cart(self.user, (mascara, 1))
        coupon = self.percent_coupon()
        coupon.categories.add(beauty)  # parent only

        result = self.validate()

        self.assertFalse(result.valid)
        self.assertEqual(
            result.error, "This coupon does not apply to any items in your cart."
        )
        # Selecting the sub-category as well makes it eligible.
        coupon.categories.add(eyes)
        self.assertEqual(self.validate().discount_amount, Decimal("3.00"))

    def test_uncategorised_product_matches_by_product_only(self):
        loose = make_variant("40.00", None, name="Gift Card")
        self.cart = make_cart(self.user, (loose, 1))

        by_category = self.percent_coupon(code="BYCAT")
        by_category.categories.add(self.skincare)
        by_product = self.percent_coupon(code="BYPROD")
        by_product.products.add(loose.product)

        self.assertFalse(validate_coupon("BYCAT", self.user, self.cart).valid)
        result = validate_coupon("BYPROD", self.user, self.cart)
        self.assertTrue(result.valid)
        self.assertEqual(result.discount_amount, Decimal("8.00"))

    # ── `lines` override (used by checkout's locked price snapshot) ─────────
    def test_explicit_lines_are_used_instead_of_the_carts_contents(self):
        self.percent_coupon()
        lines = [
            CouponLine(
                product_id=self.serum.product_id,
                category_id=self.skincare.pk,
                amount=Decimal("40.00"),
            )
        ]

        result = self.validate(lines=lines)

        self.assertEqual(result.discount_amount, Decimal("8.00"))  # 20% of 40.00

    def test_explicit_lines_are_filtered_by_the_restrictions_too(self):
        coupon = self.percent_coupon()
        coupon.categories.add(self.skincare)
        lines = [
            CouponLine(
                product_id=self.serum.product_id,
                category_id=self.skincare.pk,
                amount=Decimal("40.00"),
            ),
            CouponLine(
                product_id=self.lipstick.product_id,
                category_id=self.makeup.pk,
                amount=Decimal("500.00"),
            ),
        ]

        result = self.validate(lines=lines)

        self.assertEqual(result.discount_amount, Decimal("8.00"))

    def test_empty_cart_is_rejected_as_not_applicable(self):
        self.percent_coupon()
        self.cart = make_cart(self.user)  # no items

        result = self.validate()

        self.assertFalse(result.valid)
        self.assertEqual(
            result.error, "This coupon does not apply to any items in your cart."
        )
