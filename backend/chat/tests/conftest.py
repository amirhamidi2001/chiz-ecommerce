import factory
import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory
from faker import Faker
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

fake = Faker()
User = get_user_model()


# ─── In-memory channel layer override ────────────────────────────────────────
# Applied to the entire test session via autouse so no individual test needs
# to remember it.

IN_MEMORY_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


@pytest.fixture(autouse=True)
def use_in_memory_channel_layer(settings):
    """
    FIX 2 (continued): swap RedisChannelLayer → InMemoryChannelLayer for all
    tests. `settings` is the pytest-django fixture that applies Django setting
    overrides for the duration of the test and rolls them back afterwards.
    """
    settings.CHANNEL_LAYERS = IN_MEMORY_CHANNEL_LAYERS


# ═══════════════════════════════════════════════════════════════════════════
# Factories
# ═══════════════════════════════════════════════════════════════════════════


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.LazyFunction(lambda: fake.unique.email())
    password = factory.PostGenerationMethodCall("set_password", "Str0ngPass!")
    is_active = True
    is_verified = True
    type = 1  # CUSTOMER


class AdminUserFactory(UserFactory):
    is_staff = True
    type = 2  # ADMIN


class SuperUserFactory(UserFactory):
    is_staff = True
    is_superuser = True
    type = 3  # SUPERUSER


class ChatRoomFactory(DjangoModelFactory):
    class Meta:
        model = "chat.ChatRoom"

    customer = factory.SubFactory(UserFactory)
    status = "open"
    subject = factory.LazyFunction(lambda: fake.sentence(nb_words=4))


class ChatMessageFactory(DjangoModelFactory):
    class Meta:
        model = "chat.ChatMessage"

    room = factory.SubFactory(ChatRoomFactory)
    sender = factory.SubFactory(UserFactory)
    content = factory.LazyFunction(fake.sentence)
    message_type = "text"


acreate_user = sync_to_async(UserFactory)
acreate_admin = sync_to_async(AdminUserFactory)
acreate_room = sync_to_async(ChatRoomFactory)
acreate_message = sync_to_async(ChatMessageFactory)


@sync_to_async
def acreate_token(user) -> str:
    """Return a signed JWT access-token string for *user* (async-safe)."""
    return str(RefreshToken.for_user(user).access_token)


# ═══════════════════════════════════════════════════════════════════════════
# Pytest fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer(db):
    return UserFactory()


@pytest.fixture
def admin_user(db):
    return AdminUserFactory()


@pytest.fixture
def superuser(db):
    return SuperUserFactory()


def _jwt_client(user):
    """Return an APIClient with a valid Bearer token for *user*."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


@pytest.fixture
def customer_client(customer):
    return _jwt_client(customer)


@pytest.fixture
def admin_client(admin_user):
    return _jwt_client(admin_user)


@pytest.fixture
def superuser_client(superuser):
    return _jwt_client(superuser)


@pytest.fixture
def chat_room(db, customer):
    return ChatRoomFactory(customer=customer)


@pytest.fixture
def chat_message(db, chat_room, customer):
    return ChatMessageFactory(room=chat_room, sender=customer)
