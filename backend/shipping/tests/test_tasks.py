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
from unittest.mock import patch

from dashboard.models import IranProvince
from django.test import TestCase
from django.utils import timezone
from order.models import Order
from order.tests.factories import make_user
from shipping.models import Shipment, ShippingCarrier
from shipping.providers.base import TrackingResult
from shipping.tasks import poll_shipment_tracking


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
        subtotal=Decimal("100.00"),
        shipping_cost=Decimal("9.99"),
        tax=Decimal("10.00"),
        total=Decimal("119.99"),
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
