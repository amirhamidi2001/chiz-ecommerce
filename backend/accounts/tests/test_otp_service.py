from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from accounts.models import OTPCode
from accounts.services.otp import (
    OTPCooldownError,
    OTPExpiredError,
    OTPIncorrectCodeError,
    OTPMaxAttemptsExceededError,
    OTPNotFoundError,
    SMSDeliveryError,
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
class TestGenerateOTPSMSDispatch:
    """
    Task 2.2.1.3: generate_otp() is now responsible for actually
    dispatching the SMS via the configured SMSProvider, not just
    creating the OTPCode row. These tests mock get_sms_provider()
    directly (rather than relying on the real ConsoleSMSProvider) so
    they can assert exactly what was sent and control success/failure
    deterministically.
    """

    def test_generate_otp_calls_sms_provider_send_exactly_once(self):
        phone = "09121230100"
        with patch("accounts.services.otp.get_sms_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.send.return_value = True
            mock_get_provider.return_value = mock_provider

            code = generate_otp(phone, "login")

        mock_provider.send.assert_called_once()
        call_args = mock_provider.send.call_args
        sent_phone, sent_message = call_args[0]
        assert sent_phone == phone
        assert code in sent_message

    def test_send_false_still_creates_otp_row_but_raises_sms_delivery_error(self):
        phone = "09121230101"
        with patch("accounts.services.otp.get_sms_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.send.return_value = False
            mock_get_provider.return_value = mock_provider

            with pytest.raises(SMSDeliveryError):
                generate_otp(phone, "login")

        # The OTPCode row must still exist — the code itself is still
        # valid even though delivery failed; it is NOT rolled back.
        qs = OTPCode.objects.filter(phone_number=phone, purpose="login")
        assert qs.count() == 1
        assert qs.get().is_used is False

    def test_send_raising_an_exception_also_raises_sms_delivery_error(self):
        """
        A future real provider (e.g. Kavenegar) might raise instead of
        returning False on failure (network error, etc.) — both must be
        normalized to the same SMSDeliveryError so callers only need to
        handle one exception type.
        """
        phone = "09121230102"
        with patch("accounts.services.otp.get_sms_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.send.side_effect = ConnectionError("gateway unreachable")
            mock_get_provider.return_value = mock_provider

            with pytest.raises(SMSDeliveryError):
                generate_otp(phone, "login")

        qs = OTPCode.objects.filter(phone_number=phone, purpose="login")
        assert qs.count() == 1

    def test_delivery_failure_logs_at_error_level_for_ops_visibility(self, caplog):
        import logging

        phone = "09121230103"
        with patch("accounts.services.otp.get_sms_provider") as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.send.return_value = False
            mock_get_provider.return_value = mock_provider

            with caplog.at_level(logging.ERROR, logger="accounts.otp"):
                with pytest.raises(SMSDeliveryError):
                    generate_otp(phone, "login")

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        assert phone in error_records[0].getMessage()

    def test_cooldown_error_takes_priority_and_sms_is_never_sent(self):
        """
        If the cooldown check itself blocks the request, get_sms_provider()
        must never even be consulted — no SMS attempt for a rejected
        resend.
        """
        phone = "09121230104"
        generate_otp(phone, "login")  # first call succeeds via real console provider

        with patch("accounts.services.otp.get_sms_provider") as mock_get_provider:
            with pytest.raises(OTPCooldownError):
                generate_otp(phone, "login")
            mock_get_provider.assert_not_called()

    def test_console_provider_default_still_returns_the_code_unmocked(self):
        """
        Sanity check that the real (unmocked) default path — the
        ConsoleSMSProvider from Task 2.2.1.2 — still works end-to-end
        after this change: generate_otp() succeeds, returns the code,
        and doesn't raise, since ConsoleSMSProvider.send() always
        returns True.
        """
        code = generate_otp("09121230105", "login")
        assert isinstance(code, str)
        assert len(code) == 6


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
