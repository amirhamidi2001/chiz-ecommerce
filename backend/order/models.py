import uuid

from core.fields import RialField, whole_toman_constraint
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Order(models.Model):
    """
    Represents a placed order.

    Shipping address fields are stored directly so the order is a
    self-contained snapshot — changes to a user's profile won't affect
    historical orders.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        PROCESSING = "processing", _("Processing")
        SHIPPED = "shipped", _("Shipped")
        DELIVERED = "delivered", _("Delivered")
        CANCELLED = "cancelled", _("Cancelled")

    class PaymentMethod(models.TextChoices):
        CREDIT_CARD = "credit_card", _("Credit / Debit Card")
        PAYPAL = "paypal", _("PayPal")
        APPLE_PAY = "apple_pay", _("Apple Pay")

    # ── Identity ───────────────────────────────────────────────────────────
    order_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="orders",
    )

    # ── Status ─────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # ── Customer snapshot ──────────────────────────────────────────────────
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30)

    # ── Shipping address snapshot ──────────────────────────────────────────
    shipping_address = models.CharField(max_length=255)
    shipping_apartment = models.CharField(max_length=100, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_zip = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=10)

    # ── Billing ────────────────────────────────────────────────────────────
    billing_same_as_shipping = models.BooleanField(default=True)

    # ── Payment ────────────────────────────────────────────────────────────
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CREDIT_CARD,
    )
    # Last four digits stored only if credit card; never store full PAN
    card_last_four = models.CharField(max_length=4, blank=True)

    # ── Shipping carrier/rate (Task 7.1.1.4) ────────────────────────────────
    # The specific carrier the customer selected at checkout (resolved
    # server-side from shipping_rate_id, never trusted from client-supplied
    # pricing — see OrderCreateSerializer.validate()). SET_NULL rather than
    # PROTECT/CASCADE: a carrier being deactivated or removed later must
    # never prevent historical orders from being read, and shipping_cost
    # below is already a frozen snapshot of the price at checkout time, so
    # losing this FK doesn't lose the financial record.
    shipping_carrier = models.ForeignKey(
        "shipping.ShippingCarrier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # ── Financials (snapshot at checkout time) ─────────────────────────────
    subtotal = RialField()
    # No default any more (Task 7.1.1.4): shipping_cost is now always
    # explicitly set from the resolved ShippingRate's price at checkout —
    # a hardcoded fallback default here is no longer appropriate and could
    # mask a bug (an order silently getting the old flat $9.99 instead of
    # its actual resolved rate) if ever accidentally relied upon.
    shipping_cost = RialField()
    tax = RialField()
    discount = RialField(default=0)
    total = RialField()

    # ── Notes ──────────────────────────────────────────────────────────────
    notes = models.TextField(blank=True)

    # ── Timestamps ─────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")
        constraints = [
            whole_toman_constraint("subtotal"),
            whole_toman_constraint("shipping_cost"),
            whole_toman_constraint("tax"),
            whole_toman_constraint("discount"),
            whole_toman_constraint("total"),
        ]

    def __str__(self):
        return f"Order {self.order_number} — {self.user}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate a human-readable order number, e.g. ORD-3A7F2B
            self.order_number = f"ORD-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        first = self.first_name.strip()
        last = self.last_name.strip()
        if first and last:
            return f"{first} {last}"
        return first or last

    @property
    def shipping_address_display(self):
        parts = [self.shipping_address]
        if self.shipping_apartment:
            parts.append(self.shipping_apartment)
        parts.append(f"{self.shipping_city}, {self.shipping_state} {self.shipping_zip}")
        parts.append(self.shipping_country)
        return "\n".join(parts)


class OrderItem(models.Model):
    """A single product line within an order (frozen snapshot of price)."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "shop.Product",
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
    )
    variant = models.ForeignKey(
        "shop.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
    )

    # Frozen snapshot so price history is preserved
    product_name = models.CharField(max_length=255)
    product_slug = models.SlugField(max_length=255)
    product_image = models.URLField(blank=True)  # absolute URL at order time
    variant_sku = models.CharField(max_length=64, blank=True)
    # Frozen snapshot of variant-identifying attributes (e.g. shade/size)
    # at order time, so the order remains a fully self-contained
    # fulfillment record even if the variant is later deleted or its
    # color is renamed.
    variant_attributes_json = models.JSONField(default=dict, blank=True)
    unit_price = RialField()
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["id"]
        verbose_name = _("Order Item")
        verbose_name_plural = _("Order Items")
        constraints = [whole_toman_constraint("unit_price")]

    def __str__(self):
        return f"{self.quantity}× {self.product_name} in {self.order.order_number}"

    @property
    def subtotal(self):
        if self.unit_price is None or self.quantity is None:
            return 0
        return self.unit_price * self.quantity
