"""
OTP generation service.

Handles generating a new 6-digit one-time code, hashing it before
storage (the raw code is never persisted), and creating the OTPCode
row with a configurable TTL. Verification (Task 2.1.2.3) and the
harder, per-view abuse throttle (Task 2.1.2.4) both live elsewhere —
this module is deliberately narrow: generation + a lightweight,
always-on resend cooldown that applies regardless of which view or
throttle class eventually wraps it.
"""

import secrets

from accounts.models import OTPCode
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.utils import timezone


class OTPServiceError(Exception):
    """Base class for OTP service errors."""


class OTPCooldownError(OTPServiceError):
    """
    Raised when a caller requests a new OTP for a (phone_number, purpose)
    pair that already has a recent, unused, still-valid code — i.e. a
    resend was requested before OTP_RESEND_COOLDOWN_SECONDS has elapsed.

    This is an always-on, service-level guard against accidental
    double-submission (e.g. a double-tapped "Send code" button) turning
    into two SMS sends. It is intentionally independent of, and not a
    replacement for, the per-view rate limiting added in Task 2.1.2.4.
    """


def _generate_numeric_code(length: int = 6) -> str:
    """
    Generate a cryptographically secure, zero-padded numeric code.

    Uses `secrets` (not `random`) since OTP codes are a security-relevant
    secret — `random` is not suitable for anything security-sensitive.
    """
    upper_bound = 10**length
    return str(secrets.randbelow(upper_bound)).zfill(length)


def generate_otp(phone_number: str, purpose: str) -> str:
    """
    Generate and persist a new OTP for `phone_number` and `purpose`.

    Returns the RAW (unhashed) 6-digit code so the caller can send it
    via SMS. This is the only place the raw code exists outside of the
    SMS payload itself — only a hash of it (via Django's own password
    hasher stack, `make_password`) is ever written to the database.

    Raises:
        OTPCooldownError: if a recent, unused, still-valid OTPCode
            already exists for this exact (phone_number, purpose) pair,
            created within the last OTP_RESEND_COOLDOWN_SECONDS.
    """
    now = timezone.now()
    cooldown_cutoff = now - timezone.timedelta(
        seconds=settings.OTP_RESEND_COOLDOWN_SECONDS
    )

    recent_unused_exists = OTPCode.objects.filter(
        phone_number=phone_number,
        purpose=purpose,
        is_used=False,
        created_at__gte=cooldown_cutoff,
        expires_at__gt=now,
    ).exists()
    if recent_unused_exists:
        raise OTPCooldownError(
            f"An OTP was already requested for {phone_number!r} "
            f"(purpose={purpose!r}) within the last "
            f"{settings.OTP_RESEND_COOLDOWN_SECONDS} seconds."
        )

    raw_code = _generate_numeric_code()

    OTPCode.objects.create(
        phone_number=phone_number,
        purpose=purpose,
        code_hash=make_password(raw_code),
        expires_at=now + timezone.timedelta(seconds=settings.OTP_CODE_TTL_SECONDS),
    )

    return raw_code
