from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Percentage"
        FIXED = "fixed", "Fixed Amount"

    code = models.CharField(max_length=32, unique=True, db_index=True)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices)
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=(
            "Percentage (0-100) if discount_type=percent, or a fixed "
            "currency amount if discount_type=fixed."
        ),
    )
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Cart subtotal must be at least this amount for the coupon to apply.",
    )
    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Total number of times this coupon can be redeemed across all "
            "users. Leave blank for unlimited."
        ),
    )
    uses_per_user = models.PositiveIntegerField(
        default=1,
        help_text="Maximum number of times a single user can redeem this coupon.",
    )
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    # Optional scope restriction (Task 9.1.1.7). With neither set, the coupon
    # applies cart-wide; with either/both set, only items matching ANY of
    # them are eligible (category OR product).
    categories = models.ManyToManyField(
        "shop.Category",
        blank=True,
        help_text=(
            "If set, this coupon only applies to items in these categories. "
            "Leave empty to apply to all categories. Matching is exact: a "
            "product in a sub-category does NOT match its parent category, "
            "so select the sub-categories you want as well."
        ),
    )
    products = models.ManyToManyField(
        "shop.Product",
        blank=True,
        help_text=(
            "If set, this coupon only applies to these specific products. "
            "Leave empty (with no category restriction either) to apply "
            "cart-wide."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def clean(self):
        super().clean()
        # Normalize here as well as in save(): full_clean() runs clean()
        # BEFORE validate_unique(), so without this an admin-form entry like
        # "summer20" would pass the uniqueness check against an existing
        # "SUMMER20" and then blow up with an IntegrityError in save().
        if self.code:
            self.code = self.code.upper().strip()
        # None-guards: full_clean() still calls clean() when a required field
        # failed clean_fields() and is left unset, so comparing None values
        # here would raise TypeError instead of surfacing the field error.
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until <= self.valid_from
        ):
            raise ValidationError({"valid_until": "Must be after valid_from."})
        if self.value is not None:
            if self.discount_type == self.DiscountType.PERCENT and not (
                0 < self.value <= 100
            ):
                raise ValidationError(
                    {"value": "Percentage discount must be between 0 and 100."}
                )
            if self.discount_type == self.DiscountType.FIXED and self.value <= 0:
                raise ValidationError(
                    {"value": "Fixed discount amount must be greater than 0."}
                )

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)


class CouponRedemption(models.Model):
    """
    Record of a coupon being applied to a cart / used on an order. This is
    what makes Coupon.max_uses and Coupon.uses_per_user enforceable, and
    what lets a redemption be traced to (and reversed with) its order.

    DESIGN DECISION — authenticated-only redemption (Task 9.1.1.3):
    coupons may only be applied by authenticated users. The coupon-
    application endpoint (Task 9.1.1.6) must reject anonymous/guest carts.
    Reason: uses_per_user is meaningless without a stable identity — a
    guest could trivially bypass it with another browser or session — and
    we'd rather not ship a limit that is bypassable by design. The
    alternative (guests allowed, only the global max_uses cap applying to
    them) was rejected for that reason.

    Consequence for the schema: because redemption requires a logged-in
    user, `user` is expected to be set on every redemption created through
    the application flow. It is nullable ONLY because of on_delete=SET_NULL
    (a deleted account must not delete the usage history that max_uses
    counting and reporting depend on) — NOT to represent guests. The
    "guest" branch in __str__ therefore only ever shows for such orphaned
    rows.

    LIFECYCLE: `order` is null while the coupon is merely applied to a
    cart (checkout not yet complete) and is set once the order is created.
    A OneToOneField permits any number of NULLs, so many in-progress
    redemptions can coexist, but a given order can carry at most one.
    """

    coupon = models.ForeignKey(
        Coupon, on_delete=models.CASCADE, related_name="redemptions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupon_redemptions",
    )
    order = models.OneToOneField(
        "order.Order",
        on_delete=models.CASCADE,
        related_name="coupon_redemption",
        null=True,
        blank=True,
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=(
            "Actual currency amount discounted by this redemption "
            "(frozen at redemption time)."
        ),
    )
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-redeemed_at"]

    def __str__(self):
        return f"{self.coupon.code} redeemed by {self.user or 'guest'}"


class FlashSale(models.Model):
    """
    A time-boxed, automatically-applied percentage discount on specific
    products. Unlike a Coupon there is no code to enter: while the sale is
    active the discounted price is simply what customers see.

    This model only records WHAT is on sale, for how much, and WHEN. It does
    not itself change any price — resolving a product's effective price from
    its active sale(s) is separate work. Note nothing here prevents two
    active sales covering the same product, so that resolution step must
    define which discount wins.
    """

    name = models.CharField(max_length=200)
    products = models.ManyToManyField("shop.Product", related_name="flash_sales")
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal("100")),
        ],
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        # None-guards: full_clean() still calls clean() when a required
        # date failed clean_fields() and is unset; comparing None would
        # raise TypeError instead of surfacing that field's error.
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValidationError({"ends_at": "Must be after starts_at."})

    @property
    def is_currently_active(self):
        """True only while is_active is set AND now is within [starts_at, ends_at]."""
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at
