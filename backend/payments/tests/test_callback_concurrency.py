"""
Concurrency test proving that Task 6.2.1.5's select_for_update()-guarded
lock-then-check-then-act block in PaymentCallbackView actually prevents a
transaction from being processed twice when two callback requests for the
SAME PaymentTransaction arrive in very close succession — the exact race
that Task 6.2.1.4's plain `if txn.status != PENDING` check (without a
lock) leaves open: both requests can read PENDING before either finishes
writing.

Why TransactionTestCase instead of TestCase
---------------------------------------------
Same reasoning as order/tests/test_stock_concurrency.py: `TestCase` wraps
each test in an outer transaction that's rolled back, never committed,
so `select_for_update()` locking across two threads (each on its own,
genuinely separate DB connection) wouldn't exhibit real blocking
behavior. `TransactionTestCase` performs real commits, which is required
for the lock to actually do anything.

Why this must run against PostgreSQL
--------------------------------------
Same as test_stock_concurrency.py: this project's settings configure
`django.db.backends.postgresql` unconditionally, so no override is
needed to run this as-is. If a SQLite branch is ever introduced, this
test (like the stock ones) would need an explicit
`connection.vendor == "postgresql"` skip guard, since SQLite's locking
model doesn't support genuine multi-connection row-level blocking.

How "exactly once" is verified
--------------------------------
Setting PaymentTransaction.status to SUCCESS twice is, by itself,
idempotent-looking in the FINAL state — you can't tell from
`txn.status == SUCCESS` alone whether the write happened once or twice.
So this test also counts actual invocations of `PaymentTransaction.save()`
that occur while `status == SUCCESS` (i.e. the write inside the
success-mutation branch), via a thin wrapper around the real `save()`
method. If the lock works, exactly one such call can ever land, no
matter how the two threads interleave; the other thread must block until
the first commits, then see status != PENDING and take the no-op
early-return path.
"""

import threading
import unittest.mock as mock
from decimal import Decimal

from django.db import connections
from django.test import TransactionTestCase
from order.models import Order
from order.tests.factories import make_variant
from payments.gateways.base import PaymentVerifyResult
from payments.models import PaymentTransaction
from rest_framework.test import APIClient

from .test_views import make_order, make_order_item, make_user


def _hit_callback(url, params, results, index):
    """
    Thread worker: GET the callback URL with a fresh APIClient (and thus
    a fresh, thread-local DB connection), recording the response's status
    code and redirect target into results[index].
    """
    client = APIClient()
    try:
        response = client.get(url, params)
        results[index] = (response.status_code, getattr(response, "url", None))
    finally:
        connections.close_all()


def _run_concurrently(url, params, count=2):
    results = [None] * count
    threads = [
        threading.Thread(target=_hit_callback, args=(url, params, results, i))
        for i in range(count)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


class PaymentCallbackConcurrencyTests(TransactionTestCase):
    def test_two_concurrent_successful_callbacks_apply_state_change_exactly_once(self):
        """
        Two near-simultaneous callback requests for the same PENDING
        transaction, both backed by a mocked successful verify_payment(),
        must result in the transaction being marked SUCCESS and the order
        PROCESSING exactly once — never twice, and never left corrupted
        in some in-between state.
        """
        user = make_user(email="racer@example.com")
        variant = make_variant(name="Race Item", slug="race-item", stock=5)
        order = make_order(user, total=Decimal("100.00"))
        make_order_item(order, variant, quantity=2)
        authority = "A00000000000000000000000000000000wOGYpd"
        PaymentTransaction.objects.create(
            order=order,
            gateway="zarinpal",
            authority=authority,
            amount=order.total,
            status=PaymentTransaction.Status.PENDING,
        )

        save_calls_while_success = []
        save_lock = threading.Lock()
        original_save = PaymentTransaction.save

        def counting_save(self, *args, **kwargs):
            # Record the status AT THE MOMENT save() is called — the
            # success-mutation branch sets status=SUCCESS before calling
            # save(), so a save() call observed with status already
            # SUCCESS is exactly "the write that applies the success
            # transition" — the thing that must only ever happen once.
            if self.status == PaymentTransaction.Status.SUCCESS:
                with save_lock:
                    save_calls_while_success.append(self.pk)
            return original_save(self, *args, **kwargs)

        def fake_get_payment_gateway(name=None):
            gateway = type(
                "FakeGateway",
                (),
                {
                    "verify_payment": staticmethod(
                        lambda authority, amount: PaymentVerifyResult(
                            success=True,
                            ref_id="201202070",
                            raw_response={"data": {"code": 100}},
                        )
                    )
                },
            )()
            return gateway

        with (
            mock.patch.object(PaymentTransaction, "save", counting_save),
            mock.patch(
                "payments.views.get_payment_gateway",
                side_effect=fake_get_payment_gateway,
            ),
        ):
            results = _run_concurrently(
                "/api/payments/callback/zarinpal/",
                {"Authority": authority, "Status": "OK"},
                count=2,
            )

        # Both requests should have gotten a redirect response (302),
        # neither should have raised/500'd.
        for status_code, _ in results:
            self.assertEqual(status_code, 302)

        # The KEY assertion: the success-mutation write happened exactly
        # once, regardless of how the two threads interleaved.
        self.assertEqual(
            len(save_calls_while_success),
            1,
            f"Expected the SUCCESS transition to be written exactly once, "
            f"got {len(save_calls_while_success)}: {save_calls_while_success}",
        )

        txn = PaymentTransaction.objects.get(authority=authority)
        order.refresh_from_db()
        variant.refresh_from_db()

        self.assertEqual(txn.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(txn.ref_id, "201202070")
        self.assertEqual(order.status, Order.Status.PROCESSING)
        # Stock was already decremented at order-creation time — a
        # correctly-guarded success path never touches it, whether
        # applied once (correct) or, hypothetically, twice (a bug this
        # test would have caught via the save-count assertion above).
        self.assertEqual(variant.stock, 5)

        # Both redirects (whichever request "won" the lock, and whichever
        # took the already-processed early-return path) must point at the
        # SAME, correct order-confirmation URL — never a failure page.
        for _, redirect_url in results:
            self.assertIn(f"/order-confirmation/{order.id}", redirect_url)
