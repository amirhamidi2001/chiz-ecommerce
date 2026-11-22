from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from .models import NotificationLog, NotificationTemplate


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("event", "channel", "is_active", "updated_at")
    list_filter = ("channel", "event", "is_active")


class RecentFailuresFilter(admin.SimpleListFilter):
    """
    Failed notifications inside a recent window — the operational signal this
    log exists to surface. A burst here usually means a provider credential
    expired or SMTP/SMS configuration broke. Combine with the channel/event
    filters to see which channel is failing.
    """

    title = "recent failures"
    parameter_name = "recent_failures"

    def lookups(self, request, model_admin):
        return (
            ("1h", "Failed in the last hour"),
            ("24h", "Failed in the last 24 hours"),
            ("7d", "Failed in the last 7 days"),
        )

    WINDOWS = {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
    }

    def queryset(self, request, queryset):
        window = self.WINDOWS.get(self.value())
        if window is None:
            return queryset
        return queryset.filter(
            status=NotificationLog.Status.FAILED,
            sent_at__gte=timezone.now() - window,
        )


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Audit log — viewable and searchable, never hand-edited or deleted."""

    list_display = ("event", "channel", "recipient", "status", "sent_at")
    list_filter = (RecentFailuresFilter, "status", "channel", "event")
    search_fields = ("recipient",)
    readonly_fields = [f.name for f in NotificationLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
