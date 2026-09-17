from django.contrib import admin

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "gateway",
        "status",
        "authority",
        "amount",
        "created_at",
    )
    list_filter = ("gateway", "status")
    search_fields = ("order__order_number", "authority", "ref_id")
    readonly_fields = [f.name for f in PaymentTransaction._meta.fields]
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
