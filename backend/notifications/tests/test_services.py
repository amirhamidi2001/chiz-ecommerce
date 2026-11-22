"""
Tests for notifications.services.notify() — the orchestration layer.

The email and in-app senders (Features 16.3 / 16.4) don't exist yet, so tests
install fake modules in sys.modules for them (see `fake_senders`); that also
keeps these tests valid once the real modules land. The SMS provider is
patched at `notifications.sms.get_sms_provider`, which is where notify()
looks it up.
"""

import sys
import types
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext  # noqa: F401
from notifications.models import NotificationLog, NotificationTemplate
from notifications.services import DEFAULT_CUSTOMER_NAME, _default_channels_for, notify
from shop.tests.factories import UserFactory

Channel = NotificationTemplate.Channel
Event = NotificationTemplate.Event
Status = NotificationLog.Status

PHONE = "09123456789"


# ─── helpers / fixtures ────────────────────────────────────────────────────


@pytest.fixture
def sms_provider():
    """Patch get_sms_provider(); returns the provider mock (.send -> True)."""
    provider = MagicMock()
    provider.send.return_value = True
    with patch("notifications.sms.get_sms_provider", return_value=provider):
        yield provider


@pytest.fixture
def fake_senders():
    """Install fake notifications.email / notifications.services_inapp."""
    email = types.ModuleType("notifications.email")
    email.send_notification_email = MagicMock(return_value=True)
    inapp = types.ModuleType("notifications.services_inapp")
    inapp.create_in_app_notification = MagicMock(return_value=True)
    with patch.dict(
        sys.modules,
        {"notifications.email": email, "notifications.services_inapp": inapp},
    ):
        yield types.SimpleNamespace(
            email=email.send_notification_email,
            in_app=inapp.create_in_app_notification,
        )


def make_user(*, order_updates=True, promotions=False, phone=PHONE, **kwargs):
    user = UserFactory(**kwargs)
    user.phone_number = phone
    user.save(update_fields=["phone_number"])
    profile = user.profile
    profile.order_updates = order_updates
    profile.promotions = promotions
    profile.first_name = "Sara"
    profile.save()
    return user


def only_log():
    assert NotificationLog.objects.count() == 1
    return NotificationLog.objects.get()


@contextmanager
def logging_disabled():
    """Silence the expected logger.exception output of failure-path tests."""
    import logging

    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(logging.NOTSET)


# ─── 1. happy path: right sender called, SENT logged ───────────────────────


@pytest.mark.django_db
class TestSuccessfulSend:
    def test_sms_calls_provider_with_rendered_body_and_logs_sent(self, sms_provider):
        user = make_user()

        notify(
            user,
            Event.ORDER_STATUS_CHANGED,
            {"order_number": "ORD-1", "status": "ارسال شد"},
            channels=[Channel.SMS],
        )

        sms_provider.send.assert_called_once()
        phone, body = sms_provider.send.call_args.args
        assert phone == PHONE
        assert "ORD-1" in body and "ارسال شد" in body
        assert "Sara" in body  # customer_name filled from the profile
        assert "{" not in body  # nothing left unrendered
        log = only_log()
        assert (log.user, log.channel, log.event, log.recipient, log.status) == (
            user,
            Channel.SMS,
            Event.ORDER_STATUS_CHANGED,
            PHONE,
            Status.SENT,
        )
        assert log.error_message == ""

    def test_email_calls_sender_with_rendered_subject_and_body(
        self, sms_provider, fake_senders
    ):
        user = make_user(email="sara@example.com")

        notify(
            user,
            Event.ORDER_CONFIRMED,
            {"order_number": "ORD-7", "order_total": "1,000"},
            channels=[Channel.EMAIL],
        )

        fake_senders.email.assert_called_once()
        recipient, subject, body, context = fake_senders.email.call_args.args
        assert recipient == "sara@example.com"
        assert "ORD-7" in subject
        assert "ORD-7" in body and "1,000" in body
        assert context["order_number"] == "ORD-7"
        assert fake_senders.email.call_args.kwargs == {
            "event": "order_confirmed",
            "user_id": user.id,
        }
        sms_provider.send.assert_not_called()
        log = only_log()
        # The sender only QUEUES the email, so notify() logs QUEUED, not SENT.
        assert (log.channel, log.recipient, log.status) == (
            Channel.EMAIL,
            "sara@example.com",
            Status.QUEUED,
        )

    def test_in_app_calls_creator_with_user_and_logs_user_id(self, fake_senders):
        user = make_user()

        notify(
            user,
            Event.ORDER_CONFIRMED,
            {"order_number": "ORD-9"},
            channels=[Channel.IN_APP],
        )

        fake_senders.in_app.assert_called_once()
        called_user, event, body, context = fake_senders.in_app.call_args.args
        assert called_user == user
        assert event == Event.ORDER_CONFIRMED
        assert "ORD-9" in body
        log = only_log()
        assert (log.channel, log.recipient, log.status) == (
            Channel.IN_APP,
            str(user.id),
            Status.SENT,
        )

    def test_default_channels_send_sms_and_email_for_order_events(
        self, sms_provider, fake_senders
    ):
        user = make_user(email="sara@example.com")

        notify(user, Event.ORDER_CONFIRMED, {"order_number": "ORD-1"})

        sms_provider.send.assert_called_once()
        fake_senders.email.assert_called_once()
        assert set(NotificationLog.objects.values_list("channel", flat=True)) == {
            Channel.SMS,
            Channel.EMAIL,
        }

    def test_otp_provider_returning_false_logs_failed_and_is_never_retried(
        self, sms_provider
    ):
        """Other SMS events get a retry on a clean failure (test_tasks.py);
        OTP codes expire too fast for that to be safe."""
        sms_provider.send.return_value = False

        with patch("notifications.tasks.retry_sms_notification.apply_async") as retry:
            notify(make_user(), Event.OTP_CODE, {"code": "123456"})

        retry.assert_not_called()
        log = only_log()
        assert log.status == Status.FAILED
        assert log.error_message == "Provider reported failure."

    def test_caller_context_is_not_mutated(self, sms_provider):
        context = {"code": "123456"}

        notify(make_user(), Event.OTP_CODE, context)

        assert context == {"code": "123456"}

    def test_customer_name_falls_back_when_user_has_no_name(self, sms_provider):
        user = make_user()
        user.profile.first_name = ""
        user.profile.save()

        notify(
            user,
            Event.ORDER_STATUS_CHANGED,
            {"order_number": "ORD-1", "status": "x"},
            channels=[Channel.SMS],
        )

        assert DEFAULT_CUSTOMER_NAME in sms_provider.send.call_args.args[1]

    def test_caller_supplied_customer_name_wins(self, sms_provider):
        notify(
            make_user(),
            Event.ORDER_STATUS_CHANGED,
            {"order_number": "ORD-1", "status": "x", "customer_name": "Reza"},
            channels=[Channel.SMS],
        )

        body = sms_provider.send.call_args.args[1]
        assert "Reza" in body and "Sara" not in body

    def test_empty_channels_list_sends_nothing(self, sms_provider):
        notify(make_user(), Event.OTP_CODE, {"code": "1"}, channels=[])

        sms_provider.send.assert_not_called()
        assert NotificationLog.objects.count() == 0


# ─── 2. no template / no recipient / channel not built → SKIPPED ───────────


@pytest.mark.django_db
class TestSkipped:
    def test_no_active_template_logs_skipped_and_calls_no_sender(
        self, sms_provider, fake_senders
    ):
        NotificationTemplate.objects.filter(
            channel=Channel.SMS, event=Event.OTP_CODE
        ).update(is_active=False)

        notify(make_user(), Event.OTP_CODE, {"code": "123456"})

        log = only_log()
        assert log.status == Status.SKIPPED
        assert (
            log.error_message == "No active template configured for this channel/event."
        )
        assert log.recipient == PHONE
        sms_provider.send.assert_not_called()
        fake_senders.email.assert_not_called()
        fake_senders.in_app.assert_not_called()

    def test_missing_template_row_logs_skipped(self, sms_provider):
        NotificationTemplate.objects.filter(
            channel=Channel.SMS, event=Event.OTP_CODE
        ).delete()

        notify(None, Event.OTP_CODE, {"phone_number": PHONE, "code": "1"})

        assert only_log().status == Status.SKIPPED
        sms_provider.send.assert_not_called()

    def test_no_recipient_logs_skipped_with_reason(self, sms_provider):
        user = make_user(phone="")

        notify(user, Event.OTP_CODE, {"code": "123456"})

        log = only_log()
        assert log.status == Status.SKIPPED
        assert log.error_message == "No recipient address available for this channel."
        assert log.recipient == ""
        sms_provider.send.assert_not_called()

    def test_unbuilt_channel_is_skipped_not_failed(self, sms_provider):
        # Simulate a sender module that isn't installed (None in sys.modules
        # makes the import raise ModuleNotFoundError for exactly that name).
        user = make_user(email="sara@example.com")

        with patch.dict(sys.modules, {"notifications.email": None}):
            notify(
                user, Event.ORDER_CONFIRMED, {"order_number": "1"}, channels=["email"]
            )

        log = only_log()
        assert log.status == Status.SKIPPED
        assert "not available" in log.error_message

    def test_import_error_inside_a_sender_is_a_real_failure(self, sms_provider):
        """Only a *missing sender module* means 'not built'; a broken import
        inside an existing one is a bug and must surface as FAILED."""
        broken = types.ModuleType("notifications.email")

        def explode(*args, **kwargs):
            raise ModuleNotFoundError("No module named 'smtp_lib'", name="smtp_lib")

        broken.send_notification_email = explode
        user = make_user(email="sara@example.com")

        with patch.dict(sys.modules, {"notifications.email": broken}):
            with logging_disabled():
                notify(
                    user,
                    Event.ORDER_CONFIRMED,
                    {"order_number": "1"},
                    channels=["email"],
                )

        assert only_log().status == Status.FAILED


# ─── 3. failures are contained ─────────────────────────────────────────────


@pytest.mark.django_db
class TestFailureIsolation:
    def test_sender_exception_is_caught_logged_failed_and_not_propagated(
        self, sms_provider
    ):
        sms_provider.send.side_effect = RuntimeError("Kavenegar 401: bad API key")
        reached_after_notify = False

        with logging_disabled():
            notify(make_user(), Event.OTP_CODE, {"code": "123456"})
            # The business operation that called notify() carries on.
            reached_after_notify = True

        assert reached_after_notify
        log = only_log()
        assert log.status == Status.FAILED
        assert log.error_message == "Kavenegar 401: bad API key"

    def test_failure_is_logged_with_traceback_for_operators(self, sms_provider, caplog):
        sms_provider.send.side_effect = RuntimeError("boom")

        notify(make_user(), Event.OTP_CODE, {"code": "1"})

        assert any(r.name == "notifications" and r.exc_info for r in caplog.records)

    def test_one_channel_failing_does_not_block_the_others(
        self, sms_provider, fake_senders
    ):
        sms_provider.send.side_effect = RuntimeError("sms down")
        user = make_user(email="sara@example.com")

        with logging_disabled():
            notify(user, Event.ORDER_CONFIRMED, {"order_number": "1"})

        fake_senders.email.assert_called_once()
        statuses = dict(NotificationLog.objects.values_list("channel", "status"))
        assert statuses == {Channel.SMS: Status.FAILED, Channel.EMAIL: Status.QUEUED}

    def test_business_code_in_an_atomic_block_survives_a_failing_notify(
        self, sms_provider
    ):
        """The motivating case: an order is saved, its SMS blows up, and the
        surrounding transaction still commits normally."""
        sms_provider.send.side_effect = RuntimeError("sms down")
        user = make_user()

        with logging_disabled():
            with transaction.atomic():
                user.profile.first_name = "Changed"
                user.profile.save()
                notify(user, Event.OTP_CODE, {"code": "1"})

        user.profile.refresh_from_db()
        assert user.profile.first_name == "Changed"
        assert only_log().status == Status.FAILED

    def test_notification_log_write_failure_never_propagates(self, sms_provider):
        with patch.object(
            NotificationLog.objects, "create", side_effect=RuntimeError("db down")
        ):
            with logging_disabled():
                notify(make_user(), Event.OTP_CODE, {"code": "1"})

        sms_provider.send.assert_called_once()  # the send itself still happened

    def test_failed_log_insert_does_not_poison_the_callers_transaction(
        self, sms_provider
    ):
        """_log runs in a savepoint: a DB error inside it must leave the
        caller's atomic() block usable."""
        user = make_user()

        with transaction.atomic():
            with patch(
                "notifications.services.NotificationLog.objects.create",
                side_effect=__import__("django").db.DatabaseError("insert failed"),
            ):
                with logging_disabled():
                    notify(user, Event.OTP_CODE, {"code": "1"})
            # Would raise TransactionManagementError if the txn were aborted.
            assert NotificationLog.objects.count() == 0

    def test_template_lookup_error_never_propagates(self, sms_provider):
        with patch(
            "notifications.services.NotificationTemplate.objects.get",
            side_effect=RuntimeError("db down"),
        ):
            with logging_disabled():
                notify(make_user(), Event.OTP_CODE, {"code": "1"})

        sms_provider.send.assert_not_called()

    def test_malformed_template_still_sends(self, sms_provider):
        NotificationTemplate.objects.filter(
            channel=Channel.SMS, event=Event.OTP_CODE
        ).update(body="code { is: {code}")

        with logging_disabled():
            notify(make_user(), Event.OTP_CODE, {"code": "123456"})

        sms_provider.send.assert_called_once()
        assert only_log().status == Status.SENT

    def test_email_subject_with_missing_key_does_not_fail_the_email(
        self, sms_provider, fake_senders
    ):
        NotificationTemplate.objects.filter(
            channel=Channel.EMAIL, event=Event.ORDER_CONFIRMED
        ).update(subject="Order {order_number} {not_in_context}")
        user = make_user(email="sara@example.com")

        with logging_disabled():
            notify(
                user,
                Event.ORDER_CONFIRMED,
                {"order_number": "ORD-1"},
                channels=["email"],
            )

        subject = fake_senders.email.call_args.args[1]
        assert subject == "Order ORD-1 {not_in_context}"
        assert only_log().status == Status.QUEUED

    def test_blank_subject_falls_back_to_event_name(self, sms_provider, fake_senders):
        NotificationTemplate.objects.filter(
            channel=Channel.EMAIL, event=Event.ORDER_CONFIRMED
        ).update(subject="")
        user = make_user(email="sara@example.com")

        notify(user, Event.ORDER_CONFIRMED, {"order_number": "1"}, channels=["email"])

        assert fake_senders.email.call_args.args[1] == Event.ORDER_CONFIRMED


# ─── 4. OTP is always SMS-only ─────────────────────────────────────────────


@pytest.mark.django_db
class TestOtpRouting:
    @pytest.mark.parametrize("order_updates", [True, False])
    @pytest.mark.parametrize("promotions", [True, False])
    def test_otp_is_sms_only_whatever_the_preferences(self, order_updates, promotions):
        user = make_user(order_updates=order_updates, promotions=promotions)

        assert _default_channels_for(user, Event.OTP_CODE) == [Channel.SMS]

    def test_otp_is_sms_only_even_when_context_has_an_email(self):
        assert _default_channels_for(
            None, Event.OTP_CODE, {"email": "a@b.co", "phone_number": PHONE}
        ) == [Channel.SMS]

    def test_otp_notify_sends_exactly_one_sms_and_nothing_else(
        self, sms_provider, fake_senders
    ):
        user = make_user(
            order_updates=False, promotions=False, email="sara@example.com"
        )

        notify(user, Event.OTP_CODE, {"code": "123456"})

        sms_provider.send.assert_called_once()
        assert "123456" in sms_provider.send.call_args.args[1]
        fake_senders.email.assert_not_called()
        fake_senders.in_app.assert_not_called()
        assert only_log().channel == Channel.SMS


# ─── 5. preferences ────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDefaultChannels:
    ORDER_EVENTS = [
        Event.ORDER_CONFIRMED,
        Event.ORDER_STATUS_CHANGED,
        Event.SHIPPING_UPDATE,
    ]
    PROMO_EVENTS = [Event.BACK_IN_STOCK, Event.PRICE_DROP]

    @pytest.mark.parametrize("event", ORDER_EVENTS)
    def test_order_events_go_sms_and_email_when_order_updates_on(self, event):
        user = make_user(order_updates=True)

        assert _default_channels_for(user, event) == [Channel.SMS, Channel.EMAIL]

    @pytest.mark.parametrize("event", ORDER_EVENTS)
    def test_order_events_are_suppressed_when_order_updates_off(self, event):
        user = make_user(order_updates=False, promotions=True)

        assert _default_channels_for(user, event) == []

    @pytest.mark.parametrize("event", PROMO_EVENTS)
    def test_promo_events_go_email_when_promotions_on(self, event):
        user = make_user(promotions=True)

        assert _default_channels_for(user, event) == [Channel.EMAIL]

    @pytest.mark.parametrize("event", PROMO_EVENTS)
    def test_promo_events_are_suppressed_when_promotions_off(self, event):
        user = make_user(promotions=False, order_updates=True)

        assert _default_channels_for(user, event) == []

    @pytest.mark.parametrize("event", PROMO_EVENTS)
    def test_notify_sends_nothing_to_a_user_with_promotions_off(
        self, event, sms_provider, fake_senders
    ):
        user = make_user(promotions=False, email="sara@example.com")

        notify(user, event, {"product_name": "Serum"})

        sms_provider.send.assert_not_called()
        fake_senders.email.assert_not_called()
        assert NotificationLog.objects.count() == 0

    def test_notify_emails_a_user_with_promotions_on(self, sms_provider, fake_senders):
        user = make_user(promotions=True, email="sara@example.com")

        notify(user, Event.PRICE_DROP, {"product_name": "Serum"})

        fake_senders.email.assert_called_once()
        assert only_log().status == Status.QUEUED

    @pytest.mark.parametrize("event", [Event.WELCOME, Event.PASSWORD_RESET])
    def test_account_mail_is_email_regardless_of_preferences(self, event):
        user = make_user(order_updates=False, promotions=False)

        assert _default_channels_for(user, event) == [Channel.EMAIL]

    def test_every_default_channel_has_a_seeded_template(self):
        """Guards the seed migrations against drifting from the routing
        rules: otherwise a default channel would always be logged SKIPPED."""
        user = make_user(order_updates=True, promotions=True)
        for event in Event.values:
            for channel in _default_channels_for(user, event):
                assert NotificationTemplate.objects.filter(
                    channel=channel, event=event, is_active=True
                ).exists(), (channel, event)


# ─── 6. guests (user=None) ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestGuestNotifications:
    def test_phone_in_context_resolves_sms_channel_and_recipient(self, sms_provider):
        notify(None, Event.OTP_CODE, {"phone_number": PHONE, "code": "123456"})

        sms_provider.send.assert_called_once()
        assert sms_provider.send.call_args.args[0] == PHONE
        log = only_log()
        assert (log.user, log.channel, log.recipient, log.status) == (
            None,
            Channel.SMS,
            PHONE,
            Status.SENT,
        )

    def test_default_channels_for_guest_follow_the_context(self):
        phone_only = _default_channels_for(
            None, Event.ORDER_CONFIRMED, {"phone_number": PHONE}
        )
        email_only = _default_channels_for(
            None, Event.ORDER_CONFIRMED, {"email": "g@example.com"}
        )
        both = _default_channels_for(
            None,
            Event.ORDER_CONFIRMED,
            {"email": "g@example.com", "phone_number": PHONE},
        )

        assert phone_only == [Channel.SMS]
        assert email_only == [Channel.EMAIL]
        assert both == [Channel.EMAIL, Channel.SMS]

    def test_guest_with_no_contact_info_gets_no_channels_and_no_crash(self):
        assert _default_channels_for(None, Event.ORDER_CONFIRMED) == []
        assert _default_channels_for(None, Event.ORDER_CONFIRMED, {}) == []

    def test_guest_notify_without_contact_info_does_nothing(self, sms_provider):
        notify(None, Event.ORDER_CONFIRMED, {"order_number": "1"})

        sms_provider.send.assert_not_called()
        assert NotificationLog.objects.count() == 0

    def test_guest_gets_default_customer_name(self, sms_provider):
        notify(
            None,
            Event.ORDER_STATUS_CHANGED,
            {"phone_number": PHONE, "order_number": "ORD-1", "status": "x"},
        )

        assert DEFAULT_CUSTOMER_NAME in sms_provider.send.call_args.args[1]

    def test_anonymous_user_is_treated_as_no_user(self, sms_provider):
        notify(AnonymousUser(), Event.OTP_CODE, {"phone_number": PHONE, "code": "1"})

        log = only_log()
        assert log.user is None and log.status == Status.SENT

    def test_user_without_a_profile_falls_back_to_context(self, sms_provider):
        user = make_user()
        user.profile.delete()
        user = type(user).objects.get(pk=user.pk)  # drop the cached relation

        assert _default_channels_for(
            user, Event.ORDER_CONFIRMED, {"phone_number": PHONE}
        ) == [Channel.SMS]


# ─── seeds vs. the contexts the wired call sites actually pass ─────────────

# Mirrors shop/tasks.py (back_in_stock, price_drop) and order/signals.py
# (order_status_changed), plus the customer_name notify() injects. If a call
# site or a seeded template changes, this fails instead of customers seeing
# a literal "{placeholder}" in an SMS.
WIRED_CALL_SITE_CONTEXTS = {
    Event.BACK_IN_STOCK: {
        "product_name": "سرم",
        "variant_sku": "SKU-1",
        "product_url": "https://shop.example/product/serum",
        "customer_name": "سارا",
    },
    Event.PRICE_DROP: {
        "product_name": "سرم",
        "old_price": "1,250,000",
        "new_price": "990,000",
        "product_url": "https://shop.example/product/serum",
        "customer_name": "سارا",
    },
    Event.ORDER_STATUS_CHANGED: {
        "order_number": "ORD-1",
        "old_status": "pending",
        "new_status": "processing",
        "status": "در حال پردازش",
        "customer_name": "سارا",
        "email": "a@example.com",
        "phone_number": PHONE,
    },
}


@pytest.mark.django_db
@pytest.mark.parametrize("event", list(WIRED_CALL_SITE_CONTEXTS))
def test_seeded_templates_fully_render_with_the_wired_call_site_contexts(event):
    import re

    templates = NotificationTemplate.objects.filter(event=event)
    assert templates.exists()
    for template in templates:
        for text in (
            template.render(WIRED_CALL_SITE_CONTEXTS[event]),
            template.render_subject(WIRED_CALL_SITE_CONTEXTS[event]),
        ):
            assert not re.search(r"\{[a-z_]+\}", text), (template, text)
