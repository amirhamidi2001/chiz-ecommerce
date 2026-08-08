import pytest
from accounts.models import Profile, UserType
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:

    # ── Creation ──────────────────────────────────────────────────────────

    def test_create_user_stores_normalised_email(self):
        user = User.objects.create_user(email="TEST@Example.COM", password="Pass1!")
        assert user.email == "test@example.com"

    def test_create_user_sets_unusable_password_when_none_given(self):
        user = User.objects.create_user(email="nopass@example.com")
        assert not user.has_usable_password()

    def test_create_user_default_flags(self):
        user = User.objects.create_user(email="flags@example.com", password="Pass1!")
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_verified is False
        assert user.type == UserType.CUSTOMER

    def test_create_user_requires_email(self):
        with pytest.raises(ValueError, match="Email must be set"):
            User.objects.create_user(email="", password="Pass1!")

    def test_email_field_is_unique(self, user):
        with pytest.raises(IntegrityError):
            User.objects.create_user(email=user.email, password="Other1!")

    def test_str_returns_email(self, user):
        assert str(user) == user.email

    # ── Superuser ─────────────────────────────────────────────────────────

    def test_create_superuser_sets_all_staff_flags(self, superuser):
        assert superuser.is_staff is True
        assert superuser.is_superuser is True
        assert superuser.is_active is True
        assert superuser.is_verified is True
        assert superuser.type == UserType.SUPERUSER

    def test_create_superuser_rejects_non_staff(self):
        with pytest.raises(ValueError, match="is_staff"):
            User.objects.create_superuser(
                email="bad@example.com",
                password="Pass1!",
                is_staff=False,
            )

    def test_create_superuser_rejects_non_superuser(self):
        with pytest.raises(ValueError, match="is_superuser"):
            User.objects.create_superuser(
                email="bad2@example.com",
                password="Pass1!",
                is_superuser=False,
            )

    # ── Timestamps ────────────────────────────────────────────────────────

    def test_created_date_is_set_on_first_save(self, user):
        assert user.created_date is not None

    def test_updated_date_changes_on_save(self, user):
        original = user.updated_date
        user.is_verified = True
        user.save()
        user.refresh_from_db()
        assert user.updated_date >= original


@pytest.mark.django_db
class TestProfileModel:

    def test_profile_is_auto_created_by_signal(self, user):
        assert Profile.objects.filter(user=user).exists()

    def test_profile_has_correct_user_link(self, user):
        assert user.profile.user == user

    def test_get_fullname_with_both_names(self, user):
        user.profile.first_name = "John"
        user.profile.last_name = "Doe"
        assert user.profile.get_fullname() == "John Doe"

    def test_get_fullname_with_only_first_name(self, user):
        user.profile.first_name = "Jane"
        user.profile.last_name = ""
        assert user.profile.get_fullname() == "Jane"

    def test_get_fullname_with_only_last_name(self, user):
        user.profile.first_name = ""
        user.profile.last_name = "Smith"
        assert user.profile.get_fullname() == "Smith"

    def test_get_fullname_with_no_names_returns_default(self, user):
        user.profile.first_name = ""
        user.profile.last_name = ""
        assert user.profile.get_fullname() == "new user"

    def test_str_includes_full_name_and_email(self, user):
        user.profile.first_name = "Jane"
        user.profile.last_name = "Doe"
        assert "Jane Doe" in str(user.profile)
        assert user.email in str(user.profile)

    def test_email_preference_defaults(self, user):
        assert user.profile.order_updates is True
        assert user.profile.promotions is False
        assert user.profile.newsletter is True

    def test_one_to_one_cascade_delete(self, user):
        profile_pk = user.profile.pk
        user.delete()
        assert not Profile.objects.filter(pk=profile_pk).exists()
