from django.contrib import admin

from .models import Address, Wishlist


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "city", "province", "country", "is_default")
    list_filter = ("country", "province", "label", "is_default")
    search_fields = ("user__email", "first_name", "last_name", "city", "postal_code")


admin.site.register(Wishlist)
