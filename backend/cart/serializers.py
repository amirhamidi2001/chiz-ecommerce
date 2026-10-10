from django.utils import timezone
from promotions.services import validate_coupon
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
        # A variant with expiration_date=None has no expiration data at
        # all — that is NOT treated as "expired"; only a set date in
        # the past blocks the add. NOTE: this block is currently
        # absolute — there is no override for an admin to deliberately
        # sell expired stock (e.g. a disclosed clearance/close-out
        # sale). The backlog doesn't ask for that exception; if it
        # becomes a real business need it deserves its own deliberate
        # design, not a silent workaround here.
        if (
            variant.expiration_date is not None
            and variant.expiration_date < timezone.now().date()
        ):
            raise serializers.ValidationError(
                "This product has expired and is no longer available for purchase."
            )
        return value


class CartApplyCouponSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    # Coupon display (Task 9.1.1.6). All three are recomputed live on every
    # serialization, so the cart always reflects the coupon's CURRENT
    # validity for THIS requester (e.g. it expired since being applied, or
    # items were removed and the cart fell below min_order_amount). They
    # are for display only — checkout re-validates authoritatively
    # (Task 9.1.1.5).
    coupon_code = serializers.SerializerMethodField()
    coupon_discount = serializers.SerializerMethodField()
    coupon_error = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "subtotal",
            "total_items",
            "coupon_code",
            "coupon_discount",
            "coupon_error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def _coupon_check(self, obj):
        """
        validate_coupon() result for the cart's applied coupon (None if
        there isn't one). Computed once per cart per serializer instance,
        so the three coupon fields don't each repeat its DB queries; a
        serializer instance serves a single response, so the result can't
        go stale.
        """
        if obj.coupon_id is None:
            return None
        cache = self.__dict__.setdefault("_coupon_checks", {})
        if obj.pk not in cache:
            request = self.context.get("request")
            user = request.user if request else None
            cache[obj.pk] = validate_coupon(obj.coupon.code, user, obj)
        return cache[obj.pk]

    def get_coupon_code(self, obj):
        return obj.coupon.code if obj.coupon_id is not None else None

    def get_coupon_discount(self, obj):
        result = self._coupon_check(obj)
        return str(result.discount_amount) if result and result.valid else "0"

    def get_coupon_error(self, obj):
        result = self._coupon_check(obj)
        return result.error if result and not result.valid else None
