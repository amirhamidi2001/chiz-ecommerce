from rest_framework import serializers

from .models import Cart, CartItem


class CartItemProductSerializer(serializers.Serializer):
    """Lightweight product snapshot embedded inside a cart item."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.SlugField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    original_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )
    image = serializers.SerializerMethodField()
    stock = serializers.IntegerField()

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


class CartItemSerializer(serializers.ModelSerializer):
    product = CartItemProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "product_id",
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

    def validate_product_id(self, value):
        from shop.models import Product

        try:
            product = Product.objects.get(pk=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found.")
        if product.stock < 1:
            raise serializers.ValidationError("This product is out of stock.")
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
