from datetime import timedelta
from decimal import Decimal

from accounts.models import UserType
from cart.models import CartItem
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.utils import timezone
from order.models import Order, OrderItem
from shop.models import Product, ProductVariant, Review

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
    # NOTE: these now count VARIANTS, not products, since Epic 3 moved
    # authoritative stock tracking to ProductVariant.stock — a product
    # with 3 variants where 1 is low-stock now contributes 1 to this
    # count, not the product itself. Product.stock is a stale,
    # unmaintained field (Task 3.1.1.5) and is no longer queried here.
    # Follow-up: if the admin dashboard frontend labels this metric
    # "Low stock products" / "Out of stock products", that copy is now
    # slightly inaccurate and should be updated to say "variants" —
    # not fixed here since it's a frontend-only concern.
    low_stock = ProductVariant.objects.filter(
        stock__gt=0, stock__lte=F("low_stock_threshold"), is_active=True
    ).count()
    out_of_stock = ProductVariant.objects.filter(stock=0, is_active=True).count()

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
        "admins": User.objects.filter(
            type__in=[UserType.ADMIN, UserType.SUPERUSER]
        ).count(),
    }


def get_product_stats() -> dict:
    return {
        "total": Product.objects.count(),
        "on_sale": Product.objects.filter(is_sale=True).count(),
        "new": Product.objects.filter(is_new=True).count(),
        # NOTE: these now count VARIANTS, not products — see the
        # matching comment in get_admin_overview() above. Follow-up:
        # update frontend label copy ("... products") if it hasn't
        # already been adjusted for the variant-based catalog.
        "out_of_stock": ProductVariant.objects.filter(stock=0, is_active=True).count(),
        "low_stock": ProductVariant.objects.filter(
            stock__gt=0, stock__lte=F("low_stock_threshold"), is_active=True
        ).count(),
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


# ─── Guest (session-based) wishlist ──────────────────────────────────────────


def get_wishlist_owner_kwargs(request):
    """
    Return the filter/creation kwargs identifying the current request's
    wishlist owner: the authenticated user, or else the anonymous session.

    Unlike Cart (one row per owner, so cart.views.get_or_create_cart can
    return "the" cart), a wishlist is many rows per owner — so this returns
    kwargs usable with Wishlist.objects.filter(**kwargs) and
    serializer.save(**kwargs) rather than a single object.

    For anonymous callers the session is created on demand, so the
    returned session_key is never None (important: filter(session_key=None)
    would silently become `IS NULL` and match every user-owned row).
    """
    if request.user.is_authenticated:
        return {"user": request.user}
    if not request.session.session_key:
        request.session.create()
    return {"session_key": request.session.session_key}


def merge_session_wishlist_into_user_wishlist(request, user):
    """
    Move the current session's guest wishlist items onto `user`, then drop
    the session rows. A product the user already has wishlisted is NOT
    duplicated — the session copy is simply discarded.

    Called alongside merge_session_cart_into_user_cart() from all three
    login/registration entry points (LoginView, OTPVerifyView,
    RegisterView).

    Rows are re-pointed in place (rather than cloned like the cart merge)
    so each item keeps its original `added_at` and the wishlist ordering
    survives the merge.
    """
    from dashboard.models import Wishlist

    session_key = request.session.session_key
    if not session_key:
        return

    session_items = Wishlist.objects.filter(session_key=session_key)
    if not session_items.exists():
        return

    with transaction.atomic():
        already_owned = set(
            Wishlist.objects.filter(user=user).values_list("product_id", flat=True)
        )
        for item in session_items:
            if item.product_id in already_owned:
                continue  # dupe — cleaned up by the delete below
            try:
                # Savepoint: a concurrent add of the same product by this
                # user (second tab) must not turn a login into a 500.
                with transaction.atomic():
                    Wishlist.objects.filter(pk=item.pk).update(
                        user=user, session_key=None
                    )
            except IntegrityError:
                continue
        # Whatever is still session-owned is a skipped duplicate.
        Wishlist.objects.filter(session_key=session_key).delete()


# ─── Wishlist → cart ─────────────────────────────────────────────────────────


def get_purchasable_variants(product):
    """
    The variants of `product` a customer could put in their cart right now,
    cheapest first (price, then id — a stable order for a shade picker).

    Must agree with what the cart itself accepts, i.e.
    cart.serializers.CartItemSerializer.validate_variant_id: active, in
    stock, and not past its expiration_date (a NULL date is not "expired").
    The expiry rule matters because deactivate_expired_variants only runs
    nightly, so an expired variant can still be is_active=True for hours —
    offering it here would let a wishlist move sneak past the cart's own
    expiry block. (A parity test pins this to the cart's validator.)
    """
    today = timezone.now().date()
    return list(
        product.variants.filter(is_active=True, stock__gt=0)
        .filter(Q(expiration_date__isnull=True) | Q(expiration_date__gte=today))
        .select_related("color")
        .order_by("price", "id")
    )


def move_wishlist_item_to_cart(cart, wishlist_item, variant):
    """
    Add one unit of `variant` to `cart` (incrementing an existing line
    rather than creating a duplicate) and delete `wishlist_item`, as one
    atomic step: the item can't be lost (deleted but never added) or
    duplicated (added but left on the wishlist).

    The wishlist row is locked first, so two concurrent moves of the same
    item (double-click, two tabs) can't both add a unit. Returns False,
    changing nothing, if the item is already gone.
    """
    from dashboard.models import Wishlist

    with transaction.atomic():
        if (
            Wishlist.objects.select_for_update().filter(pk=wishlist_item.pk).first()
            is None
        ):
            return False
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, variant=variant, defaults={"quantity": 1}
        )
        if not created:
            CartItem.objects.filter(pk=cart_item.pk).update(
                quantity=F("quantity") + 1, updated_at=timezone.now()
            )
        wishlist_item.delete()
    return True
