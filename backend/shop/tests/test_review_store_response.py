"""Public ReviewSerializer exposes the store's reply (read-only)."""

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory
from shop.serializers import ReviewSerializer
from shop.tests.factories import ProductFactory, ReviewFactory

pytestmark = pytest.mark.django_db


def _context():
    return {"request": APIRequestFactory().get("/")}


class TestReviewSerializerStoreResponse:
    def test_includes_store_response_and_timestamp_when_present(self):
        responded_at = timezone.now()
        review = ReviewFactory(
            is_approved=True,
            store_response="Thank you for shopping with us!",
            store_response_at=responded_at,
        )

        data = ReviewSerializer(review, context=_context()).data

        assert data["store_response"] == "Thank you for shopping with us!"
        assert data["store_response_at"] is not None
        assert data["store_response_at"].startswith(responded_at.strftime("%Y-%m-%d"))

    def test_blank_and_null_when_absent(self):
        review = ReviewFactory(is_approved=True)

        data = ReviewSerializer(review, context=_context()).data

        assert data["store_response"] == ""
        assert data["store_response_at"] is None

    def test_fields_are_read_only_on_the_public_serializer(self):
        fields = ReviewSerializer().fields
        assert fields["store_response"].read_only is True
        assert fields["store_response_at"].read_only is True

    def test_product_detail_shows_reply_on_approved_review(self, api_client):
        product = ProductFactory()
        ReviewFactory(
            product=product,
            is_approved=True,
            store_response="Fixed in our latest batch.",
            store_response_at=timezone.now(),
        )

        res = api_client.get(reverse("product-detail", kwargs={"slug": product.slug}))

        assert res.status_code == status.HTTP_200_OK
        assert res.data["reviews"][0]["store_response"] == "Fixed in our latest batch."
