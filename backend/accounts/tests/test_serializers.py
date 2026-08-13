import pytest
from accounts.serializers import (
    ChangePasswordSerializer,
    CurrentUserSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    RegisterSerializer,
)
from accounts.tokens import password_reset_token
from django.contrib.auth import get_user_model
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()


# ─── helpers ──────────────────────────────────────────────────────────────


def make_reset_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = password_reset_token.make_token(user)
    return uid, token


class FakeRequest:
    """Minimal request stand-in accepted by serializers that need context."""

    def __init__(self, user):
        self.user = user


# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestRegisterSerializer:

    VALID = {
        "email": "new@example.com",
        "first_name": "Alice",
        "last_name": "Smith",
        "password": "StrongPass123!",
    }

    def test_valid_data_creates_user(self):
        s = RegisterSerializer(data=self.VALID)
        assert s.is_valid(), s.errors
        user = s.save()
        assert User.objects.filter(email="new@example.com").exists()
        assert user.check_password("StrongPass123!")

    def test_valid_data_updates_profile_names(self):
        s = RegisterSerializer(data=self.VALID)
        s.is_valid(raise_exception=True)
        user = s.save()
        assert user.profile.first_name == "Alice"
        assert user.profile.last_name == "Smith"

    def test_duplicate_email_raises_error(self, user):
        data = {**self.VALID, "email": user.email}
        s = RegisterSerializer(data=data)
        assert not s.is_valid()
        assert "email" in s.errors

    def test_blank_email_raises_error(self):
        s = RegisterSerializer(data={**self.VALID, "email": ""})
        assert not s.is_valid()
        assert "email" in s.errors

    def test_weak_password_raises_error(self):
        s = RegisterSerializer(data={**self.VALID, "password": "123"})
        assert not s.is_valid()
        assert "password" in s.errors

    def test_missing_first_name_raises_error(self):
        data = {k: v for k, v in self.VALID.items() if k != "first_name"}
        s = RegisterSerializer(data=data)
        assert not s.is_valid()
        assert "first_name" in s.errors


@pytest.mark.django_db
class TestProfileSerializer:

    @pytest.fixture
    def profile(self, user):
        user.profile.first_name = "Jane"
        user.profile.last_name = "Doe"
        user.profile.phone_number = "+12345678901"
        user.profile.save()
        return user.profile

    def test_serialises_email_from_user(self, profile):
        s = ProfileSerializer(profile)
        assert s.data["email"] == profile.user.email

    def test_serialises_all_expected_fields(self, profile):
        s = ProfileSerializer(profile)
        keys = set(s.data.keys())
        assert {
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "order_updates",
            "promotions",
            "newsletter",
        }.issubset(keys)

    def test_email_is_read_only(self, profile):
        """Attempting to patch email via ProfileSerializer must be ignored."""
        s = ProfileSerializer(
            profile,
            data={"email": "hacker@evil.com", "first_name": "Jane", "last_name": "Doe"},
            partial=True,
        )
        assert s.is_valid()
        updated = s.save()
        assert updated.user.email != "hacker@evil.com"

    def test_valid_patch_updates_profile(self, profile):
        s = ProfileSerializer(
            profile,
            data={"first_name": "Updated", "last_name": "Name"},
            partial=True,
        )
        assert s.is_valid(), s.errors
        updated = s.save()
        assert updated.first_name == "Updated"
        assert updated.last_name == "Name"

    def test_invalid_phone_number_raises_error(self, profile):
        s = ProfileSerializer(
            profile,
            data={"phone_number": "not-a-number"},
            partial=True,
        )
        assert not s.is_valid()
        assert "phone_number" in s.errors

    def test_toggles_can_be_updated(self, profile):
        s = ProfileSerializer(
            profile,
            data={"order_updates": False, "promotions": True, "newsletter": False},
            partial=True,
        )
        assert s.is_valid(), s.errors
        updated = s.save()
        assert updated.order_updates is False
        assert updated.promotions is True
        assert updated.newsletter is False


@pytest.mark.django_db
class TestChangePasswordSerializer:

    def _make(self, user, data):
        return ChangePasswordSerializer(
            data=data, context={"request": FakeRequest(user)}
        )

    def test_valid_data_changes_password(self, user):
        s = self._make(
            user,
            {
                "current_password": "SecurePass123!",
                "new_password": "NewSecure456!",
                "confirm_password": "NewSecure456!",
            },
        )
        assert s.is_valid(), s.errors
        s.save()
        user.refresh_from_db()
        assert user.check_password("NewSecure456!")

    def test_wrong_current_password_raises_error(self, user):
        s = self._make(
            user,
            {
                "current_password": "WrongPassword!",
                "new_password": "NewSecure456!",
                "confirm_password": "NewSecure456!",
            },
        )
        assert not s.is_valid()
        assert "current_password" in s.errors

    def test_mismatched_new_passwords_raises_error(self, user):
        s = self._make(
            user,
            {
                "current_password": "SecurePass123!",
                "new_password": "NewSecure456!",
                "confirm_password": "DifferentPass789!",
            },
        )
        assert not s.is_valid()
        assert "confirm_password" in s.errors

    def test_weak_new_password_raises_error(self, user):
        s = self._make(
            user,
            {
                "current_password": "SecurePass123!",
                "new_password": "abc",
                "confirm_password": "abc",
            },
        )
        assert not s.is_valid()
        assert "new_password" in s.errors


@pytest.mark.django_db
class TestPasswordResetRequestSerializer:

    def test_valid_email_passes(self, user):
        s = PasswordResetRequestSerializer(data={"email": user.email})
        assert s.is_valid()

    def test_unknown_email_still_passes_validation(self):
        """Never reveal whether an email exists — no error for unknown emails."""
        s = PasswordResetRequestSerializer(data={"email": "ghost@example.com"})
        assert s.is_valid()

    def test_get_user_returns_user_for_known_email(self, user):
        s = PasswordResetRequestSerializer(data={"email": user.email})
        s.is_valid()
        assert s.get_user() == user

    def test_get_user_returns_none_for_unknown_email(self):
        s = PasswordResetRequestSerializer(data={"email": "ghost@example.com"})
        s.is_valid()
        assert s.get_user() is None

    def test_invalid_email_format_raises_error(self):
        s = PasswordResetRequestSerializer(data={"email": "not-an-email"})
        assert not s.is_valid()
        assert "email" in s.errors


@pytest.mark.django_db
class TestPasswordResetConfirmSerializer:

    def test_valid_uid_and_token_resets_password(self, user):
        uid, token = make_reset_link(user)
        s = PasswordResetConfirmSerializer(
            data={
                "uid": uid,
                "token": token,
                "new_password": "BrandNew789!",
                "confirm_password": "BrandNew789!",
            }
        )
        assert s.is_valid(), s.errors
        s.save()
        user.refresh_from_db()
        assert user.check_password("BrandNew789!")

    def test_invalid_uid_raises_error(self, user):
        _, token = make_reset_link(user)
        s = PasswordResetConfirmSerializer(
            data={
                "uid": "InvalidUID==",
                "token": token,
                "new_password": "Pass123!",
                "confirm_password": "Pass123!",
            }
        )
        assert not s.is_valid()
        assert "uid" in s.errors

    def test_invalid_token_raises_error(self, user):
        uid, _ = make_reset_link(user)
        s = PasswordResetConfirmSerializer(
            data={
                "uid": uid,
                "token": "tampered-token",
                "new_password": "Pass123!",
                "confirm_password": "Pass123!",
            }
        )
        assert not s.is_valid()
        assert "token" in s.errors

    def test_token_is_invalidated_after_password_change(self, user):
        uid, token = make_reset_link(user)
        # Change the password first
        user.set_password("AlreadyChanged!")
        user.save()
        # Now try to use the old token
        s = PasswordResetConfirmSerializer(
            data={
                "uid": uid,
                "token": token,
                "new_password": "AnotherPass123!",
                "confirm_password": "AnotherPass123!",
            }
        )
        assert not s.is_valid()
        assert "token" in s.errors

    def test_mismatched_passwords_raises_error(self, user):
        uid, token = make_reset_link(user)
        s = PasswordResetConfirmSerializer(
            data={
                "uid": uid,
                "token": token,
                "new_password": "Pass123!",
                "confirm_password": "DifferentPass!",
            }
        )
        assert not s.is_valid()
        assert "confirm_password" in s.errors


# ═══════════════════════════════════════════════════════════════════════════════
# CurrentUserSerializer
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestCurrentUserSerializer:

    def test_phone_number_is_present_and_read_only(self, user):
        user.phone_number = "+989123456789"
        user.save()

        data = CurrentUserSerializer(user).data
        assert data["phone_number"] == "09123456789"
        assert "phone_number" in CurrentUserSerializer.Meta.read_only_fields

    def test_phone_number_is_null_when_not_set(self, user):
        assert user.phone_number is None
        data = CurrentUserSerializer(user).data
        assert data["phone_number"] is None
