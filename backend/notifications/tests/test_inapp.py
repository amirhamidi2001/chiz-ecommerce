"""
Tests for the in-app notification inbox (Feature 16.4):
UserNotification, create_in_app_notification(), and the
/api/notifications/ endpoints.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from notifications.models import NotificationLog, NotificationTemplate, UserNotification
from notifications.services import notify
from notifications.services_inapp import _build_link_url, create_in_app_notification
from rest_framework.test import APIClient
from shop.tests.factories import UserFactory

Event = NotificationTemplate.Event

LIST_URL = "/api/notifications/"
MARK_ALL_URL = "/api/notifications/mark-all-read/"


def detail_url(pk):
    return f"/api/notifications/{pk}/"


def make_notification(user, *, message="پیام", is_read=False, age_minutes=0, **kwargs):
    """Create a row, then back-date it (created_at is auto_now_add)."""
    notification = UserNotification.objects.create(
        user=user,
        event=kwargs.pop("event", Event.ORDER_STATUS_CHANGED),
        message=message,
        is_read=is_read,
        **kwargs,
    )
    UserNotification.objects.filter(pk=notification.pk).update(
        created_at=timezone.now() - timedelta(minutes=age_minutes)
    )
    return notification


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def other_user(db):
    return UserFactory()


@pytest.fixture
def client(user):
    api_client = APIClient()
    api_client.force_authenticate(user)
    return api_client


# ─── 1 & 2. create_in_app_notification() ───────────────────────────────────


@pytest.mark.django_db
class TestCreateInAppNotification:
    def test_creates_row_with_derived_order_link(self, user):
        result = create_in_app_notification(
            user,
            Event.ORDER_STATUS_CHANGED,
            "سفارش شما ارسال شد.",
            {"order_number": "ORD-1", "order_id": 42},
        )

        assert result is True
        notification = UserNotification.objects.get()
        assert notification.user == user
        assert notification.event == Event.ORDER_STATUS_CHANGED
        assert notification.message == "سفارش شما ارسال شد."
        assert notification.link_url == "/order-confirmation/42"
        assert notification.is_read is False

    def test_product_event_links_to_the_product_page(self, user):
        create_in_app_notification(
            user,
            Event.PRICE_DROP,
            "قیمت کم شد.",
            {"product_name": "Lipstick", "product_slug": "lipstick"},
        )

        assert UserNotification.objects.get().link_url == "/product/lipstick"

    def test_context_without_link_data_gives_empty_link(self, user):
        create_in_app_notification(user, Event.WELCOME, "خوش آمدید", {})

        assert UserNotification.objects.get().link_url == ""

    def test_none_user_returns_false_and_creates_nothing(self, db):
        result = create_in_app_notification(
            None, Event.ORDER_CONFIRMED, "msg", {"order_number": "ORD-1"}
        )

        assert result is False
        assert UserNotification.objects.count() == 0


class TestBuildLinkUrl:
    """Pure function — no database needed."""

    @pytest.mark.parametrize(
        "context",
        [
            {"order_number": "ORD-1"},  # no order_id → would be /…//
            {"order_id": 5},  # no order_number
            {"product_name": "X"},  # no slug
            {"product_slug": "x"},  # no name
            {},
            None,
        ],
    )
    def test_incomplete_context_never_builds_a_broken_link(self, context):
        assert _build_link_url(Event.ORDER_CONFIRMED, context) == ""

    def test_order_link_wins_when_both_present(self):
        context = {
            "order_number": "ORD-1",
            "order_id": 7,
            "product_name": "X",
            "product_slug": "x",
        }
        assert _build_link_url(Event.ORDER_CONFIRMED, context) == (
            "/order-confirmation/7"
        )


@pytest.mark.django_db
class TestNotifyIntegration:
    """The lazy import in notify()'s IN_APP branch resolves to the real sender."""

    @pytest.fixture(autouse=True)
    def in_app_template(self):
        # Migration 0002 already seeds an in-app template for this event;
        # pin its body so the assertions don't depend on the seeded wording.
        NotificationTemplate.objects.update_or_create(
            channel=NotificationTemplate.Channel.IN_APP,
            event=Event.ORDER_STATUS_CHANGED,
            defaults={"body": "سفارش {order_number}: {status}", "is_active": True},
        )

    def test_notify_in_app_creates_notification_and_logs_sent(self, user):
        notify(
            user,
            Event.ORDER_STATUS_CHANGED,
            {"order_number": "ORD-9", "order_id": 9, "status": "ارسال شد"},
            channels=["in_app"],
        )

        notification = UserNotification.objects.get(user=user)
        assert notification.message == "سفارش ORD-9: ارسال شد"
        assert notification.link_url == "/order-confirmation/9"
        assert NotificationLog.objects.get().status == NotificationLog.Status.SENT

    def test_notify_in_app_for_guest_is_skipped_not_failed(self, db):
        notify(
            None,
            Event.ORDER_STATUS_CHANGED,
            {"order_number": "ORD-9", "status": "x"},
            channels=["in_app"],
        )

        assert UserNotification.objects.count() == 0
        assert NotificationLog.objects.get().status == NotificationLog.Status.SKIPPED


@pytest.mark.django_db
class TestUserNotificationModel:
    def test_str_uses_email(self, user):
        n = make_notification(user)
        assert str(n) == f"{user.email} — order_status_changed (unread)"

    def test_str_survives_phone_only_account(self, db):
        phone_user = UserFactory(email=None, phone_number="09123456789")
        n = make_notification(phone_user, is_read=True)
        assert str(n) == "09123456789 — order_status_changed (read)"


# ─── 3. GET /api/notifications/ ────────────────────────────────────────────


@pytest.mark.django_db
class TestNotificationList:
    def test_requires_authentication(self):
        assert APIClient().get(LIST_URL).status_code == 401

    def test_returns_only_the_requesting_users_notifications(
        self, client, user, other_user
    ):
        mine = make_notification(user, message="mine")
        make_notification(other_user, message="theirs")

        response = client.get(LIST_URL)

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert [row["id"] for row in response.data["results"]] == [mine.id]

    def test_most_recent_first_and_correctly_paginated(self, client, user):
        # message index == age: n0 is the newest, n4 the oldest.
        rows = [
            make_notification(user, message=f"n{i}", age_minutes=i) for i in range(5)
        ]

        page1 = client.get(LIST_URL, {"page_size": 2}).data
        page2 = client.get(LIST_URL, {"page_size": 2, "page": 2}).data
        page3 = client.get(LIST_URL, {"page_size": 2, "page": 3}).data

        assert page1["count"] == 5
        assert page1["total_pages"] == 3
        assert page1["next"] is not None and page1["previous"] is None
        assert [r["id"] for r in page1["results"]] == [rows[0].id, rows[1].id]
        assert [r["id"] for r in page2["results"]] == [rows[2].id, rows[3].id]
        assert [r["id"] for r in page3["results"]] == [rows[4].id]
        assert page3["next"] is None

    def test_ordering_query_param_cannot_reorder_the_inbox(self, client, user):
        newest = make_notification(user, message="new", age_minutes=0)
        make_notification(user, message="old", age_minutes=10)

        response = client.get(LIST_URL, {"ordering": "created_at"})

        assert response.data["results"][0]["id"] == newest.id

    def test_response_exposes_only_customer_safe_fields(self, client, user):
        make_notification(user, link_url="/product/x")

        row = client.get(LIST_URL).data["results"][0]

        assert set(row) == {
            "id",
            "event",
            "message",
            "link_url",
            "is_read",
            "created_at",
        }


# ─── 4. PATCH /api/notifications/<id>/ ─────────────────────────────────────


@pytest.mark.django_db
class TestNotificationMarkRead:
    def test_requires_authentication(self, user):
        n = make_notification(user)
        response = APIClient().patch(detail_url(n.id), {"is_read": True})
        assert response.status_code == 401

    def test_owner_can_mark_read(self, client, user):
        n = make_notification(user)

        response = client.patch(detail_url(n.id), {"is_read": True}, format="json")

        assert response.status_code == 200
        assert response.data["is_read"] is True
        n.refresh_from_db()
        assert n.is_read is True

    def test_other_users_notification_is_404_and_untouched(self, client, other_user):
        theirs = make_notification(other_user)

        response = client.patch(detail_url(theirs.id), {"is_read": True}, format="json")

        assert response.status_code == 404
        theirs.refresh_from_db()
        assert theirs.is_read is False

    def test_foreign_and_nonexistent_ids_are_indistinguishable(
        self, client, other_user
    ):
        theirs = make_notification(other_user)

        foreign = client.patch(detail_url(theirs.id), {"is_read": True}, format="json")
        missing = client.patch(detail_url(999999), {"is_read": True}, format="json")

        assert foreign.status_code == missing.status_code == 404
        assert foreign.data == missing.data

    def test_only_is_read_is_writable(self, client, user):
        n = make_notification(user, message="original", link_url="/product/x")

        client.patch(
            detail_url(n.id),
            {"is_read": True, "message": "hacked", "link_url": "/evil"},
            format="json",
        )

        n.refresh_from_db()
        assert n.is_read is True
        assert n.message == "original"
        assert n.link_url == "/product/x"

    def test_put_and_delete_are_not_allowed(self, client, user):
        n = make_notification(user)
        assert client.put(detail_url(n.id), {}, format="json").status_code == 405
        assert client.delete(detail_url(n.id)).status_code == 405


# ─── 5. POST /api/notifications/mark-all-read/ ─────────────────────────────


@pytest.mark.django_db
class TestMarkAllRead:
    def test_requires_authentication(self):
        assert APIClient().post(MARK_ALL_URL).status_code == 401

    def test_marks_every_unread_for_the_user_and_nobody_elses(
        self, client, user, other_user
    ):
        mine = [make_notification(user, age_minutes=i) for i in range(3)]
        already_read = make_notification(user, is_read=True)
        theirs = [make_notification(other_user, age_minutes=i) for i in range(2)]

        response = client.post(MARK_ALL_URL)

        assert response.status_code == 200
        assert response.data == {"updated": 3}
        for n in mine + [already_read]:
            n.refresh_from_db()
            assert n.is_read is True
        for n in theirs:
            n.refresh_from_db()
            assert n.is_read is False

    def test_is_idempotent(self, client, user):
        make_notification(user)

        client.post(MARK_ALL_URL)
        second = client.post(MARK_ALL_URL)

        assert second.status_code == 200
        assert second.data == {"updated": 0}

    def test_route_is_not_swallowed_by_the_detail_route(self):
        assert reverse("notifications:notification-mark-all-read") == MARK_ALL_URL
