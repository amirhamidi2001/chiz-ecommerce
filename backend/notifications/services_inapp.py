"""
notifications/services_inapp.py
───────────────────────────────
The IN_APP channel sender, called (via a lazy import) by
notifications.services._send_single_channel().

Returns True when a UserNotification row was created and False when there was
nothing to attach one to (``user is None``). A False return is an expected
outcome, not a bug: SMS and email can reach a guest checkout through
context-supplied contact details, but an in-app inbox fundamentally needs a
real account.

After persisting, the notification is also pushed to the user's personal
Channels group (see notifications/consumers.py) so an open tab updates live.
The push is best-effort and never affects the return value: the row is the
source of truth, and clients re-sync from the REST endpoint on (re)connect.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from .consumers import notification_group_name
from .models import UserNotification

logger = logging.getLogger("notifications")


def create_in_app_notification(user, event, message, context) -> bool:
    if user is None:
        return False  # in-app notifications inherently require a real account
    link_url = _build_link_url(event, context)
    notification = UserNotification.objects.create(
        user=user, event=event, message=message, link_url=link_url
    )
    payload = {
        "id": notification.id,
        "event": str(event),
        "message": message,
        "link_url": link_url,
        "created_at": notification.created_at.isoformat(),
    }
    # on_commit: callers may be inside atomic(). Pushing early would let a
    # client re-fetch before the row is visible, and a rollback would leave a
    # live notification for a row that never existed. Outside a transaction
    # (autocommit) the callback runs immediately.
    user_id = user.id
    transaction.on_commit(lambda: _push_to_connected_user(user_id, payload))
    return True


def _push_to_connected_user(user_id, payload: dict) -> None:
    """
    group_send to the user's personal group. Delivers to nobody (harmlessly) if
    they have no open WebSocket. NEVER raises: a broker outage must not turn an
    already-persisted notification into a reported failure, and notify()'s
    callers are business-critical paths.

    async_to_sync is the right bridge here: this runs from synchronous code
    (DRF views under ASGI's threadpool, Celery tasks, signal handlers) while
    the channel layer API is async. It must NOT be called directly from a
    thread that has a running event loop — async callers use sync_to_async.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:  # CHANNEL_LAYERS not configured
            return
        async_to_sync(channel_layer.group_send)(
            notification_group_name(user_id),
            {"type": "notification.message", "payload": payload},
        )
    except Exception:  # noqa: BLE001 — see docstring
        logger.exception(
            "Could not push in-app notification %s to user %s over WebSocket",
            payload.get("id"),
            user_id,
        )


def _build_link_url(event, context) -> str:
    """
    Map an event's context to a sensible in-app destination, or "" when the
    context doesn't carry enough to build a *working* link.

    Both branches require the identifier they put in the URL: a link such as
    ``/order-confirmation//`` is worse than no link, because the click lands
    on a 404 page.
    """
    context = context or {}
    if context.get("order_number") and context.get("order_id"):
        return f"/order-confirmation/{context['order_id']}"
    if context.get("product_name") and context.get("product_slug"):
        return f"/product/{context['product_slug']}"
    return ""
