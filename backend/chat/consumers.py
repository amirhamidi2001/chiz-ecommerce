import json
import logging

from accounts.models import Profile
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from .models import ChatMessage, ChatRoom

logger = logging.getLogger(__name__)

# Max content length accepted from the client
MAX_MESSAGE_LENGTH = 4_000


class ChatConsumer(AsyncWebsocketConsumer):
    # ─── Lifecycle ────────────────────────────────────────────────────────

    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"chat_{self.room_id}"
        self.user = self.scope.get("user")

        # Reject unauthenticated connections
        if not self.user or isinstance(self.user, AnonymousUser):
            logger.warning("Unauthenticated WS rejected — room %s", self.room_id)
            await self.close(code=4001)
            return

        # Reject users who are not allowed in this room
        if not await self._can_access_room():
            logger.warning(
                "User %s denied access to room %s", self.user.pk, self.room_id
            )
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info("User %s connected to room %s", self.user.pk, self.room_id)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(
            "User %s disconnected from room %s (code=%s)",
            getattr(self.user, "pk", "?"),
            self.room_id,
            close_code,
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error("Invalid JSON payload.")
            return

        msg_type = data.get("type")
        if msg_type == "chat_message":
            await self._handle_chat_message(data)
        elif msg_type == "typing":
            await self._handle_typing(data)
        else:
            await self._send_error(f"Unknown message type: {msg_type!r}")

    # ─── Incoming message handlers ────────────────────────────────────────

    async def _handle_chat_message(self, data: dict):
        content = (data.get("content") or "").strip()
        if not content:
            await self._send_error("Message content cannot be empty.")
            return
        if len(content) > MAX_MESSAGE_LENGTH:
            await self._send_error(f"Message exceeds {MAX_MESSAGE_LENGTH} characters.")
            return

        message = await self._save_message(content)

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",  # → chat_message() below
                "id": message.pk,
                "content": message.content,
                "sender_id": self.user.pk,
                "sender_name": await self._get_display_name(),
                "is_agent": await self._is_agent(),
                "created_at": message.created_at.isoformat(),
            },
        )

    async def _handle_typing(self, data: dict):
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.typing",  # → chat_typing() below
                "sender_id": self.user.pk,
                "sender_name": await self._get_display_name(),
                "is_typing": bool(data.get("is_typing", False)),
            },
        )

    # ─── Channel-layer event handlers (group_send dispatches here) ────────

    async def chat_message(self, event: dict):
        """Broadcast a new message to this WebSocket client."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat_message",
                    "id": event["id"],
                    "content": event["content"],
                    "sender_id": event["sender_id"],
                    "sender_name": event["sender_name"],
                    "is_agent": event.get("is_agent", False),
                    "created_at": event["created_at"],
                }
            )
        )

    async def chat_typing(self, event: dict):
        """Forward typing indicators — skip the sender's own connection."""
        if event["sender_id"] != self.user.pk:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "typing",
                        "sender_id": event["sender_id"],
                        "sender_name": event["sender_name"],
                        "is_typing": event["is_typing"],
                    }
                )
            )

    # ─── Database helpers ─────────────────────────────────────────────────

    @database_sync_to_async
    def _can_access_room(self) -> bool:
        """Admins/agents may access any room; customers only their own."""
        try:
            room = ChatRoom.objects.get(pk=self.room_id)
        except ChatRoom.DoesNotExist:
            return False
        if self.user.is_staff or getattr(self.user, "type", 1) in (2, 3):
            return True
        return room.customer_id == self.user.pk

    @database_sync_to_async
    def _save_message(self, content: str) -> ChatMessage:
        """Persist the message and auto-assign an agent on first staff reply."""
        room = ChatRoom.objects.get(pk=self.room_id)
        is_staff = self.user.is_staff or getattr(self.user, "type", 1) in (2, 3)
        if is_staff and room.agent_id is None:
            room.agent = self.user
            room.status = ChatRoom.Status.ASSIGNED
            room.save(update_fields=["agent", "status", "updated_at"])
        return ChatMessage.objects.create(
            room=room,
            sender=self.user,
            content=content,
            message_type=ChatMessage.MessageType.TEXT,
        )

    @database_sync_to_async
    def _get_display_name(self) -> str:
        """Return user's full name from profile, or email if unavailable."""
        try:
            full = (
                f"{self.user.profile.first_name} {self.user.profile.last_name}".strip()
            )
            if full:
                return full
        except (Profile.DoesNotExist, AttributeError):
            pass
        return self.user.email

    @database_sync_to_async
    def _is_agent(self) -> bool:
        return self.user.is_staff or getattr(self.user, "type", 1) in (2, 3)

    # ─── Utility ──────────────────────────────────────────────────────────

    async def _send_error(self, message: str):
        await self.send(text_data=json.dumps({"type": "error", "message": message}))
