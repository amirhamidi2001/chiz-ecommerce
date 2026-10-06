"""
Tests for AdminOrderFilter + the free-text search on AdminOrderViewSet
(Task 8.1.1.3).

Verifies every existing filter/search parameter against seeded orders, the
two new ones (user_id, shipping_province) and that filters AND together.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from order.models import Order

URL = "/api/dashboard/admin/orders/"


def _ids(res):
    return {row["order_number"] for row in res.data["results"]}


@pytest.fixture
def seeded(db, make_user):
    """
    Six orders with deliberately distinct values so each filter isolates a
    different subset. created_at is auto_now_add, so it is overridden with
    .update() after creation.
    """
    alice = make_user(email="alice@example.com")
    bob = make_user(email="bob@example.com")

    def mk(
        number,
        user,
        *,
        status="pending",
        method="credit_card",
        total="50.00",
        state="tehran",
        first="Test",
        last="User",
        email=None,
        phone="09120000000",
        created="2026-01-15T12:00:00"
    ):
        order = Order.objects.create(
            user=user,
            order_number=number,
            status=status,
            first_name=first,
            last_name=last,
            email=email or (user.email if user else "guest@example.com"),
            phone=phone,
            shipping_address="1 Test St",
            shipping_city="City",
            shipping_state=state,
            shipping_zip="12345",
            shipping_country="IR",
            payment_method=method,
            subtotal=Decimal(total),
            shipping_cost=Decimal("0.00"),
            tax=Decimal("0.00"),
            total=Decimal(total),
        )
        Order.objects.filter(pk=order.pk).update(
            created_at=datetime.fromisoformat(created).replace(tzinfo=timezone.utc)
        )
        return order

    return {
        "alice": alice,
        "bob": bob,
        "A1": mk(
            "ORD-A1",
            alice,
            status="pending",
            method="credit_card",
            total="20.00",
            state="tehran",
            first="Alice",
            last="Rahimi",
            phone="09121111111",
            created="2026-01-01T00:00:00",
        ),
        "A2": mk(
            "ORD-A2",
            alice,
            status="processing",
            method="paypal",
            total="50.00",
            state="isfahan",
            first="Alice",
            last="Rahimi",
            phone="09121111111",
            created="2026-01-10T23:59:59",
        ),
        "A3": mk(
            "ORD-A3",
            alice,
            status="delivered",
            method="credit_card",
            total="100.00",
            state="tehran",
            first="Alice",
            last="Rahimi",
            phone="09121111111",
            created="2026-02-01T08:00:00",
        ),
        "B1": mk(
            "ORD-B1",
            bob,
            status="processing",
            method="apple_pay",
            total="75.00",
            state="fars",
            first="Bob",
            last="Karimi",
            phone="09132222222",
            created="2026-01-20T12:00:00",
        ),
        "B2": mk(
            "ORD-B2",
            bob,
            status="cancelled",
            method="paypal",
            total="50.00",
            state="tehran",
            first="Bob",
            last="Karimi",
            phone="09132222222",
            created="2026-03-05T12:00:00",
        ),
        # Guest order whose user was deleted (FK is SET_NULL)
        "G1": mk(
            "ORD-G1",
            None,
            status="pending",
            method="credit_card",
            total="10.00",
            state="tehran",
            first="Guest",
            last="Buyer",
            email="guest@example.com",
            phone="09153333333",
            created="2026-01-10T00:00:00",
        ),
    }


def get(client, **params):
    res = client.get(URL, params)
    assert res.status_code == 200, res.data
    return res


# ── Baseline ──────────────────────────────────────────────────────────────────


def test_no_filters_returns_everything_including_userless_orders(admin_client, seeded):
    res = get(admin_client)
    assert res.data["count"] == 6
    assert "ORD-G1" in _ids(res)


# ── Existing filters ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExistingFilters:
    def test_status(self, admin_client, seeded):
        assert _ids(get(admin_client, status="processing")) == {"ORD-A2", "ORD-B1"}

    def test_status_unknown_value_returns_empty_not_error(self, admin_client, seeded):
        assert get(admin_client, status="bogus").data["count"] == 0

    def test_payment_method(self, admin_client, seeded):
        assert _ids(get(admin_client, payment_method="paypal")) == {"ORD-A2", "ORD-B2"}

    def test_date_from_is_inclusive(self, admin_client, seeded):
        res = get(admin_client, date_from="2026-02-01")
        assert _ids(res) == {"ORD-A3", "ORD-B2"}

    def test_date_to_includes_the_whole_day(self, admin_client, seeded):
        # A2 was created at 23:59:59 on 2026-01-10; G1 at 00:00:00 the same day.
        res = get(admin_client, date_to="2026-01-10")
        assert _ids(res) == {"ORD-A1", "ORD-A2", "ORD-G1"}

    def test_date_range_single_day(self, admin_client, seeded):
        res = get(admin_client, date_from="2026-01-10", date_to="2026-01-10")
        assert _ids(res) == {"ORD-A2", "ORD-G1"}

    def test_date_range(self, admin_client, seeded):
        res = get(admin_client, date_from="2026-01-10", date_to="2026-02-01")
        assert _ids(res) == {"ORD-A2", "ORD-G1", "ORD-B1", "ORD-A3"}

    def test_inverted_date_range_is_empty(self, admin_client, seeded):
        assert (
            get(admin_client, date_from="2026-03-01", date_to="2026-01-01").data[
                "count"
            ]
            == 0
        )

    def test_invalid_date_is_400(self, admin_client, seeded):
        assert admin_client.get(URL, {"date_from": "not-a-date"}).status_code == 400

    def test_min_total_is_inclusive(self, admin_client, seeded):
        assert _ids(get(admin_client, min_total="75")) == {"ORD-B1", "ORD-A3"}

    def test_max_total_is_inclusive(self, admin_client, seeded):
        assert _ids(get(admin_client, max_total="20")) == {"ORD-A1", "ORD-G1"}

    def test_total_range(self, admin_client, seeded):
        res = get(admin_client, min_total="50", max_total="75")
        assert _ids(res) == {"ORD-A2", "ORD-B2", "ORD-B1"}


# ── Existing free-text search ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestSearch:
    def test_by_order_number(self, admin_client, seeded):
        assert _ids(get(admin_client, search="ORD-B1")) == {"ORD-B1"}

    def test_order_number_partial_and_case_insensitive(self, admin_client, seeded):
        assert _ids(get(admin_client, search="ord-b")) == {"ORD-B1", "ORD-B2"}

    def test_by_email(self, admin_client, seeded):
        assert _ids(get(admin_client, search="alice@example.com")) == {
            "ORD-A1",
            "ORD-A2",
            "ORD-A3",
        }

    def test_by_first_name(self, admin_client, seeded):
        assert _ids(get(admin_client, search="Bob")) == {"ORD-B1", "ORD-B2"}

    def test_by_last_name(self, admin_client, seeded):
        assert _ids(get(admin_client, search="Rahimi")) == {
            "ORD-A1",
            "ORD-A2",
            "ORD-A3",
        }

    def test_by_phone(self, admin_client, seeded):
        assert _ids(get(admin_client, search="09132222222")) == {"ORD-B1", "ORD-B2"}

    def test_multi_term_search_matches_across_fields(self, admin_client, seeded):
        # first_name=Alice, last_name=Rahimi -> every term must match some field
        assert _ids(get(admin_client, search="Alice Rahimi")) == {
            "ORD-A1",
            "ORD-A2",
            "ORD-A3",
        }
        assert get(admin_client, search="Alice Karimi").data["count"] == 0

    def test_no_match(self, admin_client, seeded):
        assert get(admin_client, search="zzz-nothing").data["count"] == 0


# ── New filters ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestNewFilters:
    def test_user_id(self, admin_client, seeded):
        res = get(admin_client, user_id=seeded["alice"].pk)
        assert _ids(res) == {"ORD-A1", "ORD-A2", "ORD-A3"}

    def test_user_id_excludes_userless_orders(self, admin_client, seeded):
        res = get(admin_client, user_id=seeded["bob"].pk)
        assert _ids(res) == {"ORD-B1", "ORD-B2"}

    def test_user_id_unknown_user_returns_empty(self, admin_client, seeded):
        assert get(admin_client, user_id=999999).data["count"] == 0

    def test_user_id_non_numeric_is_400(self, admin_client, seeded):
        assert admin_client.get(URL, {"user_id": "abc"}).status_code == 400

    def test_user_id_differs_from_text_search(self, admin_client, seeded):
        """Same email text on another user's order must not leak in by id."""
        Order.objects.filter(order_number="ORD-B1").update(email="alice@example.com")
        by_search = _ids(get(admin_client, search="alice@example.com"))
        by_id = _ids(get(admin_client, user_id=seeded["alice"].pk))
        assert "ORD-B1" in by_search
        assert "ORD-B1" not in by_id

    def test_shipping_province(self, admin_client, seeded):
        assert _ids(get(admin_client, shipping_province="tehran")) == {
            "ORD-A1",
            "ORD-A3",
            "ORD-B2",
            "ORD-G1",
        }

    def test_shipping_province_is_case_insensitive(self, admin_client, seeded):
        assert _ids(get(admin_client, shipping_province="Isfahan")) == {"ORD-A2"}

    def test_shipping_province_is_exact_not_substring(self, admin_client, seeded):
        assert get(admin_client, shipping_province="teh").data["count"] == 0

    def test_shipping_province_unknown_returns_empty(self, admin_client, seeded):
        assert get(admin_client, shipping_province="atlantis").data["count"] == 0


# ── Combinations ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCombinedFilters:
    def test_status_date_and_user_are_anded(self, admin_client, seeded):
        res = get(
            admin_client,
            status="processing",
            date_from="2026-01-01",
            user_id=seeded["alice"].pk,
        )
        assert _ids(res) == {"ORD-A2"}

    def test_combination_with_no_overlap_is_empty(self, admin_client, seeded):
        res = get(admin_client, status="cancelled", user_id=seeded["alice"].pk)
        assert res.data["count"] == 0

    def test_province_total_and_payment_method(self, admin_client, seeded):
        res = get(
            admin_client,
            shipping_province="tehran",
            min_total="50",
            payment_method="paypal",
        )
        assert _ids(res) == {"ORD-B2"}

    def test_filters_and_search_together(self, admin_client, seeded):
        res = get(admin_client, search="Karimi", status="processing")
        assert _ids(res) == {"ORD-B1"}

    def test_all_filters_at_once(self, admin_client, seeded):
        res = get(
            admin_client,
            status="processing",
            payment_method="paypal",
            date_from="2026-01-10",
            date_to="2026-01-10",
            min_total="50",
            max_total="50",
            user_id=seeded["alice"].pk,
            shipping_province="isfahan",
            search="ORD-A2",
        )
        assert _ids(res) == {"ORD-A2"}

    def test_filters_do_not_change_permissions(self, customer_client, seeded):
        assert customer_client.get(URL, {"status": "pending"}).status_code == 403
