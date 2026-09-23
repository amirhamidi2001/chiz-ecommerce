"""
Shared PaymentTransaction finalization logic (Task 6.5.1.1).

Extracted out of PaymentCallbackView (Tasks 6.2.1.4/6.2.1.5/6.4.1.2),
which previously carried the ONLY copy of this logic inline as
`_process_verification_result()`. This task's reconciliation Celery
task needs the exact same finalization behavior — same order-status
transition, same stock release on failure, same cart-clearing on
success — for transactions that got stuck PENDING because the customer
never returned from the gateway at all. Duplicating that logic a second
time for the Celery task would leave two independently-maintained
copies of financially important code that could drift out of sync; this
module is the one place both callers now depend on.

Two levels are provided:

- `finalize_transaction_success()` / `finalize_transaction_failure()`:
  pure mutation functions. They assume the caller has ALREADY locked
  the PaymentTransaction row (select_for_update()) and confirmed its
  status is still PENDING — they do not re-check or re-lock anything
  themselves.
- `process_verification_result()`: the orchestrator both
  PaymentCallbackView and the Celery task actually call. It owns the
  select_for_update()-locked fetch + check-then-act sequence (mirroring
  the exact lock-then-check-then-act pattern used for stock in Epic 1
  Task 1.1.1.2/1.1.1.3) and delegates the actual mutation to the two
  functions above. Centralizing the locking here — rather than in the
  two mutation functions' example signatures the task described, which
  take an already-resolved `txn` — means the critical "only one writer
  ever wins" guarantee lives in exactly one place, so a future caller
  (like this Celery task) can't accidentally reuse the mutation logic
  without ALSO reusing the concurrency guard.

Why this matters for the Celery task specifically: a "stuck" PENDING
transaction the reconciliation task picks up could, in a rare but real
race, be in the middle of receiving a genuine callback from the gateway
at the very moment the task runs. Both racing to write final state is
the exact same class of bug Task 6.2.1.5 fixed for duplicate callbacks
— process_verification_result()'s lock means whichever one gets there
first wins, and the other sees status != PENDING and applies nothing.
"""

from django.db import transaction
from order.models import Order
from order.services.stock import release_reserved_stock


def finalize_transaction_success(txn, result):
    """
    Apply a confirmed-successful verification to `txn` and its order.

    Caller must already hold a lock on `txn` (select_for_update()) and
    have confirmed txn.status == PENDING — this function does not
    re-check either.
    """
    from .models import PaymentTransaction

    txn.status = PaymentTransaction.Status.SUCCESS
    txn.ref_id = result.ref_id
    txn.raw_callback_payload = result.raw_response
    txn.save()
    # Stock was already decremented at order-creation time (Epic 1/3's
    # flow, before the customer ever reached the gateway) — nothing to
    # touch here regarding stock; this transition is purely a status
    # change.
    txn.order.status = Order.Status.PROCESSING
    txn.order.save(update_fields=["status"])

    # Task 6.4.1.2: the cart is cleared HERE, on confirmed payment
    # success — not at order-creation time. Addressed via order.user
    # rather than request.user/session, since this function is called
    # from both an AllowAny HTTP view (no reliable session state) and a
    # Celery task (no request/session at all).
    cart = getattr(txn.order.user, "cart", None)
    if cart is not None:
        cart.items.all().delete()


def finalize_transaction_failure(txn):
    """
    Apply a confirmed-failed/cancelled verification to `txn` and its
    order, releasing any stock reserved at order-creation time.

    Caller must already hold a lock on `txn` (select_for_update()) and
    have confirmed txn.status == PENDING — this function does not
    re-check either.
    """
    from .models import PaymentTransaction

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


def process_verification_result(gateway, authority, success, result=None):
    """
    The ONLY place allowed to mutate a PaymentTransaction's status.

    Locks the transaction row (select_for_update()) and re-checks its
    status BEFORE writing, all inside one atomic block. Only one
    caller's write can ever land per transaction row — anyone else
    blocks here until the first commits, then sees status != PENDING
    and takes the early-return path below, applying nothing.

    Used by both PaymentCallbackView (a real gateway callback arriving)
    and payments.tasks.reconcile_stuck_payment_transactions (proactively
    re-verifying a transaction that never got a callback at all) — see
    module docstring for why both need the same locking, not just the
    same mutation logic.

    Returns the transaction as it stands after this call — which may
    reflect a DIFFERENT caller's write (if this one lost the race), not
    necessarily the `success`/`result` passed in here.
    """
    from .models import PaymentTransaction

    with transaction.atomic():
        txn = (
            PaymentTransaction.objects.select_for_update()
            .select_related("order")
            .get(gateway=gateway, authority=authority)
        )

        if txn.status != PaymentTransaction.Status.PENDING:
            # Lost the race: something else already processed this
            # transaction while we were (a) blocked waiting for this
            # lock, or (b) off making our own verify_payment() call.
            # Apply nothing — the winner's write already happened.
            return txn

        if success:
            finalize_transaction_success(txn, result)
        else:
            finalize_transaction_failure(txn)

        return txn
