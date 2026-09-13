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

from shop.tasks import deactivate_expired_variants, notify_stock_alert_subscribers
from shop.tests.factories import ProductVariantFactory, UserFactory


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


@pytest.mark.django_db
class TestNotifyStockAlertSubscribers:
    def test_marks_only_unnotified_subscriptions_and_returns_correct_count(self):
        from shop.models import StockAlertSubscription

        variant = ProductVariantFactory(stock=10)
        user_a = UserFactory()
        user_b = UserFactory()
        user_c = UserFactory()

        already_notified_time = timezone.now() - datetime.timedelta(days=1)
        sub_a = StockAlertSubscription.objects.create(user=user_a, variant=variant)
        sub_b = StockAlertSubscription.objects.create(user=user_b, variant=variant)
        sub_c = StockAlertSubscription.objects.create(
            user=user_c, variant=variant, notified_at=already_notified_time
        )

        result = notify_stock_alert_subscribers(variant.id)

        sub_a.refresh_from_db()
        sub_b.refresh_from_db()
        sub_c.refresh_from_db()

        assert sub_a.notified_at is not None
        assert sub_b.notified_at is not None
        # Already-notified subscription's original timestamp is left
        # untouched, not overwritten with a new one.
        assert sub_c.notified_at == already_notified_time

        assert result == f"Notified 2 subscriber(s) for variant {variant.id}."

    def test_nonexistent_variant_returns_gracefully(self):
        result = notify_stock_alert_subscribers(999999)
        assert result == "Variant no longer exists."
