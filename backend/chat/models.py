import uuid

from django.conf import settings
from django.db import models


class ChatRoom(models.Model):
    """
    A support session between a customer and an agent.
    Created by the customer; assigned to an agent on first reply.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_rooms_as_customer",
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_rooms_as_agent",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    subject = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Room {self.id} — {self.customer.email} [{self.status}]"


class ChatMessage(models.Model):
    """
    A single message within a ChatRoom.
    Supports regular text and system notifications (e.g. "Agent joined").
    """

    class MessageType(models.TextChoices):
        TEXT = "text", "Text"
        SYSTEM = "system", "System"

    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages",
    )
    content = models.TextField()
    message_type = models.CharField(
        max_length=10,
        choices=MessageType.choices,
        default=MessageType.TEXT,
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        sender = getattr(self.sender, "email", "system")
        return f"[{self.room_id}] {sender}: {self.content[:50]}"
