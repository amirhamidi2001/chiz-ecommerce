from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    ChangePasswordSerializer,
    CurrentUserSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    RegisterSerializer,
)
from .tokens import password_reset_token

User = get_user_model()


def _send_welcome_email(user):
    """Send a welcome email to a newly registered user."""
    subject = "Welcome! Your account is ready."
    message = render_to_string(
        "accounts/emails/welcome.html",
        {
            "first_name": user.profile.first_name,
            "email": user.email,
        },
    )
    send_mail(
        subject=subject,
        message=f"Hi {user.profile.first_name}, welcome! Your account is ready.",
        from_email=None,
        recipient_list=[user.email],
        html_message=message,
        fail_silently=True,
    )


def _send_password_reset_email(user, request):
    """Generate a reset link and email it to the user."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = password_reset_token.make_token(user)

    frontend_base = getattr(
        __import__("django.conf", fromlist=["settings"]).settings,
        "FRONTEND_URL",
        "http://localhost:3000",
    )
    reset_url = f"{frontend_base}/reset-password/{uid}/{token}/"

    subject = "Reset your password"
    message = render_to_string(
        "accounts/emails/password_reset.html",
        {"reset_url": reset_url, "first_name": user.profile.first_name},
    )
    send_mail(
        subject=subject,
        message=f"Reset your password here: {reset_url}",
        from_email=None,
        recipient_list=[user.email],
        html_message=message,
        fail_silently=True,
    )


# ─── Register ─────────────────────────────────────────────────────────────────


class RegisterView(APIView):
    """
    Body: { email, first_name, last_name, password }
    Returns: { email, first_name, last_name, access, refresh }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        _send_welcome_email(user)

        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "email": user.email,
                "first_name": user.profile.first_name,
                "last_name": user.profile.last_name,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


# ─── Login ────────────────────────────────────────────────────────────────────


class LoginView(TokenObtainPairView):
    """
    Body: { email, password }
    Returns: { access, refresh }
    """

    permission_classes = [AllowAny]


# ─── Current user  ←  NEW  ───────────────────────────────────────────────────


class CurrentUserView(APIView):
    """
    GET /api/auth/user/

    Returns the authenticated user's core fields.
    Called by AuthContext on every mount (token re-hydration) and
    immediately after login to populate the React user state.

    Response shape:
    {
        "id": 1,
        "email": "user@example.com",
        "type": 1,            ← AuthContext uses this for isAdmin check
        "is_verified": true,
        "is_active": true,
        "is_staff": false,
        "first_name": "Jane",
        "last_name": "Doe",
        "avatar_url": "http://…/media/profiles/jane.webp"
    }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CurrentUserSerializer(request.user, context={"request": request})
        return Response(serializer.data)


# ─── Profile ──────────────────────────────────────────────────────────────────


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/auth/profile/   → return logged-in user's profile
    PATCH /api/auth/profile/  → update first_name, last_name, phone_number,
                                    order_updates, promotions, newsletter
    """

    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]  # no PUT

    def get_object(self):
        return self.request.user.profile


# ─── Change password ──────────────────────────────────────────────────────────


class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/
    Body: { current_password, new_password, confirm_password }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Password updated successfully."},
            status=status.HTTP_200_OK,
        )


# ─── Password reset request ───────────────────────────────────────────────────


class PasswordResetRequestView(APIView):
    """
    Body: { email }
    Always returns 200 to prevent user enumeration.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.get_user()
        if user:
            _send_password_reset_email(user, request)

        return Response(
            {
                "detail": "If an account with that email exists, a reset link has been sent."
            },
            status=status.HTTP_200_OK,
        )


# ─── Password reset confirm ───────────────────────────────────────────────────


class PasswordResetConfirmView(APIView):
    """
    Body: { uid, token, new_password, confirm_password }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )
