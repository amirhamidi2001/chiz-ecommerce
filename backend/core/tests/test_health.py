"""
core/tests/test_health.py
────────────────────────────
Tests for the /api/health/ endpoint (core/views.py, core/health.py,
core/tasks.py).

No CELERY_TASK_ALWAYS_EAGER setting exists anywhere in this project,
and there is no separate test-settings module — pytest.ini runs tests
directly against core.settings.development, the SAME settings used by
the real dev Docker stack (docker-compose.dev.yml). Setting
CELERY_TASK_ALWAYS_EAGER = True globally in development.py would
silently make Celery synchronous in real local dev too, which would
defeat the actual point of this health check (and of Task 22.1.1.3's
manual Docker-based verification) — checks.celery would trivially
report True even with the celery_worker container stopped, since
eager mode never touches the broker at all.

So eager mode is scoped to just these tests via Django's
override_settings, not added to development.py.
"""

from unittest.mock import patch

import pytest
from celery.exceptions import TimeoutError as CeleryTimeoutError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


def url():
    return reverse("health-check")


@pytest.mark.django_db
class TestHealthCheckHealthy:
    def test_returns_200_with_both_checks_true(self, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = True
        client = APIClient()
        res = client.get(url())
        assert res.status_code == status.HTTP_200_OK
        assert res.data["status"] == "healthy"
        assert res.data["checks"] == {"database": True, "celery": True}


@pytest.mark.django_db
class TestHealthCheckDatabaseFailureIsIndependent:
    def test_database_failure_reported_without_masking_celery_status(self, settings):
        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = True
        client = APIClient()
        with patch("django.db.connection.cursor", side_effect=Exception("db is down")):
            res = client.get(url())

        assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert res.data["status"] == "unhealthy"
        assert res.data["checks"]["database"] is False
        # Celery was NOT force-failed here — it must still be independently
        # evaluated and correctly reported as healthy, proving one check's
        # failure doesn't mask or short-circuit the other's real status.
        assert res.data["checks"]["celery"] is True


@pytest.mark.django_db
class TestHealthCheckCeleryFailureIsIndependent:
    def test_celery_apply_async_failure_reported_without_masking_database_status(self):
        client = APIClient()
        with patch(
            "core.health.celery_health_check.apply_async",
            side_effect=Exception("broker unreachable"),
        ):
            res = client.get(url())

        assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert res.data["status"] == "unhealthy"
        assert res.data["checks"]["celery"] is False
        assert res.data["checks"]["database"] is True

    def test_celery_get_timeout_reported_as_unhealthy_and_does_not_hang(self):
        """
        Simulates a queued-but-never-picked-up task (broker up, no live
        worker) — .get() raises Celery's own TimeoutError. Confirms this
        is caught and reported as False, not left to propagate as a
        500, and that the call returns promptly rather than blocking
        for longer than the configured timeout.
        """
        client = APIClient()
        with patch(
            "celery.result.AsyncResult.get",
            side_effect=CeleryTimeoutError("timed out"),
        ):
            import time

            start = time.monotonic()
            res = client.get(url())
            elapsed = time.monotonic() - start

        assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert res.data["checks"]["celery"] is False
        # The mock raises immediately rather than actually waiting out
        # the timeout, but this still guards against a code path that
        # would otherwise wrap .get() in something that retries/sleeps
        # beyond the configured bound.
        assert elapsed < 5
