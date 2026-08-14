from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import OTPCode, Profile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "get_full_name",
        "type",
        "is_active",
        "is_verified",
        "is_staff",
        "is_superuser",
        "created_date",
        "profile_link",
    )
    list_filter = ("type", "is_active", "is_verified", "is_staff", "is_superuser")
    search_fields = ("email", "profile__first_name", "profile__last_name")
    ordering = ("-created_date",)
    readonly_fields = ("created_date", "updated_date")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "type",
                    "is_active",
                    "is_verified",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("created_date", "updated_date")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "type",
                    "is_active",
                    "is_verified",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

    def get_full_name(self, obj):
        return (
            obj.profile.get_fullname() if hasattr(obj, "profile") else _("No profile")
        )

    get_full_name.short_description = _("Full name")

    def profile_link(self, obj):
        if hasattr(obj, "profile"):
            url = reverse("admin:accounts_profile_change", args=[obj.profile.pk])
            return format_html('<a href="{}">Edit Profile</a>', url)
        return _("No profile")

    profile_link.short_description = _("Profile")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "get_fullname",
        "phone_number",
        "order_updates",
        "promotions",
        "newsletter",
    )
    search_fields = ("user__email", "first_name", "last_name", "phone_number")
    list_filter = ("order_updates", "promotions", "newsletter")
    readonly_fields = ("created_date", "updated_date")
    raw_id_fields = ("user",)


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    """
    Read-only in the admin: staff can view OTP request volume/history for
    support and abuse investigation, but must never see `code_hash` — a
    hash of the one-time code — even as a read-only value. It's excluded
    from both the list and detail views entirely, and no add/change/
    delete is permitted through this interface (view-only audit trail).
    """

    list_display = (
        "phone_number",
        "purpose",
        "is_used",
        "attempts",
        "expires_at",
        "created_at",
    )
    list_filter = ("purpose", "is_used")
    search_fields = ("phone_number",)
    ordering = ("-created_at",)

    # code_hash is deliberately never included here — not in list_display,
    # not in readonly_fields, and explicitly excluded so it can't leak
    # into the auto-generated detail view either.
    exclude = ("code_hash",)
    readonly_fields = (
        "phone_number",
        "purpose",
        "expires_at",
        "attempts",
        "is_used",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
