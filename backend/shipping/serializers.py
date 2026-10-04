# IranProvince is fundamentally a general-purpose "Iran's provinces"
# concept, not something that's actually dashboard-specific — see the
# identical consideration already documented in shipping/models.py (Task
# 7.1.1.3). Same circularity check applies here: dashboard doesn't import
# anything from shipping, so this top-level import is safe.
from dashboard.models import IranProvince
from rest_framework import serializers

from .models import Shipment


class ShippingQuoteSerializer(serializers.Serializer):
    """
    Input for POST /api/shipping/quote/ (Task 7.2.1.6): the destination a
    shopper has entered/selected at checkout, before they've committed to a
    specific carrier+rate. The view resolves cart weight itself from the
    requesting user's/session's cart — it isn't part of this input.
    """

    province = serializers.ChoiceField(choices=IranProvince.choices)
    city = serializers.CharField(max_length=100)


class ShipmentSerializer(serializers.ModelSerializer):
    """
    Read-only shipment status for a customer-facing order detail page
    (Task 7.2.2.3) — nested into OrderSerializer via
    OrderSerializer.get_shipment(). Deliberately thin: exposes the
    carrier's display name (not the internal ShippingCarrier row) and the
    human-readable status label alongside the raw code, since the
    frontend widget needs both (status for which step to highlight,
    status_display for the label actually shown to the customer).
    """

    carrier_name = serializers.CharField(source="carrier.display_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Shipment
        fields = (
            "carrier_name",
            "tracking_number",
            "status",
            "status_display",
            "last_tracked_at",
        )
