"""
Shipment tracking poll (Task 7.2.2.2).

Once a Shipment has a tracking_number, nothing keeps its status current on
its own — a customer-facing tracking widget (Task 7.2.2.3) needs
reasonably fresh status data, and the order's own fulfillment status
should advance automatically once a shipment is actually delivered. This
periodic task polls every carrier's track() method for every non-terminal
Shipment and updates accordingly.

Not real-time-critical the way payment reconciliation was (Epic 6 Task
6.5.1.1) — shipment status changing a few minutes/tens of minutes late is
a non-event, unlike a payment staying unreconciled. See the periodic-task
seed migration for the chosen interval.

IMPORTANT — status normalization (what this task does NOT do): each
concrete CarrierProvider.track() implementation (Tasks 7.2.1.2-7.2.1.5) is
responsible for mapping that carrier's own status vocabulary onto THIS
platform's Shipment.Status values before returning TrackingResult — see
shipping/providers/snapbox.py's and alopeyk.py's _STATUS_MAP for how
that's done (Post/Tipax's track() raise NotImplementedError instead, so
there's no mapping to do there). This task stays carrier-agnostic by
relying on that already having happened; it does not and should not
contain any carrier-specific string matching itself, which would defeat
the point of the CarrierProvider abstraction.

CUSTOMER NOTIFICATION (Epic 16): a detected status change in
SHIPMENT_STATUSES_TO_NOTIFY (see its comment for the reasoning) sends the
customer a SHIPPING_UPDATE via notifications.services.notify().
"""

from contextlib import nullcontext

from celery import shared_task

# WHICH STATUS CHANGES TEXT THE CUSTOMER (a deliberate cost/value decision).
#
# Every SHIPPING_UPDATE goes out as an SMS (a per-message Kavenegar cost) and an
# email, so each status is judged on whether the customer would act on it in
# real time:
#
#   out_for_delivery  YES — "be reachable, someone needs to receive it".
#   delivered         YES — the outcome they are waiting for.
#   failed            YES — the carrier cancelled/stopped the delivery (both
#                     polling carriers map their cancel/stop states here) and
#                     the customer must do something. Silence is the worst
#                     outcome, and it is rare, so it costs almost nothing.
#   in_transit        NO  — "picked up" for an on-demand courier is followed
#                     within the hour by the delivery itself; low value per SMS.
#                     (Unrecognised carrier statuses are normalised to
#                     in_transit too, so notifying here would also text on
#                     noise.) The tracking widget still shows it.
#   pending           NO  — nothing has happened yet.
#
# Note SnapBox has no out_for_delivery mapping at all, so for its shipments
# only delivered/failed ever fire. Adding or removing a status here is the only
# change needed to alter the policy.
SHIPMENT_STATUSES_TO_NOTIFY = frozenset({"out_for_delivery", "delivered", "failed"})


@shared_task
def poll_shipment_tracking():
    from django.utils import timezone
    from order.signals import suppress_status_notification

    from .models import Shipment
    from .providers import get_carrier_provider

    active_shipments = (
        Shipment.objects.exclude(
            status__in=[Shipment.Status.DELIVERED, Shipment.Status.FAILED]
        )
        .exclude(tracking_number="")
        .select_related("carrier", "order")
    )

    updated_count = 0
    for shipment in active_shipments:
        provider = get_carrier_provider(shipment.carrier.code)
        result = provider.track(shipment.tracking_number)
        if not result.success:
            # Transient failure (network error, carrier API hiccup, etc.)
            # — try again next run. Do NOT mark the shipment FAILED just
            # because one poll failed; that conflates "we couldn't check"
            # with "the carrier says this shipment failed", which are very
            # different things and would be a serious false signal to a
            # customer watching their tracking status.
            continue
        if result.status and result.status != shipment.status:
            shipment.status = result.status
            shipment.last_tracked_at = timezone.now()
            shipment.save(update_fields=["status", "last_tracked_at"])
            updated_count += 1
            notify_customer = shipment.status in SHIPMENT_STATUSES_TO_NOTIFY
            if shipment.status == Shipment.Status.DELIVERED:
                # Advance the order's own status too, once Epic 8's
                # order-lifecycle state machine exists — for now, since
                # Order.Status already has a DELIVERED value (it does, per
                # the original model), set it directly here.
                order = shipment.order
                order.status = order.Status.DELIVERED
                # The shipping update below already tells the customer it was
                # delivered; the generic "order status changed" message for
                # this same moment would be a second text.
                with (
                    suppress_status_notification(order)
                    if notify_customer
                    else nullcontext()
                ):
                    order.save(update_fields=["status"])
            if notify_customer:
                _notify_customer_of_shipment_update(shipment)
    return f"Updated {updated_count} shipment(s)."


def _notify_customer_of_shipment_update(shipment):
    """
    Send SHIPPING_UPDATE for `shipment`'s new status (after commit, like every
    other notify() call site: nothing is sent for a change that rolls back).

    The order's checkout contact details are passed explicitly: they are the
    only way to reach a guest order (order.user is None) and are what the
    customer entered otherwise. notify() never raises, so a failed send can't
    stop the polling loop.
    """
    from django.conf import settings
    from django.db import transaction
    from django.utils import translation
    from notifications.models import NotificationTemplate
    from notifications.services import notify

    order = shipment.order
    # Customer-facing text is Persian whatever language the worker runs in.
    with translation.override(settings.LANGUAGE_CODE):
        shipping_status = str(shipment.get_status_display())
    context = {
        "order_number": order.order_number,
        "shipping_status": shipping_status,
        "tracking_number": shipment.tracking_number,
        "customer_name": order.first_name,
        "email": order.email,
        "phone_number": order.phone,
    }
    user = order.user

    transaction.on_commit(
        lambda: notify(user, NotificationTemplate.Event.SHIPPING_UPDATE, context)
    )
