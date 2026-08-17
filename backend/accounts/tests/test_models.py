import pytest
from accounts.models import OTPCode, Profile, UserType
from accounts.validators import normalize_iranian_phone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

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

    def test_create_user_without_email_succeeds_for_regular_users(self):
        """
        Task 2.3.1.2: email is no longer required at the manager level —
        this is what makes phone-only OTP accounts possible. A regular
        (non-staff) user can be created with email=None.
        """
        user = User.objects.create_user(
            email=None, password="Pass1!", phone_number="09121230200"
        )
        assert user.email is None
        assert user.pk is not None

    def test_create_user_without_email_raises_for_staff(self):
        """
        The one combination that's still blocked: a staff/superuser
        account MUST have an email, since Django admin login requires
        typing a value into USERNAME_FIELD ("email").
        """
        with pytest.raises(
            ValueError, match="Staff/superuser accounts must have an email"
        ):
            User.objects.create_user(email=None, password="Pass1!", is_staff=True)

    def test_email_field_is_unique(self, user):
        with pytest.raises(IntegrityError):
            User.objects.create_user(email=user.email, password="Other1!")

    def test_two_users_can_both_have_email_none(self):
        """
        Same nullable+unique pattern as phone_number (Task 2.1.1.1):
        multiple phone-only accounts with email=None must not conflict
        with each other.
        """
        u1 = User.objects.create_user(
            email=None, password="Pass1!", phone_number="09121230201"
        )
        u2 = User.objects.create_user(
            email=None, password="Pass1!", phone_number="09121230202"
        )
        assert u1.email is None
        assert u2.email is None

    # ── phone_number (Task 2.1.1.1) ──────────────────────────────────────────

    def test_two_users_can_both_have_phone_number_none(self):
        """
        Nullable + unique must not conflict on NULLs: existing
        email/password users have no phone number yet, so multiple users
        with phone_number=None must be perfectly valid.
        """
        u1 = User.objects.create_user(
            email="nophone1@example.com", password="Pass1!", phone_number=None
        )
        u2 = User.objects.create_user(
            email="nophone2@example.com", password="Pass1!", phone_number=None
        )
        assert u1.phone_number is None
        assert u2.phone_number is None
        assert User.objects.filter(phone_number__isnull=True).count() >= 2

    def test_duplicate_phone_number_raises_integrity_error(self):
        User.objects.create_user(
            email="phoneowner@example.com",
            password="Pass1!",
            phone_number="09123456789",
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email="phonestealer@example.com",
                password="Pass1!",
                phone_number="09123456789",
            )

    # ── Iranian phone validation + normalization (Task 2.1.1.2) ─────────────

    def test_normalize_iranian_phone_accepts_all_three_formats_equally(self):
        canonical = "09123456789"
        assert normalize_iranian_phone("+989123456789") == canonical
        assert normalize_iranian_phone("00989123456789") == canonical
        assert normalize_iranian_phone("09123456789") == canonical

    @pytest.mark.parametrize(
        "invalid_phone",
        [
            "12345",  # too short / not a phone at all
            "+15551234567",  # US number
            "02112345678",  # Iranian landline (area code, not mobile)
            "0812345678",  # starts with 08, not 09
            "091234567890",  # one digit too many
        ],
    )
    def test_full_clean_rejects_invalid_phone_formats(self, invalid_phone):
        """
        Tests the validator attached via `validators=[iranian_phone_regex]`
        on the model field — this is only enforced when full_clean() is
        explicitly called (Django does not run field validators on a
        plain .save()).
        """
        user = User(email="cleancheck@example.com", phone_number=invalid_phone)
        user.set_password("Pass1!")
        with pytest.raises(ValidationError) as exc_info:
            user.full_clean()
        assert "phone_number" in exc_info.value.message_dict

    @pytest.mark.parametrize(
        "invalid_phone",
        [
            "12345",
            "+15551234567",
            "02112345678",
        ],
    )
    def test_save_rejects_invalid_phone_formats(self, invalid_phone):
        """
        Tests the REAL enforcement point for the actual API path: plain
        .save() (which is what DRF serializers call, not full_clean())
        goes through User.save()'s normalization step, which raises
        ValueError for anything normalize_iranian_phone() can't parse —
        so invalid data never reaches the database via this path either,
        without relying on full_clean() ever being called.
        """
        with pytest.raises(ValueError):
            User.objects.create_user(
                email=f"savecheck-{invalid_phone}@example.com",
                password="Pass1!",
                phone_number=invalid_phone,
            )

    @pytest.mark.parametrize(
        "input_format",
        ["+989123456789", "00989123456789", "09123456789"],
    )
    def test_valid_phone_in_any_format_persists_as_same_canonical_value(
        self, input_format
    ):
        user = User.objects.create_user(
            email=f"canon-{input_format}@example.com",
            password="Pass1!",
            phone_number=input_format,
        )
        user.refresh_from_db()
        assert user.phone_number == "09123456789"

    def test_phone_number_none_is_left_alone_by_save(self):
        # save()'s normalization only runs `if self.phone_number:` — must
        # not choke on the common case of no phone number at all.
        user = User.objects.create_user(
            email="stillnophone@example.com", password="Pass1!"
        )
        assert user.phone_number is None

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


# ═══════════════════════════════════════════════════════════════════════════════
# OTPCode
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestOTPCodeModel:

    def test_can_be_created_with_all_required_fields(self):
        otp = OTPCode.objects.create(
            phone_number="09123456789",
            purpose=OTPCode.Purpose.LOGIN,
            code_hash="a" * 64,  # placeholder hash — real hashing is Task 2.1.2.2
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )
        assert otp.pk is not None
        assert otp.phone_number == "09123456789"
        assert otp.purpose == "login"
        assert otp.attempts == 0
        assert otp.is_used is False
        assert otp.created_at is not None

    def test_does_not_require_a_user(self):
        # OTP requests can happen before any User exists (first-time
        # phone registration) — this must not be a FK to User.
        otp = OTPCode.objects.create(
            phone_number="09121234567",
            purpose=OTPCode.Purpose.REGISTER,
            code_hash="b" * 64,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )
        assert not hasattr(otp, "user")
        assert OTPCode.objects.filter(pk=otp.pk).exists()

    def test_str_representation_active(self):
        otp = OTPCode.objects.create(
            phone_number="09129876543",
            purpose=OTPCode.Purpose.RESET,
            code_hash="c" * 64,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
            is_used=False,
        )
        assert str(otp) == "OTP for 09129876543 (reset) - active"

    def test_str_representation_used(self):
        otp = OTPCode.objects.create(
            phone_number="09129876543",
            purpose=OTPCode.Purpose.LOGIN,
            code_hash="d" * 64,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
            is_used=True,
        )
        assert str(otp) == "OTP for 09129876543 (login) - used"

    def test_purpose_choices(self):
        assert OTPCode.Purpose.LOGIN == "login"
        assert OTPCode.Purpose.REGISTER == "register"
        assert OTPCode.Purpose.RESET == "reset"
