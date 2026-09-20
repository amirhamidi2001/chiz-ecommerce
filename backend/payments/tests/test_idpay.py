from decimal import Decimal
from unittest.mock import patch

import requests
import responses
from django.test import RequestFactory, SimpleTestCase
from payments.gateways.idpay import IDPayGateway


class IDPayRequestPaymentTests(SimpleTestCase):
    def setUp(self):
        self.gateway = IDPayGateway()
        self.amount = Decimal("150000")
        self.callback_url = "https://example.test/payments/callback/"

    @responses.activate
    def test_successful_response_returns_authority_and_redirect_url(self):
        responses.add(
            responses.POST,
            IDPayGateway.REQUEST_URL,
            json={
                "id": "d2e353189823079e1e4181772cff5292",
                "link": "https://idpay.ir/p/ws-sandbox/d2e353189823079e1e4181772cff5292",
            },
            status=201,
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertTrue(result.success)
        # authority packs IDPay's id + our generated order_id together
        # (see gateways/idpay.py's module docstring) — the id half must
        # be exactly what the gateway returned.
        idpay_id, _, order_id = result.authority.partition(":")
        self.assertEqual(idpay_id, "d2e353189823079e1e4181772cff5292")
        self.assertTrue(order_id)  # a fresh opaque order_id was generated
        self.assertEqual(
            result.redirect_url,
            "https://idpay.ir/p/ws-sandbox/d2e353189823079e1e4181772cff5292",
        )
        self.assertEqual(result.error_message, "")

    @responses.activate
    def test_gateway_error_response_returns_failure_with_message(self):
        responses.add(
            responses.POST,
            IDPayGateway.REQUEST_URL,
            json={"error_code": 34, "error_message": "amount is invalid"},
            status=400,
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")
        self.assertIn("amount is invalid", result.error_message)
        self.assertEqual(result.authority, "")
        self.assertEqual(result.redirect_url, "")

    @responses.activate
    def test_connection_error_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            IDPayGateway.REQUEST_URL,
            body=requests.exceptions.ConnectionError("connection refused"),
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    @responses.activate
    def test_timeout_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            IDPayGateway.REQUEST_URL,
            body=requests.exceptions.Timeout("request timed out"),
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    @responses.activate
    def test_malformed_non_json_body_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            IDPayGateway.REQUEST_URL,
            body="<html>not json at all</html>",
            status=200,
            content_type="text/html",
        )

        result = self.gateway.request_payment(self.amount, self.callback_url)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    def test_amount_timeout_and_headers_are_passed_on_outbound_call(self):
        with patch("payments.gateways.idpay.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {
                "id": "abc123",
                "link": "https://idpay.ir/p/ws-sandbox/abc123",
            }

            self.gateway.request_payment(self.amount, self.callback_url)

            mock_post.assert_called_once()
            _, call_kwargs = mock_post.call_args
            self.assertIn("timeout", call_kwargs)
            self.assertEqual(
                call_kwargs["timeout"], IDPayGateway.REQUEST_TIMEOUT_SECONDS
            )
            sent_payload = call_kwargs["json"]
            self.assertEqual(sent_payload["amount"], int(self.amount))
            self.assertEqual(sent_payload["callback"], self.callback_url)
            self.assertIn("order_id", sent_payload)

            # Auth is via headers, not payload fields — confirmed a THIRD
            # distinct mechanism from ZarinPal/Zibal (see module docstring).
            headers = call_kwargs["headers"]
            self.assertIn("X-API-KEY", headers)
            self.assertIn("X-SANDBOX", headers)


class IDPayVerifyPaymentTests(SimpleTestCase):
    def setUp(self):
        self.gateway = IDPayGateway()
        self.amount = Decimal("150000")
        self.idpay_id = "d2e353189823079e1e4181772cff5292"
        self.order_id = "b7f1c1a2e3d4f5a6b7c8d9e0f1a2b3c4"
        self.authority = f"{self.idpay_id}:{self.order_id}"

    @responses.activate
    def test_successful_verification_returns_ref_id(self):
        responses.add(
            responses.POST,
            IDPayGateway.VERIFY_URL,
            json={
                "status": 100,
                "track_id": 27384837,
                "id": self.idpay_id,
                "order_id": self.order_id,
                "amount": 150000,
                "card_no": "610433******9414",
            },
            status=200,
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertTrue(result.success)
        self.assertEqual(result.ref_id, "27384837")
        self.assertEqual(result.error_message, "")
        self.assertIsNotNone(result.raw_response)

    @responses.activate
    def test_already_verified_response_also_returns_success(self):
        # status=101 and status=200 are ALSO valid success outcomes for
        # an idempotent verify call, per IDPay's documented behavior
        # (see module docstring) — a customer double-hitting the
        # callback URL must not be treated as a payment failure.
        responses.add(
            responses.POST,
            IDPayGateway.VERIFY_URL,
            json={
                "status": 101,
                "track_id": 27384837,
                "id": self.idpay_id,
                "order_id": self.order_id,
                "amount": 150000,
            },
            status=200,
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertTrue(result.success)
        self.assertEqual(result.ref_id, "27384837")

    @responses.activate
    def test_failed_verification_returns_failure_with_message(self):
        responses.add(
            responses.POST,
            IDPayGateway.VERIFY_URL,
            json={"error_code": 13, "error_message": "transaction not found"},
            status=404,
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")
        self.assertIn("transaction not found", result.error_message)
        self.assertEqual(result.ref_id, "")

    @responses.activate
    def test_connection_error_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            IDPayGateway.VERIFY_URL,
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
            IDPayGateway.VERIFY_URL,
            body=requests.exceptions.Timeout("request timed out"),
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    @responses.activate
    def test_malformed_non_json_body_is_caught_and_returns_failure(self):
        responses.add(
            responses.POST,
            IDPayGateway.VERIFY_URL,
            body="<html>not json at all</html>",
            status=200,
            content_type="text/html",
        )

        result = self.gateway.verify_payment(self.authority, self.amount)

        self.assertFalse(result.success)
        self.assertNotEqual(result.error_message, "")

    def test_malformed_authority_is_handled_without_calling_the_gateway(self):
        # No colon separator at all — can't recover an id/order_id pair.
        # This is IDPay-specific (its authority is a composite string, an
        # implementation detail of this gateway alone), so it's tested
        # here rather than at the shared PaymentGateway interface level.
        result = self.gateway.verify_payment("not-a-composite-authority", self.amount)

        self.assertFalse(result.success)
        self.assertIn("Malformed IDPay authority", result.error_message)

    def test_id_order_id_timeout_and_headers_are_passed_on_outbound_call(self):
        with patch("payments.gateways.idpay.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            mock_post.return_value.json.return_value = {
                "status": 100,
                "track_id": 1,
            }

            self.gateway.verify_payment(self.authority, self.amount)

            mock_post.assert_called_once()
            _, call_kwargs = mock_post.call_args
            self.assertIn("timeout", call_kwargs)
            self.assertEqual(
                call_kwargs["timeout"], IDPayGateway.REQUEST_TIMEOUT_SECONDS
            )
            sent_payload = call_kwargs["json"]
            self.assertEqual(sent_payload["id"], self.idpay_id)
            self.assertEqual(sent_payload["order_id"], self.order_id)

            headers = call_kwargs["headers"]
            self.assertIn("X-API-KEY", headers)
            self.assertIn("X-SANDBOX", headers)


class IDPayExtractCallbackParamsTests(SimpleTestCase):
    """
    Task 6.3.1.4: confirms IDPayGateway.extract_callback_params() parses
    IDPay's actual documented callback shape — confirmed against an
    independent CodeIgniter client library (reads exactly `status`,
    `track_id`, `id`, `order_id`) and cross-checked against a Go client
    library's callback handler signature (same four fields) — genuinely
    different field names from both ZarinPal and Zibal.
    """

    def setUp(self):
        self.gateway = IDPayGateway()
        self.factory = RequestFactory()

    def test_extracts_composite_authority_from_id_and_order_id(self):
        request = self.factory.get(
            "/api/payments/callback/idpay/",
            {
                "id": "d2e353189823079e1e4181772cff5292",
                "order_id": "b7f1c1a2e3d4f5a6b7c8d9e0f1a2b3c4",
                "status": "10",
                "track_id": "27384837",
            },
        )

        params = self.gateway.extract_callback_params(request)

        self.assertEqual(
            params["authority"],
            "d2e353189823079e1e4181772cff5292:b7f1c1a2e3d4f5a6b7c8d9e0f1a2b3c4",
        )
        self.assertFalse(params["is_customer_cancelled"])

    def test_status_1_is_customer_cancelled(self):
        # Per IDPay's documented status table, 1 = "Payment has not been
        # done" — IDPay's own definitive "customer never completed
        # payment" signal.
        request = self.factory.get(
            "/api/payments/callback/idpay/",
            {
                "id": "d2e353189823079e1e4181772cff5292",
                "order_id": "b7f1c1a2e3d4f5a6b7c8d9e0f1a2b3c4",
                "status": "1",
            },
        )

        params = self.gateway.extract_callback_params(request)

        self.assertTrue(params["is_customer_cancelled"])

    def test_other_status_values_still_proceed_to_verify(self):
        # A non-1, non-success status (e.g. 2 = "Payment failed") is NOT
        # treated as "customer cancelled" here — it still goes through
        # verify_payment() for an authoritative, specific error message,
        # rather than being lumped in with the generic cancelled case.
        request = self.factory.get(
            "/api/payments/callback/idpay/",
            {
                "id": "d2e353189823079e1e4181772cff5292",
                "order_id": "b7f1c1a2e3d4f5a6b7c8d9e0f1a2b3c4",
                "status": "2",
            },
        )

        params = self.gateway.extract_callback_params(request)

        self.assertFalse(params["is_customer_cancelled"])

    def test_missing_id_or_order_id_yields_empty_authority(self):
        request = self.factory.get("/api/payments/callback/idpay/", {"status": "1"})

        params = self.gateway.extract_callback_params(request)

        self.assertEqual(params["authority"], "")
