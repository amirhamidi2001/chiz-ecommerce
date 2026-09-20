from decimal import Decimal

from django.test import TestCase
from order.models import Order
from payments.models import PaymentGatewayConfig, PaymentTransaction


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


class PaymentGatewayConfigModelTests(TestCase):
    def test_get_solo_creates_default_row_when_none_exists(self):
        self.assertEqual(PaymentGatewayConfig.objects.count(), 0)

        config = PaymentGatewayConfig.get_solo()

        self.assertEqual(PaymentGatewayConfig.objects.count(), 1)
        self.assertEqual(config.pk, 1)
        self.assertEqual(config.active_gateway, PaymentTransaction.Gateway.ZARINPAL)
        self.assertEqual(config.fallback_order, [])

    def test_get_solo_returns_the_same_row_on_repeated_calls(self):
        first = PaymentGatewayConfig.get_solo()
        first.active_gateway = PaymentTransaction.Gateway.ZIBAL
        first.fallback_order = ["idpay"]
        first.save()

        second = PaymentGatewayConfig.get_solo()

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.active_gateway, PaymentTransaction.Gateway.ZIBAL)
        self.assertEqual(second.fallback_order, ["idpay"])
        self.assertEqual(PaymentGatewayConfig.objects.count(), 1)

    def test_save_always_enforces_pk_1_singleton(self):
        config = PaymentGatewayConfig(active_gateway=PaymentTransaction.Gateway.IDPAY)
        config.pk = 999  # attempt to create a second row
        config.save()

        self.assertEqual(config.pk, 1)
        self.assertEqual(PaymentGatewayConfig.objects.count(), 1)
