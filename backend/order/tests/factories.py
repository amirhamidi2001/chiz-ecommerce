from decimal import Decimal

from cart.models import Cart, CartItem
from django.contrib.auth import get_user_model
from shop.models import Category, Product

User = get_user_model()

TAX_RATE = Decimal("0.10")
SHIPPING_COST = Decimal("9.99")


# ─── Fixture helpers ───────────────────────────────────────────────────────────


def make_user(email="buyer@example.com", password="TestPass123!", **kwargs):
    return User.objects.create_user(email=email, password=password, **kwargs)


def make_category(name="Apparel", slug="apparel"):
    cat, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})
    return cat


def make_product(
    *,
    name="T-Shirt",
    slug="t-shirt",
    price="25.00",
    stock=10,
    category=None,
):
    if category is None:
        category = make_category()
    return Product.objects.create(
        name=name,
        slug=slug,
        price=Decimal(price),
        stock=stock,
        category=category,
    )


def make_cart_with_items(user, items):
    """
    Create a Cart for *user* populated with *items*.

    items: list of dicts  →  {"product": Product, "quantity": int}
    """
    cart, _ = Cart.objects.get_or_create(user=user)
    for entry in items:
        CartItem.objects.get_or_create(
            cart=cart,
            product=entry["product"],
            defaults={"quantity": entry["quantity"]},
        )
    return cart


# ── Valid checkout payload factory ────────────────────────────────────────────

VALID_PAYLOAD = {
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane@example.com",
    "phone": "555-1234",
    "address": "42 Elm Street",
    "apartment": "Apt 3B",
    "city": "Portland",
    "state": "OR",
    "zip": "97201",
    "country": "US",
    "billing_same": True,
    "payment_method": "credit_card",
    "card_last_four": "4242",
    "notes": "",
    # NOTE: no "discount" key here on purpose — OrderCreateSerializer no
    # longer accepts client-supplied discount at all (security fix).
}
