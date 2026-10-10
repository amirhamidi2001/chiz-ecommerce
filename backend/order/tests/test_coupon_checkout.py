"""
Coupon discount at checkout (Task 9.1.1.5).

Covers OrderCreateSerializer's server-validated discount, the
CouponRedemption created with the order, re-validation at final checkout,
and the "cancelling frees the coupon" behaviour — both for an explicit
cancellation and for a failed payment.
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from cart.models import Cart
from django.utils import timezone
from order.models import Order
from payments.models import PaymentTransaction
from payments.services import finalize_transaction_failure, finalize_transaction_success
from promotions.models import Coupon, CouponRedemption
from promotions.services import validate_coupon
from promotions.tests.factories import (
    make_category,
    make_completed_redemption,
    make_saved_coupon,
)
from promotions.tests.factories import make_variant as make_catalog_variant
from rest_framework import status
from rest_framework.test import APITestCase
from shop.models import ProductVariant, StockMovement

from .factories import (
    SHIPPING_COST,
    TAX_RATE,
    make_cart_with_items,
    make_product,
    make_user,
    make_variant,
    valid_payload,
)

URL = "/api/orders/"


class CouponCheckoutTestBase(APITestCase):
    """User with a 2 x 25.00 cart (subtotal 50.00) and an authenticated client."""

    def setUp(self):
        self.user = make_user()
        self.product = make_product(price="25.00")
        self.variant = make_variant(product=self.product, stock=10)
        self.cart = make_cart_with_items(
            self.user, [{"variant": self.variant, "quantity": 2}]
        )
        self.subtotal = Decimal("50.00")
        self.client.force_authenticate(user=self.user)

    def apply_coupon(self, coupon):
        """Stand-in for Task 9.1.1.6's apply endpoint: attach coupon to the cart."""
        self.cart.coupon = coupon
        self.cart.save(update_fields=["coupon"])

    def checkout(self, **payload_overrides):
        return self.client.post(URL, valid_payload(**payload_overrides), format="json")

    def expected_total(self, discount):
        tax = (self.subtotal * TAX_RATE).quantize(Decimal("0.01"))
        return self.subtotal + SHIPPING_COST + tax - discount


class CheckoutWithCouponTests(CouponCheckoutTestBase):
    def test_valid_coupon_sets_order_discount_and_creates_redemption(self):
        coupon = make_saved_coupon(
            discount_type=Coupon.DiscountType.PERCENT, value=Decimal("20.00")
        )
        self.apply_coupon(coupon)

        res = self.checkout()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        order = Order.objects.get(pk=res.data["id"])
        # 20% of 50.00
        self.assertEqual(order.discount, Decimal("10.00"))
        self.assertEqual(order.total, self.expected_total(Decimal("10.00")))

        redemption = CouponRedemption.objects.get()
        self.assertEqual(redemption.coupon, coupon)
        self.assertEqual(redemption.user, self.user)
        self.assertEqual(redemption.order, order)
        self.assertEqual(redemption.discount_amount, Decimal("10.00"))

    def test_fixed_coupon_larger_than_subtotal_is_capped_at_subtotal(self):
        coupon = make_saved_coupon(
            discount_type=Coupon.DiscountType.FIXED, value=Decimal("500.00")
        )
        self.apply_coupon(coupon)

        res = self.checkout()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        order = Order.objects.get(pk=res.data["id"])
        self.assertEqual(order.discount, self.subtotal)
        self.assertEqual(order.total, self.expected_total(self.subtotal))
        self.assertGreaterEqual(order.total, 0)

    def test_cart_is_not_cleared_at_order_creation(self):
        # Cart clearing happens on confirmed payment (Task 6.4.1.2), so the
        # coupon reference stays on the cart until then too.
        coupon = make_saved_coupon()
        self.apply_coupon(coupon)
        self.assertEqual(self.checkout().status_code, status.HTTP_201_CREATED)
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.coupon, coupon)
        self.assertTrue(self.cart.items.exists())


class CheckoutWithoutCouponRegressionTests(CouponCheckoutTestBase):
    def test_no_coupon_means_zero_discount_and_no_redemption(self):
        res = self.checkout()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        order = Order.objects.get(pk=res.data["id"])
        self.assertEqual(order.discount, Decimal("0.00"))
        self.assertEqual(order.total, self.expected_total(Decimal("0.00")))
        self.assertFalse(CouponRedemption.objects.exists())

    def test_client_supplied_discount_is_still_ignored(self):
        res = self.checkout(discount="40.00")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        order = Order.objects.get(pk=res.data["id"])
        self.assertEqual(order.discount, Decimal("0.00"))


class CheckoutRevalidationTests(CouponCheckoutTestBase):
    """A coupon that was valid when applied but isn't at checkout time."""

    def assertCheckoutRejectedForCoupon(self, expected_error=None):
        stock_before = self.variant.stock
        orders_before = Order.objects.count()
        redemptions_before = CouponRedemption.objects.count()
        res = self.checkout()

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)
        self.assertIn("coupon", res.data)
        if expected_error:
            self.assertEqual(str(res.data["coupon"][0]), expected_error)
        self.assertEqual(Order.objects.count(), orders_before)
        self.assertEqual(CouponRedemption.objects.count(), redemptions_before)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, stock_before)
        self.assertFalse(
            StockMovement.objects.filter(related_order__user=self.user).exists()
        )

    def test_usage_limit_exhausted_between_apply_and_checkout(self):
        coupon = make_saved_coupon(max_uses=1)
        self.apply_coupon(coupon)
        # Someone else completes checkout with the last available use.
        make_completed_redemption(coupon, make_user(email="other@example.com"))

        self.assertCheckoutRejectedForCoupon("This coupon has reached its usage limit.")

    def test_coupon_expired_between_apply_and_checkout(self):
        coupon = make_saved_coupon()
        self.apply_coupon(coupon)
        Coupon.objects.filter(pk=coupon.pk).update(
            valid_until=timezone.now() - timedelta(minutes=1)
        )

        self.assertCheckoutRejectedForCoupon("This coupon has expired.")

    def test_coupon_deactivated_between_apply_and_checkout(self):
        coupon = make_saved_coupon()
        self.apply_coupon(coupon)
        Coupon.objects.filter(pk=coupon.pk).update(is_active=False)

        self.assertCheckoutRejectedForCoupon("This coupon is no longer active.")

    def test_users_own_limit_reached_between_apply_and_checkout(self):
        coupon = make_saved_coupon(uses_per_user=1)
        self.apply_coupon(coupon)
        make_completed_redemption(coupon, self.user)

        self.assertCheckoutRejectedForCoupon("You have already used this coupon.")

    def test_authoritative_recheck_inside_transaction_rolls_everything_back(self):
        """
        The early validate() pre-check passes, but the re-validation inside
        create()'s atomic block (under the Coupon row lock) fails — e.g.
        another checkout slipped in between. Nothing may be left behind:
        no order, no stock decrement, no redemption.
        """
        coupon = make_saved_coupon()
        self.apply_coupon(coupon)

        from promotions.services import CouponValidationResult
        from promotions.services import validate_coupon as real_validate

        calls = []

        def flaky_validate(code, user, cart, **kwargs):
            calls.append(code)
            if len(calls) == 1:
                return real_validate(
                    code, user, cart, **kwargs
                )  # early pre-check passes
            return CouponValidationResult(
                valid=False, error="This coupon has reached its usage limit."
            )

        with mock.patch(
            "order.serializers.validate_coupon", side_effect=flaky_validate
        ):
            self.assertCheckoutRejectedForCoupon(
                "This coupon has reached its usage limit."
            )
        self.assertEqual(len(calls), 2)


class CancellationFreesCouponTests(CouponCheckoutTestBase):
    def checkout_with_coupon(self, coupon):
        self.apply_coupon(coupon)
        res = self.checkout()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        return Order.objects.get(pk=res.data["id"])

    def test_cancelling_deletes_redemption_and_user_can_use_coupon_again(self):
        coupon = make_saved_coupon(uses_per_user=1)
        order = self.checkout_with_coupon(coupon)

        # While the order stands, the coupon use is consumed.
        blocked = validate_coupon(coupon.code, self.user, self.cart)
        self.assertFalse(blocked.valid)
        self.assertEqual(blocked.error, "You have already used this coupon.")

        res = self.client.patch(
            f"{URL}{order.pk}/", {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertFalse(CouponRedemption.objects.filter(order=order).exists())
        self.assertEqual(coupon.redemptions.count(), 0)

        # Same user, same coupon: valid again ...
        again = validate_coupon(coupon.code, self.user, self.cart)
        self.assertTrue(again.valid)

        # ... and end to end: the cart still holds the items and coupon
        # (the cart is only cleared on confirmed payment), so a second
        # checkout with the same coupon succeeds.
        res2 = self.checkout()
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED, res2.data)
        second = Order.objects.get(pk=res2.data["id"])
        self.assertEqual(second.discount, Decimal("10.00"))
        self.assertEqual(second.coupon_redemption.coupon, coupon)

        # The limit is enforced again for the second, live order.
        self.assertFalse(validate_coupon(coupon.code, self.user, self.cart).valid)

    def test_cancelling_only_frees_that_orders_redemption(self):
        coupon = make_saved_coupon(uses_per_user=1, max_uses=5)
        other_redemption = make_completed_redemption(
            coupon, make_user(email="other@example.com")
        )
        order = self.checkout_with_coupon(coupon)

        res = self.client.patch(
            f"{URL}{order.pk}/", {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        self.assertEqual(list(coupon.redemptions.all()), [other_redemption])

    def test_cancelling_an_order_without_a_coupon_still_works(self):
        res = self.checkout()
        order = Order.objects.get(pk=res.data["id"])
        res = self.client.patch(
            f"{URL}{order.pk}/", {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)


class PaymentPathsAndCouponTests(CouponCheckoutTestBase):
    def make_pending_txn(self, order):
        return PaymentTransaction.objects.create(
            order=order,
            gateway="zarinpal",
            authority="A-COUPON-TEST",
            amount=order.total,
            status=PaymentTransaction.Status.PENDING,
        )

    def test_failed_payment_frees_the_coupon_use(self):
        coupon = make_saved_coupon(uses_per_user=1)
        self.apply_coupon(coupon)
        order = Order.objects.get(pk=self.checkout().data["id"])
        txn = self.make_pending_txn(order)
        self.assertEqual(coupon.redemptions.count(), 1)

        finalize_transaction_failure(txn)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(coupon.redemptions.count(), 0)
        self.assertTrue(validate_coupon(coupon.code, self.user, self.cart).valid)

    def test_successful_payment_keeps_redemption_and_detaches_coupon_from_cart(self):
        coupon = make_saved_coupon(uses_per_user=1)
        self.apply_coupon(coupon)
        order = Order.objects.get(pk=self.checkout().data["id"])
        txn = self.make_pending_txn(order)

        finalize_transaction_success(
            txn, SimpleNamespace(ref_id="12345", raw_response={})
        )

        cart = Cart.objects.get(user=self.user)
        self.assertFalse(cart.items.exists())
        self.assertIsNone(cart.coupon)
        # The completed order's redemption is untouched.
        self.assertEqual(order.coupon_redemption.coupon, coupon)
        self.assertFalse(validate_coupon(coupon.code, self.user, self.cart).valid)


class CartClearViewCouponTests(CouponCheckoutTestBase):
    def test_clearing_the_cart_also_detaches_the_coupon(self):
        self.apply_coupon(make_saved_coupon())

        res = self.client.delete("/api/cart/clear/")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.cart.refresh_from_db()
        self.assertFalse(self.cart.items.exists())
        self.assertIsNone(self.cart.coupon)


class RestrictedCouponCheckoutTests(CouponCheckoutTestBase):
    """Category/product-restricted coupons at checkout (Task 9.1.1.7)."""

    def setUp(self):
        super().setUp()
        # self.cart: 2 x 25.00 in the factories' default category (50.00).
        self.apparel = self.product.category
        # Add a 40.00 item from a DIFFERENT category -> cart subtotal 90.00.
        self.gadgets = make_category("Gadgets")
        self.gadget = make_catalog_variant("40.00", self.gadgets, name="Gadget")
        from cart.models import CartItem

        CartItem.objects.create(cart=self.cart, variant=self.gadget, quantity=1)
        self.cart_subtotal = Decimal("90.00")

    def restricted_coupon(self, **overrides):
        coupon = make_saved_coupon(
            discount_type=Coupon.DiscountType.PERCENT,
            value=Decimal("20.00"),
            **overrides,
        )
        coupon.categories.add(self.apparel)
        return coupon

    def test_discount_covers_only_eligible_items(self):
        self.apply_coupon(self.restricted_coupon())

        res = self.checkout()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        order = Order.objects.get(pk=res.data["id"])
        self.assertEqual(order.subtotal, self.cart_subtotal)
        # 20% of the 50.00 Apparel items, not of the 90.00 cart.
        self.assertEqual(order.discount, Decimal("10.00"))
        self.assertEqual(order.coupon_redemption.discount_amount, Decimal("10.00"))
        tax = (self.cart_subtotal * TAX_RATE).quantize(Decimal("0.01"))
        self.assertEqual(
            order.total, self.cart_subtotal + SHIPPING_COST + tax - Decimal("10.00")
        )

    def test_discount_follows_the_locked_price_not_the_stale_cart_price(self):
        self.apply_coupon(self.restricted_coupon())
        # Price rises after the coupon was applied; checkout must price (and
        # discount) from the locked variant row.
        ProductVariant.objects.filter(pk=self.variant.pk).update(price=Decimal("40.00"))

        res = self.checkout()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        order = Order.objects.get(pk=res.data["id"])
        self.assertEqual(order.subtotal, Decimal("120.00"))  # 2 x 40.00 + 40.00
        self.assertEqual(order.discount, Decimal("16.00"))  # 20% of 2 x 40.00

    def test_checkout_rejected_when_eligible_items_were_removed_after_applying(self):
        self.apply_coupon(self.restricted_coupon())
        self.cart.items.filter(variant=self.variant).delete()  # only the gadget left
        orders_before = Order.objects.count()

        res = self.checkout()

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.data)
        self.assertEqual(
            str(res.data["coupon"][0]),
            "This coupon does not apply to any items in your cart.",
        )
        self.assertEqual(Order.objects.count(), orders_before)
        self.assertFalse(CouponRedemption.objects.exists())

    def test_checkout_passes_its_locked_price_snapshot_to_validate_coupon(self):
        from promotions.services import validate_coupon as real_validate

        self.apply_coupon(self.restricted_coupon())

        with mock.patch(
            "order.serializers.validate_coupon", wraps=real_validate
        ) as spy:
            res = self.checkout()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        order = Order.objects.get(pk=res.data["id"])
        # Early pre-check (no lines) + authoritative in-transaction check
        # (with the priced snapshot every Order figure is derived from).
        self.assertEqual(spy.call_count, 2)
        self.assertNotIn("lines", spy.call_args_list[0].kwargs)
        lines = spy.call_args_list[1].kwargs["lines"]
        self.assertEqual(sum(line.amount for line in lines), order.subtotal)
        self.assertEqual(
            {line.product_id for line in lines},
            {self.variant.product_id, self.gadget.product_id},
        )
