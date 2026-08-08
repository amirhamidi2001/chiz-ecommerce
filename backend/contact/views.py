import logging

from django.conf import settings
from django.core.mail import EmailMessage
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ContactMessageSerializer

logger = logging.getLogger(__name__)


class ContactCreateAPIView(APIView):
    """
    Public endpoint — no authentication required.

    POST /api/contact/
    Validates payload, persists the message, and dispatches an e-mail
    notification to the site owner (DEFAULT_FROM_EMAIL).
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # skip JWT/session auth entirely

    def post(self, request: Request) -> Response:
        serializer = ContactMessageSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        contact_message = serializer.save()
        self._send_notification(contact_message)

        return Response(
            {"message": "Message sent successfully"},
            status=status.HTTP_201_CREATED,
        )

    # ── private ────────────────────────────────────────────────────────────

    @staticmethod
    def _send_notification(contact_message) -> None:
        """
        Fire an e-mail to the site owner.  Failures are logged but never
        bubble up to the caller — a broken SMTP config must not prevent
        the user from seeing a success response after the DB write.
        """
        try:
            recipient = settings.DEFAULT_FROM_EMAIL
            subject = f"[Contact Form] {contact_message.subject}"
            body = (
                f"You have received a new contact form submission.\n\n"
                f"Name:    {contact_message.name}\n"
                f"Email:   {contact_message.email}\n"
                f"Subject: {contact_message.subject}\n\n"
                f"Message:\n{contact_message.message}\n\n"
                f"---\n"
                f"Submitted at {contact_message.created_at:%Y-%m-%d %H:%M UTC}"
            )

            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=recipient,  # many ESPs require from == account
                to=[recipient],
                reply_to=[contact_message.email],
            )
            email.send(fail_silently=False)

        except Exception:
            logger.exception(
                "Failed to send contact-form notification email " "(id=%s, from=%s)",
                contact_message.pk,
                contact_message.email,
            )
