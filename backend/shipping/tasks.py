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
"""

from celery import shared_task


@shared_task
def poll_shipment_tracking():
    from django.utils import timezone

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
            if shipment.status == Shipment.Status.DELIVERED:
                # Advance the order's own status too, once Epic 8's
                # order-lifecycle state machine exists — for now, since
                # Order.Status already has a DELIVERED value (it does, per
                # the original model), set it directly here.
                order = shipment.order
                order.status = order.Status.DELIVERED
                order.save(update_fields=["status"])
    return f"Updated {updated_count} shipment(s)."
