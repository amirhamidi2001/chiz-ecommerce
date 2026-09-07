from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from shop.models import ProductVariant, StockMovement

from .models import Order
from .serializers import OrderCreateSerializer, OrderListSerializer, OrderSerializer


class OrderListCreateView(APIView):
    """
    GET  /api/orders/  → list the authenticated user's orders (newest first)
    POST /api/orders/  → place a new order from the user's current cart
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects.filter(user=request.user)
            .prefetch_related("items")
            .order_by("-created_at")
        )
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OrderCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        order = serializer.save()
        response_serializer = OrderSerializer(order, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    """
    GET    /api/orders/<id>/  → retrieve a specific order (owner only)
    PATCH  /api/orders/<id>/  → cancel an order (owner; only if pending/processing)
    """

    permission_classes = [IsAuthenticated]

    def _get_order(self, request, pk):
        try:
            return Order.objects.prefetch_related(
                "items__product", "items__variant"
            ).get(pk=pk, user=request.user)
        except Order.DoesNotExist:
            return None

    def get(self, request, pk):
        order = self._get_order(request, pk)
        if not order:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = OrderSerializer(order, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        """Allow a user to cancel their own order if it hasn't shipped yet."""
        order = self._get_order(request, pk)
        if not order:
            return Response(
                {"detail": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        requested_status = request.data.get("status")
        if requested_status != Order.Status.CANCELLED:
            return Response(
                {"detail": "Only cancellation is allowed via this endpoint."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.status in (Order.Status.SHIPPED, Order.Status.DELIVERED):
            return Response(
                {
                    "detail": "Cannot cancel an order that has already been shipped or delivered."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status", "updated_at"])

            # ── Restore stock for each item ──────────────────────────────
            # ProductVariant.stock is the real, authoritative inventory
            # count now (Tasks 3.1.1.1–3.1.1.4); Product.stock is
            # superseded and unused in the order flow — candidate for
            # removal in a future cleanup task.
            for order_item in order.items.all():
                if order_item.variant_id is None:
                    # Variant was deleted after the order was placed
                    # (OrderItem.variant is SET_NULL) — nothing to restore.
                    continue

                variant = ProductVariant.objects.select_for_update().get(
                    pk=order_item.variant_id
                )
                variant.stock += order_item.quantity
                variant.save(update_fields=["stock"])

                # Audit trail (Task 4.1.1.1/4.1.1.3): logged inside this
                # same atomic block, and only inside this guard, since
                # there's nothing to log a movement against for an
                # order_item whose variant no longer exists.
                StockMovement.objects.create(
                    variant=variant,
                    reason=StockMovement.Reason.CANCELLATION,
                    quantity_delta=order_item.quantity,
                    stock_after=variant.stock,
                    actor=self.request.user,
                    related_order=order,
                    note=f"Cancellation of order {order.order_number}",
                )

        serializer = OrderSerializer(order, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
