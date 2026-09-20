from decimal import Decimal
from unittest.mock import patch

import requests
import responses
from django.test import RequestFactory, SimpleTestCase
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


class ZarinPalVerifyPaymentTests(SimpleTestCase):
    def setUp(self):
        self.gateway = ZarinPalGateway()
        self.amount = Decimal("150000")
        self.authority = "A00000000000000000000000000000000wOGYpd"

    @responses.activate
    def test_successful_verification_returns_ref_id(self):
        responses.add(
            responses.POST,
            ZarinPalGateway.VERIFY_URL,
            json={
                "data": {
                    "code": 100,
                    "message": "Verified",
                    "card_hash": "...",
                    "card_pan": "502229******5995",
                    "ref_id": 201202070,
                    "fee_type": "Merchant",
                    "fee": 100,
                },
                "errors": [],
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
        # Code 101 ("already verified") happens when the customer
        # double-hits the callback URL (back-button/refresh) for an
        # authority that was already confirmed on a previous verify
        # call — this must be treated as success, not failure.
        responses.add(
            responses.POST,
            ZarinPalGateway.VERIFY_URL,
            json={
                "data": {
                    "code": 101,
                    "message": "Verified before",
                    "ref_id": 201202070,
                },
                "errors": [],
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
            ZarinPalGateway.VERIFY_URL,
            json={
                "data": [],
                "errors": {
                    "code": -21,
                    "message": "Transaction not found or unsuccessful.",
                    "validations": [],
                },
            },
            status=200,
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")
        self.assertIn("Transaction not found", result.error_message)
        self.assertEqual(result.ref_id, "")

    @responses.activate
    def test_connection_error_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            ZarinPalGateway.VERIFY_URL,
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
            ZarinPalGateway.VERIFY_URL,
            body=requests.exceptions.Timeout("request timed out"),
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    @responses.activate
    def test_malformed_non_json_body_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            ZarinPalGateway.VERIFY_URL,
            body="<html>not json at all</html>",
            status=200,
            content_type="text/html",
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    def test_amount_and_timeout_are_passed_on_outbound_call(self):
        with patch("payments.gateways.zarinpal.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {
                "data": {"code": 100, "ref_id": 1, "message": "Verified"},
                "errors": [],
            }

            self.gateway.verify_payment(self.authority, self.amount)

            mock_post.assert_called_once()
            call_args, call_kwargs = mock_post.call_args
            self.assertIn("timeout", call_kwargs)
            self.assertEqual(
                call_kwargs["timeout"], ZarinPalGateway.REQUEST_TIMEOUT_SECONDS
            )
            # The exact same amount (and unit) used for request_payment()
            # must be sent to verify_payment() — a mismatch is itself
            # grounds for ZarinPal to reject the verification.
            sent_payload = call_kwargs["json"]
            self.assertEqual(sent_payload["amount"], int(self.amount))
            self.assertEqual(sent_payload["authority"], self.authority)


class ZarinPalExtractCallbackParamsTests(SimpleTestCase):
    """
    Task 6.3.1.4: confirms ZarinPalGateway.extract_callback_params()
    reproduces exactly what PaymentCallbackView used to do inline before
    this refactor (Task 6.2.1.4/6.2.1.5) — a regression test proving the
    view's overall behavior for ZarinPal callbacks is byte-identical to
    before this task.
    """

    def setUp(self):
        self.gateway = ZarinPalGateway()
        self.factory = RequestFactory()

    def test_extracts_authority_and_ok_status(self):
        request = self.factory.get(
            "/api/payments/callback/zarinpal/",
            {"Authority": "A00000000000000000000000000000000wOGYpd", "Status": "OK"},
        )

        params = self.gateway.extract_callback_params(request)

        self.assertEqual(params["authority"], "A00000000000000000000000000000000wOGYpd")
        self.assertFalse(params["is_customer_cancelled"])

    def test_nok_status_is_customer_cancelled(self):
        request = self.factory.get(
            "/api/payments/callback/zarinpal/",
            {"Authority": "A00000000000000000000000000000000wOGYpd", "Status": "NOK"},
        )

        params = self.gateway.extract_callback_params(request)

        self.assertTrue(params["is_customer_cancelled"])

    def test_lowercase_param_names_also_accepted(self):
        request = self.factory.get(
            "/api/payments/callback/zarinpal/",
            {"authority": "lowercase-authority", "status": "OK"},
        )

        params = self.gateway.extract_callback_params(request)

        self.assertEqual(params["authority"], "lowercase-authority")
        self.assertFalse(params["is_customer_cancelled"])
