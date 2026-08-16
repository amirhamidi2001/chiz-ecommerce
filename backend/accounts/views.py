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
    OTPRequestSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    RegisterSerializer,
)
from .services.otp import OTPCooldownError, SMSDeliveryError, generate_otp
from .throttles import PhoneOTPRequestThrottle
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


# ─── OTP request ────────────────────────────────────────────────────────────────


class OTPRequestView(APIView):
    """
    POST /api/auth/otp/request/
    Body: { phone_number }

    Requests a one-time code be sent to `phone_number`. This single
    endpoint is used for BOTH login and registration — always requesting
    with purpose="login" here regardless of whether the phone belongs to
    an existing account. The login-vs-register split happens at
    verify-time instead (Task 2.3.1.2), not here: at request-time we
    don't yet know whether this is a new or returning user, and
    responding differently based on that (e.g. "no account found for
    this number" vs "code sent") would itself be a user-enumeration
    vector — the exact same reasoning PasswordResetRequestView above
    already follows for email.

    Always returns a generic 200 response with no indication of whether
    the phone number is registered — never the code itself, never a
    phone-number confirmation, never an "already registered" hint.
    """

    permission_classes = [AllowAny]
    throttle_classes = [PhoneOTPRequestThrottle]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]

        try:
            generate_otp(phone_number, purpose="login")
        except OTPCooldownError:
            return Response(
                {"detail": "Please wait before requesting another code."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except SMSDeliveryError:
            # generate_otp() already logged this at ERROR level for ops
            # visibility (Task 2.2.1.3). The OTPCode row still exists —
            # deliberately mask the delivery failure from the client and
            # respond exactly as if it succeeded, for the same
            # user-enumeration reasoning as the rest of this view: a
            # different response here could let an attacker infer things
            # about the phone number (e.g. "this number's carrier always
            # fails" vs "succeeds").
            pass

        return Response(
            {"detail": "Verification code sent."},
            status=status.HTTP_200_OK,
        )
