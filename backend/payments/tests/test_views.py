from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from order.models import Order
from rest_framework import status
from rest_framework.test import APITestCase

from payments.gateways.base import PaymentRequestResult
from payments.models import PaymentTransaction

User = get_user_model()


def make_user(email="buyer@example.com", password="TestPass123!", **kwargs):
    return User.objects.create_user(email=email, password=password, **kwargs)


def make_order(user, **kwargs):
    defaults = dict(
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        phone="555-1234",
        shipping_address="42 Elm Street",
        shipping_apartment="Apt 3B",
        shipping_city="Portland",
        shipping_state="OR",
        shipping_zip="97201",
        shipping_country="US",
        payment_method=Order.PaymentMethod.CREDIT_CARD,
        subtotal=Decimal("50.00"),
        shipping_cost=Decimal("9.99"),
        tax=Decimal("5.00"),
        discount=Decimal("0.00"),
        total=Decimal("64.99"),
        status=Order.Status.PENDING,
    )
    defaults.update(kwargs)
    return Order.objects.create(user=user, **defaults)


class PaymentInitiateViewTests(APITestCase):
    """
    Note: `payments.views.reverse` is patched in the two tests below that
    actually reach the gateway call — the view builds a callback_url via
    reverse("payments:callback", ...), and that URL name isn't registered
    until Task 6.2.1.4. Patching it here isolates this task's behavior
    (initiate → call gateway → create PaymentTransaction) from a URL that
    doesn't exist yet, per this task's own note that the view isn't
    expected to fully work end-to-end until 6.2.1.4 lands too.
    """

    URL = "/api/payments/initiate/"

    def setUp(self):
        self.user = make_user()
        self.other_user = make_user(email="other@example.com")
        self.order = make_order(self.user)
        self.client.force_authenticate(user=self.user)

    @patch("payments.views.reverse", return_value="/api/payments/callback/zarinpal/")
    @patch("payments.views.get_payment_gateway")
    def test_successful_initiation_returns_redirect_url_and_creates_transaction(
        self, mock_get_gateway, mock_reverse
    ):
        mock_gateway = mock_get_gateway.return_value
        mock_gateway.request_payment.return_value = PaymentRequestResult(
            success=True,
            authority="A00000000000000000000000000000000wOGYpd",
            redirect_url=(
                "https://sandbox.zarinpal.com/pg/StartPay/"
                "A00000000000000000000000000000000wOGYpd"
            ),
        )

        response = self.client.post(
            self.URL, {"order_id": self.order.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("redirect_url", response.data)
        self.assertEqual(
            response.data["redirect_url"],
            "https://sandbox.zarinpal.com/pg/StartPay/"
            "A00000000000000000000000000000000wOGYpd",
        )

        self.assertEqual(PaymentTransaction.objects.count(), 1)
        transaction = PaymentTransaction.objects.get()
        self.assertEqual(transaction.order, self.order)
        self.assertEqual(transaction.gateway, "zarinpal")
        self.assertEqual(transaction.amount, self.order.total)
        self.assertEqual(
            transaction.authority, "A00000000000000000000000000000000wOGYpd"
        )
        self.assertEqual(transaction.status, PaymentTransaction.Status.PENDING)

    @patch("payments.views.get_payment_gateway")
    def test_initiating_payment_for_another_users_order_returns_404(
        self, mock_get_gateway
    ):
        others_order = make_order(self.other_user)

        response = self.client.post(
            self.URL, {"order_id": others_order.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        mock_get_gateway.assert_not_called()
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    @patch("payments.views.get_payment_gateway")
    def test_initiating_payment_for_already_processing_order_returns_400(
        self, mock_get_gateway
    ):
        self.order.status = Order.Status.PROCESSING
        self.order.save(update_fields=["status"])

        response = self.client.post(
            self.URL, {"order_id": self.order.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_get_gateway.assert_not_called()
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    @patch("payments.views.reverse", return_value="/api/payments/callback/zarinpal/")
    @patch("payments.views.get_payment_gateway")
    def test_gateway_failure_returns_502_and_creates_no_transaction(
        self, mock_get_gateway, mock_reverse
    ):
        mock_gateway = mock_get_gateway.return_value
        mock_gateway.request_payment.return_value = PaymentRequestResult(
            success=False, error_message="ZarinPal payment request failed."
        )

        response = self.client.post(
            self.URL, {"order_id": self.order.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("detail", response.data)
        self.assertEqual(PaymentTransaction.objects.count(), 0)
