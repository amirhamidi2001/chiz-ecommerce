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
    product = models.ForeignKey(
        "shop.Product",
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
        unique_together = ("cart", "product")
        ordering = ["-added_at"]
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"

    def __str__(self):
        return f"{self.quantity}× {self.product.name} in {self.cart}"

    @property
    def unit_price(self):
        """Return sale price if available, otherwise regular price."""
        return self.product.price

    @property
    def subtotal(self):
        if self.unit_price is None or self.quantity is None:
            return 0
        return self.unit_price * self.quantity
