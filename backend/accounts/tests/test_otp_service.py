from datetime import timedelta

import pytest
from accounts.models import OTPCode
from accounts.services.otp import (
    OTPCooldownError,
    OTPExpiredError,
    OTPIncorrectCodeError,
    OTPMaxAttemptsExceededError,
    OTPNotFoundError,
    generate_otp,
    verify_otp,
)
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone


@pytest.mark.django_db
class TestGenerateOTP:

    def test_returns_a_six_digit_numeric_string(self):
        code = generate_otp("09123456789", "login")
        assert isinstance(code, str)
        assert len(code) == 6
        assert code.isdigit()

    def test_creates_exactly_one_unused_row_with_hashed_code(self):
        phone = "09121112222"
        code = generate_otp(phone, "login")

        qs = OTPCode.objects.filter(phone_number=phone, purpose="login")
        assert qs.count() == 1

        otp = qs.get()
        assert otp.is_used is False
        assert otp.code_hash  # non-empty
        assert otp.code_hash != code  # never stored in plaintext
        assert check_password(code, otp.code_hash)

    def test_expires_at_matches_configured_ttl(self, settings):
        settings.OTP_CODE_TTL_SECONDS = 300
        before = timezone.now()
        generate_otp("09123334444", "register")
        after = timezone.now()

        otp = OTPCode.objects.get(phone_number="09123334444", purpose="register")

        # expires_at should fall within [before + 300s, after + 300s],
        # accounting for the small amount of real time the call itself takes.
        assert before + timedelta(seconds=300) <= otp.expires_at
        assert otp.expires_at <= after + timedelta(seconds=300)

    def test_immediate_second_call_same_phone_and_purpose_raises_cooldown(self):
        phone = "09125556666"
        generate_otp(phone, "login")

        with pytest.raises(OTPCooldownError):
            generate_otp(phone, "login")

        # Only the first row was created — the cooldown attempt didn't
        # create a second row before raising.
        assert OTPCode.objects.filter(phone_number=phone, purpose="login").count() == 1

    def test_cooldown_is_scoped_per_purpose_not_just_phone(self):
        phone = "09127778888"
        generate_otp(phone, "login")

        # A different purpose for the same phone must NOT be blocked by
        # the login cooldown.
        code = generate_otp(phone, "register")
        assert isinstance(code, str)
        assert len(code) == 6

        assert OTPCode.objects.filter(phone_number=phone, purpose="login").count() == 1
        assert (
            OTPCode.objects.filter(phone_number=phone, purpose="register").count() == 1
        )

    def test_cooldown_does_not_block_a_different_phone_number(self):
        generate_otp("09121110000", "login")
        # A completely different phone number must never be affected by
        # another number's cooldown.
        code = generate_otp("09129990000", "login")
        assert isinstance(code, str)

    def test_expired_cooldown_window_allows_a_new_code(self, settings):
        settings.OTP_RESEND_COOLDOWN_SECONDS = 60
        phone = "09121234321"
        generate_otp(phone, "reset")

        # Simulate the cooldown having already elapsed by backdating the
        # existing row's created_at, rather than sleeping in the test.
        OTPCode.objects.filter(phone_number=phone, purpose="reset").update(
            created_at=timezone.now() - timedelta(seconds=61)
        )

        code = generate_otp(phone, "reset")
        assert isinstance(code, str)
        assert OTPCode.objects.filter(phone_number=phone, purpose="reset").count() == 2

    def test_two_generated_codes_are_not_trivially_identical(self):
        """
        Loose sanity check that codes are actually randomized (not a
        cryptographic randomness test, just a guard against an obviously
        broken/constant generator). Generates several codes and asserts
        they aren't all the same value.
        """
        phones = [f"0912345{i:04d}" for i in range(5)]
        codes = {generate_otp(phone, "login") for phone in phones}
        assert len(codes) > 1


@pytest.mark.django_db
class TestVerifyOTP:

    def make_otp(
        self,
        phone_number,
        purpose="login",
        raw_code="123456",
        expires_in_seconds=120,
        attempts=0,
        is_used=False,
    ):
        """
        Directly construct an OTPCode row with a known raw code and
        arbitrary expiry/attempts/is_used state — used instead of a
        time-freezing library (freezegun isn't a project dependency;
        confirmed via requirements.txt / pip) so expired/maxed-out
        scenarios don't require sleeping in real time or mocking the
        clock globally.
        """
        return OTPCode.objects.create(
            phone_number=phone_number,
            purpose=purpose,
            code_hash=make_password(raw_code),
            expires_at=timezone.now() + timedelta(seconds=expires_in_seconds),
            attempts=attempts,
            is_used=is_used,
        )

    # ── success ──────────────────────────────────────────────────────────────

    def test_correct_unexpired_code_succeeds_and_marks_used(self):
        phone = "09121230000"
        otp = self.make_otp(phone, raw_code="654321")

        result = verify_otp(phone, "login", "654321")

        assert result is True
        otp.refresh_from_db()
        assert otp.is_used is True

    def test_generate_then_verify_round_trip(self):
        """End-to-end through both service functions, not just make_otp()."""
        phone = "09121230001"
        code = generate_otp(phone, "login")
        assert verify_otp(phone, "login", code) is True

    # ── incorrect code ──────────────────────────────────────────────────────

    def test_incorrect_code_raises_and_increments_attempts_without_using(self):
        phone = "09121230002"
        otp = self.make_otp(phone, raw_code="111111")

        with pytest.raises(OTPIncorrectCodeError):
            verify_otp(phone, "login", "999999")

        otp.refresh_from_db()
        assert otp.attempts == 1
        assert otp.is_used is False  # still usable for further attempts

    def test_row_remains_usable_for_further_attempts_until_the_cap(self, settings):
        settings.OTP_MAX_VERIFICATION_ATTEMPTS = 5
        phone = "09121230003"
        otp = self.make_otp(phone, raw_code="222222")

        for _ in range(4):
            with pytest.raises(OTPIncorrectCodeError):
                verify_otp(phone, "login", "000000")

        otp.refresh_from_db()
        assert otp.attempts == 4

        # Still under the cap (5) — the correct code must still work.
        assert verify_otp(phone, "login", "222222") is True

    # ── expiry ───────────────────────────────────────────────────────────────

    def test_expired_code_fails_even_with_correct_code(self):
        phone = "09121230004"
        otp = self.make_otp(phone, raw_code="333333", expires_in_seconds=-10)

        with pytest.raises(OTPExpiredError):
            verify_otp(phone, "login", "333333")

        # Row is left untouched — expired is distinct from used/abandoned.
        otp.refresh_from_db()
        assert otp.is_used is False
        assert otp.attempts == 0

    # ── max attempts ─────────────────────────────────────────────────────────

    def test_max_attempts_reached_fails_even_with_correct_code(self, settings):
        settings.OTP_MAX_VERIFICATION_ATTEMPTS = 5
        phone = "09121230005"
        otp = self.make_otp(phone, raw_code="444444", attempts=5)

        with pytest.raises(OTPMaxAttemptsExceededError):
            verify_otp(phone, "login", "444444")  # correct code, but maxed out

        otp.refresh_from_db()
        assert otp.attempts == 5  # not incremented further past the cap
        assert otp.is_used is False

    def test_max_attempts_check_happens_before_code_comparison(self, settings):
        """
        Explicitly proves the maxed-out check short-circuits before the
        code is even compared — an incorrect guess against a maxed-out
        code must raise OTPMaxAttemptsExceededError, not
        OTPIncorrectCodeError (which would imply the code was checked).
        """
        settings.OTP_MAX_VERIFICATION_ATTEMPTS = 3
        phone = "09121230006"
        self.make_otp(phone, raw_code="555555", attempts=3)

        with pytest.raises(OTPMaxAttemptsExceededError):
            verify_otp(phone, "login", "000000")

    # ── already used ─────────────────────────────────────────────────────────

    def test_already_used_code_cannot_be_reused(self):
        phone = "09121230007"
        self.make_otp(phone, raw_code="666666", is_used=True)

        with pytest.raises(OTPNotFoundError):
            verify_otp(phone, "login", "666666")

    def test_successful_verification_then_immediate_reuse_fails(self):
        phone = "09121230008"
        otp = self.make_otp(phone, raw_code="777777")
        assert verify_otp(phone, "login", "777777") is True

        with pytest.raises(OTPNotFoundError):
            verify_otp(phone, "login", "777777")

    # ── no matching code ─────────────────────────────────────────────────────

    def test_no_otp_at_all_fails_cleanly(self):
        with pytest.raises(OTPNotFoundError):
            verify_otp("09190000000", "login", "123456")

    def test_otp_exists_for_different_purpose_does_not_match(self):
        phone = "09121230009"
        self.make_otp(phone, purpose="register", raw_code="888888")

        with pytest.raises(OTPNotFoundError):
            verify_otp(phone, "login", "888888")

    def test_otp_exists_for_different_phone_does_not_match(self):
        self.make_otp("09121111111", raw_code="999999")

        with pytest.raises(OTPNotFoundError):
            verify_otp("09122222222", "login", "999999")

    # ── most-recent-row selection ────────────────────────────────────────────

    def test_verifies_against_most_recent_unused_row_when_multiple_exist(self):
        phone = "09121230010"
        older = self.make_otp(phone, raw_code="111111")
        OTPCode.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(minutes=1)
        )
        newer = self.make_otp(phone, raw_code="222222")

        # The older code must no longer verify — only the newest row
        # (correct code "222222") should succeed.
        with pytest.raises(OTPIncorrectCodeError):
            verify_otp(phone, "login", "111111")

        assert verify_otp(phone, "login", "222222") is True
        newer.refresh_from_db()
        assert newer.is_used is True
