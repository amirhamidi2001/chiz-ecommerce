import itertools
from datetime import timedelta
from decimal import Decimal

from cart.models import Cart, CartItem
from django.contrib.auth import get_user_model
from django.utils import timezone
from order.models import Order
from promotions.models import Coupon, CouponRedemption
from shop.models import Category, Product, ProductVariant

User = get_user_model()


def make_user(email="buyer@example.com", password="TestPass123!", **kwargs):
    return User.objects.create_user(email=email, password=password, **kwargs)


def make_order(user=None, **overrides):
    data = dict(
        user=user,
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        phone="5550001234",
        shipping_address="1 Test St",
        shipping_city="Testville",
        shipping_state="CA",
        shipping_zip="90001",
        shipping_country="US",
        subtotal=Decimal("100.00"),
        shipping_cost=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("80.00"),
    )
    data.update(overrides)
    return Order.objects.create(**data)


def make_saved_coupon(**overrides):
    """A saved, currently-valid 20% coupon unless overridden."""
    now = timezone.now()
    defaults = {
        "code": "SUMMER20",
        "discount_type": Coupon.DiscountType.PERCENT,
        "value": Decimal("20.00"),
        "valid_from": now - timedelta(days=1),
        "valid_until": now + timedelta(days=30),
    }
    defaults.update(overrides)
    return Coupon.objects.create(**defaults)


def make_completed_redemption(coupon, user, discount="10.00"):
    """A redemption tied to a real order, i.e. counted toward usage limits."""
    return CouponRedemption.objects.create(
        coupon=coupon,
        user=user,
        order=make_order(user=user),
        discount_amount=Decimal(discount),
    )


def make_in_progress_redemption(coupon, user, discount="10.00"):
    """A redemption with order=None, i.e. applied to a cart, not checked out."""
    return CouponRedemption.objects.create(
        coupon=coupon, user=user, order=None, discount_amount=Decimal(discount)
    )


# ─── Catalog / cart helpers (for coupon eligibility tests) ───────────────────

_counter = itertools.count(1)


def make_category(name, parent=None):
    category, _ = Category.objects.get_or_create(
        slug=name.lower().replace(" ", "-"),
        defaults={"name": name, "parent": parent},
    )
    return category


def make_variant(price, category=None, name=None):
    """A saved variant (with its own uniquely-slugged product) at `price`."""
    n = next(_counter)
    product = Product.objects.create(
        name=name or f"Product {n}",
        slug=f"coupon-test-product-{n}",
        price=Decimal(price),
        stock=100,
        category=category,
    )
    return ProductVariant.objects.create(
        product=product, sku=f"COUPON-SKU-{n}", price=Decimal(price), stock=100
    )


def make_cart(user, *lines):
    """
    The user's cart containing exactly `lines`, each a (variant, quantity)
    pair. Any items the cart already had are removed first, so tests can
    rebuild a user's cart with different contents.
    """
    cart, _ = Cart.objects.get_or_create(user=user)
    cart.items.all().delete()
    for variant, quantity in lines:
        CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)
    return cart


def make_priced_cart(user, subtotal):
    """A single-item, uncategorised cart whose subtotal is exactly `subtotal`."""
    return make_cart(user, (make_variant(str(subtotal)), 1))
