import pytest

from .conftest import AdminUserFactory, ChatMessageFactory, ChatRoomFactory

pytestmark = pytest.mark.django_db


class TestChatRoom:

    def test_default_status_is_open(self, db):
        room = ChatRoomFactory()
        assert room.status == "open"

    def test_str_contains_customer_email(self, db, customer):
        room = ChatRoomFactory(customer=customer)
        assert customer.email in str(room)

    def test_str_contains_status(self, db):
        room = ChatRoomFactory(status="assigned")
        assert "assigned" in str(room)

    def test_id_is_uuid(self, db):
        import uuid

        room = ChatRoomFactory()
        assert isinstance(room.pk, uuid.UUID)

    def test_agent_is_null_by_default(self, db):
        room = ChatRoomFactory()
        assert room.agent is None

    def test_room_can_be_assigned_to_agent(self, db):
        agent = AdminUserFactory()
        room = ChatRoomFactory(agent=agent, status="assigned")
        assert room.agent == agent
        assert room.status == "assigned"

    def test_room_can_be_closed(self, db):
        room = ChatRoomFactory()
        room.status = "closed"
        room.save()
        room.refresh_from_db()
        assert room.status == "closed"

    def test_subject_is_optional(self, db):
        room = ChatRoomFactory(subject="")
        assert room.subject == ""

    def test_rooms_ordered_by_updated_at_desc(self, db, customer):
        from chat.models import ChatRoom

        room1 = ChatRoomFactory(customer=customer)
        room2 = ChatRoomFactory(customer=customer)
        room2.save()  # auto_now will update updated_at
        rooms = list(ChatRoom.objects.all())
        # Most-recently updated should appear first
        assert rooms[0].updated_at >= rooms[1].updated_at


class TestChatMessage:

    def test_default_message_type_is_text(self, db, chat_room, customer):
        msg = ChatMessageFactory(room=chat_room, sender=customer)
        assert msg.message_type == "text"

    def test_is_read_defaults_to_false(self, db, chat_room, customer):
        msg = ChatMessageFactory(room=chat_room, sender=customer)
        assert msg.is_read is False

    def test_message_linked_to_room(self, db, chat_room, customer):
        msg = ChatMessageFactory(room=chat_room, sender=customer)
        assert msg.room == chat_room

    def test_message_linked_to_sender(self, db, chat_room, customer):
        msg = ChatMessageFactory(room=chat_room, sender=customer)
        assert msg.sender == customer

    def test_system_message_type(self, db, chat_room):
        msg = ChatMessageFactory(
            room=chat_room,
            sender=None,
            message_type="system",
            content="Agent joined the chat.",
        )
        assert msg.message_type == "system"
        assert msg.sender is None

    def test_str_contains_content_snippet(self, db, chat_room, customer):
        msg = ChatMessageFactory(
            room=chat_room, sender=customer, content="Hello world!"
        )
        assert "Hello" in str(msg) or customer.email in str(msg)

    def test_messages_ordered_by_created_at_asc(self, db, chat_room, customer):
        msg1 = ChatMessageFactory(room=chat_room, sender=customer, content="First")
        msg2 = ChatMessageFactory(room=chat_room, sender=customer, content="Second")
        import time

        time.sleep(0.01)
        msgs = list(chat_room.messages.all())
        assert msgs[0] == msg1
        assert msgs[1] == msg2
        assert msgs[0].created_at <= msgs[1].created_at

    def test_mark_message_as_read(self, db, chat_message):
        chat_message.is_read = True
        chat_message.save()
        chat_message.refresh_from_db()
        assert chat_message.is_read is True
