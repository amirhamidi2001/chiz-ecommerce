from decimal import Decimal
from unittest.mock import patch

import requests
import responses
from django.test import RequestFactory, SimpleTestCase
from payments.gateways.zibal import ZibalGateway


class ZibalRequestPaymentTests(SimpleTestCase):
    def setUp(self):
        self.gateway = ZibalGateway()
        self.amount = Decimal("150000")
        self.callback_url = "https://example.test/payments/callback/"

    @responses.activate
    def test_successful_response_returns_authority_and_redirect_url(self):
        responses.add(
            responses.POST,
            ZibalGateway.REQUEST_URL,
            json={
                "trackId": 1533727744287,
                "result": 100,
                "message": "success",
            },
            status=200,
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertTrue(result.success)
        self.assertEqual(result.authority, "1533727744287")
        self.assertEqual(
            result.redirect_url,
            ZibalGateway.START_PAY_URL.format(track_id="1533727744287"),
        )
        self.assertIn(result.authority, result.redirect_url)
        self.assertEqual(result.error_message, "")

    @responses.activate
    def test_gateway_error_response_returns_failure_with_message(self):
        responses.add(
            responses.POST,
            ZibalGateway.REQUEST_URL,
            json={
                "result": 105,
                "message": "amount must be greater than 1000",
            },
            status=200,
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")
        self.assertIn("amount must be greater than 1000", result.error_message)
        self.assertEqual(result.authority, "")
        self.assertEqual(result.redirect_url, "")

    @responses.activate
    def test_connection_error_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            ZibalGateway.REQUEST_URL,
            body=requests.exceptions.ConnectionError("connection refused"),
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    @responses.activate
    def test_timeout_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            ZibalGateway.REQUEST_URL,
            body=requests.exceptions.Timeout("request timed out"),
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    @responses.activate
    def test_malformed_non_json_body_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            ZibalGateway.REQUEST_URL,
            body="<html>not json at all</html>",
            status=200,
            content_type="text/html",
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    def test_amount_and_timeout_are_passed_on_outbound_call(self):
        with patch("payments.gateways.zibal.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {
                "trackId": 123,
                "result": 100,
                "message": "success",
            }

            self.gateway.request_payment(self.amount, self.callback_url)

            mock_post.assert_called_once()
            _, call_kwargs = mock_post.call_args
            self.assertIn("timeout", call_kwargs)
            self.assertEqual(
                call_kwargs["timeout"], ZibalGateway.REQUEST_TIMEOUT_SECONDS
            )
            sent_payload = call_kwargs["json"]
            self.assertEqual(sent_payload["amount"], int(self.amount))
            self.assertEqual(sent_payload["callbackUrl"], self.callback_url)


class ZibalVerifyPaymentTests(SimpleTestCase):
    def setUp(self):
        self.gateway = ZibalGateway()
        self.amount = Decimal("150000")
        self.authority = "1533727744287"

    @responses.activate
    def test_successful_verification_returns_ref_id(self):
        responses.add(
            responses.POST,
            ZibalGateway.VERIFY_URL,
            json={
                "paidAt": "2018-03-25T23:43:01.053000",
                "cardNumber": "610433******9414",
                "status": 1,
                "amount": 150000,
                "refNumber": 201202070,
                "description": "Order payment",
                "orderId": "",
                "result": 100,
                "message": "success",
            },
            status=200,
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertTrue(result.success)
        self.assertEqual(result.ref_id, "201202070")
        self.assertEqual(result.error_message, "")
        self.assertIsNotNone(result.raw_response)

    @responses.activate
    def test_already_verified_response_also_returns_success(self):
        # result=201 ("processed before") happens when the customer
        # double-hits the callback URL (back-button/refresh) for a
        # trackId that was already confirmed on a previous verify call —
        # this must be treated as success, not failure. Zibal's
        # equivalent of ZarinPal's code 101.
        responses.add(
            responses.POST,
            ZibalGateway.VERIFY_URL,
            json={
                "result": 201,
                "message": "processed before",
                "refNumber": 201202070,
                "amount": 150000,
            },
            status=200,
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertTrue(result.success)
        self.assertEqual(result.ref_id, "201202070")

    @responses.activate
    def test_failed_verification_returns_failure_with_message(self):
        responses.add(
            responses.POST,
            ZibalGateway.VERIFY_URL,
            json={
                "result": 202,
                "message": "payment failed",
                "status": -2,
            },
            status=200,
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")
        self.assertIn("payment failed", result.error_message)
        self.assertEqual(result.ref_id, "")

    @responses.activate
    def test_connection_error_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            ZibalGateway.VERIFY_URL,
            body=requests.exceptions.ConnectionError("connection refused"),
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")
        self.assertIsNone(result.raw_response)

    @responses.activate
    def test_timeout_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            ZibalGateway.VERIFY_URL,
            body=requests.exceptions.Timeout("request timed out"),
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    @responses.activate
    def test_malformed_non_json_body_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            ZibalGateway.VERIFY_URL,
            body="<html>not json at all</html>",
            status=200,
            content_type="text/html",
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    def test_trackid_and_timeout_are_passed_on_outbound_call(self):
        with patch("payments.gateways.zibal.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {
                "result": 100,
                "refNumber": 1,
                "message": "success",
            }

            self.gateway.verify_payment(self.authority, self.amount)

            mock_post.assert_called_once()
            _, call_kwargs = mock_post.call_args
            self.assertIn("timeout", call_kwargs)
            self.assertEqual(
                call_kwargs["timeout"], ZibalGateway.REQUEST_TIMEOUT_SECONDS
            )
            # Unlike ZarinPal, Zibal's documented verify payload is just
            # {"merchant", "trackId"} — no amount field (amount-matching
            # against the gateway's own reported amount is a caller-side
            # concern in Zibal's API, not part of the verify request
            # itself) — confirmed against the docs cited in
            # gateways/zibal.py's module docstring.
            sent_payload = call_kwargs["json"]
            self.assertEqual(sent_payload["trackId"], self.authority)
            self.assertNotIn("amount", sent_payload)


class ZibalExtractCallbackParamsTests(SimpleTestCase):
    """
    Task 6.3.1.4: confirms ZibalGateway.extract_callback_params() parses
    Zibal's actual documented callback shape — confirmed against Zibal's
    own official npm package README:
    ``?trackId=10000&success=1&status=2&orderId=1``, genuinely different
    field names from ZarinPal's Authority/Status.
    """

    def setUp(self):
        self.gateway = ZibalGateway()
        self.factory = RequestFactory()

    def test_extracts_trackid_as_authority_when_success_is_1(self):
        request = self.factory.get(
            "/api/payments/callback/zibal/",
            {"trackId": "1533727744287", "success": "1", "status": "2", "orderId": "1"},
        )

        params = self.gateway.extract_callback_params(request)

        self.assertEqual(params["authority"], "1533727744287")
        self.assertFalse(params["is_customer_cancelled"])

    def test_success_0_is_customer_cancelled(self):
        request = self.factory.get(
            "/api/payments/callback/zibal/",
            {"trackId": "1533727744287", "success": "0", "status": "1", "orderId": "1"},
        )

        params = self.gateway.extract_callback_params(request)

        self.assertTrue(params["is_customer_cancelled"])

    def test_missing_success_param_treated_as_cancelled(self):
        # Absent `success` (e.g. a malformed/truncated redirect) must
        # fail toward "treat as cancelled, don't silently proceed to
        # verify" rather than assuming success.
        request = self.factory.get(
            "/api/payments/callback/zibal/", {"trackId": "1533727744287"}
        )

        params = self.gateway.extract_callback_params(request)

        self.assertTrue(params["is_customer_cancelled"])
