# ruff: noqa: F811  (fixtures imported from test_services shadow their own use)
"""
Tests for the SMS retry mechanism: notify() queueing retry_sms_notification on
a clean first-send failure, and the task itself.

The task is run with `.apply()` (Celery's eager execution), which also
executes `self.retry()` re-runs in-process — so "retries up to max_retries and
then stops" is tested against Celery's real retry bookkeeping rather than a
hand-set `request.retries`. Delays are ignored in eager mode. Nothing here
touches a broker: `apply_async` is always patched when notify() is the caller.
"""

from unittest.mock import MagicMock, patch

import pytest
from notifications.models import NotificationLog, NotificationTemplate
from notifications.services import notify
from notifications.tasks import FIRST_RETRY_DELAY_SECONDS, retry_sms_notification

# Shared fixtures/helpers from the notify() tests.
from .test_services import fake_senders, make_user, only_log, sms_provider  # noqa: F401

Channel = NotificationTemplate.Channel
Event = NotificationTemplate.Event
Status = NotificationLog.Status

PHONE = "09123456789"
APPLY_ASYNC = "notifications.tasks.retry_sms_notification.apply_async"


@pytest.fixture
def retry_queue():
    """Patch apply_async so notify() never reaches a real broker."""
    with patch(APPLY_ASYNC) as mock:
        yield mock


def run_task(user_id=None, event=Event.ORDER_CONFIRMED, body="متن پیام"):
    """Run retry_sms_notification eagerly, including its own retries."""
    return retry_sms_notification.apply(
        kwargs={
            "recipient": PHONE,
            "body": body,
            "event": event,
            "user_id": user_id,
        }
    )


def provider_with(*results):
    """A provider whose successive send() calls return `results`."""
    provider = MagicMock()
    provider.send.side_effect = list(results)
    return patch("notifications.sms.get_sms_provider", return_value=provider), provider


# ─── 3. a failed first send queues the retry ───────────────────────────────


@pytest.mark.django_db
class TestFailedSendQueuesRetry:
    def test_failed_sms_queues_retry_with_correct_arguments(
        self, sms_provider, retry_queue
    ):
        sms_provider.send.return_value = False
        user = make_user()

        notify(
            user,
            Event.ORDER_STATUS_CHANGED,
            {"order_number": "ORD-1", "status": "ارسال شد"},
            channels=[Channel.SMS],
        )

        retry_queue.assert_called_once()
        kwargs = retry_queue.call_args.kwargs
        assert kwargs["countdown"] == 60 == FIRST_RETRY_DELAY_SECONDS
        assert kwargs["kwargs"] == {
            "recipient": PHONE,
            "body": sms_provider.send.call_args.args[1],  # the rendered text
            "event": "order_status_changed",
            "user_id": user.id,
        }
        assert "ORD-1" in kwargs["kwargs"]["body"]
        assert sms_provider.send.call_count == 1  # not retried inline

    def test_guest_failure_queues_retry_with_no_user_id(
        self, sms_provider, retry_queue
    ):
        sms_provider.send.return_value = False

        notify(
            None,
            Event.ORDER_CONFIRMED,
            {"phone_number": PHONE, "order_number": "ORD-2", "order_total": "1"},
        )

        assert retry_queue.call_args.kwargs["kwargs"]["user_id"] is None
        assert retry_queue.call_args.kwargs["kwargs"]["recipient"] == PHONE

    def test_first_failure_is_logged_retrying_not_failed(
        self, sms_provider, retry_queue
    ):
        """The admin can tell 'never went out' from 'retry in flight'."""
        sms_provider.send.return_value = False
        user = make_user()

        notify(user, Event.ORDER_CONFIRMED, {"order_number": "1", "order_total": "2"})

        sms_logs = NotificationLog.objects.filter(channel=Channel.SMS)
        log = sms_logs.get()
        assert log.status == Status.RETRYING
        assert log.status != Status.FAILED
        assert log.recipient == PHONE and log.user == user
        assert "retry queued" in log.error_message
        assert "3 retries" in log.error_message

    def test_a_successful_send_queues_nothing(self, sms_provider, retry_queue):
        notify(
            make_user(),
            Event.ORDER_CONFIRMED,
            {"order_number": "1"},
            channels=[Channel.SMS],
        )

        retry_queue.assert_not_called()
        assert only_log().status == Status.SENT

    def test_otp_failure_is_never_retried(self, sms_provider, retry_queue):
        """OTP codes expire in 120s; a retry would deliver a dead code."""
        sms_provider.send.return_value = False

        notify(make_user(), Event.OTP_CODE, {"code": "482913"})

        retry_queue.assert_not_called()
        log = only_log()
        assert log.status == Status.FAILED
        assert log.error_message == "Provider reported failure."

    def test_otp_code_never_enters_the_retry_payload(self, sms_provider, retry_queue):
        sms_provider.send.return_value = False

        notify(None, Event.OTP_CODE, {"phone_number": PHONE, "code": "482913"})

        retry_queue.assert_not_called()

    def test_broker_failure_while_queueing_logs_failed_and_never_raises(
        self, sms_provider
    ):
        sms_provider.send.return_value = False

        with patch(APPLY_ASYNC, side_effect=ConnectionError("broker down")):
            notify(
                make_user(),
                Event.ORDER_CONFIRMED,
                {"order_number": "1"},
                channels=[Channel.SMS],
            )

        log = only_log()
        assert log.status == Status.FAILED  # not RETRYING: nothing was queued
        assert "could not be queued" in log.error_message
        assert "ConnectionError" in log.error_message

    def test_sms_exception_is_not_retried(self, sms_provider, retry_queue):
        """Only a clean False return retries; an exception stays FAILED."""
        sms_provider.send.side_effect = RuntimeError("provider blew up")

        with patch("notifications.services.logger"):
            notify(
                make_user(),
                Event.ORDER_CONFIRMED,
                {"order_number": "1"},
                channels=[Channel.SMS],
            )

        retry_queue.assert_not_called()
        log = only_log()
        assert log.status == Status.FAILED
        assert log.error_message == "provider blew up"

    def test_skipped_sms_is_not_retried(self, sms_provider, retry_queue):
        NotificationTemplate.objects.filter(
            channel=Channel.SMS, event=Event.ORDER_CONFIRMED
        ).update(is_active=False)

        notify(make_user(), Event.ORDER_CONFIRMED, {"order_number": "1"})
        notify(
            make_user(phone="", email="b@example.com"),
            Event.ORDER_STATUS_CHANGED,
            {"order_number": "1"},
        )

        retry_queue.assert_not_called()
        sms_logs = NotificationLog.objects.filter(channel=Channel.SMS)
        assert set(sms_logs.values_list("status", flat=True)) == {Status.SKIPPED}

    def test_retry_is_independent_of_the_other_channels(
        self, sms_provider, fake_senders, retry_queue
    ):
        """SMS failing queues its retry; the email still goes out normally."""
        sms_provider.send.return_value = False
        user = make_user(email="sara@example.com")

        notify(user, Event.ORDER_CONFIRMED, {"order_number": "1", "order_total": "2"})

        retry_queue.assert_called_once()
        fake_senders.email.assert_called_once()
        statuses = dict(NotificationLog.objects.values_list("channel", "status"))
        assert statuses == {Channel.SMS: Status.RETRYING, Channel.EMAIL: Status.QUEUED}


# ─── 4. email / in-app failures are never retried ──────────────────────────


@pytest.mark.django_db
class TestOnlySmsIsRetried:
    def test_email_failure_queues_no_retry_and_logs_failed(
        self, sms_provider, fake_senders, retry_queue
    ):
        fake_senders.email.return_value = False
        user = make_user(email="sara@example.com")

        notify(
            user, Event.ORDER_CONFIRMED, {"order_number": "1"}, channels=[Channel.EMAIL]
        )

        retry_queue.assert_not_called()
        log = only_log()
        assert (log.channel, log.status) == (Channel.EMAIL, Status.FAILED)
        assert log.error_message == "Provider reported failure."

    def test_in_app_failure_queues_no_retry_and_logs_failed(
        self, sms_provider, fake_senders, retry_queue
    ):
        fake_senders.in_app.return_value = False

        notify(
            make_user(),
            Event.ORDER_CONFIRMED,
            {"order_number": "1"},
            channels=[Channel.IN_APP],
        )

        retry_queue.assert_not_called()
        log = only_log()
        assert (log.channel, log.status) == (Channel.IN_APP, Status.FAILED)

    @pytest.mark.parametrize("channel", [Channel.EMAIL, Channel.IN_APP])
    def test_email_and_in_app_exceptions_queue_no_retry(
        self, channel, sms_provider, fake_senders, retry_queue
    ):
        fake_senders.email.side_effect = RuntimeError("smtp down")
        fake_senders.in_app.side_effect = RuntimeError("db down")
        user = make_user(email="sara@example.com")

        with patch("notifications.services.logger"):
            notify(
                user, Event.ORDER_CONFIRMED, {"order_number": "1"}, channels=[channel]
            )

        retry_queue.assert_not_called()
        assert only_log().status == Status.FAILED

    def test_all_channels_failing_retries_only_the_sms(
        self, sms_provider, fake_senders, retry_queue
    ):
        sms_provider.send.return_value = False
        fake_senders.email.return_value = False
        fake_senders.in_app.return_value = False
        user = make_user(email="sara@example.com")

        notify(
            user,
            Event.ORDER_CONFIRMED,
            {"order_number": "1", "order_total": "2"},
            channels=[Channel.SMS, Channel.EMAIL, Channel.IN_APP],
        )

        retry_queue.assert_called_once()
        assert retry_queue.call_args.kwargs["kwargs"]["recipient"] == PHONE
        statuses = dict(NotificationLog.objects.values_list("channel", "status"))
        assert statuses == {
            Channel.SMS: Status.RETRYING,
            Channel.EMAIL: Status.FAILED,
            Channel.IN_APP: Status.FAILED,
        }


# ─── the task itself ───────────────────────────────────────────────────────


def test_task_is_bounded_by_configuration():
    assert retry_sms_notification.max_retries == 3
    assert retry_sms_notification.default_retry_delay == 120


@pytest.mark.django_db
class TestRetryTask:
    def test_success_on_the_first_retry_logs_sent_with_the_retry_note(self):
        user = make_user()
        patcher, provider = provider_with(True)

        with patcher:
            result = run_task(user_id=user.id, event=Event.ORDER_STATUS_CHANGED)

        assert result.successful()
        provider.send.assert_called_once_with(PHONE, "متن پیام")
        log = only_log()
        assert log.status == Status.SENT
        assert log.error_message == "(sent on retry)"
        assert (log.channel, log.event, log.recipient, log.user) == (
            "sms",
            "order_status_changed",
            PHONE,
            user,
        )

    def test_recovers_midway_and_stops_retrying(self):
        patcher, provider = provider_with(False, False, True)

        with patcher:
            run_task()

        assert provider.send.call_count == 3  # stopped as soon as it worked
        log = only_log()  # exactly one outcome row, no FAILED noise
        assert (log.status, log.error_message) == (Status.SENT, "(sent on retry)")

    def test_failing_every_attempt_ends_in_one_final_failed_after_max_retries(self):
        user = make_user()
        patcher, provider = provider_with(*[False] * 20)

        with patcher:
            result = run_task(user_id=user.id)

        assert result.successful()  # the task finished; it did not blow up
        # 1 initial run + max_retries retries — and NOT indefinitely.
        assert provider.send.call_count == 1 + retry_sms_notification.max_retries == 4
        log = only_log()
        assert log.status == Status.FAILED
        assert log.error_message == "Failed after 3 retries."
        assert log.user == user

    def test_no_outcome_row_is_written_until_the_task_is_done(self):
        """Intermediate failed attempts add no rows (the original RETRYING
        row, written by notify(), is the only in-flight marker)."""
        patcher, _provider = provider_with(False, False, False, False)

        # The task imports _log from services at call time, so patch it there.
        with patcher, patch("notifications.services._log") as log_row:
            run_task()

        assert log_row.call_count == 1
        assert log_row.call_args.args[5] == "Failed after 3 retries."

    def test_provider_raising_counts_as_a_failed_attempt(self):
        patcher, provider = provider_with(
            RuntimeError("boom"), RuntimeError("boom"), True
        )

        with patcher, patch("notifications.tasks.logger"):
            run_task()

        assert provider.send.call_count == 3
        assert only_log().status == Status.SENT

    def test_provider_raising_every_time_still_ends_in_a_logged_failed(self):
        patcher, provider = provider_with(*[RuntimeError("boom")] * 20)

        with patcher, patch("notifications.tasks.logger"):
            result = run_task()

        assert result.successful()
        assert provider.send.call_count == 4
        assert only_log().status == Status.FAILED

    def test_guest_retry_logs_with_no_user(self):
        patcher, _provider = provider_with(True)

        with patcher:
            run_task(user_id=None)

        assert only_log().user is None

    def test_user_deleted_during_the_retry_window_does_not_break_the_log(self):
        user = make_user()
        user_id = user.id
        user.delete()
        patcher, _provider = provider_with(True)

        with patcher:
            result = run_task(user_id=user_id)

        assert result.successful()
        log = only_log()
        assert log.status == Status.SENT and log.user is None


# ─── notify() → queued kwargs → task, end to end ───────────────────────────


@pytest.mark.django_db
class TestEndToEnd:
    def test_failed_send_then_successful_retry_leaves_retrying_then_sent(
        self, sms_provider, retry_queue
    ):
        user = make_user()
        sms_provider.send.return_value = False
        notify(
            user, Event.ORDER_CONFIRMED, {"order_number": "ORD-9", "order_total": "5"}
        )
        queued = retry_queue.call_args.kwargs["kwargs"]

        # Later, the worker runs the queued task; the provider has recovered.
        sms_provider.send.reset_mock()
        sms_provider.send.return_value = True
        retry_sms_notification.apply(kwargs=queued)

        sms_provider.send.assert_called_once_with(PHONE, queued["body"])
        statuses = list(
            NotificationLog.objects.filter(channel="sms")
            .order_by("id")
            .values_list("status", flat=True)
        )
        assert statuses == [Status.RETRYING, Status.SENT]
        # A resolved blip never counts as a failure for the admin filter.
        assert not NotificationLog.objects.filter(status=Status.FAILED).exists()

    def test_failed_send_then_exhausted_retries_leaves_retrying_then_failed(
        self, sms_provider, retry_queue
    ):
        user = make_user()
        sms_provider.send.return_value = False
        notify(
            user, Event.ORDER_CONFIRMED, {"order_number": "ORD-9", "order_total": "5"}
        )
        queued = retry_queue.call_args.kwargs["kwargs"]

        sms_provider.send.reset_mock()
        retry_sms_notification.apply(kwargs=queued)

        assert sms_provider.send.call_count == 4
        statuses = list(
            NotificationLog.objects.filter(channel="sms")
            .order_by("id")
            .values_list("status", flat=True)
        )
        assert statuses == [Status.RETRYING, Status.FAILED]
