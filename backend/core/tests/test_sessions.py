"""
core/tests/test_sessions.py
─────────────────────────────
Verifies the cached_db session backend configured in
core/settings/base.py (Task 21.1.1.5) against real Redis + Postgres:

  1. A value set in request.session and saved is correctly retrieved
     by a SUBSEQUENT SessionStore load using the same session key —
     exercises the real read/write path, not just settings correctness.
  2. The actual durability benefit of cached_db: if the Redis-side
     cache entry is missing (simulating a Redis restart/eviction) but
     the database row still exists, the session is still correctly
     retrieved via the database fallback.

NOTE on Epic 5 "guest cart" re-verification: the task asked for this,
but there is no session-based/anonymous cart anywhere in this
codebase to re-verify. cart/models.py's Cart.user is a required
(non-nullable) OneToOneField to the authenticated user — the model's
own docstring says "One cart per authenticated user" — and every cart
view requires IsAuthenticated. There is no request.session usage
anywhere in the cart app. That acceptance criterion doesn't apply to
this codebase as it actually exists.

These tests require real, reachable Redis + Postgres — standard for
this project's existing Redis-backed tests (see
core/tests/test_redis_cache.py), and are skipped if Redis isn't
reachable.
"""

import redis as redis_py
import pytest
from django.conf import settings
from django.core.cache import caches
from django.test import TestCase
from django.utils.module_loading import import_string


def _get_session_store_class():
    """
    Resolve the SessionStore class from settings.SESSION_ENGINE, the
    same way Django's SessionMiddleware does — a hardcoded import here
    would silently exercise a fixed backend regardless of what
    SESSION_ENGINE is actually configured to, defeating the point of
    these tests as a regression guard on the settings themselves.
    """
    return import_string(f"{settings.SESSION_ENGINE}.SessionStore")


def _redis_available():
    try:
        client = redis_py.Redis(host="127.0.0.1", port=6379, socket_connect_timeout=1)
        return client.ping()
    except Exception:
        return False


REDIS_UP = _redis_available()


class SessionBackendTests(TestCase):
    def setUp(self):
        if not REDIS_UP:
            self.skipTest("Redis is not reachable in this environment.")

    def test_session_value_round_trips_via_new_store_instance(self):
        SessionStore = _get_session_store_class()
        store = SessionStore()
        store["favorite_color"] = "teal"
        store.save()
        session_key = store.session_key

        # A fresh SessionStore, as a new request would construct, loaded
        # with the same session key — this is the real read path.
        reloaded = SessionStore(session_key=session_key)
        self.assertEqual(reloaded["favorite_color"], "teal")

        # Clean up.
        reloaded.delete()

    def test_confirms_settings_use_separate_sessions_cache_alias(self):
        self.assertEqual(
            settings.SESSION_ENGINE, "django.contrib.sessions.backends.cached_db"
        )
        self.assertEqual(settings.SESSION_CACHE_ALIAS, "sessions")
        self.assertNotEqual(settings.REDIS_DB_SESSIONS, settings.REDIS_DB_CACHE)

    def test_cache_miss_falls_back_to_database(self):
        """
        The actual proof cached_db's durability benefit works: delete
        ONLY the Redis-side cache entry (simulating a Redis
        restart/eviction) while leaving the database row intact, and
        confirm the session is still correctly retrieved.

        Resolves SessionStore from settings.SESSION_ENGINE dynamically
        (see _get_session_store_class) rather than importing cached_db
        directly — a hardcoded import here would exercise a fixed
        backend regardless of what's actually configured, so this test
        would still pass even if SESSION_ENGINE were wrongly reverted
        to the pure "cache" backend (verified: an earlier draft of this
        test made exactly that mistake and passed vacuously under a
        sabotaged pure-cache SESSION_ENGINE).
        """
        SessionStore = _get_session_store_class()
        store = SessionStore()
        store["order_note"] = "gift wrap please"
        store.save()
        session_key = store.session_key
        cache_key = store.cache_key

        # Simulate a Redis-side loss: delete ONLY the cache entry, not
        # the database row.
        sessions_cache = caches[settings.SESSION_CACHE_ALIAS]
        sessions_cache.delete(cache_key)
        self.assertIsNone(sessions_cache.get(cache_key))

        # A fresh load must still succeed via the database fallback.
        reloaded = SessionStore(session_key=session_key)
        self.assertEqual(reloaded["order_note"], "gift wrap please")

        reloaded.delete()
