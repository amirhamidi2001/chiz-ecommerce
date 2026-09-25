from rest_framework import serializers

from .models import RefundRequest


class PaymentInitiateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()


class RefundRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundRequest
        fields = [
            "id",
            "order",
            "transaction",
            "amount",
            "reason",
            "status",
            "created_at",
            "resolved_at",
        ]
        read_only_fields = fields


class RefundRequestCreateSerializer(serializers.Serializer):
    """
    Validates the customer-facing POST /api/orders/<id>/refund-request/
    payload only — `order`, `transaction`, and `requested_by` are set by
    the view from the authenticated request/order lookup, not accepted
    as client input.
    """

    reason = serializers.CharField(trim_whitespace=True)
    # A partial refund is a legitimate request a customer or admin might
    # want to specify — optional, defaults to the order's full total in
    # the view if omitted here.
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=0
    )
