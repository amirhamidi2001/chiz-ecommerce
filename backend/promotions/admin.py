from django.contrib import admin

from .models import Coupon, CouponRedemption, FlashSale


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "value",
        "is_active",
        "valid_from",
        "valid_until",
        "max_uses",
    )
    list_filter = ("discount_type", "is_active")
    search_fields = ("code",)
    ordering = ("-created_at",)
    filter_horizontal = ("categories", "products")


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ("coupon", "user", "order", "discount_amount", "redeemed_at")
    list_filter = ("coupon",)
    search_fields = ("coupon__code", "user__email", "order__order_number")
    readonly_fields = [f.name for f in CouponRedemption._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = ("name", "discount_percent", "starts_at", "ends_at", "is_active")
    list_filter = ("is_active",)
    filter_horizontal = ("products",)
