"""
End-to-end integration tests for the full checkout -> payment-initiate ->
gateway callback flow (Tasks 6.2.1.1 through 6.2.1.6), exercised entirely
through the real HTTP API surface via DRF's APIClient — the same way a
browser/frontend actually would — with `responses` mocking only the
OUTBOUND calls to ZarinPal's real API.

This complements, rather than duplicates, the narrower per-task unit/view
tests already in test_zarinpal.py (gateway-level request/verify unit
tests), test_views.py (individual initiate/callback endpoint edge cases),
and test_callback_concurrency.py (the double-callback race) — the focus
here, following the same pattern as Epic 2 Task 2.3.1.4's OTP integration
suite (accounts/tests/test_otp_integration.py), is the full round trip and
the handful of scenarios that only make sense when chained together:
checkout really does reserve stock, a failed/cancelled payment really
does release it, and a customer really can retry after a network hiccup.

`responses` intercepts calls to ZarinPal's real sandbox host
(ZarinPalGateway.REQUEST_URL / VERIFY_URL) so no real network call ever
leaves this test process — every other hop (checkout, initiate, the
gateway's redirect back to our callback URL) goes through the real Django
URL routing and view/serializer/model stack.
"""

import json

import requests
import responses
from django.contrib.auth import get_user_model
from order.models import Order, OrderItem
from order.tests.factories import make_cart_with_items, make_product, make_variant
from payments.gateways.zarinpal import ZarinPalGateway
from payments.models import PaymentTransaction
from rest_framework import status
from rest_framework.test import APITestCase
from shop.models import StockMovement

User = get_user_model()

ORDERS_URL = "/api/orders/"
INITIATE_URL = "/api/payments/initiate/"


def callback_url(gateway="zarinpal"):
    return f"/api/payments/callback/{gateway}/"


VALID_CHECKOUT_PAYLOAD = {
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane@example.com",
    "phone": "555-1234",
    "address": "42 Elm Street",
    "apartment": "Apt 3B",
    "city": "Portland",
    "state": "tehran",
    "zip": "1234567890",
    "country": "IR",
    "billing_same": True,
    "payment_method": "credit_card",
    "card_last_four": "4242",
    "notes": "",
}


def zarinpal_success_response(authority="A00000000000000000000000000000000wOGYpd"):
    return {
        "data": {
            "code": 100,
            "message": "Success",
            "authority": authority,
            "fee_type": "Merchant",
            "fee": 100,
        },
        "errors": [],
    }


def zarinpal_verify_success_response(ref_id=201202070):
    return {
        "data": {
            "code": 100,
            "message": "Verified",
            "ref_id": ref_id,
            "card_pan": "502229******5995",
            "fee_type": "Merchant",
            "fee": 100,
        },
        "errors": [],
    }


def zarinpal_verify_failure_response():
    return {
        "data": [],
        "errors": {
            "code": -21,
            "message": "Transaction not found or unsuccessful.",
            "validations": [],
        },
    }


class ZarinPalCheckoutIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="buyer@example.com", password="TestPass123!"
        )
        self.product = make_product(name="Face Cream", slug="face-cream", price="50.00")
        self.variant = make_variant(product=self.product, stock=10)
        self.starting_stock = self.variant.stock
        make_cart_with_items(self.user, [{"variant": self.variant, "quantity": 2}])
        self.client.force_authenticate(user=self.user)

    def _checkout(self):
        """POST /api/orders/ — the real checkout endpoint, real payload."""
        response = self.client.post(ORDERS_URL, VALID_CHECKOUT_PAYLOAD, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["status"], Order.Status.PENDING)
        return Order.objects.get(pk=response.data["id"])

    def _initiate(self, order):
        return self.client.post(INITIATE_URL, {"order_id": order.id}, format="json")

    # ── 1. Full happy path ──────────────────────────────────────────────────

    @responses.activate
    def test_full_happy_path_checkout_to_order_confirmed(self):
        order = self._checkout()
        # Stock reserved at order-creation time, per Epic 1/3's flow —
        # before the customer ever reaches the gateway.
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, self.starting_stock - 2)

        authority = "A00000000000000000000000000000000wOGYpd"
        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            json=zarinpal_success_response(authority),
            status=200,
        )

        initiate_response = self._initiate(order)

        self.assertEqual(initiate_response.status_code, status.HTTP_200_OK)
        self.assertIn("redirect_url", initiate_response.data)
        self.assertIn(authority, initiate_response.data["redirect_url"])

        txn = PaymentTransaction.objects.get(order=order)
        self.assertEqual(txn.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(txn.gateway, "zarinpal")
        self.assertEqual(txn.authority, authority)
        self.assertEqual(txn.amount, order.total)

        # Customer completes payment on ZarinPal's hosted page; ZarinPal
        # redirects their browser back to our callback URL.
        responses.add(
            responses.POST,
            ZarinPalGateway.VERIFY_URL,
            json=zarinpal_verify_success_response(),
            status=200,
        )

        callback_response = self.client.get(
            callback_url(), {"Authority": authority, "Status": "OK"}
        )

        self.assertEqual(callback_response.status_code, status.HTTP_302_FOUND)
        self.assertIn(f"/order-confirmation/{order.id}", callback_response.url)

        order.refresh_from_db()
        txn.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, Order.Status.PROCESSING)
        self.assertEqual(txn.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(txn.ref_id, "201202070")
        # Stock was already decremented at order-creation time — a
        # successful payment must NOT touch it again.
        self.assertEqual(self.variant.stock, self.starting_stock - 2)

    # ── 2. Payment failure releases stock ───────────────────────────────────

    @responses.activate
    def test_verification_failure_cancels_order_and_restores_exact_stock(self):
        order = self._checkout()
        self.variant.refresh_from_db()
        stock_after_order_creation = self.variant.stock
        self.assertEqual(stock_after_order_creation, self.starting_stock - 2)

        order_item = OrderItem.objects.get(order=order, variant=self.variant)
        self.assertEqual(order_item.quantity, 2)

        authority = "A00000000000000000000000000000000wFAILED"
        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            json=zarinpal_success_response(authority),
            status=200,
        )
        initiate_response = self._initiate(order)
        self.assertEqual(initiate_response.status_code, status.HTTP_200_OK)

        responses.add(
            responses.POST,
            ZarinPalGateway.VERIFY_URL,
            json=zarinpal_verify_failure_response(),
            status=200,
        )

        callback_response = self.client.get(
            callback_url(), {"Authority": authority, "Status": "OK"}
        )

        self.assertEqual(callback_response.status_code, status.HTTP_302_FOUND)
        self.assertIn("/checkout/failed", callback_response.url)
        self.assertIn("reason=verification_failed", callback_response.url)

        order.refresh_from_db()
        txn = PaymentTransaction.objects.get(order=order)
        self.variant.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(txn.status, PaymentTransaction.Status.FAILED)

        # THE most financially important assertion in this suite: stock
        # must be restored to EXACTLY its pre-order value, not merely
        # "increased by some amount."
        self.assertEqual(self.variant.stock, self.starting_stock)
        self.assertEqual(
            self.variant.stock, stock_after_order_creation + order_item.quantity
        )

        movement = StockMovement.objects.get(
            related_order=order, reason=StockMovement.Reason.CANCELLATION
        )
        self.assertEqual(movement.variant, self.variant)
        self.assertEqual(movement.reason, StockMovement.Reason.CANCELLATION)
        self.assertEqual(movement.quantity_delta, order_item.quantity)
        self.assertEqual(movement.stock_after, self.starting_stock)
        self.assertIsNone(movement.actor)

    # ── 3. Customer cancels on gateway page (NOK) ───────────────────────────

    @responses.activate
    def test_customer_cancelled_nok_cancels_order_without_calling_verify(self):
        order = self._checkout()
        order_item = OrderItem.objects.get(order=order, variant=self.variant)

        authority = "A00000000000000000000000000000000wCANCEL"
        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            json=zarinpal_success_response(authority),
            status=200,
        )
        self._initiate(order)

        # Deliberately do NOT register a VERIFY_URL responses mock — if
        # the view calls verify_payment() at all in the NOK path, this
        # test fails with a responses.ConnectionError (no mock registered
        # for that URL), which is exactly the strong "was it called"
        # signal we want here, stronger than a mock-call-count assertion.
        callback_response = self.client.get(
            callback_url(), {"Authority": authority, "Status": "NOK"}
        )

        self.assertEqual(callback_response.status_code, status.HTTP_302_FOUND)
        self.assertIn("reason=cancelled", callback_response.url)

        order.refresh_from_db()
        txn = PaymentTransaction.objects.get(order=order)
        self.variant.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(txn.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(self.variant.stock, self.starting_stock)

        movement = StockMovement.objects.get(
            related_order=order, reason=StockMovement.Reason.CANCELLATION
        )
        self.assertEqual(movement.quantity_delta, order_item.quantity)

        # Only one outbound call was ever made: the initiate's
        # request_payment() POST to REQUEST_URL. No call reached
        # VERIFY_URL.
        verify_calls = [
            c for c in responses.calls if c.request.url == ZarinPalGateway.VERIFY_URL
        ]
        self.assertEqual(len(verify_calls), 0)

    # ── 4. Double-initiate rejected ─────────────────────────────────────────

    @responses.activate
    def test_second_initiate_after_order_no_longer_pending_returns_400(self):
        order = self._checkout()
        authority = "A00000000000000000000000000000000wDOUBLE"
        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            json=zarinpal_success_response(authority),
            status=200,
        )
        first_initiate = self._initiate(order)
        self.assertEqual(first_initiate.status_code, status.HTTP_200_OK)

        responses.add(
            responses.POST,
            ZarinPalGateway.VERIFY_URL,
            json=zarinpal_verify_success_response(),
            status=200,
        )
        self.client.get(callback_url(), {"Authority": authority, "Status": "OK"})

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PROCESSING)

        second_initiate = self._initiate(order)

        self.assertEqual(second_initiate.status_code, status.HTTP_400_BAD_REQUEST)
        # Still exactly one transaction for this order — the rejected
        # second initiate must not have created another.
        self.assertEqual(PaymentTransaction.objects.filter(order=order).count(), 1)

    # ── 5. Gateway network failure during initiate ──────────────────────────

    @responses.activate
    def test_initiate_network_failure_leaves_order_pending_and_stock_reserved(self):
        order = self._checkout()
        self.variant.refresh_from_db()
        stock_after_order_creation = self.variant.stock
        self.assertEqual(stock_after_order_creation, self.starting_stock - 2)

        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            body=requests.exceptions.ConnectionError("connection refused"),
        )

        response = self._initiate(order)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

        order.refresh_from_db()
        self.variant.refresh_from_db()

        # No PaymentTransaction row exists yet — request_payment() never
        # even got an authority back, so there's nothing to mark FAILED.
        self.assertEqual(PaymentTransaction.objects.filter(order=order).count(), 0)
        # The order must remain exactly PENDING — a failed INITIATE is
        # not a failed VERIFY, and must not trigger cancellation/stock
        # restoration logic that's only correct once a real gateway
        # attempt (with an authority) has actually failed.
        self.assertEqual(order.status, Order.Status.PENDING)
        # Stock reserved at order-creation time must remain reserved —
        # untouched by this failed initiate attempt.
        self.assertEqual(self.variant.stock, stock_after_order_creation)
        # Exactly one StockMovement exists for this order: the SALE
        # movement logged at checkout/order-creation time (Epic 4). No
        # CANCELLATION movement should exist — that would mean stock was
        # incorrectly "restored" for an initiate that never even reached
        # the gateway.
        self.assertEqual(StockMovement.objects.filter(related_order=order).count(), 1)
        self.assertEqual(
            StockMovement.objects.filter(
                related_order=order, reason=StockMovement.Reason.SALE
            ).count(),
            1,
        )
        self.assertEqual(
            StockMovement.objects.filter(
                related_order=order, reason=StockMovement.Reason.CANCELLATION
            ).count(),
            0,
        )

        # The customer must be able to simply retry: a second initiate,
        # this time succeeding, should work normally against the same
        # still-PENDING order.
        authority = "A00000000000000000000000000000000wRETRY"
        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            json=zarinpal_success_response(authority),
            status=200,
        )
        retry_response = self._initiate(order)

        self.assertEqual(retry_response.status_code, status.HTTP_200_OK)
        self.assertEqual(PaymentTransaction.objects.filter(order=order).count(), 1)
        txn = PaymentTransaction.objects.get(order=order)
        self.assertEqual(txn.authority, authority)
        self.assertEqual(txn.status, PaymentTransaction.Status.PENDING)


class ZarinPalCheckoutIntegrationRegressionGuardTests(APITestCase):
    """
    A couple of cross-cutting sanity checks that only matter at the full
    integration level (not worth their own dedicated unit test, but cheap
    to fold in here since the fixtures are already built for it).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            email="buyer2@example.com", password="TestPass123!"
        )
        self.variant = make_variant(name="Serum", slug="serum", price="30.00", stock=3)
        make_cart_with_items(self.user, [{"variant": self.variant, "quantity": 1}])
        self.client.force_authenticate(user=self.user)

    @responses.activate
    def test_initiate_amount_sent_to_gateway_matches_order_total(self):
        response = self.client.post(ORDERS_URL, VALID_CHECKOUT_PAYLOAD, format="json")
        order = Order.objects.get(pk=response.data["id"])

        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            json=zarinpal_success_response(),
            status=200,
        )
        self.client.post(INITIATE_URL, {"order_id": order.id}, format="json")

        self.assertEqual(len(responses.calls), 1)
        sent_payload = responses.calls[0].request.body
        sent = json.loads(sent_payload)
        self.assertEqual(sent["amount"], int(order.total))

    @responses.activate
    def test_verify_amount_sent_matches_original_order_total(self):
        response = self.client.post(ORDERS_URL, VALID_CHECKOUT_PAYLOAD, format="json")
        order = Order.objects.get(pk=response.data["id"])
        authority = "A00000000000000000000000000000000wAMOUNT"

        responses.add(
            responses.POST,
            ZarinPalGateway.REQUEST_URL,
            json=zarinpal_success_response(authority),
            status=200,
        )
        self.client.post(INITIATE_URL, {"order_id": order.id}, format="json")

        responses.add(
            responses.POST,
            ZarinPalGateway.VERIFY_URL,
            json=zarinpal_verify_success_response(),
            status=200,
        )
        self.client.get(callback_url(), {"Authority": authority, "Status": "OK"})

        verify_calls = [
            c for c in responses.calls if c.request.url == ZarinPalGateway.VERIFY_URL
        ]
        self.assertEqual(len(verify_calls), 1)

        sent = json.loads(verify_calls[0].request.body)
        self.assertEqual(sent["amount"], int(order.total))
        self.assertEqual(sent["authority"], authority)
