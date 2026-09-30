from decimal import Decimal

from cart.models import Cart, CartItem
from order.tests.factories import make_cart_with_items, make_user, make_variant
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from shipping.models import ShippingCarrier, ShippingRate

QUOTE_URL = "/api/shipping/quote/"


def make_carrier(code=ShippingCarrier.Code.POST, is_active=True):
    carrier, _ = ShippingCarrier.objects.get_or_create(
        code=code,
        defaults={"display_name": ShippingCarrier.Code(code).label},
    )
    if carrier.is_active != is_active:
        carrier.is_active = is_active
        carrier.save(update_fields=["is_active"])
    return carrier


def make_rate(
    *,
    carrier,
    province="tehran",
    city="",
    min_weight_g=0,
    max_weight_g=1_000_000,
    price="9.99",
    estimated_days_min=1,
    estimated_days_max=3,
    is_active=True,
):
    return ShippingRate.objects.create(
        carrier=carrier,
        province=province,
        city=city,
        min_weight_g=min_weight_g,
        max_weight_g=max_weight_g,
        price=Decimal(price),
        estimated_days_min=estimated_days_min,
        estimated_days_max=estimated_days_max,
        is_active=is_active,
    )


class ShippingQuoteViewAuthenticatedCartTests(APITestCase):
    """
    Acceptance criteria 1-3: matching options returned, weight-bracket
    selection is correct, empty result for no match, inactive carriers
    excluded — all exercised against an authenticated user's cart first.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        self.client.force_authenticate(user=self.user)
        # A single variant with an explicit weight_g (not the flat-estimate
        # fallback) so the weight-bracket assertions are exact and don't
        # depend on ProductVariant.DEFAULT_ESTIMATED_WEIGHT_G's value.
        self.variant = make_variant(price="50.00", stock=10)
        self.variant.weight_g = 500
        self.variant.save(update_fields=["weight_g"])
        make_cart_with_items(self.user, [{"variant": self.variant, "quantity": 2}])
        # Total cart weight = 500g * 2 = 1000g.

    def test_matching_active_rate_is_returned_with_expected_fields(self):
        carrier = make_carrier(code=ShippingCarrier.Code.POST)
        rate = make_rate(
            carrier=carrier,
            province="tehran",
            min_weight_g=0,
            max_weight_g=2000,
            price="45000.00",
            estimated_days_min=2,
            estimated_days_max=4,
        )

        response = self.client.post(
            QUOTE_URL, {"province": "tehran", "city": "Tehran"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["options"],
            [
                {
                    "carrier_id": carrier.id,
                    "carrier_name": carrier.display_name,
                    "rate_id": rate.id,
                    "price": "45000.00",
                    "estimated_days_min": 2,
                    "estimated_days_max": 4,
                }
            ],
        )

    def test_correct_weight_bracket_is_selected_among_several(self):
        # Cart weight is 1000g. Two brackets exist for the same carrier;
        # only the one that actually contains 1000g should be returned.
        carrier = make_carrier(code=ShippingCarrier.Code.POST)
        make_rate(
            carrier=carrier,
            province="tehran",
            min_weight_g=0,
            max_weight_g=999,
            price="10000.00",
        )
        heavier_rate = make_rate(
            carrier=carrier,
            province="tehran",
            min_weight_g=1000,
            max_weight_g=5000,
            price="20000.00",
        )

        response = self.client.post(
            QUOTE_URL, {"province": "tehran", "city": "Tehran"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["options"]), 1)
        option = response.data["options"][0]
        self.assertEqual(option["rate_id"], heavier_rate.id)
        self.assertEqual(option["price"], "20000.00")

    def test_multiple_active_carriers_with_matching_rates_all_appear(self):
        post = make_carrier(code=ShippingCarrier.Code.POST)
        tipax = make_carrier(code=ShippingCarrier.Code.TIPAX)
        make_rate(carrier=post, province="tehran", price="10000.00")
        make_rate(carrier=tipax, province="tehran", price="15000.00")

        response = self.client.post(
            QUOTE_URL, {"province": "tehran", "city": "Tehran"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_carrier_ids = {o["carrier_id"] for o in response.data["options"]}
        self.assertEqual(returned_carrier_ids, {post.id, tipax.id})

    def test_no_matching_rate_returns_empty_options_with_200(self):
        # No ShippingRate rows created at all for this destination — this
        # must be a normal 200 with an empty list, not an error.
        response = self.client.post(
            QUOTE_URL, {"province": "yazd", "city": "Yazd"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["options"], [])

    def test_weight_outside_every_bracket_returns_empty_options(self):
        carrier = make_carrier(code=ShippingCarrier.Code.POST)
        # Cart weight is 1000g; this bracket tops out at 500g.
        make_rate(carrier=carrier, province="tehran", min_weight_g=0, max_weight_g=500)

        response = self.client.post(
            QUOTE_URL, {"province": "tehran", "city": "Tehran"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["options"], [])

    def test_inactive_carrier_never_appears_even_with_a_matching_active_rate(self):
        # The carrier-level is_active filter must take precedence over an
        # otherwise-perfectly-matching, active ShippingRate row.
        inactive_carrier = make_carrier(
            code=ShippingCarrier.Code.SNAPBOX, is_active=False
        )
        make_rate(carrier=inactive_carrier, province="tehran", is_active=True)

        response = self.client.post(
            QUOTE_URL, {"province": "tehran", "city": "Tehran"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["options"], [])

    def test_inactive_rate_on_an_active_carrier_is_excluded(self):
        carrier = make_carrier(code=ShippingCarrier.Code.POST)
        make_rate(carrier=carrier, province="tehran", is_active=False)

        response = self.client.post(
            QUOTE_URL, {"province": "tehran", "city": "Tehran"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["options"], [])

    def test_city_specific_rate_is_preferred_over_province_wide(self):
        carrier = make_carrier(code=ShippingCarrier.Code.ALOPEYK)
        make_rate(carrier=carrier, province="tehran", city="", price="10000.00")
        city_rate = make_rate(
            carrier=carrier, province="tehran", city="Tehran", price="5000.00"
        )

        response = self.client.post(
            QUOTE_URL, {"province": "tehran", "city": "Tehran"}, format="json"
        )

        self.assertEqual(len(response.data["options"]), 1)
        self.assertEqual(response.data["options"][0]["rate_id"], city_rate.id)
        self.assertEqual(response.data["options"][0]["price"], "5000.00")

    def test_missing_province_is_a_400(self):
        response = self.client.post(QUOTE_URL, {"city": "Tehran"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("province", response.data)

    def test_invalid_province_choice_is_a_400(self):
        response = self.client.post(
            QUOTE_URL, {"province": "california", "city": "LA"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("province", response.data)

    def test_missing_city_is_a_400(self):
        response = self.client.post(QUOTE_URL, {"province": "tehran"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("city", response.data)


class ShippingQuoteViewGuestCartTests(APITestCase):
    """
    Acceptance criterion 4 (guest half): AllowAny + get_or_create_cart()
    must resolve a session-based anonymous cart correctly, exactly as it
    does for CartView elsewhere in Epic 5 — never require authentication.
    """

    def setUp(self):
        self.client = APIClient()
        self.variant = make_variant(price="30.00", stock=10)
        self.variant.weight_g = 400
        self.variant.save(update_fields=["weight_g"])

        # Pre-seed a real Django session (Cart is looked up by session_key,
        # so the anonymous cart must exist under the SAME session the test
        # client will send back on its next request) and attach a cart to
        # it directly, mirroring how an anonymous shopper's cart already
        # exists in their session before they ever reach the shipping step.
        session = self.client.session
        session.save()
        self.cart = Cart.objects.create(session_key=session.session_key)
        CartItem.objects.create(cart=self.cart, variant=self.variant, quantity=3)
        # Total anonymous cart weight = 400g * 3 = 1200g.

    def test_unauthenticated_request_is_not_rejected(self):
        response = self.client.post(
            QUOTE_URL, {"province": "tehran", "city": "Tehran"}, format="json"
        )
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_guest_cart_weight_is_used_for_bracket_selection(self):
        carrier = make_carrier(code=ShippingCarrier.Code.POST)
        make_rate(carrier=carrier, province="tehran", min_weight_g=0, max_weight_g=1199)
        matching_rate = make_rate(
            carrier=carrier, province="tehran", min_weight_g=1200, max_weight_g=5000
        )

        response = self.client.post(
            QUOTE_URL, {"province": "tehran", "city": "Tehran"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["options"]), 1)
        self.assertEqual(response.data["options"][0]["rate_id"], matching_rate.id)

    def test_guest_with_no_matching_rate_gets_empty_options_not_an_error(self):
        response = self.client.post(
            QUOTE_URL, {"province": "yazd", "city": "Yazd"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["options"], [])

    def test_guest_and_authenticated_requests_get_independent_carts(self):
        # A brand-new (unauthenticated, no pre-seeded session) request must
        # not somehow see the pre-seeded guest cart from setUp — each
        # anonymous session gets its own cart.
        carrier = make_carrier(code=ShippingCarrier.Code.POST)
        # Only a bracket matching THIS test's guest cart (1200g); a fresh
        # empty-cart session would compute weight_g=0 and miss it entirely.
        make_rate(
            carrier=carrier, province="tehran", min_weight_g=1000, max_weight_g=5000
        )

        fresh_client = APIClient()
        response = fresh_client.post(
            QUOTE_URL, {"province": "tehran", "city": "Tehran"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["options"], [])
