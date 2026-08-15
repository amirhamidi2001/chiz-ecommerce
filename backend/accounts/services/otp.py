"""
OTP generation and verification service.

Handles generating a new 6-digit one-time code, hashing it before
storage (the raw code is never persisted), creating the OTPCode row
with a configurable TTL, and verifying a user-submitted code against
it. The harder, per-view abuse throttle (Task 2.1.2.4) lives
elsewhere — this module enforces per-code invariants (expiry, max
attempts, single-use) regardless of which view or throttle class
eventually wraps it.
"""

import secrets

from accounts.models import OTPCode
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
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


class OTPNotFoundError(OTPServiceError):
    """
    Raised by verify_otp() when no unused OTPCode exists at all for the
    given (phone_number, purpose) — e.g. none was ever requested, or the
    only one that existed was already consumed by a prior successful
    verification.
    """


class OTPExpiredError(OTPServiceError):
    """
    Raised by verify_otp() when the most recent matching OTPCode's TTL
    has passed. The row itself is left untouched (`is_used` stays False)
    — expiry and "used" are kept as distinct concepts: "used" means
    "successfully verified", not "expired/abandoned".
    """


class OTPMaxAttemptsExceededError(OTPServiceError):
    """
    Raised by verify_otp() when a code has already accumulated
    OTP_MAX_VERIFICATION_ATTEMPTS failed attempts. Raised WITHOUT even
    checking the submitted code — a maxed-out code is permanently
    unusable regardless of whether this particular guess happens to be
    correct, closing a bypass where an attacker gets unlimited guesses
    as long as they never submit the real code on what would otherwise
    be the final permitted attempt.
    """


class OTPIncorrectCodeError(OTPServiceError):
    """
    Raised by verify_otp() when the submitted code doesn't match. Only a
    generic failure is signaled — the exception deliberately does not
    carry remaining-attempts detail, since surfacing that to a client
    could help an attacker calibrate a brute-force attempt. Callers that
    want to display remaining attempts to a legitimate user should query
    OTPCode themselves, not infer it from this exception.
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


def verify_otp(phone_number: str, purpose: str, submitted_code: str) -> bool:
    """
    Verify `submitted_code` against the most recent unused OTPCode for
    (phone_number, purpose).

    This function either returns True (verification succeeded — the row
    is marked is_used=True) or raises one of the specific OTPServiceError
    subclasses below; it never returns False. Distinct exceptions let the
    calling API view (Task 2.3.1.2) return precise, user-friendly error
    messages per failure mode instead of one generic "invalid code" for
    everything:

        OTPNotFoundError            — no unused code exists at all
        OTPExpiredError             — the code's TTL has passed
        OTPMaxAttemptsExceededError — too many prior failed attempts
        OTPIncorrectCodeError       — the submitted code is wrong

    Order of checks matters: max-attempts is checked BEFORE comparing
    the submitted code, so a maxed-out code is rejected even if the
    submitted code happens to be correct.
    """
    otp = (
        OTPCode.objects.filter(
            phone_number=phone_number, purpose=purpose, is_used=False
        )
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        raise OTPNotFoundError(
            f"No pending OTP found for {phone_number!r} (purpose={purpose!r})."
        )

    if otp.expires_at < timezone.now():
        # Leave the row exactly as-is (is_used stays False, attempts
        # unchanged) — expired is a distinct state from used/abandoned,
        # not something we mutate on read.
        raise OTPExpiredError("This OTP has expired.")

    if otp.attempts >= settings.OTP_MAX_VERIFICATION_ATTEMPTS:
        # Deliberately does not even look at submitted_code.
        raise OTPMaxAttemptsExceededError(
            "Maximum verification attempts exceeded for this OTP."
        )

    if check_password(submitted_code, otp.code_hash):
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        return True

    otp.attempts += 1
    otp.save(update_fields=["attempts"])
    raise OTPIncorrectCodeError("Incorrect code.")
