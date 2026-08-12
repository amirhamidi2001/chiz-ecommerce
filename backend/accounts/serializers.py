import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .tokens import password_reset_token

User = get_user_model()


# ─── Register ─────────────────────────────────────────────────────────────────


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(required=True, write_only=True)
    last_name = serializers.CharField(required=True, write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
        )
        # Update the auto-created profile
        profile = user.profile
        profile.first_name = first_name
        profile.last_name = last_name
        profile.save(update_fields=["first_name", "last_name"])
        return user


# ─── Profile (accounts app — used by ProfileView) ─────────────────────────────


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    is_verified = serializers.BooleanField(source="user.is_verified", read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        from accounts.models import Profile  # local import avoids circular

        model = Profile
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "avatar_url",
            "order_updates",
            "promotions",
            "newsletter",
            "is_verified",
        ]
        read_only_fields = ["id", "email", "is_verified", "avatar_url"]

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            return (
                request.build_absolute_uri(obj.image.url) if request else obj.image.url
            )
        return None

    def validate_phone_number(self, value):
        if value:
            # Basic phone number validation – adapt regex to your requirements
            if not re.match(r"^\+?1?\d{9,15}$", value):
                raise serializers.ValidationError("Enter a valid phone number.")
        return value


# ─── Current user (used by GET /api/auth/user/) ───────────────────────────────


class CurrentUserSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer returned by GET /api/auth/user/.

    AuthContext reads:
      • user.type          → isAdmin check  (type 2 = Admin, 3 = Superuser)
      • user.is_verified   → verified badge
      • user.first_name    → greeting / sidebar display name
      • user.last_name
      • user.avatar_url    → sidebar avatar
    """

    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone_number",
            "type",
            "is_verified",
            "is_active",
            "is_staff",
            "first_name",
            "last_name",
            "avatar_url",
        ]
        read_only_fields = fields

    def _profile(self, obj):
        try:
            return obj.profile
        except Exception:
            return None

    def get_first_name(self, obj):
        p = self._profile(obj)
        return p.first_name if p else ""

    def get_last_name(self, obj):
        p = self._profile(obj)
        return p.last_name if p else ""

    def get_avatar_url(self, obj):
        request = self.context.get("request")
        p = self._profile(obj)
        if p and p.image and hasattr(p.image, "url"):
            return request.build_absolute_uri(p.image.url) if request else p.image.url
        return None


# ─── Change password ──────────────────────────────────────────────────────────


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        user = self.context["request"].user
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": e.messages})
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


# ─── Password reset request ───────────────────────────────────────────────────


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        return value.lower().strip()

    def get_user(self):
        try:
            return User.objects.get(email=self.validated_data["email"])
        except User.DoesNotExist:
            return None


# ─── Password reset confirm ───────────────────────────────────────────────────


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        # Decode UID
        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError({"uid": "Invalid reset link."})

        # Validate token
        if not password_reset_token.check_token(user, attrs["token"]):
            raise serializers.ValidationError(
                {"token": "Reset link is invalid or has expired."}
            )

        # Validate passwords match
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        validate_password(attrs["new_password"], user)
        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user
