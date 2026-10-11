"""Customer reporting of published reviews + threshold auto-hide."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from shop.models import ReviewReport
from shop.services import refresh_product_review_stats
from shop.tests.factories import ProductFactory, ReviewFactory, UserFactory

pytestmark = pytest.mark.django_db


def report_url(review_id):
    return reverse("review-report", kwargs={"review_id": review_id})


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


PAYLOAD = {"reason": "spam", "details": "Looks like a bot."}


class TestReportReview:
    def test_authenticated_user_can_report_a_review(self, auth_client, user):
        review = ReviewFactory(is_approved=True)

        res = auth_client.post(report_url(review.id), PAYLOAD, format="json")

        assert res.status_code == status.HTTP_201_CREATED
        report = ReviewReport.objects.get()
        assert (report.review, report.reported_by) == (review, user)
        assert report.reason == "spam"
        assert report.details == "Looks like a bot."
        assert report.resolved is False

    def test_details_are_optional(self, auth_client):
        review = ReviewFactory(is_approved=True)

        res = auth_client.post(
            report_url(review.id), {"reason": "other"}, format="json"
        )

        assert res.status_code == status.HTTP_201_CREATED
        assert ReviewReport.objects.get().details == ""

    def test_duplicate_report_from_same_user_is_a_noop_200(self, auth_client):
        review = ReviewFactory(is_approved=True)
        auth_client.post(report_url(review.id), PAYLOAD, format="json")

        res = auth_client.post(
            report_url(review.id), {"reason": "offensive"}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK
        assert ReviewReport.objects.count() == 1
        assert ReviewReport.objects.get().reason == "spam"  # original untouched

    def test_invalid_reason_is_rejected(self, auth_client):
        review = ReviewFactory(is_approved=True)

        res = auth_client.post(report_url(review.id), {"reason": "nope"}, format="json")

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert ReviewReport.objects.count() == 0

    def test_unknown_review_is_404(self, auth_client):
        res = auth_client.post(report_url(999999), PAYLOAD, format="json")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_unapproved_review_cannot_be_reported(self, auth_client):
        review = ReviewFactory(is_approved=False)

        res = auth_client.post(report_url(review.id), PAYLOAD, format="json")

        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert ReviewReport.objects.count() == 0

    def test_unauthenticated_request_is_rejected_with_401(self, api_client):
        review = ReviewFactory(is_approved=True)

        res = api_client.post(report_url(review.id), PAYLOAD, format="json")

        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert ReviewReport.objects.count() == 0


class TestAutoHideThreshold:
    def _report(self, review, n):
        for _ in range(n):
            client_for(UserFactory()).post(
                report_url(review.id), PAYLOAD, format="json"
            )

    def test_three_unresolved_reports_hide_review_and_recompute_product_stats(self):
        product = ProductFactory()
        keep = ReviewFactory(product=product, rating=5, is_approved=True)
        flagged = ReviewFactory(product=product, rating=1, is_approved=True)
        refresh_product_review_stats(product)
        product.refresh_from_db()
        assert (product.reviews_count, product.rating) == (2, 3.0)

        self._report(flagged, 3)

        flagged.refresh_from_db()
        keep.refresh_from_db()
        assert flagged.is_approved is False
        assert keep.is_approved is True
        product.refresh_from_db()
        assert product.reviews_count == 1
        assert product.rating == 5.0

    def test_two_reports_do_not_hide_review(self):
        review = ReviewFactory(is_approved=True)

        self._report(review, 2)

        review.refresh_from_db()
        assert review.is_approved is True

    def test_resolved_reports_do_not_count_toward_threshold(self):
        review = ReviewFactory(is_approved=True)
        self._report(review, 2)
        review.reports.update(resolved=True)

        self._report(review, 2)  # 2 new unresolved + 2 resolved

        review.refresh_from_db()
        assert review.is_approved is True

    def test_duplicate_reports_from_one_user_never_reach_threshold(self, auth_client):
        review = ReviewFactory(is_approved=True)

        for _ in range(5):
            auth_client.post(report_url(review.id), PAYLOAD, format="json")

        review.refresh_from_db()
        assert review.is_approved is True
        assert review.reports.count() == 1
