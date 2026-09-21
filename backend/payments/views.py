import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from order.models import Order
from order.services.stock import release_reserved_stock
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .gateways import get_payment_gateway
from .models import PaymentGatewayConfig, PaymentTransaction
from .serializers import PaymentInitiateSerializer

logger = logging.getLogger(__name__)


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

        # Task 6.3.1.3: PRIMARY choice now comes from a database-backed,
        # admin-editable singleton (PaymentGatewayConfig) rather than the
        # settings-only DEFAULT_PAYMENT_GATEWAY — so an admin can react to
        # a gateway outage by changing the active gateway at runtime, no
        # env var change or redeploy needed. get_solo()'s get_or_create
        # already falls back to this model field's own default
        # (Gateway.ZARINPAL) the first time it's ever called — e.g.
        # immediately after a fresh deploy, before any admin has touched
        # this config — which happens to match settings.
        # DEFAULT_PAYMENT_GATEWAY's own default ("zarinpal"), so no extra
        # glue code is needed to keep them in sync for the common case.
        gateway_config = PaymentGatewayConfig.get_solo()
        gateway_chain = [gateway_config.active_gateway]
        for candidate in gateway_config.fallback_order:
            if candidate not in gateway_chain:
                gateway_chain.append(candidate)

        result = None
        succeeded_with = None
        attempted = []

        for gateway_name in gateway_chain:
            try:
                gateway = get_payment_gateway(gateway_name)
            except ImproperlyConfigured as exc:
                # A misconfigured/typo'd entry in fallback_order (or a
                # gateway class that no longer exists) shouldn't take
                # down the whole initiate flow — skip it and keep trying
                # the rest of the chain, but log it: a bad config entry
                # sitting there silently is exactly the kind of thing
                # that should be noticed before it matters.
                logger.warning(
                    "Payment gateway %r in the configured chain for order "
                    "%s is misconfigured, skipping: %s",
                    gateway_name,
                    order.order_number,
                    exc,
                )
                continue

            callback_url = request.build_absolute_uri(
                reverse("payments:callback", kwargs={"gateway": gateway_name})
            )
            result = gateway.request_payment(
                amount=order.total,
                callback_url=callback_url,
                description=f"Order {order.order_number}",
            )
            attempted.append(gateway_name)

            if result.success:
                succeeded_with = gateway_name
                break

            logger.warning(
                "Payment gateway %r failed to initiate for order %s: %s",
                gateway_name,
                order.order_number,
                result.error_message,
            )

        if succeeded_with is None:
            # Every gateway in the chain failed (or the chain was empty/
            # entirely misconfigured) — this operational visibility
            # matters: a string of failures across the whole fallback
            # chain is a strong signal of a genuine multi-gateway outage,
            # not a one-off blip.
            logger.error(
                "All configured payment gateways failed to initiate for "
                "order %s. Attempted, in order: %s",
                order.order_number,
                attempted or "(none — chain was empty or fully misconfigured)",
            )
            # 502, not 400/500: this is a failed call to an external
            # dependency (the gateway), not a client input error or a
            # bug on our side.
            error_message = (
                result.error_message if result else "Payment initiation failed."
            )
            return Response(
                {"detail": error_message or "Payment initiation failed."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if len(attempted) > 1:
            logger.info(
                "Payment gateway fallback succeeded for order %s: %r worked "
                "after %s failed first.",
                order.order_number,
                succeeded_with,
                attempted[:-1],
            )
        else:
            logger.info(
                "Payment initiated via %r for order %s.",
                succeeded_with,
                order.order_number,
            )

        PaymentTransaction.objects.create(
            order=order,
            gateway=succeeded_with,
            authority=result.authority,
            amount=order.total,
            status=PaymentTransaction.Status.PENDING,
        )

        return Response(
            {"redirect_url": result.redirect_url}, status=status.HTTP_200_OK
        )


class PaymentCallbackView(APIView):
    """
    GET /api/payments/callback/<gateway>/

    The gateway itself redirects the customer's browser here after they
    complete (or abandon) payment on its hosted page. The redirect's
    query params (e.g. ?Authority=...&Status=OK) are client-controlled —
    a forged "success" redirect proves nothing — so the only trustworthy
    confirmation is a server-to-server verify_payment() call against the
    gateway. See module/task notes for why AllowAny is correct here: the
    caller is the gateway's redirect (via the customer's browser), not an
    authenticated API consumer, so there's no user session to require.
    """

    permission_classes = [AllowAny]

    def get(self, request, gateway):
        try:
            gateway_instance = get_payment_gateway(gateway)
        except ImproperlyConfigured:
            # Unknown/misconfigured gateway name in the URL itself (e.g.
            # a stale callback URL for a gateway that's since been
            # removed from PAYMENT_GATEWAY_CLASSES) — there's no
            # transaction to look up without knowing which gateway's
            # authority format to expect, so this is the earliest
            # possible failure point.
            return redirect(
                f"{settings.FRONTEND_URL}/checkout/failed?reason=unknown_transaction"
            )

        # Task 6.3.1.4: extraction of this gateway's own callback
        # query-parameter convention (ZarinPal's Authority/Status=NOK,
        # Zibal's trackId/success, IDPay's id+order_id/status=1 — three
        # genuinely different shapes) now lives on the gateway itself via
        # extract_callback_params(), not hardcoded here. This view no
        # longer knows or cares which gateway's parameter names it's
        # looking at.
        params = gateway_instance.extract_callback_params(request)
        authority = params["authority"]
        is_customer_cancelled = params["is_customer_cancelled"]

        # Unlocked read: only used (a) to short-circuit an unknown
        # authority before touching any lock, and (b) as a fast-path
        # optimization for the common already-processed case (customer
        # hit back/refresh on the confirmation page) so we skip an
        # unnecessary verify_payment() network call. This read is NOT
        # what guarantees correctness under concurrent duplicate
        # callbacks — see _process_verification_result() below, which
        # re-fetches under select_for_update() and is the only place
        # that's actually allowed to decide "yes, apply this write."
        try:
            txn = PaymentTransaction.objects.select_related("order").get(
                gateway=gateway, authority=authority
            )
        except PaymentTransaction.DoesNotExist:
            return redirect(
                f"{settings.FRONTEND_URL}/checkout/failed?reason=unknown_transaction"
            )

        if txn.status != PaymentTransaction.Status.PENDING:
            if txn.status == PaymentTransaction.Status.SUCCESS:
                return redirect(
                    f"{settings.FRONTEND_URL}/order-confirmation/{txn.order.id}"
                )
            return redirect(
                f"{settings.FRONTEND_URL}/checkout/failed?reason=already_failed"
            )

        if is_customer_cancelled:
            # Gateway itself reports the customer cancelled/failed before
            # even reaching verification — no need to call verify_payment
            # for a known-cancelled flow. What "reports cancelled" means
            # is entirely gateway-specific (see extract_callback_params()
            # on each concrete gateway) — this view just trusts the
            # normalized boolean.
            final_txn = self._process_verification_result(
                gateway, authority, success=False
            )
            return self._redirect_for_failure(final_txn, reason="cancelled")

        # IMPORTANT: verify_payment() is a network call to the gateway —
        # deliberately made BEFORE acquiring any row lock. Holding a DB
        # lock across a slow external HTTP call would tie up a DB
        # connection/lock for however long the gateway takes to respond,
        # which is worth avoiding. In the rare case of two near-
        # simultaneous callbacks for the same authority, this means
        # verify_payment() may genuinely be called twice — that's fine,
        # since every gateway's verify endpoint is itself idempotent
        # (Task 6.2.1.3/6.3.1.1/6.3.1.2: ZarinPal code 101, Zibal result
        # 201, IDPay status 101/200 = "already verified"). Only the
        # DATABASE mutation below — the part that must never happen
        # twice — is guarded by the lock.
        result = gateway_instance.verify_payment(
            authority=authority, amount=txn.order.total
        )

        if result.success:
            final_txn = self._process_verification_result(
                gateway, authority, success=True, result=result
            )
            if final_txn.status == PaymentTransaction.Status.SUCCESS:
                return redirect(
                    f"{settings.FRONTEND_URL}/order-confirmation/{final_txn.order.id}"
                )
            return self._redirect_for_failure(final_txn, reason="already_failed")

        final_txn = self._process_verification_result(gateway, authority, success=False)
        return self._redirect_for_failure(final_txn, reason="verification_failed")

    def _redirect_for_failure(self, txn, reason):
        """
        Build the failure redirect for a transaction that ended up FAILED.
        `reason` reflects THIS request's own path (cancelled/
        verification_failed/already_failed) — in the extremely rare case
        where a concurrent request settled the outcome for a different
        reason than this one observed, the persisted STATE is still
        guaranteed correct and singular (see _process_verification_result);
        only the cosmetic redirect-reason query param could, in theory,
        reflect this request's path rather than whichever request won the
        race, which has no functional consequence.
        """
        if txn.status == PaymentTransaction.Status.SUCCESS:
            return redirect(
                f"{settings.FRONTEND_URL}/order-confirmation/{txn.order.id}"
            )
        return redirect(f"{settings.FRONTEND_URL}/checkout/failed?reason={reason}")

    def _process_verification_result(self, gateway, authority, success, result=None):
        """
        The ONLY place allowed to mutate a PaymentTransaction's status.

        Locks the transaction row (select_for_update()) and re-checks its
        status BEFORE writing, all inside one atomic block — mirroring
        the exact lock-then-check-then-act pattern used for stock in
        Epic 1 Task 1.1.1.2/1.1.1.3. This closes the race that a plain
        `if txn.status != PENDING` check (Task 6.2.1.4) leaves open: two
        near-simultaneous callbacks could both read PENDING before either
        finishes writing. With the lock, only one request's write can
        ever land per transaction row — the other blocks here until the
        first commits, then sees status != PENDING and takes the
        early-return path below, applying nothing.

        Returns the transaction as it stands after this call — which may
        reflect a DIFFERENT request's write (if this one lost the race),
        not necessarily the `success`/`result` passed in here.
        """
        with transaction.atomic():
            txn = (
                PaymentTransaction.objects.select_for_update()
                .select_related("order")
                .get(gateway=gateway, authority=authority)
            )

            if txn.status != PaymentTransaction.Status.PENDING:
                # Lost the race: another request already processed this
                # transaction while we were (a) blocked waiting for this
                # lock, or (b) off making our own verify_payment() call.
                # Apply nothing — the winner's write already happened.
                return txn

            if success:
                txn.status = PaymentTransaction.Status.SUCCESS
                txn.ref_id = result.ref_id
                txn.raw_callback_payload = result.raw_response
                txn.save()
                # Stock was already decremented at order-creation time
                # (Epic 1/3's flow, before the customer ever reached the
                # gateway) — nothing to touch here regarding stock; this
                # transition is purely a status change.
                txn.order.status = Order.Status.PROCESSING
                txn.order.save(update_fields=["status"])

                # Task 6.4.1.2: the cart is cleared HERE, on confirmed
                # payment success — not at order-creation time (moved out
                # of OrderCreateSerializer.create(); see that method's
                # comment). Clearing it at order-creation meant a customer
                # whose payment failed or who cancelled lost their cart
                # entirely, with no easy way to reorder, even though their
                # order was correctly cancelled and stock released below.
                # Addressed via order.user rather than request.user/session
                # — this view is AllowAny and reached via the gateway's
                # redirect, so relying on order.user (set at order-creation
                # time) is more robust than assuming any particular session
                # state on this specific request.
                cart = getattr(txn.order.user, "cart", None)
                if cart is not None:
                    cart.items.all().delete()
            else:
                txn.status = PaymentTransaction.Status.FAILED
                txn.save(update_fields=["status"])

                order = txn.order
                if order.status == Order.Status.PENDING:
                    order.status = Order.Status.CANCELLED
                    order.save(update_fields=["status"])
                    release_reserved_stock(
                        order,
                        actor=None,  # system-triggered, not an admin/user action
                        note=f"Payment failed for order {order.order_number}",
                    )

            return txn
