from datetime import date, datetime, time, timedelta

from accounts.models import UserType
from cart.models import CartItem
from core.money import percent_of
from dashboard.models import PriceAdjustmentLog
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Avg, BigIntegerField, Count, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.utils import timezone
from order.models import Order, OrderItem
from promotions.models import Coupon
from shop.models import Product, ProductVariant, Review, StockMovement

User = get_user_model()

_ACTIVE_STATUSES = ("processing", "shipped", "delivered")


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _pct_change(current, previous) -> float:
    cur = float(current or 0)
    prev = float(previous or 0)
    if prev == 0:
        return 100.0 if cur > 0 else 0.0
    return round(((cur - prev) / prev) * 100, 1)


_MIN_CUSTOM_YEAR = 2000
_MAX_CUSTOM_SPAN = timedelta(days=3660)  # ~10 years


class InvalidDateRange(ValueError):
    """A custom start/end pair is missing, malformed, or not start < end.

    Raised by get_date_range()/parse_custom_range(); the admin overview view
    turns it into a 400 instead of letting it surface as a 500.
    """


def _parse_bound(raw, name: str, *, end_of_day: bool):
    """
    Parse one custom-range bound into an aware datetime.

    Accepts a date ("2026-11-01"), an ISO datetime ("2026-11-01T09:30:00",
    with or without offset), or an already-built date/datetime. A bare date
    is interpreted in the project time zone (Asia/Tehran): the start bound
    becomes 00:00 of that day and the end bound the last instant of it, so
    `start=2026-11-01&end=2026-11-07` covers all seven days inclusive.
    """
    if isinstance(raw, datetime):
        value = raw
    elif isinstance(raw, date):
        value = datetime.combine(raw, time.max if end_of_day else time.min)
    else:
        text = str(raw).strip()
        try:
            if "T" in text or " " in text:
                value = datetime.fromisoformat(text)
            else:
                day = date.fromisoformat(text)
                value = datetime.combine(day, time.max if end_of_day else time.min)
        except ValueError:
            raise InvalidDateRange(
                f"'{name}' must be an ISO date (YYYY-MM-DD) or datetime."
            ) from None
    try:
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
    except (ValueError, OverflowError):
        raise InvalidDateRange(f"'{name}' is out of the supported range.") from None
    return value


def parse_custom_range(start_param, end_param):
    """Validate a custom range and return (start, end) aware datetimes."""
    if not start_param or not end_param:
        raise InvalidDateRange(
            "period=custom requires both 'start' and 'end' query parameters."
        )
    start = _parse_bound(start_param, "start", end_of_day=False)
    end = _parse_bound(end_param, "end", end_of_day=True)
    if start >= end:
        raise InvalidDateRange("'start' must be earlier than 'end'.")
    # Bounds that would overflow the previous-period arithmetic (or make the
    # daily chart absurdly large) are rejected up front instead of 500-ing.
    if start.year < _MIN_CUSTOM_YEAR or end - start > _MAX_CUSTOM_SPAN:
        raise InvalidDateRange(
            f"Custom range must start in {_MIN_CUSTOM_YEAR} or later "
            f"and span at most {_MAX_CUSTOM_SPAN.days} days."
        )
    return start, end


def get_date_range(period: str, start_param=None, end_param=None):
    """
    Return (start, end) aware datetimes.

    Named presets: "7d", "30d", "90d", "1y" (unknown names fall back to 30d,
    as before). "custom" uses the explicit start/end and is strict: missing,
    malformed, or reversed bounds raise InvalidDateRange rather than being
    silently replaced by a preset.
    """
    if period == "custom":
        return parse_custom_range(start_param, end_param)
    end = timezone.now()
    mapping = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
    days = mapping.get(period, 30)
    return end - timedelta(days=days), end


# ─── Admin Analytics ─────────────────────────────────────────────────────────


def get_admin_overview(period: str = "30d", start=None, end=None) -> dict:
    """
    Current-vs-previous-period KPIs plus a daily revenue chart.

    `period` is a preset ("7d"/"30d"/"90d"/"1y") or "custom" with explicit
    `start`/`end` (see get_date_range). The comparison window is the same
    length, immediately before `start`. All money values are int Rial.
    """
    start, end = get_date_range(period, start, end)
    delta = end - start
    prev_start, prev_end = start - delta, start

    cur_orders = Order.objects.filter(created_at__range=[start, end])
    prev_orders = Order.objects.filter(created_at__range=[prev_start, prev_end])

    # Revenue
    cur_rev = cur_orders.filter(status__in=_ACTIVE_STATUSES).aggregate(
        t=Coalesce(Sum("total"), 0)
    )["t"]
    prev_rev = prev_orders.filter(status__in=_ACTIVE_STATUSES).aggregate(
        t=Coalesce(Sum("total"), 0)
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
    low_stock = low_stock_variants_qs().count()
    out_of_stock = out_of_stock_variants_qs().count()

    # Daily revenue chart
    revenue_chart = list(
        Order.objects.filter(
            created_at__range=[start, end],
            status__in=_ACTIVE_STATUSES,
        )
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(revenue=Coalesce(Sum("total"), 0), orders=Count("id"))
        .order_by("date")
        .values("date", "revenue", "orders")
    )

    return {
        "revenue": {
            "current": int(cur_rev),
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
                "revenue": int(item["revenue"]),
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
            revenue=Coalesce(Sum("total"), 0),
            orders=Count("id"),
        )
        .order_by("month")
    )
    return [
        {
            "month": item["month"].strftime("%b %Y"),
            "revenue": int(item["revenue"]),
            "orders": item["orders"],
        }
        for item in data
    ]


def _items_in_range(start=None, end=None):
    """
    OrderItems whose parent order was created within [start, end].

    Either bound may be omitted (open-ended); with neither this is all-time
    history. The view layer always supplies both or neither.
    """
    qs = OrderItem.objects.all()
    if start is not None:
        qs = qs.filter(order__created_at__gte=start)
    if end is not None:
        qs = qs.filter(order__created_at__lte=end)
    return qs


# Σ(unit_price × quantity) in whole Rial. Explicit BigIntegerField keeps the
# result an int regardless of how Django would infer the mixed
# RialField × PositiveIntegerField expression.
def _line_revenue():
    return Coalesce(
        Sum(F("unit_price") * F("quantity"), output_field=BigIntegerField()), 0
    )


def get_top_products(limit: int = 10, start=None, end=None) -> list:
    """Best-selling products by units sold, optionally within a date range."""
    rows = (
        _items_in_range(start, end)
        .values("product_id", "product_name")
        .annotate(total_sold=Sum("quantity"), revenue=_line_revenue())
        .order_by("-total_sold", "-revenue", "product_name")[:limit]
    )
    return [
        {
            "product_id": r["product_id"],
            "product_name": r["product_name"],
            "total_sold": r["total_sold"],
            "revenue": int(r["revenue"]),
        }
        for r in rows
    ]


def get_top_variants(limit: int = 10, start=None, end=None) -> list:
    """
    Best-selling variants (shade/size) by units sold, optionally within a
    date range.

    Built from the frozen OrderItem snapshot (variant_sku,
    variant_attributes_json), so it reports what was actually sold even if
    the variant was later renamed or deleted. Rows with a blank variant_sku
    (pre-Epic-3 orders, or an unpopulated snapshot) are excluded.

    Aggregation is by variant_sku alone — SKUs are globally unique, so that
    IS the variant. Grouping by name/attributes too would split one variant
    into several rows after a product or colour rename. The name and
    attributes shown are the most recent snapshot among the matching items.
    """
    qs = _items_in_range(start, end).exclude(variant_sku="")
    rows = list(
        qs.values("variant_sku")
        .annotate(total_sold=Sum("quantity"), revenue=_line_revenue())
        .order_by("-total_sold", "-revenue", "variant_sku")[:limit]
    )
    if not rows:
        return []

    latest = {
        item["variant_sku"]: item
        for item in qs.filter(variant_sku__in=[r["variant_sku"] for r in rows])
        .order_by("variant_sku", "-order__created_at", "-id")
        .distinct("variant_sku")  # PostgreSQL DISTINCT ON (project is PG-only)
        .values("variant_sku", "product_name", "variant_attributes_json")
    }
    return [
        {
            "variant_sku": r["variant_sku"],
            "product_name": latest[r["variant_sku"]]["product_name"],
            "variant_attributes": latest[r["variant_sku"]]["variant_attributes_json"],
            "total_sold": r["total_sold"],
            "revenue": int(r["revenue"]),
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
        "out_of_stock": out_of_stock_variants_qs().count(),
        "low_stock": low_stock_variants_qs().count(),
        "avg_rating": float(Product.objects.aggregate(a=Avg("rating"))["a"] or 0),
    }


# ─── Inventory lists ──────────────────────────────────────────────────────────
#
# The dashboard's low_stock / out_of_stock COUNTS and the lists below are all
# built from these two querysets, so a number on the overview can never
# disagree with the list an admin clicks into from it.


def low_stock_variants_qs():
    """Active variants at or below THEIR OWN low_stock_threshold (but not 0)."""
    return ProductVariant.objects.filter(
        is_active=True, stock__gt=0, stock__lte=F("low_stock_threshold")
    )


def out_of_stock_variants_qs():
    """Active variants with no stock. Deactivated ones are not restockable."""
    return ProductVariant.objects.filter(is_active=True, stock=0)


def get_low_stock_variants(limit: int = 50) -> list:
    """Low-stock variants, lowest stock first (most urgent), ties by SKU."""
    variants = (
        low_stock_variants_qs()
        .select_related("product", "color")
        .order_by("stock", "sku")[:limit]
    )
    return [
        {
            "variant_id": v.id,
            "product_id": v.product_id,
            "sku": v.sku,
            "product_name": v.product.name,
            "color": v.color.name if v.color else None,
            "stock": v.stock,
            "low_stock_threshold": v.low_stock_threshold,
        }
        for v in variants
    ]


def get_out_of_stock_variants(limit: int = 50) -> list:
    """
    Out-of-stock variants, most recently sold out first.

    "When it ran out" is the time of the variant's latest StockMovement, NOT
    ProductVariant.updated_at: every stock write in the codebase is
    save(update_fields=["stock"]), which never touches the auto_now
    updated_at. updated_at is only the fallback for a variant with no
    movement history (e.g. seeded directly).
    """
    last_movement = (
        StockMovement.objects.filter(variant=OuterRef("pk"))
        .order_by("-created_at")
        .values("created_at")[:1]
    )
    variants = (
        out_of_stock_variants_qs()
        .select_related("product", "color")
        .annotate(
            last_stock_change_at=Coalesce(Subquery(last_movement), F("updated_at"))
        )
        .order_by("-last_stock_change_at", "-id")[:limit]
    )
    return [
        {
            "variant_id": v.id,
            "product_id": v.product_id,
            "sku": v.sku,
            "product_name": v.product.name,
            "color": v.color.name if v.color else None,
            "last_stock_change_at": v.last_stock_change_at,
        }
        for v in variants
    ]


# ─── Expiry reports ───────────────────────────────────────────────────────────
#
# Mirrors shop.admin.NearExpiryFilter (the Django-admin filter) as dashboard
# data; the near-expiry window and the expired set are disjoint by
# construction (expiration_date >= today vs < today).


def _expiry_today() -> date:
    """
    The "today" used for every expiry comparison.

    Deliberately `timezone.now().date()` (the UTC date), NOT
    `timezone.localdate()`: shop.tasks.deactivate_expired_variants and
    NearExpiryFilter both use it, and the expired-but-still-active report
    below is a cross-check on that task. If it used a different day boundary
    it would flag healthy variants for a few hours every night (the Tehran
    date runs ahead of the UTC date). Moving the whole expiry feature to
    calendar-local days is a separate, cross-cutting change.
    """
    return timezone.now().date()


def near_expiry_variants_qs(days: int = 90):
    """Active variants expiring from today through today + `days` (inclusive)."""
    today = _expiry_today()
    return ProductVariant.objects.filter(
        is_active=True,
        expiration_date__isnull=False,
        expiration_date__gte=today,
        expiration_date__lte=today + timedelta(days=days),
    )


def expired_still_active_variants_qs():
    """Variants past their expiration_date that are still is_active=True."""
    return ProductVariant.objects.filter(
        is_active=True,
        expiration_date__isnull=False,
        expiration_date__lt=_expiry_today(),
    )


def _expiry_rows(qs, limit: int) -> list:
    today = _expiry_today()
    variants = qs.select_related("product", "color").order_by("expiration_date", "sku")[
        :limit
    ]
    return [
        {
            "variant_id": v.id,
            "product_id": v.product_id,
            "sku": v.sku,
            "product_name": v.product.name,
            "color": v.color.name if v.color else None,
            "expiration_date": v.expiration_date.isoformat(),
            # negative once expired (days overdue)
            "days_until_expiry": (v.expiration_date - today).days,
            "stock": v.stock,
        }
        for v in variants
    ]


def get_near_expiry_variants(days: int = 90, limit: int = 50) -> list:
    """Active variants expiring within `days` days, soonest first."""
    return _expiry_rows(near_expiry_variants_qs(days), limit)


def get_expired_still_active_variants(limit: int = 50) -> list:
    """
    Already-expired variants that are still active, most overdue first.

    A safety net independent of the nightly sweep
    (shop.tasks.deactivate_expired_variants). Rows with days_until_expiry of
    -1 can simply be waiting for tonight's run; entries that stay on the list
    for several days (very negative days_until_expiry) point at a sweep that
    isn't running, or at a deliberate reactivation.
    """
    return _expiry_rows(expired_still_active_variants_qs(), limit)


# ─── Coupon performance ───────────────────────────────────────────────────────


def coupon_usage_qs():
    """
    Every coupon annotated with its COMPLETED-redemption figures.

    Only redemptions tied to an order (order__isnull=False) count — the same
    rule promotions.services.validate_coupon() applies to max_uses — so a
    coupon merely applied to a not-yet-checked-out cart never inflates the
    report. Cancelling an order (or a failed payment) deletes its
    CouponRedemption (order.services.coupon), so cancelled orders drop out
    of every figure without a status filter here.

    All three aggregates ride the same single `redemptions` join and the
    redemption→order link is one-to-one, so no row fan-out can multiply
    the sums.
    """
    completed = Q(redemptions__order__isnull=False)
    return Coupon.objects.annotate(
        redemption_count=Count("redemptions", filter=completed),
        total_discount_given=Coalesce(
            Sum("redemptions__discount_amount", filter=completed), 0
        ),
        total_order_value=Coalesce(
            Sum("redemptions__order__subtotal", filter=completed), 0
        ),
    )


def get_coupon_usage_report(limit: int = 50) -> list:
    """
    Coupon performance, most-redeemed first (ties: most discount given, then
    code). Coupons never redeemed are included, with zeros, at the bottom.

    * total_discount_given — Σ of each completed redemption's frozen
      discount_amount (Rial).
    * total_order_value — Σ of those orders' subtotal (Rial): the gross
      value the coupon was applied to, i.e. "drove X at a cost of Y".
    * usage_rate_pct — redemption_count as a % of max_uses; None for an
      unlimited coupon (max_uses is None) — render it as "Unlimited". A
      max_uses of 0 means nothing can be redeemed (validate_coupon rejects
      it immediately), so it is reported as fully used (100.0) rather than
      divided by zero or mislabelled as unlimited. It can exceed 100 if
      max_uses was lowered after redemptions happened.
    """
    coupons = coupon_usage_qs().order_by(
        "-redemption_count", "-total_discount_given", "code"
    )[:limit]

    def usage_rate(c):
        if c.max_uses is None:
            return None
        if c.max_uses == 0:
            return 100.0
        return round(c.redemption_count / c.max_uses * 100, 1)

    return [
        {
            "coupon_id": c.id,
            "code": c.code,
            "discount_type": c.discount_type,
            "redemption_count": c.redemption_count,
            "max_uses": c.max_uses,
            "usage_rate_pct": usage_rate(c),
            "total_discount_given": int(c.total_discount_given),
            "total_order_value": int(c.total_order_value),
            "is_active": c.is_active,
            "valid_until": c.valid_until.isoformat(),
        }
        for c in coupons
    ]


# ─── Bulk price adjustment ────────────────────────────────────────────────────


def apply_price_adjustment(price: int, adjustment_type: str, value: int) -> int:
    """
    New integer-Rial price after one adjustment.

    Percentages go through core.money.percent_of — the project's single
    rounding rule (nearest whole Toman, ties up) — so a result is ALWAYS a
    multiple of 10 and satisfies the DB's whole-Toman CHECK constraint on
    ProductVariant.price; naive round(price * 1.07) would not. Fixed
    amounts must themselves be whole-Toman (the serializer enforces it), so
    the sum stays on the grid. Every decrease is floored at 0.
    """
    kinds = PriceAdjustmentLog.AdjustmentType
    if adjustment_type == kinds.PERCENT_INCREASE:
        return percent_of(price, 100 + value)
    if adjustment_type == kinds.PERCENT_DECREASE:
        return max(0, percent_of(price, 100 - value))
    if adjustment_type == kinds.FIXED_INCREASE:
        return price + value
    if adjustment_type == kinds.FIXED_DECREASE:
        return max(0, price - value)
    raise ValueError(f"Unknown adjustment_type: {adjustment_type!r}")


def plan_price_adjustment(variants, adjustment_type: str, value: int) -> list:
    """[(variant, new_price), …] for every variant in `variants`, in order."""
    return [
        (v, apply_price_adjustment(v.price, adjustment_type, value)) for v in variants
    ]


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
            "total": int(o.total),
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
        t=Coalesce(Sum("total"), 0)
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
        "total_spent": int(total_spent),
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
