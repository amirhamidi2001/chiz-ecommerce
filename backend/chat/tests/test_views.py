import pytest
from rest_framework import status

from .conftest import ChatMessageFactory, ChatRoomFactory, UserFactory

pytestmark = pytest.mark.django_db

MY_ROOM_URL = "/api/chat/room/"
ADMIN_ROOMS_URL = "/api/chat/admin/rooms/"


def messages_url(room_id):
    return f"/api/chat/room/{room_id}/messages/"


def admin_room_url(room_id):
    return f"/api/chat/admin/rooms/{room_id}/"


# ─── Auth guards ──────────────────────────────────────────────────────────────


class TestChatAuthGuards:

    def test_get_my_room_requires_auth(self, api_client):
        assert api_client.get(MY_ROOM_URL).status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_my_room_requires_auth(self, api_client):
        assert (
            api_client.post(MY_ROOM_URL, {}).status_code == status.HTTP_401_UNAUTHORIZED
        )

    def test_admin_rooms_requires_auth(self, api_client):
        assert (
            api_client.get(ADMIN_ROOMS_URL).status_code == status.HTTP_401_UNAUTHORIZED
        )

    def test_admin_rooms_requires_admin_user(self, customer_client):
        assert (
            customer_client.get(ADMIN_ROOMS_URL).status_code
            == status.HTTP_403_FORBIDDEN
        )


# ─── Customer: get active room ────────────────────────────────────────────────


class TestGetMyRoom:

    def test_returns_404_when_no_active_room(self, customer_client):
        res = customer_client.get(MY_ROOM_URL)
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_active_room(self, customer_client, customer, db):
        room = ChatRoomFactory(customer=customer, status="open")
        res = customer_client.get(MY_ROOM_URL)
        assert res.status_code == status.HTTP_200_OK
        assert str(res.data["id"]) == str(room.pk)

    def test_closed_room_not_returned(self, customer_client, customer, db):
        ChatRoomFactory(customer=customer, status="closed")
        res = customer_client.get(MY_ROOM_URL)
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_assigned_room_is_returned(self, customer_client, customer, db):
        room = ChatRoomFactory(customer=customer, status="assigned")
        res = customer_client.get(MY_ROOM_URL)
        assert res.status_code == status.HTTP_200_OK
        assert str(res.data["id"]) == str(room.pk)

    def test_does_not_return_other_customers_room(self, customer_client, db):
        other_customer = UserFactory()
        ChatRoomFactory(customer=other_customer, status="open")
        res = customer_client.get(MY_ROOM_URL)
        assert res.status_code == status.HTTP_404_NOT_FOUND


# ─── Customer: create room ────────────────────────────────────────────────────


class TestCreateRoom:

    def test_create_room_returns_201(self, customer_client):
        res = customer_client.post(MY_ROOM_URL, {"subject": "Need help with order"})
        assert res.status_code == status.HTTP_201_CREATED

    def test_created_room_has_open_status(self, customer_client):
        res = customer_client.post(MY_ROOM_URL, {"subject": "Question"})
        assert res.data["status"] == "open"

    def test_room_subject_is_optional(self, customer_client):
        res = customer_client.post(MY_ROOM_URL, {})
        assert res.status_code == status.HTTP_201_CREATED

    def test_response_contains_room_id(self, customer_client):
        res = customer_client.post(MY_ROOM_URL, {"subject": "Hello"})
        assert "id" in res.data


# ─── Message history ──────────────────────────────────────────────────────────


class TestRoomMessages:

    def test_customer_can_fetch_own_room_messages(self, customer_client, customer, db):
        room = ChatRoomFactory(customer=customer, status="open")
        ChatMessageFactory.create_batch(3, room=room, sender=customer)
        res = customer_client.get(messages_url(room.pk))
        assert res.status_code == status.HTTP_200_OK
        items = res.data.get("results", res.data)
        assert len(items) == 3

    def test_customer_cannot_read_another_rooms_messages(self, customer_client, db):
        other_room = ChatRoomFactory(customer=UserFactory())
        res = customer_client.get(messages_url(other_room.pk))
        # Should be 403 or 404, never 200
        assert res.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)

    def test_messages_ordered_oldest_first(self, customer_client, customer, db):
        room = ChatRoomFactory(customer=customer)
        msg1 = ChatMessageFactory(room=room, sender=customer, content="first")
        msg2 = ChatMessageFactory(room=room, sender=customer, content="second")
        res = customer_client.get(messages_url(room.pk))
        items = res.data.get("results", res.data)
        assert len(items) == 2
        assert items[0]["content"] == "first"
        assert items[1]["content"] == "second"

    def test_fetching_messages_marks_them_as_read(
        self, customer_client, customer, admin_user, db
    ):
        room = ChatRoomFactory(customer=customer)
        # Admin sent message, customer has not read it
        msg = ChatMessageFactory(room=room, sender=admin_user, is_read=False)
        customer_client.get(messages_url(room.pk))
        msg.refresh_from_db()
        assert msg.is_read is True

    def test_agent_can_access_any_room_messages(self, admin_client, db):
        room = ChatRoomFactory(customer=UserFactory())
        ChatMessageFactory(room=room, sender=room.customer)
        res = admin_client.get(messages_url(room.pk))
        assert res.status_code == status.HTTP_200_OK


# ─── Admin: room management ───────────────────────────────────────────────────


class TestAdminRoomList:

    def test_admin_can_list_all_rooms(self, admin_client, db):
        ChatRoomFactory.create_batch(4)
        res = admin_client.get(ADMIN_ROOMS_URL)
        assert res.status_code == status.HTTP_200_OK
        count = res.data.get("count", len(res.data.get("results", res.data)))
        assert count >= 4

    def test_filter_by_open_status(self, admin_client, db):
        ChatRoomFactory(status="open")
        ChatRoomFactory(status="closed")
        res = admin_client.get(ADMIN_ROOMS_URL, {"status": "open"})
        rooms = res.data.get("results", res.data)
        for r in rooms:
            assert r["status"] == "open"

    def test_filter_by_assigned_status(self, admin_client, db):
        ChatRoomFactory(status="assigned")
        ChatRoomFactory(status="open")
        res = admin_client.get(ADMIN_ROOMS_URL, {"status": "assigned"})
        rooms = res.data.get("results", res.data)
        for r in rooms:
            assert r["status"] == "assigned"


class TestAdminRoomDetail:

    def test_admin_can_retrieve_room(self, admin_client, db):
        room = ChatRoomFactory()
        res = admin_client.get(admin_room_url(room.pk))
        assert res.status_code == status.HTTP_200_OK

    def test_admin_can_close_room(self, admin_client, db):
        room = ChatRoomFactory(status="open")
        res = admin_client.patch(admin_room_url(room.pk), {"status": "closed"})
        assert res.status_code == status.HTTP_200_OK
        room.refresh_from_db()
        assert room.status == "closed"

    def test_admin_can_assign_agent(self, admin_client, admin_user, db):
        room = ChatRoomFactory(status="open")
        res = admin_client.patch(admin_room_url(room.pk), {"status": "assigned"})
        assert res.status_code == status.HTTP_200_OK

    def test_nonexistent_room_returns_404(self, admin_client):
        import uuid

        fake_id = uuid.uuid4()
        res = admin_client.get(admin_room_url(fake_id))
        assert res.status_code == status.HTTP_404_NOT_FOUND
