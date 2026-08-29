from rest_framework import serializers
from shop.serializers import ColorSerializer

from .models import Cart, CartItem


class CartItemProductSerializer(serializers.Serializer):
    """Lightweight product snapshot embedded inside a cart item's variant."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.SlugField()
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        request = self.context.get("request")

        # 1. Try the first gallery image
        first_image = obj.images.first()
        if first_image and first_image.image:
            if request:
                return request.build_absolute_uri(first_image.image.url)
            return first_image.image.url

        # 2. Fall back to the dedicated thumbnail field
        if obj.thumbnail:
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url

        return None


class CartItemVariantSerializer(serializers.Serializer):
    """
    Variant snapshot embedded inside a cart item — this is now where
    price/original_price/stock/color live (previously flat on
    `product`), since each cart line is tied to one specific
    shade/size, not the product in the abstract.
    """

    id = serializers.IntegerField()
    sku = serializers.CharField()
    color = ColorSerializer(read_only=True, allow_null=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    original_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )
    stock = serializers.IntegerField()
    product = CartItemProductSerializer(read_only=True)


class CartItemSerializer(serializers.ModelSerializer):
    variant = CartItemVariantSerializer(read_only=True)
    variant_id = serializers.IntegerField(write_only=True)
    unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id",
            "variant",
            "variant_id",
            "quantity",
            "unit_price",
            "subtotal",
            "added_at",
            "updated_at",
        ]
        read_only_fields = ["id", "added_at", "updated_at"]

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def validate_variant_id(self, value):
        from shop.models import ProductVariant

        try:
            variant = ProductVariant.objects.get(pk=value)
        except ProductVariant.DoesNotExist:
            raise serializers.ValidationError("Product variant not found.")
        if not variant.is_active:
            raise serializers.ValidationError("This product variant is unavailable.")
        if variant.stock < 1:
            raise serializers.ValidationError("This product variant is out of stock.")
        return value


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "subtotal",
            "total_items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
