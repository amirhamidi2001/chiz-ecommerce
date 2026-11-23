"""
Tests for the real-time in-app notification channel (Feature 16.4):
NotificationConsumer and the WebSocket push in create_in_app_notification().

Structure mirrors chat/tests/test_consumers.py: WebsocketCommunicator against
the real ASGI ``application`` (so JWTAuthMiddleware is exercised), and
``django_db(transaction=True)`` so the consumer's thread sees committed rows.
The in-memory channel layer is applied project-wide by backend/conftest.py.

ASYNC/SYNC NOTE: create_in_app_notification() bridges to the async channel
layer with async_to_sync(), which refuses to run on a thread that has a running
event loop. Async tests therefore call it through ``sync_to_async`` — exactly
how it runs in production (sync code on a worker thread) — which also
exercises the bridge for real rather than mocking it.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.db import transaction
from notifications.consumers import notification_group_name
from notifications.models import NotificationTemplate, UserNotification
from notifications.services import notify
from notifications.services_inapp import create_in_app_notification
from rest_framework_simplejwt.tokens import RefreshToken
from shop.tests.factories import UserFactory

pytestmark = pytest.mark.django_db(transaction=True)

Event = NotificationTemplate.Event

acreate_user = sync_to_async(UserFactory)


@sync_to_async
def acreate_token(user) -> str:
    return str(RefreshToken.for_user(user).access_token)


# ─── Shared helper ────────────────────────────────────────────────────────────


async def _connect(
    token: str | None = None, *, expect_connected: bool = True
) -> WebsocketCommunicator:
    """Connect through the full ASGI application (JWTAuthMiddleware included).

    A rejection must use close code 4001 — the same "unauthenticated" code
    ChatConsumer uses, which the frontend treats as "don't retry".
    """
    from core.asgi import application  # noqa: PLC0415

    url = "/ws/notifications/"
    if token:
        url += f"?token={token}"

    communicator = WebsocketCommunicator(application, url)
    connected, code = await communicator.connect()
    assert (
        connected == expect_connected
    ), f"Expected connected={expect_connected}, got connected={connected} code={code}"
    if not expect_connected:
        assert code == 4001
    return communicator


async def _connected_user():
    user = await acreate_user()
    communicator = await _connect(await acreate_token(user))
    return user, communicator


# ─── 1 & 2. Connection / authentication ───────────────────────────────────────


class TestNotificationConnection:

    async def test_authenticated_connection_succeeds_and_joins_users_group(self):
        user, communicator = await _connected_user()

        # Membership proven by behaviour: a group_send to THIS user's group
        # reaches the socket...
        layer = get_channel_layer()
        await layer.group_send(
            notification_group_name(user.pk),
            {"type": "notification.message", "payload": {"ping": 1}},
        )
        assert await communicator.receive_json_from(timeout=5) == {"ping": 1}

        # ...and one to another user's group does not.
        await layer.group_send(
            notification_group_name(user.pk + 1000),
            {"type": "notification.message", "payload": {"ping": 2}},
        )
        assert await communicator.receive_nothing(timeout=0.3)
        await communicator.disconnect()

    async def test_group_name_is_per_user(self):
        assert notification_group_name(7) == "notifications_7"

    async def test_unauthenticated_connection_is_rejected(self):
        communicator = await _connect(expect_connected=False)
        await communicator.disconnect()

    async def test_invalid_token_is_rejected(self):
        communicator = await _connect("not-a-real-jwt", expect_connected=False)
        await communicator.disconnect()

    async def test_disconnect_leaves_the_group(self):
        user, communicator = await _connected_user()
        layer = get_channel_layer()
        group = notification_group_name(user.pk)
        assert layer.groups.get(group)

        await communicator.disconnect()

        assert not layer.groups.get(group)

    async def test_chat_routes_still_work_alongside_notifications(self):
        """Combining both apps' patterns must not shadow the chat route."""
        from core.asgi import application  # noqa: PLC0415

        user = await acreate_user()
        token = await acreate_token(user)
        # No such room → chat consumer rejects with 4003 (not a 404/route miss,
        # which would raise), proving the chat pattern still resolves.
        communicator = WebsocketCommunicator(
            application,
            f"/ws/chat/00000000-0000-0000-0000-000000000000/?token={token}",
        )
        connected, code = await communicator.connect()
        assert connected is False
        assert code == 4003


# ─── 3. Real-time delivery ────────────────────────────────────────────────────


class TestRealTimeDelivery:

    async def test_active_connection_receives_the_notification_payload(self):
        user, communicator = await _connected_user()

        result = await sync_to_async(create_in_app_notification)(
            user,
            Event.ORDER_STATUS_CHANGED,
            "سفارش شما ارسال شد.",
            {"order_number": "ORD-1", "order_id": 42},
        )

        assert result is True
        payload = await communicator.receive_json_from(timeout=5)
        row = await sync_to_async(UserNotification.objects.get)(user=user)
        assert payload == {
            "id": row.id,
            "event": "order_status_changed",
            "message": "سفارش شما ارسال شد.",
            "link_url": "/order-confirmation/42",
            "created_at": row.created_at.isoformat(),
        }
        await communicator.disconnect()

    async def test_every_open_connection_of_the_user_receives_it(self):
        user = await acreate_user()
        token = await acreate_token(user)
        tab1, tab2 = await _connect(token), await _connect(token)

        await sync_to_async(create_in_app_notification)(user, Event.WELCOME, "hi", {})

        for tab in (tab1, tab2):
            assert (await tab.receive_json_from(timeout=5))["message"] == "hi"
            await tab.disconnect()

    async def test_other_users_connection_receives_nothing(self):
        owner = await acreate_user()
        _, bystander = await _connected_user()

        await sync_to_async(create_in_app_notification)(
            owner, Event.WELCOME, "private", {}
        )

        assert await bystander.receive_nothing(timeout=0.3)
        await bystander.disconnect()

    async def test_notify_in_app_channel_delivers_end_to_end(self):
        """notify() → lazy-loaded sender → row + live push."""
        await sync_to_async(NotificationTemplate.objects.update_or_create)(
            channel=NotificationTemplate.Channel.IN_APP,
            event=Event.ORDER_STATUS_CHANGED,
            defaults={"body": "سفارش {order_number}: {status}", "is_active": True},
        )
        user, communicator = await _connected_user()

        await sync_to_async(notify)(
            user,
            Event.ORDER_STATUS_CHANGED,
            {"order_number": "ORD-9", "order_id": 9, "status": "ارسال شد"},
            channels=["in_app"],
        )

        payload = await communicator.receive_json_from(timeout=5)
        assert payload["message"] == "سفارش ORD-9: ارسال شد"
        assert payload["link_url"] == "/order-confirmation/9"
        await communicator.disconnect()


# ─── 4. No live connection / push failures never affect persistence ───────────


class TestNoActiveConnection:

    async def test_no_connection_neither_raises_nor_hangs_and_row_is_persisted(self):
        user = await acreate_user()

        result = await asyncio.wait_for(
            sync_to_async(create_in_app_notification)(
                user, Event.ORDER_CONFIRMED, "msg", {"order_number": "ORD-2"}
            ),
            timeout=5,
        )

        assert result is True
        count = await sync_to_async(UserNotification.objects.filter(user=user).count)()
        assert count == 1

    async def test_none_user_still_returns_false_and_sends_nothing(self):
        user, communicator = await _connected_user()

        result = await sync_to_async(create_in_app_notification)(
            None, Event.ORDER_CONFIRMED, "msg", {}
        )

        assert result is False
        assert await communicator.receive_nothing(timeout=0.3)
        await communicator.disconnect()

    async def test_channel_layer_failure_does_not_lose_or_fail_the_notification(
        self, caplog
    ):
        user = await acreate_user()
        broken_layer = MagicMock()
        broken_layer.group_send = AsyncMock(side_effect=ConnectionError("redis down"))

        with patch(
            "notifications.services_inapp.get_channel_layer",
            return_value=broken_layer,
        ):
            result = await sync_to_async(create_in_app_notification)(
                user, Event.WELCOME, "msg", {}
            )

        assert result is True
        count = await sync_to_async(UserNotification.objects.filter(user=user).count)()
        assert count == 1
        assert "Could not push in-app notification" in caplog.text

    async def test_no_channel_layer_configured_is_tolerated(self):
        user = await acreate_user()

        with patch("notifications.services_inapp.get_channel_layer", return_value=None):
            result = await sync_to_async(create_in_app_notification)(
                user, Event.WELCOME, "msg", {}
            )

        assert result is True


# ─── Transaction safety (sync tests; real atomic blocks) ──────────────────────


class TestPushWaitsForCommit:

    def test_push_is_deferred_until_the_outer_transaction_commits(self):
        user = UserFactory()

        with patch("notifications.services_inapp._push_to_connected_user") as push:
            with transaction.atomic():
                create_in_app_notification(user, Event.WELCOME, "msg", {})
                push.assert_not_called()  # row not visible to clients yet
            push.assert_called_once()

    def test_rolled_back_notification_is_never_pushed(self):
        user = UserFactory()

        with patch("notifications.services_inapp._push_to_connected_user") as push:
            with pytest.raises(RuntimeError):
                with transaction.atomic():
                    create_in_app_notification(user, Event.WELCOME, "msg", {})
                    raise RuntimeError("caller failed")

        push.assert_not_called()
        assert UserNotification.objects.count() == 0
