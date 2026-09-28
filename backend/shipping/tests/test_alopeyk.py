"""
Tests for AloPeykCarrierProvider (Task 7.2.1.5).

Mirrors test_snapbox.py's structure: SimpleTestCase + `responses` to mock
HTTP (never a real network call) + override_settings. Response fixtures
below are the shapes shown in AloPeyk's own official SDK documentation and
source code (see alopeyk.py's module docstring for provenance).
"""

import json
from decimal import Decimal
from types import SimpleNamespace

import requests
import responses
from django.test import SimpleTestCase, override_settings
from shipping.providers import get_carrier_provider
from shipping.providers.alopeyk import AloPeykCarrierProvider

BASE_URL = "https://api.alopeyk.com"
PRICE_URL = f"{BASE_URL}/orders/price/calc"
CREATE_URL = f"{BASE_URL}/orders"

PRICE_OK = {
    "status": "success",
    "message": None,
    "object": {
        "price": 31500,
        "distance": 22533,
        "duration": 2780,
        "status": "OK",
        "city": "tehran",
        "transport_type": "motor_taxi",
        "has_return": False,
    },
}
CREATE_OK = {
    "status": "success",
    "message": None,
    "object": {
        "id": 300,
        "invoice_number": "LKH3LN",
        "status": "new",
        "order_token": "099c68a4a300ga2165445145a8eg992375433db",
        "transport_type": "motor_taxi",
        "city": "tehran",
    },
}

ALOPEYK_SETTINGS = dict(
    ALOPEYK_API_KEY="test-token",
    ALOPEYK_API_BASE_URL=BASE_URL,
    ALOPEYK_DEFAULT_TRANSPORT_TYPE="motor_taxi",
    ALOPEYK_PICKUP_CITY="Tehran",
    ALOPEYK_PICKUP_LATITUDE="35.723711",
    ALOPEYK_PICKUP_LONGITUDE="51.410547",
    ALOPEYK_PICKUP_CONTACT_NAME="Chiz Store",
    ALOPEYK_PICKUP_CONTACT_PHONE="02112345678",
)

DESTINATION = {
    "latitude": 35.728457,
    "longitude": 51.436969,
    "city": "Tehran",
    "province": "tehran",
    "address": "N Sohrevardi Ave",
    "contact_name": "Ali Rezaei",
    "contact_phone": "09108986973",
}
# get_rate only needs coordinates + city/province (the latter for the
# availability check; neither is sent to AloPeyk itself).
COORDS_ONLY = {"latitude": 35.728457, "longitude": 51.436969, "city": "Tehran"}


def make_order(**overrides):
    fields = dict(
        order_number="ORD-ABC123",
        first_name="Jane",
        last_name="Smith",
        phone="09121234567",
        shipping_address="42 Elm Street",
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def request_json(call_index):
    return json.loads(responses.calls[call_index].request.body)


@override_settings(**ALOPEYK_SETTINGS)
class AloPeykTestCase(SimpleTestCase):
    def setUp(self):
        self.provider = AloPeykCarrierProvider()


class AloPeykServiceAreaTests(AloPeykTestCase):
    """Acceptance criterion 1: is_available_for_city()."""

    def test_returns_true_for_known_served_city(self):
        self.assertTrue(self.provider.is_available_for_city("Tehran", "tehran"))
        self.assertTrue(self.provider.is_available_for_city("karaj", "alborz"))
        self.assertTrue(
            self.provider.is_available_for_city("Mashhad", "khorasan_razavi")
        )
        self.assertTrue(self.provider.is_available_for_city("shiraz", "fars"))

    def test_returns_false_for_a_city_not_served(self):
        # Isfahan is notably NOT served, despite being a common assumption
        # (see module docstring, point 2) — a good case to lock in
        # explicitly rather than just testing an obviously-unserved city.
        self.assertFalse(self.provider.is_available_for_city("Isfahan", "isfahan"))
        self.assertFalse(self.provider.is_available_for_city("Yazd", "yazd"))

    def test_persian_city_names_are_recognized(self):
        self.assertTrue(self.provider.is_available_for_city("تهران", "tehran"))
        self.assertTrue(self.provider.is_available_for_city("شیراز", "fars"))
        self.assertFalse(self.provider.is_available_for_city("اصفهان", "isfahan"))

    def test_case_insensitive(self):
        self.assertTrue(self.provider.is_available_for_city("TEHRAN", "tehran"))
        self.assertTrue(self.provider.is_available_for_city("KaRaJ", "alborz"))

    def test_mismatched_province_for_a_served_city_returns_false(self):
        # Defensive cross-check: "Tehran" the city with "fars" the province
        # is an inconsistent combination and must not be trusted.
        self.assertFalse(self.provider.is_available_for_city("Tehran", "fars"))

    def test_blank_province_skips_the_cross_check(self):
        self.assertTrue(self.provider.is_available_for_city("Tehran", ""))

    def test_blank_or_unknown_city_returns_false(self):
        self.assertFalse(self.provider.is_available_for_city("", ""))
        self.assertFalse(self.provider.is_available_for_city("Atlantis", ""))


class AloPeykGetRateTests(AloPeykTestCase):
    @responses.activate
    def test_successful_quote_returns_price(self):
        responses.add(responses.POST, PRICE_URL, json=PRICE_OK)

        result = self.provider.get_rate({}, DESTINATION, 500)

        self.assertTrue(result.success)
        self.assertEqual(result.price, Decimal("31500"))
        self.assertEqual(result.error_message, "")

    @responses.activate
    def test_unavailable_city_fails_without_any_api_call(self):
        # Acceptance criterion 2: unserved city -> success=False with the
        # exact message, and NO network call attempted at all.
        destination = {**DESTINATION, "city": "Isfahan", "province": "isfahan"}

        result = self.provider.get_rate({}, destination, 500)

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "AloPeyk is not available in this city.")
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_request_uses_bearer_token_and_documented_payload_shape(self):
        responses.add(responses.POST, PRICE_URL, json=PRICE_OK)

        self.provider.get_rate({}, DESTINATION, 500)

        request = responses.calls[0].request
        self.assertEqual(request.headers["Authorization"], "Bearer test-token")
        body = request_json(0)
        self.assertEqual(body["transport_type"], "motor_taxi")
        self.assertFalse(body["has_return"])
        origin_addr, dest_addr = body["addresses"]
        self.assertEqual(origin_addr["type"], "origin")
        self.assertEqual(dest_addr["type"], "destination")
        self.assertEqual(dest_addr["lat"], 35.728457)
        self.assertEqual(dest_addr["lng"], 51.436969)
        # Empty origin fell back to the ALOPEYK_PICKUP_* settings.
        self.assertEqual(origin_addr["lat"], 35.723711)
        # city/province are pre-check-only, never sent to AloPeyk.
        self.assertNotIn("city", dest_addr)
        self.assertNotIn("province", dest_addr)

    @responses.activate
    def test_weight_is_not_sent_because_alopeyk_prices_by_distance_not_weight(self):
        responses.add(responses.POST, PRICE_URL, json=PRICE_OK)
        responses.add(responses.POST, PRICE_URL, json=PRICE_OK)

        self.provider.get_rate({}, DESTINATION, 100)
        self.provider.get_rate({}, DESTINATION, 90_000)

        self.assertEqual(request_json(0), request_json(1))
        self.assertNotIn("weight", responses.calls[0].request.body.decode().lower())

    @responses.activate
    def test_missing_api_key_fails_without_any_network_call(self):
        with override_settings(ALOPEYK_API_KEY=""):
            result = self.provider.get_rate({}, DESTINATION, 500)

        self.assertFalse(result.success)
        self.assertIn("ALOPEYK_API_KEY", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_missing_destination_coordinates_fails_without_network_call(self):
        result = self.provider.get_rate(
            {}, {"city": "Tehran", "province": "tehran"}, 500
        )

        self.assertFalse(result.success)
        self.assertIn("latitude/longitude", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_invalid_coordinates_are_rejected(self):
        bad = {"city": "Tehran", "province": "tehran", "latitude": 91, "longitude": 51}

        result = self.provider.get_rate({}, bad, 500)

        self.assertFalse(result.success)
        self.assertIn("latitude/longitude", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_unconfigured_pickup_with_no_origin_fails_without_network_call(self):
        with override_settings(ALOPEYK_PICKUP_LATITUDE="", ALOPEYK_PICKUP_LONGITUDE=""):
            result = self.provider.get_rate({}, DESTINATION, 500)

        self.assertFalse(result.success)
        self.assertIn("pickup location", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_api_failure_envelope_returns_message_like_the_official_sdk(self):
        # Mirrors AloPeykApiHandler::getApiResponse()'s own error extraction:
        # {"status": "fail", "message": "..."}.
        responses.add(
            responses.POST,
            PRICE_URL,
            json={"status": "fail", "message": "Invalid ACCESS-TOKEN"},
        )

        result = self.provider.get_rate({}, DESTINATION, 500)

        self.assertFalse(result.success)
        self.assertIn("Invalid ACCESS-TOKEN", result.error_message)

    @responses.activate
    def test_api_failure_with_nested_object_error_msg_is_extracted(self):
        responses.add(
            responses.POST,
            PRICE_URL,
            json={
                "status": "fail",
                "message": None,
                "object": {"error_msg": "Destination out of range"},
            },
        )

        result = self.provider.get_rate({}, DESTINATION, 500)

        self.assertFalse(result.success)
        self.assertIn("Destination out of range", result.error_message)

    @responses.activate
    def test_connection_error_is_caught(self):
        responses.add(
            responses.POST,
            PRICE_URL,
            body=requests.exceptions.ConnectionError("connection refused"),
        )

        result = self.provider.get_rate({}, DESTINATION, 500)

        self.assertFalse(result.success)
        self.assertIn("connection refused", result.error_message)

    @responses.activate
    def test_timeout_is_caught_and_request_uses_15_second_timeout(self):
        responses.add(
            responses.POST, PRICE_URL, body=requests.exceptions.Timeout("timed out")
        )

        result = self.provider.get_rate({}, DESTINATION, 500)

        self.assertFalse(result.success)
        self.assertEqual(AloPeykCarrierProvider.REQUEST_TIMEOUT_SECONDS, 15)

    @responses.activate
    def test_non_json_response_is_caught(self):
        responses.add(responses.POST, PRICE_URL, body="<html>502</html>", status=502)

        result = self.provider.get_rate({}, DESTINATION, 500)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    @responses.activate
    def test_unparseable_or_negative_price_fails(self):
        for price in ("not-a-number", -5):
            responses.add(
                responses.POST,
                PRICE_URL,
                json={"status": "success", "object": {"price": price}},
            )

        for _ in range(2):
            result = self.provider.get_rate({}, DESTINATION, 500)
            self.assertFalse(result.success)


class AloPeykCreateShipmentTests(AloPeykTestCase):
    @responses.activate
    def test_successful_booking_returns_order_id_as_tracking_number(self):
        responses.add(responses.POST, CREATE_URL, json=CREATE_OK)

        result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertTrue(result.success)
        self.assertEqual(result.tracking_number, "300")
        self.assertEqual(result.label_url, "")  # on-demand courier, no label
        self.assertEqual(result.error_message, "")

    @responses.activate
    def test_unavailable_city_fails_without_any_api_call(self):
        destination = {**DESTINATION, "city": "Isfahan", "province": "isfahan"}

        result = self.provider.create_shipment(make_order(), destination)

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "AloPeyk is not available in this city.")
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_create_order_payload_matches_documented_shape(self):
        responses.add(responses.POST, CREATE_URL, json=CREATE_OK)

        self.provider.create_shipment(make_order(), DESTINATION)

        body = request_json(0)
        self.assertEqual(body["transport_type"], "motor_taxi")
        self.assertFalse(body["has_return"])
        origin_addr, dest_addr = body["addresses"]
        self.assertEqual(origin_addr["person_fullname"], "Chiz Store")
        self.assertEqual(origin_addr["person_phone"], "02112345678")
        self.assertEqual(dest_addr["person_fullname"], "Ali Rezaei")
        self.assertEqual(dest_addr["person_phone"], "09108986973")
        self.assertEqual(dest_addr["description"], "N Sohrevardi Ave")

    @responses.activate
    def test_address_and_contact_fall_back_to_the_order(self):
        responses.add(responses.POST, CREATE_URL, json=CREATE_OK)
        destination = {  # coords + city/province only, no contact fields
            "latitude": 35.728457,
            "longitude": 51.436969,
            "city": "Tehran",
            "province": "tehran",
        }

        result = self.provider.create_shipment(make_order(), destination)

        self.assertTrue(result.success)
        _, dest_addr = request_json(0)["addresses"]
        self.assertEqual(dest_addr["description"], "42 Elm Street")
        self.assertEqual(dest_addr["person_fullname"], "Jane Smith")
        self.assertEqual(dest_addr["person_phone"], "09121234567")

    @responses.activate
    def test_missing_destination_coordinates_fails_without_network_call(self):
        result = self.provider.create_shipment(
            make_order(), {"city": "Tehran", "province": "tehran"}
        )

        self.assertFalse(result.success)
        self.assertIn("latitude/longitude", result.error_message)
        self.assertEqual(result.tracking_number, "")
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_unconfigured_pickup_fails_pointing_at_the_settings(self):
        with override_settings(ALOPEYK_PICKUP_CONTACT_PHONE=""):
            result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)
        self.assertIn("ALOPEYK_PICKUP_", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_missing_api_key_fails_without_any_network_call(self):
        with override_settings(ALOPEYK_API_KEY=""):
            result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)
        self.assertIn("ALOPEYK_API_KEY", result.error_message)
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_api_error_response_returns_failure_with_message(self):
        responses.add(
            responses.POST,
            CREATE_URL,
            json={"status": "fail", "message": "Insufficient credit"},
        )

        result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)
        self.assertIn("Insufficient credit", result.error_message)
        self.assertEqual(result.tracking_number, "")

    @responses.activate
    def test_response_without_order_id_is_treated_as_failure(self):
        responses.add(
            responses.POST,
            CREATE_URL,
            json={"status": "success", "object": {"invoice_number": "X"}},
        )

        result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)

    @responses.activate
    def test_connection_error_is_caught(self):
        responses.add(
            responses.POST,
            CREATE_URL,
            body=requests.exceptions.ConnectionError("connection refused"),
        )

        result = self.provider.create_shipment(make_order(), DESTINATION)

        self.assertFalse(result.success)
        self.assertIn("connection refused", result.error_message)


class AloPeykTrackTests(AloPeykTestCase):
    @staticmethod
    def _detail_url(order_id):
        return f"{BASE_URL}/orders/{order_id}"

    @responses.activate
    def test_confirmed_status_is_returned_with_description(self):
        responses.add(
            responses.GET,
            self._detail_url("300"),
            json={"status": "success", "object": {"id": 300, "status": "delivered"}},
        )

        result = self.provider.track("300")

        self.assertTrue(result.success)
        self.assertEqual(result.status, "delivered")
        self.assertEqual(result.status_description, "The package has been delivered")
        request = responses.calls[0].request
        self.assertEqual(request.headers["Authorization"], "Bearer test-token")

    @responses.activate
    def test_new_status_immediately_after_creation_is_understood(self):
        responses.add(
            responses.GET,
            self._detail_url("300"),
            json={"status": "success", "object": {"id": 300, "status": "new"}},
        )

        result = self.provider.track("300")

        self.assertTrue(result.success)
        self.assertEqual(result.status, "new")

    @responses.activate
    def test_unknown_status_is_passed_through_with_empty_description(self):
        responses.add(
            responses.GET,
            self._detail_url("7"),
            json={
                "status": "success",
                "object": {"id": 7, "status": "some_new_state"},
            },
        )

        result = self.provider.track("7")

        self.assertTrue(result.success)
        self.assertEqual(result.status, "some_new_state")
        self.assertEqual(result.status_description, "")

    @responses.activate
    def test_response_without_a_status_is_an_explicit_failure(self):
        responses.add(
            responses.GET,
            self._detail_url("300"),
            json={"status": "success", "object": {"id": 300}},
        )

        result = self.provider.track("300")

        self.assertFalse(result.success)

    @responses.activate
    def test_non_numeric_tracking_numbers_are_rejected_without_a_request(self):
        # "300" with surrounding whitespace is fine (stripped); anything
        # genuinely non-numeric must be rejected before any request.
        bad_numbers = ["", "   ", None, "abc", "../secrets", "300/x", "١٢٣"]
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
            self._detail_url("999"),
            json={"status": "fail", "message": "Order not found"},
        )

        result = self.provider.track("999")

        self.assertFalse(result.success)
        self.assertIn("Order not found", result.error_message)

    @responses.activate
    def test_connection_error_is_caught(self):
        responses.add(
            responses.GET,
            self._detail_url("300"),
            body=requests.exceptions.ConnectionError("connection refused"),
        )

        result = self.provider.track("300")

        self.assertFalse(result.success)
        self.assertIn("connection refused", result.error_message)

    @responses.activate
    def test_non_json_response_is_caught(self):
        responses.add(responses.GET, self._detail_url("300"), body="<html>", status=502)

        result = self.provider.track("300")

        self.assertFalse(result.success)

    @responses.activate
    def test_missing_api_key_fails_without_any_network_call(self):
        with override_settings(ALOPEYK_API_KEY=""):
            result = self.provider.track("300")

        self.assertFalse(result.success)
        self.assertIn("ALOPEYK_API_KEY", result.error_message)
        self.assertEqual(len(responses.calls), 0)


class AloPeykRegisteredInFactoryTests(SimpleTestCase):
    def test_get_carrier_provider_alopeyk_returns_alopeyk_carrier_provider(self):
        provider = get_carrier_provider("alopeyk")

        self.assertIsInstance(provider, AloPeykCarrierProvider)
