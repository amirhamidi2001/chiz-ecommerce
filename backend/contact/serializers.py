from rest_framework import serializers

from .models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    subject = serializers.CharField(max_length=255)
    message = serializers.CharField()

    class Meta:
        model = ContactMessage
        fields = ["id", "name", "email", "subject", "message", "created_at"]
        read_only_fields = ["id", "created_at"]

    # ── field-level trimming ────────────────────────────────────────────────

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def validate_subject(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Subject is required.")
        return value

    def validate_message(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Message is required.")
        return value

    def validate_email(self, value: str) -> str:
        # EmailField already validates format; we only need to normalise.
        return value.strip().lower()
