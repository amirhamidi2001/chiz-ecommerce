from decimal import Decimal

import pytest

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_delivered_order(make_order, user=None, total=Decimal("100.00")):
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

        _make_delivered_order(make_order, user=customer, total=Decimal("250.00"))
        data = get_admin_overview("30d")
        assert data["revenue"]["current"] >= 250.0

    def test_cancelled_orders_excluded_from_revenue(self, make_order, customer):
        from dashboard.services import get_admin_overview

        make_order(user=customer, status="cancelled", total=Decimal("999.00"))
        data = get_admin_overview("30d")
        # Cancelled should not contribute to revenue
        assert data["revenue"]["current"] == 0.0

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

    def test_revenue_values_are_floats(self, make_order, customer):
        from dashboard.services import get_monthly_revenue

        _make_delivered_order(make_order)
        result = get_monthly_revenue(12)
        for item in result:
            assert isinstance(item["revenue"], float)


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

        make_user(email="admin1@example.com", user_type=2)
        make_user(email="super1@example.com", user_type=3)
        make_user(email="cust1@example.com", user_type=1)
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

        make_order(user=customer, status="delivered", total=Decimal("100.00"))
        make_order(user=customer, status="cancelled", total=Decimal("50.00"))
        summary = get_user_summary(customer)
        assert summary["total_spent"] == 100.0

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
        for item in results:
            assert "product_name" in item
            assert "total_sold" in item
            assert "revenue" in item
