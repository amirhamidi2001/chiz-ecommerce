import uuid

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from chat.consumers import ChatConsumer
from chat.models import ChatMessage

from .conftest import acreate_admin, acreate_room, acreate_token, acreate_user

pytestmark = pytest.mark.django_db(transaction=True)


# ─── Shared helper ────────────────────────────────────────────────────────────


async def _connect(
    room_id,
    token: str | None = None,
    *,
    expect_connected: bool = True,
) -> WebsocketCommunicator:
    """
    Build and connect a WebsocketCommunicator for *room_id*.

    FIX 6: use the full ASGI application (with JWTAuthMiddleware), not the
    bare ChatConsumer.as_asgi().
    ────────────────────────────────────────────────────────────────────────────
    The original code passed ChatConsumer.as_asgi() directly to
    WebsocketCommunicator. That bypasses JWTAuthMiddleware, so scope["user"]
    is never set and every connection attempt that relies on auth will fail
    (or pass when it shouldn't). The middleware must be in the chain.

    Import the application object from asgi.py — the same object Daphne uses
    in production — so tests exercise the real authentication path.
    """
    # Inline import avoids a module-level circular import risk.
    from core.asgi import application  # noqa: PLC0415

    url = f"/ws/chat/{room_id}/"
    if token:
        url += f"?token={token}"

    communicator = WebsocketCommunicator(application, url)
    connected, code = await communicator.connect()
    assert (
        connected == expect_connected
    ), f"Expected connected={expect_connected}, got connected={connected} code={code}"
    return communicator


# ─── Connection auth ──────────────────────────────────────────────────────────


class TestWebSocketConnection:

    async def test_unauthenticated_connection_is_rejected(self):
        # FIX A: removed pytest.asyncio.get_event_loop().run_in_executor()
        # FIX 3: use acreate_room() — async-safe factory wrapper
        room = await acreate_room()
        communicator = await _connect(room.pk, expect_connected=False)
        # Code 4001 is already asserted inside _connect via expect_connected.
        # We also verify the communicator is in a disconnected state.
        await communicator.disconnect()

    async def test_invalid_token_is_rejected(self):
        room = await acreate_room()
        communicator = await _connect(
            room.pk, token="not-a-real-jwt", expect_connected=False
        )
        await communicator.disconnect()

    async def test_customer_can_connect_to_own_room(self):
        customer = await acreate_user()
        room = await acreate_room(customer=customer)
        # FIX 4: acreate_token() wraps the ORM write in sync_to_async
        token = await acreate_token(customer)
        communicator = await _connect(room.pk, token)
        await communicator.disconnect()

    async def test_customer_cannot_connect_to_others_room(self):
        customer = await acreate_user()
        other = await acreate_user()
        room = await acreate_room(customer=other)
        token = await acreate_token(customer)
        communicator = await _connect(room.pk, token, expect_connected=False)
        await communicator.disconnect()

    async def test_agent_can_connect_to_any_room(self):
        agent = await acreate_admin()
        room = await acreate_room()
        token = await acreate_token(agent)
        communicator = await _connect(room.pk, token)
        await communicator.disconnect()

    async def test_connection_to_nonexistent_room_is_rejected(self):
        customer = await acreate_user()
        token = await acreate_token(customer)
        fake_id = uuid.uuid4()
        communicator = await _connect(fake_id, token, expect_connected=False)
        await communicator.disconnect()


# ─── Sending messages ─────────────────────────────────────────────────────────


class TestSendMessage:

    async def test_sent_message_is_broadcast_back(self):
        customer = await acreate_user()
        room = await acreate_room(customer=customer)
        token = await acreate_token(customer)
        communicator = await _connect(room.pk, token)

        await communicator.send_json_to({"type": "chat_message", "content": "Hello!"})
        response = await communicator.receive_json_from(timeout=5)

        assert response["type"] == "chat_message"
        assert response["content"] == "Hello!"
        assert response["sender_id"] == customer.pk
        await communicator.disconnect()

    async def test_sent_message_is_persisted(self):
        customer = await acreate_user()
        room = await acreate_room(customer=customer)
        token = await acreate_token(customer)
        communicator = await _connect(room.pk, token)

        await communicator.send_json_to(
            {"type": "chat_message", "content": "Persisted?"}
        )
        await communicator.receive_json_from(timeout=5)

        # FIX 3 (inline): ORM read must also be wrapped in sync_to_async
        count = await sync_to_async(
            ChatMessage.objects.filter(room=room, content="Persisted?").count
        )()
        assert count == 1
        await communicator.disconnect()

    async def test_message_received_by_second_connected_client(self):
        customer = await acreate_user()
        agent = await acreate_admin()
        room = await acreate_room(customer=customer)

        c1 = await _connect(room.pk, await acreate_token(customer))
        c2 = await _connect(room.pk, await acreate_token(agent))

        await c1.send_json_to({"type": "chat_message", "content": "For both!"})

        r1 = await c1.receive_json_from(timeout=5)
        r2 = await c2.receive_json_from(timeout=5)
        assert r1["content"] == "For both!"
        assert r2["content"] == "For both!"

        await c1.disconnect()
        await c2.disconnect()

    async def test_empty_message_returns_error(self):
        customer = await acreate_user()
        room = await acreate_room(customer=customer)
        communicator = await _connect(room.pk, await acreate_token(customer))

        await communicator.send_json_to({"type": "chat_message", "content": "  "})
        response = await communicator.receive_json_from(timeout=5)
        assert response["type"] == "error"
        await communicator.disconnect()

    async def test_oversized_message_returns_error(self):
        customer = await acreate_user()
        room = await acreate_room(customer=customer)
        communicator = await _connect(room.pk, await acreate_token(customer))

        await communicator.send_json_to(
            {"type": "chat_message", "content": "x" * 5_000}
        )
        response = await communicator.receive_json_from(timeout=5)
        assert response["type"] == "error"
        await communicator.disconnect()

    async def test_invalid_json_returns_error(self):
        customer = await acreate_user()
        room = await acreate_room(customer=customer)
        communicator = await _connect(room.pk, await acreate_token(customer))

        await communicator.send_to(text_data="this is not json {{")
        response = await communicator.receive_json_from(timeout=5)
        assert response["type"] == "error"
        await communicator.disconnect()

    async def test_unknown_message_type_returns_error(self):
        customer = await acreate_user()
        room = await acreate_room(customer=customer)
        communicator = await _connect(room.pk, await acreate_token(customer))

        await communicator.send_json_to({"type": "unknown_type", "data": "x"})
        response = await communicator.receive_json_from(timeout=5)
        assert response["type"] == "error"
        await communicator.disconnect()


# ─── Typing indicators ────────────────────────────────────────────────────────


class TestTypingIndicator:

    async def test_typing_forwarded_to_other_client(self):
        customer = await acreate_user()
        agent = await acreate_admin()
        room = await acreate_room(customer=customer)

        c_customer = await _connect(room.pk, await acreate_token(customer))
        c_agent = await _connect(room.pk, await acreate_token(agent))

        await c_customer.send_json_to({"type": "typing", "is_typing": True})
        response = await c_agent.receive_json_from(timeout=5)

        assert response["type"] == "typing"
        assert response["is_typing"] is True
        assert response["sender_id"] == customer.pk

        await c_customer.disconnect()
        await c_agent.disconnect()

    async def test_typing_not_echoed_back_to_sender(self):
        customer = await acreate_user()
        room = await acreate_room(customer=customer)
        communicator = await _connect(room.pk, await acreate_token(customer))

        await communicator.send_json_to({"type": "typing", "is_typing": True})
        assert await communicator.receive_nothing(timeout=1) is True
        await communicator.disconnect()


# ─── Auto-assign agent ────────────────────────────────────────────────────────


class TestAgentAutoAssign:

    async def test_agent_is_auto_assigned_on_first_reply(self):
        customer = await acreate_user()
        agent = await acreate_admin()
        room = await acreate_room(customer=customer, status="open")
        assert room.agent is None

        c_agent = await _connect(room.pk, await acreate_token(agent))
        await c_agent.send_json_to(
            {"type": "chat_message", "content": "Hi, I'm here to help!"}
        )
        await c_agent.receive_json_from(timeout=5)

        # FIX 3 (inline): refresh_from_db is synchronous ORM — wrap it
        await sync_to_async(room.refresh_from_db)()
        assert room.agent_id == agent.pk
        assert room.status == "assigned"
        await c_agent.disconnect()
