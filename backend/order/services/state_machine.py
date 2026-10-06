"""
Order-status state machine.

Single source of truth for which `Order.status` transitions are legal when
a status is changed through an API/service (currently the admin order
endpoint and `order.services.cancellation.cancel_order`).

Audit of every place the codebase writes `Order.status` (done when this
module was introduced):

    order/serializers.py   OrderCreateSerializer       -> PENDING (initial)
    payments/services.py   finalize_transaction_success PENDING -> PROCESSING
    payments/services.py   finalize_transaction_failure PENDING -> CANCELLED
                           (guarded by `order.status == PENDING`)
    order/views.py         OrderDetailView.patch        PENDING|PROCESSING -> CANCELLED
                           (now via cancel_order)
    shipping/tasks.py      poll_shipment_tracking       * -> DELIVERED
    dashboard (admin)      AdminOrderViewSet            any -> any (until now)

Nothing in the codebase ever sets SHIPPED except the admin endpoint, and
the carrier polling task sets DELIVERED directly -- in practice from
PROCESSING, because no automated step moves an order to SHIPPED first.
So PROCESSING -> DELIVERED is a real, legitimate transition and is part
of the map below. (The payment and shipping code paths write the field
directly and do not consult this map; see their call sites.)
"""

from order.models import Order

VALID_TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.PROCESSING, Order.Status.CANCELLED},
    Order.Status.PROCESSING: {
        Order.Status.SHIPPED,
        Order.Status.DELIVERED,  # carrier-confirmed delivery (shipping.tasks)
        Order.Status.CANCELLED,
    },
    Order.Status.SHIPPED: {Order.Status.DELIVERED},
    Order.Status.DELIVERED: set(),  # terminal
    Order.Status.CANCELLED: set(),  # terminal
}


def is_valid_transition(current: str, new: str) -> bool:
    if current == new:
        return True  # no-op re-submission of the same status is harmless
    return new in VALID_TRANSITIONS.get(current, set())
