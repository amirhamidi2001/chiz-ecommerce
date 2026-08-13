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
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("The Email must be set"))
        email = self.normalize_email(email).lower()
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
    email = models.EmailField(_("email address"), unique=True)
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
        return self.email


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    first_name = models.CharField(max_length=255, blank=False)
    last_name = models.CharField(max_length=255, blank=False)
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
        return f"{self.get_fullname()} - {self.user.email}"


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
