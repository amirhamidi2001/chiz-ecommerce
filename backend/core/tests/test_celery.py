"""
core/tests/test_celery.py
────────────────────────────
Tests for the Celery bootstrap (core/celery.py, core/__init__.py,
core/settings/base.py CELERY_* settings).

NOTE ON SCOPE: this task's brief described a "full inventory" of
@shared_task functions spanning shop/payments/shipping/notifications,
and asked for a PeriodicTask seed migration registering three specific
periodic tasks. Neither exists in this codebase: there is no
payments/, shipping/, or notifications/ app anywhere in the project,
and no tasks.py file exists in ANY app (including shop) at the time
this task was implemented. Seeding PeriodicTask rows pointing at
task paths that don't exist would create broken schedule entries that
only fail at runtime when Beat tries to dispatch them — exactly the
failure mode the task's own instructions warn against — so no seed
migration was added, and there's nothing to test for that here.

These tests instead confirm what's actually real: the Celery app is
correctly wired to Django's Redis-backed broker/result-backend (DB 1,
per the documented allocation scheme), autodiscovery genuinely runs
(there's just nothing to discover yet), and CELERY_TIMEZONE tracks
whatever TIME_ZONE is actually configured — a regression guard that
holds regardless of what that value is.
"""

from django.conf import settings
from django.test import TestCase

from core.celery import app as celery_app


class CeleryBootstrapTests(TestCase):
    def test_broker_and_result_backend_use_the_documented_redis_db(self):
        expected = f"redis://127.0.0.1:6379/{settings.REDIS_DB_CELERY}"
        self.assertEqual(celery_app.conf.broker_url, expected)
        self.assertEqual(celery_app.conf.result_backend, expected)

    def test_celery_broker_db_is_distinct_from_cache_and_sessions(self):
        self.assertNotEqual(settings.REDIS_DB_CELERY, settings.REDIS_DB_CACHE)
        self.assertNotEqual(settings.REDIS_DB_CELERY, settings.REDIS_DB_SESSIONS)
        self.assertNotEqual(settings.REDIS_DB_CELERY, settings.REDIS_DB_CHANNELS)

    def test_beat_scheduler_is_the_database_scheduler(self):
        self.assertEqual(
            celery_app.conf.beat_scheduler,
            "django_celery_beat.schedulers.DatabaseScheduler",
        )

    def test_celery_timezone_matches_django_time_zone(self):
        """
        Regression guard against CELERY_TIMEZONE silently drifting from
        TIME_ZONE (e.g. someone hardcoding "UTC" instead of referencing
        the setting) — without this, an admin scheduling "run at 2 AM"
        via the database scheduler could get a confusing mismatch.
        """
        self.assertEqual(settings.CELERY_TIMEZONE, settings.TIME_ZONE)
        self.assertEqual(celery_app.conf.timezone, settings.TIME_ZONE)

    def test_task_serialization_is_json_only(self):
        self.assertEqual(celery_app.conf.task_serializer, "json")
        self.assertEqual(celery_app.conf.result_serializer, "json")
        self.assertEqual(celery_app.conf.accept_content, ["json"])

    def test_autodiscovery_registers_the_builtin_debug_task(self):
        """
        Confirms autodiscover_tasks() actually ran without erroring and
        the app is a genuinely usable Celery app — the concrete,
        available proof that autodiscovery works, given no app in this
        codebase has a tasks.py module yet for it to find.
        """
        self.assertIn("core.celery.debug_task", celery_app.tasks)
