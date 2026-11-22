import logging

from cart.services import merge_session_cart_into_user_cart
from dashboard.services import merge_session_wishlist_into_user_wishlist
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import translation
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext as _
from notifications.email import (
    DEFAULT_RECIPIENT_NAME,
    EMAIL_LANGUAGE,
    send_notification_email_task,
)
from notifications.models import NotificationTemplate
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    ChangePasswordSerializer,
    CurrentUserSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    RegisterSerializer,
)
from .services.otp import (
    OTPCooldownError,
    OTPExpiredError,
    OTPIncorrectCodeError,
    OTPMaxAttemptsExceededError,
    OTPNotFoundError,
    SMSDeliveryError,
    generate_otp,
    verify_otp,
)
from .throttles import AuthSensitiveRateThrottle, PhoneOTPRequestThrottle
from .tokens import password_reset_token

User = get_user_model()

logger = logging.getLogger(__name__)


def _queue_email(**kwargs):
    """
    Queue an email on Celery — off the request path, so a slow or down SMTP
    server can no longer slow or fail the request.

    Never raises. Registration must not fail because an email couldn't be
    queued (the old inline send used fail_silently=True for the same reason),
    and the password-reset view must stay indistinguishable for known and
    unknown addresses: an error only for existing accounts would reveal them.
    """
    try:
        send_notification_email_task.delay(**kwargs)
    except Exception:  # noqa: BLE001 — see docstring
        logger.exception("Could not queue %s email", kwargs.get("event"))


def _send_welcome_email(user):
    """
    Queue a welcome email for a newly registered user.

    Subject and plain-text part are rendered here under EMAIL_LANGUAGE
    (Persian), not the request's language: the HTML (rendered by the task, also
    in Persian) is RTL Persian only, and a subject/fallback that followed an
    English Accept-Language header would contradict it.
    """
    first_name = user.profile.first_name or DEFAULT_RECIPIENT_NAME
    with translation.override(EMAIL_LANGUAGE):
        subject = _("Welcome! Your account is ready.")
        text_message = _("Hi %(first_name)s, welcome! Your account is ready.") % {
            "first_name": first_name
        }
    _queue_email(
        recipient=user.email,
        subject=subject,
        body_text=text_message,
        template_name="accounts/emails/welcome.html",
        context={
            "first_name": first_name,
            "email": user.email,
            "shop_url": settings.FRONTEND_URL,
        },
        event=NotificationTemplate.Event.WELCOME,
        user_id=user.pk,
    )


def _send_password_reset_email(user, request):
    """Generate a reset link and queue the email carrying it (Persian, see above)."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = password_reset_token.make_token(user)

    reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

    first_name = user.profile.first_name or DEFAULT_RECIPIENT_NAME
    with translation.override(EMAIL_LANGUAGE):
        subject = _("Reset your password")
        text_message = _("Reset your password here: %(url)s") % {"url": reset_url}
    _queue_email(
        recipient=user.email,
        subject=subject,
        body_text=text_message,
        template_name="accounts/emails/password_reset.html",
        context={"reset_url": reset_url, "first_name": first_name},
        event=NotificationTemplate.Event.PASSWORD_RESET,
        user_id=user.pk,
    )


# ─── Register ─────────────────────────────────────────────────────────────────


class RegisterView(APIView):
    """
    Body: { email, first_name, last_name, password }
    Returns: { email, first_name, last_name, access, refresh }
    """

    permission_classes = [AllowAny]
    # Tighter than the general anon rate — mass fake account creation is
    # a real, specific abuse vector for this endpoint (Task 2.4.1.4).
    throttle_classes = [AuthSensitiveRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        _send_welcome_email(user)
        merge_session_cart_into_user_cart(request, user)
        merge_session_wishlist_into_user_wishlist(request, user)

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
    # Tighter than the general anon rate — login is the classic
    # credential-stuffing target (Task 2.4.1.4). TokenObtainPairView
    # inherits DRF's normal APIView.throttle_classes machinery
    # unmodified (verified directly, not assumed — see
    # accounts/tests/test_views.py), so setting this here works exactly
    # like it does on a plain APIView.
    throttle_classes = [AuthSensitiveRateThrottle]

    def post(self, request, *args, **kwargs):
        # Mirrors rest_framework_simplejwt.views.TokenViewBase.post()
        # exactly (including its TokenError → InvalidToken handling) —
        # TokenObtainPairView doesn't expose the authenticated user in
        # the same way a plain APIView would (there's no request.user
        # set by the time post() runs; auth happens INSIDE the
        # serializer's validate()), so the user has to come from
        # serializer.user after is_valid() succeeds, which SimpleJWT's
        # TokenObtainSerializer sets internally.
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0]) from e

        merge_session_cart_into_user_cart(request, serializer.user)
        merge_session_wishlist_into_user_wishlist(request, serializer.user)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


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
            {"detail": _("Password updated successfully.")},
            status=status.HTTP_200_OK,
        )


# ─── Password reset request ───────────────────────────────────────────────────


class PasswordResetRequestView(APIView):
    """
    Body: { email }
    Always returns 200 to prevent user enumeration.
    """

    permission_classes = [AllowAny]
    # Tighter than the general anon rate — email-enumeration/spam is a
    # real abuse vector for this endpoint (Task 2.4.1.4).
    throttle_classes = [AuthSensitiveRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.get_user()
        if user:
            _send_password_reset_email(user, request)

        return Response(
            {
                "detail": _(
                    "If an account with that email exists, a reset link has been sent."
                )
            },
            status=status.HTTP_200_OK,
        )


# ─── Password reset confirm ───────────────────────────────────────────────────


class PasswordResetConfirmView(APIView):
    """
    Body: { uid, token, new_password, confirm_password }
    """

    permission_classes = [AllowAny]
    # Tighter than the general anon rate — same sensitive-endpoint
    # reasoning as PasswordResetRequestView above (Task 2.4.1.4);
    # guards against scripted token/uid guessing too.
    throttle_classes = [AuthSensitiveRateThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": _("Password has been reset successfully.")},
            status=status.HTTP_200_OK,
        )


# ─── OTP request ────────────────────────────────────────────────────────────────


class OTPRequestView(APIView):
    """
    POST /api/auth/otp/request/
    Body: { phone_number }

    Requests a one-time code be sent to `phone_number`. Used for BOTH
    login and registration — the login-vs-register split happens at
    verify-time instead, not here (revealing whether a phone is
    registered at request-time would itself be a user-enumeration
    vector, same reasoning as PasswordResetRequestView above).

    Always returns a generic 200 response with no indication of whether
    the phone number is registered.
    """

    permission_classes = [AllowAny]
    # Deliberately combining both: setting throttle_classes here
    # REPLACES DEFAULT_THROTTLE_CLASSES for this view entirely — DRF
    # does not merge per-view throttle_classes with the global defaults.
    # PhoneOTPRequestThrottle alone caps requests PER PHONE NUMBER
    # (3/10min), but does not cap the total volume of requests a single
    # client can make by cycling through many different phone numbers
    # (each gets its own fresh 3-request allowance) — AnonRateThrottle
    # adds a general, IP-based backstop (the project-wide "anon" rate)
    # against that kind of high-volume enumeration/scanning.
    throttle_classes = [PhoneOTPRequestThrottle, AnonRateThrottle]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]

        try:
            generate_otp(phone_number, purpose="login")
        except OTPCooldownError:
            return Response(
                {"detail": _("Please wait before requesting another code.")},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except SMSDeliveryError:
            pass

        return Response(
            {"detail": _("Verification code sent.")},
            status=status.HTTP_200_OK,
        )


# ─── OTP verify ─────────────────────────────────────────────────────────────────


class OTPVerifyView(APIView):
    """
    POST /api/auth/otp/verify/
    Body: { phone_number, code }
    Returns: { access, refresh, is_new_user }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        try:
            verify_otp(phone_number, purpose="login", submitted_code=code)
        except OTPNotFoundError:
            return Response(
                {
                    "code": _(
                        "No pending verification code found for this number. "
                        "Please request a new one."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except OTPExpiredError:
            return Response(
                {"code": _("This code has expired. Please request a new one.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except OTPMaxAttemptsExceededError:
            return Response(
                {"code": _("Too many incorrect attempts. Please request a new code.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except OTPIncorrectCodeError:
            return Response(
                {"code": _("Incorrect code.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(phone_number=phone_number).first()
        is_new_user = user is None

        if is_new_user:
            user = User.objects.create_user(
                email=None,
                phone_number=phone_number,
                is_verified=True,
            )
        elif not user.is_verified:
            user.is_verified = True
            user.save(update_fields=["is_verified"])

        merge_session_cart_into_user_cart(request, user)
        merge_session_wishlist_into_user_wishlist(request, user)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "is_new_user": is_new_user,
            },
            status=status.HTTP_201_CREATED if is_new_user else status.HTTP_200_OK,
        )
