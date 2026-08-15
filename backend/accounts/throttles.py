"""
DRF throttle for OTP-request endpoints.

Task 2.1.2.2 added a lightweight in-service cooldown (~60s per
(phone_number, purpose) pair) purely to stop accidental double-taps —
it does not stop a scripted attacker from spamming OTP requests across
many different `purpose` values, or simply waiting out that cooldown
repeatedly, to SMS-bomb a phone number (a real cost/abuse concern once
Epic 16 wires up real SMS sending via Kavenegar).

This throttle is a harder, DRF-level cap, independent of and in
addition to that service-layer cooldown. It's not applied to any view
yet — Task 2.3.1.1 attaches it via `throttle_classes` on the actual
OTP-request view once that view exists. This module only defines and
unit-tests the throttle class itself.
"""

import re

from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import SimpleRateThrottle

# DRF's built-in SimpleRateThrottle.parse_rate() only understands a bare
# unit as the period ("min", "hour", "day", ...) — each treated as
# exactly 1 of that unit. It does NOT support a numeric multiplier like
# "10min" (i.e. "3/10min" raises a KeyError inside DRF's own parser,
# since it tries to look up the period string's first character, "1",
# as a unit). Since this throttle's rate is naturally expressed as
# "N requests per M minutes" (matching the backlog's stated
# requirement), parse_rate() is overridden below to support an optional
# leading multiplier while still accepting DRF's normal "N/unit" syntax.
_RATE_PERIOD_RE = re.compile(r"^(\d+)?([a-zA-Z]+)$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class PhoneOTPRequestThrottle(SimpleRateThrottle):
    """
    Rate-limits OTP requests keyed by the PHONE NUMBER being targeted,
    not by request.user or IP.

    Keying by phone number (rather than the default user/IP-based
    scheme) matters here specifically because the phone number is the
    resource being protected from abuse (each request costs real money
    via the SMS gateway once wired up), and an attacker can trivially
    rotate IPs/proxies while still hammering the same victim phone
    number — IP-based throttling alone would not stop that.

    Falls back to IP-based throttling (via the standard `get_ident`)
    when no `phone_number` is present in the request body, so a
    malformed request without a phone number still gets *some*
    throttling instead of bypassing the limit entirely.
    """

    scope = "otp_request"

    def parse_rate(self, rate):
        """
        Extended version of SimpleRateThrottle.parse_rate() that also
        accepts an optional leading multiplier on the period, e.g.
        "3/10min" -> (3, 600). Falls through to the same unit mapping
        DRF itself uses ('s'/'m'/'h'/'d', matched by first letter) for
        the base duration, so plain "N/min", "N/hour", etc. still work
        exactly as they do in stock DRF.
        """
        if rate is None:
            return (None, None)
        num, period = rate.split("/")
        num_requests = int(num)

        match = _RATE_PERIOD_RE.match(period)
        if not match:
            raise ImproperlyConfigured(f"Invalid throttle rate period: {period!r}")
        multiplier_str, unit = match.groups()
        multiplier = int(multiplier_str) if multiplier_str else 1

        try:
            base_seconds = _UNIT_SECONDS[unit[0]]
        except KeyError:
            raise ImproperlyConfigured(f"Invalid throttle rate period: {period!r}")

        return (num_requests, base_seconds * multiplier)

    def get_cache_key(self, request, view):
        phone_number = None
        # request.data may not exist / may not behave like a dict for
        # every possible request type reaching this throttle (e.g. a
        # bare mock in tests, or a request whose body failed to parse)
        # — be defensive rather than let a malformed request bypass
        # throttling via an unhandled exception here.
        data = getattr(request, "data", None)
        if data is not None:
            try:
                phone_number = data.get("phone_number")
            except AttributeError:
                phone_number = None

        if phone_number:
            ident = phone_number
        else:
            # No phone number provided — fall back to an IP-based bucket
            # so the request is still throttled, just not scoped to a
            # specific victim phone number.
            ident = self.get_ident(request)

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }
