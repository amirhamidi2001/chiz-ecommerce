from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.utils import timezone
from order.models import Order, OrderItem
from shop.models import Product, Review

User = get_user_model()

_ACTIVE_STATUSES = ("processing", "shipped", "delivered")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _pct_change(current, previous) -> float:
    cur = float(current or 0)
    prev = float(previous or 0)
    if prev == 0:
        return 100.0 if cur > 0 else 0.0
    return round(((cur - prev) / prev) * 100, 1)


def get_date_range(period: str):
    """Return (start, end) aware datetimes for a named period."""
    end = timezone.now()
    mapping = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
    days = mapping.get(period, 30)
    return end - timedelta(days=days), end


# ─── Admin Analytics ─────────────────────────────────────────────────────────


def get_admin_overview(period: str = "30d") -> dict:
    start, end = get_date_range(period)
    delta = end - start
    prev_start, prev_end = start - delta, start

    cur_orders = Order.objects.filter(created_at__range=[start, end])
    prev_orders = Order.objects.filter(created_at__range=[prev_start, prev_end])

    # Revenue
    cur_rev = cur_orders.filter(status__in=_ACTIVE_STATUSES).aggregate(
        t=Coalesce(Sum("total"), Decimal("0"))
    )["t"]
    prev_rev = prev_orders.filter(status__in=_ACTIVE_STATUSES).aggregate(
        t=Coalesce(Sum("total"), Decimal("0"))
    )["t"]

    # Orders
    cur_cnt = cur_orders.count()
    prev_cnt = prev_orders.count()

    # New users
    cur_users = User.objects.filter(created_date__range=[start, end]).count()
    prev_users = User.objects.filter(created_date__range=[prev_start, prev_end]).count()

    # Products
    total_products = Product.objects.count()
    low_stock = Product.objects.filter(stock__gt=0, stock__lte=5).count()
    out_of_stock = Product.objects.filter(stock=0).count()

    # Daily revenue chart
    revenue_chart = list(
        Order.objects.filter(
            created_at__range=[start, end],
            status__in=_ACTIVE_STATUSES,
        )
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(revenue=Coalesce(Sum("total"), Decimal("0")), orders=Count("id"))
        .order_by("date")
        .values("date", "revenue", "orders")
    )

    return {
        "revenue": {
            "current": float(cur_rev),
            "change": _pct_change(cur_rev, prev_rev),
        },
        "orders": {
            "current": cur_cnt,
            "change": _pct_change(cur_cnt, prev_cnt),
        },
        "users": {
            "current": cur_users,
            "change": _pct_change(cur_users, prev_users),
        },
        "products": {
            "total": total_products,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
        },
        "revenue_chart": [
            {
                "date": str(item["date"]),
                "revenue": float(item["revenue"]),
                "orders": item["orders"],
            }
            for item in revenue_chart
        ],
    }


def get_order_status_distribution() -> list:
    return list(
        Order.objects.values("status").annotate(count=Count("id")).order_by("-count")
    )


def get_monthly_revenue(months: int = 12) -> list:
    start = timezone.now() - timedelta(days=months * 31)
    data = (
        Order.objects.filter(
            created_at__gte=start,
            status__in=_ACTIVE_STATUSES,
        )
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(
            revenue=Coalesce(Sum("total"), Decimal("0")),
            orders=Count("id"),
        )
        .order_by("month")
    )
    return [
        {
            "month": item["month"].strftime("%b %Y"),
            "revenue": float(item["revenue"]),
            "orders": item["orders"],
        }
        for item in data
    ]


def get_top_products(limit: int = 10) -> list:
    rows = (
        OrderItem.objects.values("product_id", "product_name")
        .annotate(
            total_sold=Sum("quantity"),
            revenue=Coalesce(
                Sum(F("unit_price") * F("quantity"), output_field=DecimalField()),
                Decimal("0"),
            ),
        )
        .order_by("-total_sold")[:limit]
    )
    return [
        {
            "product_id": r["product_id"],
            "product_name": r["product_name"],
            "total_sold": r["total_sold"],
            "revenue": float(r["revenue"]),
        }
        for r in rows
    ]


def get_user_stats() -> dict:
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "total": User.objects.count(),
        "active": User.objects.filter(is_active=True).count(),
        "verified": User.objects.filter(is_verified=True).count(),
        "new_this_month": User.objects.filter(created_date__gte=month_start).count(),
        "admins": User.objects.filter(type__in=[2, 3]).count(),
    }


def get_product_stats() -> dict:
    return {
        "total": Product.objects.count(),
        "on_sale": Product.objects.filter(is_sale=True).count(),
        "new": Product.objects.filter(is_new=True).count(),
        "out_of_stock": Product.objects.filter(stock=0).count(),
        "low_stock": Product.objects.filter(stock__gt=0, stock__lte=5).count(),
        "avg_rating": float(Product.objects.aggregate(a=Avg("rating"))["a"] or 0),
    }


def get_recent_orders(limit: int = 10) -> list:
    orders = (
        Order.objects.select_related("user")
        .prefetch_related("items")
        .order_by("-created_at")[:limit]
    )
    return [
        {
            "id": o.id,
            "order_number": o.order_number,
            "full_name": o.full_name,
            "email": o.email,
            "status": o.status,
            "total": float(o.total),
            "items_count": o.items.count(),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


# ─── User Summary ─────────────────────────────────────────────────────────────


def get_user_summary(user) -> dict:
    from dashboard.models import Wishlist

    total_orders = user.orders.count()
    total_spent = user.orders.filter(status__in=_ACTIVE_STATUSES).aggregate(
        t=Coalesce(Sum("total"), Decimal("0"))
    )["t"]
    wishlist_count = Wishlist.objects.filter(user=user).count()

    full_name = ""
    try:
        full_name = user.profile.get_fullname()
    except Exception:
        pass

    reviews_count = Review.objects.filter(name=full_name).count() if full_name else 0
    pending_orders = user.orders.filter(status__in=["pending", "processing"]).count()

    return {
        "total_orders": total_orders,
        "total_spent": float(total_spent),
        "wishlist_count": wishlist_count,
        "reviews_count": reviews_count,
        "pending_orders": pending_orders,
    }
