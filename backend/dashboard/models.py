from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class IranProvince(models.TextChoices):
    """
    The 31 official provinces (ostan) of Iran. Verified against
    Wikipedia's "Provinces of Iran" article (sourced in turn from
    Iran's Statistical Centre / statoids.com) rather than assumed from
    general knowledge, since an incomplete or misspelled list directly
    affects real customers' ability to enter a valid shipping address.
    """

    ALBORZ = "alborz", "Alborz"
    ARDABIL = "ardabil", "Ardabil"
    BUSHEHR = "bushehr", "Bushehr"
    CHAHARMAHAL_AND_BAKHTIARI = (
        "chaharmahal_and_bakhtiari",
        "Chaharmahal and Bakhtiari",
    )
    EAST_AZERBAIJAN = "east_azerbaijan", "East Azerbaijan"
    FARS = "fars", "Fars"
    GILAN = "gilan", "Gilan"
    GOLESTAN = "golestan", "Golestan"
    HAMADAN = "hamadan", "Hamadan"
    HORMOZGAN = "hormozgan", "Hormozgan"
    ILAM = "ilam", "Ilam"
    ISFAHAN = "isfahan", "Isfahan"
    KERMAN = "kerman", "Kerman"
    KERMANSHAH = "kermanshah", "Kermanshah"
    KHUZESTAN = "khuzestan", "Khuzestan"
    KOHGILUYEH_AND_BOYER_AHMAD = (
        "kohgiluyeh_and_boyer_ahmad",
        "Kohgiluyeh and Boyer-Ahmad",
    )
    KURDISTAN = "kurdistan", "Kurdistan"
    LORESTAN = "lorestan", "Lorestan"
    MARKAZI = "markazi", "Markazi"
    MAZANDARAN = "mazandaran", "Mazandaran"
    NORTH_KHORASAN = "north_khorasan", "North Khorasan"
    QAZVIN = "qazvin", "Qazvin"
    QOM = "qom", "Qom"
    KHORASAN_RAZAVI = "khorasan_razavi", "Khorasan Razavi"
    SEMNAN = "semnan", "Semnan"
    SISTAN_AND_BALUCHESTAN = "sistan_and_baluchestan", "Sistan and Baluchestan"
    SOUTH_KHORASAN = "south_khorasan", "South Khorasan"
    TEHRAN = "tehran", "Tehran"
    WEST_AZERBAIJAN = "west_azerbaijan", "West Azerbaijan"
    YAZD = "yazd", "Yazd"
    ZANJAN = "zanjan", "Zanjan"


iran_postal_code_validator = RegexValidator(
    regex=r"^\d{10}$", message="Enter a valid 10-digit Iranian postal code."
)


class Address(models.Model):
    """Saved shipping / billing address for a user."""

    class Label(models.TextChoices):
        HOME = "home", "Home"
        OFFICE = "office", "Office"
        OTHER = "other", "Other"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    label = models.CharField(max_length=20, choices=Label.choices, default=Label.HOME)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)
    address_line = models.CharField(max_length=255)
    apartment = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=30, choices=IranProvince.choices, blank=True)
    postal_code = models.CharField(
        max_length=10, blank=True, validators=[iran_postal_code_validator]
    )
    # Kept as a plain CharField (not choices) deliberately: this platform
    # targets Iran exclusively (hence the "IR" default), but hard-coding
    # a single-value choices field would foreclose international
    # shipping if the business ever expands — the default alone makes
    # Iran the practical norm without that restriction.
    country = models.CharField(max_length=10, default="IR")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name = "Address"
        verbose_name_plural = "Addresses"

    def __str__(self):
        return f"{self.label} — {self.user.email}"

    def save(self, *args, **kwargs):
        # Ensure only one default address per user
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class Wishlist(models.Model):
    """A single saved product in a user's wishlist."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    product = models.ForeignKey(
        "shop.Product",
        on_delete=models.CASCADE,
        related_name="wishlisted_by",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")
        ordering = ["-added_at"]
        verbose_name = "Wishlist Item"
        verbose_name_plural = "Wishlist Items"

    def __str__(self):
        return f"{self.user.email} — {self.product.name}"
