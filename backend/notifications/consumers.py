"""
notifications/consumers.py
──────────────────────────
Real-time delivery of in-app notifications over WebSocket.

A deliberately narrower sibling of chat/consumers.py: no rooms and no
client→server messages. Each authenticated user has exactly ONE personal
group (``notifications_<user_id>``); every open tab/device of that user joins
it, and ``create_in_app_notification()`` pushes to it with ``group_send``.

Authentication is NOT done here — core/asgi.py wraps this consumer in the same
``chat.middleware.JWTAuthMiddleware`` as the chat consumer, which resolves the
``?token=<access JWT>`` query param into ``scope["user"]``.

A push is best-effort: a user with no open socket simply misses it. The
notification is always persisted first (UserNotification), so clients re-sync
from ``GET /api/notifications/`` whenever they (re)connect.
"""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


def notification_group_name(user_id) -> str:
    """The one place that defines a user's personal notification group, so the
    consumer (subscriber) and services_inapp (publisher) can't drift apart."""
    return f"notifications_{user_id}"


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or isinstance(self.user, AnonymousUser):
            logger.warning("Unauthenticated notification WS rejected")
            await self.close(code=4001)
            return
        self.group_name = notification_group_name(self.user.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification_message(self, event):
        """Handler for messages sent to this user's group — the method
        name MUST match the 'type' key used when sending to the group
        (Channels converts 'notification.message' <-> this method
        name automatically)."""
        await self.send(text_data=json.dumps(event["payload"]))
