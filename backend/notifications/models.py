import logging

from django.conf import settings
from django.db import models

logger = logging.getLogger("notifications")


class _SafeDict(dict):
    """Leave unknown ``{placeholder}`` tokens visibly intact when formatting."""

    def __missing__(self, key):
        return f"{{{key}}}"


class NotificationTemplate(models.Model):
    """
    Admin-editable message text, keyed by (channel, event).

    Seeded with Persian copy by migration 0002; staff can adjust the wording
    in the admin without a code deploy. Placeholders use ``str.format``
    syntax, e.g. ``{order_number}`` or ``{customer_name}``.
    """

    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        IN_APP = "in_app", "In-App"

    class Event(models.TextChoices):
        OTP_CODE = "otp_code", "OTP Verification Code"
        ORDER_CONFIRMED = "order_confirmed", "Order Confirmed"
        ORDER_STATUS_CHANGED = "order_status_changed", "Order Status Changed"
        SHIPPING_UPDATE = "shipping_update", "Shipping Update"
        BACK_IN_STOCK = "back_in_stock", "Back In Stock"
        PRICE_DROP = "price_drop", "Price Drop"
        WELCOME = "welcome", "Welcome"
        PASSWORD_RESET = "password_reset", "Password Reset"

    channel = models.CharField(max_length=10, choices=Channel.choices)
    event = models.CharField(max_length=30, choices=Event.choices)
    subject = models.CharField(
        max_length=200,
        blank=True,
        help_text="Email subject line. Ignored for SMS/in-app channels.",
    )
    body = models.TextField(
        help_text=(
            "Message body. Use {placeholder} syntax for dynamic values "
            "(e.g. {order_number}, {customer_name})."
        ),
    )
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("channel", "event")
        ordering = ["event", "channel"]

    def __str__(self):
        return f"{self.get_event_display()} — {self.get_channel_display()}"

    def render(self, context: dict) -> str:
        """
        Render ``body`` with ``context``.

        Never raises for template-content problems: a broken template must
        not stop the notification pipeline.

        * Missing placeholder keys are left in place as ``{key}`` (visible
          to an admin/developer) and a warning is logged.
        * A structurally malformed body (stray brace, positional ``{0}``,
          a format spec on a missing key, attribute access on a
          string, ...) is returned unrendered, with a warning.
        """
        return self._render_text(self.body, context)

    def render_subject(self, context: dict) -> str:
        """Same safe rendering as :meth:`render`, applied to ``subject``."""
        return self._render_text(self.subject, context) if self.subject else ""

    def _render_text(self, text: str, context: dict) -> str:
        try:
            return text.format(**context)
        except (KeyError, IndexError):
            logger.warning(
                "Template render for %s/%s missing context keys; "
                "sending partially unrendered.",
                self.channel,
                self.event,
            )
            try:
                return text.format_map(_SafeDict(context))
            except (ValueError, AttributeError, IndexError, TypeError):
                return self._render_failed(text)
        except (ValueError, AttributeError, TypeError):
            return self._render_failed(text)

    def _render_failed(self, text: str) -> str:
        logger.warning(
            "Template for %s/%s is malformed and could not be rendered; "
            "sending body unrendered.",
            self.channel,
            self.event,
        )
        return text


class NotificationLog(models.Model):
    """
    Audit record of one notification attempt: who, which channel/event, and
    whether it went out. Append-only — rows are written by the sending
    service and never edited; the admin is read-only. A notification that
    needed an SMS retry therefore shows as a RETRYING row followed, later, by
    its final SENT or FAILED row; an email shows as QUEUED followed by its
    outcome row.
    """

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        # FAILED is final: this notification never went out. A first SMS
        # failure that has a retry queued is RETRYING instead (the resolution
        # then arrives as a *later* SENT or FAILED row for the same message).
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"  # e.g. user opted out, or channel unavailable
        RETRYING = "retrying", "Retrying"  # failed once; a retry is queued
        # Email is sent by a Celery task, so notify() can only record that the
        # send was QUEUED; the task then appends the real outcome (SENT = the
        # mail server accepted it, or FAILED) as a later row.
        QUEUED = "queued", "Queued"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_logs",
    )
    channel = models.CharField(
        max_length=10, choices=NotificationTemplate.Channel.choices
    )
    event = models.CharField(max_length=30, choices=NotificationTemplate.Event.choices)
    recipient = models.CharField(
        max_length=255,
        help_text="Phone number, email address, or user ID depending on channel.",
    )
    status = models.CharField(max_length=10, choices=Status.choices)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [models.Index(fields=["user", "event", "-sent_at"])]

    def __str__(self):
        return f"{self.event} to {self.recipient} via {self.channel} — {self.status}"
