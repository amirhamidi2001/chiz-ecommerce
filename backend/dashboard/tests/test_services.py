from decimal import Decimal

import pytest
from accounts.models import UserType

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_delivered_order(make_order, user=None, total=1_000_000):
    o = make_order(user=user, status="delivered", total=total)
    return o


# ══════════════════════════════════════════════════════════════════════════════
# get_admin_overview
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGetAdminOverview:

    def test_returns_required_top_level_keys(self):
        from dashboard.services import get_admin_overview

        data = get_admin_overview("30d")
        for key in ("revenue", "orders", "users", "products", "revenue_chart"):
            assert key in data, f"Missing key: {key}"

    def test_revenue_reflects_delivered_orders(self, make_order, customer):
        from dashboard.services import get_admin_overview

        _make_delivered_order(make_order, user=customer, total=2_500_000)
        data = get_admin_overview("30d")
        assert data["revenue"]["current"] >= 2_500_000

    def test_cancelled_orders_excluded_from_revenue(self, make_order, customer):
        from dashboard.services import get_admin_overview

        make_order(user=customer, status="cancelled", total=9_990_000)
        data = get_admin_overview("30d")
        # Cancelled should not contribute to revenue
        assert data["revenue"]["current"] == 0

    def test_revenue_chart_list_of_dicts(self, make_order, customer):
        from dashboard.services import get_admin_overview

        _make_delivered_order(make_order, user=customer)
        data = get_admin_overview("30d")
        chart = data["revenue_chart"]
        assert isinstance(chart, list)
        if chart:
            assert "date" in chart[0]
            assert "revenue" in chart[0]
            assert "orders" in chart[0]

    def test_pct_change_is_numeric(self):
        from dashboard.services import get_admin_overview

        data = get_admin_overview("7d")
        assert isinstance(data["revenue"]["change"], (int, float))
        assert isinstance(data["orders"]["change"], (int, float))

    def test_products_dict_has_correct_keys(self):
        from dashboard.services import get_admin_overview

        data = get_admin_overview("30d")
        for key in ("total", "low_stock", "out_of_stock"):
            assert key in data["products"]

    def test_low_stock_and_out_of_stock_reflect_variant_data(self, make_variant):
        """
        low_stock/out_of_stock must be computed off ProductVariant, not
        the stale Product.stock field — construct variants with known
        stock/threshold combinations and assert exact counts.
        """
        from dashboard.services import get_admin_overview

        make_variant(stock=3, low_stock_threshold=5)  # low (below threshold)
        make_variant(stock=5, low_stock_threshold=5)  # low (equal to threshold)
        make_variant(stock=0, low_stock_threshold=5)  # out of stock
        make_variant(stock=0, low_stock_threshold=5)  # out of stock
        make_variant(stock=20, low_stock_threshold=5)  # healthy stock

        data = get_admin_overview("30d")
        assert data["products"]["low_stock"] == 2
        assert data["products"]["out_of_stock"] == 2

    def test_inactive_variants_excluded_from_low_stock_and_out_of_stock(
        self, make_variant
    ):
        """
        A deactivated/expired variant (Task 3.3.1.3) shouldn't surface
        as an actionable "needs restocking" alert.
        """
        from dashboard.services import get_admin_overview

        make_variant(stock=2, low_stock_threshold=5, is_active=False)  # would be low
        make_variant(stock=0, low_stock_threshold=5, is_active=False)  # would be out

        data = get_admin_overview("30d")
        assert data["products"]["low_stock"] == 0
        assert data["products"]["out_of_stock"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# get_monthly_revenue
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGetMonthlyRevenue:

    def test_returns_list(self):
        from dashboard.services import get_monthly_revenue

        result = get_monthly_revenue(12)
        assert isinstance(result, list)

    def test_items_have_month_revenue_orders_keys(self, make_order, customer):
        from dashboard.services import get_monthly_revenue

        _make_delivered_order(make_order, user=customer)
        result = get_monthly_revenue(12)
        assert len(result) >= 1
        for item in result:
            assert "month" in item
            assert "revenue" in item
            assert "orders" in item

    def test_revenue_values_are_whole_rial_ints(self, make_order, customer):
        from dashboard.services import get_monthly_revenue

        _make_delivered_order(make_order)
        result = get_monthly_revenue(12)
        for item in result:
            assert type(item["revenue"]) is int  # never a float (ADR 0001 I-1)


# ══════════════════════════════════════════════════════════════════════════════
# get_user_stats
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGetUserStats:

    def test_returns_expected_keys(self):
        from dashboard.services import get_user_stats

        stats = get_user_stats()
        for key in ("total", "active", "verified", "new_this_month", "admins"):
            assert key in stats

    def test_total_counts_created_users(self, make_user):
        from dashboard.services import get_user_stats
        from django.contrib.auth import get_user_model

        User = get_user_model()
        before = User.objects.count()
        make_user(email="stats1@example.com")
        make_user(email="stats2@example.com")
        stats = get_user_stats()
        assert stats["total"] == before + 2

    def test_admins_counts_only_type_2_and_3(self, make_user):
        from dashboard.services import get_user_stats

        make_user(email="admin1@example.com", user_type=UserType.ADMIN)
        make_user(email="super1@example.com", user_type=UserType.SUPERUSER)
        make_user(email="cust1@example.com", user_type=UserType.CUSTOMER)
        stats = get_user_stats()
        # At least the 2 we created
        assert stats["admins"] >= 2


# ══════════════════════════════════════════════════════════════════════════════
# get_user_summary
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGetUserSummary:

    def test_returns_expected_keys(self, customer):
        from dashboard.services import get_user_summary

        summary = get_user_summary(customer)
        for key in (
            "total_orders",
            "total_spent",
            "wishlist_count",
            "reviews_count",
            "pending_orders",
        ):
            assert key in summary

    def test_total_orders_counts_correctly(self, customer, make_order):
        from dashboard.services import get_user_summary

        make_order(user=customer, status="delivered")
        make_order(user=customer, status="pending")
        summary = get_user_summary(customer)
        assert summary["total_orders"] == 2

    def test_total_spent_sums_active_orders(self, customer, make_order):
        from dashboard.services import get_user_summary

        make_order(user=customer, status="delivered", total=1_000_000)
        make_order(user=customer, status="cancelled", total=500_000)
        summary = get_user_summary(customer)
        assert summary["total_spent"] == 1_000_000
        assert type(summary["total_spent"]) is int

    def test_wishlist_count(self, customer, make_product):
        from dashboard.models import Wishlist
        from dashboard.services import get_user_summary

        Wishlist.objects.create(user=customer, product=make_product())
        Wishlist.objects.create(user=customer, product=make_product())
        summary = get_user_summary(customer)
        assert summary["wishlist_count"] == 2

    def test_pending_orders_count(self, customer, make_order):
        from dashboard.services import get_user_summary

        make_order(user=customer, status="pending")
        make_order(user=customer, status="processing")
        make_order(user=customer, status="delivered")
        summary = get_user_summary(customer)
        assert summary["pending_orders"] == 2


# ══════════════════════════════════════════════════════════════════════════════
# get_top_products
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGetTopProducts:

    def test_returns_list(self):
        from dashboard.services import get_top_products

        assert isinstance(get_top_products(10), list)

    def test_items_have_required_fields(self, make_order, make_product, customer):
        from dashboard.services import get_top_products
        from order.models import OrderItem

        order = make_order(user=customer, status="delivered")
        product = make_product(name="Top Seller")
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            product_slug=product.slug,
            unit_price=product.price,
            quantity=3,
        )
        results = get_top_products(10)
        assert len(results) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# get_product_stats
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGetProductStats:

    def test_returns_required_keys(self):
        from dashboard.services import get_product_stats

        data = get_product_stats()
        for key in (
            "total",
            "on_sale",
            "new",
            "out_of_stock",
            "low_stock",
            "avg_rating",
        ):
            assert key in data

    def test_low_stock_and_out_of_stock_reflect_variant_data(self, make_variant):
        from dashboard.services import get_product_stats

        make_variant(stock=3, low_stock_threshold=5)  # low (below threshold)
        make_variant(stock=5, low_stock_threshold=5)  # low (equal to threshold)
        make_variant(stock=0, low_stock_threshold=5)  # out of stock
        make_variant(stock=0, low_stock_threshold=5)  # out of stock
        make_variant(stock=20, low_stock_threshold=5)  # healthy stock

        data = get_product_stats()
        assert data["low_stock"] == 2
        assert data["out_of_stock"] == 2

    def test_inactive_variants_excluded_from_low_stock_and_out_of_stock(
        self, make_variant
    ):
        from dashboard.services import get_product_stats

        make_variant(stock=2, low_stock_threshold=5, is_active=False)  # would be low
        make_variant(stock=0, low_stock_threshold=5, is_active=False)  # would be out

        data = get_product_stats()
        assert data["low_stock"] == 0
        assert data["out_of_stock"] == 0

    def test_low_stock_respects_per_variant_threshold_override(self, make_variant):
        """
        A variant with an overridden (higher) threshold should count as
        low-stock at a stock level that a default-threshold variant
        would not.
        """
        from dashboard.services import get_product_stats

        make_variant(stock=8, low_stock_threshold=10)  # low: 8 <= 10
        make_variant(stock=8, low_stock_threshold=5)  # healthy: 8 > 5

        data = get_product_stats()
        assert data["low_stock"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# Real-Postgres regression proof for Epic 14's integer-Rial money fields
# ══════════════════════════════════════════════════════════════════════════════
#
# Everything below runs through the ORM against the project's real Postgres
# test database (settings.DATABASES is postgresql — asserted first, so this
# class can never silently pass on SQLite/a mock). Expected values are exact
# integers computed by hand from the constructed orders, not "> 0" checks.

from datetime import datetime, timedelta  # noqa: E402

from django.db import connection  # noqa: E402
from django.utils import timezone  # noqa: E402


def _backdate(order, when):
    """created_at is auto_now_add, so move it with a queryset update."""
    from order.models import Order

    Order.objects.filter(pk=order.pk).update(created_at=when)


def _tehran(year, month, day, hour=12, minute=0, second=0):
    return timezone.make_aware(
        datetime(year, month, day, hour, minute, second),
        timezone.get_current_timezone(),
    )


def _add_item(order, product, unit_price, quantity, sku="", attrs=None, name=None):
    from order.models import OrderItem

    return OrderItem.objects.create(
        order=order,
        product=product,
        product_name=name or product.name,
        product_slug=product.slug,
        variant_sku=sku,
        variant_attributes_json=attrs or {},
        unit_price=unit_price,
        quantity=quantity,
    )


@pytest.mark.django_db
class TestIntegerRialAggregatesOnPostgres:

    def test_tests_really_run_on_postgres(self):
        assert connection.vendor == "postgresql"

    def test_admin_overview_exact_integer_values(self, make_order, customer):
        from dashboard.services import get_admin_overview

        now = timezone.now()
        # current 30d window: 1,000,000 + 2,500,000 + 300,000 count as revenue
        for status_, total, days_ago in (
            ("delivered", 1_000_000, 2),
            ("shipped", 2_500_000, 3),
            ("processing", 300_000, 4),
            ("cancelled", 9_990_000, 5),  # in order count, never in revenue
            ("pending", 123_450, 6),  # in order count, never in revenue
        ):
            _backdate(
                make_order(user=customer, status=status_, total=total),
                now - timedelta(days=days_ago),
            )
        # previous 30d window: one delivered order of 1,900,000
        _backdate(
            make_order(user=customer, status="delivered", total=1_900_000),
            now - timedelta(days=40),
        )

        data = get_admin_overview("30d")

        assert data["revenue"]["current"] == 3_800_000
        assert type(data["revenue"]["current"]) is int
        assert data["revenue"]["change"] == 100.0  # (3.8M - 1.9M) / 1.9M
        assert type(data["revenue"]["change"]) is float
        assert data["orders"]["current"] == 5
        assert data["orders"]["change"] == 400.0  # 5 vs 1

        chart = data["revenue_chart"]
        assert sum(r["revenue"] for r in chart) == 3_800_000
        assert sum(r["orders"] for r in chart) == 3  # active statuses only
        assert all(type(r["revenue"]) is int for r in chart)
        assert all(isinstance(r["date"], str) for r in chart)

    def test_empty_database_yields_int_zero_not_none_or_decimal(self):
        from dashboard.services import get_admin_overview

        data = get_admin_overview("30d")
        assert data["revenue"]["current"] == 0
        assert type(data["revenue"]["current"]) is int
        assert data["revenue_chart"] == []

    def test_top_products_exact_revenue_and_ordering(
        self, make_order, make_product, customer
    ):
        from dashboard.services import get_top_products

        a = make_product(name="Serum", price=250_000)
        b = make_product(name="Palette", price=4_000_000)
        o1 = make_order(user=customer, status="delivered", total=1_000_000)
        o2 = make_order(user=customer, status="delivered", total=4_500_000)
        _add_item(o1, a, 250_000, 3)  # 750,000
        _add_item(o2, a, 250_000, 2)  # 500,000  -> Serum: 5 sold, 1,250,000
        _add_item(o2, b, 4_000_000, 1)  # Palette: 1 sold, 4,000,000

        rows = get_top_products(10)

        assert rows == [
            {
                "product_id": a.id,
                "product_name": "Serum",
                "total_sold": 5,
                "revenue": 1_250_000,
            },
            {
                "product_id": b.id,
                "product_name": "Palette",
                "total_sold": 1,
                "revenue": 4_000_000,
            },
        ]
        assert all(type(r["revenue"]) is int for r in rows)

    def test_top_products_respects_limit(self, make_order, make_product, customer):
        from dashboard.services import get_top_products

        order = make_order(user=customer, status="delivered")
        for i in range(3):
            _add_item(order, make_product(name=f"P{i}"), 100_000, i + 1)
        assert len(get_top_products(2)) == 2

    def test_monthly_revenue_exact_per_month(self, make_order, customer):
        from dashboard.services import get_monthly_revenue

        this_month = timezone.localtime(timezone.now()).replace(
            day=15, hour=12, minute=0, second=0, microsecond=0
        )
        earlier = this_month - timedelta(days=40)  # always a different month
        for status_, total, when in (
            ("delivered", 1_000_000, this_month),
            ("shipped", 2_000_000, this_month - timedelta(days=1)),
            ("delivered", 700_000, earlier),
            ("cancelled", 5_000_000, earlier),  # excluded
        ):
            _backdate(make_order(user=customer, status=status_, total=total), when)

        result = get_monthly_revenue(12)
        by_month = {r["month"]: r for r in result}

        assert by_month[this_month.strftime("%b %Y")] == {
            "month": this_month.strftime("%b %Y"),
            "revenue": 3_000_000,
            "orders": 2,
        }
        assert by_month[earlier.strftime("%b %Y")]["revenue"] == 700_000
        assert by_month[earlier.strftime("%b %Y")]["orders"] == 1
        assert all(type(r["revenue"]) is int for r in result)

    def test_user_summary_exact_total_spent(self, make_order, customer):
        from dashboard.services import get_user_summary

        make_order(user=customer, status="delivered", total=1_250_000)
        make_order(user=customer, status="shipped", total=750_000)
        make_order(user=customer, status="cancelled", total=9_000_000)
        make_order(user=customer, status="pending", total=420_000)

        summary = get_user_summary(customer)

        assert summary["total_spent"] == 2_000_000
        assert type(summary["total_spent"]) is int
        assert summary["total_orders"] == 4
        assert summary["pending_orders"] == 1

    def test_user_summary_with_no_orders_is_int_zero(self, customer):
        from dashboard.services import get_user_summary

        summary = get_user_summary(customer)
        assert summary["total_spent"] == 0
        assert type(summary["total_spent"]) is int

    def test_no_decimal_leaks_into_any_money_output(
        self, make_order, make_product, customer
    ):
        """Guard against a regression back to Decimal/float money values."""
        from dashboard.services import (
            get_admin_overview,
            get_monthly_revenue,
            get_recent_orders,
            get_top_products,
            get_user_summary,
        )

        order = make_order(user=customer, status="delivered", total=1_000_000)
        _add_item(order, make_product(name="Z"), 500_000, 2)

        for value in (
            get_admin_overview("7d")["revenue"]["current"],
            get_admin_overview("7d")["revenue_chart"][0]["revenue"],
            get_monthly_revenue(1)[0]["revenue"],
            get_top_products(1)[0]["revenue"],
            get_user_summary(customer)["total_spent"],
            get_recent_orders(1)[0]["total"],
        ):
            assert type(value) is int


# ══════════════════════════════════════════════════════════════════════════════
# period=custom — service layer
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCustomPeriod:

    def test_get_date_range_custom_date_strings_are_inclusive_days(self):
        from dashboard.services import get_date_range

        start, end = get_date_range("custom", "2026-03-01", "2026-03-07")
        assert timezone.is_aware(start) and timezone.is_aware(end)
        assert start == _tehran(2026, 3, 1, 0, 0, 0)
        assert end.date() == _tehran(2026, 3, 7).date()
        assert (end.hour, end.minute, end.second) == (23, 59, 59)

    def test_get_date_range_custom_accepts_iso_datetimes(self):
        from dashboard.services import get_date_range

        start, end = get_date_range(
            "custom", "2026-03-01T08:00:00+00:00", "2026-03-02T08:00:00Z"
        )
        assert end - start == timedelta(days=1)

    def test_presets_unchanged(self):
        from dashboard.services import get_date_range

        for period, days in (("7d", 7), ("30d", 30), ("90d", 90), ("1y", 365)):
            start, end = get_date_range(period)
            assert (end - start) == timedelta(days=days)
        start, end = get_date_range("nonsense")  # historical fallback
        assert (end - start) == timedelta(days=30)

    @pytest.mark.parametrize(
        "start,end",
        [
            (None, None),
            ("2026-03-01", None),
            (None, "2026-03-07"),
            ("", "2026-03-07"),
            ("not-a-date", "2026-03-07"),
            ("2026-03-01", "2026-13-45"),
            ("2026-03-07", "2026-03-01"),  # reversed
            ("2026-03-01T10:00:00", "2026-03-01T10:00:00"),  # start == end
            ("0001-01-01", "2026-03-01"),  # overflow / out of range
            ("2000-01-01", "2026-03-01"),  # span beyond the 10-year cap
        ],
    )
    def test_invalid_custom_range_raises_clean_error(self, start, end):
        from dashboard.services import InvalidDateRange, get_admin_overview

        with pytest.raises(InvalidDateRange):
            get_admin_overview("custom", start, end)

    def test_custom_range_returns_exact_data_for_that_window(
        self, make_order, customer
    ):
        from dashboard.services import get_admin_overview

        for status_, total, when in (
            ("delivered", 1_000_000, _tehran(2026, 3, 1, 0, 0, 1)),  # in (1st day)
            ("shipped", 2_000_000, _tehran(2026, 3, 7, 23, 59, 0)),  # in (last day)
            ("cancelled", 500_000, _tehran(2026, 3, 4)),  # in count, not revenue
            ("delivered", 8_000_000, _tehran(2026, 2, 28, 23, 59, 0)),  # before
            ("delivered", 9_000_000, _tehran(2026, 3, 8, 0, 0, 1)),  # after
            # also inside the comparison window (7 days before 2026-03-01)
            ("delivered", 1_500_000, _tehran(2026, 2, 25)),
        ):
            _backdate(make_order(user=customer, status=status_, total=total), when)

        data = get_admin_overview("custom", "2026-03-01", "2026-03-07")

        assert data["revenue"]["current"] == 3_000_000
        assert type(data["revenue"]["current"]) is int
        assert data["orders"]["current"] == 3
        # previous window [Feb 22 00:00, Mar 1 00:00] holds the 1,500,000 and
        # the 8,000,000 (Feb 28) orders = 9,500,000 -> (3.0M - 9.5M) / 9.5M
        assert data["revenue"]["change"] == -68.4
        assert [r["revenue"] for r in data["revenue_chart"]] == [1_000_000, 2_000_000]
        assert [r["date"] for r in data["revenue_chart"]] == [
            "2026-03-01",
            "2026-03-07",
        ]


# ══════════════════════════════════════════════════════════════════════════════
# period=custom — HTTP endpoint (/api/dashboard/admin/overview/)
# ══════════════════════════════════════════════════════════════════════════════

OVERVIEW_URL = "/api/dashboard/admin/overview/"


@pytest.mark.django_db
class TestAdminOverviewCustomPeriodEndpoint:

    def test_custom_range_200_with_integer_rial_json(
        self, admin_client, make_order, customer
    ):
        _backdate(
            make_order(user=customer, status="delivered", total=2_500_000),
            _tehran(2026, 3, 3),
        )
        resp = admin_client.get(
            OVERVIEW_URL,
            {"period": "custom", "start": "2026-03-01", "end": "2026-03-07"},
        )
        assert resp.status_code == 200
        assert resp.data["revenue"]["current"] == 2_500_000
        assert resp.data["orders"]["current"] == 1
        # exactly an integer in the rendered JSON, not "2500000.0"
        assert b'"current":2500000,' in resp.content.replace(b" ", b"")

    @pytest.mark.parametrize(
        "params",
        [
            {"period": "custom"},
            {"period": "custom", "start": "2026-03-01"},
            {"period": "custom", "end": "2026-03-07"},
            {"period": "custom", "start": "garbage", "end": "2026-03-07"},
            {"period": "custom", "start": "2026-03-07", "end": "2026-03-01"},
            {"period": "custom", "start": "2026-03-01", "end": "2026-03-01T00:00:00"},
        ],
    )
    def test_bad_custom_params_return_400_not_500(self, admin_client, params):
        resp = admin_client.get(OVERVIEW_URL, params)
        assert resp.status_code == 400
        assert "detail" in resp.data and resp.data["detail"]

    def test_preset_periods_still_work_and_ignore_start_end(self, admin_client):
        resp = admin_client.get(
            OVERVIEW_URL, {"period": "7d", "start": "garbage", "end": "garbage"}
        )
        assert resp.status_code == 200

    def test_default_period_still_works(self, admin_client):
        assert admin_client.get(OVERVIEW_URL).status_code == 200

    def test_non_admin_cannot_use_custom_range(self, customer_client):
        resp = customer_client.get(
            OVERVIEW_URL,
            {"period": "custom", "start": "2026-03-01", "end": "2026-03-07"},
        )
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# get_top_products — date range
# ══════════════════════════════════════════════════════════════════════════════

RANGE_START = _tehran(2026, 3, 1, 0, 0, 0)
RANGE_END = _tehran(2026, 3, 7, 23, 59, 59)


def _order_on(make_order, customer, when, status_="delivered", total=1_000_000):
    order = make_order(user=customer, status=status_, total=total)
    _backdate(order, when)
    return order


@pytest.mark.django_db
class TestTopProductsDateRange:

    def test_orders_outside_range_are_excluded(
        self, make_order, make_product, customer
    ):
        from dashboard.services import get_top_products

        serum = make_product(name="Serum")
        palette = make_product(name="Palette")
        before = _order_on(make_order, customer, _tehran(2026, 2, 28, 23, 59, 0))
        inside1 = _order_on(make_order, customer, _tehran(2026, 3, 2))
        inside2 = _order_on(make_order, customer, _tehran(2026, 3, 6))
        after = _order_on(make_order, customer, _tehran(2026, 3, 8, 0, 0, 1))
        _add_item(before, serum, 250_000, 10)  # out
        _add_item(after, serum, 250_000, 20)  # out
        _add_item(before, palette, 4_000_000, 7)  # out: Palette absent entirely
        _add_item(inside1, serum, 250_000, 3)  # 750,000
        _add_item(inside2, serum, 250_000, 2)  # 500,000

        rows = get_top_products(10, RANGE_START, RANGE_END)

        assert rows == [
            {
                "product_id": serum.id,
                "product_name": "Serum",
                "total_sold": 5,
                "revenue": 1_250_000,
            }
        ]

    def test_without_range_aggregates_all_time(
        self, make_order, make_product, customer
    ):
        from dashboard.services import get_top_products

        serum = make_product(name="Serum")
        _add_item(
            _order_on(make_order, customer, _tehran(2025, 1, 5)), serum, 250_000, 4
        )
        _add_item(
            _order_on(make_order, customer, _tehran(2026, 3, 2)), serum, 250_000, 1
        )

        rows = get_top_products(10)
        assert (rows[0]["total_sold"], rows[0]["revenue"]) == (5, 1_250_000)

    def test_range_bounds_are_inclusive(self, make_order, make_product, customer):
        from dashboard.services import get_top_products

        p = make_product(name="Edge")
        _add_item(_order_on(make_order, customer, RANGE_START), p, 100_000, 1)
        _add_item(_order_on(make_order, customer, RANGE_END), p, 100_000, 1)

        assert get_top_products(10, RANGE_START, RANGE_END)[0]["total_sold"] == 2

    def test_open_ended_start_only(self, make_order, make_product, customer):
        from dashboard.services import get_top_products

        p = make_product(name="Open")
        _add_item(_order_on(make_order, customer, _tehran(2026, 2, 1)), p, 100_000, 5)
        _add_item(_order_on(make_order, customer, _tehran(2026, 3, 2)), p, 100_000, 2)

        assert get_top_products(10, start=RANGE_START)[0]["total_sold"] == 2

    def test_revenue_is_exact_int_rial(self, make_order, make_product, customer):
        from dashboard.services import get_top_products

        p = make_product(name="Exact")
        order = _order_on(make_order, customer, _tehran(2026, 3, 3))
        _add_item(order, p, 1_234_560, 3)  # 3,703,680

        row = get_top_products(10, RANGE_START, RANGE_END)[0]
        assert row["revenue"] == 3_703_680
        assert type(row["revenue"]) is int
        assert type(row["total_sold"]) is int

    def test_ordering_and_limit(self, make_order, make_product, customer):
        from dashboard.services import get_top_products

        order = _order_on(make_order, customer, _tehran(2026, 3, 3))
        for name, qty in (("A", 1), ("B", 5), ("C", 3)):
            _add_item(order, make_product(name=name), 100_000, qty)

        rows = get_top_products(2, RANGE_START, RANGE_END)
        assert [r["product_name"] for r in rows] == ["B", "C"]


# ══════════════════════════════════════════════════════════════════════════════
# get_top_variants
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGetTopVariants:

    def test_aggregates_by_sku_distinguishing_shades_of_same_product(
        self, make_order, make_product, customer
    ):
        from dashboard.services import get_top_variants

        lipstick = make_product(name="Velvet Lipstick")
        other = make_product(name="Mascara")
        o1 = _order_on(make_order, customer, _tehran(2026, 3, 2))
        o2 = _order_on(make_order, customer, _tehran(2026, 3, 3))
        rose = {"color": "Rose"}
        nude = {"color": "Nude"}
        _add_item(o1, lipstick, 300_000, 3, sku="VL-ROSE", attrs=rose)  # 900,000
        _add_item(o2, lipstick, 300_000, 2, sku="VL-ROSE", attrs=rose)  # 600,000
        _add_item(o2, lipstick, 320_000, 4, sku="VL-NUDE", attrs=nude)  # 1,280,000
        _add_item(o2, other, 150_000, 1, sku="MA-BLK", attrs={"color": "Black"})

        rows = get_top_variants(10)

        assert rows == [
            {
                "variant_sku": "VL-ROSE",
                "product_name": "Velvet Lipstick",
                "variant_attributes": rose,
                "total_sold": 5,
                "revenue": 1_500_000,
            },
            {
                "variant_sku": "VL-NUDE",
                "product_name": "Velvet Lipstick",
                "variant_attributes": nude,
                "total_sold": 4,
                "revenue": 1_280_000,
            },
            {
                "variant_sku": "MA-BLK",
                "product_name": "Mascara",
                "variant_attributes": {"color": "Black"},
                "total_sold": 1,
                "revenue": 150_000,
            },
        ]

    def test_same_sku_with_renamed_snapshot_stays_one_row_latest_snapshot(
        self, make_order, make_product, customer
    ):
        from dashboard.services import get_top_variants

        p = make_product(name="Velvet Lipstick")
        old = _order_on(make_order, customer, _tehran(2026, 3, 1))
        new = _order_on(make_order, customer, _tehran(2026, 3, 5))
        _add_item(
            old, p, 300_000, 2, sku="VL-ROSE", attrs={"color": "Rose"}, name="Lipstick"
        )
        _add_item(
            new,
            p,
            300_000,
            3,
            sku="VL-ROSE",
            attrs={"color": "Rosewood"},
            name="Velvet Lipstick",
        )

        rows = get_top_variants(10)

        assert len(rows) == 1
        assert rows[0]["total_sold"] == 5
        assert rows[0]["revenue"] == 1_500_000
        assert rows[0]["product_name"] == "Velvet Lipstick"
        assert rows[0]["variant_attributes"] == {"color": "Rosewood"}

    def test_blank_sku_rows_are_excluded(self, make_order, make_product, customer):
        from dashboard.services import get_top_variants

        p = make_product(name="Legacy")
        order = _order_on(make_order, customer, _tehran(2026, 3, 2))
        _add_item(order, p, 100_000, 50, sku="")  # historical, no snapshot
        _add_item(order, p, 100_000, 2, sku="LG-1", attrs={"size": "50ml"})

        rows = get_top_variants(10)

        assert [r["variant_sku"] for r in rows] == ["LG-1"]
        assert rows[0]["total_sold"] == 2

    def test_blank_sku_rows_do_not_use_up_limit_slots(
        self, make_order, make_product, customer
    ):
        from dashboard.services import get_top_variants

        p = make_product(name="Legacy")
        order = _order_on(make_order, customer, _tehran(2026, 3, 2))
        _add_item(order, p, 100_000, 99, sku="")
        _add_item(order, p, 100_000, 1, sku="LG-1")

        assert [r["variant_sku"] for r in get_top_variants(1)] == ["LG-1"]

    def test_date_range_excludes_outside_orders(
        self, make_order, make_product, customer
    ):
        from dashboard.services import get_top_variants

        p = make_product(name="Ranged")
        out = _order_on(make_order, customer, _tehran(2026, 2, 20))
        inside = _order_on(make_order, customer, _tehran(2026, 3, 4))
        _add_item(out, p, 200_000, 9, sku="RG-OUT")
        _add_item(inside, p, 200_000, 2, sku="RG-IN")

        rows = get_top_variants(10, RANGE_START, RANGE_END)

        assert [(r["variant_sku"], r["total_sold"]) for r in rows] == [("RG-IN", 2)]

    def test_revenue_is_exact_int_rial(self, make_order, make_product, customer):
        from dashboard.services import get_top_variants

        p = make_product(name="Exact")
        order = _order_on(make_order, customer, _tehran(2026, 3, 3))
        _add_item(order, p, 1_234_560, 3, sku="EX-1")

        row = get_top_variants(10)[0]
        assert row["revenue"] == 3_703_680
        assert type(row["revenue"]) is int
        assert type(row["total_sold"]) is int

    def test_empty_result(self):
        from dashboard.services import get_top_variants

        assert get_top_variants(10) == []

    def test_ties_are_ordered_deterministically(
        self, make_order, make_product, customer
    ):
        from dashboard.services import get_top_variants

        p = make_product(name="Tie")
        order = _order_on(make_order, customer, _tehran(2026, 3, 3))
        _add_item(order, p, 100_000, 2, sku="T-B")
        _add_item(order, p, 100_000, 2, sku="T-A")
        _add_item(order, p, 300_000, 2, sku="T-C")  # same units, more revenue

        assert [r["variant_sku"] for r in get_top_variants(10)] == ["T-C", "T-A", "T-B"]


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

TOP_PRODUCTS_URL = "/api/dashboard/admin/top-products/"
TOP_VARIANTS_URL = "/api/dashboard/admin/top-variants/"
REVENUE_URL = "/api/dashboard/admin/revenue-stats/"
CUSTOM_MARCH = {"period": "custom", "start": "2026-03-01", "end": "2026-03-07"}


@pytest.fixture
def march_sales(make_order, make_product, customer):
    """One in-range and one out-of-range sale of the same variant."""
    p = make_product(name="Serum")
    _add_item(
        _order_on(make_order, customer, _tehran(2026, 3, 3)),
        p, 250_000, 2, sku="SR-1", attrs={"size": "30ml"},
    )  # fmt: skip
    _add_item(
        _order_on(make_order, customer, _tehran(2026, 1, 3)),
        p, 250_000, 8, sku="SR-1", attrs={"size": "30ml"},
    )  # fmt: skip
    return p


@pytest.mark.django_db
class TestTopReportEndpoints:

    def test_top_variants_custom_range(self, admin_client, march_sales):
        resp = admin_client.get(TOP_VARIANTS_URL, CUSTOM_MARCH)
        assert resp.status_code == 200
        assert resp.data["top_variants"] == [
            {
                "variant_sku": "SR-1",
                "product_name": "Serum",
                "variant_attributes": {"size": "30ml"},
                "total_sold": 2,
                "revenue": 500_000,
            }
        ]

    def test_top_products_custom_range(self, admin_client, march_sales):
        resp = admin_client.get(TOP_PRODUCTS_URL, CUSTOM_MARCH)
        assert resp.status_code == 200
        (row,) = resp.data["top_products"]
        assert (row["total_sold"], row["revenue"]) == (2, 500_000)

    def test_no_period_means_all_time(self, admin_client, march_sales):
        for url, key in ((TOP_PRODUCTS_URL, "top_products"),
                         (TOP_VARIANTS_URL, "top_variants")):  # fmt: skip
            resp = admin_client.get(url)
            assert resp.status_code == 200
            assert resp.data[key][0]["total_sold"] == 10
            assert (
                admin_client.get(url, {"period": "all"}).data[key][0]["total_sold"]
                == 10
            )

    def test_limit_param(self, admin_client, make_order, make_product, customer):
        order = _order_on(make_order, customer, _tehran(2026, 3, 3))
        for i in range(3):
            _add_item(order, make_product(name=f"P{i}"), 100_000, i + 1, sku=f"S{i}")
        for url, key in ((TOP_PRODUCTS_URL, "top_products"),
                         (TOP_VARIANTS_URL, "top_variants")):  # fmt: skip
            assert len(admin_client.get(url, {"limit": 2}).data[key]) == 2

    @pytest.mark.parametrize("url", [TOP_PRODUCTS_URL, TOP_VARIANTS_URL])
    @pytest.mark.parametrize(
        "params",
        [
            {"period": "custom"},
            {"period": "custom", "start": "2026-03-07", "end": "2026-03-01"},
            {"period": "custom", "start": "nope", "end": "2026-03-01"},
            {"limit": "abc"},
            {"limit": "0"},
            {"limit": "101"},
        ],
    )
    def test_bad_params_return_400(self, admin_client, url, params):
        resp = admin_client.get(url, params)
        assert resp.status_code == 400
        assert resp.data["detail"]

    @pytest.mark.parametrize("url", [TOP_PRODUCTS_URL, TOP_VARIANTS_URL])
    def test_permissions(self, anon_client, customer_client, url):
        assert anon_client.get(url).status_code in (401, 403)
        assert customer_client.get(url).status_code == 403

    def test_overview_top_products_follows_selected_period(
        self, admin_client, march_sales
    ):
        resp = admin_client.get(OVERVIEW_URL, CUSTOM_MARCH)
        assert resp.status_code == 200
        (row,) = resp.data["top_products"]
        assert row["total_sold"] == 2

    def test_revenue_stats_all_time_by_default_and_period_aware(
        self, admin_client, march_sales
    ):
        assert admin_client.get(REVENUE_URL).data["top_products"][0]["total_sold"] == 10
        ranged = admin_client.get(REVENUE_URL, CUSTOM_MARCH)
        assert ranged.data["top_products"][0]["total_sold"] == 2
        bad = admin_client.get(REVENUE_URL, {"period": "custom"})
        assert bad.status_code == 400


# ══════════════════════════════════════════════════════════════════════════════
# Inventory lists: low stock / out of stock
# ══════════════════════════════════════════════════════════════════════════════

LOW_STOCK_URL = "/api/dashboard/admin/inventory/low-stock/"
OUT_OF_STOCK_URL = "/api/dashboard/admin/inventory/out-of-stock/"


def _stock_move(variant, when, delta=-1):
    from shop.models import StockMovement

    movement = StockMovement.objects.create(
        variant=variant,
        reason=StockMovement.Reason.SALE,
        quantity_delta=delta,
        stock_after=variant.stock,
    )
    StockMovement.objects.filter(pk=movement.pk).update(created_at=when)


@pytest.mark.django_db
class TestLowStockVariants:

    def test_uses_each_variants_own_threshold_sorted_most_urgent_first(
        self, make_variant, make_product
    ):
        from dashboard.services import get_low_stock_variants

        p = make_product(name="Lipstick")
        # stock vs own threshold:
        v_low3 = make_variant(product=p, stock=3, low_stock_threshold=5)  # low
        v_low1 = make_variant(product=p, stock=1, low_stock_threshold=2)  # low
        v_edge = make_variant(product=p, stock=5, low_stock_threshold=5)  # == → low
        v_high_thr = make_variant(product=p, stock=12, low_stock_threshold=20)  # low
        # NOT low: above own threshold, even though 8 < the "global" 10/20 above
        make_variant(product=p, stock=8, low_stock_threshold=7)
        make_variant(product=p, stock=100, low_stock_threshold=5)
        # NOT low: zero stock (that's out-of-stock), and inactive
        make_variant(product=p, stock=0, low_stock_threshold=5)
        make_variant(product=p, stock=2, low_stock_threshold=5, is_active=False)

        rows = get_low_stock_variants()

        assert [r["variant_id"] for r in rows] == [
            v_low1.id,
            v_low3.id,
            v_edge.id,
            v_high_thr.id,
        ]
        assert [r["stock"] for r in rows] == [1, 3, 5, 12]
        assert rows[0] == {
            "variant_id": v_low1.id,
            "product_id": p.id,
            "sku": v_low1.sku,
            "product_name": "Lipstick",
            "color": None,
            "stock": 1,
            "low_stock_threshold": 2,
        }

    def test_includes_colour_name_and_respects_limit(self, make_variant, make_product):
        from dashboard.services import get_low_stock_variants
        from shop.models import Color

        rose = Color.objects.create(name="Rose", hex_code="#ff007f")
        p = make_product(name="Blush")
        v = make_variant(product=p, stock=1)
        v.color = rose
        v.save(update_fields=["color"])
        make_variant(product=p, stock=2)
        make_variant(product=p, stock=3)

        rows = get_low_stock_variants(limit=2)

        assert len(rows) == 2
        assert rows[0]["color"] == "Rose"
        assert [r["stock"] for r in rows] == [1, 2]

    def test_empty(self):
        from dashboard.services import get_low_stock_variants

        assert get_low_stock_variants() == []

    def test_list_and_overview_count_always_agree(self, make_variant, make_product):
        from dashboard.services import get_low_stock_variants, get_product_stats

        p = make_product(name="X")
        for stock, thr in ((1, 5), (5, 5), (6, 5), (0, 5), (3, 3)):
            make_variant(product=p, stock=stock, low_stock_threshold=thr)

        stats = get_product_stats()
        assert stats["low_stock"] == len(get_low_stock_variants()) == 3


@pytest.mark.django_db
class TestOutOfStockVariants:

    def test_only_active_zero_stock(self, make_variant, make_product):
        from dashboard.services import get_out_of_stock_variants

        p = make_product(name="Mascara")
        active_zero = make_variant(product=p, stock=0)
        make_variant(product=p, stock=0, is_active=False)  # deactivated: excluded
        make_variant(product=p, stock=1)  # in stock
        make_variant(product=p, stock=9, low_stock_threshold=10)  # low, not out

        rows = get_out_of_stock_variants()

        assert len(rows) == 1
        row = rows[0]
        assert row["variant_id"] == active_zero.id
        assert row["product_id"] == p.id
        assert row["sku"] == active_zero.sku
        assert row["product_name"] == "Mascara"
        assert row["color"] is None
        assert "last_stock_change_at" in row

    def test_most_recently_sold_out_first_by_stock_movement_not_updated_at(
        self, make_variant, make_product
    ):
        """updated_at is never bumped by stock writes (update_fields=['stock'])."""
        from dashboard.services import get_out_of_stock_variants

        p = make_product(name="Palette")
        ran_out_long_ago = make_variant(product=p, stock=0)
        ran_out_today = make_variant(product=p, stock=0)
        _stock_move(ran_out_long_ago, _tehran(2026, 1, 1))
        _stock_move(ran_out_today, _tehran(2026, 3, 1))
        # updated_at deliberately DISAGREES with the movement times: the
        # "long ago" variant has the newest updated_at, so ordering by
        # updated_at would put it first (wrongly).
        from shop.models import ProductVariant

        ProductVariant.objects.filter(pk=ran_out_long_ago.pk).update(
            updated_at=_tehran(2026, 6, 1)
        )
        ProductVariant.objects.filter(pk=ran_out_today.pk).update(
            updated_at=_tehran(2026, 2, 1)
        )

        rows = get_out_of_stock_variants()

        assert [r["variant_id"] for r in rows] == [
            ran_out_today.id,
            ran_out_long_ago.id,
        ]
        assert rows[0]["last_stock_change_at"] == _tehran(2026, 3, 1)

    def test_variant_without_movements_falls_back_to_updated_at(
        self, make_variant, make_product
    ):
        from dashboard.services import get_out_of_stock_variants

        p = make_product(name="Seeded")
        v = make_variant(product=p, stock=0)
        row = get_out_of_stock_variants()[0]
        v.refresh_from_db()
        assert row["last_stock_change_at"] == v.updated_at

    def test_limit(self, make_variant, make_product):
        from dashboard.services import get_out_of_stock_variants

        p = make_product(name="Many")
        for _ in range(3):
            make_variant(product=p, stock=0)
        assert len(get_out_of_stock_variants(limit=2)) == 2

    def test_list_and_overview_count_always_agree(self, make_variant, make_product):
        from dashboard.services import get_out_of_stock_variants, get_product_stats

        p = make_product(name="X")
        for stock, active in ((0, True), (0, True), (0, False), (4, True)):
            make_variant(product=p, stock=stock, is_active=active)

        assert get_product_stats()["out_of_stock"] == 2
        assert len(get_out_of_stock_variants()) == 2


@pytest.mark.django_db
class TestInventoryEndpoints:

    @pytest.mark.parametrize("url", [LOW_STOCK_URL, OUT_OF_STOCK_URL])
    def test_admin_only(self, anon_client, customer_client, url):
        assert anon_client.get(url).status_code in (401, 403)
        assert customer_client.get(url).status_code == 403

    @pytest.mark.parametrize("url", [LOW_STOCK_URL, OUT_OF_STOCK_URL])
    def test_admin_and_superuser_allowed(self, admin_client, superuser_client, url):
        assert admin_client.get(url).status_code == 200
        assert superuser_client.get(url).status_code == 200

    def test_low_stock_payload_and_edit_link(
        self, admin_client, make_variant, make_product
    ):
        p = make_product(name="Lipstick")
        v = make_variant(product=p, stock=2, low_stock_threshold=5)
        make_variant(product=p, stock=50)

        resp = admin_client.get(LOW_STOCK_URL)

        assert resp.status_code == 200
        assert resp.data["count"] == 1
        (row,) = resp.data["results"]
        assert row["variant_id"] == v.id
        assert row["stock"] == 2 and row["low_stock_threshold"] == 5
        # absolute link straight to that variant's edit form in Django admin
        assert row["admin_url"].startswith("http")
        assert row["admin_url"].endswith(f"/shop/productvariant/{v.id}/change/")

    def test_edit_link_resolves_to_the_variant_change_form(
        self, admin_client, make_variant, make_product
    ):
        from urllib.parse import urlparse

        from django.urls import resolve

        v = make_variant(product=make_product(name="L"), stock=0)
        row = admin_client.get(OUT_OF_STOCK_URL).data["results"][0]

        match = resolve(urlparse(row["admin_url"]).path)
        assert match.url_name == "shop_productvariant_change"
        assert str(v.id) in match.args or str(v.id) == str(
            match.kwargs.get("object_id")
        )

    def test_out_of_stock_payload_excludes_inactive(
        self, admin_client, make_variant, make_product
    ):
        p = make_product(name="Mascara")
        active = make_variant(product=p, stock=0)
        make_variant(product=p, stock=0, is_active=False)

        resp = admin_client.get(OUT_OF_STOCK_URL)

        assert resp.data["count"] == 1
        assert [r["variant_id"] for r in resp.data["results"]] == [active.id]
        assert resp.data["results"][0]["admin_url"].endswith("/change/")

    def test_count_is_uncapped_total_while_results_honour_limit(
        self, admin_client, make_variant, make_product
    ):
        p = make_product(name="Many")
        for _ in range(3):
            make_variant(product=p, stock=1)

        resp = admin_client.get(LOW_STOCK_URL, {"limit": 2})

        assert resp.data["count"] == 3
        assert len(resp.data["results"]) == 2

    @pytest.mark.parametrize("url", [LOW_STOCK_URL, OUT_OF_STOCK_URL])
    @pytest.mark.parametrize("limit", ["abc", "0", "-1", "201"])
    def test_bad_limit_returns_400(self, admin_client, url, limit):
        resp = admin_client.get(url, {"limit": limit})
        assert resp.status_code == 400
        assert resp.data["detail"]

    def test_overview_summary_count_matches_endpoint_count(
        self, admin_client, make_variant, make_product
    ):
        p = make_product(name="X")
        for stock in (0, 1, 2, 30):
            make_variant(product=p, stock=stock)

        overview = admin_client.get(OVERVIEW_URL).data["product_stats"]

        assert overview["low_stock"] == admin_client.get(LOW_STOCK_URL).data["count"]
        assert (
            overview["out_of_stock"] == admin_client.get(OUT_OF_STOCK_URL).data["count"]
        )


# ══════════════════════════════════════════════════════════════════════════════
# Expiry reports: near-expiry / expired-but-still-active
# ══════════════════════════════════════════════════════════════════════════════

from datetime import date  # noqa: E402

NEAR_EXPIRY_URL = "/api/dashboard/admin/inventory/near-expiry/"
EXPIRED_URL = "/api/dashboard/admin/inventory/expired/"
FIXED_TODAY = date(2026, 6, 15)


@pytest.fixture
def fixed_today(monkeypatch):
    """Freeze the report's "today" so day-boundary cases are exact."""
    from dashboard import services

    monkeypatch.setattr(services, "_expiry_today", lambda: FIXED_TODAY)
    return FIXED_TODAY


@pytest.fixture
def make_expiring(make_variant, make_product):
    """make_expiring(offset_days, **variant_kwargs) → variant expiring today+offset
    (offset None → no expiration_date)."""
    from shop.models import ProductVariant

    product = make_product(name="Cream")

    def _make(offset_days, base=None, **kwargs):
        v = make_variant(product=product, **kwargs)
        if offset_days is not None:
            ProductVariant.objects.filter(pk=v.pk).update(
                expiration_date=(base or FIXED_TODAY) + timedelta(days=offset_days)
            )
            v.refresh_from_db()
        return v

    return _make


@pytest.mark.django_db
class TestNearExpiryVariants:

    def test_window_includes_and_excludes_correctly(self, fixed_today, make_expiring):
        from dashboard.services import get_near_expiry_variants

        today_v = make_expiring(0)  # expires today → still near, not expired
        soon = make_expiring(30)
        edge = make_expiring(90)  # last day of the window → included
        make_expiring(91)  # too far out
        make_expiring(400)  # way too far out
        make_expiring(-1)  # already expired → belongs to the other report
        make_expiring(-200)  # long expired → ditto
        make_expiring(None)  # no expiry data at all
        make_expiring(10, is_active=False)  # deactivated

        rows = get_near_expiry_variants()

        assert [r["variant_id"] for r in rows] == [today_v.id, soon.id, edge.id]

    def test_days_param_changes_the_window(self, fixed_today, make_expiring):
        from dashboard.services import get_near_expiry_variants

        a = make_expiring(5)
        b = make_expiring(30)
        c = make_expiring(60)
        d = make_expiring(90)

        ids = lambda days: [
            r["variant_id"] for r in get_near_expiry_variants(days)
        ]  # noqa: E731
        assert ids(0) == []
        assert ids(5) == [a.id]
        assert ids(30) == [a.id, b.id]
        assert ids(60) == [a.id, b.id, c.id]
        assert ids(90) == [a.id, b.id, c.id, d.id]

    def test_row_shape_sorted_soonest_first_and_limit(self, fixed_today, make_expiring):
        from dashboard.services import get_near_expiry_variants

        later = make_expiring(40, stock=7)
        sooner = make_expiring(12, stock=3)

        rows = get_near_expiry_variants()

        assert [r["variant_id"] for r in rows] == [sooner.id, later.id]
        assert rows[0] == {
            "variant_id": sooner.id,
            "product_id": sooner.product_id,
            "sku": sooner.sku,
            "product_name": "Cream",
            "color": None,
            "expiration_date": "2026-06-27",
            "days_until_expiry": 12,
            "stock": 3,
        }
        assert type(rows[0]["days_until_expiry"]) is int
        assert len(get_near_expiry_variants(limit=1)) == 1

    def test_includes_colour_name(self, fixed_today, make_expiring):
        from dashboard.services import get_near_expiry_variants
        from shop.models import Color

        v = make_expiring(5)
        v.color = Color.objects.create(name="Rose", hex_code="#ff007f")
        v.save(update_fields=["color"])
        assert get_near_expiry_variants()[0]["color"] == "Rose"

    def test_empty(self, fixed_today):
        from dashboard.services import get_near_expiry_variants

        assert get_near_expiry_variants() == []

    def test_today_matches_the_nightly_sweeps_definition(self):
        """Same UTC-date 'today' as shop.tasks / NearExpiryFilter (see helper)."""
        from dashboard.services import _expiry_today

        assert _expiry_today() == timezone.now().date()


@pytest.mark.django_db
class TestExpiredStillActiveVariants:

    def test_finds_expired_but_active_only(self, fixed_today, make_expiring):
        from dashboard.services import get_expired_still_active_variants

        yesterday = make_expiring(-1)
        long_ago = make_expiring(-200)
        make_expiring(0)  # expires today → not yet expired
        make_expiring(30)  # in the future
        make_expiring(-5, is_active=False)  # already swept/deactivated
        make_expiring(None)  # unknown expiry ≠ expired

        rows = get_expired_still_active_variants()

        # most overdue first
        assert [r["variant_id"] for r in rows] == [long_ago.id, yesterday.id]
        assert [r["days_until_expiry"] for r in rows] == [-200, -1]
        assert rows[1]["expiration_date"] == "2026-06-14"
        assert set(rows[0]) == {
            "variant_id",
            "product_id",
            "sku",
            "product_name",
            "color",
            "expiration_date",
            "days_until_expiry",
            "stock",
        }

    def test_limit(self, fixed_today, make_expiring):
        from dashboard.services import get_expired_still_active_variants

        for offset in (-1, -2, -3):
            make_expiring(offset)
        assert len(get_expired_still_active_variants(limit=2)) == 2

    def test_near_expiry_and_expired_reports_never_overlap(
        self, fixed_today, make_expiring
    ):
        from dashboard.services import (
            get_expired_still_active_variants,
            get_near_expiry_variants,
        )

        for offset in (-30, -1, 0, 1, 30, 90, 200):
            make_expiring(offset)

        near = {r["variant_id"] for r in get_near_expiry_variants(365)}
        expired = {r["variant_id"] for r in get_expired_still_active_variants()}
        assert near and expired and not (near & expired)

    def test_empties_once_the_nightly_sweep_has_run(self, make_expiring):
        """Simulate the sweep NOT having run, then running it (real clock)."""
        from dashboard.services import get_expired_still_active_variants
        from shop.tasks import deactivate_expired_variants

        real_today = timezone.now().date()
        make_expiring(-3, base=real_today)
        make_expiring(-40, base=real_today)
        make_expiring(10, base=real_today)

        assert len(get_expired_still_active_variants()) == 2  # sweep hasn't run

        deactivate_expired_variants()

        assert get_expired_still_active_variants() == []  # safety net clears


@pytest.mark.django_db
class TestExpiryEndpoints:

    @pytest.mark.parametrize("url", [NEAR_EXPIRY_URL, EXPIRED_URL])
    def test_admin_only(self, anon_client, customer_client, url):
        assert anon_client.get(url).status_code in (401, 403)
        assert customer_client.get(url).status_code == 403

    @pytest.mark.parametrize("url", [NEAR_EXPIRY_URL, EXPIRED_URL])
    def test_admin_and_superuser_allowed(
        self, admin_client, superuser_client, fixed_today, url
    ):
        assert admin_client.get(url).status_code == 200
        assert superuser_client.get(url).status_code == 200

    def test_near_expiry_default_is_90_days(
        self, admin_client, fixed_today, make_expiring
    ):
        inside = make_expiring(90)
        make_expiring(91)

        resp = admin_client.get(NEAR_EXPIRY_URL)

        assert resp.status_code == 200
        assert resp.data["days"] == 90
        assert resp.data["count"] == 1
        (row,) = resp.data["results"]
        assert row["variant_id"] == inside.id
        assert row["admin_url"].endswith(f"/shop/productvariant/{inside.id}/change/")

    def test_days_query_param_changes_results(
        self, admin_client, fixed_today, make_expiring
    ):
        a = make_expiring(10)
        make_expiring(60)

        r30 = admin_client.get(NEAR_EXPIRY_URL, {"days": 30})
        r90 = admin_client.get(NEAR_EXPIRY_URL, {"days": 90})

        assert [r["variant_id"] for r in r30.data["results"]] == [a.id]
        assert r30.data["days"] == 30 and r30.data["count"] == 1
        assert r90.data["count"] == 2

    @pytest.mark.parametrize("days", ["abc", "-1", "366", "", "1.5"])
    def test_bad_days_returns_400(self, admin_client, fixed_today, days):
        resp = admin_client.get(NEAR_EXPIRY_URL, {"days": days})
        assert resp.status_code == 400
        assert "days" in resp.data["detail"]

    @pytest.mark.parametrize("url", [NEAR_EXPIRY_URL, EXPIRED_URL])
    @pytest.mark.parametrize("limit", ["abc", "0", "201"])
    def test_bad_limit_returns_400(self, admin_client, fixed_today, url, limit):
        assert admin_client.get(url, {"limit": limit}).status_code == 400

    def test_count_is_uncapped_total(self, admin_client, fixed_today, make_expiring):
        for offset in (1, 2, 3):
            make_expiring(offset)
        resp = admin_client.get(NEAR_EXPIRY_URL, {"limit": 2})
        assert resp.data["count"] == 3 and len(resp.data["results"]) == 2

    def test_expired_endpoint_payload(self, admin_client, fixed_today, make_expiring):
        overdue = make_expiring(-9, stock=4)
        make_expiring(-9, is_active=False)
        make_expiring(5)

        resp = admin_client.get(EXPIRED_URL)

        assert resp.status_code == 200
        assert resp.data["count"] == 1
        (row,) = resp.data["results"]
        assert row["variant_id"] == overdue.id
        assert row["days_until_expiry"] == -9
        assert row["stock"] == 4
        assert row["admin_url"].endswith(f"/shop/productvariant/{overdue.id}/change/")

    def test_existing_stock_endpoints_unaffected_by_refactor(
        self, admin_client, make_variant, make_product
    ):
        make_variant(product=make_product(name="X"), stock=1)
        resp = admin_client.get(LOW_STOCK_URL)
        assert resp.status_code == 200 and resp.data["count"] == 1
        assert "days" not in resp.data


# ══════════════════════════════════════════════════════════════════════════════
# Coupon usage / performance report
# ══════════════════════════════════════════════════════════════════════════════

COUPON_USAGE_URL = "/api/dashboard/admin/promotions/coupon-usage/"


@pytest.fixture
def make_coupon(db):
    from promotions.models import Coupon

    def _make(code, max_uses=None, **kwargs):
        defaults = dict(
            discount_type="percent",
            percent_off=10,
            valid_from=timezone.now() - timedelta(days=30),
            valid_until=timezone.now() + timedelta(days=30),
            max_uses=max_uses,
        )
        defaults.update(kwargs)
        return Coupon.objects.create(code=code, **defaults)

    return _make


@pytest.fixture
def redeem(make_order, customer):
    """redeem(coupon, subtotal, discount) → completed redemption on a new order;
    redeem(coupon, discount=…, completed=False) → in-progress (cart-only)."""
    from order.models import Order
    from promotions.models import CouponRedemption

    def _redeem(coupon, subtotal=1_000_000, discount=100_000, completed=True):
        order = None
        if completed:
            order = make_order(user=customer, status="delivered", total=subtotal)
            Order.objects.filter(pk=order.pk).update(
                subtotal=subtotal, discount=discount, total=subtotal - discount
            )
        return CouponRedemption.objects.create(
            coupon=coupon, user=customer, order=order, discount_amount=discount
        )

    return _redeem


def _row(rows, code):
    return next(r for r in rows if r["code"] == code)


@pytest.mark.django_db
class TestCouponUsageReport:

    def test_three_completed_redemptions_exact_figures(self, make_coupon, redeem):
        from dashboard.services import get_coupon_usage_report

        c = make_coupon("SAVE10")
        redeem(c, subtotal=1_000_000, discount=100_000)
        redeem(c, subtotal=2_500_000, discount=250_000)
        redeem(c, subtotal=600_000, discount=60_000)

        row = _row(get_coupon_usage_report(), "SAVE10")

        assert row["coupon_id"] == c.id
        assert row["discount_type"] == "percent"
        assert row["redemption_count"] == 3
        assert row["total_discount_given"] == 410_000  # Σ actual discount_amount
        assert row["total_order_value"] == 4_100_000  # Σ order subtotals
        assert row["is_active"] is True
        assert row["valid_until"] == c.valid_until.isoformat()
        for key in ("redemption_count", "total_discount_given", "total_order_value"):
            assert type(row[key]) is int

    def test_discount_is_the_frozen_redemption_amount_not_recomputed(
        self, make_coupon, redeem
    ):
        from dashboard.services import get_coupon_usage_report

        c = make_coupon("FROZEN", percent_off=50)  # live rule would say 50%
        redeem(c, subtotal=1_000_000, discount=70_000)  # what was actually given

        assert _row(get_coupon_usage_report(), "FROZEN")["total_discount_given"] == (
            70_000
        )

    def test_in_progress_redemptions_do_not_count_toward_anything(
        self, make_coupon, redeem
    ):
        from dashboard.services import get_coupon_usage_report

        c = make_coupon("CARTONLY", max_uses=10)
        redeem(c, subtotal=1_000_000, discount=100_000)  # completed
        redeem(c, discount=999_990, completed=False)  # abandoned-cart applications
        redeem(c, discount=999_990, completed=False)

        row = _row(get_coupon_usage_report(), "CARTONLY")

        assert row["redemption_count"] == 1
        assert row["total_discount_given"] == 100_000
        assert row["total_order_value"] == 1_000_000
        assert row["usage_rate_pct"] == 10.0

    def test_coupon_with_only_in_progress_redemptions_reports_zeros(
        self, make_coupon, redeem
    ):
        from dashboard.services import get_coupon_usage_report

        c = make_coupon("ONLYCART")
        redeem(c, discount=50_000, completed=False)

        row = _row(get_coupon_usage_report(), "ONLYCART")
        assert (
            row["redemption_count"],
            row["total_discount_given"],
            row["total_order_value"],
        ) == (0, 0, 0)

    def test_unlimited_coupon_has_null_usage_rate(self, make_coupon, redeem):
        from dashboard.services import get_coupon_usage_report

        c = make_coupon("UNLIMITED", max_uses=None)
        redeem(c)
        redeem(c)

        row = _row(get_coupon_usage_report(), "UNLIMITED")
        assert row["max_uses"] is None
        assert row["usage_rate_pct"] is None
        assert row["redemption_count"] == 2

    def test_usage_rate_percentage(self, make_coupon, redeem):
        from dashboard.services import get_coupon_usage_report

        quarter = make_coupon("QUARTER", max_uses=8)
        thirds = make_coupon("THIRDS", max_uses=3)
        full = make_coupon("FULL", max_uses=2)
        for _ in range(2):
            redeem(quarter)
        redeem(thirds)
        for _ in range(2):
            redeem(full)

        rows = get_coupon_usage_report()
        assert _row(rows, "QUARTER")["usage_rate_pct"] == 25.0
        assert _row(rows, "THIRDS")["usage_rate_pct"] == 33.3  # rounded to 1 dp
        assert _row(rows, "FULL")["usage_rate_pct"] == 100.0

    def test_zero_max_uses_is_fully_used_not_a_division_error_or_unlimited(
        self, make_coupon
    ):
        from dashboard.services import get_coupon_usage_report

        make_coupon("NOUSES", max_uses=0)
        assert _row(get_coupon_usage_report(), "NOUSES")["usage_rate_pct"] == 100.0

    def test_ordered_by_redemption_count_descending(self, make_coupon, redeem):
        from dashboard.services import get_coupon_usage_report

        few = make_coupon("FEW")
        many = make_coupon("MANY")
        mid = make_coupon("MID")
        unused = make_coupon("UNUSED")
        redeem(few)
        for _ in range(3):
            redeem(many)
        for _ in range(2):
            redeem(mid)

        codes = [r["code"] for r in get_coupon_usage_report()]
        assert codes == ["MANY", "MID", "FEW", "UNUSED"]
        assert unused.code in codes  # never-redeemed coupons still listed

    def test_ties_break_by_discount_then_code(self, make_coupon, redeem):
        from dashboard.services import get_coupon_usage_report

        a = make_coupon("AAA")
        b = make_coupon("BBB")
        c = make_coupon("CCC")
        redeem(a, discount=10_000)
        redeem(b, discount=90_000)  # same count, more discount → first
        redeem(c, discount=10_000)  # ties with AAA → code order

        assert [r["code"] for r in get_coupon_usage_report()] == ["BBB", "AAA", "CCC"]

    def test_limit(self, make_coupon):
        from dashboard.services import get_coupon_usage_report

        for i in range(3):
            make_coupon(f"C{i}")
        assert len(get_coupon_usage_report(limit=2)) == 2

    def test_each_coupon_only_counts_its_own_redemptions(self, make_coupon, redeem):
        from dashboard.services import get_coupon_usage_report

        a = make_coupon("A1")
        b = make_coupon("B1")
        redeem(a, subtotal=1_000_000, discount=100_000)
        redeem(b, subtotal=3_000_000, discount=300_000)
        redeem(b, subtotal=3_000_000, discount=300_000)

        rows = get_coupon_usage_report()
        assert _row(rows, "A1")["total_order_value"] == 1_000_000
        assert _row(rows, "B1")["total_order_value"] == 6_000_000
        assert _row(rows, "B1")["total_discount_given"] == 600_000

    def test_inactive_and_expired_coupons_are_still_reported(self, make_coupon, redeem):
        from dashboard.services import get_coupon_usage_report

        c = make_coupon(
            "OLD",
            is_active=False,
            valid_from=timezone.now() - timedelta(days=60),
            valid_until=timezone.now() - timedelta(days=30),
        )
        redeem(c)

        row = _row(get_coupon_usage_report(), "OLD")
        assert row["is_active"] is False
        assert row["redemption_count"] == 1

    def test_fixed_amount_coupon_type(self, make_coupon):
        from dashboard.services import get_coupon_usage_report

        make_coupon("FIX", discount_type="fixed", percent_off=None, fixed_amount=50_000)
        assert _row(get_coupon_usage_report(), "FIX")["discount_type"] == "fixed"

    def test_cancelled_order_drops_out_of_the_report(
        self, make_coupon, redeem, customer
    ):
        """cancel_order() deletes the redemption, so it stops counting."""
        from dashboard.services import get_coupon_usage_report
        from order.services.cancellation import cancel_order

        c = make_coupon("CANCEL")
        kept = redeem(c, subtotal=1_000_000, discount=100_000)
        cancelled = redeem(c, subtotal=2_000_000, discount=200_000)
        assert _row(get_coupon_usage_report(), "CANCEL")["redemption_count"] == 2

        cancelled.order.status = "pending"
        cancelled.order.save(update_fields=["status"])
        cancel_order(cancelled.order, actor=customer)

        row = _row(get_coupon_usage_report(), "CANCEL")
        assert row["redemption_count"] == 1
        assert row["total_discount_given"] == kept.discount_amount == 100_000
        assert row["total_order_value"] == 1_000_000


@pytest.mark.django_db
class TestCouponUsageEndpoint:

    def test_admin_only(self, anon_client, customer_client):
        assert anon_client.get(COUPON_USAGE_URL).status_code in (401, 403)
        assert customer_client.get(COUPON_USAGE_URL).status_code == 403

    def test_admin_and_superuser_allowed(self, admin_client, superuser_client):
        assert admin_client.get(COUPON_USAGE_URL).status_code == 200
        assert superuser_client.get(COUPON_USAGE_URL).status_code == 200

    def test_payload(self, admin_client, make_coupon, redeem):
        c = make_coupon("PAY", max_uses=4)
        redeem(c, subtotal=1_000_000, discount=100_000)
        redeem(c, discount=999_990, completed=False)
        make_coupon("FREE", max_uses=None)

        resp = admin_client.get(COUPON_USAGE_URL)

        assert resp.status_code == 200
        assert resp.data["count"] == 2
        pay, free = resp.data["results"]
        assert pay["code"] == "PAY" and pay["redemption_count"] == 1
        assert pay["usage_rate_pct"] == 25.0
        assert pay["total_discount_given"] == 100_000
        assert pay["total_order_value"] == 1_000_000
        assert free["usage_rate_pct"] is None  # frontend shows "Unlimited"

    def test_limit_and_uncapped_count(self, admin_client, make_coupon):
        for i in range(3):
            make_coupon(f"L{i}")
        resp = admin_client.get(COUPON_USAGE_URL, {"limit": 2})
        assert resp.data["count"] == 3 and len(resp.data["results"]) == 2

    @pytest.mark.parametrize("limit", ["abc", "0", "201"])
    def test_bad_limit_returns_400(self, admin_client, limit):
        assert admin_client.get(COUPON_USAGE_URL, {"limit": limit}).status_code == 400
