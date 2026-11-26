from django.contrib import admin

from .models import Address, PriceAdjustmentLog, Wishlist


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "city", "province", "country", "is_default")
    list_filter = ("country", "province", "label", "is_default")
    search_fields = ("user__email", "first_name", "last_name", "city", "postal_code")


admin.site.register(Wishlist)


@admin.register(PriceAdjustmentLog)
class PriceAdjustmentLogAdmin(admin.ModelAdmin):
    """Read-only: an audit trail must not be editable from the admin."""

    list_display = (
        "created_at",
        "actor",
        "adjustment_type",
        "value",
        "affected_count",
        "matched_count",
    )
    list_filter = ("adjustment_type",)
    readonly_fields = [f.name for f in PriceAdjustmentLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
