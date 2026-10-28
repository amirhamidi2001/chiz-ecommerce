"""Tests for the "frequently bought together" recommendation service + endpoint."""

from decimal import Decimal
from itertools import count

import pytest
from django.urls import reverse
from order.models import Order, OrderItem
from shop.recommendations import (
    get_category_affinity_recommendations,
    get_frequently_bought_together,
)
from shop.serializers import ProductListSerializer
from shop.tests.factories import CategoryFactory, ProductFactory, UserFactory

pytestmark = pytest.mark.django_db

_seq = count(1)


def make_order(products, status=Order.Status.DELIVERED, user=None):
    """Create an order containing one OrderItem per given product."""
    n = next(_seq)
    order = Order.objects.create(
        user=user,
        status=status,
        first_name="Test",
        last_name="Buyer",
        email=f"buyer{n}@example.com",
        phone="555-0000",
        shipping_address="1 Test St",
        shipping_city="Tehran",
        shipping_state="tehran",
        shipping_zip="1234567890",
        shipping_country="IR",
        subtotal=100_000,
        shipping_cost=0,
        tax=0,
        total=100_000,
    )
    for p in products:
        OrderItem.objects.create(
            order=order,
            product=p,
            product_name=p.name,
            product_slug=p.slug,
            unit_price=100_000,
            quantity=1,
        )
    return order


@pytest.fixture
def target():
    return ProductFactory(name="Target Serum", slug="target-serum")


# ─── 1. Ranking ───────────────────────────────────────────────────────────────
def test_ranked_by_co_occurrence_frequency(target):
    often = ProductFactory(name="Often", slug="often")
    rarely = ProductFactory(name="Rarely", slug="rarely")
    for _ in range(3):
        make_order([target, often])
    make_order([target, rarely])

    result = get_frequently_bought_together(target.id)

    assert [p.id for p in result] == [often.id, rarely.id]


def test_ranking_survives_regardless_of_db_id_order(target):
    # Created in the OPPOSITE order of their ranking, so a plain id__in fetch
    # (ascending id) would return them wrong — guards the re-sort step.
    low_rank = ProductFactory(name="Low", slug="low")
    high_rank = ProductFactory(name="High", slug="high")
    make_order([target, low_rank])
    make_order([target, high_rank])
    make_order([target, high_rank])

    result = get_frequently_bought_together(target.id)

    assert [p.id for p in result] == [high_rank.id, low_rank.id]


def test_repeated_line_in_one_order_counts_once(target):
    # co-occurrence is per ORDER, not per OrderItem row
    a = ProductFactory(name="A", slug="a")
    b = ProductFactory(name="B", slug="b")
    make_order([target, a, a, a])  # three lines of A, one order
    make_order([target, b])
    make_order([target, b])

    result = get_frequently_bought_together(target.id)

    assert [p.id for p in result] == [b.id, a.id]


# ─── 2. Completed orders only ─────────────────────────────────────────────────
@pytest.mark.parametrize("status", [Order.Status.CANCELLED, Order.Status.PENDING])
def test_non_completed_orders_are_ignored(target, status):
    ghost = ProductFactory(name="Ghost", slug="ghost")
    make_order([target, ghost], status=status)

    assert get_frequently_bought_together(target.id) == []


@pytest.mark.parametrize(
    "status",
    [Order.Status.PROCESSING, Order.Status.SHIPPED, Order.Status.DELIVERED],
)
def test_completed_statuses_all_count(target, status):
    other = ProductFactory(name="Other", slug="other")
    make_order([target, other], status=status)

    assert [p.id for p in get_frequently_bought_together(target.id)] == [other.id]


# ─── 3. Target never recommends itself ────────────────────────────────────────
def test_target_never_in_own_results(target):
    other = ProductFactory(name="Other", slug="other")
    make_order([target, other])
    make_order([target, other])

    result = get_frequently_bought_together(target.id)

    assert target.id not in [p.id for p in result]


# ─── 4. Empty cases ───────────────────────────────────────────────────────────
def test_no_purchase_history_returns_empty_list(target):
    assert get_frequently_bought_together(target.id) == []


def test_only_ever_bought_alone_returns_empty_list(target):
    make_order([target])

    assert get_frequently_bought_together(target.id) == []


def test_deleted_products_are_excluded(target):
    gone = ProductFactory(name="Gone", slug="gone")
    kept = ProductFactory(name="Kept", slug="kept")
    make_order([target, gone, kept])
    gone.delete()  # OrderItem.product -> NULL (SET_NULL)

    result = get_frequently_bought_together(target.id)

    assert [p.id for p in result] == [kept.id]


# ─── 5. Limit ─────────────────────────────────────────────────────────────────
def test_default_limit_is_four(target):
    others = [ProductFactory(name=f"P{i}", slug=f"p{i}") for i in range(6)]
    make_order([target, *others])

    assert len(get_frequently_bought_together(target.id)) == 4


def test_custom_limit_is_respected(target):
    others = [ProductFactory(name=f"P{i}", slug=f"p{i}") for i in range(6)]
    make_order([target, *others])

    assert len(get_frequently_bought_together(target.id, limit=2)) == 2
    assert len(get_frequently_bought_together(target.id, limit=6)) == 6


# ─── 6. API endpoint ──────────────────────────────────────────────────────────
def url_for(product):
    return reverse("product-fbt", kwargs={"slug": product.slug})


def test_endpoint_url_shape(target):
    assert url_for(target) == "/api/products/target-serum/frequently-bought-together/"


def test_endpoint_serializes_with_list_serializer_in_ranked_order(api_client, target):
    often = ProductFactory(name="Often", slug="often")
    rarely = ProductFactory(name="Rarely", slug="rarely")
    make_order([target, often])
    make_order([target, often])
    make_order([target, rarely])

    response = api_client.get(url_for(target))

    assert response.status_code == 200
    # unpaginated plain list
    assert isinstance(response.data, list)
    assert [row["id"] for row in response.data] == [often.id, rarely.id]
    # lightweight list serializer shape, not the detail serializer
    assert set(response.data[0].keys()) == set(ProductListSerializer.Meta.fields)
    assert "ingredients" not in response.data[0]


def test_endpoint_ignores_ordering_param(api_client, target):
    # filter backends are disabled: ?ordering= must neither error nor
    # discard the co-occurrence ranking
    often = ProductFactory(name="Often", slug="often")
    rarely = ProductFactory(name="Rarely", slug="rarely")
    make_order([target, often])
    make_order([target, often])
    make_order([target, rarely])

    response = api_client.get(url_for(target), {"ordering": "price"})

    assert response.status_code == 200
    assert [row["id"] for row in response.data] == [often.id, rarely.id]


def test_endpoint_empty_list_when_no_history(api_client, target):
    response = api_client.get(url_for(target))

    assert response.status_code == 200
    assert response.data == []


def test_endpoint_unknown_slug_is_404(api_client):
    response = api_client.get("/api/products/nope/frequently-bought-together/")

    assert response.status_code == 404


def test_endpoint_is_public(api_client, target):
    # AllowAny — no authentication required
    assert api_client.get(url_for(target)).status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Category-affinity recommendations (homepage)
# ═══════════════════════════════════════════════════════════════════════════════
HOME_URL = "/api/products/home-recommendations/"


@pytest.fixture
def cat_a():
    return CategoryFactory(name="Cat A", slug="cat-a")


@pytest.fixture
def cat_b():
    return CategoryFactory(name="Cat B", slug="cat-b")


def make_product(name, category, rating="3.0", reviews=0):
    return ProductFactory(
        name=name,
        slug=name.lower().replace(" ", "-"),
        category=category,
        rating=Decimal(rating),
        reviews_count=reviews,
    )


def ids(products):
    return [p.id for p in products]


# ─── service ──────────────────────────────────────────────────────────────────
def test_affinity_returns_higher_rated_same_category_excluding_viewed(cat_a, cat_b):
    viewed = make_product("Viewed A", cat_a, "4.0")
    best = make_product("Best A", cat_a, "4.9")
    ok = make_product("Ok A", cat_a, "3.0")
    other_cat = make_product("Other B", cat_b, "5.0")

    result = get_category_affinity_recommendations([viewed.id])

    assert ids(result) == [best.id, ok.id]  # ranked by rating
    assert viewed.id not in ids(result)  # already viewed
    assert other_cat.id not in ids(result)  # different category


def test_affinity_uses_reviews_count_as_tiebreaker(cat_a):
    viewed = make_product("Viewed A", cat_a)
    few = make_product("Few Reviews", cat_a, "4.0", reviews=2)
    many = make_product("Many Reviews", cat_a, "4.0", reviews=90)

    assert ids(get_category_affinity_recommendations([viewed.id])) == [many.id, few.id]


def test_affinity_unions_viewed_and_purchased_categories(cat_a, cat_b):
    viewed = make_product("Viewed A", cat_a)
    in_a = make_product("In A", cat_a, "4.0")
    in_b = make_product("In B", cat_b, "4.5")

    result = get_category_affinity_recommendations([viewed.id], [cat_b.id])

    assert set(ids(result)) == {in_a.id, in_b.id}


def test_affinity_purchased_categories_alone_are_enough(cat_b):
    in_b = make_product("In B", cat_b)

    assert ids(get_category_affinity_recommendations([], [cat_b.id])) == [in_b.id]


def test_affinity_no_signal_returns_empty_list(cat_a):
    make_product("Unrelated", cat_a)

    assert get_category_affinity_recommendations([]) == []
    assert get_category_affinity_recommendations([], None) == []
    assert get_category_affinity_recommendations([], []) == []


def test_affinity_unknown_viewed_ids_return_empty_list(cat_a):
    make_product("Unrelated", cat_a)

    assert get_category_affinity_recommendations([987654]) == []


def test_affinity_respects_limit(cat_a):
    viewed = make_product("Viewed A", cat_a)
    for i in range(10):
        make_product(f"A{i}", cat_a)

    assert len(get_category_affinity_recommendations([viewed.id])) == 8
    assert len(get_category_affinity_recommendations([viewed.id], limit=3)) == 3


# ─── endpoint ─────────────────────────────────────────────────────────────────
def test_home_view_authenticated_uses_purchase_history_with_no_viewed_ids(
    api_client, cat_a, cat_b
):
    user = UserFactory()
    bought = make_product("Bought B", cat_b, "4.0")
    sibling = make_product("Sibling B", cat_b, "4.5")
    make_product("Unrelated A", cat_a, "5.0")
    make_order([bought], user=user)
    api_client.force_authenticate(user=user)

    response = api_client.post(HOME_URL, {"viewed_product_ids": []}, format="json")

    assert response.status_code == 200
    assert set(ids_of(response)) == {bought.id, sibling.id}


def test_home_view_authenticated_blends_purchased_and_viewed(api_client, cat_a, cat_b):
    user = UserFactory()
    bought = make_product("Bought B", cat_b, "4.0")
    viewed = make_product("Viewed A", cat_a, "4.0")
    in_a = make_product("In A", cat_a, "3.0")
    make_order([bought], user=user)
    api_client.force_authenticate(user=user)

    response = api_client.post(
        HOME_URL, {"viewed_product_ids": [viewed.id]}, format="json"
    )

    got = set(ids_of(response))
    assert in_a.id in got and bought.id in got
    assert viewed.id not in got


def test_home_view_ignores_uncompleted_and_other_users_orders(api_client, cat_a, cat_b):
    user = UserFactory()
    someone_else = UserFactory()
    pending_product = make_product("Pending B", cat_b)
    other_users_product = make_product("Theirs A", cat_a)
    make_order([pending_product], status=Order.Status.PENDING, user=user)
    make_order([other_users_product], user=someone_else)
    api_client.force_authenticate(user=user)

    response = api_client.post(HOME_URL, {"viewed_product_ids": []}, format="json")

    assert response.status_code == 200
    assert response.data == []


def test_home_view_anonymous_relies_on_client_supplied_ids(api_client, cat_a, cat_b):
    viewed = make_product("Viewed A", cat_a, "4.0")
    best = make_product("Best A", cat_a, "4.9")
    make_product("Other B", cat_b, "5.0")
    # purchase history exists for SOME user; an anonymous request must not see it
    make_order([make_product("Bought B", cat_b)], user=UserFactory())

    response = api_client.post(
        HOME_URL, {"viewed_product_ids": [viewed.id]}, format="json"
    )

    assert response.status_code == 200
    assert ids_of(response) == [best.id]


def test_home_view_anonymous_with_no_ids_returns_empty_list(api_client, cat_a):
    make_product("Something", cat_a)

    response = api_client.post(HOME_URL, {"viewed_product_ids": []}, format="json")

    assert response.status_code == 200
    assert response.data == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"viewed_product_ids": None},
        {"viewed_product_ids": "1,2,3"},
        {"viewed_product_ids": {"a": 1}},
        {"viewed_product_ids": ["abc", None, 1.5, [], {}, True, -4, 0, 10**12]},
    ],
)
def test_home_view_tolerates_malformed_payloads(api_client, cat_a, payload):
    make_product("Something", cat_a)

    response = api_client.post(HOME_URL, payload, format="json")

    assert response.status_code == 200
    assert response.data == []


def test_home_view_accepts_numeric_strings_and_dedupes(api_client, cat_a):
    viewed = make_product("Viewed A", cat_a)
    sibling = make_product("Sibling A", cat_a)

    response = api_client.post(
        HOME_URL, {"viewed_product_ids": [str(viewed.id), viewed.id]}, format="json"
    )

    assert response.status_code == 200
    assert ids_of(response) == [sibling.id]


def test_home_view_only_considers_first_twenty_ids(api_client, cat_a, cat_b):
    viewed_in_b = make_product("Viewed B", cat_b)
    in_b = make_product("In B", cat_b)
    # 20 junk ids first push the real B view past the cap
    junk = list(range(900_000, 900_020))

    response = api_client.post(
        HOME_URL, {"viewed_product_ids": junk + [viewed_in_b.id]}, format="json"
    )

    assert response.status_code == 200
    assert in_b.id not in ids_of(response)


def test_home_view_uses_list_serializer_shape_and_is_post_only(api_client, cat_a):
    viewed = make_product("Viewed A", cat_a)
    make_product("Sibling A", cat_a)

    response = api_client.post(
        HOME_URL, {"viewed_product_ids": [viewed.id]}, format="json"
    )

    assert set(response.data[0].keys()) == set(ProductListSerializer.Meta.fields)
    assert api_client.get(HOME_URL).status_code == 405


def ids_of(response):
    return [row["id"] for row in response.data]
