"""
core/tests/test_redis_cache.py
───────────────────────────────
Verifies the Redis-backed cache configured in core/settings/base.py
against a REAL Redis connection (not mocked):

  1. cache.set()/cache.get() round-trips correctly.
  2. The cache's Redis DB index is genuinely distinct from the
     Channels layer's Redis DB index — proven by writing a marker key
     directly into the cache's DB via redis-py and confirming it is
     NOT visible when querying the Channels DB directly.

These tests require a real, reachable Redis instance (see
docker-compose.dev.yml's `redis` service) — they are skipped
automatically if one isn't available, so they don't break CI/dev
environments that haven't started Redis.
"""

import redis as redis_py
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase


def _redis_available():
    try:
        client = redis_py.Redis(host="127.0.0.1", port=6379, socket_connect_timeout=1)
        return client.ping()
    except Exception:
        return False


REDIS_UP = _redis_available()


class RedisCacheRoundTripTests(TestCase):
    """cache.set()/cache.get() round-trip against the real cache backend."""

    def setUp(self):
        if not REDIS_UP:
            self.skipTest("Redis is not reachable in this environment.")
        cache.clear()

    def tearDown(self):
        if REDIS_UP:
            cache.clear()

    def test_cache_set_get_round_trip(self):
        cache.set("test_key", "test_value")
        self.assertEqual(cache.get("test_key"), "test_value")

    def test_cache_get_missing_key_returns_none(self):
        self.assertIsNone(cache.get("does_not_exist"))


class RedisDbIsolationTests(TestCase):
    """
    Concrete proof that the cache and the Channels layer use different
    Redis DB indices: a marker key written directly (via redis-py) into
    the cache's DB must NOT be visible from the Channels DB.
    """

    def setUp(self):
        if not REDIS_UP:
            self.skipTest("Redis is not reachable in this environment.")

        self.cache_db = settings.REDIS_DB_CACHE
        self.channels_db = settings.REDIS_DB_CHANNELS
        self.assertNotEqual(
            self.cache_db,
            self.channels_db,
            "REDIS_DB_CACHE and REDIS_DB_CHANNELS must be distinct.",
        )

        self.cache_client = redis_py.Redis(
            host="127.0.0.1", port=6379, db=self.cache_db
        )
        self.channels_client = redis_py.Redis(
            host="127.0.0.1", port=6379, db=self.channels_db
        )
        self.marker_key = "isolation_test_marker"

    def tearDown(self):
        if REDIS_UP:
            self.cache_client.delete(self.marker_key)
            self.channels_client.delete(self.marker_key)

    def test_cache_and_channels_use_isolated_dbs(self):
        self.cache_client.set(self.marker_key, "only-in-cache-db")

        self.assertEqual(
            self.cache_client.get(self.marker_key),
            b"only-in-cache-db",
        )
        self.assertIsNone(
            self.channels_client.get(self.marker_key),
            "Marker key set in the cache DB leaked into the Channels DB — "
            "they are not actually isolated.",
        )
