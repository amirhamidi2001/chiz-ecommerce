"""
Review moderation (Epic 1 follow-up): `Review.is_approved`, auto-approval for
verified purchases, approved-only public output, and approved-only rating
aggregates.
"""

from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, override_settings
from django.urls import reverse
from order.models import Order, OrderItem
from rest_framework import status
from shop.admin import ReviewAdmin
from shop.models import Review
from shop.services import refresh_product_review_stats
from shop.tests.factories import ProductFactory, ReviewFactory, UserFactory

pytestmark = pytest.mark.django_db


def _order_for(user, product, order_status=Order.Status.DELIVERED, n=[0]):
    n[0] += 1
    order = Order.objects.create(
        user=user,
        order_number=f"ORD-MOD-{n[0]:04d}",
        status=order_status,
        first_name="T",
        last_name="U",
        email=user.email or "t@example.com",
        phone="5550001234",
        shipping_address="1 Test St",
        shipping_city="Testville",
        shipping_state="CA",
        shipping_zip="90001",
        shipping_country="US",
        payment_method="card",
        subtotal=Decimal("10.00"),
        shipping_cost=Decimal("0.00"),
        tax=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=Decimal("10.00"),
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        product_slug=product.slug,
        unit_price=Decimal("10.00"),
        quantity=1,
    )
    return order


def _post_review(client, product, rating=5):
    return client.post(
        reverse("product-review-create", kwargs={"slug": product.slug}),
        {"rating": rating, "headline": "Nice", "comment": "Works well."},
        format="json",
    )


class TestReviewDefault:
    def test_is_approved_defaults_to_false(self):
        review = Review.objects.create(
            product=ProductFactory(), name="A", rating=4, comment="ok"
        )
        assert review.is_approved is False


class TestAutoApprovalAtCreation:
    def test_verified_purchase_is_auto_approved_by_default(self, auth_client, user):
        product = ProductFactory()
        _order_for(user, product)

        res = _post_review(auth_client, product)

        assert res.status_code == status.HTTP_201_CREATED
        review = Review.objects.get(product=product, user=user)
        assert review.is_verified_purchase is True
        assert review.is_approved is True

    @pytest.mark.parametrize("auto_approve", [True, False])
    def test_non_verified_purchase_is_pending_regardless_of_setting(
        self, auth_client, user, settings, auto_approve
    ):
        settings.REVIEW_AUTO_APPROVE_VERIFIED_PURCHASES = auto_approve
        product = ProductFactory()

        res = _post_review(auth_client, product)

        assert res.status_code == status.HTTP_201_CREATED
        review = Review.objects.get(product=product, user=user)
        assert review.is_verified_purchase is False
        assert review.is_approved is False

    @override_settings(REVIEW_AUTO_APPROVE_VERIFIED_PURCHASES=False)
    def test_verified_purchase_is_pending_when_auto_approve_disabled(
        self, auth_client, user
    ):
        product = ProductFactory()
        _order_for(user, product)

        _post_review(auth_client, product)

        review = Review.objects.get(product=product, user=user)
        assert review.is_verified_purchase is True
        assert review.is_approved is False

    def test_undelivered_order_does_not_count_as_verified(self, auth_client, user):
        product = ProductFactory()
        _order_for(user, product, order_status=Order.Status.PENDING)

        _post_review(auth_client, product)

        review = Review.objects.get(product=product, user=user)
        assert review.is_approved is False


class TestRatingAggregatesOnlyCountApproved:
    def test_refresh_ignores_pending_reviews(self):
        product = ProductFactory()
        ReviewFactory(product=product, rating=5, is_approved=True)
        ReviewFactory(product=product, rating=3, is_approved=True)
        ReviewFactory(product=product, rating=1, is_approved=False)
        ReviewFactory(product=product, rating=1, is_approved=False)

        refresh_product_review_stats(product)

        product.refresh_from_db()
        assert product.reviews_count == 2
        assert product.rating == 4.0  # (5 + 3) / 2, not (5+3+1+1) / 4

    def test_refresh_resets_to_zero_when_nothing_approved(self):
        product = ProductFactory(rating=4.5, reviews_count=7)
        ReviewFactory(product=product, rating=2, is_approved=False)

        refresh_product_review_stats(product)

        product.refresh_from_db()
        assert product.reviews_count == 0
        assert product.rating == 0

    def test_posting_a_pending_review_does_not_change_public_stats(self, auth_client):
        product = ProductFactory()
        ReviewFactory(product=product, rating=4, is_approved=True)
        refresh_product_review_stats(product)

        _post_review(auth_client, product, rating=1)  # unverified -> pending

        product.refresh_from_db()
        assert product.reviews_count == 1
        assert product.rating == 4.0

    def test_posting_an_auto_approved_review_updates_public_stats(
        self, auth_client, user
    ):
        product = ProductFactory()
        ReviewFactory(product=product, rating=3, is_approved=True)
        refresh_product_review_stats(product)
        _order_for(user, product)

        _post_review(auth_client, product, rating=5)

        product.refresh_from_db()
        assert product.reviews_count == 2
        assert product.rating == 4.0


class TestPublicReviewList:
    def test_product_detail_never_includes_unapproved_reviews(self, api_client):
        product = ProductFactory()
        approved = ReviewFactory(product=product, is_approved=True)
        pending = ReviewFactory(product=product, is_approved=False)

        res = api_client.get(reverse("product-detail", kwargs={"slug": product.slug}))

        assert res.status_code == status.HTTP_200_OK
        ids = [r["id"] for r in res.data["reviews"]]
        assert ids == [approved.id]
        assert pending.id not in ids


class TestReviewAdminActions:
    def _admin(self):
        return ReviewAdmin(Review, AdminSite())

    def _request(self):
        return RequestFactory().post("/admin/shop/review/")

    def test_approve_action_refreshes_product_stats(self, monkeypatch):
        product = ProductFactory()
        ReviewFactory(product=product, rating=4, is_approved=True)
        pending = ReviewFactory(product=product, rating=2, is_approved=False)
        refresh_product_review_stats(product)
        admin_obj = self._admin()
        monkeypatch.setattr(admin_obj, "message_user", lambda *a, **k: None)

        admin_obj.approve_reviews(self._request(), Review.objects.filter(pk=pending.pk))

        product.refresh_from_db()
        assert product.reviews_count == 2
        assert product.rating == 3.0

    def test_unapprove_action_refreshes_product_stats(self, monkeypatch):
        product = ProductFactory()
        ReviewFactory(product=product, rating=4, is_approved=True)
        bad = ReviewFactory(product=product, rating=1, is_approved=True)
        refresh_product_review_stats(product)
        admin_obj = self._admin()
        monkeypatch.setattr(admin_obj, "message_user", lambda *a, **k: None)

        admin_obj.unapprove_reviews(self._request(), Review.objects.filter(pk=bad.pk))

        product.refresh_from_db()
        assert product.reviews_count == 1
        assert product.rating == 4.0
