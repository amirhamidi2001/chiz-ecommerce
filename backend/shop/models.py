from decimal import Decimal
from typing import NamedTuple

from core.fields import RialField, whole_toman_constraint
from core.money import percent_of
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .search import SEARCH_VECTOR_SOURCE_FIELDS, refresh_product_search_vectors
from .text_utils import normalize_persian_text
from .validators import validate_ean13


def discounted_price(price: int, sale) -> int:
    """`price` (Rial) reduced by `sale.discount_percent`, rounded ONCE to a whole
    Toman (ADR 0001 invariant I-3)."""
    return percent_of(price, Decimal("100") - sale.discount_percent)


class FlashSaleCardPricing(NamedTuple):
    """What a product CARD shows for a product that is currently on sale."""

    sale: object  # promotions.FlashSale
    original_price: int  # lowest regular price (Rial) among the product's variants
    price: int  # that price with the sale applied ("starting at")
    price_varies: bool  # variants differ in price, so "from" is the honest label


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
        verbose_name_plural = _("Categories")
        ordering = ["name"]

    def save(self, *args, **kwargs):
        # Names feed Product.search_vector, so they are canonicalised like
        # product text (see shop/text_utils.py).
        self.name = normalize_persian_text(self.name)
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
        # Names feed Product.search_vector, so they are canonicalised like
        # product text (see shop/text_utils.py).
        self.name = normalize_persian_text(self.name)
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
    OILY = "oily", _("Oily")
    DRY = "dry", _("Dry")
    COMBINATION = "combination", _("Combination")
    SENSITIVE = "sensitive", _("Sensitive")
    NORMAL = "normal", _("Normal")
    ALL = "all", _("All Skin Types")


class HairType(models.TextChoices):
    STRAIGHT = "straight", _("Straight")
    WAVY = "wavy", _("Wavy")
    CURLY = "curly", _("Curly")
    COILY = "coily", _("Coily")
    ALL = "all", _("All Hair Types")


class ProductGender(models.TextChoices):
    UNISEX = "unisex", _("Unisex")
    FEMALE = "female", _("Female")
    MALE = "male", _("Male")


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
    # Iran Food & Drug Administration (IRC) registration code, required
    # for legal retail sale of many cosmetics in Iran. This is a
    # compliance-relevant field, not just display metadata — but format
    # validation is deliberately left out of scope here: the backlog
    # doesn't specify a format, and IRC code formats aren't something
    # to guess at without authoritative documentation. Plain optional
    # text for now; this lays groundwork for a future admin
    # verification workflow (Task 3.2.1.13) rather than implementing it.
    irc_regulatory_code = models.CharField(max_length=50, blank=True)
    # Whether a staff member has actually checked/confirmed the
    # irc_regulatory_code above is valid — distinct from merely having
    # something typed into the code field. See clean() below for the
    # optional, settings-driven publish-guard this enables.
    regulatory_verified = models.BooleanField(default=False)
    price = RialField()
    original_price = RialField(null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    reviews_count = models.PositiveIntegerField(default=0)
    is_new = models.BooleanField(default=False)
    is_sale = models.BooleanField(default=False)
    # Cruelty-free/vegan/organic certification badges — all default
    # False (unverified/unclaimed by default). A product should only
    # display one of these badges once genuinely confirmed by an
    # admin, not opt-in-by-default, since a false-positive claim here
    # is a meaningfully worse outcome than a missing badge.
    is_cruelty_free = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    is_organic = models.BooleanField(default=False)
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
    # Weighted Postgres full-text search vector (see shop/search.py for how
    # it is built and why the "simple" config). Maintained by save() and by
    # the Brand/Category rename signals — NOT automatically by Postgres, so
    # queryset.update()/bulk_create() on the text fields leave it stale until
    # `manage.py rebuild_search_vectors` is run. editable=False keeps it out
    # of admin forms and ModelSerializer input.
    search_vector = SearchVectorField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            GinIndex(fields=["search_vector"], name="product_search_vector_idx"),
        ]
        constraints = [
            whole_toman_constraint("price"),
            whole_toman_constraint("original_price"),
        ]

    def clean(self):
        super().clean()
        # OFF by default (REQUIRE_REGULATORY_VERIFICATION defaults to
        # False in settings). When enabled, this only blocks products
        # that HAVE an irc_regulatory_code entered but haven't been
        # verified yet — it deliberately does NOT make IRC codes
        # mandatory for every product. Whether codes should be
        # mandatory for all products (vs. only claimed-but-unverified
        # ones) is a separate business decision the backlog didn't ask
        # for here ("optional (configurable)").
        if (
            settings.REQUIRE_REGULATORY_VERIFICATION
            and self.irc_regulatory_code
            and not self.regulatory_verified
        ):
            raise ValidationError(
                {
                    "regulatory_verified": _(
                        "This product has an IRC regulatory code entered but "
                        "has not been verified by a staff member yet."
                    )
                }
            )

    def save(self, *args, **kwargs):
        # Canonicalise Persian/Arabic character variants and strip zero-width
        # characters BEFORE slug generation and the search_vector refresh, so
        # stored text and normalised search queries always agree.
        self.name = normalize_persian_text(self.name)
        self.short_description = normalize_persian_text(self.short_description)
        self.description = normalize_persian_text(self.description)
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        # One transaction for the row write AND the vector refresh: a full
        # save() writes the instance's (stale/NULL) search_vector first, and
        # without this a concurrent search could briefly miss the product.
        with transaction.atomic():
            super().save(*args, **kwargs)
            # Skip the extra UPDATE for saves that provably can't change the
            # vector, e.g. refresh_product_review_stats's
            # save(update_fields=["rating", "reviews_count"]).
            update_fields = kwargs.get("update_fields")
            if update_fields is None or SEARCH_VECTOR_SOURCE_FIELDS.intersection(
                update_fields
            ):
                refresh_product_search_vectors(type(self).objects.filter(pk=self.pk))

    def __str__(self):
        return self.name

    @property
    def active_flash_sale(self):
        """
        The FlashSale currently discounting this product, or None.

        A sale is current when is_active is set and now is within
        [starts_at, ends_at]. If several current sales cover the same
        product (an admin configuration edge case), the one that STARTED
        most recently wins; if they started at the same instant, the most
        recently created one wins. That is deliberately simple — it is NOT
        "highest discount wins".

        Resolves from a prefetched `flash_sales` when present (the product
        views prefetch the current ones), costing no query; otherwise issues
        one query. Both paths apply the same rule.
        """
        now = timezone.now()
        if "flash_sales" in getattr(self, "_prefetched_objects_cache", {}):
            current = [
                sale
                for sale in self.flash_sales.all()
                if sale.is_active and sale.starts_at <= now <= sale.ends_at
            ]
            return max(
                current, key=lambda sale: (sale.starts_at, sale.pk), default=None
            )
        return (
            self.flash_sales.filter(
                is_active=True, starts_at__lte=now, ends_at__gte=now
            )
            .order_by("-starts_at", "-pk")
            .first()
        )

    def _active_variant_prices(self):
        """
        Regular (pre-sale) prices of this product's ACTIVE variants.

        The single definition of "which variants count" for any
        product-level price: shared by flash_sale_card_pricing() and
        lowest_active_price so a product's "starting at" figure can't
        drift between the storefront card and anything else built on it.
        Uses prefetched `variants` when available (no extra query).
        """
        return [v.price for v in self.variants.all() if v.is_active]

    @property
    def lowest_active_price(self):
        """
        The product's "starting at" price: the cheapest ACTIVE variant's
        regular price, or None if it has no active variant.

        This is the same figure product cards show (see
        flash_sale_card_pricing) and is the basis for price-drop
        detection (ProductPriceSnapshot / handle_variant_price_change).

        Deliberately NOT filtered on stock: cards show out-of-stock
        variants' prices too, and — more importantly — a stock filter
        would make this value move whenever the cheapest variant sells
        out or is restocked, which would read as a price "drop" on every
        restock. Regular price only: flash-sale discounts are
        time-windowed and fire no variant save, so they are not part of
        this value.
        """
        return min(self._active_variant_prices(), default=None)

    def flash_sale_card_pricing(self):
        """
        Product-card pricing for a product on sale, or None if it isn't.

        Real prices live on variants, and a card can't show one badge per
        shade/size, so a card shows "starting at": the cheapest active
        variant's price, with the sale applied, against that same price
        struck through. (Falls back to `price` if there are no active
        variants.) Uses prefetched `variants` when available.
        """
        sale = self.active_flash_sale
        if sale is None:
            return None
        prices = self._active_variant_prices() or [self.price]
        lowest, highest = min(prices), max(prices)
        return FlashSaleCardPricing(
            sale=sale,
            original_price=lowest,
            price=discounted_price(lowest, sale),
            price_varies=lowest != highest,
        )

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
        help_text=_("EAN-13 barcode (13 digits with a valid check digit). Optional."),
    )
    color = models.ForeignKey(
        Color,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="variants",
    )
    price = RialField()
    original_price = RialField(null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
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
        constraints = [
            whole_toman_constraint("price"),
            whole_toman_constraint("original_price"),
        ]

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
                {
                    "expiration_date": _(
                        "Expiration date must be after manufacture date."
                    )
                }
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

    @property
    def active_flash_sale(self):
        """The FlashSale currently discounting this variant's product, or None.
        See Product.active_flash_sale for the rules (incl. overlapping sales)."""
        return self.product.active_flash_sale

    @property
    def effective_price(self):
        """`price` with any current flash-sale discount applied, to 2 places."""
        sale = self.active_flash_sale
        if sale is None:
            return self.price
        return discounted_price(self.price, sale)

    @property
    def is_low_stock(self) -> bool:
        return 0 < self.stock <= self.low_stock_threshold

    # Flat per-item fallback used when a variant has neither weight_g nor
    # volume_ml set. Deliberately conservative/approximate — real
    # packaging weight data is inherently imperfect at this stage of the
    # project (Task 7.1.1.4); this is an explicitly-flagged simplification
    # rather than a silent inaccuracy, and is expected to shrink in
    # importance over time as more variants get real weight_g data.
    DEFAULT_ESTIMATED_WEIGHT_G = 100

    # volume_ml -> weight_g approximation for liquid products that only
    # have volume recorded. Roughly 1 gram per ml is a reasonable
    # approximation for water-based cosmetic liquids (serums, toners),
    # though it will overshoot for genuinely dense liquids and undershoot
    # for less dense ones — again, an explicit approximation, not a
    # precise conversion.
    ML_TO_GRAMS_APPROXIMATION = 1

    def weight_g_or_estimate(self) -> int:
        """
        Best-effort shippable weight in grams for this variant, used by
        the shipping-rate lookup (ShippingRate.find_rate) to compute
        total cart weight. Precedence:

          1. weight_g, if set — the real, authoritative value.
          2. volume_ml, if set and weight_g isn't — approximated at
             ML_TO_GRAMS_APPROXIMATION grams per ml (see that constant's
             docstring for the caveat).
          3. DEFAULT_ESTIMATED_WEIGHT_G — a flat, conservative per-item
             fallback when neither dimension is recorded at all.
        """
        if self.weight_g is not None:
            return self.weight_g
        if self.volume_ml is not None:
            return self.volume_ml * self.ML_TO_GRAMS_APPROXIMATION
        return self.DEFAULT_ESTIMATED_WEIGHT_G


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        SALE = "sale", _("Sale")
        CANCELLATION = "cancellation", _("Order Cancellation")
        MANUAL = "manual", _("Manual Adjustment")
        RESTOCK = "restock", _("Restock")
        EXPIRY_SWEEP = "expiry_sweep", _("Expiry Deactivation")

    variant = models.ForeignKey(
        "shop.ProductVariant", on_delete=models.CASCADE, related_name="stock_movements"
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    quantity_delta = models.IntegerField(
        help_text=_("Positive for increases, negative for decreases.")
    )
    stock_after = models.PositiveIntegerField(
        help_text=_("Variant's stock value immediately after this movement.")
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
        help_text=_(
            "Admin user who triggered this (manual adjustments only); null for system-triggered movements."
        ),
    )
    note = models.CharField(max_length=255, blank=True)
    related_order = models.ForeignKey(
        "order.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["variant", "-created_at"])]

    def __str__(self):
        sign = "+" if self.quantity_delta >= 0 else ""
        return f"{self.variant} {sign}{self.quantity_delta} ({self.reason})"


class StockAlertSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stock_alert_subscriptions",
    )
    variant = models.ForeignKey(
        "shop.ProductVariant",
        on_delete=models.CASCADE,
        related_name="alert_subscriptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "variant")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — alert for {self.variant}"


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
    # Moderation gate: only approved reviews are shown publicly and counted
    # in Product.rating / Product.reviews_count. See ProductReviewCreateView
    # (auto-approval for verified purchases) and the admin moderation queue.
    is_approved = models.BooleanField(default=False)
    name = models.CharField(max_length=200)
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    headline = models.CharField(max_length=300, blank=True)
    comment = models.TextField()
    # Official store reply: a single response per review (deliberately not a
    # thread). Written by admins only via the dashboard; `store_response_at` is
    # set server-side whenever the response text changes.
    store_response = models.TextField(blank=True)
    store_response_at = models.DateTimeField(null=True, blank=True)
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


class ReviewImage(models.Model):
    """A photo attached to a review (verified purchasers only)."""

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="reviews/images/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Stable order for display: the order the customer uploaded them.
        ordering = ["id"]

    def __str__(self):
        return f"Image for review #{self.review_id}"


class ReviewReport(models.Model):
    """A customer's flag on an (already published) review."""

    class Reason(models.TextChoices):
        SPAM = "spam", _("Spam or fake")
        OFFENSIVE = "offensive", _("Offensive content")
        IRRELEVANT = "irrelevant", _("Not relevant to the product")
        OTHER = "other", _("Other")

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="reports")
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="review_reports",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        # One report per user per review. As with Review's (product, user)
        # constraint, PostgreSQL treats NULLs as distinct, so reports whose
        # reporter account was later deleted (SET_NULL) don't collide.
        unique_together = ("review", "reported_by")

    def __str__(self):
        return f"Report on review #{self.review_id} — {self.reason}"


class ProductPriceSnapshot(models.Model):
    """
    A product's lowest_active_price ("starting at") at a point in time.

    The newest snapshot is the baseline the next variant change is compared
    against to tell a genuine price DROP from an increase or an unrelated
    change — a drop can't be detected without knowing the previous price.
    A row is written whenever the product's lowest active price changes
    (see shop/signals.py handle_variant_price_change), not on every save.
    """

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="price_snapshots"
    )
    price = RialField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # "-id" breaks ties between snapshots written within the same
        # clock tick, so .first() is always genuinely the latest.
        ordering = ["-recorded_at", "-id"]
        constraints = [whole_toman_constraint("price")]

    def __str__(self):
        return f"{self.product_id} @ {self.price} ({self.recorded_at:%Y-%m-%d %H:%M})"


class SearchQueryLog(models.Model):
    """
    One row per customer product search (ProductListView ?search=), for
    merchandising analytics: popular terms, and zero-result terms that point
    to a catalog gap or a search-quality bug.

    Written asynchronously by shop.tasks.log_search_query. `query` holds the
    NORMALISED term (Persian/Arabic variants canonicalised, whitespace
    collapsed, lower-cased, truncated to 255) so spelling variants of the same
    search aggregate together. `result_count` is the total number of matches
    for that request (i.e. after any other filters the customer applied).
    """

    query = models.CharField(max_length=255)
    result_count = models.PositiveIntegerField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="search_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"'{self.query}' ({self.result_count} results)"
