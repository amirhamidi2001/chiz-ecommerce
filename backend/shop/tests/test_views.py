import pytest
from django.urls import reverse
from order.models import Order, OrderItem
from rest_framework import status
from rest_framework.test import APIClient
from shop.models import Review
from shop.tests.factories import (
    BrandFactory,
    CategoryFactory,
    ColorFactory,
    ProductColorFactory,
    ProductFactory,
    ProductImageFactory,
    ReviewFactory,
    UserFactory,
)


# ─── helpers ────────────────────────────────────────────────────────────────
def url(name, **kwargs):
    return reverse(name, kwargs=kwargs)


def make_order_with_item(
    user, product, order_status=Order.Status.DELIVERED, quantity=1
):
    """
    Create a minimal, valid Order + OrderItem for *user* containing
    *product*, at the given order status. Used to exercise
    ProductReviewCreateView._is_verified_purchase() without going through
    the full checkout flow (that's order app's own test surface).
    """
    order = Order.objects.create(
        user=user,
        status=order_status,
        first_name="Test",
        last_name="Buyer",
        email=user.email,
        phone="555-0100",
        shipping_address="1 Test St",
        shipping_city="Testville",
        shipping_state="TS",
        shipping_zip="00000",
        shipping_country="US",
        subtotal=product.price * quantity,
        tax=0,
        total=product.price * quantity,
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        product_slug=product.slug,
        unit_price=product.price,
        quantity=quantity,
    )
    return order


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/categories/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestCategoryListView:

    def test_returns_200(self, api_client):
        res = api_client.get(url("category-list"))
        assert res.status_code == status.HTTP_200_OK

    def test_returns_only_root_categories(self, api_client):
        root = CategoryFactory(name="Root", slug="root")
        child = CategoryFactory(name="Child", slug="child", parent=root)
        res = api_client.get(url("category-list"))
        results = res.data["results"]
        names = [c["name"] for c in results]
        assert "Root" in names
        assert "Child" not in names

    def test_children_are_nested(self, api_client):
        root = CategoryFactory(name="Root", slug="root")
        child = CategoryFactory(name="Child", slug="child", parent=root)
        res = api_client.get(url("category-list"))
        root_data = next(c for c in res.data["results"] if c["name"] == "Root")
        child_names = [c["name"] for c in root_data["children"]]
        assert "Child" in child_names

    def test_empty_db_returns_empty_list(self, api_client):
        res = api_client.get(url("category-list"))
        assert res.data["count"] == 0
        assert res.data["results"] == []

    def test_no_authentication_required(self, api_client):
        """Public endpoint — no auth header needed."""
        res = api_client.get(url("category-list"))
        assert res.status_code != status.HTTP_401_UNAUTHORIZED


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/brands/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestBrandListView:

    def test_returns_200(self, api_client):
        res = api_client.get(url("brand-list"))
        assert res.status_code == status.HTTP_200_OK

    def test_returns_all_brands(self, api_client):
        BrandFactory.create_batch(5)
        res = api_client.get(url("brand-list"))
        assert len(res.data) == 5

    def test_search_by_name(self, api_client):
        BrandFactory(name="Nike")
        BrandFactory(name="Adidas")
        BrandFactory(name="Puma")
        res = api_client.get(url("brand-list"), {"search": "nik"})
        assert len(res.data) == 1
        assert res.data[0]["name"] == "Nike"

    def test_not_paginated(self, api_client):
        """Brand list returns a plain list, not a paginated envelope."""
        BrandFactory.create_batch(20)
        res = api_client.get(url("brand-list"))
        assert isinstance(res.data, list)
        assert len(res.data) == 20


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/colors/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestColorListView:

    def test_returns_200(self, api_client):
        res = api_client.get(url("color-list"))
        assert res.status_code == status.HTTP_200_OK

    def test_returns_all_colors(self, api_client):
        ColorFactory.create_batch(6)
        res = api_client.get(url("color-list"))
        assert len(res.data) == 6

    def test_not_paginated(self, api_client):
        ColorFactory.create_batch(15)
        res = api_client.get(url("color-list"))
        assert isinstance(res.data, list)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/products/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductListView:

    # ── Pagination ─────────────────────────────────────────────────────────
    def test_paginated_response_shape(self, api_client, products_bulk):
        res = api_client.get(url("product-list"))
        assert res.status_code == status.HTTP_200_OK
        for key in (
            "count",
            "total_pages",
            "next",
            "previous",
            "current_page",
            "results",
        ):
            assert key in res.data, f"Missing pagination key: {key}"

    def test_default_page_size_is_12(self, api_client):
        ProductFactory.create_batch(20)
        res = api_client.get(url("product-list"))
        assert len(res.data["results"]) == 12

    def test_custom_page_size(self, api_client):
        ProductFactory.create_batch(10)
        res = api_client.get(url("product-list"), {"page_size": 5})
        assert len(res.data["results"]) == 5

    def test_page_2_returns_correct_items(self, api_client):
        ProductFactory.create_batch(15)
        res = api_client.get(url("product-list"), {"page": 2, "page_size": 10})
        assert len(res.data["results"]) == 5

    def test_total_pages_calculated_correctly(self, api_client):
        ProductFactory.create_batch(25)
        res = api_client.get(url("product-list"), {"page_size": 10})
        assert res.data["total_pages"] == 3

    # ── Search ──────────────────────────────────────────────────────────────
    def test_search_by_product_name(self, api_client):
        ProductFactory(name="Wireless Headphones")
        ProductFactory(name="Running Shoes")
        ProductFactory(name="Wireless Speaker")
        res = api_client.get(url("product-list"), {"search": "wireless"})
        names = [p["name"] for p in res.data["results"]]
        assert all("wireless" in n.lower() for n in names)
        assert len(names) == 2

    def test_search_no_match_returns_empty(self, api_client):
        ProductFactory.create_batch(5)
        res = api_client.get(url("product-list"), {"search": "xyznonexistent123"})
        assert res.data["count"] == 0

    # ── Ordering ────────────────────────────────────────────────────────────
    def test_order_by_price_ascending(self, api_client):
        ProductFactory(name="Expensive", price=200)
        ProductFactory(name="Cheap", price=10)
        ProductFactory(name="Mid", price=50)
        res = api_client.get(url("product-list"), {"ordering": "price"})
        prices = [float(p["price"]) for p in res.data["results"]]
        assert prices == sorted(prices)

    def test_order_by_price_descending(self, api_client):
        ProductFactory(name="Expensive", price=200)
        ProductFactory(name="Cheap", price=10)
        res = api_client.get(url("product-list"), {"ordering": "-price"})
        prices = [float(p["price"]) for p in res.data["results"]]
        assert prices == sorted(prices, reverse=True)

    def test_order_by_rating(self, api_client):
        ProductFactory(price=10, rating=4.5)
        ProductFactory(price=20, rating=3.0)
        ProductFactory(price=30, rating=5.0)
        res = api_client.get(url("product-list"), {"ordering": "-rating"})
        ratings = [float(p["rating"]) for p in res.data["results"]]
        assert ratings == sorted(ratings, reverse=True)

    # ── Filtering ────────────────────────────────────────────────────────────
    def test_filter_by_category_slug(self, api_client):
        cat_a = CategoryFactory(slug="electronics")
        cat_b = CategoryFactory(slug="clothing")
        ProductFactory.create_batch(3, category=cat_a)
        ProductFactory.create_batch(2, category=cat_b)
        res = api_client.get(url("product-list"), {"category": "electronics"})
        assert res.data["count"] == 3

    def test_filter_is_new(self, api_client, new_products):
        ProductFactory.create_batch(3, is_new=False)
        res = api_client.get(url("product-list"), {"is_new": "true"})
        assert res.data["count"] == 4
        assert all(p["is_new"] for p in res.data["results"])

    def test_filter_is_sale(self, api_client, sale_products):
        ProductFactory.create_batch(3, is_sale=False)
        res = api_client.get(url("product-list"), {"is_sale": "true"})
        assert res.data["count"] == 4

    def test_filter_min_price(self, api_client):
        ProductFactory(price=10)
        ProductFactory(price=100)
        ProductFactory(price=500)
        res = api_client.get(url("product-list"), {"min_price": 99})
        assert res.data["count"] == 2

    def test_filter_max_price(self, api_client):
        ProductFactory(price=10)
        ProductFactory(price=100)
        ProductFactory(price=500)
        res = api_client.get(url("product-list"), {"max_price": 101})
        assert res.data["count"] == 2

    def test_filter_brand_slug(self, api_client):
        brand = BrandFactory(slug="nike")
        ProductFactory.create_batch(3, brand=brand)
        ProductFactory.create_batch(2)
        res = api_client.get(url("product-list"), {"brand": "nike"})
        assert res.data["count"] == 3

    def test_filter_color_by_name(self, api_client):
        red = ColorFactory(name="Red", hex_code="#ff0000")
        p_red = ProductFactory()
        ProductColorFactory(product=p_red, color=red)
        ProductFactory.create_batch(3)  # no color
        res = api_client.get(url("product-list"), {"color": "Red"})
        ids = [p["id"] for p in res.data["results"]]
        assert p_red.id in ids

    def test_no_auth_required(self, api_client):
        res = api_client.get(url("product-list"))
        assert res.status_code == status.HTTP_200_OK

    # ── Response field validation ────────────────────────────────────────────
    def test_result_items_have_expected_fields(self, api_client):
        ProductFactory()
        res = api_client.get(url("product-list"))
        item = res.data["results"][0]
        for field in (
            "id",
            "name",
            "slug",
            "price",
            "rating",
            "is_new",
            "is_sale",
            "category",
            "brand",
        ):
            assert field in item, f"Missing field in product list item: {field}"

    def test_result_items_do_not_contain_reviews(self, api_client):
        """List serializer should not include the full review list."""
        product = ProductFactory()
        ReviewFactory.create_batch(3, product=product)
        res = api_client.get(url("product-list"))
        item = res.data["results"][0]
        assert "reviews" not in item


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/products/<slug>/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestProductDetailView:

    def test_returns_200_for_valid_slug(self, api_client, product):
        res = api_client.get(url("product-detail", slug=product.slug))
        assert res.status_code == status.HTTP_200_OK

    def test_returns_404_for_invalid_slug(self, api_client):
        res = api_client.get(url("product-detail", slug="does-not-exist"))
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_response_contains_nested_relations(
        self, api_client, product_with_relations
    ):
        res = api_client.get(url("product-detail", slug=product_with_relations.slug))
        for key in ("images", "colors", "reviews", "category", "brand"):
            assert key in res.data, f"Missing key: {key}"

    def test_reviews_are_populated(self, api_client, product):
        ReviewFactory.create_batch(3, product=product)
        res = api_client.get(url("product-detail", slug=product.slug))
        assert len(res.data["reviews"]) == 3

    def test_colors_are_populated(self, api_client, product, color):
        ProductColorFactory(product=product, color=color)
        res = api_client.get(url("product-detail", slug=product.slug))
        assert len(res.data["colors"]) == 1
        assert res.data["colors"][0]["color"]["name"] == color.name

    def test_description_in_detail_not_in_list(self, api_client, product):
        res = api_client.get(url("product-detail", slug=product.slug))
        assert "description" in res.data

    def test_no_auth_required(self, api_client, product):
        res = api_client.get(url("product-detail", slug=product.slug))
        assert res.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/products/<slug>/related/
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestRelatedProductsView:

    def test_returns_products_from_same_category(self, api_client, category, brand):
        product = ProductFactory(category=category, brand=brand, slug="main-product")
        related1 = ProductFactory(category=category, brand=brand)
        related2 = ProductFactory(category=category, brand=brand)
        other = ProductFactory()  # different category

        res = api_client.get(url("product-related", slug=product.slug))
        ids = [p["id"] for p in res.data]
        assert related1.id in ids
        assert related2.id in ids
        assert other.id not in ids

    def test_excludes_current_product(self, api_client, category, brand):
        product = ProductFactory(category=category, brand=brand)
        ProductFactory.create_batch(3, category=category, brand=brand)
        res = api_client.get(url("product-related", slug=product.slug))
        ids = [p["id"] for p in res.data]
        assert product.id not in ids

    def test_max_8_related_products(self, api_client, category, brand):
        product = ProductFactory(category=category, brand=brand)
        ProductFactory.create_batch(12, category=category, brand=brand)
        res = api_client.get(url("product-related", slug=product.slug))
        assert len(res.data) <= 8

    def test_invalid_slug_returns_empty_list(self, api_client):
        res = api_client.get(url("product-related", slug="ghost-product"))
        assert res.status_code == status.HTTP_200_OK
        assert res.data == []

    def test_not_paginated(self, api_client, category, brand):
        product = ProductFactory(category=category, brand=brand)
        ProductFactory.create_batch(5, category=category, brand=brand)
        res = api_client.get(url("product-related", slug=product.slug))
        assert isinstance(res.data, list)


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/products/<slug>/reviews/   —   Task 1.3.1.3 security fix
# ═══════════════════════════════════════════════════════════════════════════════
#
# Reviews used to be postable by anyone (AllowAny) under any free-text
# `name`. They now require authentication, and the review's `user` +
# display `name` are always derived server-side from the authenticated
# account — never trusted from client input.
@pytest.mark.django_db
class TestProductReviewCreateView:

    VALID_PAYLOAD = {
        "rating": 5,
        "headline": "Great product",
        "comment": "Exactly what I needed, works perfectly.",
    }

    def test_unauthenticated_post_returns_401(self, api_client, product):
        res = api_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert product.reviews.count() == 0

    def test_authenticated_post_succeeds_and_sets_user(
        self, auth_client, user, product
    ):
        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED

        review = product.reviews.get()
        assert review.user_id == user.id
        assert review.rating == 5
        assert review.comment == self.VALID_PAYLOAD["comment"]

    def test_authenticated_post_ignores_client_submitted_name(
        self, auth_client, user, product
    ):
        """
        Security regression guard (same "don't trust client input" pattern
        as Task 1.2.1.2's discount fix): even if a client forges a
        `name` value in the payload — e.g. impersonating someone else, or
        injecting something malicious — the server must completely ignore
        it. The stored `name` always comes from the authenticated user's
        own profile, never from the request body.
        """
        user.profile.first_name = "Real"
        user.profile.last_name = "Reviewer"
        user.profile.save()

        forged_payload = {**self.VALID_PAYLOAD, "name": "Totally Fake Person"}
        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            forged_payload,
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED

        review = product.reviews.get()
        assert review.user_id == user.id
        assert review.name == "Real Reviewer"
        assert review.name != "Totally Fake Person"
        assert res.data["name"] == "Real Reviewer"

    def test_review_name_uses_profile_full_name(self, auth_client, user, product):
        user.profile.first_name = "Ada"
        user.profile.last_name = "Lovelace"
        user.profile.save()

        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED
        assert product.reviews.get().name == "Ada Lovelace"

    def test_review_name_falls_back_to_email_when_profile_has_no_name(
        self, auth_client, user, product
    ):
        # UserFactory-created users have a blank profile (first/last name
        # both "") until they fill it in — must not surface the internal
        # "new user" placeholder as a public review author name.
        assert user.profile.first_name == ""
        assert user.profile.last_name == ""

        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED

        review = product.reviews.get()
        assert review.name == user.email
        assert review.name != "new user"

    def test_response_includes_user_id_not_full_user_object(
        self, auth_client, user, product
    ):
        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.data["user_id"] == user.id
        assert "user" not in res.data
        assert "email" not in res.data

    def test_product_stats_still_update_after_authenticated_review(
        self, auth_client, product
    ):
        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED
        product.refresh_from_db()
        assert product.reviews_count == 1
        assert product.rating == 5.0

    # ── one review per user per product (Task 1.3.1.4) ──────────────────────

    def test_first_review_for_product_succeeds(self, auth_client, product):
        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED
        assert product.reviews.count() == 1

    def test_second_review_same_product_same_user_returns_400(
        self, auth_client, user, product
    ):
        first = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert first.status_code == status.HTTP_201_CREATED

        second = auth_client.post(
            url("product-review-create", slug=product.slug),
            {**self.VALID_PAYLOAD, "comment": "A different comment entirely."},
            format="json",
        )

        assert second.status_code == status.HTTP_400_BAD_REQUEST
        # DRF wraps validate()-level dict errors as lists of ErrorDetail
        assert (
            str(second.data["detail"][0]) == "You have already reviewed this product."
        )
        # Still exactly one review — the duplicate attempt created nothing.
        assert product.reviews.filter(user=user).count() == 1
        assert Review.objects.filter(product=product, user=user).count() == 1

    def test_same_user_can_review_a_different_product(self, auth_client, user):
        product_a = ProductFactory()
        product_b = ProductFactory()

        res_a = auth_client.post(
            url("product-review-create", slug=product_a.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        res_b = auth_client.post(
            url("product-review-create", slug=product_b.slug),
            self.VALID_PAYLOAD,
            format="json",
        )

        assert res_a.status_code == status.HTTP_201_CREATED
        assert res_b.status_code == status.HTTP_201_CREATED
        assert Review.objects.filter(user=user).count() == 2

    def test_two_different_users_can_review_the_same_product(self, product):
        user_a = UserFactory()
        user_b = UserFactory()
        client_a = APIClient()
        client_a.force_authenticate(user=user_a)
        client_b = APIClient()
        client_b.force_authenticate(user=user_b)

        res_a = client_a.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        res_b = client_b.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )

        assert res_a.status_code == status.HTTP_201_CREATED
        assert res_b.status_code == status.HTTP_201_CREATED
        assert product.reviews.count() == 2
        assert set(product.reviews.values_list("user_id", flat=True)) == {
            user_a.id,
            user_b.id,
        }

    def test_duplicate_review_raises_clean_400_not_500_integrity_error(
        self, auth_client, user, product
    ):
        """
        The application-layer check in ReviewCreateSerializer.validate()
        must catch the duplicate before Django ever attempts the INSERT,
        so a race-free duplicate attempt gets a clean 400 rather than an
        unhandled IntegrityError bubbling up as a 500.
        """
        ReviewFactory(product=product, user=user)

        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "detail" in res.data

    # ── is_verified_purchase computation (Task 1.3.1.5) ──────────────────────

    def test_delivered_order_for_this_product_marks_review_verified(
        self, auth_client, user, product
    ):
        make_order_with_item(user, product, order_status=Order.Status.DELIVERED)

        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED

        review = product.reviews.get()
        assert review.is_verified_purchase is True
        assert res.data["is_verified_purchase"] is True

    @pytest.mark.parametrize(
        "not_yet_delivered_status",
        [Order.Status.PENDING, Order.Status.PROCESSING, Order.Status.SHIPPED],
    )
    def test_undelivered_order_does_not_mark_review_verified(
        self, auth_client, user, product, not_yet_delivered_status
    ):
        make_order_with_item(user, product, order_status=not_yet_delivered_status)

        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED

        review = product.reviews.get()
        assert review.is_verified_purchase is False

    def test_no_order_history_leaves_review_unverified(self, auth_client, product):
        # user (from the `user` fixture, via auth_client) has no orders at all
        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED
        review = product.reviews.get()
        assert review.is_verified_purchase is False

    def test_delivered_order_for_a_different_product_does_not_verify_this_review(
        self, auth_client, user, product
    ):
        """
        Proves the check is scoped to THIS product, not "has any
        delivered order ever" — a delivered purchase of some other item
        must not verify a review left on an unrelated product.
        """
        other_product = ProductFactory()
        make_order_with_item(user, other_product, order_status=Order.Status.DELIVERED)

        res = auth_client.post(
            url("product-review-create", slug=product.slug),
            self.VALID_PAYLOAD,
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED

        review = product.reviews.get()
        assert review.is_verified_purchase is False
