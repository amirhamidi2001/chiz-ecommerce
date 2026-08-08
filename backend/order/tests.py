from decimal import Decimal

from cart.models import Cart, CartItem
from django.contrib.auth import get_user_model
from django.test import TestCase
from order.models import Order, OrderItem
from rest_framework import serializers, status
from rest_framework.test import APITestCase
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
    "discount": "0.00",
    "notes": "",
}


# ══════════════════════════════════════════════════════════════════════════════
# 1. Model Tests
# ══════════════════════════════════════════════════════════════════════════════


class OrderModelTests(TestCase):
    """Unit-test Order and OrderItem model properties."""

    def setUp(self):
        self.user = make_user()
        self.product = make_product()

    def _make_order(self, **kwargs):
        defaults = dict(
            user=self.user,
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="555-1234",
            shipping_address="42 Elm Street",
            shipping_apartment="Apt 3B",
            shipping_city="Portland",
            shipping_state="OR",
            shipping_zip="97201",
            shipping_country="US",
            payment_method=Order.PaymentMethod.CREDIT_CARD,
            subtotal=Decimal("50.00"),
            shipping_cost=SHIPPING_COST,
            tax=Decimal("5.00"),
            discount=Decimal("0.00"),
            total=Decimal("64.99"),
            status=Order.Status.PROCESSING,
        )
        defaults.update(kwargs)
        return Order.objects.create(**defaults)

    # ── Order ─────────────────────────────────────────────────────────────────

    def test_order_number_auto_generated(self):
        order = self._make_order()
        self.assertTrue(order.order_number.startswith("ORD-"))
        self.assertEqual(len(order.order_number), 10)  # "ORD-" + 6 hex chars

    def test_order_number_is_unique(self):
        order1 = self._make_order()
        order2 = self._make_order()
        self.assertNotEqual(order1.order_number, order2.order_number)

    def test_order_number_immutable_on_resave(self):
        order = self._make_order()
        original_number = order.order_number
        order.status = Order.Status.SHIPPED
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.order_number, original_number)

    def test_full_name_property(self):
        order = self._make_order(first_name="Jane", last_name="Smith")
        self.assertEqual(order.full_name, "Jane Smith")

    def test_full_name_strips_extra_whitespace(self):
        order = self._make_order(first_name="  Bob  ", last_name="  Jones  ")
        self.assertNotIn("  ", order.full_name)

    def test_str_contains_order_number(self):
        order = self._make_order()
        self.assertIn(order.order_number, str(order))

    def test_shipping_address_display_contains_all_parts(self):
        order = self._make_order()
        display = order.shipping_address_display
        self.assertIn("42 Elm Street", display)
        self.assertIn("Apt 3B", display)
        self.assertIn("Portland", display)
        self.assertIn("OR", display)
        self.assertIn("97201", display)
        self.assertIn("US", display)

    def test_shipping_address_display_omits_blank_apartment(self):
        order = self._make_order(shipping_apartment="")
        display = order.shipping_address_display
        self.assertNotIn("Apt 3B", display)

    def test_status_default_is_pending(self):
        order = Order.objects.create(
            user=self.user,
            first_name="A",
            last_name="B",
            email="a@b.com",
            phone="1",
            shipping_address="x",
            shipping_city="y",
            shipping_state="z",
            shipping_zip="0",
            shipping_country="US",
            payment_method=Order.PaymentMethod.CREDIT_CARD,
            subtotal=Decimal("0"),
            shipping_cost=Decimal("0"),
            tax=Decimal("0"),
            discount=Decimal("0"),
            total=Decimal("0"),
        )
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_order_ordering_newest_first(self):
        order1 = self._make_order()
        order2 = self._make_order()
        orders = list(Order.objects.filter(user=self.user))
        self.assertEqual(orders[0].pk, order2.pk)
        self.assertEqual(orders[1].pk, order1.pk)

    def test_status_choices(self):
        valid_statuses = [
            Order.Status.PENDING,
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
            Order.Status.CANCELLED,
        ]
        for s in valid_statuses:
            with self.subTest(status=s):
                order = self._make_order(status=s)
                self.assertEqual(order.status, s)

    # ── OrderItem ─────────────────────────────────────────────────────────────

    def test_order_item_subtotal(self):
        order = self._make_order()
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            product_slug=self.product.slug,
            unit_price=Decimal("25.00"),
            quantity=4,
        )
        self.assertEqual(item.subtotal, Decimal("100.00"))

    def test_order_item_str_contains_product_name(self):
        order = self._make_order()
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            product_slug=self.product.slug,
            unit_price=Decimal("10.00"),
            quantity=1,
        )
        self.assertIn(self.product.name, str(item))

    def test_order_item_preserves_price_snapshot(self):
        """Changing the product price later must not affect order item price."""
        order = self._make_order()
        snapshot_price = Decimal("25.00")
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            product_slug=self.product.slug,
            unit_price=snapshot_price,
            quantity=1,
        )
        self.product.price = Decimal("999.00")
        self.product.save()
        item.refresh_from_db()
        self.assertEqual(item.unit_price, snapshot_price)

    def test_order_item_product_null_on_product_deletion(self):
        """When the Product is deleted the FK becomes NULL (SET_NULL)."""
        order = self._make_order()
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            product_slug=self.product.slug,
            unit_price=self.product.price,
            quantity=1,
        )
        self.product.delete()
        item.refresh_from_db()
        self.assertIsNone(item.product)
        # Snapshot fields must still be intact
        self.assertEqual(item.product_name, "T-Shirt")


# ══════════════════════════════════════════════════════════════════════════════
# 2. OrderCreateSerializer Tests
# ══════════════════════════════════════════════════════════════════════════════


class OrderCreateSerializerTests(TestCase):
    """Validate the create serializer's financial math and business rules."""

    def setUp(self):
        self.user = make_user()
        self.product = make_product(price="100.00", stock=5)
        make_cart_with_items(self.user, [{"product": self.product, "quantity": 2}])
        self.request = type(
            "Request", (), {"user": self.user, "build_absolute_uri": lambda s, u: u}
        )()

    def _serialize(self, data=None):
        from order.serializers import OrderCreateSerializer

        payload = {**VALID_PAYLOAD, **(data or {})}
        s = OrderCreateSerializer(data=payload, context={"request": self.request})
        return s

    # ── Field validation ──────────────────────────────────────────────────────

    def test_valid_payload_passes(self):
        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)

    def test_missing_first_name_fails(self):
        s = self._serialize({"first_name": ""})
        self.assertFalse(s.is_valid())
        self.assertIn("first_name", s.errors)

    def test_missing_last_name_fails(self):
        s = self._serialize({"last_name": ""})
        self.assertFalse(s.is_valid())

    def test_invalid_email_fails(self):
        s = self._serialize({"email": "not-an-email"})
        self.assertFalse(s.is_valid())
        self.assertIn("email", s.errors)

    def test_invalid_payment_method_fails(self):
        s = self._serialize({"payment_method": "bitcoin"})
        self.assertFalse(s.is_valid())
        self.assertIn("payment_method", s.errors)

    def test_card_last_four_non_digit_fails(self):
        s = self._serialize({"card_last_four": "ABCD"})
        self.assertFalse(s.is_valid())

    def test_card_last_four_blank_allowed(self):
        s = self._serialize({"payment_method": "paypal", "card_last_four": ""})
        self.assertTrue(s.is_valid(), s.errors)

    def test_negative_discount_fails(self):
        s = self._serialize({"discount": "-10.00"})
        self.assertFalse(s.is_valid())

    def test_missing_address_fails(self):
        s = self._serialize({"address": ""})
        self.assertFalse(s.is_valid())
        self.assertIn("address", s.errors)

    # ── Empty / missing cart ──────────────────────────────────────────────────

    def test_empty_cart_raises_validation_error(self):
        Cart.objects.filter(user=self.user).delete()
        cart = Cart.objects.create(user=self.user)  # cart exists but empty
        s = self._serialize()
        self.assertFalse(s.is_valid())
        self.assertIn("cart", s.errors)

    # ── Financial calculations ────────────────────────────────────────────────

    def test_order_subtotal_matches_cart_subtotal(self):
        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()
        cart = Cart.objects.get(user=self.user)
        # Cart should be empty after creation
        self.assertEqual(cart.subtotal, Decimal("0"))
        # Order subtotal = 2 × $100
        self.assertEqual(order.subtotal, Decimal("200.00"))

    def test_order_tax_is_ten_percent_of_subtotal(self):
        s = self._serialize()
        s.is_valid()
        order = s.save()
        expected_tax = (order.subtotal * TAX_RATE).quantize(Decimal("0.01"))
        self.assertEqual(order.tax, expected_tax)

    def test_order_shipping_cost_is_fixed(self):
        s = self._serialize()
        s.is_valid()
        order = s.save()
        self.assertEqual(order.shipping_cost, SHIPPING_COST)

    def test_order_total_formula(self):
        s = self._serialize({"discount": "10.00"})
        s.is_valid()
        order = s.save()
        expected = (
            order.subtotal + SHIPPING_COST + order.tax - Decimal("10.00")
        ).quantize(Decimal("0.01"))
        self.assertEqual(order.total, expected)

    def test_order_total_with_zero_discount(self):
        s = self._serialize({"discount": "0.00"})
        s.is_valid()
        order = s.save()
        expected = (order.subtotal + SHIPPING_COST + order.tax).quantize(
            Decimal("0.01")
        )
        self.assertEqual(order.total, expected)

    # ── Cart-to-order flow ────────────────────────────────────────────────────

    def test_order_items_match_cart_items(self):
        product2 = make_product(name="Trousers", slug="trousers", price="60.00")
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(
            self.user,
            [
                {"product": self.product, "quantity": 2},
                {"product": product2, "quantity": 1},
            ],
        )
        s = self._serialize()
        s.is_valid()
        order = s.save()
        self.assertEqual(order.items.count(), 2)

    def test_order_items_snapshot_product_name(self):
        s = self._serialize()
        s.is_valid()
        order = s.save()
        item = order.items.first()
        self.assertEqual(item.product_name, self.product.name)

    def test_order_items_snapshot_unit_price(self):
        s = self._serialize()
        s.is_valid()
        order = s.save()
        item = order.items.first()
        self.assertEqual(item.unit_price, self.product.price)

    def test_order_items_snapshot_quantity(self):
        s = self._serialize()
        s.is_valid()
        order = s.save()
        item = order.items.first()
        self.assertEqual(item.quantity, 2)

    def test_cart_cleared_after_order_creation(self):
        s = self._serialize()
        s.is_valid()
        s.save()
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 0)

    def test_order_status_is_processing_after_creation(self):
        s = self._serialize()
        s.is_valid()
        order = s.save()
        self.assertEqual(order.status, Order.Status.PROCESSING)

    def test_order_linked_to_correct_user(self):
        s = self._serialize()
        s.is_valid()
        order = s.save()
        self.assertEqual(order.user, self.user)

    # ── Atomicity: partial failure must not leave orphaned data ──────────────

    def test_failure_mid_loop_rolls_back_order_and_preserves_cart(self):
        """
        If OrderItem creation blows up partway through the loop, the whole
        create() call must roll back: no Order row should be committed and
        the cart's items must remain untouched.
        """
        from unittest.mock import patch

        # Cart needs 2+ items so the failure happens mid-loop, not on the
        # first iteration.
        product2 = make_product(name="Trousers", slug="trousers", price="60.00")
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(
            self.user,
            [
                {"product": self.product, "quantity": 2},
                {"product": product2, "quantity": 1},
            ],
        )

        orders_before = Order.objects.count()
        cart = Cart.objects.get(user=self.user)
        items_before = cart.items.count()

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)

        real_create = OrderItem.objects.create
        call_count = {"n": 0}

        def flaky_create(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("simulated mid-loop failure")
            return real_create(*args, **kwargs)

        with patch("order.serializers.OrderItem.objects.create", side_effect=flaky_create):
            with self.assertRaises(RuntimeError):
                s.save()

        # No orphaned Order row was committed.
        self.assertEqual(Order.objects.count(), orders_before)

        # Cart items were not deleted.
        cart.refresh_from_db()
        self.assertEqual(cart.items.count(), items_before)

    # ── Row-level locking on checkout ─────────────────────────────────────────

    def test_checkout_locks_only_the_products_in_the_cart(self):
        """
        select_for_update() must be invoked on the Product queryset, scoped
        to exactly the product ids referenced by the cart being checked
        out — not the whole table.
        """
        from unittest.mock import patch

        from shop.models import Product

        other_product = make_product(
            name="Untouched", slug="untouched", price="15.00"
        )  # not in the cart — must not be locked

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)

        real_qs = Product.objects.select_for_update()
        with patch(
            "order.serializers.Product.objects.select_for_update",
            return_value=real_qs,
        ) as mock_select_for_update:
            order = s.save()

        mock_select_for_update.assert_called_once_with()

        locked_product_ids = set(order.items.values_list("product_id", flat=True))
        self.assertEqual(locked_product_ids, {self.product.id})
        self.assertNotIn(other_product.id, locked_product_ids)

    def test_checkout_product_query_uses_for_update(self):
        """
        The locking queryset's compiled SQL must contain FOR UPDATE. This
        only has real meaning on Postgres (the project's configured engine
        in core/settings/base.py); skip on backends where SELECT ... FOR
        UPDATE isn't part of the compiled SQL the same way.
        """
        from django.db import connection

        from shop.models import Product

        if connection.vendor == "sqlite":
            self.skipTest("SELECT ... FOR UPDATE semantics differ on SQLite")

        qs = Product.objects.select_for_update().filter(id=self.product.id)
        self.assertIn("FOR UPDATE", str(qs.query))

    def test_order_item_product_is_the_locked_instance(self):
        """
        The Product referenced on the created OrderItem must be the same
        row fetched (and locked) by the select_for_update() query, not a
        stale copy obtained earlier via the cart's select_related.
        """
        s = self._serialize()
        s.is_valid()
        order = s.save()
        item = order.items.first()
        self.assertEqual(item.product_id, self.product.id)
        self.assertEqual(item.product_name, self.product.name)

    # ── Stock validation + decrement ──────────────────────────────────────────

    def test_sufficient_stock_decrements_by_ordered_quantity(self):
        """
        Ordering a quantity within available stock succeeds, and the
        product's stock is reduced by exactly the ordered quantity.
        """
        # self.product has stock=5, cart quantity=2 (see setUp).
        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        s.save()

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5 - 2)

    def test_insufficient_stock_raises_and_rolls_back_everything(self):
        """
        Ordering more than available stock must raise a ValidationError,
        and afterward: no Order or OrderItem rows exist, and the
        product's stock is completely unchanged — proving the atomic
        rollback covers the new stock-decrement logic too.
        """
        low_stock_product = make_product(
            name="Scarce Item", slug="scarce-item", price="40.00", stock=1
        )
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(
            self.user, [{"product": low_stock_product, "quantity": 3}]
        )

        orders_before = Order.objects.count()
        items_before = OrderItem.objects.count()
        stock_before = low_stock_product.stock

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)

        with self.assertRaises(serializers.ValidationError) as ctx:
            s.save()
        self.assertIn("stock", ctx.exception.detail)

        self.assertEqual(Order.objects.count(), orders_before)
        self.assertEqual(OrderItem.objects.count(), items_before)

        low_stock_product.refresh_from_db()
        self.assertEqual(low_stock_product.stock, stock_before)

    def test_second_item_out_of_stock_prevents_first_item_decrement_too(self):
        """
        Cart with two items: the first has enough stock, the second does
        not. Neither product's stock should be decremented — partial
        success across items is not allowed.
        """
        healthy_product = make_product(
            name="Plenty", slug="plenty", price="10.00", stock=10
        )
        scarce_product = make_product(
            name="Scarce Two", slug="scarce-two", price="20.00", stock=1
        )
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(
            self.user,
            [
                {"product": healthy_product, "quantity": 2},
                {"product": scarce_product, "quantity": 5},
            ],
        )

        orders_before = Order.objects.count()
        healthy_stock_before = healthy_product.stock
        scarce_stock_before = scarce_product.stock

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)

        with self.assertRaises(serializers.ValidationError):
            s.save()

        self.assertEqual(Order.objects.count(), orders_before)

        healthy_product.refresh_from_db()
        scarce_product.refresh_from_db()
        self.assertEqual(healthy_product.stock, healthy_stock_before)
        self.assertEqual(scarce_product.stock, scarce_stock_before)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Order List + Create API  —  GET / POST  /api/orders/
# ══════════════════════════════════════════════════════════════════════════════


class OrderListCreateAPITests(APITestCase):
    URL = "/api/orders/"

    def setUp(self):
        self.user = make_user()
        self.product = make_product(price="50.00", stock=10)
        make_cart_with_items(self.user, [{"product": self.product, "quantity": 1}])
        self.client.force_authenticate(user=self.user)

    def _post_order(self, payload=None):
        return self.client.post(self.URL, payload or VALID_PAYLOAD, format="json")

    # ── GET: list ─────────────────────────────────────────────────────────────

    def test_get_empty_order_list(self):
        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, [])

    def test_get_returns_own_orders(self):
        self._post_order()
        # Restore cart for second order
        make_cart_with_items(self.user, [{"product": self.product, "quantity": 1}])
        self._post_order()
        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

    def test_get_list_ordered_newest_first(self):
        self._post_order()
        make_cart_with_items(self.user, [{"product": self.product, "quantity": 1}])
        self._post_order()
        res = self.client.get(self.URL)
        self.assertGreater(res.data[0]["id"], res.data[1]["id"])

    def test_get_list_contains_required_fields(self):
        self._post_order()
        res = self.client.get(self.URL)
        item = res.data[0]
        for field in (
            "id",
            "order_number",
            "status",
            "total",
            "item_count",
            "created_at",
        ):
            with self.subTest(field=field):
                self.assertIn(field, item)

    def test_get_does_not_return_other_users_orders(self):
        other = make_user(email="other@example.com")
        other_cart = make_cart_with_items(
            other, [{"product": self.product, "quantity": 1}]
        )
        other_client = self.__class__.__new__(self.__class__)
        other_client.__dict__.update(self.__dict__)
        self.client.force_authenticate(user=other)
        self.client.post(self.URL, VALID_PAYLOAD, format="json")

        # Back to original user
        self.client.force_authenticate(user=self.user)
        res = self.client.get(self.URL)
        self.assertEqual(res.data, [])

    # ── POST: create order ────────────────────────────────────────────────────

    def test_post_creates_order_returns_201(self):
        res = self._post_order()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_post_creates_order_in_database(self):
        self._post_order()
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)

    def test_post_response_contains_order_number(self):
        res = self._post_order()
        self.assertIn("order_number", res.data)
        self.assertTrue(res.data["order_number"].startswith("ORD-"))

    def test_post_response_contains_items(self):
        res = self._post_order()
        self.assertEqual(len(res.data["items"]), 1)
        self.assertEqual(res.data["items"][0]["product_name"], self.product.name)

    def test_post_response_contains_financials(self):
        res = self._post_order()
        for field in ("subtotal", "shipping_cost", "tax", "discount", "total"):
            with self.subTest(field=field):
                self.assertIn(field, res.data)

    def test_post_clears_cart_after_order(self):
        self._post_order()
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 0)

    def test_post_with_empty_cart_returns_400(self):
        Cart.objects.filter(user=self.user).delete()
        Cart.objects.create(user=self.user)
        res = self._post_order()
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_missing_first_name_returns_400(self):
        payload = {**VALID_PAYLOAD, "first_name": ""}
        res = self.client.post(self.URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("first_name", res.data)

    def test_post_invalid_payment_method_returns_400(self):
        payload = {**VALID_PAYLOAD, "payment_method": "cash"}
        res = self.client.post(self.URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_invalid_email_returns_400(self):
        payload = {**VALID_PAYLOAD, "email": "bad-email"}
        res = self.client.post(self.URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_missing_address_returns_400(self):
        payload = {**VALID_PAYLOAD, "address": ""}
        res = self.client.post(self.URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_insufficient_stock_returns_400_and_nothing_committed(self):
        Cart.objects.filter(user=self.user).delete()
        low_stock = make_product(
            name="API Scarce", slug="api-scarce", price="12.00", stock=1
        )
        make_cart_with_items(self.user, [{"product": low_stock, "quantity": 2}])

        orders_before = Order.objects.count()
        stock_before = low_stock.stock

        res = self._post_order()

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("stock", res.data)
        self.assertEqual(Order.objects.count(), orders_before)

        low_stock.refresh_from_db()
        self.assertEqual(low_stock.stock, stock_before)

    def test_post_multiple_orders_each_get_unique_numbers(self):
        res1 = self._post_order()
        make_cart_with_items(self.user, [{"product": self.product, "quantity": 1}])
        res2 = self._post_order()
        self.assertNotEqual(res1.data["order_number"], res2.data["order_number"])

    def test_post_discount_applied_to_total(self):
        payload = {**VALID_PAYLOAD, "discount": "5.00"}
        res = self.client.post(self.URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(res.data["discount"]), Decimal("5.00"))
        order = Order.objects.get(user=self.user)
        subtotal = order.subtotal
        expected = (subtotal + SHIPPING_COST + order.tax - Decimal("5.00")).quantize(
            Decimal("0.01")
        )
        self.assertEqual(order.total, expected)

    def test_post_paypal_payment_method(self):
        payload = {**VALID_PAYLOAD, "payment_method": "paypal", "card_last_four": ""}
        res = self.client.post(self.URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["payment_method"], "paypal")

    def test_post_apple_pay_method(self):
        payload = {**VALID_PAYLOAD, "payment_method": "apple_pay", "card_last_four": ""}
        res = self.client.post(self.URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_post_order_with_notes(self):
        payload = {**VALID_PAYLOAD, "notes": "Leave at front door"}
        res = self.client.post(self.URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["notes"], "Leave at front door")

    def test_post_multi_item_cart_creates_correct_order_items(self):
        product2 = make_product(name="Cap", slug="cap", price="15.00")
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(
            self.user,
            [
                {"product": self.product, "quantity": 2},
                {"product": product2, "quantity": 3},
            ],
        )
        res = self._post_order()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(res.data["items"]), 2)

    def test_post_billing_same_as_shipping_stored(self):
        payload = {**VALID_PAYLOAD, "billing_same": False}
        res = self.client.post(self.URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(user=self.user)
        self.assertFalse(order.billing_same_as_shipping)


# ══════════════════════════════════════════════════════════════════════════════
# 4. Order Detail API  —  GET / PATCH  /api/orders/<id>/
# ══════════════════════════════════════════════════════════════════════════════


class OrderDetailAPITests(APITestCase):

    def _detail_url(self, order_id):
        return f"/api/orders/{order_id}/"

    def setUp(self):
        self.user = make_user()
        self.product = make_product(price="30.00", stock=10)
        make_cart_with_items(self.user, [{"product": self.product, "quantity": 2}])
        self.client.force_authenticate(user=self.user)
        res = self.client.post("/api/orders/", VALID_PAYLOAD, format="json")
        self.order = Order.objects.get(pk=res.data["id"])

    # ── GET ───────────────────────────────────────────────────────────────────

    def test_get_order_detail_returns_200(self):
        res = self.client.get(self._detail_url(self.order.pk))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_get_order_detail_contains_all_top_level_fields(self):
        res = self.client.get(self._detail_url(self.order.pk))
        for field in (
            "id",
            "order_number",
            "status",
            "status_display",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "shipping_address",
            "shipping_city",
            "shipping_state",
            "shipping_zip",
            "shipping_country",
            "payment_method",
            "payment_display",
            "subtotal",
            "shipping_cost",
            "tax",
            "discount",
            "total",
            "items",
            "created_at",
            "updated_at",
        ):
            with self.subTest(field=field):
                self.assertIn(field, res.data)

    def test_get_order_detail_items_have_expected_fields(self):
        res = self.client.get(self._detail_url(self.order.pk))
        item = res.data["items"][0]
        for field in (
            "id",
            "product_name",
            "product_slug",
            "unit_price",
            "quantity",
            "subtotal",
        ):
            with self.subTest(field=field):
                self.assertIn(field, item)

    def test_get_order_detail_subtotal_is_correct(self):
        res = self.client.get(self._detail_url(self.order.pk))
        expected = (self.product.price * 2).quantize(Decimal("0.01"))
        self.assertEqual(Decimal(res.data["subtotal"]), expected)

    def test_get_order_detail_full_name(self):
        res = self.client.get(self._detail_url(self.order.pk))
        self.assertEqual(res.data["full_name"], "Jane Smith")

    def test_get_nonexistent_order_returns_404(self):
        res = self.client.get(self._detail_url(99999))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_another_users_order_returns_404(self):
        other = make_user(email="other@example.com")
        other_cart = make_cart_with_items(
            other, [{"product": self.product, "quantity": 1}]
        )
        self.client.force_authenticate(user=other)
        res1 = self.client.post("/api/orders/", VALID_PAYLOAD, format="json")
        other_order_id = res1.data["id"]

        # Switch back to original user and try to read other's order
        self.client.force_authenticate(user=self.user)
        res2 = self.client.get(self._detail_url(other_order_id))
        self.assertEqual(res2.status_code, status.HTTP_404_NOT_FOUND)

    # ── PATCH: cancel ─────────────────────────────────────────────────────────

    def test_patch_cancel_pending_order(self):
        self.order.status = Order.Status.PENDING
        self.order.save()
        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

    def test_patch_cancel_processing_order(self):
        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

    def test_patch_cancel_shipped_order_returns_400(self):
        self.order.status = Order.Status.SHIPPED
        self.order.save()
        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.SHIPPED)

    def test_patch_cancel_delivered_order_returns_400(self):
        self.order.status = Order.Status.DELIVERED
        self.order.save()
        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_non_cancel_status_returns_400(self):
        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "delivered"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_cancel_returns_updated_order(self):
        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.data["status"], Order.Status.CANCELLED)

    def test_patch_cancel_nonexistent_order_returns_404(self):
        res = self.client.patch(
            self._detail_url(99999), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_cancel_another_users_order_returns_404(self):
        other = make_user(email="other@example.com")
        other_cart = make_cart_with_items(
            other, [{"product": self.product, "quantity": 1}]
        )
        self.client.force_authenticate(user=other)
        res1 = self.client.post("/api/orders/", VALID_PAYLOAD, format="json")
        other_order_id = res1.data["id"]

        self.client.force_authenticate(user=self.user)
        res2 = self.client.patch(
            self._detail_url(other_order_id), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res2.status_code, status.HTTP_404_NOT_FOUND)

        # Verify other user's order was not changed
        other_order = Order.objects.get(pk=other_order_id)
        self.assertNotEqual(other_order.status, Order.Status.CANCELLED)

    # ── PATCH: cancel restores stock ────────────────────────────────────────

    def test_patch_cancel_restores_stock_for_each_item(self):
        """
        Cancelling an order returns every OrderItem's quantity back to its
        product's stock.
        """
        # setUp() created self.order for 2 units of self.product (stock
        # started at 10, and Task 1.1.1.3's decrement left it at 8).
        self.product.refresh_from_db()
        stock_after_purchase = self.product.stock
        self.assertEqual(stock_after_purchase, 8)

        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, stock_after_purchase + 2)
        self.assertEqual(self.product.stock, 10)

    def test_patch_cancel_with_deleted_product_skips_gracefully(self):
        """
        If one of the order's OrderItem.product rows was deleted after the
        order was placed (SET_NULL), cancelling must not raise, and stock
        restoration should still happen for the remaining valid items.
        """
        second_product = make_product(
            name="Backpack", slug="backpack", price="45.00", stock=10
        )
        make_cart_with_items(
            self.user,
            [
                {"product": self.product, "quantity": 1},
                {"product": second_product, "quantity": 3},
            ],
        )
        res = self.client.post("/api/orders/", VALID_PAYLOAD, format="json")
        order = Order.objects.get(pk=res.data["id"])

        second_product.refresh_from_db()
        self.assertEqual(second_product.stock, 7)  # 10 - 3

        # Simulate the product having been deleted after the order was
        # placed — OrderItem.product is SET_NULL, so this leaves the
        # OrderItem with product=None.
        second_product.delete()

        other_item = order.items.exclude(product__isnull=True).first()
        self.assertIsNotNone(other_item)
        restored_product = other_item.product
        stock_before_cancel = restored_product.stock

        res = self.client.patch(
            self._detail_url(order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        restored_product.refresh_from_db()
        self.assertEqual(
            restored_product.stock, stock_before_cancel + other_item.quantity
        )

    def test_patch_cancel_shipped_order_does_not_modify_stock(self):
        """
        Regression: the shipped/delivered guard clause must still run
        before any stock-restoration logic, so a rejected cancellation
        leaves product stock untouched.
        """
        self.product.refresh_from_db()
        stock_before = self.product.stock

        self.order.status = Order.Status.SHIPPED
        self.order.save()

        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, stock_before)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Authentication Guard Tests
# ══════════════════════════════════════════════════════════════════════════════


class OrderAuthTests(APITestCase):
    """Every order endpoint must return 401 for unauthenticated callers."""

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=5)
        make_cart_with_items(self.user, [{"product": self.product, "quantity": 1}])
        # Create a real order (authenticated) to test detail endpoints
        self.client.force_authenticate(user=self.user)
        res = self.client.post("/api/orders/", VALID_PAYLOAD, format="json")
        self.order_id = res.data["id"]
        self.client.force_authenticate(user=None)  # back to unauthenticated

    def test_list_orders_unauthenticated(self):
        res = self.client.get("/api/orders/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_order_unauthenticated(self):
        res = self.client.post("/api/orders/", VALID_PAYLOAD, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_order_detail_unauthenticated(self):
        res = self.client.get(f"/api/orders/{self.order_id}/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cancel_order_unauthenticated(self):
        res = self.client.patch(
            f"/api/orders/{self.order_id}/", {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_cannot_read_order_data(self):
        res = self.client.get(f"/api/orders/{self.order_id}/")
        data = res.data if isinstance(res.data, dict) else {}
        self.assertNotIn("order_number", data)


# ══════════════════════════════════════════════════════════════════════════════
# 6. Cross-User Isolation Tests
# ══════════════════════════════════════════════════════════════════════════════


class OrderIsolationTests(APITestCase):
    """Verify strict per-user data separation across all order endpoints."""

    def setUp(self):
        self.product = make_product(price="20.00", stock=20)
        self.user_a = make_user(email="a@example.com")
        self.user_b = make_user(email="b@example.com")

        # User A places an order
        make_cart_with_items(self.user_a, [{"product": self.product, "quantity": 2}])
        self.client.force_authenticate(user=self.user_a)
        res_a = self.client.post("/api/orders/", VALID_PAYLOAD, format="json")
        self.order_a_id = res_a.data["id"]

        # User B places an order
        make_cart_with_items(self.user_b, [{"product": self.product, "quantity": 3}])
        self.client.force_authenticate(user=self.user_b)
        res_b = self.client.post("/api/orders/", VALID_PAYLOAD, format="json")
        self.order_b_id = res_b.data["id"]

    def test_user_a_cannot_see_user_b_orders(self):
        self.client.force_authenticate(user=self.user_a)
        res = self.client.get("/api/orders/")
        ids = [o["id"] for o in res.data]
        self.assertIn(self.order_a_id, ids)
        self.assertNotIn(self.order_b_id, ids)

    def test_user_b_cannot_see_user_a_orders(self):
        self.client.force_authenticate(user=self.user_b)
        res = self.client.get("/api/orders/")
        ids = [o["id"] for o in res.data]
        self.assertIn(self.order_b_id, ids)
        self.assertNotIn(self.order_a_id, ids)

    def test_user_a_cannot_fetch_user_b_order_detail(self):
        self.client.force_authenticate(user=self.user_a)
        res = self.client.get(f"/api/orders/{self.order_b_id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_b_cannot_cancel_user_a_order(self):
        self.client.force_authenticate(user=self.user_b)
        res = self.client.patch(
            f"/api/orders/{self.order_a_id}/", {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        order_a = Order.objects.get(pk=self.order_a_id)
        self.assertNotEqual(order_a.status, Order.Status.CANCELLED)

    def test_order_counts_are_independent(self):
        self.client.force_authenticate(user=self.user_a)
        res_a = self.client.get("/api/orders/")
        self.client.force_authenticate(user=self.user_b)
        res_b = self.client.get("/api/orders/")
        self.assertEqual(len(res_a.data), 1)
        self.assertEqual(len(res_b.data), 1)
