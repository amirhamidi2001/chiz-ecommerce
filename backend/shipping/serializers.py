# IranProvince is fundamentally a general-purpose "Iran's provinces"
# concept, not something that's actually dashboard-specific — see the
# identical consideration already documented in shipping/models.py (Task
# 7.1.1.3). Same circularity check applies here: dashboard doesn't import
# anything from shipping, so this top-level import is safe.
from dashboard.models import IranProvince
from rest_framework import serializers


class ShippingQuoteSerializer(serializers.Serializer):
    """
    Input for POST /api/shipping/quote/ (Task 7.2.1.6): the destination a
    shopper has entered/selected at checkout, before they've committed to a
    specific carrier+rate. The view resolves cart weight itself from the
    requesting user's/session's cart — it isn't part of this input.
    """

    province = serializers.ChoiceField(choices=IranProvince.choices)
    city = serializers.CharField(max_length=100)
