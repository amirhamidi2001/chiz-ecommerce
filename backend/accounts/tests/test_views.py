from unittest.mock import patch

import pytest
from accounts.models import OTPCode
from accounts.tokens import password_reset_token
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status

User = get_user_model()

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
TOKEN_REFRESH_URL = "/api/auth/token/refresh/"
PROFILE_URL = "/api/auth/profile/"
CHANGE_PW_URL = "/api/auth/change-password/"
PW_RESET_URL = "/api/auth/password-reset/"
PW_RESET_CONF_URL = "/api/auth/password-reset/confirm/"
OTP_REQUEST_URL = "/api/auth/otp/request/"


def make_reset_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = password_reset_token.make_token(user)
    return uid, token


# ──────────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRegisterView:

    PAYLOAD = {
        "email": "newuser@example.com",
        "first_name": "New",
        "last_name": "User",
        "password": "SecurePass123!",
    }

    def test_register_returns_201_with_tokens(self, api_client):
        res = api_client.post(REGISTER_URL, self.PAYLOAD, format="json")
        assert res.status_code == status.HTTP_201_CREATED
        assert "access" in res.data
        assert "refresh" in res.data

    def test_register_returns_user_info(self, api_client):
        res = api_client.post(REGISTER_URL, self.PAYLOAD, format="json")
        assert res.data["email"] == "newuser@example.com"
        assert res.data["first_name"] == "New"
        assert res.data["last_name"] == "User"

    def test_register_creates_user_in_database(self, api_client):
        api_client.post(REGISTER_URL, self.PAYLOAD, format="json")
        assert User.objects.filter(email="newuser@example.com").exists()

    def test_register_auto_creates_and_populates_profile(self, api_client):
        api_client.post(REGISTER_URL, self.PAYLOAD, format="json")
        user = User.objects.get(email="newuser@example.com")
        assert user.profile.first_name == "New"
        assert user.profile.last_name == "User"

    def test_register_sends_welcome_email(self, api_client):
        api_client.post(REGISTER_URL, self.PAYLOAD, format="json")
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["newuser@example.com"]

    def test_register_duplicate_email_returns_400(self, api_client, user):
        data = {**self.PAYLOAD, "email": user.email}
        res = api_client.post(REGISTER_URL, data, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in res.data

    def test_register_missing_password_returns_400(self, api_client):
        data = {k: v for k, v in self.PAYLOAD.items() if k != "password"}
        res = api_client.post(REGISTER_URL, data, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in res.data

    def test_register_missing_first_name_returns_400(self, api_client):
        data = {k: v for k, v in self.PAYLOAD.items() if k != "first_name"}
        res = api_client.post(REGISTER_URL, data, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "first_name" in res.data


# ──────────────────────────────────────────────────────────────────────────
# Login
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLoginView:

    def test_valid_credentials_return_200_with_tokens(self, api_client, user):
        res = api_client.post(
            LOGIN_URL,
            {
                "email": user.email,
                "password": "SecurePass123!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        assert "access" in res.data
        assert "refresh" in res.data

    def test_wrong_password_returns_401(self, api_client, user):
        res = api_client.post(
            LOGIN_URL,
            {
                "email": user.email,
                "password": "WrongPassword!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_nonexistent_email_returns_401(self, api_client):
        res = api_client.post(
            LOGIN_URL,
            {
                "email": "ghost@example.com",
                "password": "Pass123!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_inactive_user_cannot_login(self, api_client, user):
        user.is_active = False
        user.save()
        res = api_client.post(
            LOGIN_URL,
            {
                "email": user.email,
                "password": "SecurePass123!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_password_field_returns_400(self, api_client, user):
        res = api_client.post(LOGIN_URL, {"email": user.email}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST


# ──────────────────────────────────────────────────────────────────────────
# Token Refresh
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTokenRefreshView:

    def test_valid_refresh_returns_new_access_token(self, api_client, user_tokens):
        res = api_client.post(
            TOKEN_REFRESH_URL, {"refresh": user_tokens["refresh"]}, format="json"
        )
        assert res.status_code == status.HTTP_200_OK
        assert "access" in res.data
        # SimpleJWT with ROTATE_REFRESH_TOKENS returns a new refresh token too
        assert res.data["access"] != user_tokens["access"]

    def test_invalid_refresh_token_returns_401(self, api_client):
        res = api_client.post(
            TOKEN_REFRESH_URL, {"refresh": "bad.token.value"}, format="json"
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ──────────────────────────────────────────────────────────────────────────
# Profile
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestProfileView:

    def test_get_profile_returns_200_for_authenticated_user(self, auth_client, user):
        res = auth_client.get(PROFILE_URL)
        assert res.status_code == status.HTTP_200_OK

    def test_get_profile_returns_correct_fields(self, auth_client, user):
        user.profile.first_name = "Jane"
        user.profile.last_name = "Doe"
        user.profile.save()

        res = auth_client.get(PROFILE_URL)
        assert res.data["email"] == user.email
        assert res.data["first_name"] == "Jane"
        assert res.data["last_name"] == "Doe"

    def test_get_profile_returns_401_for_unauthenticated(self, api_client):
        res = api_client.get(PROFILE_URL)
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patch_updates_personal_info(self, auth_client, user):
        res = auth_client.patch(
            PROFILE_URL,
            {
                "first_name": "Updated",
                "last_name": "Name",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        user.profile.refresh_from_db()
        assert user.profile.first_name == "Updated"
        assert user.profile.last_name == "Name"

    def test_patch_updates_email_preferences(self, auth_client, user):
        res = auth_client.patch(
            PROFILE_URL,
            {
                "order_updates": False,
                "promotions": True,
                "newsletter": False,
            },
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        user.profile.refresh_from_db()
        assert user.profile.order_updates is False
        assert user.profile.promotions is True
        assert user.profile.newsletter is False

    def test_patch_invalid_phone_returns_400(self, auth_client):
        res = auth_client.patch(PROFILE_URL, {"phone_number": "abc"}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in res.data

    def test_put_method_not_allowed(self, auth_client):
        res = auth_client.put(PROFILE_URL, {"first_name": "X"}, format="json")
        assert res.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_patch_cannot_change_email(self, auth_client, user):
        original_email = user.email
        auth_client.patch(PROFILE_URL, {"email": "hacker@evil.com"}, format="json")
        user.refresh_from_db()
        assert user.email == original_email

    def test_user_cannot_access_another_users_profile(self, api_client, second_user):
        """Each authenticated user sees only their own profile."""
        from rest_framework_simplejwt.tokens import RefreshToken

        token = str(RefreshToken.for_user(second_user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        second_user.profile.first_name = "Other"
        second_user.profile.save()

        res = api_client.get(PROFILE_URL)
        assert res.data["email"] == second_user.email


# ──────────────────────────────────────────────────────────────────────────
# Change Password
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestChangePasswordView:

    def test_valid_change_returns_200(self, auth_client, user):
        res = auth_client.post(
            CHANGE_PW_URL,
            {
                "current_password": "SecurePass123!",
                "new_password": "NewSecure456!",
                "confirm_password": "NewSecure456!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        assert "detail" in res.data

    def test_password_is_actually_changed(self, auth_client, user):
        auth_client.post(
            CHANGE_PW_URL,
            {
                "current_password": "SecurePass123!",
                "new_password": "NewSecure456!",
                "confirm_password": "NewSecure456!",
            },
            format="json",
        )
        user.refresh_from_db()
        assert user.check_password("NewSecure456!")
        assert not user.check_password("SecurePass123!")

    def test_wrong_current_password_returns_400(self, auth_client):
        res = auth_client.post(
            CHANGE_PW_URL,
            {
                "current_password": "WrongCurrent!",
                "new_password": "NewSecure456!",
                "confirm_password": "NewSecure456!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "current_password" in res.data

    def test_mismatched_new_passwords_returns_400(self, auth_client):
        res = auth_client.post(
            CHANGE_PW_URL,
            {
                "current_password": "SecurePass123!",
                "new_password": "NewSecure456!",
                "confirm_password": "DifferentPass!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "confirm_password" in res.data

    def test_unauthenticated_returns_401(self, api_client):
        res = api_client.post(
            CHANGE_PW_URL,
            {
                "current_password": "Pass123!",
                "new_password": "New123!",
                "confirm_password": "New123!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED


# ──────────────────────────────────────────────────────────────────────────
# Password Reset Request
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPasswordResetRequestView:

    def test_known_email_returns_200(self, api_client, user):
        res = api_client.post(PW_RESET_URL, {"email": user.email}, format="json")
        assert res.status_code == status.HTTP_200_OK

    def test_unknown_email_also_returns_200(self, api_client):
        """Prevents user enumeration — always 200 regardless of whether the email exists."""
        res = api_client.post(
            PW_RESET_URL, {"email": "ghost@example.com"}, format="json"
        )
        assert res.status_code == status.HTTP_200_OK

    def test_reset_email_is_sent_for_known_user(self, api_client, user):
        api_client.post(PW_RESET_URL, {"email": user.email}, format="json")
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user.email]

    def test_no_email_sent_for_unknown_user(self, api_client):
        api_client.post(PW_RESET_URL, {"email": "ghost@example.com"}, format="json")
        assert len(mail.outbox) == 0

    def test_invalid_email_format_returns_400(self, api_client):
        res = api_client.post(PW_RESET_URL, {"email": "not-an-email"}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST


# ──────────────────────────────────────────────────────────────────────────
# Password Reset Confirm
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPasswordResetConfirmView:

    def test_valid_reset_returns_200(self, api_client, user):
        uid, token = make_reset_link(user)
        res = api_client.post(
            PW_RESET_CONF_URL,
            {
                "uid": uid,
                "token": token,
                "new_password": "BrandNew789!",
                "confirm_password": "BrandNew789!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK

    def test_valid_reset_changes_password(self, api_client, user):
        uid, token = make_reset_link(user)
        api_client.post(
            PW_RESET_CONF_URL,
            {
                "uid": uid,
                "token": token,
                "new_password": "BrandNew789!",
                "confirm_password": "BrandNew789!",
            },
            format="json",
        )
        user.refresh_from_db()
        assert user.check_password("BrandNew789!")

    def test_invalid_token_returns_400(self, api_client, user):
        uid, _ = make_reset_link(user)
        res = api_client.post(
            PW_RESET_CONF_URL,
            {
                "uid": uid,
                "token": "tampered",
                "new_password": "NewPass123!",
                "confirm_password": "NewPass123!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "token" in res.data

    def test_invalid_uid_returns_400(self, api_client, user):
        _, token = make_reset_link(user)
        res = api_client.post(
            PW_RESET_CONF_URL,
            {
                "uid": "InvalidUID==",
                "token": token,
                "new_password": "NewPass123!",
                "confirm_password": "NewPass123!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "uid" in res.data

    def test_token_cannot_be_reused_after_password_change(self, api_client, user):
        uid, token = make_reset_link(user)
        # First use — succeeds
        api_client.post(
            PW_RESET_CONF_URL,
            {
                "uid": uid,
                "token": token,
                "new_password": "FirstReset123!",
                "confirm_password": "FirstReset123!",
            },
            format="json",
        )
        # Second use — token is now stale because the password hash changed
        res = api_client.post(
            PW_RESET_CONF_URL,
            {
                "uid": uid,
                "token": token,
                "new_password": "SecondReset456!",
                "confirm_password": "SecondReset456!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_mismatched_passwords_returns_400(self, api_client, user):
        uid, token = make_reset_link(user)
        res = api_client.post(
            PW_RESET_CONF_URL,
            {
                "uid": uid,
                "token": token,
                "new_password": "Pass123!",
                "confirm_password": "Different456!",
            },
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "confirm_password" in res.data


# ──────────────────────────────────────────────────────────────────────────
# OTP Request
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestOTPRequestView:

    VALID_PHONE = "09123456789"

    @pytest.fixture(autouse=True)
    def clear_throttle_cache(self):
        """
        PhoneOTPRequestThrottle (Task 2.1.2.4) stores request history in
        Django's cache, which persists across tests in the same process
        (LocMemCache) — clear it before and after every test in this
        class so throttle/cooldown state never leaks between tests.
        """
        cache.clear()
        yield
        cache.clear()

    def test_valid_phone_number_returns_200_and_creates_one_otp_row(
        self, api_client
    ):
        res = api_client.post(
            OTP_REQUEST_URL, {"phone_number": self.VALID_PHONE}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK
        assert res.data == {"detail": "Verification code sent."}

        qs = OTPCode.objects.filter(phone_number=self.VALID_PHONE, purpose="login")
        assert qs.count() == 1

    def test_response_never_reveals_the_code_or_phone_confirmation(
        self, api_client
    ):
        """
        Deliberately vague response — no code, no phone-number echo, no
        hint about whether the number is already registered (same
        user-enumeration reasoning as PasswordResetRequestView).
        """
        res = api_client.post(
            OTP_REQUEST_URL, {"phone_number": self.VALID_PHONE}, format="json"
        )
        assert set(res.data.keys()) == {"detail"}
        assert self.VALID_PHONE not in res.data["detail"]

    @pytest.mark.parametrize(
        "invalid_phone",
        [
            "12345",
            "+15551234567",  # US number
            "02112345678",  # Iranian landline, not mobile
            "0812345678",  # wrong prefix (08, not 09)
        ],
    )
    def test_invalid_phone_format_returns_400_with_field_error(
        self, api_client, invalid_phone
    ):
        res = api_client.post(
            OTP_REQUEST_URL, {"phone_number": invalid_phone}, format="json"
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in res.data
        assert OTPCode.objects.filter(phone_number=invalid_phone).count() == 0

    def test_missing_phone_number_returns_400(self, api_client):
        res = api_client.post(OTP_REQUEST_URL, {}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in res.data

    def test_international_format_is_accepted_and_normalized(self, api_client):
        res = api_client.post(
            OTP_REQUEST_URL, {"phone_number": "+989123456789"}, format="json"
        )
        assert res.status_code == status.HTTP_200_OK
        # Stored under the normalized local-format number, not the raw
        # international-format input.
        assert OTPCode.objects.filter(
            phone_number="09123456789", purpose="login"
        ).exists()

    def test_second_immediate_request_same_phone_returns_429_cooldown(
        self, api_client
    ):
        first = api_client.post(
            OTP_REQUEST_URL, {"phone_number": self.VALID_PHONE}, format="json"
        )
        assert first.status_code == status.HTTP_200_OK

        second = api_client.post(
            OTP_REQUEST_URL, {"phone_number": self.VALID_PHONE}, format="json"
        )

        assert second.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "wait" in second.data["detail"].lower()

        # Cooldown rejection must not create a second row.
        assert (
            OTPCode.objects.filter(
                phone_number=self.VALID_PHONE, purpose="login"
            ).count()
            == 1
        )

    def test_fourth_request_within_throttle_window_returns_429_from_throttle(
        self, api_client
    ):
        """
        Isolates the DRF-level PhoneOTPRequestThrottle (Task 2.1.2.4,
        3 requests / 10 min) from the OTP service's own ~60s resend
        cooldown (Task 2.1.2.2) — which would otherwise block the 2nd
        request already, before the throttle ever gets a chance to be
        the thing that blocks the 4th. generate_otp() is patched to
        bypass the cooldown check entirely (always "succeeding") so
        every one of the first 3 requests reaches 200, and the 4th is
        blocked purely by the throttle layer.
        """
        phone = "09121230099"

        with patch("accounts.views.generate_otp") as mock_generate_otp:
            mock_generate_otp.return_value = "123456"

            for _ in range(3):
                res = api_client.post(
                    OTP_REQUEST_URL, {"phone_number": phone}, format="json"
                )
                assert res.status_code == status.HTTP_200_OK

            fourth = api_client.post(
                OTP_REQUEST_URL, {"phone_number": phone}, format="json"
            )

        assert fourth.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        # DRF's own throttle message ("Request was throttled...") is
        # distinct from the service-cooldown message asserted in
        # test_second_immediate_request_same_phone_returns_429_cooldown
        # above — confirms this 429 came from the throttle layer, not
        # the service-level cooldown (which was bypassed via the mock).
        assert "throttled" in str(fourth.data["detail"]).lower()

    def test_sms_delivery_failure_is_masked_and_still_returns_200(self, api_client):
        """
        Task 2.2.1.3's SMSDeliveryError must be swallowed by this view —
        the client still gets the same generic success response even
        when the SMS provider itself failed, per the user-enumeration
        reasoning documented on OTPRequestView. The OTPCode row still
        exists regardless (created before the send attempt).
        """
        from accounts.services.otp import SMSDeliveryError

        with patch("accounts.views.generate_otp") as mock_generate_otp:
            mock_generate_otp.side_effect = SMSDeliveryError("gateway down")

            res = api_client.post(
                OTP_REQUEST_URL, {"phone_number": self.VALID_PHONE}, format="json"
            )

        assert res.status_code == status.HTTP_200_OK
        assert res.data == {"detail": "Verification code sent."}
