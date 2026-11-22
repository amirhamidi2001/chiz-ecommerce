"""
notifications/email.py
──────────────────────
The EMAIL channel's sender, called by notifications.services.notify().

    send_notification_email(recipient, subject, body_text, context,
                            template_name=None, event=None, user_id=None) -> bool

It does NOT send: it QUEUES `send_notification_email_task` (a Celery task,
defined in tasks.py and re-exported here) and returns True, meaning "queued",
not "delivered". That is a deliberate difference from the SMS providers, whose
True means the gateway's API accepted the message. notify() therefore logs the
EMAIL attempt as QUEUED, and the task appends the real outcome (SENT = accepted
by the mail server, or FAILED) when it actually runs. If the broker is
unreachable, queueing raises and notify() records the attempt as FAILED.

The task sends a multipart message: `body_text` (the rendered, admin-editable
NotificationTemplate text) as the plain-text part, and an RTL, table-based HTML
version rendered in the worker from `template_name`
(notifications/emails/<event>.html, falling back to generic.html). The HTML
shows the same copy — so editing a template in the admin changes both parts —
plus a details card built from the context. The account emails (welcome,
password reset) queue the same task with their own template.

Email is Persian-only: the layouts are right-to-left Persian, so everything
rendered here is rendered under EMAIL_LANGUAGE, whatever language the current
request or worker is in.
"""

import json

from django.template.loader import render_to_string, select_template
from django.utils import translation

from .tasks import send_notification_email_task

# The language every email is rendered in (templates are Persian/RTL only).
EMAIL_LANGUAGE = "fa"

# Used where a recipient's first name is blank, e.g. «کاربر عزیز» ("dear user").
DEFAULT_RECIPIENT_NAME = "کاربر"

TEMPLATE_DIR = "notifications/emails"


def _paragraphs(body: str) -> list[str]:
    """Split the plain-text body into paragraphs on blank lines."""
    return [p.strip() for p in body.replace("\r\n", "\n").split("\n\n") if p.strip()]


def resolve_template_name(event) -> str:
    """Name of the HTML template for `event` (dedicated layout, else generic)."""
    candidates = [f"{TEMPLATE_DIR}/generic.html"]
    if event:
        candidates.insert(0, f"{TEMPLATE_DIR}/{event}.html")
    return select_template(candidates).template.name


def render_email_template(template_name, subject, body, context) -> str:
    """Render `template_name` as the HTML part, under EMAIL_LANGUAGE."""
    template_context = {
        **(context or {}),
        "subject": subject,
        "body": body,
        "paragraphs": _paragraphs(body),
    }
    with translation.override(EMAIL_LANGUAGE):
        return render_to_string(template_name, template_context)


def render_email_html(event, subject, body, context) -> str:
    """Render the HTML part for `event` (what the task does, by event)."""
    return render_email_template(resolve_template_name(event), subject, body, context)


def _json_safe(context) -> dict:
    """The task arguments travel as JSON; coerce anything else (Decimal,
    datetime, lazy strings...) to its string form rather than failing the send."""
    return json.loads(json.dumps(context or {}, default=str, skipkeys=True))


def send_notification_email(
    recipient,
    subject,
    body_text,
    context,
    template_name=None,
    event=None,
    user_id=None,
) -> bool:
    """Queue the email; True means QUEUED, not delivered (see module docstring)."""
    send_notification_email_task.delay(
        recipient=recipient,
        subject=subject,
        body_text=body_text,
        template_name=template_name or resolve_template_name(event),
        context=_json_safe(context),
        event=event,
        user_id=user_id,
    )
    return True
