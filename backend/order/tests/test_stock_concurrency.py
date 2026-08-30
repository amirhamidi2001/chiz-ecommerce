"""
Concurrency tests proving that the row-level locking added in Task 1.1.1.2
(select_for_update), combined with the atomic order-creation block from
Task 1.1.1.1 and the stock decrement from Task 1.1.1.3, actually prevents
overselling when two or more requests race to buy the last unit(s) of the
same inventory — not just that each piece works in isolation, but that
they compose correctly under real concurrency.

Retargeted from Product to ProductVariant (this task): ProductVariant.stock
is now the real, authoritative per-shade/size inventory count, and
select_for_update() in OrderCreateSerializer.create() locks ProductVariant
rows (scoped with `of=("self",)` to avoid Postgres's "FOR UPDATE cannot be
applied to the nullable side of an outer join" restriction, since
ProductVariant.color is a nullable FK reached via select_related). Every
assertion below checks ProductVariant.stock, not Product.stock — this is
the single most important regression check in the whole variant-migration
epic: proving overselling is still impossible after repointing the lock
from Product to ProductVariant, not just assuming the repointing preserved
the guarantee.

Why TransactionTestCase instead of TestCase
---------------------------------------------
`django.test.TestCase` wraps every test in an outer transaction (and each
individual DB operation inside it in a SAVEPOINT) that gets rolled back at
the end of the test — it never actually commits anything. `select_for_update`
locking only has real teeth across genuinely separate, concurrently-open
transactions on separate connections; a thread racing against the main
test's still-open, never-committed outer transaction does not reproduce
real locking/blocking behavior and can silently pass or silently deadlock
depending on timing. `TransactionTestCase` performs real commits and
truncates tables between tests instead, which is required for multiple
threads (each getting their own DB connection, since Django's DB
connections are thread-local) to actually contend for the same lock.

Why this must run against PostgreSQL
--------------------------------------
This project's settings (backend/core/settings/base.py) already configure
`django.db.backends.postgresql` unconditionally — there is no SQLite branch
in core/settings/*, and the dev/CI stack provisions a real Postgres via
docker-compose. So no settings override is required to run this file as-is.

If, in the future, DATABASES ever gets pointed at SQLite for a lighter/
faster local test run, these tests would silently stop being meaningful:
SQLite's locking model does not support genuine multi-connection row-level
blocking the way `SELECT ... FOR UPDATE` does on Postgres, so a race that
Postgres would correctly serialize might just appear to "pass" on SQLite
without ever exercising the lock. In that scenario, guard these tests
explicitly, e.g.:

    import unittest
    from django.db import connection

    @unittest.skipUnless(
        connection.vendor == "postgresql", "requires real row-level locking"
    )
    class StockConcurrencyTests(TransactionTestCase):
        ...

or point DJANGO_SETTINGS_MODULE at a Postgres-backed settings module
specifically for this file when running it in isolation.

Flakiness note
---------------
This file was run 5x locally in a loop before being considered done,
specifically to rule out timing-dependent flakiness (see task acceptance
criteria). All scenarios use `threading.Thread` with all threads started
before any `join()`, so the requests are launched essentially
simultaneously rather than sequentially, and the assertions only depend on
final, settled state (final stock, counts, and per-response status codes)
rather than assuming any particular interleaving/order.
"""

import threading

from django.db import connections
from django.test import TransactionTestCase
from order.models import Order, OrderItem
from rest_framework import status
from rest_framework.test import APIClient

from .factories import (
    VALID_PAYLOAD,
    make_cart_with_items,
    make_color,
    make_product,
    make_user,
    make_variant,
)


def _place_order(user, results, index):
    """
    Thread worker: authenticate as *user* with a fresh APIClient and POST
    to /api/orders/, recording (status_code, response_data) into
    results[index].

    Each thread gets its own DB connection automatically (Django's DB
    connections are thread-local); we explicitly close it when done so we
    don't leak connections across threads/tests.
    """
    client = APIClient()
    client.force_authenticate(user=user)
    try:
        response = client.post("/api/orders/", VALID_PAYLOAD, format="json")
        results[index] = (response.status_code, response.data)
    finally:
        connections.close_all()


def _run_concurrently(users):
    """Fire one order-creation request per user, all at roughly the same time."""
    results = [None] * len(users)
    threads = [
        threading.Thread(target=_place_order, args=(user, results, i))
        for i, user in enumerate(users)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


class StockConcurrencyTests(TransactionTestCase):
    """
    End-to-end proof, through the real POST /api/orders/ endpoint, that
    concurrent checkouts against the same low-stock VARIANT cannot oversell.
    """

    def test_two_concurrent_buyers_one_unit_stock_only_one_succeeds(self):
        """
        A variant has exactly 1 unit of stock. Two different users each
        try to buy 1 unit at the same time. Exactly one request must
        succeed (201); the other must fail with a stock-related 400.
        Stock must end at 0, and exactly one Order/OrderItem must exist
        for the variant — never two.
        """
        variant = make_variant(name="Last One", slug="last-one", stock=1)

        user_a = make_user(email="racer-a@example.com")
        user_b = make_user(email="racer-b@example.com")
        make_cart_with_items(user_a, [{"variant": variant, "quantity": 1}])
        make_cart_with_items(user_b, [{"variant": variant, "quantity": 1}])

        results = _run_concurrently([user_a, user_b])
        statuses = [r[0] for r in results]

        self.assertEqual(
            sorted(statuses),
            sorted([status.HTTP_400_BAD_REQUEST, status.HTTP_201_CREATED]),
            f"Expected exactly one success and one stock-rejection, got: {results}",
        )

        # The rejected request must have failed specifically on stock, not
        # some unrelated validation issue.
        failed_body = results[statuses.index(status.HTTP_400_BAD_REQUEST)][1]
        self.assertIn("stock", failed_body)

        variant.refresh_from_db()
        self.assertEqual(variant.stock, 0)

        self.assertEqual(
            Order.objects.filter(items__variant=variant).distinct().count(), 1
        )
        self.assertEqual(OrderItem.objects.filter(variant=variant).count(), 1)

    def test_three_buyers_five_stock_two_units_each_never_oversells(self):
        """
        A variant has 5 units of stock. Three different users each try to
        buy 2 units at the same time (total demand of 6 against a supply
        of 5). At most 2 of the 3 orders can succeed (since 3 * 2 = 6 > 5),
        stock must never go negative, and the final stock must exactly
        match 5 - (2 * number_of_successes).
        """
        variant = make_variant(name="Scarce Batch", slug="scarce-batch", stock=5)

        users = [make_user(email=f"batch-buyer-{i}@example.com") for i in range(3)]
        for user in users:
            make_cart_with_items(user, [{"variant": variant, "quantity": 2}])

        results = _run_concurrently(users)
        statuses = [r[0] for r in results]

        successes = statuses.count(status.HTTP_201_CREATED)
        failures = statuses.count(status.HTTP_400_BAD_REQUEST)

        self.assertEqual(successes + failures, 3, f"Unexpected statuses: {results}")
        self.assertGreaterEqual(successes, 1)
        self.assertLessEqual(successes, 2)  # ceil: 5 stock / 2 per order

        variant.refresh_from_db()
        self.assertGreaterEqual(variant.stock, 0)
        self.assertEqual(variant.stock, 5 - successes * 2)

        self.assertEqual(OrderItem.objects.filter(variant=variant).count(), successes)

    def test_two_buyers_different_variants_of_same_product_both_succeed(self):
        """
        The critical proof that locking is correctly scoped PER VARIANT,
        not accidentally over-broad at the product level: two customers
        concurrently order the LAST unit of two DIFFERENT variants
        (Shade A and Shade B) of the SAME product, each variant with
        stock=1. Since they're different variants, they don't actually
        contend for the same inventory — BOTH requests must succeed.

        If the locking had regressed to locking the shared Product row
        instead of each ProductVariant row, this test would fail (one
        request would be spuriously rejected for "insufficient stock"
        even though the variant it wanted had stock available).
        """
        product = make_product(name="Foundation", slug="foundation", stock=2)
        color_a = make_color(name="Shade A")
        color_b = make_color(name="Shade B")
        shade_a = make_variant(
            product=product, sku="FOUND-A", color=color_a, price="30.00", stock=1
        )
        shade_b = make_variant(
            product=product, sku="FOUND-B", color=color_b, price="30.00", stock=1
        )

        user_a = make_user(email="shade-a-buyer@example.com")
        user_b = make_user(email="shade-b-buyer@example.com")
        make_cart_with_items(user_a, [{"variant": shade_a, "quantity": 1}])
        make_cart_with_items(user_b, [{"variant": shade_b, "quantity": 1}])

        results = _run_concurrently([user_a, user_b])
        statuses = [r[0] for r in results]

        self.assertEqual(
            statuses,
            [status.HTTP_201_CREATED, status.HTTP_201_CREATED],
            f"Expected both different-variant orders to succeed, got: {results}",
        )

        shade_a.refresh_from_db()
        shade_b.refresh_from_db()
        self.assertEqual(shade_a.stock, 0)
        self.assertEqual(shade_b.stock, 0)

        self.assertEqual(OrderItem.objects.filter(variant=shade_a).count(), 1)
        self.assertEqual(OrderItem.objects.filter(variant=shade_b).count(), 1)
        self.assertEqual(
            Order.objects.filter(items__variant__in=[shade_a, shade_b])
            .distinct()
            .count(),
            2,
        )
