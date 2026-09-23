from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from order.models import Order
from order.tests.factories import make_variant
from payments.gateways.base import PaymentVerifyResult
from payments.models import PaymentTransaction
from payments.tasks import reconcile_stuck_payment_transactions
from shop.models import StockMovement

from .test_views import make_order, make_order_item, make_user


def make_stuck_transaction(
    order,
    *,
    age_minutes,
    status=PaymentTransaction.Status.PENDING,
    gateway="zarinpal",
    authority="A00000000000000000000000000000000wOGYpd",
):
    """
    Create a PaymentTransaction and backdate its created_at, since
    `created_at` is `auto_now_add=True` and ignores any explicit value
    passed to .create() — a subsequent .update() is required to actually
    set it in the past for threshold testing.
    """
    txn = PaymentTransaction.objects.create(
        order=order,
        gateway=gateway,
        authority=authority,
        amount=order.total,
        status=status,
    )
    PaymentTransaction.objects.filter(pk=txn.pk).update(
        created_at=timezone.now() - timedelta(minutes=age_minutes)
    )
    txn.refresh_from_db()
    return txn


class ReconcileStuckPaymentTransactionsTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.order = make_order(self.user, total=Decimal("100.00"))
        self.variant = make_variant(stock=5)
        self.order_item = make_order_item(self.order, self.variant, quantity=2)
        self.stock_after_order_creation = self.variant.stock

    @patch("payments.tasks.get_payment_gateway")
    def test_stuck_transaction_recovered_as_success_when_gateway_confirms_payment(
        self, mock_get_gateway
    ):
        # Older than the default 30-minute threshold, with no callback
        # ever having arrived — exactly the "customer closed the tab"
        # scenario this task exists for.
        txn = make_stuck_transaction(self.order, age_minutes=45)

        mock_gateway = mock_get_gateway.return_value
        mock_gateway.verify_payment.return_value = PaymentVerifyResult(
            success=True, ref_id="201202070", raw_response={"data": {"code": 100}}
        )

        result_message = reconcile_stuck_payment_transactions()

        mock_get_gateway.assert_called_once_with("zarinpal")
        mock_gateway.verify_payment.assert_called_once_with(
            authority=txn.authority, amount=self.order.total
        )

        txn.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(txn.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(txn.ref_id, "201202070")
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        # Stock was already decremented at order-creation time — a
        # recovered success must NOT touch it.
        self.assertEqual(self.variant.stock, self.stock_after_order_creation)
        self.assertIn("1 success", result_message)
        self.assertIn("0 failed", result_message)

    @patch("payments.tasks.get_payment_gateway")
    def test_stuck_transaction_finalized_as_failed_when_gateway_confirms_no_payment(
        self, mock_get_gateway
    ):
        txn = make_stuck_transaction(self.order, age_minutes=45)

        mock_gateway = mock_get_gateway.return_value
        mock_gateway.verify_payment.return_value = PaymentVerifyResult(
            success=False, error_message="Transaction not found or unsuccessful."
        )

        result_message = reconcile_stuck_payment_transactions()

        txn.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(txn.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        # Stock reserved at order-creation time must be released back.
        self.assertEqual(
            self.variant.stock,
            self.stock_after_order_creation + self.order_item.quantity,
        )

        movement = StockMovement.objects.get(
            related_order=self.order, reason=StockMovement.Reason.CANCELLATION
        )
        self.assertEqual(movement.quantity_delta, self.order_item.quantity)
        self.assertIsNone(movement.actor)

        self.assertIn("0 success", result_message)
        self.assertIn("1 failed", result_message)

    @patch("payments.tasks.get_payment_gateway")
    def test_transaction_younger_than_threshold_is_left_untouched(
        self, mock_get_gateway
    ):
        # 10 minutes old — well under the default 30-minute threshold.
        # Might still get a real callback any moment; not eligible yet.
        txn = make_stuck_transaction(self.order, age_minutes=10)

        reconcile_stuck_payment_transactions()

        mock_get_gateway.assert_not_called()

        txn.refresh_from_db()
        self.order.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(txn.status, PaymentTransaction.Status.PENDING)
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertEqual(self.variant.stock, self.stock_after_order_creation)

    @patch("payments.tasks.get_payment_gateway")
    def test_already_settled_transactions_are_never_touched_regardless_of_age(
        self, mock_get_gateway
    ):
        # Both old enough to be eligible by age alone — but the
        # .filter(status=PENDING) clause must exclude them outright.
        success_txn = make_stuck_transaction(
            self.order,
            age_minutes=60,
            status=PaymentTransaction.Status.SUCCESS,
            authority="ALREADY-SUCCESS",
        )
        other_order = make_order(self.user, total=Decimal("50.00"))
        failed_txn = make_stuck_transaction(
            other_order,
            age_minutes=90,
            status=PaymentTransaction.Status.FAILED,
            authority="ALREADY-FAILED",
        )

        reconcile_stuck_payment_transactions()

        mock_get_gateway.assert_not_called()

        success_txn.refresh_from_db()
        failed_txn.refresh_from_db()
        self.assertEqual(success_txn.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(failed_txn.status, PaymentTransaction.Status.FAILED)

    @patch("payments.tasks.get_payment_gateway")
    def test_multiple_stuck_transactions_are_each_reconciled_independently(
        self, mock_get_gateway
    ):
        order_a = make_order(self.user, total=Decimal("20.00"))
        variant_a = make_variant(name="A", slug="a", stock=5)
        make_order_item(order_a, variant_a, quantity=1)
        txn_a = make_stuck_transaction(order_a, age_minutes=40, authority="AUTH-A")

        order_b = make_order(self.user, total=Decimal("30.00"))
        variant_b = make_variant(name="B", slug="b", stock=5)
        make_order_item(order_b, variant_b, quantity=1)
        txn_b = make_stuck_transaction(order_b, age_minutes=50, authority="AUTH-B")

        def fake_verify(authority, amount):
            if authority == "AUTH-A":
                return PaymentVerifyResult(success=True, ref_id="REF-A")
            return PaymentVerifyResult(success=False, error_message="failed")

        mock_gateway = mock_get_gateway.return_value
        mock_gateway.verify_payment.side_effect = fake_verify

        result_message = reconcile_stuck_payment_transactions()

        txn_a.refresh_from_db()
        txn_b.refresh_from_db()
        self.assertEqual(txn_a.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(txn_b.status, PaymentTransaction.Status.FAILED)
        self.assertIn("1 success", result_message)
        self.assertIn("1 failed", result_message)
