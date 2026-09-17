from decimal import Decimal
from unittest.mock import patch

import requests
import responses
from django.test import SimpleTestCase

from payments.gateways.zarinpal import ZarinPalGateway


class ZarinPalRequestPaymentTests(SimpleTestCase):
    def setUp(self):
        self.gateway = ZarinPalGateway()
        self.amount = Decimal("150000")
        self.callback_url = "https://example.test/payments/callback/"

    @responses.activate
    def test_successful_response_returns_authority_and_redirect_url(self):
        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            json={
                "data": {
                    "code": 100,
                    "message": "Success",
                    "authority": "A00000000000000000000000000000000wOGYpd",
                    "fee_type": "Merchant",
                    "fee": 100,
                },
                "errors": [],
            },
            status=200,
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertTrue(result.success)
        self.assertEqual(result.authority, "A00000000000000000000000000000000wOGYpd")
        self.assertEqual(
            result.redirect_url,
            ZarinPalGateway.START_PAY_URL.format(
                authority="A00000000000000000000000000000000wOGYpd"
            ),
        )
        self.assertIn(result.authority, result.redirect_url)
        self.assertEqual(result.error_message, "")

    @responses.activate
    def test_gateway_error_response_returns_failure_with_message(self):
        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            json={
                "data": [],
                "errors": {
                    "code": -9,
                    "message": "amount is required and must be a positive number",
                    "validations": [],
                },
            },
            status=200,
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")
        self.assertIn("amount is required", result.error_message)
        self.assertEqual(result.authority, "")
        self.assertEqual(result.redirect_url, "")

    @responses.activate
    def test_connection_error_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            body=requests.exceptions.ConnectionError("connection refused"),
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    @responses.activate
    def test_timeout_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            body=requests.exceptions.Timeout("request timed out"),
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    @responses.activate
    def test_malformed_non_json_body_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            body="<html>not json at all</html>",
            status=200,
            content_type="text/html",
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    def test_timeout_parameter_is_passed_on_outbound_call(self):
        with patch("payments.gateways.zarinpal.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {
                "data": {"code": 100, "authority": "A123", "message": "Success"},
                "errors": [],
            }

            self.gateway.request_payment(self.amount, self.callback_url)

            mock_post.assert_called_once()
            _, call_kwargs = mock_post.call_args
            self.assertIn("timeout", call_kwargs)
            self.assertEqual(
                call_kwargs["timeout"], ZarinPalGateway.REQUEST_TIMEOUT_SECONDS
            )
