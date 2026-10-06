"""
Tests for the order_status_changed hook (Task 8.1.1.2).

The key test is `test_saving_without_status_change_does_not_fire`: it
proves the pre_save/post_save change detection really distinguishes a
status change from any other save.
"""

from contextlib import contextmanager
from decimal import Decimal

from accounts.models import UserType
from django.contrib.auth import get_user_model
from order.models import Order
from order.signals import order_status_changed
from rest_framework.test import APITestCase

User = get_user_model()


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
        subtotal=Decimal("10.00"),
        shipping_cost=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("10.00"),
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

    # ── placeholder receiver ─────────────────────────────────────────────
    def test_placeholder_receiver_logs_the_change(self):
        order = make_order(user=self.customer)
        with self.assertLogs("order.notifications", level="INFO") as logs:
            order.status = Order.Status.PROCESSING
            order.save()
        message = logs.records[0].getMessage()
        self.assertIn(order.order_number, message)
        self.assertIn("pending -> processing", message)
