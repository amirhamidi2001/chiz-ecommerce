"""
GET /api/dashboard/customer/payment-history/ — the customer's own PaymentTransaction
records. Replaces the old "payment methods" tab, which fabricated a summary from
historical order.payment_method strings.
"""

import pytest
from payments.models import PaymentTransaction
from rest_framework import status

URL = "/api/dashboard/customer/payment-history/"


@pytest.fixture
def make_txn(db):
    def _make(order, amount=299_900, gateway="zarinpal", txn_status="success", **extra):
        return PaymentTransaction.objects.create(
            order=order,
            gateway=gateway,
            status=txn_status,
            amount=amount,
            authority=extra.pop("authority", "A0000SECRET"),
            raw_callback_payload={"internal": "audit-only"},
            **extra,
        )

    return _make


class TestUserPaymentHistory:
    def test_unauthenticated_returns_401(self, anon_client):
        assert anon_client.get(URL).status_code == status.HTTP_401_UNAUTHORIZED

    def test_empty_for_user_without_transactions(self, customer_client):
        res = customer_client.get(URL)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 0

    def test_lists_own_transactions_with_expected_fields(
        self, customer_client, customer, make_order, make_txn
    ):
        order = make_order(user=customer)
        make_txn(order, amount=299_900, gateway="zibal", ref_id="REF-123")
        res = customer_client.get(URL)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        row = res.data["results"][0]
        assert row["order_number"] == order.order_number
        assert row["order_id"] == order.pk
        assert row["gateway"] == "zibal"
        assert row["gateway_display"] == "Zibal"
        assert row["status"] == "success"
        assert row["status_display"] == "Success"
        assert row["ref_id"] == "REF-123"
        # Rial integer on the wire (the SPA converts to Toman for display).
        assert row["amount"] == 299_900
        assert isinstance(row["amount"], int)

    def test_never_includes_another_users_transactions(
        self, customer_client, customer, make_order, make_txn, make_user
    ):
        other = make_user(email="other-pay@example.com")
        mine = make_order(user=customer)
        theirs = make_order(user=other)
        make_txn(mine, amount=100_000)
        make_txn(theirs, amount=777_000)
        res = customer_client.get(URL)
        assert res.data["count"] == 1
        assert [r["order_number"] for r in res.data["results"]] == [mine.order_number]
        assert 777_000 not in [r["amount"] for r in res.data["results"]]

    def test_ignores_user_scoping_query_params(
        self, customer_client, customer, make_order, make_txn, make_user
    ):
        other = make_user(email="other-pay2@example.com")
        make_txn(make_order(user=other), amount=555_000)
        res = customer_client.get(URL, {"user": other.pk, "order__user": other.pk})
        assert res.data["count"] == 0

    def test_excludes_guest_order_transactions(
        self, customer_client, customer, make_order, make_txn
    ):
        guest_order = make_order(user=customer)
        guest_order.user = None
        guest_order.save(update_fields=["user"])
        make_txn(guest_order)
        assert customer_client.get(URL).data["count"] == 0

    def test_does_not_leak_gateway_internals(
        self, customer_client, customer, make_order, make_txn
    ):
        make_txn(make_order(user=customer))
        row = customer_client.get(URL).data["results"][0]
        assert "authority" not in row
        assert "raw_callback_payload" not in row

    def test_includes_pending_and_failed_newest_first(
        self, customer_client, customer, make_order, make_txn
    ):
        order = make_order(user=customer)
        first = make_txn(order, txn_status="failed")
        second = make_txn(order, txn_status="success")
        res = customer_client.get(URL)
        assert [r["id"] for r in res.data["results"]] == [second.pk, first.pk]
        assert {r["status"] for r in res.data["results"]} == {"failed", "success"}

    def test_is_paginated(self, customer_client, customer, make_order, make_txn):
        order = make_order(user=customer)
        for _ in range(3):
            make_txn(order)
        res = customer_client.get(URL, {"page_size": 2})
        assert res.data["count"] == 3
        assert len(res.data["results"]) == 2
        assert res.data["next"] is not None

    def test_read_only(self, customer_client):
        assert (
            customer_client.post(URL, {}).status_code
            == status.HTTP_405_METHOD_NOT_ALLOWED
        )
