from accounts.models import UserType
from cart.models import CartItem
from cart.views import get_or_create_cart
from core.money import rial_to_toman
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from payments.models import PaymentTransaction, RefundRequest
from payments.serializers import RefundRequestCreateSerializer, RefundRequestSerializer
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .serializers import OrderCreateSerializer, OrderListSerializer, OrderSerializer
from .services.cancellation import cancel_order
from .services.invoice import generate_invoice_pdf


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
                {"detail": _("Order not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = OrderSerializer(order, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        """Allow a user to cancel their own order if it hasn't shipped yet."""
        order = self._get_order(request, pk)
        if not order:
            return Response(
                {"detail": _("Order not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

        requested_status = request.data.get("status")
        if requested_status != Order.Status.CANCELLED:
            return Response(
                {"detail": _("Only cancellation is allowed via this endpoint.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Shared with the admin endpoint (dashboard.views.AdminOrderViewSet)
        # via order.services.cancellation.cancel_order — one authoritative
        # implementation of the status change + atomic stock restoration.
        try:
            cancel_order(order, actor=request.user)
        except ValueError:
            return Response(
                {
                    "detail": _(
                        "Cannot cancel an order that has already been shipped or "
                        "delivered."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
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
                {"detail": _("Order not found.")}, status=status.HTTP_404_NOT_FOUND
            )

        if order.status not in self.ELIGIBLE_STATUSES:
            return Response(
                {
                    "detail": _(
                        "This order isn't eligible for a refund request in its "
                        "current status (%(status)s)."
                    )
                    % {"status": order.get_status_display()}
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
                {
                    "amount": _("Cannot exceed the order total (%(total)s Toman).")
                    % {"total": f"{rial_to_toman(order.total):,}"}
                },
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


class PDFPassthroughRenderer(BaseRenderer):
    """
    Lets content negotiation accept `Accept: application/pdf` (otherwise DRF
    answers 406 before the view runs). The PDF is returned as a plain
    HttpResponse and never rendered; this only renders error bodies, as JSON.
    """

    media_type = "application/pdf"
    format = "pdf"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return JSONRenderer().render(data, accepted_media_type, renderer_context)


class OrderInvoiceView(APIView):
    """
    GET /api/orders/<id>/invoice/ → PDF invoice for an order.
    Allowed for the order's owner and for staff/admin users.
    """

    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer, PDFPassthroughRenderer]

    def get(self, request, pk):
        order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk)
        user = request.user
        if order.user_id != user.id and not (
            user.is_staff or user.type in (UserType.ADMIN, UserType.SUPERUSER)
        ):
            return Response(
                {"detail": _("You do not have permission to view this invoice.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        pdf_bytes = generate_invoice_pdf(order)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="invoice_{order.order_number}.pdf"'
        )
        return response


def _reorder_unavailable_reason(variant):
    """
    Why `variant` can't be put back in a cart, or None if it can.

    Must agree with what the cart itself accepts
    (cart.serializers.CartItemSerializer.validate_variant_id: active, in stock,
    and not past its expiration_date; a NULL date is not "expired"). The expiry
    rule matters because deactivate_expired_variants only runs nightly, so an
    expired variant can still be is_active=True for hours. The messages reuse
    the cart's own (already translated) strings.

    Returns (reason_code, message).
    """
    if variant is None or not variant.is_active:
        return "unavailable", _("This product variant is unavailable.")
    if variant.expiration_date is not None and variant.expiration_date < (
        timezone.now().date()
    ):
        return "unavailable", _(
            "This product has expired and is no longer available for purchase."
        )
    if variant.stock < 1:
        return "out_of_stock", _("This product variant is out of stock.")
    return None


class OrderReorderView(APIView):
    """
    POST /api/orders/<id>/reorder/ → put a past order's items back in the cart.

    Always partly succeeds: every item that can be bought again is added and
    the rest are listed with a reason, so one discontinued item never blocks
    the whole reorder (same pattern as the wishlist "move all to cart").
    A historical item can fail three ways: its variant was deleted
    (OrderItem.variant is SET_NULL), deactivated/expired, or is out of stock.

    Quantities are added to whatever is already in the cart for that variant.
    They are NOT capped at current stock: the cart doesn't cap either, and
    checkout's stock lock is the authoritative check.

    Only the order's owner can reorder it; anyone else (and guest orders,
    which have no owner) gets 404, same as not existing.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk, user=request.user)
        cart = get_or_create_cart(request)

        added, unavailable = [], []
        with transaction.atomic():
            for item in order.items.select_related("variant", "variant__product"):
                variant = item.variant
                problem = _reorder_unavailable_reason(variant)
                if problem:
                    code, message = problem
                    unavailable.append(
                        {
                            "product_name": item.product_name,
                            "reason": message,
                            "reason_code": code,
                        }
                    )
                    continue
                cart_item, created = CartItem.objects.get_or_create(
                    cart=cart, variant=variant, defaults={"quantity": item.quantity}
                )
                if not created:
                    # F() so a concurrent add can't be overwritten by a stale read.
                    CartItem.objects.filter(pk=cart_item.pk).update(
                        quantity=F("quantity") + item.quantity,
                        updated_at=timezone.now(),
                    )
                added.append(item.product_name)

        return Response(
            {"added_count": len(added), "added": added, "unavailable": unavailable},
            status=status.HTTP_200_OK,
        )
