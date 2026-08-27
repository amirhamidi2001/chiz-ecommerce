import re

from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle

_RATE_PERIOD_RE = re.compile(r"^(\d+)?([a-zA-Z]+)$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class AuthSensitiveRateThrottle(AnonRateThrottle):
    """
    Tighter throttle for sensitive, high-value-target auth endpoints —
    login, register, and password-reset request/confirm — where a
    scripted attacker (credential stuffing, mass fake account creation,
    email-enumeration/spam) is meaningfully more likely to target than
    ordinary browsing. Deliberately much stricter than the general
    "anon" scope (Task 2.4.1.3).

    Plain AnonRateThrottle subclass — no custom get_cache_key() needed,
    since keying by IP (the default AnonRateThrottle behavior) is
    exactly right here, unlike PhoneOTPRequestThrottle below which
    needed to key by phone number instead.
    """

    scope = "auth_sensitive"


class PhoneOTPRequestThrottle(SimpleRateThrottle):
    """
    Rate-limits OTP requests keyed by the PHONE NUMBER being targeted,
    not by request.user or IP.
    """

    scope = "otp_request"

    def parse_rate(self, rate):
        """
        Extended parse_rate supporting an optional leading multiplier on
        the period, e.g. "3/10min" -> (3, 600). DRF's stock parse_rate
        only supports a bare unit ("min", "hour", ...), not "10min".
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
        data = getattr(request, "data", None)
        if data is not None:
            try:
                phone_number = data.get("phone_number")
            except AttributeError:
                phone_number = None

        if phone_number:
            ident = phone_number
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }
