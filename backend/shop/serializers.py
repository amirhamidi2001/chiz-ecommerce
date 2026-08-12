from rest_framework import serializers

from .models import Brand, Category, Color, Product, ProductColor, ProductImage, Review


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
            "thumbnail_url",
            "category",
            "brand",
            "created_at",
        )

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None


# ─── Product detail serializer — full with nested relations ───────────────────
class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategoryMinimalSerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    colors = ProductColorSerializer(many=True, read_only=True)
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
            "reviews",
            "category",
            "brand",
            "created_at",
        )

    def get_thumbnail_url(self, obj):
        request = self.context.get("request")
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None
