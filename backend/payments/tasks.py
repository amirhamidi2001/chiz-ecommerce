"""
Payment reconciliation (Task 6.5.1.1).

A PaymentTransaction can get stuck PENDING indefinitely if the customer
never returns from the gateway's hosted page at all (closes the tab,
loses connectivity, etc.) — PaymentCallbackView (Task 6.2.1.4/6.2.1.5)
only ever runs if the gateway actually calls back, which won't happen
for a truly abandoned session. Left alone, that leaves the order stuck
PENDING forever with stock permanently reserved against it.

This periodic task finds PaymentTransaction rows PENDING for longer
than a configurable threshold and actively re-verifies each one against
its gateway — checking for the rarer but real case where the callback
silently failed to reach this platform even though payment actually
succeeded, not just assuming abandonment. Either way, it finalizes the
transaction one way or the other using the exact same shared logic
PaymentCallbackView uses (payments.services.process_verification_result)
— see that module's docstring for why this must be the SAME function,
not a second copy, and why that function's own locking matters
specifically for this task (a stuck transaction could, in a rare race,
be in the middle of receiving a genuine callback at the moment this task
runs).
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .gateways import get_payment_gateway
from .models import PaymentTransaction
from .services import process_verification_result

logger = logging.getLogger(__name__)


@shared_task
def reconcile_stuck_payment_transactions():
    cutoff = timezone.now() - timedelta(
        minutes=settings.PAYMENT_RECONCILIATION_THRESHOLD_MINUTES
    )
    stuck = PaymentTransaction.objects.filter(
        status=PaymentTransaction.Status.PENDING, created_at__lt=cutoff
    ).select_related("order")

    reconciled_success = 0
    reconciled_failed = 0
    still_pending = 0

    for txn in stuck:
        try:
            gateway_instance = get_payment_gateway(txn.gateway)
        except Exception as exc:  # noqa: BLE001 — see comment below
            # A gateway that's since been removed/misconfigured
            # shouldn't crash the whole reconciliation run and leave
            # every OTHER stuck transaction unreconciled — skip this one
            # and keep going, but log it: a transaction we can no longer
            # even attempt to reconcile is exactly the kind of thing
            # that needs a human to notice.
            logger.error(
                "Cannot reconcile PaymentTransaction %s for order %s: "
                "gateway %r is unavailable: %s",
                txn.pk,
                txn.order.order_number,
                txn.gateway,
                exc,
            )
            still_pending += 1
            continue

        # Same network-call-before-lock reasoning as PaymentCallbackView
        # (Task 6.2.1.5): verify_payment() is a network call, and
        # process_verification_result() below is what actually acquires
        # the row lock — kept separate here for the same reason.
        result = gateway_instance.verify_payment(
            authority=txn.authority, amount=txn.order.total
        )

        final_txn = process_verification_result(
            txn.gateway, txn.authority, success=result.success, result=result
        )

        if final_txn.status == PaymentTransaction.Status.SUCCESS:
            if result.success:
                # This is the recovery case this task exists for: the
                # gateway confirms the payment actually succeeded, even
                # though no callback ever arrived here. Worth its own
                # log line — a pattern of these is a sign the callback
                # URL itself may be unreachable from the gateway's side,
                # not just individually abandoned checkouts.
                logger.warning(
                    "Reconciliation recovered a SUCCESSFUL payment for "
                    "order %s (gateway %r, authority %s) that never "
                    "received a callback.",
                    txn.order.order_number,
                    txn.gateway,
                    txn.authority,
                )
            reconciled_success += 1
        elif final_txn.status == PaymentTransaction.Status.FAILED:
            reconciled_failed += 1
        else:
            # Still PENDING: process_verification_result() found the
            # transaction was no longer PENDING by the time it acquired
            # the lock (e.g. a genuine callback landed a moment ago) —
            # nothing to count as this task's own doing.
            still_pending += 1

    logger.info(
        "Payment reconciliation run: %s success, %s failed, %s left pending.",
        reconciled_success,
        reconciled_failed,
        still_pending,
    )
    return f"Reconciled: {reconciled_success} success, {reconciled_failed} failed."
