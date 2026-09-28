"""
Tests for SnapBoxCarrierProvider (Task 7.2.1.4).

Unlike test_post.py / test_tipax.py (whose carriers have no API, so those
tests just assert NotImplementedError), SnapBox has a real API, so these
follow Epic 6's gateway test structure: SimpleTestCase + the `responses`
library to mock HTTP (never a real network call) + override_settings.

Response fixtures below are the shapes shown in SnapBox's own OpenAPI
examples (see snapbox.py's module docstring for provenance and for the
points still needing a staging smoke test — notably the track() response
body, which the spec does not document).
"""

import json
from decimal import Decimal
from types import SimpleNamespace

import requests
import responses
from django.test import SimpleTestCase, override_settings
from shipping.providers import get_carrier_provider
from shipping.providers.snapbox import SnapBoxCarrierProvider

STAGING = SnapBoxCarrierProvider.STAGING_BASE_URL
PRODUCTION = SnapBoxCarrierProvider.PRODUCTION_BASE_URL
PRICING_URL = STAGING + SnapBoxCarrierProvider.PRICING_PATH
CREATE_URL = STAGING + SnapBoxCarrierProvider.CREATE_ORDER_PATH

PRICING_ID = "37ee6d99-c6f8-47bf-9248-eb305f7b4c09"
PRICING_OK = {
    "rateChartId": 1,
    "pricingConfigId": 1,
    "distanceCharged": 0,
    "terminalsCharged": 2,
    "timeFactor": 1,
    "totalFare": 70000,
    "pricingId": PRICING_ID,
}
CREATE_OK = {
    "status_code": 201,
    "data": {"orderId": 1422},
    "api_status": "success",
    "message": "Order created succesfully.",
    "key": "ORDER_CREATED",
}

SNAPBOX_SETTINGS = dict(
    SNAPBOX_API_KEY="test-token",
    SNAPBOX_SANDBOX=True,
    SNAPBOX_DEFAULT_DELIVERY_CATEGORY="bike",
    SNAPBOX_CUSTOMER_WALLET_TYPE="SNAPP_BOX",
    SNAPBOX_PICKUP_CITY="Tehran",
    SNAPBOX_PICKUP_ADDRESS="Jordan St, Tehran",
    SNAPBOX_PICKUP_LATITUDE="35.784869",
    SNAPBOX_PICKUP_LONGITUDE="51.376754",
    SNAPBOX_PICKUP_CONTACT_NAME="Chiz Store",
    SNAPBOX_PICKUP_CONTACT_PHONE="02112345678",
)

DESTINATION = {
    "latitude": 35.706674,
    "longitude": 51.364912,
    "city": "Tehran",
    "address": "Valiasr St, Tehran",
    "contact_name": "Ali Rezaei",
    "contact_phone": "09108986973",
}
# get_rate only needs coordinates (+ a city, here taken from the pickup).
COORDS_ONLY = {"latitude": 35.706674, "longitude": 51.364912}


class FakeItems:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


def make_order(items=None, **overrides):
    if items is None:
        items = [SimpleNamespace(product_name="Vitamin C Serum", quantity=2)]
    fields = dict(
        order_number="ORD-ABC123",
        first_name="Jane",
        last_name="Smith",
        phone="09121234567",
        shipping_address="42 Elm Street",
        shipping_city="Tehran",
        items=FakeItems(items),
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def request_json(call_index):
    return json.loads(responses.calls[call_index].request.body)


@override_settings(**SNAPBOX_SETTINGS)
class SnapBoxTestCase(SimpleTestCase):
    def setUp(self):
        self.provider = SnapBoxCarrierProvider()


class SnapBoxGetRateTests(SnapBoxTestCase):
    @responses.activate
    def test_successful_quote_returns_price_from_total_fare(self):
        responses.add(responses.POST, PRICING_URL, json=PRICING_OK)

        result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertTrue(result.success)
        self.assertEqual(result.price, Decimal("70000"))
        self.assertEqual(result.error_message, "")

    @responses.activate
    def test_request_uses_staging_host_raw_token_and_documented_payload(self):
        responses.add(responses.POST, PRICING_URL, json=PRICING_OK)

        self.provider.get_rate({}, COORDS_ONLY, 500)

        request = responses.calls[0].request
        self.assertTrue(request.url.startswith(STAGING))
        # Raw token, no "Bearer " prefix (matches the spec's example).
        self.assertEqual(request.headers["Authorization"], "test-token")
        body = request_json(0)
        self.assertEqual(body["city"], "tehran")
        self.assertEqual(body["deliveryCategory"], "bike")
        self.assertEqual(body["deliveryFarePaymentType"], "prepaid")
        self.assertEqual(body["customerWalletType"], "SNAPP_BOX")
        self.assertFalse(body["isReturn"])
        pickup, drop = body["terminals"]
        self.assertEqual((pickup["type"], pickup["sequenceNumber"]), ("pickup", 1))
        self.assertEqual((drop["type"], drop["sequenceNumber"]), ("drop", 2))
        # Empty origin fell back to the SNAPBOX_PICKUP_* settings.
        self.assertEqual(pickup["latitude"], 35.784869)
        self.assertEqual(pickup["longitude"], 51.376754)
        self.assertEqual(drop["latitude"], 35.706674)

    @responses.activate
    def test_weight_is_not_sent_because_snapbox_prices_by_route_not_weight(self):
        responses.add(responses.POST, PRICING_URL, json=PRICING_OK)
        responses.add(responses.POST, PRICING_URL, json=PRICING_OK)

        self.provider.get_rate({}, COORDS_ONLY, 100)
        self.provider.get_rate({}, COORDS_ONLY, 90_000)

        self.assertEqual(request_json(0), request_json(1))
        self.assertNotIn("weight", responses.calls[0].request.body.decode().lower())

    @responses.activate
    def test_production_host_is_used_when_sandbox_is_off(self):
        responses.add(
            responses.POST,
            PRODUCTION + SnapBoxCarrierProvider.PRICING_PATH,
            json=PRICING_OK,
        )

        with override_settings(SNAPBOX_SANDBOX=False):
            result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertTrue(result.success)
        self.assertTrue(responses.calls[0].request.url.startswith(PRODUCTION))

    @responses.activate
    def test_explicit_origin_overrides_configured_pickup(self):
        responses.add(responses.POST, PRICING_URL, json=PRICING_OK)
        origin = {"latitude": "35.70", "longitude": "51.40", "city": "Tehran"}

        result = self.provider.get_rate(origin, COORDS_ONLY, 500)

        self.assertTrue(result.success)
        # String coordinates are accepted and sent as numbers.
        self.assertEqual(request_json(0)["terminals"][0]["latitude"], 35.70)

    @responses.activate
    def test_persian_city_name_is_accepted(self):
        responses.add(responses.POST, PRICING_URL, json=PRICING_OK)
        destination = {**COORDS_ONLY, "city": "تهران"}

        result = self.provider.get_rate({}, destination, 500)

        self.assertTrue(result.success)
        self.assertEqual(request_json(0)["city"], "tehran")

    @responses.activate
    def test_missing_api_key_fails_without_any_network_call(self):
        with override_settings(SNAPBOX_API_KEY=""):
            result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertFalse(result.success)
        self.assertIn("SNAPBOX_API_KEY", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_missing_destination_coordinates_fails_without_network_call(self):
        # SnapBox addresses stops by lat/long; the system stores none, so a
        # street address alone must fail clearly rather than be guessed at.
        result = self.provider.get_rate(
            {}, {"address": "Valiasr St", "city": "Tehran"}, 500
        )

        self.assertFalse(result.success)
        self.assertIn("latitude/longitude", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_invalid_coordinates_are_rejected(self):
        bad_values = [
            {"latitude": "abc", "longitude": 51.0},
            {"latitude": 91, "longitude": 51.0},
            {"latitude": 35.0, "longitude": 181},
            {"latitude": float("nan"), "longitude": 51.0},
            {"latitude": None, "longitude": None},
        ]
        for destination in bad_values:
            with self.subTest(destination=destination):
                result = self.provider.get_rate({}, destination, 500)
                self.assertFalse(result.success)
                self.assertIn("latitude/longitude", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_unconfigured_pickup_with_no_origin_fails_without_network_call(self):
        with override_settings(SNAPBOX_PICKUP_LATITUDE="", SNAPBOX_PICKUP_LONGITUDE=""):
            result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertFalse(result.success)
        self.assertIn("pickup location", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_unsupported_city_fails_naming_the_city_and_supported_ones(self):
        destination = {**COORDS_ONLY, "city": "Shiraz"}

        result = self.provider.get_rate({}, destination, 500)

        self.assertFalse(result.success)
        self.assertIn("Shiraz", result.error_message)
        self.assertIn("Tehran", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_pickup_and_destination_in_different_cities_fails(self):
        destination = {**COORDS_ONLY, "city": "Mashhad"}

        result = self.provider.get_rate({}, destination, 500)

        self.assertFalse(result.success)
        self.assertIn("single city", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_no_city_anywhere_fails(self):
        with override_settings(SNAPBOX_PICKUP_CITY=""):
            result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertFalse(result.success)
        self.assertIn("city", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_invalid_delivery_category_setting_fails(self):
        with override_settings(SNAPBOX_DEFAULT_DELIVERY_CATEGORY="truck"):
            result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertFalse(result.success)
        self.assertIn("SNAPBOX_DEFAULT_DELIVERY_CATEGORY", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_api_error_response_returns_failure_with_message(self):
        responses.add(
            responses.POST,
            PRICING_URL,
            json={"message": "Unauthorized token"},
            status=401,
        )

        result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertFalse(result.success)
        self.assertIn("Unauthorized token", result.error_message)
        self.assertEqual(result.price, Decimal("0"))

    @responses.activate
    def test_error_without_message_falls_back_to_http_status(self):
        responses.add(responses.POST, PRICING_URL, json={}, status=500)

        result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertFalse(result.success)
        self.assertIn("HTTP 500", result.error_message)

    @responses.activate
    def test_connection_error_is_caught(self):
        responses.add(
            responses.POST,
            PRICING_URL,
            body=requests.exceptions.ConnectionError("connection refused"),
        )

        result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertFalse(result.success)
        self.assertIn("connection refused", result.error_message)

    @responses.activate
    def test_timeout_is_caught_and_request_uses_15_second_timeout(self):
        responses.add(
            responses.POST,
            PRICING_URL,
            body=requests.exceptions.Timeout("timed out"),
        )

        result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")
        self.assertEqual(SnapBoxCarrierProvider.REQUEST_TIMEOUT_SECONDS, 15)

    @responses.activate
    def test_non_json_response_is_caught(self):
        responses.add(responses.POST, PRICING_URL, body="<html>502</html>", status=502)

        result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    @responses.activate
    def test_response_without_total_fare_fails(self):
        responses.add(responses.POST, PRICING_URL, json={"pricingId": PRICING_ID})

        result = self.provider.get_rate({}, COORDS_ONLY, 500)

        self.assertFalse(result.success)

    @responses.activate
    def test_unparseable_or_negative_fare_fails(self):
        # Multiple responses registered for one URL are served in order.
        fares = ["not-a-number", -5]
        for fare in fares:
            responses.add(responses.POST, PRICING_URL, json={"totalFare": fare})

        for fare in fares:
            with self.subTest(fare=fare):
                result = self.provider.get_rate({}, COORDS_ONLY, 500)
                self.assertFalse(result.success)


class SnapBoxCreateShipmentTests(SnapBoxTestCase):
    def _register_success(self):
        responses.add(responses.POST, PRICING_URL, json=PRICING_OK)
        responses.add(responses.POST, CREATE_URL, json=CREATE_OK, status=201)

    @responses.activate
    def test_successful_booking_returns_order_id_as_tracking_number(self):
        self._register_success()

        result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertTrue(result.success)
        self.assertEqual(result.tracking_number, "1422")
        # On-demand courier: there is no printable label.
        self.assertEqual(result.label_url, "")
        self.assertEqual(result.error_message, "")

    @responses.activate
    def test_pricing_is_fetched_first_and_its_id_is_sent_with_the_order(self):
        self._register_success()

        self.provider.create_shipment(make_order(), DESTINATION)

        self.assertEqual(len(responses.calls), 2)
        self.assertTrue(responses.calls[0].request.url.endswith("/order/pricing"))
        self.assertTrue(responses.calls[1].request.url.endswith("/create_order"))
        details = request_json(1)["data"]["orderDetails"]
        self.assertEqual(details["pricingId"], PRICING_ID)

    @responses.activate
    def test_create_order_payload_matches_documented_shape(self):
        self._register_success()

        self.provider.create_shipment(make_order(), DESTINATION)

        data = request_json(1)["data"]
        details = data["orderDetails"]
        self.assertEqual(details["customerRefId"], "ORD-ABC123")
        self.assertEqual(details["city"], "tehran")
        self.assertEqual(details["deliveryCategory"], "bike")
        self.assertEqual(details["vehicleCategory"], "bike")
        self.assertEqual(details["deliveryFarePaymentType"], "prepaid")
        self.assertFalse(details["isReturn"])
        # "customer" in SnapBox terms is the merchant account, not the buyer.
        self.assertEqual(details["customerName"], "Chiz Store")
        # Fields deliberately omitted (see snapbox.py docstring, point e).
        self.assertNotIn("timeSlotDTO", data)
        self.assertNotIn("packageSize", details)

        (pickup,) = data["pickUpDetails"]
        self.assertEqual((pickup["type"], pickup["sequenceNumber"]), ("pickup", 1))
        self.assertEqual(pickup["contactName"], "Chiz Store")
        self.assertEqual(pickup["latitude"], 35.784869)
        self.assertEqual(pickup["paymentType"], "prepaid")
        self.assertEqual(pickup["cashOnPickup"], 0)
        self.assertEqual(pickup["cashOnDelivery"], 0)

        (drop,) = data["dropOffDetails"]
        self.assertEqual((drop["type"], drop["sequenceNumber"]), ("drop", 2))
        self.assertEqual(drop["contactName"], "Ali Rezaei")
        self.assertEqual(drop["contactPhoneNumber"], "09108986973")
        self.assertEqual(drop["address"], "Valiasr St, Tehran")
        self.assertEqual(drop["longitude"], 51.364912)

        (item,) = data["itemDetails"]
        self.assertEqual(item["name"], "Vitamin C Serum")
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(item["quantityMeasuringUnit"], "unit")
        self.assertEqual(item["pickedUpSequenceNumber"], 1)
        self.assertEqual(item["dropOffSequenceNumber"], 2)

    @responses.activate
    def test_address_city_and_contact_fall_back_to_the_order(self):
        self._register_success()

        result = self.provider.create_shipment(
            make_order(),
            {"latitude": 35.706674, "longitude": 51.364912},  # coords only
        )

        self.assertTrue(result.success)
        (drop,) = request_json(1)["data"]["dropOffDetails"]
        self.assertEqual(drop["address"], "42 Elm Street")
        self.assertEqual(drop["contactName"], "Jane Smith")
        self.assertEqual(drop["contactPhoneNumber"], "09121234567")

    @responses.activate
    def test_blank_destination_values_fall_back_but_explicit_ones_win(self):
        self._register_success()
        destination = {**DESTINATION, "contact_name": "", "address": "Explicit St"}

        self.provider.create_shipment(make_order(), destination)

        (drop,) = request_json(1)["data"]["dropOffDetails"]
        self.assertEqual(drop["contactName"], "Jane Smith")  # blank -> order
        self.assertEqual(drop["address"], "Explicit St")  # explicit wins

    @responses.activate
    def test_order_with_no_items_gets_a_single_generic_item(self):
        self._register_success()

        self.provider.create_shipment(make_order(items=[]), DESTINATION)

        (item,) = request_json(1)["data"]["itemDetails"]
        self.assertEqual(item["name"], "Order ORD-ABC123")
        self.assertEqual(item["quantity"], 1)

    @responses.activate
    def test_multiple_order_items_are_all_sent(self):
        self._register_success()
        items = [
            SimpleNamespace(product_name="Serum", quantity=1),
            SimpleNamespace(product_name="Toner", quantity=3),
        ]

        self.provider.create_shipment(make_order(items=items), DESTINATION)

        sent = request_json(1)["data"]["itemDetails"]
        self.assertEqual(
            [(i["name"], i["quantity"]) for i in sent],
            [("Serum", 1), ("Toner", 3)],
        )

    @responses.activate
    def test_missing_destination_coordinates_fails_without_network_call(self):
        result = self.provider.create_shipment(
            make_order(), {"address": "Valiasr St", "city": "Tehran"}
        )

        self.assertFalse(result.success)
        self.assertIn("latitude/longitude", result.error_message)
        self.assertEqual(result.tracking_number, "")
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_unconfigured_pickup_fails_pointing_at_the_settings(self):
        with override_settings(SNAPBOX_PICKUP_CONTACT_PHONE=""):
            result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)
        self.assertIn("SNAPBOX_PICKUP_", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_missing_order_number_fails_without_network_call(self):
        result = self.provider.create_shipment(make_order(order_number=""), DESTINATION)

        self.assertFalse(result.success)
        self.assertIn("order_number", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_unsupported_destination_city_fails(self):
        result = self.provider.create_shipment(
            make_order(), {**DESTINATION, "city": "Shiraz"}
        )

        self.assertFalse(result.success)
        self.assertIn("Shiraz", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_missing_api_key_fails_without_any_network_call(self):
        with override_settings(SNAPBOX_API_KEY=""):
            result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)
        self.assertIn("SNAPBOX_API_KEY", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_pricing_failure_stops_before_create_order_is_called(self):
        responses.add(
            responses.POST, PRICING_URL, json={"message": "no couriers"}, status=422
        )

        result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)
        self.assertIn("no couriers", result.error_message)
        self.assertEqual(len(responses.calls), 1)  # create_order never attempted

    @responses.activate
    def test_create_order_error_response_returns_failure_with_message(self):
        responses.add(responses.POST, PRICING_URL, json=PRICING_OK)
        responses.add(
            responses.POST,
            CREATE_URL,
            json={"message": "customerRefId already exists", "key": "DUPLICATE"},
            status=400,
        )

        result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)
        self.assertIn("customerRefId already exists", result.error_message)
        self.assertEqual(result.tracking_number, "")

    @responses.activate
    def test_created_response_without_order_id_is_treated_as_failure(self):
        responses.add(responses.POST, PRICING_URL, json=PRICING_OK)
        responses.add(
            responses.POST, CREATE_URL, json={"api_status": "success"}, status=201
        )

        result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)

    @responses.activate
    def test_connection_error_on_create_order_is_caught(self):
        responses.add(responses.POST, PRICING_URL, json=PRICING_OK)
        responses.add(
            responses.POST,
            CREATE_URL,
            body=requests.exceptions.ConnectionError("connection refused"),
        )

        result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)
        self.assertIn("connection refused", result.error_message)

    @responses.activate
    def test_timeout_on_pricing_step_is_caught(self):
        responses.add(
            responses.POST,
            PRICING_URL,
            body=requests.exceptions.Timeout("timed out"),
        )

        result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)
        self.assertEqual(len(responses.calls), 1)


class SnapBoxTrackTests(SnapBoxTestCase):
    @staticmethod
    def _details_url(order_id):
        return f"{STAGING}/v2/orders/{order_id}"

    @responses.activate
    def test_top_level_status_is_returned_with_description(self):
        responses.add(
            responses.GET, self._details_url("1422"), json={"status": "PICKED_UP"}
        )

        result = self.provider.track("1422")

        self.assertTrue(result.success)
        self.assertEqual(result.status, "PICKED_UP")
        self.assertEqual(result.status_description, "The package has been picked up")
        request = responses.calls[0].request
        self.assertEqual(request.headers["Authorization"], "test-token")

    @responses.activate
    def test_status_nested_under_data_is_also_understood(self):
        responses.add(
            responses.GET,
            self._details_url("1422"),
            json={"data": {"status": "DELIVERED"}},
        )

        result = self.provider.track("1422")

        self.assertTrue(result.success)
        self.assertEqual(result.status, "DELIVERED")

    @responses.activate
    def test_unknown_status_is_passed_through_with_empty_description(self):
        responses.add(
            responses.GET, self._details_url("7"), json={"status": "SOMETHING_NEW"}
        )

        result = self.provider.track("7")

        self.assertTrue(result.success)
        self.assertEqual(result.status, "SOMETHING_NEW")
        self.assertEqual(result.status_description, "")

    @responses.activate
    def test_response_without_a_status_is_an_explicit_failure(self):
        # The endpoint's response body is undocumented in the spec; an
        # unrecognized shape must fail loudly, not be guessed at.
        responses.add(responses.GET, self._details_url("1422"), json={"id": 1422})

        result = self.provider.track("1422")

        self.assertFalse(result.success)
        self.assertIn("undocumented", result.error_message)

    @responses.activate
    def test_non_numeric_tracking_numbers_are_rejected_without_a_request(self):
        # The value is interpolated into a URL path, so anything other than
        # plain ASCII digits must be refused (path-injection guard).
        bad_numbers = [
            "",
            "   ",
            None,
            "abc",
            "12 3",
            "../secrets",
            "1422/x",
            "1422?x=1",
            "١٢٣",
        ]
        for number in bad_numbers:
            with self.subTest(number=number):
                result = self.provider.track(number)
                self.assertFalse(result.success)
                self.assertIn("numeric", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_not_found_response_returns_failure_with_message(self):
        responses.add(
            responses.GET,
            self._details_url("999"),
            json={"message": "Order not found"},
            status=404,
        )

        result = self.provider.track("999")

        self.assertFalse(result.success)
        self.assertIn("Order not found", result.error_message)

    @responses.activate
    def test_connection_error_is_caught(self):
        responses.add(
            responses.GET,
            self._details_url("1422"),
            body=requests.exceptions.ConnectionError("connection refused"),
        )

        result = self.provider.track("1422")

        self.assertFalse(result.success)
        self.assertIn("connection refused", result.error_message)

    @responses.activate
    def test_timeout_is_caught(self):
        responses.add(
            responses.GET,
            self._details_url("1422"),
            body=requests.exceptions.Timeout("timed out"),
        )

        result = self.provider.track("1422")

        self.assertFalse(result.success)

    @responses.activate
    def test_non_json_response_is_caught(self):
        responses.add(
            responses.GET, self._details_url("1422"), body="<html>", status=502
        )

        result = self.provider.track("1422")

        self.assertFalse(result.success)

    @responses.activate
    def test_missing_api_key_fails_without_any_network_call(self):
        with override_settings(SNAPBOX_API_KEY=""):
            result = self.provider.track("1422")

        self.assertFalse(result.success)
        self.assertIn("SNAPBOX_API_KEY", result.error_message)
        self.assertEqual(len(responses.calls), 0)


class SnapBoxRegisteredInFactoryTests(SimpleTestCase):
    def test_get_carrier_provider_snapbox_returns_snapbox_carrier_provider(self):
        provider = get_carrier_provider("snapbox")

        self.assertIsInstance(provider, SnapBoxCarrierProvider)
