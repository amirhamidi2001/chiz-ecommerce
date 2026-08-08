from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import ChatMessage, ChatRoom

User = get_user_model()


class SenderSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    is_agent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "full_name", "is_agent"]

    def get_full_name(self, obj) -> str:
        try:
            return obj.profile.get_fullname()
        except AttributeError:
            return obj.email

    def get_is_agent(self, obj) -> bool:
        return obj.is_staff or getattr(obj, "type", 1) in (2, 3)


class ChatMessageSerializer(serializers.ModelSerializer):
    sender = SenderSerializer(read_only=True)

    class Meta:
        model = ChatMessage
        fields = ["id", "content", "sender", "message_type", "is_read", "created_at"]
        read_only_fields = fields


class ChatRoomSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    customer_name = serializers.SerializerMethodField()
    agent_email = serializers.EmailField(
        source="agent.email", read_only=True, allow_null=True
    )
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            "id",
            "customer_email",
            "customer_name",
            "agent_email",
            "status",
            "subject",
            "last_message",
            "unread_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "customer_email",
            "customer_name",
            "agent_email",
            "created_at",
        ]

    def get_customer_name(self, obj) -> str:
        u = obj.customer
        try:
            return u.profile.get_fullname()
        except AttributeError:
            return u.email

    def get_last_message(self, obj) -> dict | None:
        msg = obj.messages.last()
        if not msg:
            return None
        return {
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
        }

    def get_unread_count(self, obj) -> int:
        user = self.context["request"].user
        return obj.messages.filter(is_read=False).exclude(sender=user).count()


class CreateChatRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatRoom
        fields = ["subject"]
