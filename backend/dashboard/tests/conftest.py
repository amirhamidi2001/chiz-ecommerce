from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


# ── HTTP clients ──────────────────────────────────────────────────────────────


@pytest.fixture
def anon_client():
    """Unauthenticated API client."""
    return APIClient()


def _bearer(user: User) -> APIClient:
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client


# ── User factories ────────────────────────────────────────────────────────────


@pytest.fixture
def make_user(db):
    """
    Factory: make_user(email=…, password=…, type=1, **extra) → User
    Profile is assumed to be created via a post_save signal.
    """
    _counter = [0]

    def _make(
        email: str | None = None,
        password: str = "testPass123!",
        user_type: int = 1,
        is_verified: bool = True,
        **extra,
    ) -> User:
        _counter[0] += 1
        if email is None:
            email = f"user{_counter[0]}@example.com"
        user = User.objects.create_user(email=email, password=password, **extra)
        user.type = user_type
        user.is_verified = is_verified
        user.save(update_fields=["type", "is_verified"])
        return user

    return _make


@pytest.fixture
def customer(make_user):
    return make_user(email="customer@example.com", user_type=1)


@pytest.fixture
def admin_user(make_user):
    return make_user(email="admin@example.com", user_type=2)


@pytest.fixture
def superuser_user(make_user):
    return make_user(email="superuser@example.com", user_type=3)


# ── Authenticated clients ─────────────────────────────────────────────────────


@pytest.fixture
def customer_client(customer):
    return _bearer(customer)


@pytest.fixture
def admin_client(admin_user):
    return _bearer(admin_user)


@pytest.fixture
def superuser_client(superuser_user):
    return _bearer(superuser_user)


# ── Shop fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def make_category(db):
    from shop.models import Category

    _counter = [0]

    def _make(name: str | None = None, parent=None):
        _counter[0] += 1
        name = name or f"Category {_counter[0]}"
        return Category.objects.create(name=name, parent=parent)

    return _make


@pytest.fixture
def make_brand(db):
    from shop.models import Brand

    _counter = [0]

    def _make(name: str | None = None):
        _counter[0] += 1
        return Brand.objects.create(name=name or f"Brand {_counter[0]}")

    return _make


@pytest.fixture
def make_product(db, make_category, make_brand):
    from shop.models import Product

    _counter = [0]

    def _make(
        name: str | None = None,
        price: Decimal = Decimal("99.99"),
        stock: int = 10,
        is_sale: bool = False,
        is_new: bool = False,
        category=None,
        brand=None,
    ) -> "Product":
        _counter[0] += 1
        return Product.objects.create(
            name=name or f"Product {_counter[0]}",
            price=price,
            original_price=price,
            stock=stock,
            is_sale=is_sale,
            is_new=is_new,
            category=category or make_category(),
            brand=brand or make_brand(),
        )

    return _make


# ── Order fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def make_order(db, customer):
    from order.models import Order

    _counter = [0]

    def _make(
        user=None,
        status: str = "pending",
        total: Decimal = Decimal("99.99"),
    ) -> "Order":
        _counter[0] += 1
        return Order.objects.create(
            user=user or customer,
            order_number=f"ORD-TEST-{_counter[0]:04d}",
            status=status,
            first_name="Test",
            last_name="User",
            email="customer@example.com",
            phone="5550001234",
            shipping_address="123 Test St",
            shipping_city="Testville",
            shipping_state="CA",
            shipping_zip="90001",
            shipping_country="US",
            payment_method="card",
            subtotal=total,
            shipping_cost=Decimal("0.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00"),
            total=total,
        )

    return _make


# ── Contact fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def make_message(db):
    from contact.models import ContactMessage

    _counter = [0]

    def _make():
        _counter[0] += 1
        return ContactMessage.objects.create(
            name=f"Sender {_counter[0]}",
            email=f"sender{_counter[0]}@example.com",
            subject=f"Subject {_counter[0]}",
            message="Test message body.",
        )

    return _make
