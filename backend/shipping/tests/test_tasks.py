"""
Tests for shipping.tasks.poll_shipment_tracking (Task 7.2.2.2).

Mirrors payments/tests/test_tasks.py's conventions: TestCase, the task
function called directly (not via .delay()), and the carrier-resolution
factory mocked out. get_carrier_provider is imported LAZILY inside the
task body (`from .providers import get_carrier_provider`), matching the
task's own given implementation — so the patch target is the true source,
shipping.providers.get_carrier_provider, not shipping.tasks (which has no
such module-level name to patch).
"""

from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from dashboard.models import IranProvince
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone, translation
from django.utils.translation import trans_real
from notifications.models import NotificationLog
from order.models import Order
from order.tests.factories import make_user
from shipping.models import Shipment, ShippingCarrier
from shipping.providers.base import TrackingResult
from shipping.tasks import SHIPMENT_STATUSES_TO_NOTIFY, poll_shipment_tracking

LOCALE_DIR = Path(settings.BASE_DIR) / "locale" / "fa" / "LC_MESSAGES"
PO, MO = LOCALE_DIR / "django.po", LOCALE_DIR / "django.mo"


def setUpModule():
    """The shipping-update text carries the status's Persian label, so these
    tests need the compiled catalog. The .mo is gitignored and built at deploy
    time (core/tests/test_persian_catalog.py does the same)."""
    if not MO.exists() or MO.stat().st_mtime < PO.stat().st_mtime:
        call_command("compilemessages", locale=["fa"], verbosity=0)
    trans_real._translations.clear()
    trans_real._default = None


def make_order(user, **overrides):
    fields = dict(
        user=user,
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        phone="555-1234",
        shipping_address="42 Elm Street",
        shipping_city="Tehran",
        shipping_state=IranProvince.TEHRAN,
        shipping_zip="1234567890",
        shipping_country="IR",
        subtotal=1_000_000,
        shipping_cost=99_900,
        tax=100_000,
        total=1_199_900,
    )
    fields.update(overrides)
    return Order.objects.create(**fields)


class PollShipmentTrackingTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.carrier = ShippingCarrier.objects.get(code=ShippingCarrier.Code.POST)

    def make_shipment(self, *, order_number=None, **overrides):
        fields = dict(
            order=(
                make_order(self.user, order_number=order_number)
                if order_number
                else make_order(self.user)
            ),
            carrier=self.carrier,
            tracking_number="TRK123",
            status=Shipment.Status.PENDING,
        )
        fields.update(overrides)
        return Shipment.objects.create(**fields)

    def test_new_status_updates_the_shipment_and_sets_last_tracked_at(self):
        shipment = self.make_shipment(status=Shipment.Status.PENDING)
        self.assertIsNone(shipment.last_tracked_at)

        with patch("shipping.providers.get_carrier_provider") as mock_get_provider:
            mock_get_provider.return_value.track.return_value = TrackingResult(
                success=True, status=Shipment.Status.IN_TRANSIT
            )
            before = timezone.now()
            result = poll_shipment_tracking()

        mock_get_provider.assert_called_once_with(self.carrier.code)
        mock_get_provider.return_value.track.assert_called_once_with("TRK123")

        shipment.refresh_from_db()
        self.assertEqual(shipment.status, Shipment.Status.IN_TRANSIT)
        self.assertIsNotNone(shipment.last_tracked_at)
        self.assertGreaterEqual(shipment.last_tracked_at, before)
        self.assertEqual(result, "Updated 1 shipment(s).")

    def test_same_status_as_currently_recorded_does_not_resave(self):
        # Explicit decision (per the task's own given implementation):
        # a no-op status is NOT re-saved — last_tracked_at is only
        # touched when the status actually changes, so it staying None
        # here is the correct, intentional behavior, not an oversight.
        shipment = self.make_shipment(status=Shipment.Status.IN_TRANSIT)

        with patch("shipping.providers.get_carrier_provider") as mock_get_provider:
            mock_get_provider.return_value.track.return_value = TrackingResult(
                success=True, status=Shipment.Status.IN_TRANSIT
            )
            result = poll_shipment_tracking()

        shipment.refresh_from_db()
        self.assertEqual(shipment.status, Shipment.Status.IN_TRANSIT)
        self.assertIsNone(shipment.last_tracked_at)
        self.assertEqual(result, "Updated 0 shipment(s).")

    def test_transition_to_delivered_also_updates_the_order_status(self):
        shipment = self.make_shipment(status=Shipment.Status.OUT_FOR_DELIVERY)
        order = shipment.order
        self.assertNotEqual(order.status, Order.Status.DELIVERED)

        with patch("shipping.providers.get_carrier_provider") as mock_get_provider:
            mock_get_provider.return_value.track.return_value = TrackingResult(
                success=True, status=Shipment.Status.DELIVERED
            )
            poll_shipment_tracking()

        shipment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(shipment.status, Shipment.Status.DELIVERED)
        self.assertEqual(order.status, Order.Status.DELIVERED)

    def test_transition_to_a_non_delivered_status_does_not_touch_order_status(self):
        shipment = self.make_shipment(status=Shipment.Status.PENDING)
        order = shipment.order
        original_order_status = order.status

        with patch("shipping.providers.get_carrier_provider") as mock_get_provider:
            mock_get_provider.return_value.track.return_value = TrackingResult(
                success=True, status=Shipment.Status.OUT_FOR_DELIVERY
            )
            poll_shipment_tracking()

        order.refresh_from_db()
        self.assertEqual(order.status, original_order_status)

    def test_shipment_already_delivered_is_excluded_from_polling(self):
        self.make_shipment(status=Shipment.Status.DELIVERED)

        with patch("shipping.providers.get_carrier_provider") as mock_get_provider:
            result = poll_shipment_tracking()

        mock_get_provider.assert_not_called()
        self.assertEqual(result, "Updated 0 shipment(s).")

    def test_shipment_already_failed_is_excluded_from_polling(self):
        self.make_shipment(status=Shipment.Status.FAILED)

        with patch("shipping.providers.get_carrier_provider") as mock_get_provider:
            poll_shipment_tracking()

        mock_get_provider.assert_not_called()

    def test_shipment_with_no_tracking_number_yet_is_excluded_from_polling(self):
        # Not yet booked with the carrier — nothing to poll.
        self.make_shipment(tracking_number="", status=Shipment.Status.PENDING)

        with patch("shipping.providers.get_carrier_provider") as mock_get_provider:
            poll_shipment_tracking()

        mock_get_provider.assert_not_called()

    def test_failed_track_call_leaves_the_shipment_untouched_and_does_not_raise(self):
        shipment = self.make_shipment(status=Shipment.Status.PENDING)

        with patch("shipping.providers.get_carrier_provider") as mock_get_provider:
            mock_get_provider.return_value.track.return_value = TrackingResult(
                success=False, error_message="Carrier API timed out"
            )
            # Must not raise — a transient polling failure is expected to
            # be retried on the next scheduled run, not crash the task.
            result = poll_shipment_tracking()

        shipment.refresh_from_db()
        self.assertEqual(shipment.status, Shipment.Status.PENDING)
        self.assertIsNone(shipment.last_tracked_at)
        self.assertEqual(result, "Updated 0 shipment(s).")

    def test_one_failure_does_not_prevent_other_shipments_from_updating(self):
        failing = self.make_shipment(
            order_number="ORD-FAIL0001",
            tracking_number="FAIL1",
            status=Shipment.Status.PENDING,
        )
        succeeding = self.make_shipment(
            order_number="ORD-OK00001",
            tracking_number="OK1",
            status=Shipment.Status.PENDING,
        )

        def fake_track(tracking_number):
            if tracking_number == "FAIL1":
                return TrackingResult(success=False, error_message="boom")
            return TrackingResult(success=True, status=Shipment.Status.IN_TRANSIT)

        with patch("shipping.providers.get_carrier_provider") as mock_get_provider:
            mock_get_provider.return_value.track.side_effect = fake_track
            result = poll_shipment_tracking()

        failing.refresh_from_db()
        succeeding.refresh_from_db()
        self.assertEqual(failing.status, Shipment.Status.PENDING)
        self.assertEqual(succeeding.status, Shipment.Status.IN_TRANSIT)
        self.assertEqual(result, "Updated 1 shipment(s).")


class ShipmentUpdateNotificationTests(TestCase):
    """SHIPPING_UPDATE notifications from poll_shipment_tracking (Epic 16).

    Policy under test: out_for_delivery, delivered and failed notify the
    customer; in_transit and pending do not (see SHIPMENT_STATUSES_TO_NOTIFY).
    Django's TestCase wraps each test in a transaction, so on_commit callbacks
    only run inside `captureOnCommitCallbacks(execute=True)`.
    """

    def setUp(self):
        self.user = make_user()
        self.carrier = ShippingCarrier.objects.get(code=ShippingCarrier.Code.POST)

    def make_shipment(self, *, user="default", **overrides):
        fields = dict(
            order=make_order(self.user if user == "default" else user),
            carrier=self.carrier,
            tracking_number="TRK123",
            status=Shipment.Status.PENDING,
        )
        fields.update(overrides)
        return Shipment.objects.create(**fields)

    def poll(self, new_status, *, success=True):
        """Run the task with the carrier reporting `new_status`; callbacks
        registered with on_commit are executed (as a real commit would)."""
        with patch("shipping.providers.get_carrier_provider") as mock_get_provider:
            mock_get_provider.return_value.track.return_value = TrackingResult(
                success=success, status=new_status if success else ""
            )
            with self.captureOnCommitCallbacks(execute=True):
                return poll_shipment_tracking()

    # ── 1. notifying statuses → notify() with the right details ──────────

    @patch("notifications.services.notify")
    def test_change_to_each_notifying_status_calls_notify_with_correct_details(
        self, mock_notify
    ):
        expectations = [
            (Shipment.Status.IN_TRANSIT, Shipment.Status.OUT_FOR_DELIVERY),
            (Shipment.Status.OUT_FOR_DELIVERY, Shipment.Status.DELIVERED),
            (Shipment.Status.IN_TRANSIT, Shipment.Status.FAILED),
        ]
        for old_status, new_status in expectations:
            with self.subTest(new_status=new_status):
                mock_notify.reset_mock()
                shipment = self.make_shipment(
                    status=old_status, tracking_number=f"TRK-{new_status}"
                )

                with self.settings(LANGUAGE_CODE="fa"):
                    self.poll(new_status)

                mock_notify.assert_called_once()
                user, event, context = mock_notify.call_args.args
                self.assertEqual(user, self.user)
                self.assertEqual(event, "shipping_update")
                self.assertEqual(context["order_number"], shipment.order.order_number)
                self.assertEqual(context["tracking_number"], f"TRK-{new_status}")
                with translation.override("fa"):
                    expected_label = str(Shipment.Status(new_status).label)
                self.assertEqual(context["shipping_status"], expected_label)
                # Really Persian, not an untranslated English label.
                self.assertRegex(context["shipping_status"], r"[\u0600-\u06FF]")
                self.assertEqual(context["customer_name"], "Jane")
                self.assertEqual(context["email"], "jane@example.com")
                self.assertEqual(context["phone_number"], "555-1234")
                shipment.delete()

    @patch("notifications.services.notify")
    def test_label_is_persian_even_when_the_worker_language_is_english(
        self, mock_notify
    ):
        self.make_shipment(status=Shipment.Status.IN_TRANSIT)

        with self.settings(LANGUAGE_CODE="fa"):
            with translation.override("en"):
                self.poll(Shipment.Status.OUT_FOR_DELIVERY)

        with translation.override("fa"):
            expected = str(Shipment.Status.OUT_FOR_DELIVERY.label)
        self.assertEqual(mock_notify.call_args.args[2]["shipping_status"], expected)

    @patch("notifications.services.notify")
    def test_notification_is_deferred_until_the_transaction_commits(self, mock_notify):
        self.make_shipment(status=Shipment.Status.IN_TRANSIT)

        with patch("shipping.providers.get_carrier_provider") as mock_get_provider:
            mock_get_provider.return_value.track.return_value = TrackingResult(
                success=True, status=Shipment.Status.OUT_FOR_DELIVERY
            )
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                poll_shipment_tracking()
                mock_notify.assert_not_called()

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        mock_notify.assert_called_once()

    @patch("notifications.services.notify")
    def test_each_changed_shipment_is_notified_separately(self, mock_notify):
        first = self.make_shipment(
            status=Shipment.Status.IN_TRANSIT, tracking_number="A1"
        )
        second = self.make_shipment(
            user=make_user(email="other@example.com"),
            status=Shipment.Status.IN_TRANSIT,
            tracking_number="B2",
        )

        self.poll(Shipment.Status.OUT_FOR_DELIVERY)

        self.assertEqual(mock_notify.call_count, 2)
        notified = {c.args[2]["order_number"] for c in mock_notify.call_args_list}
        self.assertEqual(
            notified, {first.order.order_number, second.order.order_number}
        )

    # ── 2. no change → no duplicate ──────────────────────────────────────

    @patch("notifications.services.notify")
    def test_same_status_does_not_notify_again(self, mock_notify):
        self.make_shipment(status=Shipment.Status.OUT_FOR_DELIVERY)

        result = self.poll(Shipment.Status.OUT_FOR_DELIVERY)

        self.assertEqual(result, "Updated 0 shipment(s).")
        mock_notify.assert_not_called()

    @patch("notifications.services.notify")
    def test_repeated_polls_notify_exactly_once_per_change(self, mock_notify):
        self.make_shipment(status=Shipment.Status.IN_TRANSIT)

        for _ in range(3):
            self.poll(Shipment.Status.OUT_FOR_DELIVERY)

        self.assertEqual(mock_notify.call_count, 1)

    @patch("notifications.services.notify")
    def test_failed_track_call_does_not_notify(self, mock_notify):
        shipment = self.make_shipment(status=Shipment.Status.IN_TRANSIT)

        self.poll("", success=False)

        mock_notify.assert_not_called()
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, Shipment.Status.IN_TRANSIT)

    # ── 3. excluded statuses: updated, but silent ────────────────────────

    @patch("notifications.services.notify")
    def test_transition_to_in_transit_updates_the_shipment_but_does_not_notify(
        self, mock_notify
    ):
        shipment = self.make_shipment(status=Shipment.Status.PENDING)

        result = self.poll(Shipment.Status.IN_TRANSIT)

        shipment.refresh_from_db()
        self.assertEqual(shipment.status, Shipment.Status.IN_TRANSIT)
        self.assertIsNotNone(shipment.last_tracked_at)
        self.assertEqual(result, "Updated 1 shipment(s).")
        mock_notify.assert_not_called()

    @patch("notifications.services.notify")
    def test_transition_to_pending_updates_the_shipment_but_does_not_notify(
        self, mock_notify
    ):
        shipment = self.make_shipment(status=Shipment.Status.IN_TRANSIT)

        self.poll(Shipment.Status.PENDING)

        shipment.refresh_from_db()
        self.assertEqual(shipment.status, Shipment.Status.PENDING)
        mock_notify.assert_not_called()

    def test_notification_policy_is_explicit_and_valid(self):
        self.assertEqual(
            SHIPMENT_STATUSES_TO_NOTIFY,
            {
                Shipment.Status.OUT_FOR_DELIVERY,
                Shipment.Status.DELIVERED,
                Shipment.Status.FAILED,
            },
        )
        self.assertTrue(SHIPMENT_STATUSES_TO_NOTIFY <= set(Shipment.Status.values))
        self.assertNotIn(Shipment.Status.IN_TRANSIT, SHIPMENT_STATUSES_TO_NOTIFY)
        self.assertNotIn(Shipment.Status.PENDING, SHIPMENT_STATUSES_TO_NOTIFY)

    # ── delivered: one message, not two ──────────────────────────────────

    @patch("order.signals.notify")
    @patch("notifications.services.notify")
    def test_delivery_sends_the_shipping_update_but_not_a_second_status_message(
        self, mock_shipping_notify, mock_status_notify
    ):
        shipment = self.make_shipment(status=Shipment.Status.OUT_FOR_DELIVERY)

        self.poll(Shipment.Status.DELIVERED)

        mock_shipping_notify.assert_called_once()
        mock_status_notify.assert_not_called()
        shipment.order.refresh_from_db()
        self.assertEqual(shipment.order.status, Order.Status.DELIVERED)

    @patch("order.signals.notify")
    @patch("notifications.services.notify")
    def test_order_status_is_unchanged_for_non_delivered_notifying_statuses(
        self, mock_shipping_notify, mock_status_notify
    ):
        shipment = self.make_shipment(status=Shipment.Status.IN_TRANSIT)
        original = shipment.order.status

        self.poll(Shipment.Status.OUT_FOR_DELIVERY)

        shipment.order.refresh_from_db()
        self.assertEqual(shipment.order.status, original)
        mock_status_notify.assert_not_called()

    @patch("order.signals.notify")
    @patch("notifications.services.notify")
    def test_delivery_still_sends_the_status_message_if_delivered_is_not_notified(
        self, mock_shipping_notify, mock_status_notify
    ):
        """The generic message is only suppressed because the shipping update
        replaces it; if the policy ever drops `delivered`, it must come back."""
        shipment = self.make_shipment(status=Shipment.Status.OUT_FOR_DELIVERY)

        with patch(
            "shipping.tasks.SHIPMENT_STATUSES_TO_NOTIFY",
            frozenset({"out_for_delivery", "failed"}),
        ):
            self.poll(Shipment.Status.DELIVERED)

        mock_shipping_notify.assert_not_called()
        mock_status_notify.assert_called_once()
        shipment.order.refresh_from_db()
        self.assertEqual(shipment.order.status, Order.Status.DELIVERED)

    # ── guests and the real notify() chain ───────────────────────────────

    @patch("notifications.services.notify")
    def test_guest_order_is_notified_via_its_checkout_contact_details(
        self, mock_notify
    ):
        self.make_shipment(
            user=None,
            status=Shipment.Status.IN_TRANSIT,
        )

        self.poll(Shipment.Status.OUT_FOR_DELIVERY)

        user, _event, context = mock_notify.call_args.args
        self.assertIsNone(user)
        self.assertEqual(context["phone_number"], "555-1234")
        self.assertEqual(context["email"], "jane@example.com")

    @patch("notifications.sms.get_sms_provider")
    def test_real_notify_sends_the_sms_with_the_rendered_message(
        self, mock_get_provider
    ):
        """No notify mock: poll -> notify() -> template -> SMS provider -> log."""
        provider = mock_get_provider.return_value
        provider.send.return_value = True
        shipment = self.make_shipment(
            user=None, status=Shipment.Status.IN_TRANSIT, tracking_number="TRK-777"
        )

        with self.settings(LANGUAGE_CODE="fa"):
            self.poll(Shipment.Status.OUT_FOR_DELIVERY)

        provider.send.assert_called_once()
        phone, body = provider.send.call_args.args
        self.assertEqual(phone, "555-1234")
        self.assertIn(shipment.order.order_number, body)
        self.assertIn("TRK-777", body)
        self.assertIn("Jane", body)
        self.assertNotIn("{", body)  # every placeholder rendered
        log = NotificationLog.objects.get(channel="sms")
        self.assertEqual(log.event, "shipping_update")
        self.assertEqual(log.status, "sent")
        self.assertIsNone(log.user)

    @patch("notifications.sms.get_sms_provider")
    def test_a_failing_sms_does_not_stop_the_polling_loop(self, mock_get_provider):
        mock_get_provider.return_value.send.side_effect = RuntimeError("sms down")
        first = self.make_shipment(
            status=Shipment.Status.IN_TRANSIT, tracking_number="A1"
        )
        second = self.make_shipment(
            user=make_user(email="other@example.com"),
            status=Shipment.Status.IN_TRANSIT,
            tracking_number="B2",
        )

        with self.assertLogs("notifications", level="ERROR"):
            result = self.poll(Shipment.Status.OUT_FOR_DELIVERY)

        self.assertEqual(result, "Updated 2 shipment(s).")
        for shipment in (first, second):
            shipment.refresh_from_db()
            self.assertEqual(shipment.status, Shipment.Status.OUT_FOR_DELIVERY)
