"""
_send_welcome_email() / _send_password_reset_email() (accounts/views.py).

These are called directly (not through the API) so the assertions are about the
messages themselves. They no longer send: they QUEUE
notifications.tasks.send_notification_email_task. The root conftest mocks that
queue for every test; classes that inspect the resulting email use the
`run_email_tasks` fixture, which executes the queued task synchronously through
Django's locmem backend (`mail.outbox`), and TestQueueing... asserts on the
queue itself.

Subject, plain-text part and HTML part are rendered under EMAIL_LANGUAGE
(Persian) regardless of the request's language. The root conftest pins every
test to English, so the "is Persian" assertions below are meaningful: they
only pass because the functions override the language themselves. The compiled
catalog is needed for the gettext-based strings (the .mo is gitignored and
built at deploy time — same approach as core/tests/test_persian_catalog.py).
"""

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from accounts.tokens import password_reset_token
from accounts.views import _send_password_reset_email, _send_welcome_email
from django.conf import settings as django_settings
from django.core import mail
from django.core.management import call_command
from django.utils import translation
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import trans_real
from notifications.models import NotificationLog
from notifications.tests.test_email import audit, style_of

PERSIAN = re.compile(r"[\u0600-\u06FF]")
LOCALE_DIR = Path(django_settings.BASE_DIR) / "locale" / "fa" / "LC_MESSAGES"


@pytest.fixture(scope="module", autouse=True)
def compiled_persian_catalog():
    po, mo = LOCALE_DIR / "django.po", LOCALE_DIR / "django.mo"
    if not mo.exists() or mo.stat().st_mtime < po.stat().st_mtime:
        call_command("compilemessages", locale=["fa"], verbosity=0)
    trans_real._translations.clear()
    trans_real._default = None


def html_of(message):
    ((html, mimetype),) = message.alternatives
    assert mimetype == "text/html"
    return html


# ─── welcome ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.usefixtures("run_email_tasks")
class TestWelcomeEmail:
    def test_sends_one_multipart_email_to_the_user(self, user):
        _send_welcome_email(user)

        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == [user.email]
        assert len(message.alternatives) == 1
        assert html_of(message).lstrip().startswith("<!DOCTYPE html>")

    def test_subject_is_persian(self, user):
        _send_welcome_email(user)

        subject = mail.outbox[0].subject
        assert subject == "خوش آمدید! حساب کاربری شما آماده است."
        assert subject != "Welcome! Your account is ready."

    def test_plain_text_fallback_is_persian_not_the_old_english(self, user):
        _send_welcome_email(user)

        text = mail.outbox[0].body
        assert text == "Jane عزیز، خوش آمدید! حساب کاربری شما آماده است."
        assert PERSIAN.search(text)
        assert "welcome" not in text.lower() and "Hi " not in text

    def test_html_is_persian_rtl_and_greets_by_name(self, user):
        _send_welcome_email(user)

        html = html_of(mail.outbox[0])
        assert 'lang="fa"' in html and 'dir="rtl"' in html
        assert "Jane" in html
        assert "خوش آمدید" in html
        assert "Welcome to" not in html and "Get Started" not in html

    def test_html_is_email_safe_no_scripts_tailwind_or_style_blocks(self, user):
        """The old template loaded the Tailwind CDN script and styled with
        classes; mail clients strip scripts, so none of that ever applied."""
        _send_welcome_email(user)

        html = html_of(mail.outbox[0])
        for forbidden in ("<script", "tailwind", "<style", 'class="', "<link"):
            assert forbidden not in html, forbidden
        assert "<table" in html

    def test_call_to_action_links_to_the_storefront_not_a_dead_hash(
        self, user, settings
    ):
        settings.FRONTEND_URL = "https://shop.example.test"

        _send_welcome_email(user)

        html = html_of(mail.outbox[0])
        assert 'href="https://shop.example.test"' in html
        assert 'href="#"' not in html

    def test_language_does_not_depend_on_the_active_request_language(self, user):
        with translation.override("en"):
            _send_welcome_email(user)

        message = mail.outbox[0]
        assert PERSIAN.search(message.subject)
        assert PERSIAN.search(message.body)
        assert "Welcome" not in message.subject

    def test_blank_first_name_falls_back_instead_of_a_dangling_comma(self, create_user):
        nameless = create_user(email="nameless@example.com", first_name="")

        _send_welcome_email(nameless)

        message = mail.outbox[0]
        assert message.body.startswith("کاربر عزیز")
        assert "کاربر عزیز" in html_of(message)

    def test_user_supplied_name_is_html_escaped(self, create_user):
        hostile = create_user(
            email="x@example.com", first_name="<script>alert(1)</script>"
        )

        _send_welcome_email(hostile)

        html = html_of(mail.outbox[0])
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html

    def test_an_smtp_failure_in_the_worker_cannot_affect_the_caller(
        self, user, settings
    ):
        """Registration must never fail because an email couldn't be sent. The
        SMTP call now happens in the worker, so the request can't see it; the
        failure is recorded in the NotificationLog instead of being swallowed
        by fail_silently=True."""
        settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
        settings.EMAIL_HOST = "127.0.0.1"
        settings.EMAIL_PORT = 1  # nothing listens here

        _send_welcome_email(user)  # must not raise

        log = NotificationLog.objects.get(event="welcome")
        assert (log.status, log.recipient, log.user) == (
            NotificationLog.Status.FAILED,
            user.email,
            user,
        )
        assert log.error_message


# ─── password reset ────────────────────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.usefixtures("run_email_tasks")
class TestPasswordResetEmail:
    def test_sends_one_multipart_email_to_the_user(self, user):
        _send_password_reset_email(user, request=None)

        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == [user.email]
        assert len(message.alternatives) == 1

    def test_subject_is_persian(self, user):
        _send_password_reset_email(user, request=None)

        assert mail.outbox[0].subject == "بازیابی رمز عبور"
        assert mail.outbox[0].subject != "Reset your password"

    def test_plain_text_fallback_is_persian_and_carries_the_link(self, user, settings):
        settings.FRONTEND_URL = "https://shop.example.test"

        _send_password_reset_email(user, request=None)

        text = mail.outbox[0].body
        assert text.startswith("برای بازیابی رمز عبور از این لینک استفاده کنید:")
        assert "Reset your password here" not in text
        assert re.search(r"https://shop\.example\.test/reset-password/\S+/\S+/", text)

    def test_html_is_persian_rtl_with_button_and_visible_fallback_link(
        self, user, settings
    ):
        settings.FRONTEND_URL = "https://shop.example.test"

        _send_password_reset_email(user, request=None)

        html = html_of(mail.outbox[0])
        url = re.search(r"https://shop\.example\.test/reset-password/\S+?/\S+?/", html)
        assert url
        assert 'lang="fa"' in html and 'dir="rtl"' in html
        assert "درخواست بازیابی رمز عبور" in html
        assert "تعیین رمز عبور جدید" in html  # the button label
        assert f'href="{url.group(0)}"' in html  # the button
        assert html.count(url.group(0)) >= 2  # …and the copy-paste fallback
        assert "Reset Password" not in html and "Password Reset Request" not in html
        for forbidden in ("<script", "tailwind", "<style", 'class="'):
            assert forbidden not in html, forbidden

    def test_language_does_not_depend_on_the_active_request_language(self, user):
        with translation.override("en"):
            _send_password_reset_email(user, request=None)

        message = mail.outbox[0]
        assert PERSIAN.search(message.subject) and PERSIAN.search(message.body)

    def test_blank_first_name_falls_back(self, create_user):
        nameless = create_user(email="nameless@example.com", first_name="")

        _send_password_reset_email(nameless, request=None)

        assert "کاربر عزیز" in html_of(mail.outbox[0])


# ─── the FRONTEND_URL cleanup changed nothing ──────────────────────────────


@pytest.mark.django_db
@pytest.mark.usefixtures("run_email_tasks")
class TestResetUrlConstruction:
    """The `getattr(__import__(...), "FRONTEND_URL", "http://localhost:3000")`
    construct became a plain `settings.FRONTEND_URL`. The URL must be built
    exactly as before: {FRONTEND_URL}/reset-password/{uid}/{token}/ ."""

    def extract_url(self, message):
        return re.search(r"(https?://\S+/reset-password/\S+/\S+/)", message.body).group(
            1
        )

    def test_url_uses_the_configured_frontend_url(self, user, settings):
        settings.FRONTEND_URL = "https://configured.example.test"

        _send_password_reset_email(user, request=None)

        url = self.extract_url(mail.outbox[0])
        assert url.startswith("https://configured.example.test/reset-password/")

    def test_url_has_the_exact_uid_token_shape_and_the_token_is_valid(
        self, user, settings
    ):
        settings.FRONTEND_URL = "https://configured.example.test"

        _send_password_reset_email(user, request=None)

        url = self.extract_url(mail.outbox[0])
        match = re.fullmatch(
            r"https://configured\.example\.test/reset-password/([^/]+)/([^/]+)/", url
        )
        assert match, url
        uid, token = match.groups()
        assert force_str(urlsafe_base64_decode(uid)) == str(user.pk)
        assert password_reset_token.check_token(user, token)

    @pytest.mark.parametrize(
        "frontend_url",
        ["http://localhost:3000", "https://shop.example.com", "https://a.b/c"],
    )
    def test_each_configured_value_is_used_verbatim(self, user, settings, frontend_url):
        settings.FRONTEND_URL = frontend_url

        _send_password_reset_email(user, request=None)

        message = mail.outbox[0]
        assert f"{frontend_url}/reset-password/" in message.body
        assert f'href="{frontend_url}/reset-password/' in html_of(message)

    def test_a_trailing_slash_is_not_normalised_behaviour_is_unchanged(
        self, user, settings
    ):
        """Deliberately pinned: the cleanup was zero-behaviour-change."""
        settings.FRONTEND_URL = "https://shop.example.test/"

        _send_password_reset_email(user, request=None)

        assert "https://shop.example.test//reset-password/" in mail.outbox[0].body

    def test_settings_define_frontend_url_so_no_fallback_is_needed(self):
        """The old getattr default could never fire: both settings modules
        define FRONTEND_URL (production has no default at all)."""
        assert django_settings.FRONTEND_URL


# ─── the same email-client rules hold for these two templates ──────────────


@pytest.mark.django_db
@pytest.mark.usefixtures("run_email_tasks")
class TestAccountEmailHtmlAudit:
    @pytest.fixture(params=["welcome", "password_reset"])
    def html(self, request, user):
        (
            _send_welcome_email(user)
            if request.param == "welcome"
            else (_send_password_reset_email(user, request=None))
        )
        return html_of(mail.outbox[-1])

    def test_explicit_rtl_on_document_body_and_every_table(self, html):
        parsed = audit(html)
        assert parsed.html_attrs.get("dir") == "rtl"
        assert parsed.body_attrs.get("dir") == "rtl"
        assert parsed.tables
        for table in parsed.tables:
            assert table.get("dir") == "rtl", table
            assert "direction:rtl" in style_of(table), table

    def test_every_text_cell_is_explicitly_right_aligned_rtl(self, html):
        for cell in audit(html).cells:
            if not cell["text"].strip():
                continue
            style = style_of(cell["attrs"])
            assert "direction:rtl" in style, cell
            is_button = cell["has_link"] and "bgcolor" in cell["attrs"]
            assert (
                "text-align:center" if is_button else "text-align:right"
            ) in style, cell

    def test_latin_tokens_are_isolated_as_ltr(self, html):
        stripped = re.sub(r"<title>.*?</title>", "", html, flags=re.S)
        stripped = re.sub(r'<span dir="ltr"[^>]*>.*?</span>', "", stripped, flags=re.S)
        assert "Chiz" not in re.sub(r"<[^>]+>", " ", stripped)


# ─── the point of the change: nothing is sent in the request path ──────────


@pytest.mark.django_db
class TestQueueingInsteadOfSending:
    """_send_welcome_email / _send_password_reset_email used to call send_mail()
    inline, blocking the request on the SMTP round-trip. They now queue a
    Celery task. Run with the conftest's mocked queue (nothing executes)."""

    @pytest.fixture
    def smtp_must_not_be_touched(self):
        """Fails loudly if anything in the request path opens a mail connection
        or sends — which is exactly what used to block the request."""
        with (
            patch(
                "django.core.mail.get_connection",
                side_effect=AssertionError("mail connection opened inline"),
            ),
            patch(
                "django.core.mail.message.EmailMessage.send",
                side_effect=AssertionError("email sent inline"),
            ),
        ):
            yield

    def test_welcome_queues_one_task_and_sends_nothing_inline(
        self, user, _email_queue_is_mocked, smtp_must_not_be_touched
    ):
        _send_welcome_email(user)

        _email_queue_is_mocked.assert_called_once()
        assert mail.outbox == []

    def test_password_reset_queues_one_task_and_sends_nothing_inline(
        self, user, _email_queue_is_mocked, smtp_must_not_be_touched
    ):
        _send_password_reset_email(user, request=None)

        _email_queue_is_mocked.assert_called_once()
        assert mail.outbox == []

    def test_welcome_task_arguments(self, user, settings, _email_queue_is_mocked):
        settings.FRONTEND_URL = "https://shop.example.test"

        _send_welcome_email(user)

        kwargs = _email_queue_is_mocked.call_args.kwargs
        assert kwargs == {
            "recipient": user.email,
            "subject": "خوش آمدید! حساب کاربری شما آماده است.",
            "body_text": "Jane عزیز، خوش آمدید! حساب کاربری شما آماده است.",
            "template_name": "accounts/emails/welcome.html",
            "context": {
                "first_name": "Jane",
                "email": user.email,
                "shop_url": "https://shop.example.test",
            },
            "event": "welcome",
            "user_id": user.pk,
        }

    def test_password_reset_task_arguments(
        self, user, settings, _email_queue_is_mocked
    ):
        settings.FRONTEND_URL = "https://shop.example.test"

        _send_password_reset_email(user, request=None)

        kwargs = _email_queue_is_mocked.call_args.kwargs
        url = kwargs["context"]["reset_url"]
        assert url.startswith("https://shop.example.test/reset-password/")
        assert kwargs["recipient"] == user.email
        assert kwargs["subject"] == "بازیابی رمز عبور"
        assert kwargs["body_text"].endswith(url)
        assert kwargs["template_name"] == "accounts/emails/password_reset.html"
        assert kwargs["context"]["first_name"] == "Jane"
        assert kwargs["event"] == "password_reset"
        assert kwargs["user_id"] == user.pk

    def test_task_arguments_are_json_serialisable(self, user, _email_queue_is_mocked):
        """They cross the broker as JSON."""
        _send_welcome_email(user)
        first = _email_queue_is_mocked.call_args.kwargs
        _send_password_reset_email(user, request=None)
        second = _email_queue_is_mocked.call_args.kwargs

        json.dumps(first)
        json.dumps(second)

    def test_subject_and_text_are_persian_whatever_the_request_language(
        self, user, _email_queue_is_mocked
    ):
        with translation.override("en"):
            _send_welcome_email(user)

        kwargs = _email_queue_is_mocked.call_args.kwargs
        assert PERSIAN.search(kwargs["subject"]) and PERSIAN.search(kwargs["body_text"])

    def test_every_email_goes_through_the_one_shared_task(self):
        """Welcome, reset and notify()'s EMAIL channel share a single Celery
        task, not parallel async-email mechanisms."""
        import accounts.views
        import notifications.email
        import notifications.tasks

        task = notifications.tasks.send_notification_email_task
        assert accounts.views.send_notification_email_task is task
        assert notifications.email.send_notification_email_task is task

    # a broken queue must never break the caller -----------------------------

    def test_a_broker_error_is_swallowed_and_logged(
        self, user, _email_queue_is_mocked, caplog
    ):
        _email_queue_is_mocked.side_effect = ConnectionError("broker down")

        _send_welcome_email(user)  # must not raise
        _send_password_reset_email(user, request=None)  # must not raise

        messages = [r.getMessage() for r in caplog.records]
        assert any("Could not queue welcome email" in m for m in messages)
        assert any("Could not queue password_reset email" in m for m in messages)
