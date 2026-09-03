from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.utils.text import slugify

from .validators import validate_ean13


class Category(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    image = models.ImageField(upload_to="categories/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    logo = models.ImageField(upload_to="brands/", null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Color(models.Model):
    name = models.CharField(max_length=100)
    hex_code = models.CharField(max_length=10)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.hex_code})"


class SkinType(models.TextChoices):
    OILY = "oily", "Oily"
    DRY = "dry", "Dry"
    COMBINATION = "combination", "Combination"
    SENSITIVE = "sensitive", "Sensitive"
    NORMAL = "normal", "Normal"
    ALL = "all", "All Skin Types"


class HairType(models.TextChoices):
    STRAIGHT = "straight", "Straight"
    WAVY = "wavy", "Wavy"
    CURLY = "curly", "Curly"
    COILY = "coily", "Coily"
    ALL = "all", "All Hair Types"


class ProductGender(models.TextChoices):
    UNISEX = "unisex", "Unisex"
    FEMALE = "female", "Female"
    MALE = "male", "Male"


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, unique=True, blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    # Raw INCI (International Nomenclature of Cosmetic Ingredients)
    # ingredients text — a long, comma-separated technical ingredient
    # list. Plain storable/displayable text only for now; a
    # structured, individually-searchable ingredient list with
    # allergen-flagging is a much bigger feature and explicitly out of
    # scope here. Not made searchable via ProductFilter/full-text
    # search in this task either — that's tracked separately under the
    # project's Search epic if/when ingredient-based search becomes a
    # requirement.
    ingredients = models.TextField(blank=True)
    # Separate fields on purpose (not one combined field): these are
    # semantically distinct and will likely be displayed in visually
    # distinct sections on the product detail page — usage_instructions
    # as routine informational content, warnings often styled with more
    # visual prominence/urgency (e.g. an icon or colored callout box).
    usage_instructions = models.TextField(blank=True)
    warnings = models.TextField(blank=True)
    # Free text rather than a curated ISO country-code choices list:
    # cosmetics on this platform are sourced from a very wide range of
    # countries, and a hardcoded choices list would need constant
    # maintenance as new brands/origins are added. A proper
    # ISO-3166-backed dropdown is a reasonable future enhancement but
    # is explicitly out of scope for this task.
    country_of_origin = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    stock = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    reviews_count = models.PositiveIntegerField(default=0)
    is_new = models.BooleanField(default=False)
    is_sale = models.BooleanField(default=False)
    # Skin-type suitability is a property of the product formulation
    # itself (e.g. "this serum is for oily skin"), not of a specific
    # shade/size — unlike price/stock, it does NOT vary per
    # ProductVariant, so it lives here on Product. blank=True with no
    # default on purpose: not every category (haircare, fragrance,
    # tools) has a meaningful skin type, and leaving it unset must be
    # valid rather than forcing an arbitrary "all" default onto
    # products where the concept doesn't apply.
    skin_type = models.CharField(
        max_length=20,
        choices=SkinType.choices,
        blank=True,
    )
    # Same rationale as skin_type: a property of the product
    # formulation (shampoo/conditioner/styling products), not of a
    # specific shade/size, so it lives on Product rather than
    # ProductVariant. blank=True with no default — most product
    # categories (skincare, fragrance, tools) have no meaningful hair
    # type, and leaving it unset must be valid.
    hair_type = models.CharField(
        max_length=20,
        choices=HairType.choices,
        blank=True,
    )
    # Unlike skin_type/hair_type, defaults to UNISEX rather than blank:
    # every product realistically has SOME applicable answer here (even
    # if it's "unisex"), and defaulting to the most inclusive option
    # avoids accidentally mis-filtering products that haven't been
    # explicitly tagged yet.
    gender = models.CharField(
        max_length=10,
        choices=ProductGender.choices,
        default=ProductGender.UNISEX,
    )
    # Nullable (not just blank) since this is numeric: 0 would be
    # ambiguous between "SPF 0 / no protection" and "not specified",
    # so None genuinely means "not applicable" (most makeup remover,
    # most haircare) while blank/0 aren't overloaded to mean that too.
    # MaxValueValidator(100) is a generous sanity bound, not an attempt
    # to encode exact real-world SPF labeling regulations — real
    # products realistically top out around SPF 50-100.
    spf = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(100)]
    )
    thumbnail = models.ImageField(
        upload_to="products/thumbnails/", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def discount_percent(self):
        if self.original_price and self.original_price > self.price:
            return round((1 - self.price / self.original_price) * 100)
        return 0


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="products/images/")

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductColor(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="colors"
    )
    color = models.ForeignKey(
        Color, on_delete=models.CASCADE, related_name="product_colors"
    )

    class Meta:
        unique_together = ("product", "color")

    def __str__(self):
        return f"{self.product.name} — {self.color.name}"


class ProductVariant(models.Model):
    # NOTE on when `barcode`'s validate_ean13 validator actually fires:
    # like every Django field validator, it does NOT run on a bare
    # `.save()`/`.objects.create()` call — Django only runs field
    # validators as part of `full_clean()`. That means:
    #   - Django admin (ProductVariantAdmin / ProductVariantInline,
    #     Task 3.1.1.6) DOES enforce it, since ModelForm-based admin
    #     forms call full_clean() during validation — malformed
    #     barcodes typed by hand there will be correctly rejected.
    #   - A DRF ModelSerializer for ProductVariant (none exists yet in
    #     this codebase as of this task — cart/serializers.py only
    #     reads/validates a variant_id, it doesn't create/update
    #     ProductVariant rows) WOULD also enforce it automatically,
    #     since DRF auto-generates field-level validators from the
    #     model field's `validators=[...]` and runs them in
    #     `is_valid()`. Any future variant-creation/bulk-import API
    #     serializer just needs to be a ModelSerializer (or otherwise
    #     include this validator) for the same protection to apply.
    #   - Code paths that call `.save()` directly without going through
    #     a ModelForm/DRF serializer/explicit `full_clean()` (e.g. the
    #     legacy-data migration in Task 3.1.1.2, or test factories) do
    #     NOT get this validation for free — that's expected/desired,
    #     since blank barcodes and legacy placeholder data shouldn't be
    #     forced through EAN-13 validation retroactively.
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    sku = models.CharField(max_length=64, unique=True, blank=True)
    barcode = models.CharField(
        max_length=20,
        blank=True,
        validators=[validate_ean13],
        help_text="EAN-13 barcode (13 digits with a valid check digit). Optional.",
    )
    color = models.ForeignKey(
        Color,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="variants",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    # Unlike skin_type/hair_type/spf (formulation-level, on Product),
    # volume/weight genuinely differ per purchasable unit — a serum
    # sold in 30ml and 50ml sizes needs each size tracked as its own
    # variant with its own volume/price/stock. Both nullable/optional:
    # a variant is typically measured in EITHER volume (liquids —
    # serums, toners, perfume) OR weight (solids/powders — pressed
    # powder, lipstick, some balms), not both, and some variants (e.g.
    # a color-only eyeshadow-palette variant with no size variation)
    # may need neither. Deliberately no "exactly one must be set"
    # validation — that would break perfectly valid variants that have
    # neither dimension recorded.
    volume_ml = models.PositiveIntegerField(null=True, blank=True)
    weight_g = models.PositiveIntegerField(null=True, blank=True)
    # Batch-specific, not formulation-specific: a single Product can
    # have multiple variants (and, in a fuller implementation, multiple
    # batches per variant) with different expiration dates — matching
    # the volume_ml/weight_g placement decision (Task 3.2.1.4), this
    # lives on ProductVariant, not Product. Both nullable/optional
    # since not every product category has meaningful expiration data,
    # though most cosmetics/skincare will. See clean() below for the
    # expiration-after-manufacture validation.
    manufacture_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    # Standard cosmetics industry practice for recall management and
    # quality control, pairing naturally with the dates above. Plain
    # free text — real batch/lot number formats vary significantly by
    # manufacturer, so unlike sku/barcode (which have this platform's
    # own generation/checksum logic), no format validation is imposed
    # here.
    batch_number = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def clean(self):
        super().clean()
        # Skip the comparison entirely if either date is unset — only
        # meaningful to compare when both are actually present.
        if (
            self.expiration_date is not None
            and self.manufacture_date is not None
            and self.expiration_date <= self.manufacture_date
        ):
            raise ValidationError(
                {"expiration_date": "Expiration date must be after manufacture date."}
            )

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = self._generate_sku()
        super().save(*args, **kwargs)

    def _generate_sku(self) -> str:
        category_code = (
            self.product.category.name[:3].upper() if self.product.category else "GEN"
        )
        brand_code = (
            self.product.brand.name[:3].upper() if self.product.brand else "UNK"
        )
        base = f"{category_code}-{brand_code}-{self.product.id}"
        sku = base
        counter = 1
        while ProductVariant.objects.filter(sku=sku).exclude(pk=self.pk).exists():
            sku = f"{base}-{counter}"
            counter += 1
        return sku

    def __str__(self):
        return f"{self.product.name} — {self.sku or 'unsaved'}"


class Review(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )
    is_verified_purchase = models.BooleanField(default=False)
    name = models.CharField(max_length=200)
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    headline = models.CharField(max_length=300, blank=True)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("product", "user")
        # NOTE on `user=None` rows: this project's DB backend is
        # PostgreSQL (see core/settings/base.py), where a UNIQUE
        # constraint/index treats NULL as distinct from every other NULL
        # (standard SQL semantics — NULL is never considered equal to
        # NULL, including for uniqueness checks). That means this
        # constraint does NOT collapse multiple historical reviews with
        # user=None on the same product into a conflict; only rows with
        # the same *non-null* (product, user) pair are rejected. This is
        # exactly the desired behavior — pre-auth anonymous reviews
        # (Task 1.3.1.1) are left alone, and only authenticated users are
        # limited to one review per product. If this project ever moves
        # to a DB backend with different NULL-handling in unique
        # constraints (e.g. some older MySQL configurations), this
        # assumption should be re-verified.

    def __str__(self):
        return f"{self.name} — {self.product.name} ({self.rating}★)"
