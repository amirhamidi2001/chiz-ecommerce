from decimal import Decimal

from django.test import TestCase
from order.models import Order

from payments.models import PaymentTransaction


def make_order(**kwargs):
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
    )
    defaults.update(kwargs)
    return Order.objects.create(**defaults)


class PaymentTransactionModelTests(TestCase):
    def setUp(self):
        self.order = make_order()

    def test_create_transaction_linked_to_order(self):
        transaction = PaymentTransaction.objects.create(
            order=self.order,
            gateway=PaymentTransaction.Gateway.ZARINPAL,
            amount=Decimal("64.99"),
        )
        self.assertEqual(transaction.order, self.order)
        self.assertIn(transaction, self.order.payment_transactions.all())

    def test_status_defaults_to_pending(self):
        transaction = PaymentTransaction.objects.create(
            order=self.order,
            gateway=PaymentTransaction.Gateway.ZIBAL,
            amount=Decimal("10.00"),
        )
        self.assertEqual(transaction.status, PaymentTransaction.Status.PENDING)

    def test_str_representation(self):
        transaction = PaymentTransaction.objects.create(
            order=self.order,
            gateway=PaymentTransaction.Gateway.IDPAY,
            amount=Decimal("20.00"),
        )
        expected = (
            f"{transaction.gateway} — {self.order.order_number} — "
            f"{transaction.status}"
        )
        self.assertEqual(str(transaction), expected)
