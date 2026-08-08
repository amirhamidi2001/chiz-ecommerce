import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


# ─── HTTP clients ──────────────────────────────────────────────────────────


@pytest.fixture
def api_client():
    """Unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def auth_client(user):
    """DRF client pre-authenticated with a valid JWT for `user`."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


# ─── Users ─────────────────────────────────────────────────────────────────


@pytest.fixture
def create_user(db):
    """
    Factory fixture.  Call it with any keyword args accepted by create_user().

    Usage:
        user = create_user(email='foo@example.com', password='Pass1234!')
    """

    def _factory(
        email="user@example.com",
        password="SecurePass123!",
        first_name="Jane",
        last_name="Doe",
        **kwargs,
    ):
        user = User.objects.create_user(email=email, password=password, **kwargs)
        # The Profile is created by the post_save signal; just update names.
        user.profile.first_name = first_name
        user.profile.last_name = last_name
        user.profile.save()
        return user

    return _factory


@pytest.fixture
def user(create_user):
    """A single ready-to-use regular user."""
    return create_user()


@pytest.fixture
def second_user(create_user):
    """A second user for isolation tests."""
    return create_user(email="other@example.com")


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email="admin@example.com",
        password="AdminPass123!",
    )


# ─── Token helpers ─────────────────────────────────────────────────────────


@pytest.fixture
def user_tokens(user):
    """Return {'access': ..., 'refresh': ...} strings for `user`."""
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


# ─── Settings overrides ────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    """
    Use the fastest hasher in tests so password-heavy tests don't slow down.
    Django's MD5PasswordHasher is fine for testing (never use in production).
    """
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def email_backend(settings):
    """Capture outgoing emails in memory instead of sending them."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
