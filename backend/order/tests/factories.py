from decimal import Decimal

from cart.models import Cart, CartItem
from django.contrib.auth import get_user_model
from shop.models import Category, Color, Product, ProductVariant

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


def make_color(name="Red", hex_code="#FF0000"):
    return Color.objects.create(name=name, hex_code=hex_code)


def make_variant(
    *,
    product=None,
    sku=None,
    color=None,
    price=None,
    stock=10,
    is_active=True,
    **product_kwargs,
):
    """
    Create and return a ProductVariant. If no product is given, one is
    created via make_product(**product_kwargs). If no price is given,
    the variant mirrors the backing product's price (matching how
    checkout reads price off the variant now, per Task 3.1.1.3).
    """
    if product is None:
        product = make_product(**product_kwargs)
    if price is None:
        price = product.price
    if sku is None:
        sku = (
            f"SKU-{product.id}-{ProductVariant.objects.filter(product=product).count()}"
        )
    return ProductVariant.objects.create(
        product=product,
        sku=sku,
        color=color,
        price=Decimal(price),
        stock=stock,
        is_active=is_active,
    )


def make_cart_with_items(user, items):
    """
    Create a Cart for *user* populated with *items*.

    items: list of dicts, either:
      - {"variant": ProductVariant, "quantity": int}                 (preferred)
      - {"product": Product, "quantity": int}  → auto-creates/reuses
        a default variant for that product, for callers that only
        care about product-level setup.
    """
    cart, _ = Cart.objects.get_or_create(user=user)
    for entry in items:
        variant = entry.get("variant")
        if variant is None:
            product = entry["product"]
            variant = ProductVariant.objects.filter(product=product).first()
            if variant is None:
                variant = make_variant(product=product, stock=product.stock)
        CartItem.objects.get_or_create(
            cart=cart,
            variant=variant,
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
