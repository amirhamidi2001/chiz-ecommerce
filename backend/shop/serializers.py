from rest_framework import serializers

from .models import (
    Brand,
    Category,
    Color,
    Product,
    ProductColor,
    ProductImage,
    ProductVariant,
    Review,
    StockAlertSubscription,
)


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent", "image", "children", "created_at")

    def get_children(self, obj):
        children = obj.children.all()
        return CategorySerializer(children, many=True, context=self.context).data


class CategoryMinimalSerializer(serializers.ModelSerializer):
    """Lightweight serializer used inside product representations."""

    class Meta:
        model = Category
        fields = ("id", "name", "slug")


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("id", "name", "slug", "logo")


class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = ("id", "name", "hex_code")


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image")


class ProductColorSerializer(serializers.ModelSerializer):
    color = ColorSerializer(read_only=True)

    class Meta:
        model = ProductColor
        fields = ("id", "color")


def _money(value):
    """Format like every other DecimalField in the API (honours DRF settings)."""
    return serializers.DecimalField(max_digits=10, decimal_places=2).to_representation(
        value
    )


class ProductVariantSerializer(serializers.ModelSerializer):
    color = ColorSerializer(read_only=True)
    # `price` / `original_price` stay the plain stored values; `effective_price`
    # is `price` with any current flash-sale discount applied (equal to
    # `price` when there is none). Flash-sale resolution lives on the model
    # (ProductVariant.active_flash_sale).
    effective_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    is_on_flash_sale = serializers.SerializerMethodField()
    # Lets the frontend render a countdown without a second request.
    flash_sale_ends_at = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "sku",
            "barcode",
            "color",
            "price",
            "original_price",
            "effective_price",
            "is_on_flash_sale",
            "flash_sale_ends_at",
            "stock",
            "volume_ml",
            "weight_g",
            "manufacture_date",
            "expiration_date",
            "batch_number",
            "is_active",
        )

    def get_is_on_flash_sale(self, obj):
        return obj.active_flash_sale is not None

    def get_flash_sale_ends_at(self, obj):
        sale = obj.active_flash_sale
        if sale is None:
            return None
        # Same ISO-8601 formatting as every other datetime in the API.
        return serializers.DateTimeField().to_representation(sale.ends_at)


# ─── Review — read (used inside product detail & review list responses) ───────
class ReviewSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(read_only=True)
    is_verified_purchase = serializers.BooleanField(read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "user_id",
            "name",
            "rating",
            "headline",
            "comment",
            "is_verified_purchase",
            "created_at",
        )


# ─── Review — write (validates and accepts new review submissions) ────────────
class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Write-only serializer for POSTing a new review.

    `product` and `user` are both injected server-side in the view
    (`perform_create` / `save(product=…, user=…)`) and are therefore
    excluded from the client-writable input fields. `name` is likewise
    NOT accepted from the client — it's derived from the authenticated
    user's profile in `create()` below, so a reviewer can't submit
    reviews under an arbitrary display name.
    """

    class Meta:
        model = Review
        fields = ("rating", "headline", "comment")

    def validate(self, attrs):
        """
        Enforce one-review-per-user-per-product at the application layer,
        ahead of the DB-level unique_together constraint (Task 1.3.1.4),
        so a duplicate attempt surfaces as a clean 400 with a friendly
        message instead of an IntegrityError-driven 500.

        `product` is provided by the view via get_serializer_context();
        `request.user` is the authenticated user (permission_classes on
        the view already requires authentication before we ever get
        here, but the checks below are defensive rather than assumed).
        """
        request = self.context.get("request")
        product = self.context.get("product")
        user = getattr(request, "user", None)

        if (
            product is not None
            and user is not None
            and getattr(user, "is_authenticated", False)
            and Review.objects.filter(product=product, user=user).exists()
        ):
            raise serializers.ValidationError(
                {"detail": "You have already reviewed this product."}
            )

        return attrs

    def create(self, validated_data):
        user = validated_data.get("user")
        display_name = ""
        if user is not None:
            profile = getattr(user, "profile", None)
            if profile is not None and (profile.first_name or profile.last_name):
                display_name = profile.get_fullname()
        if not display_name:
            # Newly-registered users may not have filled out their
            # profile's first/last name yet — fall back to their email
            # rather than a placeholder like "new user".
            display_name = user.email if user is not None else ""
        validated_data["name"] = display_name
        return super().create(validated_data)

    def validate_rating(self, value: int) -> int:
        if not (1 <= value <= 5):
            raise serializers.ValidationError(
                "Rating must be an integer between 1 and 5."
            )
        return value

    def validate_comment(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Review comment cannot be blank.")
        return value

    def validate_headline(self, value: str) -> str:
        return value.strip()


# ─── Product list serializer — lightweight, no nested reviews ─────────────────
class ProductListSerializer(serializers.ModelSerializer):
    category = CategoryMinimalSerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    discount_percent = serializers.ReadOnlyField()
    # Flash-sale display for the CARD. Real prices are per-variant, so these
    # are "starting at" figures: the cheapest active variant's price with the
    # sale applied (flash_sale_price) against that same variant's regular
    # price (flash_sale_original_price). `flash_sale_price_varies` is true
    # when variants differ in price, i.e. the UI should say "From $X". All
    # null/false when the product isn't currently on sale.
    is_on_flash_sale = serializers.SerializerMethodField()
    flash_sale_price = serializers.SerializerMethodField()
    flash_sale_original_price = serializers.SerializerMethodField()
    flash_sale_price_varies = serializers.SerializerMethodField()
    flash_sale_discount_percent = serializers.SerializerMethodField()
    flash_sale_ends_at = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "short_description",
            "price",
            "original_price",
            "discount_percent",
            "stock",
            "rating",
            "reviews_count",
            "is_new",
            "is_sale",
            "is_on_flash_sale",
            "flash_sale_price",
            "flash_sale_original_price",
            "flash_sale_price_varies",
            "flash_sale_discount_percent",
            "flash_sale_ends_at",
            "thumbnail_url",
            "category",
            "brand",
            "created_at",
            # Browse/filter-relevant new fields only (Tasks 3.2.1.1–3.2.1.13)
            # — these drive badges/filter chips shown directly on product
            # cards. Detail-only fields (ingredients, usage_instructions,
            # warnings, country_of_origin, irc_regulatory_code,
            # regulatory_verified) are deliberately NOT included here to
            # keep list/grid payloads lightweight.
            "skin_type",
            "hair_type",
            "gender",
            "is_cruelty_free",
            "is_vegan",
            "is_organic",
        )

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None

    def _flash_pricing(self, obj):
        """Resolve the product's sale pricing once per serialization, however
        many of the flash_sale_* fields ask for it."""
        cache = self.__dict__.setdefault("_flash_pricing_cache", {})
        if obj.pk not in cache:
            cache[obj.pk] = obj.flash_sale_card_pricing()
        return cache[obj.pk]

    def get_is_on_flash_sale(self, obj):
        return self._flash_pricing(obj) is not None

    def get_flash_sale_price(self, obj):
        pricing = self._flash_pricing(obj)
        return _money(pricing.price) if pricing else None

    def get_flash_sale_original_price(self, obj):
        pricing = self._flash_pricing(obj)
        return _money(pricing.original_price) if pricing else None

    def get_flash_sale_price_varies(self, obj):
        pricing = self._flash_pricing(obj)
        return pricing.price_varies if pricing else False

    def get_flash_sale_discount_percent(self, obj):
        pricing = self._flash_pricing(obj)
        if not pricing:
            return None
        return serializers.DecimalField(
            max_digits=5, decimal_places=2
        ).to_representation(pricing.sale.discount_percent)

    def get_flash_sale_ends_at(self, obj):
        pricing = self._flash_pricing(obj)
        if not pricing:
            return None
        return serializers.DateTimeField().to_representation(pricing.sale.ends_at)


# ─── Product detail serializer — full with nested relations ───────────────────
class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategoryMinimalSerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    # TODO: colors field is superseded by variants and should be removed
    # once frontend fully migrates to variant-based rendering.
    colors = ProductColorSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    discount_percent = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "slug",
            "short_description",
            "description",
            "price",
            "original_price",
            "discount_percent",
            "stock",
            "rating",
            "reviews_count",
            "is_new",
            "is_sale",
            "thumbnail_url",
            "images",
            "colors",
            "variants",
            "reviews",
            "category",
            "brand",
            "created_at",
            # All new Product fields (Tasks 3.2.1.1–3.2.1.13) — the detail
            # page is exactly where a customer needs the full ingredient
            # list, usage instructions, and warnings, and where
            # regulatory transparency matters most.
            "skin_type",
            "hair_type",
            "spf",
            "ingredients",
            "country_of_origin",
            "usage_instructions",
            "warnings",
            "gender",
            "is_cruelty_free",
            "is_vegan",
            "is_organic",
            "irc_regulatory_code",
            "regulatory_verified",
        )

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None


class StockAlertSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockAlertSubscription
        fields = ("id", "variant", "created_at")
        read_only_fields = ("id", "created_at")
