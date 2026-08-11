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
    The `product` field is injected in the view via perform_create / save(product=…)
    and is therefore excluded from the input fields.
    """

    class Meta:
        model = Review
        fields = ("name", "rating", "headline", "comment")

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name cannot be blank.")
        return value

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
