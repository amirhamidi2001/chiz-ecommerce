from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price", "subtotal", "added_at")
    fields = ("product", "quantity", "unit_price", "subtotal", "added_at")

    def unit_price(self, obj):
        return f"${obj.unit_price:.2f}"

    def subtotal(self, obj):
        return f"${obj.subtotal:.2f}"

    unit_price.short_description = "Unit Price"
    subtotal.short_description = "Subtotal"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user_email", "total_items", "cart_subtotal", "updated_at")
    list_filter = ("updated_at",)
    search_fields = ("user__email", "user__first_name", "user__last_name")
    readonly_fields = ("created_at", "updated_at", "cart_subtotal", "total_items")
    inlines = [CartItemInline]
    ordering = ("-updated_at",)

    def user_email(self, obj):
        return obj.user.email

    def cart_subtotal(self, obj):
        return f"${obj.subtotal:.2f}"

    def total_items(self, obj):
        return obj.total_items

    user_email.short_description = "User"
    cart_subtotal.short_description = "Subtotal"
    total_items.short_description = "Items"


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cart_user",
        "product_name",
        "quantity",
        "unit_price_display",
        "item_subtotal",
        "added_at",
    )
    list_filter = ("added_at", "cart__user")
    search_fields = (
        "product__name",
        "cart__user__email",
        "cart__user__first_name",
        "cart__user__last_name",
    )
    readonly_fields = ("added_at", "updated_at")
    ordering = ("-added_at",)

    def cart_user(self, obj):
        return obj.cart.user.email

    def product_name(self, obj):
        return obj.product.name

    def unit_price_display(self, obj):
        return f"${obj.unit_price:.2f}"

    def item_subtotal(self, obj):
        return f"${obj.subtotal:.2f}"

    cart_user.short_description = "User"
    product_name.short_description = "Product"
    unit_price_display.short_description = "Unit Price"
    item_subtotal.short_description = "Subtotal"
