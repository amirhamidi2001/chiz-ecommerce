"""
notifications.email.send_notification_email and the RTL email templates.

Two kinds of tests:
  * behaviour — what is sent, to whom, in which parts, how failures surface;
  * an HTML audit — the email-client rules from notifications/emails/base.html
    (table layout, inline styles only, explicit dir="rtl" + text-align:right,
    LTR tokens isolated) checked against every template that notify() can use.
"""

import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from smtplib import SMTPException
from unittest.mock import patch

import pytest
from django.conf import settings as django_settings
from django.core import mail
from django.utils import translation
from notifications.email import (
    render_email_html,
    send_notification_email,
    send_notification_email_task,
)
from notifications.models import NotificationLog, NotificationTemplate
from notifications.services import notify

from .test_services import make_user

Channel = NotificationTemplate.Channel
Event = NotificationTemplate.Event
Status = NotificationLog.Status

PERSIAN = re.compile(r"[\u0600-\u06FF]")

ORDER_CONTEXT = {
    "order_number": "ORD-3A7F2B",
    "order_total": "1,250,000",
    "customer_name": "سارا",
}
SHIPPING_CONTEXT = {
    "order_number": "ORD-3A7F2B",
    "shipping_status": "در حال تحویل",
    "tracking_number": "TRK-998877",
    "customer_name": "سارا",
}

# (event, context) for every event whose email notify() can send.
EMAIL_CASES = [
    (Event.ORDER_CONFIRMED, ORDER_CONTEXT),
    (Event.SHIPPING_UPDATE, SHIPPING_CONTEXT),
    (
        Event.ORDER_STATUS_CHANGED,
        {"order_number": "ORD-3A7F2B", "status": "ارسال شد", "customer_name": "سارا"},
    ),
    (
        Event.BACK_IN_STOCK,
        {
            "product_name": "سرم",
            "product_url": "https://shop.example/product/serum",
            "customer_name": "سارا",
        },
    ),
    (
        Event.PRICE_DROP,
        {
            "product_name": "سرم",
            "old_price": "1,250,000",
            "new_price": "990,000",
            "product_url": "https://shop.example/product/serum",
            "customer_name": "سارا",
        },
    ),
]


def rendered_copy(event, context):
    """(subject, body) from the seeded EMAIL NotificationTemplate for `event`."""
    template = NotificationTemplate.objects.get(channel=Channel.EMAIL, event=event)
    return template.render_subject(context), template.render(context)


def html_for(event, context):
    subject, body = rendered_copy(event, context)
    return render_email_html(event, subject, body, context)


# ─── HTML audit ────────────────────────────────────────────────────────────


class Audit(HTMLParser):
    """Collects what the email-client rules need to know about the markup."""

    def __init__(self):
        super().__init__()
        self.html_attrs = {}
        self.body_attrs = {}
        self.tables = []
        self.cells = []  # {"attrs", "text", "has_link"}: a cell's OWN text only
        self._open = []  # stack of ("table", None) / ("td", cell)

    def _current_cell(self):
        if self._open and self._open[-1][0] == "td":
            return self._open[-1][1]
        return None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.html_attrs = attrs
        elif tag == "body":
            self.body_attrs = attrs
        elif tag == "table":
            self.tables.append(attrs)
            self._open.append(("table", None))
        elif tag == "td":
            cell = {"attrs": attrs, "text": "", "has_link": False}
            self.cells.append(cell)
            self._open.append(("td", cell))
        elif tag == "a" and self._current_cell() is not None:
            self._current_cell()["has_link"] = True

    def handle_endtag(self, tag):
        if tag in ("table", "td") and self._open:
            self._open.pop()

    def handle_data(self, data):
        cell = self._current_cell()
        if cell is not None:
            cell["text"] += data


def audit(html):
    parser = Audit()
    parser.feed(html)
    return parser


def style_of(attrs):
    return re.sub(r"\s+", "", attrs.get("style", "")).lower()


@pytest.mark.django_db
class TestHtmlAudit:
    """Every email notify() can send, rendered with realistic context."""

    @pytest.fixture(params=EMAIL_CASES, ids=[c[0] for c in EMAIL_CASES])
    def html(self, request):
        event, context = request.param
        return html_for(event, context)

    def test_document_and_body_are_explicitly_rtl_persian(self, html):
        parsed = audit(html)
        assert parsed.html_attrs.get("dir") == "rtl"
        assert parsed.html_attrs.get("lang") == "fa"
        assert parsed.body_attrs.get("dir") == "rtl"
        assert "direction:rtl" in style_of(parsed.body_attrs)

    def test_layout_is_tables_and_every_table_is_explicitly_rtl(self, html):
        parsed = audit(html)
        assert len(parsed.tables) >= 2
        for table in parsed.tables:
            assert table.get("dir") == "rtl", table
            assert table.get("role") == "presentation", table
            assert "direction:rtl" in style_of(table), table

    def test_every_text_cell_has_explicit_rtl_direction_and_right_alignment(self, html):
        """Not relying on dir= alone to cascade: each cell that holds text says
        `direction:rtl;text-align:right` itself. (A button's label, inside its
        own link cell, is centred.)"""
        text_cells = [c for c in audit(html).cells if c["text"].strip()]
        assert text_cells
        for cell in text_cells:
            style = style_of(cell["attrs"])
            assert "direction:rtl" in style, cell
            is_button = cell["has_link"] and "bgcolor" in cell["attrs"]
            if is_button:
                assert "text-align:center" in style, cell
            else:
                assert "text-align:right" in style, cell

    def test_every_text_cell_sets_a_persian_capable_font_stack(self, html):
        for cell in audit(html).cells:
            if cell["text"].strip():
                style = style_of(cell["attrs"])
                assert "font-family:" in style, cell
                assert "tahoma" in style, cell  # has Persian glyphs on Win/macOS

    def test_no_features_email_clients_drop(self, html):
        lowered = html.lower()
        for forbidden in (
            "<style",
            "<script",
            "<link",
            "<img",  # remote images are blocked by default
            "display:flex",
            "display: flex",
            "display:grid",
            "display: grid",
            "float:",
            "position:",
            "@import",
            "@font-face",
            "tailwind",
            'class="',
        ):
            assert forbidden not in lowered, forbidden

    def test_no_unrendered_template_syntax_or_python_noise(self, html):
        assert "{{" not in html and "{%" not in html and "{#" not in html
        assert ">None<" not in html and "None" not in re.sub(r"<[^>]+>", " ", html)

    def test_has_real_persian_text_and_a_utf8_declaration(self, html):
        visible = re.sub(r"<[^>]+>", " ", html)
        assert PERSIAN.search(visible)
        assert "charset=UTF-8" in html

    def test_latin_tokens_are_isolated_as_ltr(self, html):
        """The brand name never sits bare inside the right-to-left flow: every
        occurrence is inside an explicit dir="ltr" span (or the <title>)."""
        without_isolated = re.sub(r"<title>.*?</title>", "", html, flags=re.S)
        without_isolated = re.sub(
            r'<span dir="ltr"[^>]*>.*?</span>', "", without_isolated, flags=re.S
        )
        visible = re.sub(r"<[^>]+>", " ", without_isolated)
        assert "Chiz" not in visible


@pytest.mark.django_db
class TestTemplateContent:
    def test_order_confirmed_shows_heading_order_number_and_total(self):
        html = html_for(Event.ORDER_CONFIRMED, ORDER_CONTEXT)

        assert "سفارش شما تأیید شد" in html
        assert "خلاصه سفارش" in html
        assert (
            '<span dir="ltr" style="direction:ltr;unicode-bidi:embed;">ORD-3A7F2B</span>'
            in html
        )
        assert (
            '<span dir="ltr" style="direction:ltr;unicode-bidi:embed;">1,250,000</span>'
            " تومان" in html
        )

    def test_the_html_shows_the_admin_editable_copy(self):
        NotificationTemplate.objects.filter(
            channel=Channel.EMAIL, event=Event.ORDER_CONFIRMED
        ).update(
            body="{customer_name} عزیز،\n\nمتن ویرایش‌شده توسط مدیر {order_number}"
        )

        html = html_for(Event.ORDER_CONFIRMED, ORDER_CONTEXT)

        assert "متن ویرایش‌شده توسط مدیر ORD-3A7F2B" in html
        assert "سارا عزیز،" in html

    def test_shipping_update_shows_status_and_tracking_number(self):
        html = html_for(Event.SHIPPING_UPDATE, SHIPPING_CONTEXT)

        assert "وضعیت ارسال سفارش شما" in html
        assert "جزئیات ارسال" in html
        assert "در حال تحویل" in html
        assert (
            '<span dir="ltr" style="direction:ltr;unicode-bidi:embed;">TRK-998877</span>'
            in html
        )

    def test_shipping_update_omits_the_tracking_row_when_there_is_none(self):
        context = {**SHIPPING_CONTEXT, "tracking_number": ""}

        html = html_for(Event.SHIPPING_UPDATE, context)

        assert "کد رهگیری:" not in html
        assert 'dir="ltr" style="direction:ltr;unicode-bidi:embed;">TRK' not in html
        assert "در حال تحویل" in html

    def test_details_card_is_omitted_entirely_without_any_order_details(self):
        html = render_email_html(Event.ORDER_CONFIRMED, "موضوع", "متن", {})

        assert "خلاصه سفارش" not in html
        assert "متن" in html

    @pytest.mark.parametrize(
        "event",
        [
            Event.ORDER_STATUS_CHANGED,
            Event.BACK_IN_STOCK,
            Event.PRICE_DROP,
            Event.WELCOME,
            None,
            "event_that_does_not_exist",
        ],
    )
    def test_events_without_a_dedicated_layout_use_the_generic_one(self, event):
        html = render_email_html(
            event, "عنوان نمونه", "پاراگراف اول\n\nپاراگراف دوم", {}
        )

        assert "<h1" in html and "عنوان نمونه</h1>" in html
        assert "پاراگراف اول" in html and "پاراگراف دوم" in html
        assert "خلاصه سفارش" not in html and "جزئیات ارسال" not in html

    def test_body_is_split_into_paragraph_rows(self):
        html = render_email_html(None, "s", "یک\n\nدو\n\nسه", {})

        assert len(re.findall(r"line-height:2;color:#374151;\">", html)) == 3

    def test_single_newlines_inside_a_paragraph_become_line_breaks(self):
        html = render_email_html(None, "s", "خط اول\nخط دوم", {})

        assert "خط اول<br>خط دوم" in html

    def test_body_text_is_html_escaped(self):
        html = render_email_html(None, "s", "<b>x</b> & <script>alert(1)</script>", {})

        assert "<script>alert(1)</script>" not in html
        assert "&lt;b&gt;x&lt;/b&gt; &amp; &lt;script&gt;" in html

    def test_urls_in_the_body_become_links(self):
        html = render_email_html(
            None, "s", "لینک:\nhttps://shop.example/product/serum", {}
        )

        assert 'href="https://shop.example/product/serum"' in html

    def test_rendering_is_independent_of_the_active_language(self):
        with translation.override("en"):
            html = html_for(Event.ORDER_CONFIRMED, ORDER_CONTEXT)

        assert 'lang="fa"' in html and "سفارش شما تأیید شد" in html


# ─── queueing: send_notification_email() only QUEUES ───────────────────────


@pytest.mark.django_db
class TestSendNotificationEmailQueues:
    """The sender must not send. It queues send_notification_email_task and
    returns True meaning "queued" (not "delivered")."""

    def test_queues_the_task_with_the_resolved_template_and_returns_true(
        self, _email_queue_is_mocked
    ):
        subject, body = rendered_copy(Event.ORDER_CONFIRMED, ORDER_CONTEXT)

        result = send_notification_email(
            "sara@example.com",
            subject,
            body,
            ORDER_CONTEXT,
            event=Event.ORDER_CONFIRMED,
            user_id=7,
        )

        assert result is True
        _email_queue_is_mocked.assert_called_once_with(
            recipient="sara@example.com",
            subject=subject,
            body_text=body,
            template_name="notifications/emails/order_confirmed.html",
            context=ORDER_CONTEXT,
            event="order_confirmed",
            user_id=7,
        )

    def test_nothing_is_sent_by_the_call_itself(self, _email_queue_is_mocked):
        with patch("django.core.mail.EmailMultiAlternatives.send") as smtp:
            send_notification_email("a@example.com", "s", "b", {}, event="welcome")

        smtp.assert_not_called()
        assert mail.outbox == []

    def test_explicit_template_name_wins_over_the_event(self, _email_queue_is_mocked):
        send_notification_email(
            "a@example.com",
            "s",
            "b",
            {},
            template_name="accounts/emails/welcome.html",
            event=Event.ORDER_CONFIRMED,
        )

        assert (
            _email_queue_is_mocked.call_args.kwargs["template_name"]
            == "accounts/emails/welcome.html"
        )

    @pytest.mark.parametrize(
        "event, expected",
        [
            (Event.ORDER_CONFIRMED, "order_confirmed.html"),
            (Event.SHIPPING_UPDATE, "shipping_update.html"),
            (Event.PRICE_DROP, "generic.html"),  # no dedicated layout
            (None, "generic.html"),
            ("unknown_event", "generic.html"),
        ],
    )
    def test_template_is_resolved_from_the_event(
        self, event, expected, _email_queue_is_mocked
    ):
        send_notification_email("a@example.com", "s", "b", {}, event=event)

        assert (
            _email_queue_is_mocked.call_args.kwargs["template_name"]
            == f"notifications/emails/{expected}"
        )

    def test_the_context_is_made_json_safe_for_the_broker(self, _email_queue_is_mocked):
        from datetime import datetime
        from decimal import Decimal

        send_notification_email(
            "a@example.com",
            "s",
            "b",
            {"total": Decimal("1250.5"), "when": datetime(2026, 1, 2, 3, 4), "n": 3},
        )

        context = _email_queue_is_mocked.call_args.kwargs["context"]
        assert context == {"total": "1250.5", "when": "2026-01-02 03:04:00", "n": 3}
        json.dumps(context)  # round-trips

    def test_a_broken_broker_raises_so_notify_can_log_the_failure(
        self, _email_queue_is_mocked
    ):
        _email_queue_is_mocked.side_effect = ConnectionError("broker down")

        with pytest.raises(ConnectionError):
            send_notification_email("a@example.com", "s", "b", {}, event="welcome")


# ─── the task: the one place an email is actually sent ─────────────────────


def run_task(**overrides):
    kwargs = {
        "recipient": "sara@example.com",
        "subject": "موضوع",
        "body_text": "سارا عزیز،\n\nمتن ساده",
        "template_name": "notifications/emails/generic.html",
        "context": {},
        "event": None,
        "user_id": None,
    }
    kwargs.update(overrides)
    return send_notification_email_task.apply(kwargs=kwargs)


@pytest.mark.django_db
class TestSendNotificationEmailTask:
    def test_sends_a_multipart_message_with_the_rendered_html_and_plain_text(self):
        subject, body = rendered_copy(Event.ORDER_CONFIRMED, ORDER_CONTEXT)

        result = run_task(
            subject=subject,
            body_text=body,
            template_name="notifications/emails/order_confirmed.html",
            context=ORDER_CONTEXT,
        )

        assert result.successful()
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == ["sara@example.com"]
        assert message.subject == subject
        assert message.body == body  # plain-text part is exactly the copy
        ((html, mimetype),) = message.alternatives
        assert mimetype == "text/html"
        # …and the HTML is the rendered template: RTL layout + order details.
        assert 'dir="rtl"' in html and "سفارش شما تأیید شد" in html
        assert "ORD-3A7F2B" in html and "1,250,000" in html

    def test_plain_text_and_html_carry_the_same_copy(self):
        subject, body = rendered_copy(Event.SHIPPING_UPDATE, SHIPPING_CONTEXT)

        run_task(
            subject=subject,
            body_text=body,
            template_name="notifications/emails/shipping_update.html",
            context=SHIPPING_CONTEXT,
        )

        message = mail.outbox[0]
        html = message.alternatives[0][0]
        for line in message.body.splitlines():
            if line.strip():
                assert line.strip() in html

    def test_without_a_template_it_sends_plain_text_only(self):
        run_task(template_name=None)

        message = mail.outbox[0]
        assert message.alternatives == []
        assert message.body.startswith("سارا عزیز")

    def test_newlines_in_the_subject_are_collapsed_not_rejected(self):
        """A newline in a header is rejected as header injection; the subject
        is admin-editable text plus context values, so it is flattened."""
        result = run_task(subject="خط اول\r\nBcc: evil@example.com")

        assert result.successful()
        assert mail.outbox[0].subject == "خط اول Bcc: evil@example.com"
        assert mail.outbox[0].bcc == []

    def test_html_is_rendered_in_persian_whatever_the_workers_language(self):
        with translation.override("en"):
            run_task()

        assert 'lang="fa"' in mail.outbox[0].alternatives[0][0]

    def test_it_is_one_registered_celery_task_defined_in_tasks_py(self):
        """Celery's autodiscover_tasks() only imports each app's tasks.py, so a
        task defined elsewhere is unknown to a worker."""
        assert send_notification_email_task.name == (
            "notifications.tasks.send_notification_email_task"
        )
        assert send_notification_email_task.__module__ == "notifications.tasks"

    def test_autodiscovery_alone_registers_the_task_without_email_py(self):
        """Celery's autodiscover_tasks() imports each app's tasks.py, so the
        task must be defined there. (A real worker also happens to import
        email.py, via Django's system checks -> the URLconf -> accounts.views,
        but registration shouldn't depend on that import chain.) Fresh
        interpreter: only django.setup() and autodiscovery."""
        code = (
            "import sys, django\n"
            "django.setup()\n"
            "from core.celery import app\n"
            "app.autodiscover_tasks(force=True)\n"
            "print('notifications.tasks.send_notification_email_task' in app.tasks)\n"
            "print('notifications.email' in sys.modules)\n"
        )
        env = {
            "PATH": os.environ.get("PATH", ""),
            "DJANGO_SETTINGS_MODULE": "core.settings.development",
            "SECRET_KEY": "x",
            "DATABASE_NAME": "n",
            "DATABASE_USER": "u",
            "DATABASE_PASSWORD": "p",
            "DATABASE_HOST": "localhost",
        }
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=django_settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        registered, email_imported = result.stdout.strip().splitlines()[-2:]
        assert registered == "True"
        assert email_imported == "False"  # registration didn't need email.py


@pytest.mark.django_db
class TestEmailTaskOutcomeLogging:
    """The task appends the REAL outcome, so the log can tell 'queued' from
    'the mail server accepted it' from 'it failed'."""

    def test_success_appends_a_sent_row_for_events(self):
        user = make_user(email="sara@example.com")

        run_task(event="order_confirmed", user_id=user.id)

        log = NotificationLog.objects.get()
        assert (log.channel, log.event, log.recipient, log.user) == (
            "email",
            "order_confirmed",
            "sara@example.com",
            user,
        )
        assert log.status == Status.SENT
        assert log.error_message == "Accepted by the mail server."

    def test_smtp_failure_logs_failed_and_the_task_really_fails(self):
        """fail_silently=False: Celery's own failure tracking sees the real
        exception (the old inline send swallowed it)."""
        with patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=SMTPException("535 auth failed"),
        ):
            result = run_task(event="order_confirmed")

        assert result.failed()
        assert isinstance(result.result, SMTPException)
        log = NotificationLog.objects.get()
        assert log.status == Status.FAILED
        assert log.error_message == "535 auth failed"

    def test_a_template_error_is_logged_failed_too(self):
        result = run_task(
            template_name="notifications/emails/nope.html", event="welcome"
        )

        assert result.failed()
        assert NotificationLog.objects.get().status == Status.FAILED
        assert mail.outbox == []

    def test_backend_reporting_nothing_sent_is_logged_failed(self):
        with patch("django.core.mail.EmailMultiAlternatives.send", return_value=0):
            result = run_task(event="order_confirmed")

        assert result.successful()
        log = NotificationLog.objects.get()
        assert log.status == Status.FAILED
        assert "nothing sent" in log.error_message

    def test_no_log_row_without_an_event(self):
        run_task(event=None)

        assert NotificationLog.objects.count() == 0
        assert len(mail.outbox) == 1

    def test_deleted_user_does_not_break_logging(self):
        user = make_user()
        user_id = user.id
        user.delete()

        result = run_task(event="order_confirmed", user_id=user_id)

        assert result.successful()
        log = NotificationLog.objects.get()
        assert log.status == Status.SENT and log.user is None


# ─── through notify() ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestThroughNotify:
    def test_notify_queues_and_logs_queued_then_the_task_logs_the_outcome(
        self, run_email_tasks
    ):
        user = make_user(email="sara@example.com")

        notify(user, Event.ORDER_CONFIRMED, ORDER_CONTEXT, channels=[Channel.EMAIL])

        run_email_tasks.assert_called_once()
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == ["sara@example.com"]
        assert "ORD-3A7F2B" in message.alternatives[0][0]
        rows = list(NotificationLog.objects.order_by("id"))
        assert [r.status for r in rows] == [Status.QUEUED, Status.SENT]
        assert all(r.recipient == "sara@example.com" and r.user == user for r in rows)

    def test_queued_row_says_queued_not_delivered(self, _email_queue_is_mocked):
        user = make_user(email="sara@example.com")

        notify(user, Event.ORDER_CONFIRMED, ORDER_CONTEXT, channels=[Channel.EMAIL])

        log = NotificationLog.objects.get()
        assert log.status == Status.QUEUED
        assert log.status != Status.SENT  # not claimed as delivered
        assert "Queued" in log.error_message
        assert mail.outbox == []  # nothing sent yet: only queued

    def test_notify_passes_the_event_and_user_id_to_the_queued_task(
        self, _email_queue_is_mocked
    ):
        user = make_user(email="sara@example.com")

        notify(user, Event.SHIPPING_UPDATE, SHIPPING_CONTEXT, channels=[Channel.EMAIL])

        kwargs = _email_queue_is_mocked.call_args.kwargs
        assert kwargs["event"] == "shipping_update"
        assert kwargs["user_id"] == user.id
        assert kwargs["template_name"] == "notifications/emails/shipping_update.html"
        assert kwargs["recipient"] == "sara@example.com"

    def test_guest_checkout_email_uses_the_address_from_the_context(
        self, run_email_tasks
    ):
        notify(
            None,
            Event.ORDER_CONFIRMED,
            {**ORDER_CONTEXT, "email": "guest@example.com"},
            channels=[Channel.EMAIL],
        )

        assert mail.outbox[0].to == ["guest@example.com"]
        assert run_email_tasks.call_args.kwargs["user_id"] is None
        assert NotificationLog.objects.filter(user__isnull=False).count() == 0

    def test_smtp_failure_in_the_task_leaves_queued_then_failed(self, run_email_tasks):
        user = make_user(email="sara@example.com")

        with patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=SMTPException("connection refused"),
        ):
            notify(user, Event.ORDER_CONFIRMED, ORDER_CONTEXT, channels=[Channel.EMAIL])

        rows = list(NotificationLog.objects.order_by("id"))
        assert [r.status for r in rows] == [Status.QUEUED, Status.FAILED]
        assert rows[1].error_message == "connection refused"

    def test_a_broker_outage_logs_failed_without_raising_or_retrying_sms_style(
        self, _email_queue_is_mocked
    ):
        user = make_user(email="sara@example.com")
        _email_queue_is_mocked.side_effect = ConnectionError("broker down")

        with (
            patch("notifications.tasks.retry_sms_notification.apply_async") as retry,
            patch("notifications.services.logger"),
        ):
            notify(user, Event.ORDER_CONFIRMED, ORDER_CONTEXT, channels=[Channel.EMAIL])

        log = NotificationLog.objects.get()
        assert log.status == Status.FAILED  # never claims QUEUED for a lost task
        assert log.error_message == "broker down"
        retry.assert_not_called()  # email failures are not retried
