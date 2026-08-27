import pytest
from accounts.tokens import password_reset_token
from accounts.throttles import AuthSensitiveRateThrottle
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

User = get_user_model()

REGISTER_URL = "/api/auth/register/"
LOGIN_URL = "/api/auth/login/"
TOKEN_REFRESH_URL = "/api/auth/token/refresh/"
CURRENT_USER_URL = "/api/auth/user/"
PROFILE_URL = "/api/auth/profile/"
CHANGE_PW_URL = "/api/auth/change-password/"
PW_RESET_URL = "/api/auth/password-reset/"
PW_RESET_CONF_URL = "/api/auth/password-reset/confirm/"


@pytest.fixture(autouse=True)
def _clear_throttle_cache_for_every_test():
    """
    Module-wide autouse fixture (Task 2.4.1.4). LoginView, RegisterView,
    PasswordResetRequestView, and PasswordResetConfirmView all gained a
    REAL throttle (AuthSensitiveRateThrottle, 10/min) in this task —
    before that, these endpoints had zero throttling of their own, so
    the many pre-existing tests in this file that repeatedly POST to
    them never mattered. Throttle history lives in Django's cache
    (LocMemCache, no CACHES override anywhere in this project), which
    persists across every test function in the same process — without
    clearing it here, the cumulative request count across ALL tests in
    this file (not just the throttle-specific ones below) can exceed
    the real 10/min limit and start failing unrelated,
    previously-passing tests with an unexpected 429. Scoped to the
    whole module (not just TestAuthSensitiveRateThrottle) since any
    class here can hit these now-throttled endpoints.
    """
    cache.clear()
    yield
    cache.clear()


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
# auth_sensitive throttle scope (Task 2.4.1.4)
# ──────────────────────────────────────────────────────────────────────────
#
# Uses the same patch.object(ThrottleClass, "rate", ..., create=True)
# pattern already established in shop/tests/test_views.py for the
# general anon-rate test, rather than @override_settings — DRF binds a
# throttle class's rate as an instance attribute resolved from
# settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"][self.scope] inside
# SimpleRateThrottle.__init__ at instantiation time, so overriding the
# *settings* dict doesn't reliably affect an already-imported throttle
# class the way patching the class attribute directly does.
@pytest.mark.django_db
class TestAuthSensitiveRateThrottle:
    # Cache clearing is handled by the module-level
    # _clear_throttle_cache_for_every_test autouse fixture above — no
    # class-specific fixture needed here.

    def test_login_returns_429_once_lowered_limit_is_exceeded(self):
        """
        Hammers POST /api/auth/login/ with intentionally wrong
        credentials — it doesn't matter that every attempt fails
        authentication (400/401), only that enough requests land to
        exceed the (temporarily lowered) auth_sensitive rate and
        produce a 429.
        """
        with patch.object(AuthSensitiveRateThrottle, "rate", "3/min", create=True):
            client = APIClient()
            statuses = [
                client.post(
                    LOGIN_URL,
                    {"email": "nobody@example.com", "password": "wrong-password"},
                    format="json",
                ).status_code
                for _ in range(5)
            ]

        # First 3 requests (the lowered limit) are NOT throttled — they
        # fail on bad credentials instead (401/400 depending on
        # SimpleJWT's exact response), never 429.
        assert status.HTTP_429_TOO_MANY_REQUESTS not in statuses[:3]
        # ...and at least one request beyond that is throttled.
        assert status.HTTP_429_TOO_MANY_REQUESTS in statuses[3:]

    def test_register_returns_429_once_lowered_limit_is_exceeded(self):
        """
        Uses a fresh, unique email per request specifically so every
        attempt reaches the throttle check rather than short-circuiting
        on a 400 "email already exists" validation error, which would
        make this test meaningless (it needs to prove the THROTTLE
        fires, not registration's own uniqueness validation).
        """
        with patch.object(AuthSensitiveRateThrottle, "rate", "3/min", create=True):
            client = APIClient()
            statuses = []
            for i in range(5):
                payload = {
                    "email": f"throttle-register-{i}@example.com",
                    "first_name": "Throttle",
                    "last_name": "Test",
                    "password": "SecurePass123!",
                }
                res = client.post(REGISTER_URL, payload, format="json")
                statuses.append(res.status_code)

        assert statuses[:3] == [
            status.HTTP_201_CREATED,
            status.HTTP_201_CREATED,
            status.HTTP_201_CREATED,
        ]
        assert status.HTTP_429_TOO_MANY_REQUESTS in statuses[3:]

    def test_password_reset_request_returns_429_once_lowered_limit_is_exceeded(self):
        with patch.object(AuthSensitiveRateThrottle, "rate", "3/min", create=True):
            client = APIClient()
            statuses = [
                client.post(
                    PW_RESET_URL, {"email": "someone@example.com"}, format="json"
                ).status_code
                for _ in range(5)
            ]

        # First 3 succeed with the endpoint's normal always-200
        # enumeration-safe response.
        assert statuses[:3] == [status.HTTP_200_OK] * 3
        assert status.HTTP_429_TOO_MANY_REQUESTS in statuses[3:]

    def test_password_reset_confirm_returns_429_once_lowered_limit_is_exceeded(self):
        with patch.object(AuthSensitiveRateThrottle, "rate", "3/min", create=True):
            client = APIClient()
            statuses = [
                client.post(
                    PW_RESET_CONF_URL,
                    {
                        "uid": "invalid-uid",
                        "token": "invalid-token",
                        "new_password": "Pass123!",
                        "confirm_password": "Pass123!",
                    },
                    format="json",
                ).status_code
                for _ in range(5)
            ]

        # Invalid uid/token means every non-throttled attempt fails
        # validation (400) — never 429 for the first 3.
        assert status.HTTP_429_TOO_MANY_REQUESTS not in statuses[:3]
        assert status.HTTP_429_TOO_MANY_REQUESTS in statuses[3:]

    def test_current_user_view_is_not_affected_by_auth_sensitive_scope(
        self, auth_client
    ):
        """
        CurrentUserView requires authentication already and was
        deliberately NOT given throttle_classes = [AuthSensitiveRateThrottle]
        (Task 2.4.1.4's explicit exclusion list). Proof: even with
        auth_sensitive set to an absurdly low 1/min, several authenticated
        requests to this view must all still succeed — if it were
        wrongly using this scope, the 2nd request would already 429.
        """
        with patch.object(AuthSensitiveRateThrottle, "rate", "1/min", create=True):
            statuses = [auth_client.get(CURRENT_USER_URL).status_code for _ in range(5)]

        assert statuses == [status.HTTP_200_OK] * 5

    def test_profile_view_is_not_affected_by_auth_sensitive_scope(self, auth_client):
        """Same isolation proof as above, for ProfileView."""
        with patch.object(AuthSensitiveRateThrottle, "rate", "1/min", create=True):
            statuses = [auth_client.get(PROFILE_URL).status_code for _ in range(5)]

        assert statuses == [status.HTTP_200_OK] * 5

    def test_normal_traffic_is_not_throttled_under_the_real_default_rate(self):
        """
        Sanity check with the REAL (untouched) 10/min default: a
        handful of ordinary login attempts must not be throttled.
        """
        client = APIClient()
        statuses = [
            client.post(
                LOGIN_URL,
                {"email": "nobody@example.com", "password": "wrong-password"},
                format="json",
            ).status_code
            for _ in range(5)
        ]
        assert status.HTTP_429_TOO_MANY_REQUESTS not in statuses
