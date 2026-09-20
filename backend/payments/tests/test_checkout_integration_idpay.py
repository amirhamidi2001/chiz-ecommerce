"""
End-to-end integration tests for the full checkout -> payment-initiate ->
gateway callback flow, using IDPAY as the active gateway (Task 6.3.1.4).

Mirrors test_checkout_integration.py's structure/rigor exactly, but
exercises IDPay's actual documented request/verify/callback shapes —
header-based auth, a composite "{id}:{order_id}" authority, and callback
params (`id`, `order_id`, `status`, `track_id`) genuinely different from
both ZarinPal and Zibal. `responses` mocks only the OUTBOUND calls to
IDPay's real API (IDPayGateway.REQUEST_URL / VERIFY_URL); every other hop
goes through the real Django URL routing and view/serializer/model stack
via APIClient.
"""

import responses
from django.contrib.auth import get_user_model
from order.models import Order, OrderItem
from order.tests.factories import make_cart_with_items, make_product, make_variant
from payments.gateways.idpay import IDPayGateway
from payments.models import PaymentGatewayConfig, PaymentTransaction
from rest_framework import status
from rest_framework.test import APITestCase
from shop.models import StockMovement

User = get_user_model()

ORDERS_URL = "/api/orders/"
INITIATE_URL = "/api/payments/initiate/"


def callback_url(gateway="idpay"):
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


def idpay_success_response(idpay_id="d2e353189823079e1e4181772cff5292"):
    return {"id": idpay_id, "link": f"https://idpay.ir/p/ws-sandbox/{idpay_id}"}


def idpay_verify_success_response(track_id=27384837):
    return {
        "status": 100,
        "track_id": track_id,
        "amount": 6499,
        "card_no": "610433******9414",
    }


def idpay_verify_failure_response():
    return {"error_code": 13, "error_message": "transaction not found"}


class IDPayCheckoutIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="buyer@example.com", password="TestPass123!"
        )
        self.product = make_product(name="Face Cream", slug="face-cream", price="50.00")
        self.variant = make_variant(product=self.product, stock=10)
        self.starting_stock = self.variant.stock
        make_cart_with_items(self.user, [{"variant": self.variant, "quantity": 2}])
        self.client.force_authenticate(user=self.user)
        # Task 6.3.1.3: make IDPay the active gateway for this suite.
        PaymentGatewayConfig.objects.create(
            active_gateway=PaymentTransaction.Gateway.IDPAY
        )

    def _checkout(self):
        response = self.client.post(ORDERS_URL, VALID_CHECKOUT_PAYLOAD, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["status"], Order.Status.PENDING)
        return Order.objects.get(pk=response.data["id"])

    def _initiate(self, order):
        return self.client.post(INITIATE_URL, {"order_id": order.id}, format="json")

    @responses.activate
    def test_full_happy_path_checkout_to_order_confirmed(self):
        order = self._checkout()
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, self.starting_stock - 2)

        idpay_id = "d2e353189823079e1e4181772cff5292"
        responses.add(
            responses.POST,
            IDPayGateway.REQUEST_URL,
            json=idpay_success_response(idpay_id),
            status=201,
        )

        initiate_response = self._initiate(order)

        self.assertEqual(initiate_response.status_code, status.HTTP_200_OK)
        self.assertIn(idpay_id, initiate_response.data["redirect_url"])

        txn = PaymentTransaction.objects.get(order=order)
        self.assertEqual(txn.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(txn.gateway, "idpay")
        # authority is the composite "{id}:{order_id}" this gateway
        # generates — we don't know the generated order_id half here, so
        # just confirm the idpay_id half matches.
        stored_idpay_id, _, stored_order_id = txn.authority.partition(":")
        self.assertEqual(stored_idpay_id, idpay_id)
        self.assertTrue(stored_order_id)

        responses.add(
            responses.POST,
            IDPayGateway.VERIFY_URL,
            json=idpay_verify_success_response(),
            status=200,
        )

        # IDPay's actual documented callback query params — id, order_id,
        # status, track_id — genuinely different names from both ZarinPal
        # and Zibal.
        callback_response = self.client.get(
            callback_url(),
            {
                "id": idpay_id,
                "order_id": stored_order_id,
                "status": "10",
                "track_id": "27384837",
            },
        )

        self.assertEqual(callback_response.status_code, status.HTTP_302_FOUND)
        self.assertIn(f"/order-confirmation/{order.id}", callback_response.url)

        order.refresh_from_db()
        txn.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, Order.Status.PROCESSING)
        self.assertEqual(txn.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(txn.ref_id, "27384837")
        self.assertEqual(self.variant.stock, self.starting_stock - 2)

    @responses.activate
    def test_verification_failure_cancels_order_and_restores_exact_stock(self):
        order = self._checkout()
        order_item = OrderItem.objects.get(order=order, variant=self.variant)

        idpay_id = "aaaa53189823079e1e4181772cff5292"
        responses.add(
            responses.POST,
            IDPayGateway.REQUEST_URL,
            json=idpay_success_response(idpay_id),
            status=201,
        )
        self._initiate(order)

        txn = PaymentTransaction.objects.get(order=order)
        _, _, order_id = txn.authority.partition(":")

        responses.add(
            responses.POST,
            IDPayGateway.VERIFY_URL,
            json=idpay_verify_failure_response(),
            status=404,
        )

        callback_response = self.client.get(
            callback_url(),
            {"id": idpay_id, "order_id": order_id, "status": "2", "track_id": "0"},
        )

        self.assertEqual(callback_response.status_code, status.HTTP_302_FOUND)
        self.assertIn("reason=verification_failed", callback_response.url)

        order.refresh_from_db()
        txn.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(txn.status, PaymentTransaction.Status.FAILED)
        # THE most financially important assertion: stock restored to
        # EXACTLY its pre-order value.
        self.assertEqual(self.variant.stock, self.starting_stock)

        movement = StockMovement.objects.get(
            related_order=order, reason=StockMovement.Reason.CANCELLATION
        )
        self.assertEqual(movement.quantity_delta, order_item.quantity)
        self.assertEqual(movement.stock_after, self.starting_stock)

    @responses.activate
    def test_customer_cancelled_status_1_cancels_order_without_calling_verify(self):
        order = self._checkout()
        order_item = OrderItem.objects.get(order=order, variant=self.variant)

        idpay_id = "bbbb53189823079e1e4181772cff5292"
        responses.add(
            responses.POST,
            IDPayGateway.REQUEST_URL,
            json=idpay_success_response(idpay_id),
            status=201,
        )
        self._initiate(order)

        txn = PaymentTransaction.objects.get(order=order)
        _, _, order_id = txn.authority.partition(":")

        # Deliberately no VERIFY_URL mock registered — if the view calls
        # verify_payment() at all for IDPay's status=1 ("Payment has not
        # been done") case, this test fails with a responses connection
        # error, a stronger "was it called" signal than a call-count
        # assertion.
        callback_response = self.client.get(
            callback_url(),
            {"id": idpay_id, "order_id": order_id, "status": "1", "track_id": "0"},
        )

        self.assertEqual(callback_response.status_code, status.HTTP_302_FOUND)
        self.assertIn("reason=cancelled", callback_response.url)

        order.refresh_from_db()
        txn.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(txn.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(self.variant.stock, self.starting_stock)

        movement = StockMovement.objects.get(
            related_order=order, reason=StockMovement.Reason.CANCELLATION
        )
        self.assertEqual(movement.quantity_delta, order_item.quantity)

        verify_calls = [
            c for c in responses.calls if c.request.url == IDPayGateway.VERIFY_URL
        ]
        self.assertEqual(len(verify_calls), 0)
