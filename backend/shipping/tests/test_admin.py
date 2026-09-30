from decimal import Decimal
from unittest.mock import patch

from accounts.models import UserType
from dashboard.models import IranProvince
from django.contrib.admin import helpers
from django.test import Client, TestCase
from order.models import Order
from order.tests.factories import make_user
from shipping.models import Shipment, ShippingCarrier
from shipping.providers.base import ShipmentCreateResult

BOOK_URL = "/admin/shipping/shipment/"


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


class BookShipmentActionTests(TestCase):
    def setUp(self):
        self.admin_user = make_user(
            email="admin@example.com", type=UserType.ADMIN, is_staff=True
        )
        self.admin_user.is_superuser = True
        self.admin_user.save(update_fields=["is_superuser"])

        self.customer = make_user(email="buyer@example.com")
        self.carrier = ShippingCarrier.objects.get(code=ShippingCarrier.Code.POST)

        self.client = Client()
        self.client.force_login(self.admin_user)

    def _post_action(self, shipments):
        data = {
            helpers.ACTION_CHECKBOX_NAME: [str(s.pk) for s in shipments],
            "action": "book_shipment",
            "index": "0",
        }
        return self.client.post(BOOK_URL, data, follow=True)

    def test_successful_booking_populates_tracking_number_and_label_url(self):
        order = make_order(self.customer, order_number="ORD-SUCCESS1")
        shipment = Shipment.objects.create(order=order, carrier=self.carrier)

        with patch("shipping.admin.get_carrier_provider") as mock_get_provider:
            mock_provider = mock_get_provider.return_value
            mock_provider.create_shipment.return_value = ShipmentCreateResult(
                success=True,
                tracking_number="TRK987654",
                label_url="https://example.test/labels/TRK987654",
            )

            self._post_action([shipment])

        mock_get_provider.assert_called_once_with(self.carrier.code)
        mock_provider.create_shipment.assert_called_once_with(
            order=order,
            destination={
                "address": order.shipping_address,
                "city": order.shipping_city,
                "province": order.shipping_state,
                "postal_code": order.shipping_zip,
            },
        )

        shipment.refresh_from_db()
        self.assertEqual(shipment.tracking_number, "TRK987654")
        self.assertEqual(shipment.label_url, "https://example.test/labels/TRK987654")
        self.assertEqual(shipment.status, Shipment.Status.PENDING)

    def test_failed_booking_leaves_tracking_fields_blank_and_shows_error_message(self):
        order = make_order(self.customer, order_number="ORD-FAILURE1")
        shipment = Shipment.objects.create(order=order, carrier=self.carrier)

        with patch("shipping.admin.get_carrier_provider") as mock_get_provider:
            mock_provider = mock_get_provider.return_value
            mock_provider.create_shipment.return_value = ShipmentCreateResult(
                success=False,
                error_message="Destination out of range",
            )

            response = self._post_action([shipment])

        shipment.refresh_from_db()
        self.assertEqual(shipment.tracking_number, "")
        self.assertEqual(shipment.label_url, "")

        messages = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any(
                "ORD-FAILURE1" in m and "Destination out of range" in m
                for m in messages
            )
        )

    def test_shipment_with_a_tracking_number_already_is_skipped(self):
        # Already booked — re-running the action must not call the
        # carrier API again for it.
        order = make_order(self.customer, order_number="ORD-ALREADY1")
        shipment = Shipment.objects.create(
            order=order, carrier=self.carrier, tracking_number="EXISTING123"
        )

        with patch("shipping.admin.get_carrier_provider") as mock_get_provider:
            self._post_action([shipment])

        mock_get_provider.assert_not_called()
        shipment.refresh_from_db()
        self.assertEqual(shipment.tracking_number, "EXISTING123")

    def test_mixed_success_and_failure_in_one_batch_are_handled_independently(self):
        success_order = make_order(self.customer, order_number="ORD-MIXOK01")
        failure_order = make_order(self.customer, order_number="ORD-MIXBAD1")
        success_shipment = Shipment.objects.create(
            order=success_order, carrier=self.carrier
        )
        failure_shipment = Shipment.objects.create(
            order=failure_order, carrier=self.carrier
        )

        def fake_create_shipment(order, destination):
            if order.order_number == "ORD-MIXOK01":
                return ShipmentCreateResult(success=True, tracking_number="OK123")
            return ShipmentCreateResult(success=False, error_message="Carrier down")

        with patch("shipping.admin.get_carrier_provider") as mock_get_provider:
            mock_get_provider.return_value.create_shipment.side_effect = (
                fake_create_shipment
            )
            response = self._post_action([success_shipment, failure_shipment])

        success_shipment.refresh_from_db()
        failure_shipment.refresh_from_db()
        self.assertEqual(success_shipment.tracking_number, "OK123")
        self.assertEqual(failure_shipment.tracking_number, "")

        messages = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("ORD-MIXBAD1" in m and "Carrier down" in m for m in messages)
        )
