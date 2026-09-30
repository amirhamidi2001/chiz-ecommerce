from django.contrib import admin

from .models import Shipment, ShippingCarrier, ShippingRate
from .providers import get_carrier_provider


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


@admin.action(description="Book shipment with carrier")
def book_shipment(modeladmin, request, queryset):
    """
    Calls the assigned carrier's create_shipment() for every selected
    Shipment that hasn't been booked yet (tracking_number is still blank),
    and records the resulting tracking_number/label_url.

    This is a stopgap for Feature 7.2.1: it only handles the "call the
    carrier API" half of booking — an admin still has to create the blank
    Shipment row by hand first (via the ordinary Django admin "Add
    Shipment" form, picking the order and carrier), then select it here
    and run this action to actually book it. A proper "Book Shipment"
    button integrated directly into the admin ORDER management UI (which
    would also auto-create the Shipment row from Order.shipping_carrier
    in one step) is Epic 8's territory, once that epic's admin
    order-operations tasks exist.
    """
    for shipment in queryset.filter(tracking_number=""):
        provider = get_carrier_provider(shipment.carrier.code)
        result = provider.create_shipment(
            order=shipment.order,
            destination={
                "address": shipment.order.shipping_address,
                "city": shipment.order.shipping_city,
                "province": shipment.order.shipping_state,
                "postal_code": shipment.order.shipping_zip,
            },
        )
        if result.success:
            shipment.tracking_number = result.tracking_number
            shipment.label_url = result.label_url
            shipment.status = Shipment.Status.PENDING
            shipment.save()
        else:
            modeladmin.message_user(
                request,
                f"Failed to book shipment for {shipment.order.order_number}: "
                f"{result.error_message}",
                level="ERROR",
            )


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("order", "carrier", "tracking_number", "status", "last_tracked_at")
    list_filter = ("carrier", "status")
    search_fields = ("order__order_number", "tracking_number")
    actions = [book_shipment]
