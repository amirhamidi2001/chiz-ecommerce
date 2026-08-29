from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Cart(models.Model):
    """One cart per authenticated user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Cart"
        verbose_name_plural = "Carts"

    def __str__(self):
        return f"Cart of {self.user.email}"

    @property
    def subtotal(self):
        """Sum of all item subtotals."""
        return sum(item.subtotal for item in self.items.all())

    @property
    def total_items(self):
        """Total number of individual units in the cart."""
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    """A single product line inside a cart."""

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        "shop.ProductVariant",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("cart", "variant")
        ordering = ["-added_at"]
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"

    def __str__(self):
        variant_detail = (
            self.variant.color.name if self.variant.color_id else self.variant.sku
        )
        return f"{self.quantity}× {self.variant.product.name} ({variant_detail}) in {self.cart}"

    @property
    def unit_price(self):
        """Return the specific variant's price."""
        return self.variant.price

    @property
    def subtotal(self):
        if self.unit_price is None or self.quantity is None:
            return 0
        return self.unit_price * self.quantity
