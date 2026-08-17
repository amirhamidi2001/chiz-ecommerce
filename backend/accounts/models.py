from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from .validators import iranian_phone_regex, normalize_iranian_phone


class UserType(models.IntegerChoices):
    CUSTOMER = 1, _("customer")
    ADMIN = 2, _("admin")
    SUPERUSER = 3, _("superuser")


class UserManager(BaseUserManager):
    def create_user(self, email=None, password=None, **extra_fields):
        # email is optional here specifically to support phone-only OTP
        # accounts (Task 2.3.1.2): a customer who registers purely via
        # phone/OTP has no email at all. USERNAME_FIELD stays "email"
        # (unchanged — email remains the identifier for the existing
        # email+password flow and for Django admin), but that only
        # matters for accounts that actually need to type an email
        # somewhere to log in (staff/admin). A phone-only *customer*
        # account never needs to authenticate via the admin login form,
        # so a null email is fine for them; email must remain unique at
        # the DB level (see the `unique=True, null=True` field below —
        # same nullable+unique pattern already used for phone_number in
        # Task 2.1.1.1: Postgres treats each NULL as distinct, so
        # multiple email-less accounts don't collide with each other).
        #
        # Guard against the one combination that WOULD be broken by a
        # null email: a staff/superuser account can't log into Django
        # admin without a value in its USERNAME_FIELD.
        if not email and (
            extra_fields.get("is_staff") or extra_fields.get("is_superuser")
        ):
            raise ValueError(_("Staff/superuser accounts must have an email."))

        if email:
            email = self.normalize_email(email).lower()
        else:
            email = None

        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("type", UserType.SUPERUSER)
        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    # Nullable + unique: mirrors the exact same pattern already used for
    # phone_number (Task 2.1.1.1) to support phone-only OTP accounts
    # (Task 2.3.1.2) that have no email at all. USERNAME_FIELD stays
    # "email" — see UserManager.create_user() above for the staff/admin
    # implications of this being nullable.
    email = models.EmailField(_("email address"), unique=True, null=True, blank=True)
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        validators=[iranian_phone_regex],
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    type = models.IntegerField(choices=UserType.choices, default=UserType.CUSTOMER)

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        # Normalize before persisting so a single canonical format
        # ("09XXXXXXXXX") is always what's stored, regardless of which
        # of the three accepted input formats the caller supplied. This
        # runs on every plain .save() call (including the path DRF
        # serializers use), unlike validators=[...] above which are
        # only enforced when full_clean() is explicitly called.
        if self.phone_number:
            self.phone_number = normalize_iranian_phone(self.phone_number)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email or self.phone_number or f"User #{self.pk}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    # blank=True (not blank=False): an OTP-created user (Task 2.3.1.2) has
    # no name data at all yet, so the auto-created Profile from the
    # create_profile signal below must be allowed to hold empty strings
    # here without full_clean() raising later (e.g. an admin form).
    # This is a Django-level validation-only relaxation — blank=False
    # never enforced a DB NOT-NULL-with-content constraint (it's not
    # checked by plain .save(), only by full_clean()/ModelForms), so
    # this needs no destructive data migration; existing rows are
    # already compatible. The frontend (Task 2.3.2) is expected to
    # prompt new OTP users to fill these in — see OTPVerifyView's
    # is_new_user response flag.
    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(
        max_length=12,
        blank=True,
        null=True,
    )
    image = models.ImageField(
        upload_to="profiles/", default="profiles/default.webp", blank=True
    )

    order_updates = models.BooleanField(default=True, verbose_name="Order Updates")
    promotions = models.BooleanField(default=False, verbose_name="Promotions")
    newsletter = models.BooleanField(default=True, verbose_name="Newsletter")

    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)

    def get_fullname(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return _("new user")

    def __str__(self):
        identifier = (
            self.user.email or self.user.phone_number or f"user #{self.user_id}"
        )
        return f"{self.get_fullname()} - {identifier}"


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


class OTPCode(models.Model):
    """
    A one-time-code request record for phone-based login/registration/
    password reset. Schema only in this task — code generation, hashing,
    and verification logic land in Tasks 2.1.2.2 and 2.1.2.3.

    Deliberately NOT a FK to User: an OTP request can happen before any
    User exists yet (first-time registration via phone), so this model
    must be able to stand alone.
    """

    class Purpose(models.TextChoices):
        LOGIN = "login", "Login"
        REGISTER = "register", "Register"
        RESET = "reset", "Password Reset"

    phone_number = models.CharField(max_length=15, db_index=True)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    # NEVER store the raw 6-digit code — only a hash of it (Task 2.1.2.2).
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["phone_number", "purpose", "is_used"]),
        ]

    def __str__(self):
        status = "used" if self.is_used else "active"
        return f"OTP for {self.phone_number} ({self.purpose}) - {status}"
