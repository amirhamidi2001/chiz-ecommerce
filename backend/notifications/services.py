"""
notifications/services.py
─────────────────────────
`notify(user, event, context)` — the single entry point every
notification-triggering call site routes through.

It looks up the template for each target channel, renders it, hands it to the
channel's sender, and records one NotificationLog row per attempt.

THE CONTRACT THAT MATTERS: notify() NEVER raises. It is called from
business-critical paths (order status changes, stock movements, ...), and a
broken template, a provider outage or an SMTP timeout must never break the
operation that triggered it — an order must not fail to update because its
SMS failed to send. That is why this module catches ``Exception`` broadly at
the channel boundary (the one place in this codebase where that is right),
and why even the NotificationLog write is guarded: it runs in its own
savepoint, so a failed insert cannot poison a caller's ``atomic()`` block.

A clean SMS failure (provider returned False) is retried by a bounded Celery
task — see notifications/tasks.py and NO_SMS_RETRY_EVENTS.

Channel senders are imported lazily, inside the function that uses them:
  * notifications/email.py       (Feature 16.3) — send_notification_email()
  * notifications/services_inapp.py (Feature 16.4) — create_in_app_notification()
so this module imports cleanly before they exist and there is no circular-
import risk (they import from notifications.models themselves). Until a
sender module exists, that channel is logged as SKIPPED ("channel not
available"), not FAILED, so unbuilt channels don't light up the
"recent failures" admin filter.

Context placeholders
────────────────────
`notify()` adds ``customer_name`` (profile first name, else «مشتری») unless
the caller supplies one. Everything else comes from the call site; the
seeded templates (migrations 0002/0004) document the placeholder names.
"""

import importlib
import logging

from django.db import transaction

from .models import NotificationLog, NotificationTemplate

logger = logging.getLogger("notifications")

Channel = NotificationTemplate.Channel
Event = NotificationTemplate.Event

# «مشتری» = "customer" — reads naturally in "{customer_name} عزیز،".
DEFAULT_CUSTOMER_NAME = "مشتری"

# Events preference-gated by Profile.order_updates / Profile.promotions.
ORDER_UPDATE_EVENTS = (
    Event.ORDER_CONFIRMED,
    Event.ORDER_STATUS_CHANGED,
    Event.SHIPPING_UPDATE,
)
PROMOTION_EVENTS = (Event.BACK_IN_STOCK, Event.PRICE_DROP)
# Account/security mail: always email, not a preference.
TRANSACTIONAL_EMAIL_EVENTS = (Event.WELCOME, Event.PASSWORD_RESET)


# SMS events that must NOT be retried when the first send fails cleanly.
# An OTP code expires after OTP_CODE_TTL_SECONDS (120s) and the user has
# already been told it failed (and can request a new one after 60s), so a retry
# minutes later would deliver an expired or duplicate code — and the code would
# sit in the Celery broker payload meanwhile.
NO_SMS_RETRY_EVENTS = (Event.OTP_CODE,)


class ChannelUnavailable(Exception):
    """The channel's sender module isn't built/installed yet."""


def notify(user, event: str, context: dict, channels: list[str] | None = None):
    """
    Send a notification to `user` for `event`, rendering the appropriate
    template(s) with `context`, across all applicable channels (or a specific
    subset via `channels`), logging each attempt. Never raises.

    `user` may be None for notifications with no associated account (an OTP
    send before a User row exists, a guest-checkout order confirmation) — in
    that case `context` must supply an explicit recipient
    (``context["phone_number"]`` / ``context["email"]``).
    """
    try:
        user = _normalize_user(user)
        context = _with_defaults(user, context)
        if channels is None:
            target_channels = _default_channels_for(user, event, context)
        else:
            target_channels = list(channels)
    except Exception:  # noqa: BLE001 — notify() must never break its caller
        logger.exception("Notification setup failed: event=%s", event)
        return

    for channel in target_channels:
        try:
            _send_single_channel(user, event, channel, context)
        except Exception:  # noqa: BLE001 — one channel never blocks another
            logger.exception(
                "Unexpected notification error: event=%s channel=%s", event, channel
            )


def _normalize_user(user):
    """AnonymousUser / unsaved users can't be a FK target — treat as None."""
    if user is None or getattr(user, "pk", None) is None:
        return None
    return user


def _with_defaults(user, context: dict | None) -> dict:
    """Copy of `context` with ``customer_name`` filled in if absent."""
    context = dict(context or {})
    if "customer_name" not in context:
        profile = getattr(user, "profile", None)
        first_name = (getattr(profile, "first_name", "") or "").strip()
        context["customer_name"] = first_name or DEFAULT_CUSTOMER_NAME
    return context


def _default_channels_for(user, event: str, context: dict | None = None) -> list[str]:
    """
    Which channels a notification goes out on by default, respecting the
    user's notification preferences (Profile.order_updates / .promotions).

    * OTP is always SMS-only — it isn't a preference, it's how the user
      proves phone ownership.
    * Welcome / password-reset are always email — account mail, not marketing.
    * Order events (confirmed / status / shipping) → SMS + email when the user
      has `order_updates` on.
    * Back-in-stock / price-drop → email when the user has `promotions` on.
    * No user / no profile (e.g. guest checkout) → whichever recipient info
      is present in `context`.
    """
    context = context or {}

    if event == Event.OTP_CODE:
        return [Channel.SMS]
    if event in TRANSACTIONAL_EMAIL_EVENTS:
        return [Channel.EMAIL]

    profile = getattr(user, "profile", None) if user is not None else None
    if profile is None:
        channels = []
        if context.get("email"):
            channels.append(Channel.EMAIL)
        if context.get("phone_number"):
            channels.append(Channel.SMS)
        return channels

    if event in ORDER_UPDATE_EVENTS and profile.order_updates:
        return [Channel.SMS, Channel.EMAIL]
    if event in PROMOTION_EVENTS and profile.promotions:
        return [Channel.EMAIL]
    return []


def _resolve_recipient(user, channel: str, context: dict) -> str:
    if channel == Channel.SMS:
        return (
            context.get("phone_number")
            or (getattr(user, "phone_number", "") if user else "")
            or ""
        )
    if channel == Channel.EMAIL:
        return (
            context.get("email") or (getattr(user, "email", "") if user else "") or ""
        )
    if channel == Channel.IN_APP:
        return str(user.id) if user else ""
    return ""


def _log(user, channel, event, recipient, status, error_message=""):
    """
    Write one NotificationLog row without ever raising. The savepoint keeps a
    failed insert from aborting a transaction the caller is inside.
    """
    try:
        with transaction.atomic():
            return NotificationLog.objects.create(
                user=user,
                channel=channel,
                event=event,
                recipient=(recipient or "")[:255],
                status=status,
                error_message=error_message,
            )
    except Exception:  # noqa: BLE001
        logger.exception(
            "Could not write NotificationLog: event=%s channel=%s status=%s",
            event,
            channel,
            status,
        )
        return None


def _mark_failed(row, error_message) -> bool:
    """
    Turn a QUEUED row that never actually reached the queue into FAILED, in
    place, so the log never says "queued" for an email that was not. Returns
    False if there is no such row (or it couldn't be updated) so the caller
    appends a normal FAILED row instead.
    """
    if row is None:
        return False
    try:
        with transaction.atomic():
            NotificationLog.objects.filter(pk=row.pk).update(
                status=NotificationLog.Status.FAILED, error_message=error_message
            )
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Could not update NotificationLog row %s", row.pk)
        return False


def _load_sender(module_name: str, attribute: str):
    """
    Import a channel sender lazily. Only a missing *sender module itself*
    means "channel not built yet"; a ModuleNotFoundError from inside it is a
    real bug and propagates to be logged as FAILED.
    """
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise ChannelUnavailable(f"{module_name} is not available yet.") from exc
        raise
    return getattr(module, attribute)


def _send_single_channel(user, event, channel, context):
    recipient = _resolve_recipient(user, channel, context)

    try:
        template = NotificationTemplate.objects.get(
            channel=channel, event=event, is_active=True
        )
    except NotificationTemplate.DoesNotExist:
        _log(
            user,
            channel,
            event,
            recipient,
            NotificationLog.Status.SKIPPED,
            "No active template configured for this channel/event.",
        )
        return

    if not recipient:
        _log(
            user,
            channel,
            event,
            "",
            NotificationLog.Status.SKIPPED,
            "No recipient address available for this channel.",
        )
        return

    queued_row = None  # the QUEUED row written before an email is dispatched
    try:
        body = template.render(context)

        if channel == Channel.SMS:
            from .sms import get_sms_provider

            success = get_sms_provider().send(recipient, body)
        elif channel == Channel.EMAIL:
            send_notification_email = _load_sender(
                "notifications.email", "send_notification_email"
            )
            subject = template.render_subject(context) or event
            # Email is sent by a Celery task, so the sender only QUEUES it. The
            # QUEUED row is written BEFORE dispatch: a fast worker could
            # otherwise finish and log its SENT/FAILED outcome first, leaving
            # the log showing an already-delivered email as merely "queued".
            # If queueing then fails, that same row is corrected to FAILED.
            queued_row = _log(
                user,
                channel,
                event,
                recipient,
                NotificationLog.Status.QUEUED,
                "Queued for delivery; the outcome is logged by the email task.",
            )
            success = send_notification_email(
                recipient,
                subject,
                body,
                context,
                event=event,
                user_id=user.id if user else None,
            )
        elif channel == Channel.IN_APP:
            create_in_app_notification = _load_sender(
                "notifications.services_inapp", "create_in_app_notification"
            )
            success = create_in_app_notification(user, event, body, context)
        else:
            success = False
    except ChannelUnavailable as exc:
        _log(
            user,
            channel,
            event,
            recipient,
            NotificationLog.Status.SKIPPED,
            f"Channel not available: {exc}",
        )
        return
    except Exception as exc:  # noqa: BLE001 — deliberate: see module docstring
        logger.exception(
            "Notification send failed: event=%s channel=%s", event, channel
        )
        if not _mark_failed(queued_row, str(exc)):
            _log(
                user,
                channel,
                event,
                recipient,
                NotificationLog.Status.FAILED,
                str(exc),
            )
        return

    if success:
        # For email True only means "queued" and QUEUED was logged above; the
        # task appends the real outcome (SENT / FAILED) when it runs.
        if channel != Channel.EMAIL:
            _log(user, channel, event, recipient, NotificationLog.Status.SENT)
        return

    if _mark_failed(queued_row, "Provider reported failure."):
        return  # an email whose sender returned False was never queued

    # A clean SMS failure (provider returned False) gets a bounded retry via
    # Celery rather than an inline one, which would block the caller. Email and
    # in-app failures, exceptions (handled above) and OTP codes never retry.
    error_message = "Provider reported failure."
    if channel == Channel.SMS and event not in NO_SMS_RETRY_EVENTS:
        queued, detail = _queue_sms_retry(user, event, recipient, body)
        if queued:
            _log(
                user,
                channel,
                event,
                recipient,
                NotificationLog.Status.RETRYING,
                f"Provider reported failure; {detail}",
            )
            return
        error_message = f"Provider reported failure; {detail}"

    _log(
        user,
        channel,
        event,
        recipient,
        NotificationLog.Status.FAILED,
        error_message,
    )


def _queue_sms_retry(user, event, recipient, body) -> tuple[bool, str]:
    """
    Queue retry_sms_notification. Returns (queued, human-readable detail).

    Queueing can itself fail (broker down); that must not propagate, and the
    log must then say FAILED, not claim a retry that doesn't exist.
    """
    try:
        from .tasks import FIRST_RETRY_DELAY_SECONDS, retry_sms_notification

        retry_sms_notification.apply_async(
            kwargs={
                "recipient": recipient,
                "body": body,
                "event": event,
                "user_id": user.id if user else None,
            },
            countdown=FIRST_RETRY_DELAY_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 — never break the caller
        logger.exception("Could not queue SMS retry: event=%s", event)
        return False, f"retry could not be queued ({type(exc).__name__})."
    return True, f"retry queued (up to {retry_sms_notification.max_retries} retries)."
