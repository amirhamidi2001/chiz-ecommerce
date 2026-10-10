"""
Cart-level coupon application (Task 9.1.1.6): POST/DELETE
/api/cart/apply-coupon/ and the live coupon fields on GET /api/cart/.
"""

from datetime import timedelta
from decimal import Decimal
from unittest import mock

from cart.models import Cart
from django.core.cache import cache
from django.utils import timezone
from order.tests.factories import make_cart_with_items, make_user, make_variant
from promotions.models import Coupon
from promotions.services import validate_coupon
from promotions.tests.factories import (
    make_category,
    make_completed_redemption,
    make_saved_coupon,
)
from promotions.tests.factories import make_variant as make_catalog_variant
from rest_framework import status
from rest_framework.test import APITestCase

CART_URL = "/api/cart/"
APPLY_URL = "/api/cart/apply-coupon/"


class CouponCartTestBase(APITestCase):
    def setUp(self):
        # Several anonymous requests per test accumulate against the
        # cache-backed AnonRateThrottle; same precedent as
        # CartAnonymousAccessTests in test_cart.py.
        cache.clear()
        self.variant = make_variant(price="25.00", stock=20)

    def tearDown(self):
        cache.clear()


class AuthenticatedCartTestBase(CouponCartTestBase):
    """Authenticated user with a 2 x 25.00 cart (subtotal 50.00)."""

    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.cart = make_cart_with_items(
            self.user, [{"variant": self.variant, "quantity": 2}]
        )
        self.client.force_authenticate(user=self.user)

    def apply(self, code="SUMMER20"):
        return self.client.post(APPLY_URL, {"code": code}, format="json")

    def attach(self, coupon):
        """Attach directly, bypassing the endpoint (to set up 'applied earlier')."""
        self.cart.coupon = coupon
        self.cart.save(update_fields=["coupon"])


class ApplyCouponTests(AuthenticatedCartTestBase):
    def test_valid_coupon_is_applied_to_the_cart(self):
        coupon = make_saved_coupon(
            discount_type=Coupon.DiscountType.PERCENT, value=Decimal("20.00")
        )

        res = self.apply()

        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data, {"code": "SUMMER20", "discount_amount": "10.00"})
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.coupon, coupon)

    def test_code_is_case_and_whitespace_insensitive(self):
        coupon = make_saved_coupon()
        res = self.apply("  summer20 ")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.coupon, coupon)

    def test_applying_a_second_valid_coupon_replaces_the_first(self):
        make_saved_coupon(code="FIRST")
        second = make_saved_coupon(code="SECOND")
        self.assertEqual(self.apply("FIRST").status_code, status.HTTP_200_OK)
        self.assertEqual(self.apply("SECOND").status_code, status.HTTP_200_OK)
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.coupon, second)

    def test_rejections_return_400_and_leave_cart_unchanged(self):
        now = timezone.now()
        cases = {
            "NOPE": ("Invalid coupon code.", None),
            "INACTIVE": (
                "This coupon is no longer active.",
                dict(code="INACTIVE", is_active=False),
            ),
            "EXPIRED": (
                "This coupon has expired.",
                dict(
                    code="EXPIRED",
                    valid_from=now - timedelta(days=10),
                    valid_until=now - timedelta(days=1),
                ),
            ),
            "FUTURE": (
                "This coupon is not yet valid.",
                dict(
                    code="FUTURE",
                    valid_from=now + timedelta(days=1),
                    valid_until=now + timedelta(days=10),
                ),
            ),
            "BIGCART": (
                "This coupon requires a minimum order of 500.00.",
                dict(code="BIGCART", min_order_amount=Decimal("500.00")),
            ),
        }
        for code, (error, overrides) in cases.items():
            if overrides:
                make_saved_coupon(**overrides)
            with self.subTest(code=code):
                res = self.apply(code)
                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(res.data, {"coupon": [error]})
                self.cart.refresh_from_db()
                self.assertIsNone(self.cart.coupon)

    def test_usage_limit_rejections_leave_cart_unchanged(self):
        exhausted = make_saved_coupon(code="LASTONE", max_uses=1)
        make_completed_redemption(exhausted, make_user(email="other@example.com"))
        used_by_me = make_saved_coupon(code="ONCEONLY", uses_per_user=1)
        make_completed_redemption(used_by_me, self.user)

        for code, error in [
            ("LASTONE", "This coupon has reached its usage limit."),
            ("ONCEONLY", "You have already used this coupon."),
        ]:
            with self.subTest(code=code):
                res = self.apply(code)
                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(res.data, {"coupon": [error]})
                self.cart.refresh_from_db()
                self.assertIsNone(self.cart.coupon)

    def test_failed_apply_keeps_a_previously_applied_coupon(self):
        good = make_saved_coupon(code="GOOD")
        self.assertEqual(self.apply("GOOD").status_code, status.HTTP_200_OK)

        res = self.apply("NOPE")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.coupon, good)

    def test_missing_or_blank_code_is_a_400(self):
        for payload in ({}, {"code": ""}, {"code": "   "}):
            with self.subTest(payload=payload):
                res = self.client.post(APPLY_URL, payload, format="json")
                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("code", res.data)

    def test_does_not_touch_another_users_cart(self):
        make_saved_coupon()
        other_cart = make_cart_with_items(
            make_user(email="other@example.com"),
            [{"variant": self.variant, "quantity": 1}],
        )
        self.assertEqual(self.apply().status_code, status.HTTP_200_OK)
        other_cart.refresh_from_db()
        self.assertIsNone(other_cart.coupon)


class RestrictedCouponCartTests(AuthenticatedCartTestBase):
    """Category-restricted coupons through the cart endpoints (Task 9.1.1.7)."""

    def setUp(self):
        super().setUp()
        self.skincare = make_category("Skincare")
        self.serum = make_catalog_variant("30.00", self.skincare, name="Serum")
        # Cart: 2 x 25.00 (uncategorised-by-coupon) + 30.00 Skincare = 80.00.
        from cart.models import CartItem

        CartItem.objects.create(cart=self.cart, variant=self.serum, quantity=1)

    def skincare_coupon(self):
        coupon = make_saved_coupon(
            discount_type=Coupon.DiscountType.PERCENT, value=Decimal("20.00")
        )
        coupon.categories.add(self.skincare)
        return coupon

    def test_apply_reports_the_discount_on_eligible_items_only(self):
        coupon = self.skincare_coupon()

        res = self.apply()

        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["discount_amount"], "6.00")  # 20% of 30.00
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.coupon, coupon)

    def test_apply_rejected_when_nothing_in_the_cart_is_eligible(self):
        self.cart.items.filter(variant=self.serum).delete()
        self.skincare_coupon()

        res = self.apply()

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            res.data,
            {"coupon": ["This coupon does not apply to any items in your cart."]},
        )
        self.cart.refresh_from_db()
        self.assertIsNone(self.cart.coupon)

    def test_cart_view_tracks_eligibility_as_items_change(self):
        self.skincare_coupon()
        self.assertEqual(self.apply().status_code, status.HTTP_200_OK)

        res = self.client.get(CART_URL)
        self.assertEqual(res.data["coupon_discount"], "6.00")
        self.assertIsNone(res.data["coupon_error"])

        self.cart.items.filter(variant=self.serum).delete()  # eligible item removed

        res = self.client.get(CART_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["coupon_code"], "SUMMER20")
        self.assertEqual(res.data["coupon_discount"], "0")
        self.assertEqual(
            res.data["coupon_error"],
            "This coupon does not apply to any items in your cart.",
        )


class RemoveCouponTests(AuthenticatedCartTestBase):
    def test_delete_clears_the_applied_coupon(self):
        self.attach(make_saved_coupon())

        res = self.client.delete(APPLY_URL)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.cart.refresh_from_db()
        self.assertIsNone(self.cart.coupon)

    def test_delete_with_no_coupon_is_a_harmless_204(self):
        res = self.client.delete(APPLY_URL)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.cart.refresh_from_db()
        self.assertIsNone(self.cart.coupon)


class CartRetrievalCouponFieldsTests(AuthenticatedCartTestBase):
    def test_no_coupon_fields_are_empty(self):
        res = self.client.get(CART_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data["coupon_code"])
        self.assertEqual(res.data["coupon_discount"], "0")
        self.assertIsNone(res.data["coupon_error"])

    def test_get_after_applying_includes_code_and_discount(self):
        make_saved_coupon(
            discount_type=Coupon.DiscountType.PERCENT, value=Decimal("20.00")
        )
        self.assertEqual(self.apply().status_code, status.HTTP_200_OK)

        res = self.client.get(CART_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["coupon_code"], "SUMMER20")
        self.assertEqual(res.data["coupon_discount"], "10.00")
        self.assertIsNone(res.data["coupon_error"])

    def test_discount_tracks_the_cart_as_it_changes(self):
        make_saved_coupon(
            discount_type=Coupon.DiscountType.PERCENT, value=Decimal("20.00")
        )
        self.assertEqual(self.apply().status_code, status.HTTP_200_OK)

        # Add 2 more of the same variant -> 4 x 25.00 = 100.00; the add-item
        # response is also a CartSerializer payload, so it carries the fields.
        res = self.client.post(
            CART_URL, {"variant_id": self.variant.id, "quantity": 2}, format="json"
        )

        self.assertIn(res.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        self.assertEqual(res.data["coupon_code"], "SUMMER20")
        self.assertEqual(res.data["coupon_discount"], "20.00")

    def test_expired_since_applied_shows_error_without_failing_the_request(self):
        coupon = make_saved_coupon()
        self.assertEqual(self.apply().status_code, status.HTTP_200_OK)
        Coupon.objects.filter(pk=coupon.pk).update(
            valid_until=timezone.now() - timedelta(minutes=1)
        )

        res = self.client.get(CART_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["coupon_code"], "SUMMER20")  # still attached
        self.assertEqual(res.data["coupon_discount"], "0")
        self.assertEqual(res.data["coupon_error"], "This coupon has expired.")
        self.assertEqual(len(res.data["items"]), 1)  # the rest of the cart is intact

    def test_cart_falling_below_min_order_after_applying_shows_error(self):
        make_saved_coupon(min_order_amount=Decimal("40.00"))
        self.assertEqual(self.apply().status_code, status.HTTP_200_OK)
        item = self.cart.items.get()
        item.quantity = 1  # subtotal 25.00 < 40.00
        item.save()

        res = self.client.get(CART_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["coupon_discount"], "0")
        self.assertEqual(
            res.data["coupon_error"], "This coupon requires a minimum order of 40.00."
        )

    def test_deleted_coupon_simply_disappears_from_the_cart(self):
        coupon = make_saved_coupon()
        self.assertEqual(self.apply().status_code, status.HTTP_200_OK)
        coupon.delete()  # Cart.coupon is SET_NULL

        res = self.client.get(CART_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data["coupon_code"])
        self.assertIsNone(res.data["coupon_error"])

    def test_coupon_is_validated_once_per_serialization(self):
        make_saved_coupon()
        self.assertEqual(self.apply().status_code, status.HTTP_200_OK)

        with mock.patch(
            "cart.serializers.validate_coupon", wraps=validate_coupon
        ) as spy:
            res = self.client.get(CART_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(spy.call_count, 1)


class GuestCartCouponTests(CouponCartTestBase):
    """Coupons are authenticated-only (Task 9.1.1.3); guests get 'please log in'."""

    def setUp(self):
        super().setUp()
        make_saved_coupon()
        # A guest cart: adding an item creates the session-based cart.
        res = self.client.post(
            CART_URL, {"variant_id": self.variant.id, "quantity": 2}, format="json"
        )
        self.assertIn(res.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        self.cart = Cart.objects.get(session_key=self.client.session.session_key)

    def test_guest_applying_a_valid_coupon_is_told_to_log_in(self):
        res = self.client.post(APPLY_URL, {"code": "SUMMER20"}, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data, {"coupon": ["Please log in to use a coupon code."]})
        self.cart.refresh_from_db()
        self.assertIsNone(self.cart.coupon)

    def test_guest_cart_shows_no_coupon_by_default(self):
        res = self.client.get(CART_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data["coupon_code"])
        self.assertEqual(res.data["coupon_discount"], "0")
        self.assertIsNone(res.data["coupon_error"])

    def test_guest_delete_is_a_harmless_204(self):
        res = self.client.delete(APPLY_URL)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

    def test_guest_cart_with_a_coupon_attached_reports_login_error_not_a_crash(self):
        # Shouldn't be reachable through the API; guards the serializer
        # against an AnonymousUser requester if it ever happens.
        self.cart.coupon = Coupon.objects.get(code="SUMMER20")
        self.cart.save(update_fields=["coupon"])

        res = self.client.get(CART_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["coupon_discount"], "0")
        self.assertEqual(
            res.data["coupon_error"], "Please log in to use a coupon code."
        )
