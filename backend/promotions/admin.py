from core.jalali import JalaliAdminMixin, jalali_column
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Coupon, CouponRedemption, FlashSale


@admin.register(Coupon)
class CouponAdmin(JalaliAdminMixin, admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "percent_off",
        "fixed_amount",
        "is_active",
        "valid_from",
        "valid_from_jalali",
        "valid_until",
        "valid_until_jalali",
        "max_uses",
    )
    list_filter = ("discount_type", "is_active")
    search_fields = ("code",)
    ordering = ("-created_at",)
    filter_horizontal = ("categories", "products")

    # Campaign windows are scheduled against the Persian calendar, so show Jalali
    # beside each Gregorian input (read-only; storage and editing unchanged).
    valid_from_jalali = jalali_column("valid_from", _("Valid from (Jalali)"))
    valid_until_jalali = jalali_column("valid_until", _("Valid until (Jalali)"))
    readonly_fields = ("valid_from_jalali", "valid_until_jalali")
    jalali_companions = {
        "valid_from": "valid_from_jalali",
        "valid_until": "valid_until_jalali",
    }


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
class FlashSaleAdmin(JalaliAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "discount_percent",
        "starts_at",
        "starts_at_jalali",
        "ends_at",
        "ends_at_jalali",
        "is_active",
    )
    list_filter = ("is_active",)
    filter_horizontal = ("products",)

    starts_at_jalali = jalali_column("starts_at", _("Starts (Jalali)"))
    ends_at_jalali = jalali_column("ends_at", _("Ends (Jalali)"))
    readonly_fields = ("starts_at_jalali", "ends_at_jalali")
    jalali_companions = {
        "starts_at": "starts_at_jalali",
        "ends_at": "ends_at_jalali",
    }
