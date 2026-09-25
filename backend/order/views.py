from django.db import transaction
from payments.models import PaymentTransaction, RefundRequest
from payments.serializers import RefundRequestCreateSerializer, RefundRequestSerializer
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .serializers import OrderCreateSerializer, OrderListSerializer, OrderSerializer
from .services.stock import release_reserved_stock


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
            #
            # Shared with the payment-failure path (Task 6.2.1.4) via
            # order.services.stock.release_reserved_stock — see that
            # module for why this is a shared helper rather than two
            # independently-maintained copies.
            release_reserved_stock(
                order,
                actor=self.request.user,
                note=f"Cancellation of order {order.order_number}",
            )

        serializer = OrderSerializer(order, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class RefundRequestCreateView(APIView):
    """
    POST /api/orders/<id>/refund-request/ — customer requests a refund
    for their own order (Task 6.4.2.3).

    This only RECORDS the request — no real money moves and no gateway
    refund API is called anywhere in this flow. A staff member processes
    the actual refund manually through the gateway's merchant dashboard
    outside this platform, then updates the RefundRequest's status via
    the admin actions on RefundRequestAdmin (payments/admin.py).
    """

    permission_classes = [IsAuthenticated]

    # PENDING hasn't even been paid yet (nothing to refund), and
    # CANCELLED orders already have their stock released — neither is a
    # sensible state to request a refund from.
    ELIGIBLE_STATUSES = (
        Order.Status.PROCESSING,
        Order.Status.SHIPPED,
        Order.Status.DELIVERED,
    )

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk, user=request.user)
        except Order.DoesNotExist:
            # Same shape as OrderDetailView: a nonexistent order and an
            # order belonging to someone else are indistinguishable from
            # the outside — both 404, never leaking which case it was.
            return Response(
                {"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if order.status not in self.ELIGIBLE_STATUSES:
            return Response(
                {
                    "detail": (
                        "This order isn't eligible for a refund request in its "
                        f"current status ({order.get_status_display()})."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RefundRequestCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data.get("amount")
        if amount is None:
            # Defaults to the order's full total — a partial refund is a
            # legitimate request a customer or admin might want to
            # specify instead, hence `amount` being optional at all.
            amount = order.total
        elif amount > order.total:
            return Response(
                {"amount": f"Cannot exceed the order total ({order.total})."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Attach the most recent SUCCESSFUL transaction, if any, purely
        # for staff context (which gateway transaction this refund
        # request actually refers to) — not required for the request
        # itself to be valid.
        latest_successful_transaction = (
            order.payment_transactions.filter(status=PaymentTransaction.Status.SUCCESS)
            .order_by("-created_at")
            .first()
        )

        refund_request = RefundRequest.objects.create(
            order=order,
            transaction=latest_successful_transaction,
            requested_by=request.user,
            amount=amount,
            reason=serializer.validated_data["reason"],
        )

        # TODO: Epic 16 — notify staff a new refund request was submitted,
        # once the proper notification infrastructure exists. No ad-hoc
        # email sending here in the meantime.

        response_serializer = RefundRequestSerializer(refund_request)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
