"""
Tests for accounts.throttles.PhoneOTPRequestThrottle.

Per this task's scope, the throttle is not yet attached to any real
view (that's Task 2.3.1.1) — these tests exercise the throttle class
directly against a lightweight fake request object exposing just the
`.data` and `.META` attributes SimpleRateThrottle actually touches,
matching the acceptance criteria's suggested approach.

DRF throttles store their request history in Django's cache backend
(`rest_framework.throttling.SimpleRateThrottle.cache`, which defaults
to `django.core.cache.cache`). No CACHES setting is configured anywhere
in core/settings/*.py, so Django falls back to its default
LocMemCache — fine for these tests, but the cache must be cleared
between tests since LocMemCache persists in-process for the life of
the test run, not just for a single request/response cycle like a real
throttle's cache entries eventually expiring would.
"""

import pytest
from accounts.throttles import PhoneOTPRequestThrottle
from django.core.cache import cache


class FakeRequest:
    """
    Minimal stand-in for a DRF Request: only exposes what
    SimpleRateThrottle.get_cache_key() / get_ident() actually read
    (`.data` and `.META`), rather than spinning up a full
    APIRequestFactory request for what's a pure unit test of the
    throttle's key-building logic.
    """

    def __init__(self, data=None, remote_addr="127.0.0.1"):
        self.data = data if data is not None else {}
        self.META = {"REMOTE_ADDR": remote_addr}


@pytest.fixture(autouse=True)
def clear_cache():
    """
    Throttle history lives in Django's cache (LocMemCache by default in
    this project), which persists across tests in the same process —
    clear it before and after every test so throttle state never leaks
    between test cases.
    """
    cache.clear()
    yield
    cache.clear()


class TestPhoneOTPRequestThrottleRateParsing:

    def test_rate_string_parses_to_3_requests_per_600_seconds(self):
        """
        "3/10min" isn't valid syntax for DRF's stock parse_rate() (it
        only supports a bare unit, not a numeric multiplier) — this
        confirms PhoneOTPRequestThrottle's parse_rate() override
        correctly interprets the configured DEFAULT_THROTTLE_RATES
        value as 3 requests per 600 seconds (10 minutes).
        """
        throttle = PhoneOTPRequestThrottle()
        assert throttle.num_requests == 3
        assert throttle.duration == 600


class TestPhoneOTPRequestThrottleAllowRequest:

    def test_first_three_requests_allowed_fourth_blocked(self):
        request = FakeRequest({"phone_number": "09121234567"})
        throttle = PhoneOTPRequestThrottle()

        results = [throttle.allow_request(request, None) for _ in range(4)]

        assert results == [True, True, True, False]

    def test_two_different_phone_numbers_each_get_independent_allowance(self):
        request_a = FakeRequest({"phone_number": "09121111111"})
        request_b = FakeRequest({"phone_number": "09122222222"})

        throttle_a = PhoneOTPRequestThrottle()
        for _ in range(3):
            assert throttle_a.allow_request(request_a, None) is True
        # Phone A is now maxed out.
        assert PhoneOTPRequestThrottle().allow_request(request_a, None) is False

        # Phone B must be completely unaffected by phone A's usage —
        # proves the cache key is scoped per phone number.
        throttle_b = PhoneOTPRequestThrottle()
        for _ in range(3):
            assert throttle_b.allow_request(request_b, None) is True
        assert PhoneOTPRequestThrottle().allow_request(request_b, None) is False

    def test_missing_phone_number_does_not_raise_and_still_throttles(self):
        request = FakeRequest({})  # no "phone_number" key at all

        throttle = PhoneOTPRequestThrottle()
        # Must not raise (e.g. AttributeError/KeyError) — falls back to
        # an IP-based bucket instead of crashing or bypassing entirely.
        result = throttle.allow_request(request, None)
        assert result is True

        # The fallback bucket is still a real, enforced limit: repeating
        # the same no-phone request from the same IP eventually blocks.
        results = [
            PhoneOTPRequestThrottle().allow_request(FakeRequest({}), None)
            for _ in range(3)
        ]
        assert results == [True, True, False]

    def test_none_phone_number_value_falls_back_gracefully(self):
        # phone_number present but explicitly None (e.g. a client sent
        # `"phone_number": null`) must be treated the same as missing.
        request = FakeRequest({"phone_number": None})
        throttle = PhoneOTPRequestThrottle()
        assert throttle.allow_request(request, None) is True

    def test_blank_phone_number_value_falls_back_gracefully(self):
        request = FakeRequest({"phone_number": ""})
        throttle = PhoneOTPRequestThrottle()
        assert throttle.allow_request(request, None) is True

    def test_missing_phone_and_present_phone_are_tracked_independently(self):
        """
        The IP-based fallback bucket and a real phone-number bucket must
        not collide with each other in the cache.
        """
        no_phone_request = FakeRequest({})
        phone_request = FakeRequest({"phone_number": "09123334444"})

        for _ in range(3):
            assert (
                PhoneOTPRequestThrottle().allow_request(no_phone_request, None) is True
            )
        # No-phone bucket (same IP) is now maxed out...
        assert PhoneOTPRequestThrottle().allow_request(no_phone_request, None) is False

        # ...but a request WITH a phone number must be unaffected.
        assert PhoneOTPRequestThrottle().allow_request(phone_request, None) is True

    def test_scope_is_otp_request(self):
        assert PhoneOTPRequestThrottle.scope == "otp_request"
