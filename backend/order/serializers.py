from decimal import Decimal

from rest_framework import serializers

from .models import Order, OrderItem

TAX_RATE = Decimal("0.10")  # 10%
SHIPPING_COST = Decimal("9.99")


# ─── Read serializers ─────────────────────────────────────────────────────────


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_name",
            "product_slug",
            "product_image",
            "unit_price",
            "quantity",
            "subtotal",
        ]
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    full_name = serializers.CharField(read_only=True)
    shipping_address_display = serializers.CharField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "status_display",
            # customer snapshot
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            # shipping
            "shipping_address",
            "shipping_apartment",
            "shipping_city",
            "shipping_state",
            "shipping_zip",
            "shipping_country",
            "shipping_address_display",
            "billing_same_as_shipping",
            # payment
            "payment_method",
            "payment_display",
            "card_last_four",
            # financials
            "subtotal",
            "shipping_cost",
            "tax",
            "discount",
            "total",
            # items
            "items",
            # meta
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ─── Write serializer (checkout submission) ───────────────────────────────────


class OrderCreateSerializer(serializers.Serializer):
    """
    Validates the checkout form payload and creates an Order from the
    authenticated user's current cart.
    """

    # Customer info
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30)

    # Shipping address
    address = serializers.CharField(max_length=255)
    apartment = serializers.CharField(max_length=100, allow_blank=True, default="")
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    zip = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=10)

    # Billing
    billing_same = serializers.BooleanField(default=True)

    # Payment
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices)
    card_last_four = serializers.CharField(
        max_length=4, min_length=4, allow_blank=True, default=""
    )

    # Optional
    notes = serializers.CharField(allow_blank=True, default="")
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), default=Decimal("0")
    )

    def validate_card_last_four(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError("Must be 4 numeric digits.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        try:
            cart = user.cart
        except Exception:
            raise serializers.ValidationError({"cart": "No cart found for this user."})
        if not cart.items.exists():
            raise serializers.ValidationError({"cart": "Your cart is empty."})
        attrs["cart"] = cart
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        cart = validated_data["cart"]
        discount = validated_data.get("discount", Decimal("0"))

        subtotal = Decimal(str(cart.subtotal))
        tax = (subtotal * TAX_RATE).quantize(Decimal("0.01"))
        total = (subtotal + SHIPPING_COST + tax - discount).quantize(Decimal("0.01"))

        order = Order.objects.create(
            user=request.user,
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            email=validated_data["email"],
            phone=validated_data["phone"],
            shipping_address=validated_data["address"],
            shipping_apartment=validated_data.get("apartment", ""),
            shipping_city=validated_data["city"],
            shipping_state=validated_data["state"],
            shipping_zip=validated_data["zip"],
            shipping_country=validated_data["country"],
            billing_same_as_shipping=validated_data.get("billing_same", True),
            payment_method=validated_data["payment_method"],
            card_last_four=validated_data.get("card_last_four", ""),
            subtotal=subtotal,
            shipping_cost=SHIPPING_COST,
            tax=tax,
            discount=discount,
            total=total,
            notes=validated_data.get("notes", ""),
            status=Order.Status.PROCESSING,
        )

        # ── Snapshot each cart item ────────────────────────────────────────
        for cart_item in (
            cart.items.select_related("product")
            .prefetch_related("product__images")
            .all()
        ):
            product = cart_item.product

            # Build absolute image URL
            image_url = ""
            first_img = product.images.first()
            if first_img and first_img.image:
                try:
                    image_url = request.build_absolute_uri(first_img.image.url)
                except Exception:
                    image_url = ""
            elif product.thumbnail:
                try:
                    image_url = request.build_absolute_uri(product.thumbnail.url)
                except Exception:
                    image_url = ""

            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                product_slug=product.slug,
                product_image=image_url,
                unit_price=cart_item.unit_price,
                quantity=cart_item.quantity,
            )

        # ── Clear the cart ─────────────────────────────────────────────────
        cart.items.all().delete()

        return order


class OrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for order list view."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "status_display",
            "total",
            "item_count",
            "created_at",
        ]

    def get_item_count(self, obj):
        return obj.items.count()
