"""
notifications/tasks.py
──────────────────────
Bounded retry for SMS notifications that failed cleanly on the first attempt.

notify() (services.py) queues `retry_sms_notification` when the SMS provider
returns False — a transient Kavenegar blip, a brief rate limit — instead of
retrying inline, which would block the request or task that triggered the
notification.

Schedule (default settings): the first retry runs 60s after the failed send,
then every 120s, up to 3 retries — at most 4 task executions over ~7 minutes,
after which the notification is logged FAILED for good. So there are never
more than 5 send attempts per notification (1 original + 4 here).

What the log looks like: notify() records the original attempt as RETRYING;
this task appends the outcome — SENT "(sent on retry)" or a final FAILED.

Deliberate limits:
* SMS only. Email/in-app failures aren't retried (lower stakes; a separate task
  if wanted).
* Never for OTP codes: they expire after OTP_CODE_TTL_SECONDS (120s) and the
  user is told the send failed, so a retry minutes later would deliver a dead
  or duplicate code. See NO_SMS_RETRY_EVENTS in services.py.
* The provider only reports True/False, so a *permanent* rejection (invalid
  number, no credit) is retried too — harmless, just wasted attempts.
* A send that timed out after Kavenegar had already accepted it can be
  delivered twice (at-least-once). Inherent to retrying without a delivery
  receipt.
"""

import logging

from celery import shared_task

logger = logging.getLogger("notifications")

# Delay before the first retry; later retries use default_retry_delay below.
FIRST_RETRY_DELAY_SECONDS = 60


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def retry_sms_notification(self, recipient, body, event, user_id):
    from django.contrib.auth import get_user_model

    from .models import NotificationLog
    from .services import _log
    from .sms import get_sms_provider

    try:
        success = get_sms_provider().send(recipient, body)
    except Exception:  # noqa: BLE001 — a raising provider is just a failed attempt
        logger.exception("SMS retry raised: event=%s", event)
        success = False

    # The user may have been deleted since the original attempt; log with no
    # user rather than failing the insert.
    user = get_user_model().objects.filter(pk=user_id).first() if user_id else None

    if success:
        _log(
            user,
            "sms",
            event,
            recipient,
            NotificationLog.Status.SENT,
            "(sent on retry)",
        )
        return

    if self.request.retries >= self.max_retries:
        _log(
            user,
            "sms",
            event,
            recipient,
            NotificationLog.Status.FAILED,
            f"Failed after {self.max_retries} retries.",
        )
        return

    raise self.retry()


@shared_task
def send_notification_email_task(
    recipient,
    subject,
    body_text,
    template_name=None,
    context=None,
    event=None,
    user_id=None,
):
    """
    Send one email, off the request path. The ONLY email-sending mechanism:
    notify()'s EMAIL channel (via notifications.email.send_notification_email)
    and the account emails (welcome / password reset) both queue this task.

    It lives in tasks.py, not email.py, on purpose: Celery's
    `autodiscover_tasks()` imports each app's `tasks` module, so a task defined
    anywhere else is unknown to a worker until something happens to import it.

    `body_text` is the plain-text part; `template_name` (optional) is rendered
    in the worker, with `context`, as the HTML part. All arguments must be
    JSON-serialisable (Celery's serializer).

    Transport errors are re-raised after being logged, so Celery's own failure
    tracking sees the real exception (unlike the old inline `fail_silently=True`,
    which swallowed them). When `event` is given, the outcome is appended to the
    NotificationLog: SENT (accepted by the mail server — not a delivery receipt)
    or FAILED.
    """
    from django.contrib.auth import get_user_model
    from django.core.mail import EmailMultiAlternatives

    from .email import render_email_template
    from .models import NotificationLog
    from .services import _log

    def log_outcome(status, note):
        if not event:
            return
        user = get_user_model().objects.filter(pk=user_id).first() if user_id else None
        _log(user, "email", event, recipient, status, note)

    # One line only: a newline in a header is rejected as header injection.
    subject = " ".join(str(subject).split())
    try:
        message = EmailMultiAlternatives(
            subject=subject, body=body_text, to=[recipient]
        )
        if template_name:
            message.attach_alternative(
                render_email_template(template_name, subject, body_text, context or {}),
                "text/html",
            )
        sent = message.send(fail_silently=False)
    except Exception as exc:
        log_outcome(NotificationLog.Status.FAILED, str(exc))
        raise

    if sent == 1:
        log_outcome(NotificationLog.Status.SENT, "Accepted by the mail server.")
    else:
        log_outcome(
            NotificationLog.Status.FAILED, "Mail backend reported nothing sent."
        )
