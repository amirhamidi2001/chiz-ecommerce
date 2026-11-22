import logging
import re

import pytest
from django.db import IntegrityError, transaction
from notifications.models import NotificationLog, NotificationTemplate
from shop.tests.factories import UserFactory

Channel = NotificationTemplate.Channel
Event = NotificationTemplate.Event

PERSIAN_LETTERS = re.compile(r"[\u0600-\u06FF]")
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


def make_template(body, channel=Channel.SMS, event=Event.ORDER_CONFIRMED, **kwargs):
    """Unsaved instance — render() needs no DB."""
    return NotificationTemplate(channel=channel, event=event, body=body, **kwargs)


class TestRender:
    def test_substitutes_all_placeholders(self):
        template = make_template("Hi {customer_name}, order {order_number} is in.")

        result = template.render({"customer_name": "Sara", "order_number": "ORD-1"})

        assert result == "Hi Sara, order ORD-1 is in."

    def test_extra_context_keys_are_ignored(self):
        template = make_template("Order {order_number}")

        assert template.render({"order_number": "ORD-1", "unused": "x"}) == (
            "Order ORD-1"
        )

    def test_missing_key_does_not_raise_logs_warning_and_keeps_placeholder(
        self, caplog
    ):
        template = make_template("Hi {customer_name}, order {order_number}.")

        with caplog.at_level(logging.WARNING, logger="notifications"):
            result = template.render({"customer_name": "Sara"})

        assert result == "Hi Sara, order {order_number}."
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert warnings[0].name == "notifications"
        assert "sms/order_confirmed" in warnings[0].getMessage()

    def test_all_keys_missing_keeps_every_placeholder(self, caplog):
        template = make_template("{a} and {b}")

        with caplog.at_level(logging.WARNING, logger="notifications"):
            assert template.render({}) == "{a} and {b}"

    @pytest.mark.parametrize(
        "body",
        [
            "stray { brace",  # unmatched brace
            "positional {0} and {}",  # positional fields
            "price {price:,}",  # format spec on a missing key
            "{order.number}",  # attribute access on a missing key
        ],
    )
    def test_malformed_body_never_raises_and_returns_body_unrendered(
        self, body, caplog
    ):
        template = make_template(body)

        with caplog.at_level(logging.WARNING, logger="notifications"):
            result = template.render({"order_number": "ORD-1"})

        assert result == body
        assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.django_db
class TestNotificationTemplateModel:
    def test_unique_together_blocks_duplicate_channel_event_pair(self):
        # A free pair (the seed migration owns the real ones).
        NotificationTemplate.objects.filter(
            channel=Channel.SMS, event=Event.WELCOME
        ).delete()
        NotificationTemplate.objects.create(
            channel=Channel.SMS, event=Event.WELCOME, body="first"
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                NotificationTemplate.objects.create(
                    channel=Channel.SMS, event=Event.WELCOME, body="second"
                )

    def test_same_event_on_different_channels_is_allowed(self):
        NotificationTemplate.objects.filter(event=Event.WELCOME).delete()
        NotificationTemplate.objects.create(
            channel=Channel.SMS, event=Event.WELCOME, body="a"
        )
        NotificationTemplate.objects.create(
            channel=Channel.IN_APP, event=Event.WELCOME, body="b"
        )

        assert NotificationTemplate.objects.filter(event=Event.WELCOME).count() == 2

    def test_str_uses_event_and_channel_display_names(self):
        template = make_template("x", channel=Channel.EMAIL, event=Event.PASSWORD_RESET)

        assert str(template) == "Password Reset — Email"

    def test_is_active_defaults_to_true(self):
        assert make_template("x").is_active is True


@pytest.mark.django_db
class TestSeededTemplates:
    def test_otp_code_sms_template_is_seeded_in_persian(self):
        template = NotificationTemplate.objects.get(
            channel=Channel.SMS, event=Event.OTP_CODE
        )

        assert template.is_active is True
        assert template.body.strip()
        assert PERSIAN_LETTERS.search(template.body)
        assert "{code}" in template.body
        # Renders end-to-end with the OTP service's context key.
        rendered = template.render({"code": "123456"})
        assert "123456" in rendered
        assert "{code}" not in rendered

    def test_every_seeded_template_is_non_empty_persian(self):
        templates = list(NotificationTemplate.objects.all())

        assert len(templates) == 18
        for template in templates:
            assert template.body.strip(), template
            assert PERSIAN_LETTERS.search(template.body), template
            # Only {placeholders} may contain Latin letters.
            assert not re.search(
                r"[A-Za-z]", PLACEHOLDER.sub("", template.body)
            ), template

    def test_every_email_template_has_a_persian_subject(self):
        emails = NotificationTemplate.objects.filter(channel=Channel.EMAIL)

        assert emails.exists()
        for template in emails:
            assert PERSIAN_LETTERS.search(template.subject), template

    def test_non_email_templates_have_no_subject(self):
        assert not (
            NotificationTemplate.objects.exclude(channel=Channel.EMAIL)
            .exclude(subject="")
            .exists()
        )


@pytest.mark.django_db
class TestNotificationLog:
    def make_log(self, **kwargs):
        defaults = {
            "channel": Channel.SMS,
            "event": Event.OTP_CODE,
            "recipient": "+989121234567",
            "status": NotificationLog.Status.SENT,
        }
        defaults.update(kwargs)
        return NotificationLog.objects.create(**defaults)

    @pytest.mark.parametrize("status", NotificationLog.Status.values)
    def test_row_can_be_created_for_each_status(self, status):
        log = self.make_log(status=status)

        log.refresh_from_db()
        assert log.status == status
        assert log.sent_at is not None
        assert log.error_message == ""

    def test_failed_row_stores_error_message(self):
        log = self.make_log(
            status=NotificationLog.Status.FAILED, error_message="credentials expired"
        )

        log.refresh_from_db()
        assert log.error_message == "credentials expired"

    def test_user_none_is_valid(self):
        log = self.make_log(user=None)

        log.refresh_from_db()
        assert log.user is None

    def test_deleting_the_user_keeps_the_log_row(self):
        user = UserFactory()
        log = self.make_log(user=user)

        user.delete()

        log.refresh_from_db()
        assert log.user is None

    def test_related_name_exposes_logs_on_user(self):
        user = UserFactory()
        log = self.make_log(user=user)

        assert list(user.notification_logs.all()) == [log]

    def test_default_ordering_is_newest_first(self):
        first = self.make_log()
        second = self.make_log()

        assert list(NotificationLog.objects.all()) == [second, first]

    def test_str_is_readable(self):
        log = self.make_log(
            channel=Channel.EMAIL,
            event=Event.ORDER_CONFIRMED,
            recipient="sara@example.com",
            status=NotificationLog.Status.FAILED,
        )

        assert str(log) == ("order_confirmed to sara@example.com via email — failed")
