"""
shop/tests/test_tasks.py
────────────────────────
Tests for shop/tasks.py's deactivate_expired_variants (Task 3.3.1.3).

No existing Celery task test convention exists anywhere in this
project yet — this is the first shop-level @shared_task. Calls the
task directly as a plain Python function (per Celery's standard
testing pattern: a @shared_task-decorated function can be called
without .delay()/.apply_async(), executing synchronously with no
broker needed) rather than requiring a running worker.
"""

import datetime

import pytest
from django.utils import timezone

from shop.tasks import deactivate_expired_variants
from shop.tests.factories import ProductVariantFactory


@pytest.mark.django_db
class TestDeactivateExpiredVariants:

    def test_expired_active_variant_is_deactivated(self):
        yesterday = timezone.now().date() - datetime.timedelta(days=1)
        variant = ProductVariantFactory(expiration_date=yesterday, is_active=True)

        deactivate_expired_variants()

        variant.refresh_from_db()
        assert variant.is_active is False

    def test_future_expiration_variant_is_untouched(self):
        tomorrow = timezone.now().date() + datetime.timedelta(days=1)
        variant = ProductVariantFactory(expiration_date=tomorrow, is_active=True)

        deactivate_expired_variants()

        variant.refresh_from_db()
        assert variant.is_active is True

    def test_null_expiration_date_variant_is_never_touched(self):
        variant = ProductVariantFactory(expiration_date=None, is_active=True)

        deactivate_expired_variants()

        variant.refresh_from_db()
        assert variant.is_active is True

    def test_already_inactive_variant_is_unaffected(self):
        yesterday = timezone.now().date() - datetime.timedelta(days=1)
        variant = ProductVariantFactory(expiration_date=yesterday, is_active=False)

        # Should not raise, and should not touch this row (it's already
        # excluded by the is_active=True filter clause).
        result = deactivate_expired_variants()

        variant.refresh_from_db()
        assert variant.is_active is False
        assert "Deactivated 0 expired variant(s)." == result

    def test_returns_correct_count_and_only_deactivates_matching_rows(self):
        yesterday = timezone.now().date() - datetime.timedelta(days=1)
        tomorrow = timezone.now().date() + datetime.timedelta(days=1)

        expired_active = ProductVariantFactory(
            expiration_date=yesterday, is_active=True
        )
        future = ProductVariantFactory(expiration_date=tomorrow, is_active=True)
        no_expiry = ProductVariantFactory(expiration_date=None, is_active=True)
        already_inactive = ProductVariantFactory(
            expiration_date=yesterday, is_active=False
        )

        result = deactivate_expired_variants()

        assert result == "Deactivated 1 expired variant(s)."

        expired_active.refresh_from_db()
        future.refresh_from_db()
        no_expiry.refresh_from_db()
        already_inactive.refresh_from_db()

        assert expired_active.is_active is False
        assert future.is_active is True
        assert no_expiry.is_active is True
        assert already_inactive.is_active is False
