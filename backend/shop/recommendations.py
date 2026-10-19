"""Behavioral product recommendations (co-purchase based)."""

from django.db.models import Count
from order.models import Order, OrderItem

from .models import Product

# Only orders that genuinely progressed past payment confirmation count as a
# "bought together" signal. PENDING (abandoned payment) and CANCELLED never do.
COMPLETED_ORDER_STATUSES = [
    Order.Status.PROCESSING,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
]


def get_frequently_bought_together(product_id: int, limit: int = 4) -> list[Product]:
    """
    Return up to `limit` products most frequently purchased in the SAME order
    as `product_id`, based on completed (non-cancelled) order history, ranked
    by co-occurrence frequency.

    Works at the PRODUCT level (not variant level): variant-level co-occurrence
    would fragment an already-sparse signal across shade/size combinations.

    Possible future optimization: a short-TTL cache on the endpoint (co-purchase
    patterns change slowly). Deliberately not built here.
    """
    order_ids = (
        OrderItem.objects.filter(
            product_id=product_id,
            order__status__in=COMPLETED_ORDER_STATUSES,
        )
        .values_list("order_id", flat=True)
        .distinct()
    )

    co_occurring_product_ids = (
        OrderItem.objects.filter(order_id__in=order_ids)
        .exclude(product_id=product_id)
        .exclude(product_id__isnull=True)
        .values("product_id")
        .annotate(co_occurrence_count=Count("order_id", distinct=True))
        # product_id tie-breaker keeps equal-count results deterministic
        .order_by("-co_occurrence_count", "product_id")[:limit]
    )
    product_ids_ranked = [row["product_id"] for row in co_occurring_product_ids]
    if not product_ids_ranked:
        return []

    # filter(id__in=...) does NOT preserve list order, so re-sort in Python to
    # keep the co-occurrence ranking.
    products = Product.objects.filter(id__in=product_ids_ranked).select_related(
        "category", "brand"
    )
    products_by_id = {p.id: p for p in products}
    return [products_by_id[pid] for pid in product_ids_ranked if pid in products_by_id]


def get_category_affinity_recommendations(
    viewed_product_ids: list[int],
    purchased_category_ids: list[int] | None = None,
    limit: int = 8,
) -> list[Product]:
    """
    Simple heuristic: recommend products from categories the visitor has
    recently viewed or purchased from, excluding products they've already
    viewed, favoring higher-rated products within those categories.

    This is NOT a machine-learning recommender — it is a deliberately simple,
    explainable category-affinity heuristic. The category set is the UNION of
    the viewed products' categories and the purchased categories; there is no
    per-category weighting. No signal at all -> [].
    """
    viewed_product_ids = list(viewed_product_ids or [])
    category_ids = {cid for cid in (purchased_category_ids or []) if cid is not None}
    if viewed_product_ids:
        viewed_categories = Product.objects.filter(
            id__in=viewed_product_ids
        ).values_list("category_id", flat=True)
        category_ids.update(cid for cid in viewed_categories if cid is not None)

    if not category_ids:
        return []

    return list(
        Product.objects.filter(category_id__in=category_ids)
        .exclude(id__in=viewed_product_ids)
        .select_related("category", "brand")
        # id tie-breaker keeps equal-rating results deterministic
        .order_by("-rating", "-reviews_count", "id")[:limit]
    )
