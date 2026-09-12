"""
core/health.py
────────────────
Shared health-check logic. No check_health management command or any
other health-check mechanism existed anywhere in this codebase before
this task (verified: no health-related view/command/URL anywhere) — this
module exists so that if a management command is ever added later, it
can call the exact same functions the HTTP endpoint uses, rather than
duplicating the apply_async()/.get() logic.
"""

from core.tasks import celery_health_check

CELERY_HEALTH_CHECK_TIMEOUT = 5  # seconds — bounded so the health check
# itself never hangs indefinitely if Celery is down; short enough to
# poll regularly, long enough to distinguish "healthy and fast" from
# "broken or badly degraded".


def check_database() -> bool:
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


def check_celery(timeout: int = CELERY_HEALTH_CHECK_TIMEOUT) -> bool:
    """
    Queues celery_health_check and BLOCKS waiting for a real worker to
    pick it up and complete it. This is the crux of the whole check:
    proving broker connectivity AND at least one live worker process,
    not just that Django can construct a task message (which an
    importable, correctly-configured Celery app object could do even
    with the broker or every worker down).
    """
    try:
        result = celery_health_check.apply_async()
        result.get(timeout=timeout)
        return True
    except Exception:
        return False


def run_health_checks() -> dict:
    checks = {"database": check_database(), "celery": check_celery()}
    return {
        "status": "healthy" if all(checks.values()) else "unhealthy",
        "checks": checks,
    }
