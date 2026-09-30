from decimal import Decimal

from dashboard.models import IranProvince
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from order.models import Order
from order.tests.factories import make_user
from shipping.models import Shipment, ShippingCarrier, ShippingRate


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


class ShippingCarrierModelTests(TestCase):
    def setUp(self):
        # The 0002 data migration already seeds the four carrier codes,
        # and `code` is unique — clear them so these tests can freely
        # create rows against any of the Code choices.
        ShippingCarrier.objects.all().delete()

    def test_create_shipping_carrier(self):
        carrier = ShippingCarrier.objects.create(
            code=ShippingCarrier.Code.POST,
            display_name="Iran Post",
        )
        self.assertEqual(ShippingCarrier.objects.count(), 1)
        self.assertEqual(carrier.code, ShippingCarrier.Code.POST)
        self.assertEqual(carrier.display_name, "Iran Post")

    def test_str_returns_display_name(self):
        carrier = ShippingCarrier.objects.create(
            code=ShippingCarrier.Code.TIPAX,
            display_name="Tipax",
        )
        self.assertEqual(str(carrier), "Tipax")


class ShippingCarrierSeedMigrationTests(TestCase):
    """
    Confirms the 0002 data migration seeded exactly the four expected
    carrier rows, all inactive by default (a carrier shouldn't be
    selectable at checkout until its Phase 7.2 integration is done and
    an admin deliberately activates it).
    """

    def test_seed_migration_creates_exactly_four_inactive_carriers(self):
        self.assertEqual(ShippingCarrier.objects.count(), 4)

        expected_codes = {
            ShippingCarrier.Code.POST,
            ShippingCarrier.Code.TIPAX,
            ShippingCarrier.Code.SNAPBOX,
            ShippingCarrier.Code.ALOPEYK,
        }
        actual_codes = set(ShippingCarrier.objects.values_list("code", flat=True))
        self.assertEqual(actual_codes, expected_codes)

        self.assertFalse(ShippingCarrier.objects.filter(is_active=True).exists())


class ShippingRateFindRateTests(TestCase):
    def setUp(self):
        # 0002 already seeds all four carrier rows (inactive) — reuse
        # one rather than creating a new one, since `code` is unique.
        self.carrier = ShippingCarrier.objects.get(code=ShippingCarrier.Code.POST)

    def test_find_rate_returns_rate_within_bracket(self):
        rate = ShippingRate.objects.create(
            carrier=self.carrier,
            province=IranProvince.TEHRAN,
            min_weight_g=0,
            max_weight_g=1000,
            price=Decimal("50000.00"),
        )

        found = ShippingRate.find_rate(
            carrier=self.carrier,
            province=IranProvince.TEHRAN,
            city="",
            weight_g=500,
        )

        self.assertEqual(found, rate)

    def test_find_rate_returns_none_when_weight_outside_all_brackets(self):
        ShippingRate.objects.create(
            carrier=self.carrier,
            province=IranProvince.TEHRAN,
            min_weight_g=0,
            max_weight_g=1000,
            price=Decimal("50000.00"),
        )

        found = ShippingRate.find_rate(
            carrier=self.carrier,
            province=IranProvince.TEHRAN,
            city="",
            weight_g=5000,
        )

        # Callers (Task 7.1.1.4) must handle None gracefully — e.g.
        # falling back to a default cost or surfacing "not available
        # for this destination" — rather than assuming a rate always
        # exists and crashing on attribute access.
        self.assertIsNone(found)

    def test_find_rate_returns_none_when_no_rate_configured_for_province(self):
        # No ShippingRate rows created at all for this carrier/province.
        found = ShippingRate.find_rate(
            carrier=self.carrier,
            province=IranProvince.YAZD,
            city="",
            weight_g=500,
        )

        self.assertIsNone(found)

    def test_find_rate_prefers_city_specific_over_province_wide(self):
        province_wide = ShippingRate.objects.create(
            carrier=self.carrier,
            province=IranProvince.TEHRAN,
            city="",
            min_weight_g=0,
            max_weight_g=1000,
            price=Decimal("50000.00"),
        )
        city_specific = ShippingRate.objects.create(
            carrier=self.carrier,
            province=IranProvince.TEHRAN,
            city="Tehran",
            min_weight_g=0,
            max_weight_g=1000,
            price=Decimal("20000.00"),
        )

        found = ShippingRate.find_rate(
            carrier=self.carrier,
            province=IranProvince.TEHRAN,
            city="Tehran",
            weight_g=500,
        )

        self.assertEqual(found, city_specific)
        self.assertNotEqual(found, province_wide)

    def test_find_rate_never_returns_inactive_rate(self):
        ShippingRate.objects.create(
            carrier=self.carrier,
            province=IranProvince.TEHRAN,
            min_weight_g=0,
            max_weight_g=1000,
            price=Decimal("50000.00"),
            is_active=False,
        )

        found = ShippingRate.find_rate(
            carrier=self.carrier,
            province=IranProvince.TEHRAN,
            city="",
            weight_g=500,
        )

        self.assertIsNone(found)


class ShippingRateCleanTests(TestCase):
    def setUp(self):
        self.carrier = ShippingCarrier.objects.get(code=ShippingCarrier.Code.POST)

    def test_clean_rejects_max_weight_less_than_or_equal_to_min_weight(self):
        rate = ShippingRate(
            carrier=self.carrier,
            province=IranProvince.TEHRAN,
            min_weight_g=1000,
            max_weight_g=1000,
            price=Decimal("50000.00"),
        )

        with self.assertRaises(ValidationError):
            rate.clean()


class ShipmentModelTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user)
        self.carrier = ShippingCarrier.objects.get(code=ShippingCarrier.Code.POST)

    def test_create_shipment_linked_to_order(self):
        shipment = Shipment.objects.create(
            order=self.order,
            carrier=self.carrier,
            tracking_number="TRK123456",
        )

        self.assertEqual(shipment.order, self.order)
        self.assertEqual(shipment.carrier, self.carrier)
        self.assertEqual(shipment.status, Shipment.Status.PENDING)
        # Accessible from the order side too, via the OneToOne related_name.
        self.order.refresh_from_db()
        self.assertEqual(self.order.shipment, shipment)

    def test_str_includes_order_number_and_status(self):
        shipment = Shipment.objects.create(order=self.order, carrier=self.carrier)

        self.assertEqual(
            str(shipment),
            f"Shipment for {self.order.order_number} — {Shipment.Status.PENDING}",
        )

    def test_second_shipment_for_the_same_order_is_rejected(self):
        Shipment.objects.create(order=self.order, carrier=self.carrier)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Shipment.objects.create(order=self.order, carrier=self.carrier)

    def test_carrier_cannot_be_deleted_while_a_shipment_references_it(self):
        Shipment.objects.create(order=self.order, carrier=self.carrier)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.carrier.delete()

    def test_deleting_the_order_deletes_its_shipment(self):
        shipment = Shipment.objects.create(order=self.order, carrier=self.carrier)
        shipment_id = shipment.id

        self.order.delete()

        self.assertFalse(Shipment.objects.filter(id=shipment_id).exists())
