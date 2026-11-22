"""
The ORDER_CONFIRMED notification (Epic 16).

It is sent on confirmed PAYMENT SUCCESS — from
payments.services.finalize_transaction_success() — not when the order is
created in PENDING status (the customer hasn't paid yet, and an order whose
payment fails is cancelled and its stock released) and not from
PaymentCallbackView itself (see _notify_order_confirmed_on_commit for why).

`payments.services.notify` and `order.signals.notify` are patched
separately: the first is this notification, the second is the generic
"order status changed" one, which must NOT also fire for the payment-success
transition (the customer would get two texts for one event).

Django's TestCase wraps each test in a transaction, so on_commit callbacks
only run inside `captureOnCommitCallbacks(execute=True)`.
"""

from unittest.mock import patch

from cart.models import Cart, CartItem
from django.test import TestCase
from notifications.models import NotificationLog
from order.models import Order
from order.tests.factories import make_variant
from payments.gateways.base import PaymentVerifyResult
from payments.models import PaymentTransaction
from payments.tasks import reconcile_stuck_payment_transactions
from rest_framework import status
from rest_framework.test import APITestCase

from .test_tasks import make_stuck_transaction
from .test_views import make_order, make_order_item, make_user

AUTHORITY = "A00000000000000000000000000000000wOGYpd"
GUEST_PHONE = "09123456789"


def gateway_returning(mock_get_gateway, *, verified, cancelled=False):
    gateway = mock_get_gateway.return_value
    gateway.extract_callback_params.return_value = {
        "authority": AUTHORITY,
        "is_customer_cancelled": cancelled,
    }
    gateway.verify_payment.return_value = PaymentVerifyResult(
        success=verified,
        ref_id="201202070" if verified else "",
        raw_response={"data": {"code": 100 if verified else 101}},
    )
    return gateway


class OrderConfirmedNotificationTests(APITestCase):
    URL = "/api/payments/callback/zarinpal/"

    def setUp(self):
        self.user = make_user()
        # 1,000,000 Rial == 100,000 Toman.
        self.order = make_order(self.user, total=1_000_000)
        self.variant = make_variant(stock=5)
        make_order_item(self.order, self.variant, quantity=2)
        self.txn = PaymentTransaction.objects.create(
            order=self.order,
            gateway="zarinpal",
            authority=AUTHORITY,
            amount=self.order.total,
            status=PaymentTransaction.Status.PENDING,
        )

    def callback(self, params=None):
        return self.client.get(
            self.URL, params or {"Authority": AUTHORITY, "Status": "OK"}
        )

    # ── 1. success → notify(ORDER_CONFIRMED) ─────────────────────────────

    @patch("order.signals.notify")
    @patch("payments.services.notify")
    @patch("payments.views.get_payment_gateway")
    def test_successful_callback_notifies_with_order_confirmed_and_order_details(
        self, mock_get_gateway, mock_notify, _mock_status_notify
    ):
        gateway_returning(mock_get_gateway, verified=True)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.callback()

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        mock_notify.assert_called_once()
        user, event, context = mock_notify.call_args.args
        self.assertEqual(user, self.user)
        self.assertEqual(event, "order_confirmed")
        self.assertEqual(context["order_number"], self.order.order_number)
        # Toman, formatted — NOT the stored Rial (1,000,000), which the
        # template's «تومان» would present as ten times the real price.
        self.assertEqual(context["order_total"], "100,000")
        self.assertEqual(context["customer_name"], "Jane")

    @patch("order.signals.notify")
    @patch("payments.services.notify")
    @patch("payments.views.get_payment_gateway")
    def test_notification_is_deferred_until_the_transaction_commits(
        self, mock_get_gateway, mock_notify, _mock_status_notify
    ):
        gateway_returning(mock_get_gateway, verified=True)

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.callback()
            mock_notify.assert_not_called()  # nothing sent yet

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        mock_notify.assert_called_once()

    @patch("order.signals.notify")
    @patch("payments.services.notify")
    @patch("payments.views.get_payment_gateway")
    def test_payment_success_sends_only_one_message_not_a_second_status_change(
        self, mock_get_gateway, mock_confirmed, mock_status_changed
    ):
        """PENDING -> PROCESSING also fires the generic status-change
        notification; it must be suppressed for this transition."""
        gateway_returning(mock_get_gateway, verified=True)

        with self.captureOnCommitCallbacks(execute=True):
            self.callback()

        mock_confirmed.assert_called_once()
        mock_status_changed.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PROCESSING)

    @patch("order.signals.notify")
    @patch("payments.services.notify")
    @patch("payments.views.get_payment_gateway")
    def test_duplicate_callback_does_not_notify_again(
        self, mock_get_gateway, mock_notify, _mock_status_notify
    ):
        gateway_returning(mock_get_gateway, verified=True)

        with self.captureOnCommitCallbacks(execute=True):
            self.callback()
        with self.captureOnCommitCallbacks(execute=True):
            self.callback()  # customer refreshed the confirmation redirect

        self.assertEqual(mock_notify.call_count, 1)

    @patch("order.signals.notify")
    @patch("payments.services.notify")
    @patch("payments.views.get_payment_gateway")
    def test_rolled_back_success_sends_nothing(
        self, mock_get_gateway, mock_notify, _mock_status_notify
    ):
        """If anything later in the same transaction fails, the payment isn't
        recorded — and the customer must not have been told it was."""
        gateway_returning(mock_get_gateway, verified=True)
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)

        with patch("cart.models.Cart.clear", side_effect=RuntimeError("boom")):
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(RuntimeError):
                    self.callback()

        mock_notify.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    # ── 3. failed / cancelled payment → no confirmation ──────────────────

    @patch("order.signals.notify")
    @patch("payments.services.notify")
    @patch("payments.views.get_payment_gateway")
    def test_failed_verification_does_not_send_order_confirmed(
        self, mock_get_gateway, mock_notify, _mock_status_notify
    ):
        gateway_returning(mock_get_gateway, verified=False)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.callback()

        self.assertIn("/checkout/failed", response.url)
        mock_notify.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

    @patch("order.signals.notify")
    @patch("payments.services.notify")
    @patch("payments.views.get_payment_gateway")
    def test_customer_cancelled_payment_does_not_send_order_confirmed(
        self, mock_get_gateway, mock_notify, _mock_status_notify
    ):
        gateway_returning(mock_get_gateway, verified=False, cancelled=True)

        with self.captureOnCommitCallbacks(execute=True):
            self.callback({"Authority": AUTHORITY, "Status": "NOK"})

        mock_notify.assert_not_called()

    @patch("order.signals.notify")
    @patch("payments.services.notify")
    def test_creating_a_pending_order_does_not_send_order_confirmed(
        self, mock_notify, _mock_status_notify
    ):
        """The deliberate placement decision: an unpaid PENDING order has
        not been confirmed."""
        with self.captureOnCommitCallbacks(execute=True):
            make_order(self.user, total=1_000_000)

        mock_notify.assert_not_called()


class GuestOrderConfirmedNotificationTests(APITestCase):
    """Guest checkout: order.user is None, so the phone number must come
    from the order's own checkout details."""

    URL = "/api/payments/callback/zarinpal/"

    def setUp(self):
        self.order = make_order(
            None,
            total=1_000_000,
            first_name="Guest",
            email="guest@example.com",
            phone=GUEST_PHONE,
        )
        make_order_item(self.order, make_variant(stock=5), quantity=1)
        PaymentTransaction.objects.create(
            order=self.order,
            gateway="zarinpal",
            authority=AUTHORITY,
            amount=self.order.total,
            status=PaymentTransaction.Status.PENDING,
        )

    @patch("order.signals.notify")
    @patch("payments.services.notify")
    @patch("payments.views.get_payment_gateway")
    def test_guest_order_passes_phone_from_the_order_with_no_user(
        self, mock_get_gateway, mock_notify, _mock_status_notify
    ):
        gateway_returning(mock_get_gateway, verified=True)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(self.URL, {"Authority": AUTHORITY, "Status": "OK"})

        mock_notify.assert_called_once()
        user, event, context = mock_notify.call_args.args
        self.assertIsNone(user)
        self.assertEqual(event, "order_confirmed")
        self.assertEqual(context["phone_number"], GUEST_PHONE)
        self.assertEqual(context["email"], "guest@example.com")
        self.assertEqual(context["customer_name"], "Guest")

    @patch("notifications.sms.get_sms_provider")
    @patch("payments.views.get_payment_gateway")
    def test_guest_confirmation_sms_is_really_sent_to_the_orders_phone(
        self, mock_get_gateway, mock_get_provider
    ):
        """No notify mock: the full chain, user=None -> SMS channel ->
        recipient from the order -> rendered Persian text -> log row."""
        gateway_returning(mock_get_gateway, verified=True)
        provider = mock_get_provider.return_value
        provider.send.return_value = True

        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(self.URL, {"Authority": AUTHORITY, "Status": "OK"})

        provider.send.assert_called_once()
        phone, body = provider.send.call_args.args
        self.assertEqual(phone, GUEST_PHONE)
        self.assertIn(self.order.order_number, body)
        self.assertIn("Guest", body)
        self.assertNotIn("{", body)  # every placeholder rendered
        log = NotificationLog.objects.get(channel="sms")
        self.assertIsNone(log.user)
        self.assertEqual(log.event, "order_confirmed")
        self.assertEqual(log.recipient, GUEST_PHONE)
        self.assertEqual(log.status, "sent")

    @patch("notifications.sms.get_sms_provider")
    @patch("payments.views.get_payment_gateway")
    def test_failed_guest_payment_never_sends_an_order_confirmed_message(
        self, mock_get_gateway, mock_get_provider
    ):
        gateway_returning(mock_get_gateway, verified=False)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(self.URL, {"Authority": AUTHORITY, "Status": "OK"})

        # The order is cancelled (a status-change message may go out), but
        # nothing may say it was confirmed.
        self.assertFalse(
            NotificationLog.objects.filter(event="order_confirmed").exists()
        )


class RegisteredCustomerWithoutAccountPhoneTests(APITestCase):
    """A customer who signed up by email has no phone on their account but
    gave one at checkout — that's where the SMS must go."""

    @patch("notifications.sms.get_sms_provider")
    @patch("payments.views.get_payment_gateway")
    def test_sms_goes_to_the_phone_entered_at_checkout(
        self, mock_get_gateway, mock_get_provider
    ):
        user = make_user()  # phone_number is unset on the account
        order = make_order(user, total=1_000_000, phone=GUEST_PHONE)
        make_order_item(order, make_variant(stock=5), quantity=1)
        PaymentTransaction.objects.create(
            order=order,
            gateway="zarinpal",
            authority=AUTHORITY,
            amount=order.total,
            status=PaymentTransaction.Status.PENDING,
        )
        gateway_returning(mock_get_gateway, verified=True)
        provider = mock_get_provider.return_value
        provider.send.return_value = True

        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(
                "/api/payments/callback/zarinpal/",
                {"Authority": AUTHORITY, "Status": "OK"},
            )

        provider.send.assert_called_once()
        self.assertEqual(provider.send.call_args.args[0], GUEST_PHONE)
        self.assertEqual(NotificationLog.objects.get(channel="sms").user, user)


class ReconciliationPathNotificationTests(TestCase):
    """reconcile_stuck_payment_transactions recovers payments for customers
    who never returned from the gateway. They paid, so they must be told —
    which is why the notification can't live in PaymentCallbackView."""

    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user, total=1_000_000)
        make_order_item(self.order, make_variant(stock=5), quantity=2)

    @patch("order.signals.notify")
    @patch("payments.services.notify")
    @patch("payments.tasks.get_payment_gateway")
    def test_recovered_payment_sends_order_confirmed_once(
        self, mock_get_gateway, mock_notify, mock_status_notify
    ):
        make_stuck_transaction(self.order, age_minutes=45)
        mock_get_gateway.return_value.verify_payment.return_value = PaymentVerifyResult(
            success=True, ref_id="201202070", raw_response={"data": {"code": 100}}
        )

        with self.captureOnCommitCallbacks(execute=True):
            reconcile_stuck_payment_transactions()

        mock_notify.assert_called_once()
        user, event, context = mock_notify.call_args.args
        self.assertEqual(user, self.user)
        self.assertEqual(event, "order_confirmed")
        self.assertEqual(context["order_number"], self.order.order_number)
        self.assertEqual(context["order_total"], "100,000")
        mock_status_notify.assert_not_called()

    @patch("payments.services.notify")
    @patch("payments.tasks.get_payment_gateway")
    def test_stuck_transaction_the_gateway_says_was_not_paid_sends_nothing(
        self, mock_get_gateway, mock_notify
    ):
        make_stuck_transaction(self.order, age_minutes=45)
        mock_get_gateway.return_value.verify_payment.return_value = PaymentVerifyResult(
            success=False, ref_id="", raw_response={}
        )

        with self.captureOnCommitCallbacks(execute=True):
            reconcile_stuck_payment_transactions()

        mock_notify.assert_not_called()

    @patch("payments.services.notify")
    @patch("payments.tasks.get_payment_gateway")
    def test_transactions_below_the_age_threshold_send_nothing(
        self, mock_get_gateway, mock_notify
    ):
        make_stuck_transaction(self.order, age_minutes=1)

        with self.captureOnCommitCallbacks(execute=True):
            reconcile_stuck_payment_transactions()

        mock_get_gateway.assert_not_called()
        mock_notify.assert_not_called()
