"""
End-to-end integration tests for the full OTP flow (Tasks 2.3.1.1–2.3.1.3):
POST /api/auth/otp/request/ -> POST /api/auth/otp/verify/ -> authenticated
requests using the issued JWT — exercised entirely through the real HTTP
API via DRF's APIClient, the same way the frontend (Task 2.3.2) or a
mobile client actually would.

This complements, rather than duplicates, the narrower unit/view tests
already in test_otp_service.py (service-layer exception behavior) and
test_views.py (individual endpoint edge cases) — the focus here is the
full round trip and the handful of scenarios that only make sense when
chained together (e.g. "request, then verify, then use the token").

Known-code strategy: ConsoleSMSProvider only prints/logs the code, so a
black-box HTTP client can't recover it from the response (the request
endpoint deliberately never echoes it — Task 2.3.1.1). Rather than
mocking internals like `secrets.choice` (brittle — coupled to
generate_otp's exact implementation) or parsing ConsoleSMSProvider's
print/log output (indirect, and still requires monkeypatching), these
tests call the real `generate_otp()` service function directly to seed
a known code, then drive the rest of the flow purely through HTTP. This
matches the pattern already used elsewhere in test_views.py (e.g.
TestOTPVerifyView), so it's consistent with the existing suite, not a
new convention.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from accounts.models import OTPCode
from accounts.services.otp import generate_otp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

OTP_REQUEST_URL = "/api/auth/otp/request/"
OTP_VERIFY_URL = "/api/auth/otp/verify/"
CURRENT_USER_URL = "/api/auth/user/"


@pytest.mark.django_db
class TestOTPFullFlowIntegration:

    @pytest.fixture(autouse=True)
    def clear_throttle_and_cooldown_cache(self):
        """
        Both PhoneOTPRequestThrottle (Task 2.1.2.4) and the OTP service's
        own resend cooldown (Task 2.1.2.2) key off Django's cache /
        OTPCode rows respectively — the cache half needs clearing
        between tests the same way test_views.py's OTP test classes
        already do, so throttle state never leaks across tests.
        """
        cache.clear()
        yield
        cache.clear()

    # ── 1. Happy path — brand-new phone number ──────────────────────────────

    def test_happy_path_new_user_full_flow(self):
        client = APIClient()
        phone = "09121110001"

        request_res = client.post(
            OTP_REQUEST_URL, {"phone_number": phone}, format="json"
        )
        assert request_res.status_code == status.HTTP_200_OK

        # The request endpoint never echoes the code (by design — Task
        # 2.3.1.1's user-enumeration reasoning) — recover it via the
        # service layer directly, the least-brittle available option
        # for a true black-box HTTP test. This calls the real
        # generate_otp() again (a legitimate second request against the
        # same phone would hit the resend cooldown, so instead simulate
        # "the user received the code via SMS" by deleting the row the
        # HTTP call above created and issuing a fresh one we can read).
        OTPCode.objects.filter(phone_number=phone).delete()
        code = generate_otp(phone, "login")

        verify_res = client.post(
            OTP_VERIFY_URL,
            {"phone_number": phone, "code": code},
            format="json",
        )

        assert verify_res.status_code == status.HTTP_201_CREATED
        assert verify_res.data["is_new_user"] is True
        assert "access" in verify_res.data
        assert "refresh" in verify_res.data

        assert User.objects.filter(phone_number=phone).count() == 1

    # ── 2. Happy path — returning user ───────────────────────────────────────

    def test_happy_path_returning_user_full_flow_same_identity(self):
        client = APIClient()
        phone = "09121110002"
        existing_user = User.objects.create_user(
            email=None, phone_number=phone, is_verified=False
        )

        request_res = client.post(
            OTP_REQUEST_URL, {"phone_number": phone}, format="json"
        )
        assert request_res.status_code == status.HTTP_200_OK

        OTPCode.objects.filter(phone_number=phone).delete()
        code = generate_otp(phone, "login")

        verify_res = client.post(
            OTP_VERIFY_URL,
            {"phone_number": phone, "code": code},
            format="json",
        )

        assert verify_res.status_code == status.HTTP_200_OK
        assert verify_res.data["is_new_user"] is False

        # No duplicate account was created.
        assert User.objects.filter(phone_number=phone).count() == 1

        # Confirm the issued token really does identify the SAME
        # existing user — call GET /api/auth/user/ with it (rather than
        # decoding the JWT ourselves, this exercises the real
        # authentication path end-to-end, same as a real client would).
        access_token = verify_res.data["access"]
        authed_client = APIClient()
        authed_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        me_res = authed_client.get(CURRENT_USER_URL)
        assert me_res.status_code == status.HTTP_200_OK
        assert me_res.data["id"] == existing_user.pk
        assert me_res.data["phone_number"] == phone

    # ── 3. Wrong code ─────────────────────────────────────────────────────────

    def test_wrong_code_returns_400_no_tokens_and_increments_attempts(self):
        client = APIClient()
        phone = "09121110003"

        client.post(OTP_REQUEST_URL, {"phone_number": phone}, format="json")
        OTPCode.objects.filter(phone_number=phone).delete()
        real_code = generate_otp(phone, "login")
        wrong_code = "000000" if real_code != "000000" else "111111"

        verify_res = client.post(
            OTP_VERIFY_URL,
            {"phone_number": phone, "code": wrong_code},
            format="json",
        )

        assert verify_res.status_code == status.HTTP_400_BAD_REQUEST
        assert "access" not in verify_res.data
        assert "refresh" not in verify_res.data
        assert not User.objects.filter(phone_number=phone).exists()

        otp = OTPCode.objects.get(phone_number=phone, purpose="login")
        assert otp.attempts == 1
        assert otp.is_used is False

    # ── 4. Expired code ────────────────────────────────────────────────────────

    def test_expired_code_returns_400_specific_message_no_tokens(self):
        client = APIClient()
        phone = "09121110004"

        client.post(OTP_REQUEST_URL, {"phone_number": phone}, format="json")
        OTPCode.objects.filter(phone_number=phone).delete()
        code = generate_otp(phone, "login")

        # Fast-forward expires_at into the past directly on the row.
        OTPCode.objects.filter(phone_number=phone, purpose="login").update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        verify_res = client.post(
            OTP_VERIFY_URL,
            {"phone_number": phone, "code": code},
            format="json",
        )

        assert verify_res.status_code == status.HTTP_400_BAD_REQUEST
        assert "expired" in verify_res.data["code"].lower()
        assert "access" not in verify_res.data
        assert not User.objects.filter(phone_number=phone).exists()

    # ── 5. Max attempts exceeded ──────────────────────────────────────────────

    def test_max_attempts_exceeded_permanently_dead_even_with_correct_code(
        self, settings
    ):
        """
        Submits the wrong code OTP_MAX_VERIFICATION_ATTEMPTS times, then
        submits the CORRECT code on the next attempt — proving the code
        is permanently dead after too many wrong guesses, not merely
        rate-limited (i.e. the max-attempts check happens BEFORE the
        code comparison, so a maxed-out code rejects even a subsequently
        correct guess).
        """
        settings.OTP_MAX_VERIFICATION_ATTEMPTS = 5
        client = APIClient()
        phone = "09121110005"

        client.post(OTP_REQUEST_URL, {"phone_number": phone}, format="json")
        OTPCode.objects.filter(phone_number=phone).delete()
        real_code = generate_otp(phone, "login")
        wrong_code = "000000" if real_code != "000000" else "111111"

        for attempt in range(5):
            res = client.post(
                OTP_VERIFY_URL,
                {"phone_number": phone, "code": wrong_code},
                format="json",
            )
            assert (
                res.status_code == status.HTTP_400_BAD_REQUEST
            ), f"attempt {attempt + 1} unexpectedly succeeded"

        otp = OTPCode.objects.get(phone_number=phone, purpose="login")
        assert otp.attempts == 5

        # Now try the REAL code — must still fail.
        final_res = client.post(
            OTP_VERIFY_URL,
            {"phone_number": phone, "code": real_code},
            format="json",
        )
        assert final_res.status_code == status.HTTP_400_BAD_REQUEST
        assert "too many" in final_res.data["code"].lower()
        assert "access" not in final_res.data
        assert not User.objects.filter(phone_number=phone).exists()

    # ── 6. Rate limiting on request ──────────────────────────────────────────

    def test_request_endpoint_rate_limits_beyond_configured_throttle(self):
        """
        End-to-end version of the throttle check (unit-level coverage of
        PhoneOTPRequestThrottle itself lives in test_throttles.py, and
        Task 2.3.1.1's own tests already isolate the throttle layer from
        the service cooldown for a single scenario — this is the
        "hammer the real endpoint repeatedly" version for full-flow
        completeness, not a duplicate of either).

        generate_otp is patched to bypass the service-level ~60s resend
        cooldown so it doesn't interfere with observing the DRF-level
        throttle specifically (3 requests / 10 min by default).
        """
        client = APIClient()
        phone = "09121110006"

        with patch("accounts.views.generate_otp") as mock_generate_otp:
            mock_generate_otp.return_value = "123456"

            responses = [
                client.post(OTP_REQUEST_URL, {"phone_number": phone}, format="json")
                for _ in range(3)
            ]
            for res in responses:
                assert res.status_code == status.HTTP_200_OK

            throttled_res = client.post(
                OTP_REQUEST_URL, {"phone_number": phone}, format="json"
            )

        assert throttled_res.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # ── 7. Cross-purpose isolation ────────────────────────────────────────────
    #
    # OTPVerifyView (Task 2.3.1.2) hardcodes purpose="login" for every
    # verification — it never accepts or exposes `purpose` as a request
    # parameter, so there's no way for an HTTP client to submit a
    # verify call against a different purpose in the first place. This
    # scenario is therefore moot at the view/integration level; full
    # purpose-isolation coverage (a code generated for "login" cannot
    # verify against "register"/"reset") already exists at the service
    # layer in accounts/tests/test_otp_service.py
    # (TestVerifyOTP.test_otp_exists_for_different_purpose_does_not_match).

    # ── Full flow sanity: request then verify then re-request cooldown ──────

    def test_full_flow_then_immediate_reverify_fails_code_already_used(self):
        """
        Extra full-chain sanity check: after a successful verify, the
        exact same code can't be replayed (the OTPCode row is marked
        used, so a second verify attempt with the same code hits the
        "no pending code" path, not a false "success").
        """
        client = APIClient()
        phone = "09121110007"

        client.post(OTP_REQUEST_URL, {"phone_number": phone}, format="json")
        OTPCode.objects.filter(phone_number=phone).delete()
        code = generate_otp(phone, "login")

        first = client.post(
            OTP_VERIFY_URL, {"phone_number": phone, "code": code}, format="json"
        )
        assert first.status_code == status.HTTP_201_CREATED

        replay = client.post(
            OTP_VERIFY_URL, {"phone_number": phone, "code": code}, format="json"
        )
        assert replay.status_code == status.HTTP_400_BAD_REQUEST
        assert "access" not in replay.data

        # Still exactly one user — replay didn't create a second account.
        assert User.objects.filter(phone_number=phone).count() == 1
