from decimal import Decimal

from cart.models import Cart, CartItem
from django.contrib.auth import get_user_model
from shipping.models import ShippingCarrier, ShippingRate
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
    expiration_date=None,
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
        expiration_date=expiration_date,
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


# ── Shipping fixtures (Task 7.1.1.4) ────────────────────────────────────────


def make_shipping_carrier(*, code=ShippingCarrier.Code.POST, is_active=True):
    """
    Get-or-create a ShippingCarrier by code. Task 7.1.1.2's data migration
    already seeds all four carrier codes (inactive by default, since a
    carrier shouldn't be live until an admin deliberately activates it) —
    reuse that row rather than creating a duplicate (`code` is unique),
    flipping is_active as needed for the test.

    Note: TransactionTestCase-based tests (test_stock_concurrency.py)
    truncate all tables between tests, including this migration-seeded
    data — get_or_create handles that transparently by just creating a
    fresh row on demand when the seeded one is gone.
    """
    carrier, _ = ShippingCarrier.objects.get_or_create(
        code=code,
        defaults={"display_name": ShippingCarrier.Code(code).label},
    )
    if carrier.is_active != is_active:
        carrier.is_active = is_active
        carrier.save(update_fields=["is_active"])
    return carrier


def make_shipping_rate(
    *,
    carrier=None,
    province="tehran",
    city="",
    min_weight_g=0,
    max_weight_g=1_000_000,
    price=None,
    is_active=True,
):
    """
    Get-or-create a ShippingRate. Defaults to a wide weight bracket
    (0-1,000,000g) covering ordinary test carts — whose variants
    generally have no explicit weight_g/volume_ml set and so fall back to
    ProductVariant.weight_g_or_estimate()'s flat ~100g/item estimate —
    without every test needing to reason about exact cart weight.

    price defaults to SHIPPING_COST (9.99) so existing tests that assert
    a specific dollar shipping_cost (carried over from the old flat
    constant) keep passing unchanged.
    """
    if carrier is None:
        carrier = make_shipping_carrier()
    if price is None:
        price = SHIPPING_COST
    rate, _ = ShippingRate.objects.get_or_create(
        carrier=carrier,
        province=province,
        city=city,
        min_weight_g=min_weight_g,
        max_weight_g=max_weight_g,
        defaults={"price": Decimal(price), "is_active": is_active},
    )
    return rate


# ── Valid checkout payload factory ────────────────────────────────────────────

VALID_PAYLOAD = {
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane@example.com",
    "phone": "555-1234",
    "address": "42 Elm Street",
    "apartment": "Apt 3B",
    "city": "Portland",
    "state": "tehran",
    "zip": "1234567890",
    "country": "IR",
    "billing_same": True,
    "payment_method": "credit_card",
    "card_last_four": "4242",
    "notes": "",
    # NOTE: no "discount" key here on purpose — OrderCreateSerializer no
    # longer accepts client-supplied discount at all (security fix).
    #
    # NOTE: also no "shipping_carrier_id"/"shipping_rate_id" keys here —
    # those reference real DB rows that can't exist at module-import time,
    # so they're not part of this static dict. Use valid_payload() below
    # instead of this dict directly whenever a payload will actually be
    # submitted to OrderCreateSerializer/the checkout endpoint; VALID_PAYLOAD
    # itself remains useful for reading individual static field values
    # (e.g. VALID_PAYLOAD["email"]) where no submission happens.
}


def valid_payload(**overrides):
    """
    Returns a fresh copy of VALID_PAYLOAD with a valid
    shipping_carrier_id/shipping_rate_id filled in (Task 7.1.1.4 made
    both required fields) — a default carrier+rate for VALID_PAYLOAD's
    own "tehran" state. Uses get_or_create under the hood, so repeated
    calls resolve to the same underlying rows rather than piling up
    duplicates.
    """
    rate = make_shipping_rate()
    payload = {
        **VALID_PAYLOAD,
        "shipping_carrier_id": rate.carrier_id,
        "shipping_rate_id": rate.id,
    }
    payload.update(overrides)
    return payload
