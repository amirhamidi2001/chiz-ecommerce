from decimal import Decimal

from cart.models import Cart, CartItem
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from shop.models import Category, Product

User = get_user_model()


# ─── Fixtures helpers ──────────────────────────────────────────────────────────


def make_user(email="user@example.com", password="TestPass123!", **kwargs):
    """Create and return an active test user."""
    return User.objects.create_user(email=email, password=password, **kwargs)


def make_category(name="Electronics", slug="electronics"):
    category, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})
    return category


def make_product(
    *,
    name="Widget",
    slug="widget",
    price="49.99",
    stock=10,
    original_price=None,
    category=None,
):
    """Create and return a minimal Product instance."""
    if category is None:
        category = make_category()
    return Product.objects.create(
        name=name,
        slug=slug,
        price=Decimal(price),
        original_price=Decimal(original_price) if original_price else None,
        stock=stock,
        category=category,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. Model Tests
# ══════════════════════════════════════════════════════════════════════════════


class CartModelTests(TestCase):
    """Unit-test Cart model properties and computed values."""

    def setUp(self):
        self.user = make_user()
        self.product = make_product()

    # ── Cart ──────────────────────────────────────────────────────────────────

    def test_cart_created_with_user(self):
        cart = Cart.objects.create(user=self.user)
        self.assertEqual(cart.user, self.user)

    def test_cart_str_contains_user_email(self):
        cart = Cart.objects.create(user=self.user)
        self.assertIn(self.user.email, str(cart))

    def test_empty_cart_subtotal_is_zero(self):
        cart = Cart.objects.create(user=self.user)
        self.assertEqual(cart.subtotal, Decimal("0"))

    def test_empty_cart_total_items_is_zero(self):
        cart = Cart.objects.create(user=self.user)
        self.assertEqual(cart.total_items, 0)

    def test_subtotal_single_item(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=3)
        expected = self.product.price * 3
        self.assertEqual(cart.subtotal, expected)

    def test_subtotal_multiple_items(self):
        cart = Cart.objects.create(user=self.user)
        product2 = make_product(name="Gadget", slug="gadget", price="29.99")
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        CartItem.objects.create(cart=cart, product=product2, quantity=5)
        expected = (self.product.price * 2) + (product2.price * 5)
        self.assertEqual(cart.subtotal, expected)

    def test_total_items_counts_all_units(self):
        cart = Cart.objects.create(user=self.user)
        product2 = make_product(name="Gadget", slug="gadget")
        CartItem.objects.create(cart=cart, product=self.product, quantity=4)
        CartItem.objects.create(cart=cart, product=product2, quantity=2)
        self.assertEqual(cart.total_items, 6)

    def test_one_cart_per_user_enforced(self):
        """OneToOneField must prevent a second cart for the same user."""
        Cart.objects.create(user=self.user)
        with self.assertRaises(Exception):
            Cart.objects.create(user=self.user)

    # ── CartItem ──────────────────────────────────────────────────────────────

    def test_cart_item_str(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        self.assertIn(self.product.name, str(item))
        self.assertIn("2", str(item))

    def test_cart_item_unit_price_equals_product_price(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.assertEqual(item.unit_price, self.product.price)

    def test_cart_item_subtotal(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, product=self.product, quantity=3)
        self.assertEqual(item.subtotal, self.product.price * 3)

    def test_cart_item_default_quantity_is_one(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, product=self.product)
        self.assertEqual(item.quantity, 1)

    def test_cart_item_quantity_minimum_one(self):
        """Validators should reject quantity < 1."""
        cart = Cart.objects.create(user=self.user)
        item = CartItem(cart=cart, product=self.product, quantity=0)
        with self.assertRaises(Exception):
            item.full_clean()

    def test_cart_item_unique_together_cart_product(self):
        """Duplicate (cart, product) must raise an error."""
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        with self.assertRaises(Exception):
            CartItem.objects.create(cart=cart, product=self.product, quantity=2)

    def test_deleting_item_updates_cart_subtotal(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        item.delete()
        self.assertEqual(cart.subtotal, Decimal("0"))

    def test_cart_item_ordering_newest_first(self):
        """Items should be returned by -added_at (newest first) by default."""
        cart = Cart.objects.create(user=self.user)
        product2 = make_product(name="Second", slug="second")
        item1 = CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        item2 = CartItem.objects.create(cart=cart, product=product2, quantity=1)
        items = list(CartItem.objects.filter(cart=cart))
        self.assertEqual(items[0], item2)
        self.assertEqual(items[1], item1)


# ══════════════════════════════════════════════════════════════════════════════
# 2. Serializer Tests
# ══════════════════════════════════════════════════════════════════════════════


class CartItemSerializerTests(TestCase):
    """Validate CartItemSerializer field-level rules."""

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=5)
        # Fake DRF request with authenticated user
        self.request = type("Request", (), {"user": self.user})()

    def _serialize(self, data):
        from cart.serializers import CartItemSerializer

        return CartItemSerializer(data=data, context={"request": self.request})

    def test_valid_data_passes(self):
        s = self._serialize({"product_id": self.product.id, "quantity": 2})
        self.assertTrue(s.is_valid(), s.errors)

    def test_missing_product_id_is_invalid(self):
        s = self._serialize({"quantity": 1})
        self.assertFalse(s.is_valid())
        self.assertIn("product_id", s.errors)

    def test_nonexistent_product_id_is_invalid(self):
        s = self._serialize({"product_id": 99999, "quantity": 1})
        self.assertFalse(s.is_valid())
        self.assertIn("product_id", s.errors)

    def test_out_of_stock_product_is_invalid(self):
        oos = make_product(name="OOS", slug="oos", stock=0)
        s = self._serialize({"product_id": oos.id, "quantity": 1})
        self.assertFalse(s.is_valid())
        self.assertIn("product_id", s.errors)

    def test_quantity_zero_is_invalid(self):
        s = self._serialize({"product_id": self.product.id, "quantity": 0})
        self.assertFalse(s.is_valid())
        self.assertIn("quantity", s.errors)

    def test_quantity_negative_is_invalid(self):
        s = self._serialize({"product_id": self.product.id, "quantity": -5})
        self.assertFalse(s.is_valid())
        self.assertIn("quantity", s.errors)

    def test_quantity_large_is_valid(self):
        self.product.stock = 100
        self.product.save()
        s = self._serialize({"product_id": self.product.id, "quantity": 50})
        self.assertTrue(s.is_valid(), s.errors)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Cart API  —  GET / POST  /api/cart/
# ══════════════════════════════════════════════════════════════════════════════


class CartAPITests(APITestCase):
    URL = "/api/cart/"

    def setUp(self):
        self.user = make_user()
        self.product = make_product(price="19.99", stock=10)
        self.client.force_authenticate(user=self.user)

    # ── GET ───────────────────────────────────────────────────────────────────

    def test_get_creates_cart_for_new_user(self):
        self.assertFalse(Cart.objects.filter(user=self.user).exists())
        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(Cart.objects.filter(user=self.user).exists())

    def test_get_returns_empty_cart(self):
        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["items"], [])
        self.assertEqual(res.data["total_items"], 0)
        self.assertEqual(Decimal(res.data["subtotal"]), Decimal("0.00"))

    def test_get_returns_populated_cart(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=3)
        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["items"]), 1)
        self.assertEqual(res.data["total_items"], 3)

    def test_get_cart_subtotal_is_correct(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        res = self.client.get(self.URL)
        expected = (self.product.price * 2).quantize(Decimal("0.01"))
        self.assertEqual(Decimal(res.data["subtotal"]), expected)

    def test_get_does_not_create_duplicate_carts(self):
        self.client.get(self.URL)
        self.client.get(self.URL)
        self.assertEqual(Cart.objects.filter(user=self.user).count(), 1)

    def test_get_does_not_return_another_users_cart(self):
        other = make_user(email="other@example.com")
        other_cart = Cart.objects.create(user=other)
        product2 = make_product(name="Other", slug="other-product")
        CartItem.objects.create(cart=other_cart, product=product2, quantity=5)

        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["items"], [])

    # ── POST: add item ────────────────────────────────────────────────────────

    def test_post_adds_new_item_returns_201(self):
        res = self.client.post(self.URL, {"product_id": self.product.id, "quantity": 2})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_post_creates_cart_implicitly(self):
        self.assertFalse(Cart.objects.filter(user=self.user).exists())
        self.client.post(self.URL, {"product_id": self.product.id, "quantity": 1})
        self.assertTrue(Cart.objects.filter(user=self.user).exists())

    def test_post_item_appears_in_cart_response(self):
        res = self.client.post(self.URL, {"product_id": self.product.id, "quantity": 1})
        self.assertEqual(len(res.data["items"]), 1)
        self.assertEqual(res.data["items"][0]["product"]["id"], self.product.id)

    def test_post_default_quantity_is_one(self):
        self.client.post(self.URL, {"product_id": self.product.id})
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.first().quantity, 1)

    def test_post_increments_existing_item_quantity(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)

        res = self.client.post(self.URL, {"product_id": self.product.id, "quantity": 3})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        cart.refresh_from_db()
        self.assertEqual(cart.items.first().quantity, 5)

    def test_post_updates_subtotal_correctly(self):
        res = self.client.post(self.URL, {"product_id": self.product.id, "quantity": 2})
        expected = (self.product.price * 2).quantize(Decimal("0.01"))
        self.assertEqual(Decimal(res.data["subtotal"]), expected)

    def test_post_missing_product_id_returns_400(self):
        res = self.client.post(self.URL, {"quantity": 1})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("product_id", res.data)

    def test_post_invalid_product_id_returns_400(self):
        res = self.client.post(self.URL, {"product_id": 99999, "quantity": 1})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_out_of_stock_product_returns_400(self):
        oos = make_product(name="OOS", slug="oos-product", stock=0)
        res = self.client.post(self.URL, {"product_id": oos.id, "quantity": 1})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_quantity_zero_returns_400(self):
        res = self.client.post(self.URL, {"product_id": self.product.id, "quantity": 0})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_multiple_different_products(self):
        product2 = make_product(name="Second", slug="second", price="9.99")
        self.client.post(self.URL, {"product_id": self.product.id, "quantity": 1})
        res = self.client.post(self.URL, {"product_id": product2.id, "quantity": 2})
        self.assertEqual(len(res.data["items"]), 2)
        self.assertEqual(res.data["total_items"], 3)

    def test_post_response_contains_required_fields(self):
        res = self.client.post(self.URL, {"product_id": self.product.id, "quantity": 1})
        self.assertIn("id", res.data)
        self.assertIn("items", res.data)
        self.assertIn("subtotal", res.data)
        self.assertIn("total_items", res.data)


# ══════════════════════════════════════════════════════════════════════════════
# 4. Cart Item API  —  PUT / PATCH / DELETE  /api/cart/item/<id>/
# ══════════════════════════════════════════════════════════════════════════════


class CartItemAPITests(APITestCase):

    def _item_url(self, item_id):
        return f"/api/cart/item/{item_id}/"

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=20)
        self.cart = Cart.objects.create(user=self.user)
        self.item = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=2
        )
        self.client.force_authenticate(user=self.user)

    # ── PUT / PATCH: update quantity ──────────────────────────────────────────

    def test_put_updates_quantity(self):
        res = self.client.put(self._item_url(self.item.id), {"quantity": 5})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 5)

    def test_patch_updates_quantity(self):
        res = self.client.patch(self._item_url(self.item.id), {"quantity": 7})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 7)

    def test_update_returns_full_cart(self):
        res = self.client.patch(self._item_url(self.item.id), {"quantity": 4})
        self.assertIn("items", res.data)
        self.assertIn("subtotal", res.data)
        self.assertIn("total_items", res.data)

    def test_update_recalculates_subtotal(self):
        res = self.client.put(self._item_url(self.item.id), {"quantity": 4})
        expected = (self.product.price * 4).quantize(Decimal("0.01"))
        self.assertEqual(Decimal(res.data["subtotal"]), expected)

    def test_update_quantity_zero_returns_400(self):
        res = self.client.put(self._item_url(self.item.id), {"quantity": 0})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_quantity_negative_returns_400(self):
        res = self.client.patch(self._item_url(self.item.id), {"quantity": -1})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_missing_quantity_returns_400(self):
        res = self.client.put(self._item_url(self.item.id), {})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_non_integer_quantity_returns_400(self):
        res = self.client.patch(self._item_url(self.item.id), {"quantity": "abc"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_nonexistent_item_returns_404(self):
        res = self.client.put(self._item_url(99999), {"quantity": 3})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_other_users_item_returns_404(self):
        other = make_user(email="other@example.com")
        other_cart = Cart.objects.create(user=other)
        other_item = CartItem.objects.create(
            cart=other_cart, product=self.product, quantity=1
        )
        res = self.client.patch(self._item_url(other_item.id), {"quantity": 5})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_does_not_change_other_users_item(self):
        other = make_user(email="other@example.com")
        other_cart = Cart.objects.create(user=other)
        other_item = CartItem.objects.create(
            cart=other_cart, product=self.product, quantity=1
        )
        self.client.patch(self._item_url(other_item.id), {"quantity": 99})
        other_item.refresh_from_db()
        self.assertEqual(other_item.quantity, 1)

    # ── DELETE: remove item ───────────────────────────────────────────────────

    def test_delete_removes_item(self):
        res = self.client.delete(self._item_url(self.item.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(CartItem.objects.filter(pk=self.item.id).exists())

    def test_delete_returns_updated_cart(self):
        res = self.client.delete(self._item_url(self.item.id))
        self.assertEqual(res.data["items"], [])
        self.assertEqual(res.data["total_items"], 0)

    def test_delete_updates_subtotal_to_zero_when_last_item(self):
        res = self.client.delete(self._item_url(self.item.id))
        self.assertEqual(Decimal(res.data["subtotal"]), Decimal("0.00"))

    def test_delete_nonexistent_item_returns_404(self):
        res = self.client.delete(self._item_url(99999))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_other_users_item_returns_404(self):
        other = make_user(email="other@example.com")
        other_cart = Cart.objects.create(user=other)
        other_item = CartItem.objects.create(
            cart=other_cart, product=self.product, quantity=1
        )
        res = self.client.delete(self._item_url(other_item.id))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(CartItem.objects.filter(pk=other_item.id).exists())

    def test_delete_only_removes_targeted_item(self):
        product2 = make_product(name="Second", slug="second-item")
        item2 = CartItem.objects.create(cart=self.cart, product=product2, quantity=3)
        self.client.delete(self._item_url(self.item.id))
        self.assertFalse(CartItem.objects.filter(pk=self.item.id).exists())
        self.assertTrue(CartItem.objects.filter(pk=item2.id).exists())


# ══════════════════════════════════════════════════════════════════════════════
# 5. Cart Clear API  —  DELETE  /api/cart/clear/
# ══════════════════════════════════════════════════════════════════════════════


class CartClearAPITests(APITestCase):
    URL = "/api/cart/clear/"

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=10)
        self.cart = Cart.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_clear_removes_all_items(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        product2 = make_product(name="Second", slug="second-clr")
        CartItem.objects.create(cart=self.cart, product=product2, quantity=5)

        res = self.client.delete(self.URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(self.cart.items.count(), 0)

    def test_clear_returns_empty_cart_payload(self):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=3)
        res = self.client.delete(self.URL)
        self.assertEqual(res.data["items"], [])
        self.assertEqual(res.data["total_items"], 0)
        self.assertEqual(Decimal(res.data["subtotal"]), Decimal("0.00"))

    def test_clear_empty_cart_still_returns_200(self):
        res = self.client.delete(self.URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_clear_creates_cart_for_new_user(self):
        new_user = make_user(email="new@example.com")
        self.client.force_authenticate(user=new_user)
        res = self.client.delete(self.URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(Cart.objects.filter(user=new_user).exists())

    def test_clear_does_not_affect_other_users_cart(self):
        other = make_user(email="other@example.com")
        other_cart = Cart.objects.create(user=other)
        product2 = make_product(name="Other", slug="other-clr")
        CartItem.objects.create(cart=other_cart, product=product2, quantity=4)

        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.client.delete(self.URL)

        self.assertEqual(other_cart.items.count(), 1)

    def test_clear_preserves_cart_object(self):
        """The Cart row must survive; only CartItems are deleted."""
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.client.delete(self.URL)
        self.assertTrue(Cart.objects.filter(user=self.user).exists())


# ══════════════════════════════════════════════════════════════════════════════
# 6. Authentication Guard Tests
# ══════════════════════════════════════════════════════════════════════════════


class CartAuthTests(APITestCase):
    """Every cart endpoint must return 401 for unauthenticated callers."""

    def setUp(self):
        self.user = make_user()
        self.product = make_product(stock=5)
        self.cart = Cart.objects.create(user=self.user)
        self.item = CartItem.objects.create(
            cart=self.cart, product=self.product, quantity=1
        )

    def test_get_cart_unauthenticated(self):
        res = self.client.get("/api/cart/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_post_cart_unauthenticated(self):
        res = self.client.post("/api/cart/", {"product_id": self.product.id})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_item_unauthenticated(self):
        res = self.client.put(f"/api/cart/item/{self.item.id}/", {"quantity": 3})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_item_unauthenticated(self):
        res = self.client.patch(f"/api/cart/item/{self.item.id}/", {"quantity": 3})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_item_unauthenticated(self):
        res = self.client.delete(f"/api/cart/item/{self.item.id}/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_clear_cart_unauthenticated(self):
        res = self.client.delete("/api/cart/clear/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_cannot_read_cart_data(self):
        res = self.client.get("/api/cart/")
        self.assertNotIn("items", res.data if isinstance(res.data, dict) else {})
