from datetime import timedelta

import pytest
from accounts.models import OTPCode
from accounts.services.otp import OTPCooldownError, generate_otp
from django.contrib.auth.hashers import check_password
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
