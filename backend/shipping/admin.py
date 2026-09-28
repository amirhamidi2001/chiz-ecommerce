from django.contrib import admin

from .models import ShippingCarrier, ShippingRate


@admin.register(ShippingCarrier)
class ShippingCarrierAdmin(admin.ModelAdmin):
    list_display = ("display_name", "code", "is_active", "supports_same_day")
    list_filter = ("is_active", "supports_same_day")


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = (
        "carrier",
        "province",
        "city",
        "min_weight_g",
        "max_weight_g",
        "price",
        "is_active",
    )
    list_filter = ("carrier", "province", "is_active")
    search_fields = ("city",)
