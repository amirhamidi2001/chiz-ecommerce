from django.conf import settings
from django.urls import reverse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from order.models import Order

from .models import PaymentTransaction
from .serializers import PaymentInitiateSerializer
from .gateways import get_payment_gateway


class PaymentInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_id = serializer.validated_data["order_id"]

        try:
            # SECURITY: scoped to user=request.user — without this
            # filter, any authenticated user could submit any other
            # user's numeric order_id and initiate/hijack the payment
            # flow against someone else's order.
            order = Order.objects.get(pk=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response(
                {"order_id": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if order.status != Order.Status.PENDING:
            return Response(
                {"detail": "This order has already been paid or is no longer payable."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        gateway_name = settings.DEFAULT_PAYMENT_GATEWAY
        gateway = get_payment_gateway(gateway_name)
        callback_url = request.build_absolute_uri(
            reverse("payments:callback", kwargs={"gateway": gateway_name})
        )
        result = gateway.request_payment(
            amount=order.total,
            callback_url=callback_url,
            description=f"Order {order.order_number}",
        )

        if not result.success:
            # 502, not 400/500: this is a failed call to an external
            # dependency (the gateway), not a client input error or a
            # bug on our side.
            return Response(
                {"detail": result.error_message or "Payment initiation failed."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        PaymentTransaction.objects.create(
            order=order,
            gateway=gateway_name,
            authority=result.authority,
            amount=order.total,
            status=PaymentTransaction.Status.PENDING,
        )

        return Response(
            {"redirect_url": result.redirect_url}, status=status.HTTP_200_OK
        )
