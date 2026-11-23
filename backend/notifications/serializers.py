from rest_framework import serializers

from .models import UserNotification


class UserNotificationSerializer(serializers.ModelSerializer):
    """
    Customer-facing view of an inbox entry. Only ``is_read`` is writable —
    the message and its link are written by the system, never by the client.
    """

    class Meta:
        model = UserNotification
        fields = ["id", "event", "message", "link_url", "is_read", "created_at"]
        read_only_fields = ["id", "event", "message", "link_url", "created_at"]
