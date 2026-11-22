"""
backend/conftest.py
───────────────────
Project-wide pytest fixtures.

LANGUAGE PIN (Epic 14): the site default is Persian (LANGUAGE_CODE = "fa")
and LocaleMiddleware now serves Persian to any request without an
Accept-Language header. The pre-Epic-14 suite asserts on English message
text, so by default every test runs under English. Tests that exercise
translation opt in explicitly — by sending an Accept-Language header,
wrapping code in translation.override("fa"), or using override_settings —
exactly as production clients would.

This applies to pytest runs (the project's runner, see pytest.ini); it is
not applied when running `manage.py test`.
"""

import pytest
from django.utils import translation


@pytest.fixture(autouse=True)
def _english_by_default(settings):
    settings.LANGUAGE_CODE = "en"
    translation.activate("en")
    yield
    translation.deactivate()


# ─── Notification templates survive TransactionTestCase flushes ────────────
#
# The starting NotificationTemplate rows (Epic 16) are created by DATA
# MIGRATIONS, which run once when the test database is built. A
# TransactionTestCase — e.g. payments/tests/test_callback_concurrency.py —
# TRUNCATEs every table when it finishes, wiping them; and with `--reuse-db`
# (pytest.ini) the next run reuses that emptied database WITHOUT re-running
# migrations, so every test that sends a real notification then finds no
# template and silently logs SKIPPED. (`serialized_rollback` doesn't help: the
# last flush still leaves the table empty for the next session.)
#
# So tests that touch the database get the seed rows topped up first. It uses
# the migrations' own seed functions and `get_or_create`, so it adds nothing
# when the rows are already there — one COUNT query per test in that case.

_SEED_MIGRATIONS = (
    "notifications.migrations.0002_seed_notification_templates",
    "notifications.migrations.0004_seed_remaining_email_templates",
)


_DB_FIXTURES = {
    "db",
    "transactional_db",
    "live_server",
    "django_db_reset_sequences",
    "django_db_serialized_rollback",
}


@pytest.fixture(autouse=True)
def _notification_templates_seeded(request):
    from django.test import SimpleTestCase, TransactionTestCase

    cls = getattr(request, "cls", None)
    is_django_unittest = cls is not None and issubclass(cls, SimpleTestCase)
    if is_django_unittest:
        # Django TestCase classes get their database from pytest-django's
        # class-level setup, which has already run (class scope precedes
        # function scope). SimpleTestCase has no database at all.
        uses_database = issubclass(cls, TransactionTestCase)
    else:
        uses_database = request.node.get_closest_marker(
            "django_db"
        ) is not None or bool(_DB_FIXTURES & set(request.fixturenames))

    if not uses_database:
        yield
        return

    if not is_django_unittest:
        # Autouse fixtures run before the ones a test asks for, so enable the
        # database now. `db` and `transactional_db` both resolve through the
        # same helper, which picks the right flavour from this test's own
        # marker/fixtures — so this is equivalent to what the test requests.
        request.getfixturevalue("db")

    import importlib

    from django.apps import apps

    seeds = [importlib.import_module(name) for name in _SEED_MIGRATIONS]
    expected = sum(len(module.SEED_TEMPLATES) for module in seeds)
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    if NotificationTemplate.objects.count() < expected:
        for module in seeds:
            module.seed_templates(apps, None)
    yield


# ─── Email is sent by a Celery task (Epic 16) ──────────────────────────────
#
# notify()'s EMAIL channel and the account emails queue
# notifications.tasks.send_notification_email_task with `.delay()`. Nothing
# runs a worker in tests, and Celery isn't in eager mode, so a real `.delay()`
# would publish to the configured broker (or hang retrying when there is none).
# This autouse fixture makes the queue a MagicMock for every test: tests that
# assert "an email WOULD be sent" inspect it, and tests that need the email to
# actually go out (django.core.mail.outbox) request `run_email_tasks`, which
# executes queued tasks synchronously — the same convention as
# shop/tests/test_search_log.py's `run_log_tasks`.


@pytest.fixture(autouse=True)
def _email_queue_is_mocked():
    from unittest.mock import patch

    with patch("notifications.tasks.send_notification_email_task.delay") as queue:
        yield queue


@pytest.fixture
def run_email_tasks():
    """Make queued email tasks run synchronously (via Celery's eager apply, so
    a failing task is recorded in its result rather than raised into the
    caller — as with a real worker). Yields the patched `.delay` mock."""
    from unittest.mock import patch

    from notifications.tasks import send_notification_email_task

    def run(*args, **kwargs):
        return send_notification_email_task.apply(args=args, kwargs=kwargs)

    with patch(
        "notifications.tasks.send_notification_email_task.delay", side_effect=run
    ) as queue:
        yield queue
