from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "product",
        "product_name",
        "product_slug",
        "unit_price",
        "quantity",
        "item_subtotal",
    )
    fields = (
        "product",
        "product_name",
        "unit_price",
        "quantity",
        "item_subtotal",
    )
    can_delete = False

    def item_subtotal(self, obj):
        return f"${obj.subtotal:.2f}"

    item_subtotal.short_description = "Subtotal"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "user_email",
        "full_name",
        "status",
        "payment_method",
        "order_total",
        "item_count",
        "created_at",
    )
    list_filter = ("status", "payment_method", "created_at", "shipping_country")
    search_fields = (
        "order_number",
        "email",
        "first_name",
        "last_name",
        "user__email",
    )
    readonly_fields = (
        "order_number",
        "subtotal",
        "shipping_cost",
        "tax",
        "discount",
        "total",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Order Identity",
            {
                "fields": ("order_number", "user", "status", "notes"),
            },
        ),
        (
            "Customer",
            {
                "fields": ("first_name", "last_name", "email", "phone"),
            },
        ),
        (
            "Shipping Address",
            {
                "fields": (
                    "shipping_address",
                    "shipping_apartment",
                    "shipping_city",
                    "shipping_state",
                    "shipping_zip",
                    "shipping_country",
                    "billing_same_as_shipping",
                ),
            },
        ),
        (
            "Payment",
            {
                "fields": ("payment_method", "card_last_four"),
            },
        ),
        (
            "Financials",
            {
                "fields": ("subtotal", "shipping_cost", "tax", "discount", "total"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    inlines = [OrderItemInline]
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    def user_email(self, obj):
        return obj.user.email if obj.user else "—"

    def order_total(self, obj):
        return f"${obj.total:.2f}"

    def item_count(self, obj):
        return obj.items.count()

    user_email.short_description = "User"
    order_total.short_description = "Total"
    item_count.short_description = "Items"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order_number",
        "product_name",
        "unit_price",
        "quantity",
        "item_subtotal",
    )
    list_filter = ("order__status",)
    search_fields = ("product_name", "order__order_number", "order__email")
    readonly_fields = (
        "order",
        "product",
        "product_name",
        "product_slug",
        "product_image",
        "unit_price",
        "quantity",
    )

    def order_number(self, obj):
        return obj.order.order_number

    def item_subtotal(self, obj):
        return f"${obj.subtotal:.2f}"

    order_number.short_description = "Order"
    item_subtotal.short_description = "Subtotal"
