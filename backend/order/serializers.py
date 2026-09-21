from decimal import Decimal

from dashboard.models import Address, IranProvince, iran_postal_code_validator
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from shop.models import ProductVariant, StockMovement

from .models import Order, OrderItem
from .services.pricing import PricingError, calculate_order_totals

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
            "variant",
            "variant_sku",
            "variant_attributes_json",
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
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    # Shipping address — either supply address_id (a saved Address) OR
    # all of these manually; enforced in validate(), see there for why
    # these can't simply stay required=True at the field level.
    address_id = serializers.IntegerField(required=False, allow_null=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    apartment = serializers.CharField(max_length=100, allow_blank=True, default="")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    state = serializers.ChoiceField(
        choices=IranProvince.choices, required=False, allow_blank=True
    )
    zip = serializers.CharField(
        max_length=10,
        required=False,
        allow_blank=True,
        validators=[iran_postal_code_validator],
    )
    country = serializers.CharField(max_length=10, required=False, allow_blank=True)

    # If checking out with manually-typed fields (not address_id), save
    # them as a new Address for next time.
    save_address = serializers.BooleanField(default=False)

    # Billing
    billing_same = serializers.BooleanField(default=True)

    # Payment
    # Task 6.4.1.3: made optional with a default. Checkout no longer asks
    # the customer to pick a payment method type on this platform at all
    # (real payment happens on the gateway's own hosted page — tracked
    # separately via PaymentTransaction.gateway, e.g. "zarinpal"), so the
    # frontend stopped sending this field entirely (Task 6.4.1.1). Keeping
    # the field itself (rather than removing it from the model) avoids a
    # migration and keeps existing order-history/admin displays working;
    # CREDIT_CARD is just a harmless placeholder value now, not a real
    # signal of anything. An explicit value is still accepted and
    # validated normally if a caller does send one.
    payment_method = serializers.ChoiceField(
        choices=Order.PaymentMethod.choices,
        required=False,
        default=Order.PaymentMethod.CREDIT_CARD,
    )
    card_last_four = serializers.CharField(
        max_length=4, min_length=4, allow_blank=True, default=""
    )

    # Optional
    notes = serializers.CharField(allow_blank=True, default="")

    def validate_card_last_four(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError("Must be 4 numeric digits.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user

        # ── Resolve shipping address: saved address_id OR manual fields ────────
        address_id = attrs.get("address_id")
        if address_id is not None:
            # SECURITY: scoped to user=user — without this filter, any
            # authenticated user could submit ANY OTHER user's numeric
            # address_id and have their order shipped using (and their
            # own account able to see) someone else's saved address.
            try:
                address = Address.objects.get(pk=address_id, user=user)
            except Address.DoesNotExist:
                raise serializers.ValidationError({"address_id": "Address not found."})

            # A saved address_id takes precedence over any manually-typed
            # fields also present in the same payload — the saved address
            # is the more trustworthy source, and this avoids a confusing
            # "which one actually applies" ambiguity.
            attrs["first_name"] = address.first_name
            attrs["last_name"] = address.last_name
            attrs["phone"] = address.phone
            attrs["address"] = address.address_line
            attrs["apartment"] = address.apartment
            attrs["city"] = address.city
            attrs["state"] = address.province
            attrs["zip"] = address.postal_code
            attrs["country"] = address.country
        else:
            # No saved address referenced — every one of these fields is
            # required=False at the field-declaration level (so that an
            # address_id-based checkout doesn't have to also supply them),
            # but at least one complete path must fully supply an address,
            # so enforce that here instead.
            required_manual_fields = (
                "first_name",
                "last_name",
                "phone",
                "address",
                "city",
                "state",
                "zip",
                "country",
            )
            missing = {
                field: "This field is required when no address_id is provided."
                for field in required_manual_fields
                if not attrs.get(field)
            }
            if missing:
                raise serializers.ValidationError(missing)

        try:
            cart = user.cart
        except Exception:
            raise serializers.ValidationError({"cart": "No cart found for this user."})
        if not cart.items.exists():
            raise serializers.ValidationError({"cart": "Your cart is empty."})

        # Non-locking, best-effort availability pre-check. This is a UX
        # improvement layered on top of create()'s existing atomic,
        # select_for_update()-locked stock decrement (Epic 1 Task 1.1.1.3
        # / Epic 3 Task 3.1.1.5), which remains the actual race-safe
        # guarantee — deliberately does NOT lock rows here, since this
        # check's only job is a clearer, itemized error message, not a
        # meaningfully earlier point in time (DRF calls validate() and
        # create() back-to-back within the same request when a view does
        # is_valid() then save(), so there's no real time gap between the
        # two checks in practice).
        problems = []
        for item in cart.items.select_related("variant").all():
            if (
                item.variant is None
                or not item.variant.is_active
                or item.variant.stock < item.quantity
            ):
                problems.append(item)

        if problems:
            raise serializers.ValidationError(
                {
                    "cart": [
                        (
                            (
                                f"{item.variant.product.name} ({item.variant.sku}) is no "
                                "longer available in the requested quantity."
                            )
                            if item.variant is not None
                            else "One of the items in your cart is no longer available."
                        )
                        for item in problems
                    ]
                }
            )

        attrs["cart"] = cart
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        cart = validated_data["cart"]

        with transaction.atomic():
            # ── Lock the referenced ProductVariant rows FIRST ───────────────
            # Row-level lock so concurrent checkouts against the same
            # variant(s) serialize instead of racing on stock — AND, as of
            # this task, on price too. Locking is scoped to the variant,
            # not the product, so two customers ordering the LAST unit of
            # two DIFFERENT variants of the SAME product don't spuriously
            # contend with each other.
            cart_items = list(
                cart.items.select_related("variant__product", "variant__color")
                .prefetch_related("variant__product__images")
                .all()
            )
            variant_ids = {cart_item.variant_id for cart_item in cart_items}
            locked_variants = {
                variant.id: variant
                for variant in ProductVariant.objects.select_for_update(of=("self",))
                .select_related("product", "color")
                .prefetch_related("product__images")
                .filter(id__in=variant_ids)
            }

            # ── Validate + capture each item's price ONCE, from the LOCKED
            # variant ──────────────────────────────────────────────────────
            # Previously, cart.subtotal (used for Order.subtotal/total) and
            # cart_item.unit_price (used for each OrderItem.unit_price)
            # were two SEPARATE, independent reads of variant.price — the
            # former computed before this atomic block even started, the
            # latter from cart_item.variant (the UNLOCKED object fetched
            # just above), and NEITHER used locked_variant.price at all,
            # despite locked_variant being the one row-locked, guaranteed-
            # fresh-as-of-lock-acquisition source available. A price
            # change landing between any of those independent reads could
            # have made Order.subtotal internally inconsistent with
            # sum(OrderItem.unit_price × quantity) for the SAME order —
            # a real, if narrow, TOCTOU-style gap. Capturing
            # locked_variant.price ONCE per item here, then deriving BOTH
            # the subtotal AND every OrderItem snapshot from this single
            # captured list, closes it: every price used anywhere in this
            # order is the same value, read after the lock was acquired.
            priced_items = []
            subtotal = Decimal("0")
            for cart_item in cart_items:
                locked_variant = locked_variants[cart_item.variant_id]

                # Defense in depth: re-validate expiration at checkout,
                # mirroring the existing "re-validate stock at checkout,
                # don't just trust the cart" principle. A cart item can
                # have been valid when added (Task's cart-side check)
                # but since expired — e.g. it sat in the cart for days
                # past the variant's expiration_date. This check runs
                # BEFORE any OrderItem is created or stock decremented
                # for ANY item in this checkout, so if this is, say,
                # the 3rd of 5 cart items, raising here rolls back the
                # Order and the earlier 2 items' stock decrements too,
                # via the outer transaction.atomic() block — nothing is
                # left partially committed.
                #
                # NOTE: this block is currently absolute — there is no
                # override letting an admin deliberately sell expired
                # stock (e.g. a disclosed clearance/close-out sale).
                # The backlog doesn't ask for that exception; if it
                # becomes a real business need it deserves its own
                # deliberate design (e.g. a per-variant flag or
                # admin-only checkout path), not a silent workaround
                # here.
                if (
                    locked_variant.expiration_date is not None
                    and locked_variant.expiration_date < timezone.now().date()
                ):
                    variant_detail = (
                        locked_variant.color.name
                        if locked_variant.color
                        else locked_variant.sku
                    )
                    raise serializers.ValidationError(
                        {
                            "expired_item": (
                                f"'{locked_variant.product.name} — {variant_detail}' "
                                "has expired and can no longer be purchased. Please "
                                "remove it from your cart."
                            )
                        }
                    )

                # Validate stock. Raising here inside the atomic block
                # rolls back the Order (and any earlier OrderItem/stock
                # writes from this same loop) as a unit.
                if locked_variant.stock < cart_item.quantity:
                    variant_detail = (
                        locked_variant.color.name
                        if locked_variant.color
                        else locked_variant.sku
                    )
                    raise serializers.ValidationError(
                        {
                            "stock": (
                                f"Only {locked_variant.stock} of "
                                f"'{locked_variant.product.name} — {variant_detail}' "
                                "left in stock."
                            )
                        }
                    )

                unit_price = locked_variant.price
                priced_items.append((cart_item, locked_variant, unit_price))
                subtotal += unit_price * cart_item.quantity

            # SECURITY: discount is intentionally NOT read from client input.
            # There is no coupon/promo system yet (tracked separately as
            # Epic 9), so discount is hardcoded to zero here rather than
            # trusted from the checkout payload — previously a client could
            # submit an arbitrary `discount` value directly in the POST body
            # and have it applied at checkout with no server-side validation.
            # TODO: Epic 9 — replace with server-validated coupon discount
            try:
                totals = calculate_order_totals(
                    subtotal=subtotal, discount=Decimal("0")
                )
            except (PricingError, ValueError) as e:
                raise serializers.ValidationError({"discount": str(e)})

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
                subtotal=totals["subtotal"],
                shipping_cost=totals["shipping_cost"],
                tax=totals["tax"],
                discount=totals["discount"],
                total=totals["total"],
                notes=validated_data.get("notes", ""),
                status=Order.Status.PENDING,
            )

            # ── Snapshot each cart item, decrement stock ────────────────────
            for cart_item, locked_variant, unit_price in priced_items:
                product = locked_variant.product

                locked_variant.stock -= cart_item.quantity
                locked_variant.save(update_fields=["stock"])
                # Product.stock is now superseded by ProductVariant.stock and
                # unused in the order flow — candidate for removal in a
                # future cleanup task.

                # Audit trail (Task 4.1.1.1): logged inside this same atomic
                # block so the movement row and the stock decrement commit
                # or roll back together — an audit entry for a decrement
                # that got rolled back would be a lie.
                StockMovement.objects.create(
                    variant=locked_variant,
                    reason=StockMovement.Reason.SALE,
                    quantity_delta=-cart_item.quantity,
                    stock_after=locked_variant.stock,
                    related_order=order,
                    note=f"Order {order.order_number}",
                )

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
                    variant=locked_variant,
                    variant_sku=locked_variant.sku,
                    variant_attributes_json={
                        "color": (
                            locked_variant.color.name if locked_variant.color else None
                        )
                    },
                    unit_price=unit_price,
                    quantity=cart_item.quantity,
                )

            # NOTE: the cart is deliberately NOT cleared here any more
            # (Task 6.4.1.2). It used to be cleared at order-creation time,
            # but Phase 6's real-payment flow creates the order as PENDING
            # *before* the customer ever reaches the gateway — clearing the
            # cart at this point meant a customer whose payment failed or
            # who cancelled at the gateway page lost their cart entirely,
            # with no easy way to reorder, even though their order was
            # correctly cancelled and stock released
            # (payments.views.PaymentCallbackView._mark_failed). The cart is
            # now cleared only on CONFIRMED payment success, in
            # PaymentCallbackView.get()'s success branch — see that view for
            # the corresponding cart.items.all().delete() call.

            # ── Save this address for next time ──────────────────────────────
            # Only when checkout used manually-typed fields (not an
            # existing address_id — that address is already saved by
            # definition) and the customer explicitly opted in.
            if validated_data.get("save_address") and not validated_data.get(
                "address_id"
            ):
                Address.objects.create(
                    user=request.user,
                    first_name=validated_data["first_name"],
                    last_name=validated_data["last_name"],
                    phone=validated_data["phone"],
                    address_line=validated_data["address"],
                    apartment=validated_data.get("apartment", ""),
                    city=validated_data["city"],
                    province=validated_data["state"],
                    postal_code=validated_data["zip"],
                    country=validated_data["country"],
                )

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
