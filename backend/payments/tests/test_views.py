from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from order.models import Order, OrderItem
from order.tests.factories import make_variant
from payments.gateways.base import PaymentRequestResult, PaymentVerifyResult
from payments.models import PaymentTransaction
from rest_framework import status
from rest_framework.test import APITestCase
from shop.models import StockMovement

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


def make_order_item(order, variant, quantity=2):
    return OrderItem.objects.create(
        order=order,
        product=variant.product,
        variant=variant,
        product_name=variant.product.name,
        product_slug=variant.product.slug,
        variant_sku=variant.sku,
        unit_price=variant.price,
        quantity=quantity,
    )


class PaymentInitiateViewTests(APITestCase):
    URL = "/api/payments/initiate/"

    def setUp(self):
        self.user = make_user()
        self.other_user = make_user(email="other@example.com")
        self.order = make_order(self.user)
        self.client.force_authenticate(user=self.user)

    @patch("payments.views.get_payment_gateway")
    def test_successful_initiation_returns_redirect_url_and_creates_transaction(
        self, mock_get_gateway
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

    @patch("payments.views.get_payment_gateway")
    def test_gateway_failure_returns_502_and_creates_no_transaction(
        self, mock_get_gateway
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


class PaymentCallbackViewTests(APITestCase):
    def url(self, gateway="zarinpal"):
        return f"/api/payments/callback/{gateway}/"

    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user, total=Decimal("100.00"))
        self.variant = make_variant(stock=5)
        self.order_item = make_order_item(self.order, self.variant, quantity=2)
        self.authority = "A00000000000000000000000000000000wOGYpd"
        self.txn = PaymentTransaction.objects.create(
            order=self.order,
            gateway="zarinpal",
            authority=self.authority,
            amount=self.order.total,
            status=PaymentTransaction.Status.PENDING,
        )
        # Stock was already decremented at order-creation time (Epic
        # 1/3's flow) — simulate that here since these tests create the
        # order directly rather than going through OrderCreateSerializer.
        self.stock_after_order_creation = self.variant.stock

    @patch("payments.views.get_payment_gateway")
    def test_successful_callback_marks_success_and_processing_without_touching_stock(
        self, mock_get_gateway
    ):
        mock_gateway = mock_get_gateway.return_value
        mock_gateway.verify_payment.return_value = PaymentVerifyResult(
            success=True, ref_id="201202070", raw_response={"data": {"code": 100}}
        )

        response = self.client.get(
            self.url(), {"Authority": self.authority, "Status": "OK"}
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn(f"/order-confirmation/{self.order.id}", response.url)

        self.txn.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.txn.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(self.txn.ref_id, "201202070")
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        # No double-decrement, no restoration — stock is untouched.
        self.assertEqual(self.variant.stock, self.stock_after_order_creation)
        self.assertEqual(
            StockMovement.objects.filter(related_order=self.order).count(), 0
        )

    @patch("payments.views.get_payment_gateway")
    def test_failed_verification_marks_failed_cancels_order_and_restores_stock(
        self, mock_get_gateway
    ):
        mock_gateway = mock_get_gateway.return_value
        mock_gateway.verify_payment.return_value = PaymentVerifyResult(
            success=False, error_message="Transaction not found or unsuccessful."
        )

        response = self.client.get(
            self.url(), {"Authority": self.authority, "Status": "OK"}
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("/checkout/failed", response.url)
        self.assertIn("reason=verification_failed", response.url)

        self.txn.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.txn.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        # Stock reserved at order-creation time must be released back.
        self.assertEqual(
            self.variant.stock,
            self.stock_after_order_creation + self.order_item.quantity,
        )

        movement = StockMovement.objects.get(related_order=self.order)
        self.assertEqual(movement.variant, self.variant)
        self.assertEqual(movement.reason, StockMovement.Reason.CANCELLATION)
        self.assertEqual(movement.quantity_delta, self.order_item.quantity)
        self.assertEqual(movement.stock_after, self.variant.stock)
        self.assertIsNone(movement.actor)

    @patch("payments.views.get_payment_gateway")
    def test_nok_status_short_circuits_without_calling_verify_payment(
        self, mock_get_gateway
    ):
        mock_gateway = mock_get_gateway.return_value

        response = self.client.get(
            self.url(), {"Authority": self.authority, "Status": "NOK"}
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("reason=cancelled", response.url)
        mock_gateway.verify_payment.assert_not_called()

        self.txn.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.txn.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(
            self.variant.stock,
            self.stock_after_order_creation + self.order_item.quantity,
        )

    @patch("payments.views.get_payment_gateway")
    def test_duplicate_callback_on_already_success_transaction_is_idempotent(
        self, mock_get_gateway
    ):
        self.txn.status = PaymentTransaction.Status.SUCCESS
        self.txn.ref_id = "201202070"
        self.txn.save()
        self.order.status = Order.Status.PROCESSING
        self.order.save(update_fields=["status"])

        response = self.client.get(
            self.url(), {"Authority": self.authority, "Status": "OK"}
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn(f"/order-confirmation/{self.order.id}", response.url)

        mock_gateway = mock_get_gateway.return_value
        mock_gateway.verify_payment.assert_not_called()

        self.txn.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.txn.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(self.txn.ref_id, "201202070")
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(self.variant.stock, self.stock_after_order_creation)

    @patch("payments.views.get_payment_gateway")
    def test_unknown_authority_redirects_to_generic_failure_without_raising(
        self, mock_get_gateway
    ):
        response = self.client.get(
            self.url(), {"Authority": "totally-unknown-authority", "Status": "OK"}
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("reason=unknown_transaction", response.url)

        mock_gateway = mock_get_gateway.return_value
        mock_gateway.verify_payment.assert_not_called()
