"""
Tests for the order_status_changed hook (Task 8.1.1.2).

The key test is `test_saving_without_status_change_does_not_fire`: it
proves the pre_save/post_save change detection really distinguishes a
status change from any other save.
"""

from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from accounts.models import UserType
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from django.utils import translation
from django.utils.translation import trans_real
from notifications.models import NotificationLog
from order.models import Order
from order.signals import order_status_changed, suppress_status_notification
from rest_framework.test import APITestCase

User = get_user_model()

LOCALE_DIR = Path(settings.BASE_DIR) / "locale" / "fa" / "LC_MESSAGES"
PO, MO = LOCALE_DIR / "django.po", LOCALE_DIR / "django.mo"


def setUpModule():
    """The notification text carries the status's Persian label, so these
    tests need the compiled catalog. The .mo is gitignored and built at deploy
    time (see core/tests/test_persian_catalog.py, which does the same)."""
    if not MO.exists() or MO.stat().st_mtime < PO.stat().st_mtime:
        call_command("compilemessages", locale=["fa"], verbosity=0)
    trans_real._translations.clear()
    trans_real._default = None


@contextmanager
def capture_status_changes():
    """Collect (order_pk, previous_status, new_status) for every signal fired."""
    events = []

    def _receiver(sender, order, previous_status, **kwargs):
        # Snapshot values now: `order` is the live instance and may be
        # mutated by later saves in the same test.
        events.append((order.pk, previous_status, order.status))

    order_status_changed.connect(_receiver, weak=False)
    try:
        yield events
    finally:
        order_status_changed.disconnect(_receiver)


def make_order(user=None, status=Order.Status.PENDING, **overrides):
    data = dict(
        user=user,
        status=status,
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        phone="5550001234",
        shipping_address="1 Test St",
        shipping_city="Testville",
        shipping_state="CA",
        shipping_zip="90001",
        shipping_country="US",
        subtotal=100_000,
        shipping_cost=0,
        tax=0,
        total=100_000,
    )
    data.update(overrides)
    return Order.objects.create(**data)


class OrderStatusSignalTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="customer@example.com", password="TestPass123!"
        )
        self.admin = User.objects.create_user(
            email="admin@example.com", password="TestPass123!"
        )
        self.admin.type = UserType.ADMIN
        self.admin.save(update_fields=["type"])

    # ── created ──────────────────────────────────────────────────────────
    def test_creating_order_fires_exactly_once(self):
        with capture_status_changes() as events:
            order = make_order(user=self.customer)
        self.assertEqual(events, [(order.pk, None, Order.Status.PENDING)])

    # ── no status change ─────────────────────────────────────────────────
    def test_saving_without_status_change_does_not_fire(self):
        order = make_order(user=self.customer)
        with capture_status_changes() as events:
            order.notes = "Leave at the door"
            order.save()
            order.notes = "Ring the bell"
            order.save(update_fields=["notes"])
            Order.objects.get(pk=order.pk).save()  # fresh instance, full save
        self.assertEqual(events, [])

    def test_resaving_same_status_value_does_not_fire(self):
        order = make_order(user=self.customer, status=Order.Status.PROCESSING)
        with capture_status_changes() as events:
            order.status = Order.Status.PROCESSING
            order.save()
        self.assertEqual(events, [])

    # ── direct status changes ────────────────────────────────────────────
    def test_status_change_fires_once_with_previous_and_new(self):
        order = make_order(user=self.customer)
        with capture_status_changes() as events:
            order.status = Order.Status.PROCESSING
            order.save()
        self.assertEqual(
            events, [(order.pk, Order.Status.PENDING, Order.Status.PROCESSING)]
        )

    def test_status_change_with_update_fields_fires(self):
        order = make_order(user=self.customer)
        with capture_status_changes() as events:
            order.status = Order.Status.PROCESSING
            order.save(update_fields=["status"])
        self.assertEqual(len(events), 1)

    def test_back_to_back_changes_each_fire_once_with_correct_values(self):
        order = make_order(user=self.customer)
        with capture_status_changes() as events:
            order.status = Order.Status.PROCESSING
            order.save()
            order.status = Order.Status.SHIPPED
            order.save()
        self.assertEqual(
            events,
            [
                (order.pk, Order.Status.PENDING, Order.Status.PROCESSING),
                (order.pk, Order.Status.PROCESSING, Order.Status.SHIPPED),
            ],
        )

    def test_stale_instance_compares_against_database_not_memory(self):
        """previous_status is what's in the DB, even if this instance is stale."""
        order = make_order(user=self.customer)
        Order.objects.filter(pk=order.pk).update(status=Order.Status.PROCESSING)
        with capture_status_changes() as events:
            order.status = Order.Status.SHIPPED  # in-memory still says PENDING
            order.save()
        self.assertEqual(
            events, [(order.pk, Order.Status.PROCESSING, Order.Status.SHIPPED)]
        )

    # ── via the real endpoints ───────────────────────────────────────────
    def test_customer_cancellation_fires_once(self):
        order = make_order(user=self.customer, status=Order.Status.PROCESSING)
        self.client.force_authenticate(user=self.customer)
        with capture_status_changes() as events:
            res = self.client.patch(
                f"/api/orders/{order.pk}/", {"status": "cancelled"}, format="json"
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            events, [(order.pk, Order.Status.PROCESSING, Order.Status.CANCELLED)]
        )

    def test_repeat_customer_cancellation_does_not_fire_again(self):
        order = make_order(user=self.customer)
        self.client.force_authenticate(user=self.customer)
        self.client.patch(
            f"/api/orders/{order.pk}/", {"status": "cancelled"}, format="json"
        )
        with capture_status_changes() as events:
            self.client.patch(
                f"/api/orders/{order.pk}/", {"status": "cancelled"}, format="json"
            )
        self.assertEqual(events, [])

    def test_admin_status_change_fires_once(self):
        order = make_order(user=self.customer, status=Order.Status.PROCESSING)
        self.client.force_authenticate(user=self.admin)
        with capture_status_changes() as events:
            res = self.client.patch(
                f"/api/dashboard/admin/orders/{order.pk}/",
                {"status": "shipped"},
                format="json",
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            events, [(order.pk, Order.Status.PROCESSING, Order.Status.SHIPPED)]
        )

    def test_admin_cancellation_fires_once(self):
        order = make_order(user=self.customer)
        self.client.force_authenticate(user=self.admin)
        with capture_status_changes() as events:
            res = self.client.patch(
                f"/api/dashboard/admin/orders/{order.pk}/",
                {"status": "cancelled"},
                format="json",
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            events, [(order.pk, Order.Status.PENDING, Order.Status.CANCELLED)]
        )

    def test_rejected_admin_transition_does_not_fire(self):
        order = make_order(user=self.customer, status=Order.Status.DELIVERED)
        self.client.force_authenticate(user=self.admin)
        with capture_status_changes() as events:
            res = self.client.patch(
                f"/api/dashboard/admin/orders/{order.pk}/",
                {"status": "pending"},
                format="json",
            )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(events, [])

    # ── operational log line (kept alongside the real notification) ─────
    def test_receiver_still_logs_the_change(self):
        order = make_order(user=self.customer)
        with self.assertLogs("order.notifications", level="INFO") as logs:
            order.status = Order.Status.PROCESSING
            order.save()
        message = logs.records[0].getMessage()
        self.assertIn(order.order_number, message)
        self.assertIn("pending -> processing", message)


class OrderStatusNotificationTests(APITestCase):
    """The receiver that routes a status change through notify() (Epic 16).

    Django's TestCase wraps each test in a transaction, so on_commit callbacks
    only run inside `captureOnCommitCallbacks(execute=True)`.
    """

    def setUp(self):
        self.customer = User.objects.create_user(
            email="customer@example.com", password="TestPass123!"
        )

    def persian_label(self, status):
        with translation.override("fa"):
            return str(Order.Status(status).label)

    def test_status_change_calls_notify_with_the_expected_arguments(self):
        order = make_order(user=self.customer)
        with patch("order.signals.notify") as mock_notify:
            with self.captureOnCommitCallbacks(execute=True):
                order.status = Order.Status.PROCESSING
                order.save()

        mock_notify.assert_called_once()
        user, event, context = mock_notify.call_args.args
        self.assertEqual(user, self.customer)
        self.assertEqual(event, "order_status_changed")
        self.assertEqual(context["order_number"], order.order_number)
        self.assertEqual(context["old_status"], "pending")
        self.assertEqual(context["new_status"], "processing")

    def test_context_carries_persian_status_label_and_checkout_contact(self):
        order = make_order(user=self.customer)
        # The suite pins LANGUAGE_CODE to "en" (root conftest); the site
        # default in production is "fa", which is what the receiver uses.
        with self.settings(LANGUAGE_CODE="fa"):
            with patch("order.signals.notify") as mock_notify:
                with self.captureOnCommitCallbacks(execute=True):
                    order.status = Order.Status.SHIPPED
                    order.save()

        context = mock_notify.call_args.args[2]
        self.assertEqual(context["status"], self.persian_label("shipped"))
        # Really Persian, not an untranslated English label.
        self.assertRegex(context["status"], r"[\u0600-\u06FF]")
        self.assertEqual(context["customer_name"], "Jane")
        self.assertEqual(context["email"], "jane@example.com")
        self.assertEqual(context["phone_number"], "5550001234")

    def test_label_is_persian_even_when_the_active_language_is_english(self):
        order = make_order(user=self.customer)
        with self.settings(LANGUAGE_CODE="fa"):
            with patch("order.signals.notify") as mock_notify:
                with translation.override("en"):  # e.g. an English-browser admin
                    with self.captureOnCommitCallbacks(execute=True):
                        order.status = Order.Status.PROCESSING
                        order.save()

        label = mock_notify.call_args.args[2]["status"]
        self.assertEqual(label, self.persian_label("processing"))
        self.assertRegex(label, r"[\u0600-\u06FF]")

    def test_notify_is_deferred_until_the_transaction_commits(self):
        order = make_order(user=self.customer)
        with patch("order.signals.notify") as mock_notify:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                order.status = Order.Status.PROCESSING
                order.save()
                mock_notify.assert_not_called()  # nothing sent yet
            self.assertEqual(len(callbacks), 1)
            for callback in callbacks:
                callback()
        mock_notify.assert_called_once()

    def test_rolled_back_status_change_sends_nothing(self):
        order = make_order(user=self.customer)
        with patch("order.signals.notify") as mock_notify:
            with self.captureOnCommitCallbacks(execute=True):
                try:
                    with transaction.atomic():
                        order.status = Order.Status.CANCELLED
                        order.save()
                        raise RuntimeError("payment finalisation failed")
                except RuntimeError:
                    pass
        mock_notify.assert_not_called()

    def test_context_is_snapshotted_at_signal_time(self):
        order = make_order(user=self.customer)
        with patch("order.signals.notify") as mock_notify:
            with self.captureOnCommitCallbacks(execute=True):
                order.status = Order.Status.PROCESSING
                order.save()
                # A later save in the same transaction must not rewrite what
                # the first change's notification says.
                order.status = Order.Status.SHIPPED
                order.save()

        sent = [c.args[2]["new_status"] for c in mock_notify.call_args_list]
        self.assertEqual(sent, ["processing", "shipped"])

    def test_each_change_notifies_once(self):
        order = make_order(user=self.customer)
        with patch("order.signals.notify") as mock_notify:
            with self.captureOnCommitCallbacks(execute=True):
                order.save()  # no status change
            self.assertEqual(mock_notify.call_count, 0)
            with self.captureOnCommitCallbacks(execute=True):
                order.status = Order.Status.PROCESSING
                order.save()
        self.assertEqual(mock_notify.call_count, 1)

    def test_creating_an_order_does_not_send_a_status_change_notification(self):
        with patch("order.signals.notify") as mock_notify:
            with self.captureOnCommitCallbacks(execute=True):
                make_order(user=self.customer)
        mock_notify.assert_not_called()

    def test_guest_order_is_notified_via_its_checkout_contact_details(self):
        order = make_order(user=None)
        with patch("order.signals.notify") as mock_notify:
            with self.captureOnCommitCallbacks(execute=True):
                order.status = Order.Status.PROCESSING
                order.save()

        user, _event, context = mock_notify.call_args.args
        self.assertIsNone(user)
        self.assertEqual(context["email"], "jane@example.com")
        self.assertEqual(context["phone_number"], "5550001234")

    def test_real_notify_end_to_end_sends_sms_and_logs_it(self):
        """No mocks: console SMS provider, template seeded by migration."""
        order = make_order(user=self.customer)
        with self.captureOnCommitCallbacks(execute=True):
            order.status = Order.Status.PROCESSING
            order.save()

        log = NotificationLog.objects.get(channel="sms")
        self.assertEqual(log.event, "order_status_changed")
        self.assertEqual(log.recipient, "5550001234")
        self.assertEqual(log.status, "sent")
        self.assertEqual(log.user, self.customer)

    def test_order_opted_out_of_order_updates_gets_no_notification(self):
        self.customer.profile.order_updates = False
        self.customer.profile.save()
        order = make_order(user=self.customer)
        with self.captureOnCommitCallbacks(execute=True):
            order.status = Order.Status.PROCESSING
            order.save()
        self.assertEqual(NotificationLog.objects.count(), 0)

    def test_a_failing_notification_does_not_break_the_status_change(self):
        order = make_order(user=self.customer)
        with patch(
            "notifications.sms.get_sms_provider", side_effect=RuntimeError("down")
        ):
            with self.assertLogs("notifications", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    order.status = Order.Status.PROCESSING
                    order.save()

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PROCESSING)
        self.assertEqual(NotificationLog.objects.get(channel="sms").status, "failed")

    # ── suppress_status_notification (used on the payment-success path) ──

    def test_suppressed_save_sends_no_status_change_notification(self):
        order = make_order(user=self.customer)
        with patch("order.signals.notify") as mock_notify:
            with self.captureOnCommitCallbacks(execute=True):
                with suppress_status_notification(order):
                    order.status = Order.Status.PROCESSING
                    order.save()

        mock_notify.assert_not_called()

    def test_suppression_is_scoped_to_the_with_block(self):
        order = make_order(user=self.customer)
        with suppress_status_notification(order):
            pass
        with patch("order.signals.notify") as mock_notify:
            with self.captureOnCommitCallbacks(execute=True):
                order.status = Order.Status.PROCESSING
                order.save()

        mock_notify.assert_called_once()

    def test_suppression_is_reset_even_if_the_block_raises(self):
        order = make_order(user=self.customer)
        with self.assertRaises(RuntimeError):
            with suppress_status_notification(order):
                raise RuntimeError("boom")

        self.assertFalse(order._suppress_status_notification)

    def test_suppression_only_affects_the_given_order(self):
        order = make_order(user=self.customer)
        other = make_order(user=self.customer)
        with patch("order.signals.notify") as mock_notify:
            with self.captureOnCommitCallbacks(execute=True):
                with suppress_status_notification(order):
                    other.status = Order.Status.PROCESSING
                    other.save()

        mock_notify.assert_called_once()

    def test_admin_style_manual_pending_to_processing_still_notifies(self):
        """The state machine allows PENDING -> PROCESSING by hand; that
        isn't the payment path, so the customer is still told."""
        order = make_order(user=self.customer)
        with patch("order.signals.notify") as mock_notify:
            with self.captureOnCommitCallbacks(execute=True):
                order.status = Order.Status.PROCESSING
                order.save(update_fields=["status"])

        mock_notify.assert_called_once()
        self.assertEqual(mock_notify.call_args.args[2]["old_status"], "pending")
        self.assertEqual(mock_notify.call_args.args[2]["new_status"], "processing")
