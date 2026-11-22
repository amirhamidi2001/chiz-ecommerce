"""
Tests for the NotificationLog admin: the RecentFailuresFilter's queryset
logic (called directly with a constructed request, as for ZeroResultsFilter /
NearExpiryFilter) and the audit-log permissions.
"""

from datetime import timedelta

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.utils import timezone
from notifications.admin import NotificationLogAdmin, RecentFailuresFilter
from notifications.models import NotificationLog

Status = NotificationLog.Status


def make_log(status, age):
    log = NotificationLog.objects.create(
        channel="sms", event="otp_code", recipient="+989121234567", status=status
    )
    # sent_at is auto_now_add, so back-date it with an UPDATE.
    NotificationLog.objects.filter(pk=log.pk).update(sent_at=timezone.now() - age)
    return log


def apply_filter(window=None):
    params = {"recent_failures": window} if window else {}
    request = RequestFactory().get("/", params)
    f = RecentFailuresFilter(
        request, dict(request.GET.lists()), NotificationLog, NotificationLogAdmin
    )
    return f.queryset(request, NotificationLog.objects.all())


@pytest.fixture
def logs(db):
    return {
        "fail_30m": make_log(Status.FAILED, timedelta(minutes=30)),
        "fail_5h": make_log(Status.FAILED, timedelta(hours=5)),
        "fail_3d": make_log(Status.FAILED, timedelta(days=3)),
        "fail_30d": make_log(Status.FAILED, timedelta(days=30)),
        "sent_now": make_log(Status.SENT, timedelta(minutes=1)),
        "skipped_now": make_log(Status.SKIPPED, timedelta(minutes=1)),
    }


@pytest.mark.django_db
class TestRecentFailuresFilter:
    def test_no_value_returns_everything(self, logs):
        assert apply_filter().count() == 6

    def test_one_hour_window(self, logs):
        assert set(apply_filter("1h")) == {logs["fail_30m"]}

    def test_24_hour_window(self, logs):
        assert set(apply_filter("24h")) == {logs["fail_30m"], logs["fail_5h"]}

    def test_seven_day_window(self, logs):
        assert set(apply_filter("7d")) == {
            logs["fail_30m"],
            logs["fail_5h"],
            logs["fail_3d"],
        }

    def test_only_failed_rows_match_never_sent_or_skipped(self, logs):
        for window in ("1h", "24h", "7d"):
            assert not set(apply_filter(window)) & {
                logs["sent_now"],
                logs["skipped_now"],
            }

    def test_unknown_value_is_ignored(self, logs):
        assert apply_filter("bogus").count() == 6


class TestNotificationLogAdminConfig:
    def setup_method(self):
        self.model_admin = NotificationLogAdmin(NotificationLog, admin.site)
        self.request = RequestFactory().get("/")

    def test_is_registered(self):
        assert NotificationLog in admin.site._registry

    def test_is_read_only_audit_log(self):
        assert self.model_admin.has_add_permission(self.request) is False
        assert self.model_admin.has_change_permission(self.request) is False
        assert self.model_admin.has_delete_permission(self.request) is False

    def test_every_field_is_readonly(self):
        assert set(self.model_admin.readonly_fields) == {
            f.name for f in NotificationLog._meta.fields
        }

    def test_recent_failures_filter_is_offered(self):
        assert RecentFailuresFilter in self.model_admin.list_filter
