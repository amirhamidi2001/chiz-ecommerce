import pytest
from django.test import RequestFactory
from rest_framework.test import APIClient
from shop.tests.factories import (
    BrandFactory,
    CategoryFactory,
    ColorFactory,
    ProductColorFactory,
    ProductFactory,
    ProductImageFactory,
    ReviewFactory,
    UserFactory,
)

# ─── HTTP clients ────────────────────────────────────────────────────────────


@pytest.fixture
def api_client():
    """Unauthenticated DRF APIClient."""
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def auth_client(user):
    """DRF APIClient authenticated as `user` (fixture above)."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def rf():
    """Django RequestFactory for unit-testing views directly."""
    return RequestFactory()


# ─── Individual model instances ───────────────────────────────────────────────


@pytest.fixture
def category(db):
    return CategoryFactory(name="Electronics", slug="electronics")


@pytest.fixture
def child_category(db, category):
    return CategoryFactory(name="Smartphones", slug="smartphones", parent=category)


@pytest.fixture
def brand(db):
    return BrandFactory(name="TestBrand", slug="testbrand")


@pytest.fixture
def color(db):
    return ColorFactory(name="Black", hex_code="#000000")


@pytest.fixture
def product(db, category, brand):
    return ProductFactory(category=category, brand=brand)


@pytest.fixture
def product_with_relations(db, product, color):
    """Product that already has an image, a color, and three reviews."""
    ProductImageFactory(product=product)
    ProductColorFactory(product=product, color=color)
    ReviewFactory.create_batch(3, product=product)
    return product


# ─── Bulk collections ────────────────────────────────────────────────────────


@pytest.fixture
def products_bulk(db, category, brand):
    """12 products — enough to fill one default page."""
    return ProductFactory.create_batch(12, category=category, brand=brand)


@pytest.fixture
def sale_products(db, category, brand):
    return ProductFactory.create_batch(
        4, category=category, brand=brand, is_sale=True, is_new=False
    )


@pytest.fixture
def new_products(db, category, brand):
    return ProductFactory.create_batch(
        4, category=category, brand=brand, is_new=True, is_sale=False
    )
