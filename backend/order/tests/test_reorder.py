"""
POST /api/orders/<id>/reorder/ — put a past order's items back in the cart.
"""

from datetime import timedelta

from cart.models import Cart, CartItem
from django.urls import reverse
from django.utils import timezone
from order.models import Order, OrderItem
from rest_framework import status
from rest_framework.test import APITestCase

from .factories import make_user, make_variant


def make_order_with_items(user, lines, order_status=Order.Status.DELIVERED):
    """lines: [(variant, quantity), ...]. Items snapshot the product name."""
    order = Order.objects.create(
        user=user,
        status=order_status,
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        phone="09121234567",
        shipping_address="12 Valiasr St",
        shipping_city="Tehran",
        shipping_state="tehran",
        shipping_zip="1234567890",
        shipping_country="IR",
        payment_method="credit_card",
        subtotal=0,
        shipping_cost=0,
        tax=0,
        discount=0,
        total=0,
    )
    for variant, quantity in lines:
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            product_name=variant.product.name,
            product_slug=variant.product.slug,
            variant_sku=variant.sku,
            unit_price=variant.price,
            quantity=quantity,
        )
    return order


def reorder_url(order):
    return reverse("order:order-reorder", kwargs={"pk": order.pk})


class ReorderTestBase(APITestCase):
    def setUp(self):
        self.user = make_user(email="buyer@example.com")
        self.client.force_authenticate(self.user)
        self.serum = make_variant(name="Rose Serum", slug="rose-serum", stock=10)
        self.cream = make_variant(name="Day Cream", slug="day-cream", stock=10)

    def cart_quantities(self):
        cart = Cart.objects.get(user=self.user)
        return {i.variant_id: i.quantity for i in cart.items.all()}


class TestReorderAllAvailable(ReorderTestBase):
    def test_adds_every_item_with_the_original_quantities(self):
        order = make_order_with_items(self.user, [(self.serum, 2), (self.cream, 3)])

        res = self.client.post(reorder_url(order))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["added_count"], 2)
        self.assertCountEqual(res.data["added"], ["Rose Serum", "Day Cream"])
        self.assertEqual(res.data["unavailable"], [])
        self.assertEqual(self.cart_quantities(), {self.serum.id: 2, self.cream.id: 3})

    def test_sums_with_quantity_already_in_the_cart(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.serum, quantity=4)
        order = make_order_with_items(self.user, [(self.serum, 2), (self.cream, 1)])

        res = self.client.post(reorder_url(order))

        self.assertEqual(res.data["added_count"], 2)
        self.assertEqual(self.cart_quantities(), {self.serum.id: 6, self.cream.id: 1})
        self.assertEqual(cart.items.count(), 2)  # no duplicate line for the serum

    def test_reordering_twice_adds_twice(self):
        order = make_order_with_items(self.user, [(self.serum, 2)])
        self.client.post(reorder_url(order))
        self.client.post(reorder_url(order))
        self.assertEqual(self.cart_quantities(), {self.serum.id: 4})

    def test_does_not_modify_the_original_order(self):
        order = make_order_with_items(self.user, [(self.serum, 2)])
        self.client.post(reorder_url(order))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(Order.objects.count(), 1)


class TestReorderPartialSuccess(ReorderTestBase):
    def test_deleted_variant_is_reported_and_the_rest_still_added(self):
        order = make_order_with_items(self.user, [(self.serum, 2), (self.cream, 1)])
        self.cream.delete()  # OrderItem.variant is SET_NULL
        self.assertIsNone(order.items.get(product_name="Day Cream").variant)

        res = self.client.post(reorder_url(order))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["added"], ["Rose Serum"])
        self.assertEqual(res.data["added_count"], 1)
        self.assertEqual(len(res.data["unavailable"]), 1)
        gone = res.data["unavailable"][0]
        self.assertEqual(gone["product_name"], "Day Cream")
        self.assertEqual(gone["reason_code"], "unavailable")
        self.assertTrue(gone["reason"])
        self.assertEqual(self.cart_quantities(), {self.serum.id: 2})

    def test_deactivated_variant_is_unavailable(self):
        order = make_order_with_items(self.user, [(self.serum, 1), (self.cream, 1)])
        self.cream.is_active = False
        self.cream.save()

        res = self.client.post(reorder_url(order))

        self.assertEqual(res.data["added"], ["Rose Serum"])
        self.assertEqual(res.data["unavailable"][0]["reason_code"], "unavailable")
        self.assertNotIn(self.cream.id, self.cart_quantities())

    def test_expired_variant_that_is_still_active_is_unavailable(self):
        """Same rule as the cart: the nightly deactivation sweep may not have run."""
        order = make_order_with_items(self.user, [(self.serum, 1)])
        self.serum.expiration_date = timezone.now().date() - timedelta(days=1)
        self.serum.save()

        res = self.client.post(reorder_url(order))

        self.assertEqual(res.data["added_count"], 0)
        self.assertEqual(res.data["unavailable"][0]["reason_code"], "unavailable")

    def test_variant_with_no_expiry_date_is_fine(self):
        order = make_order_with_items(self.user, [(self.serum, 1)])
        self.assertIsNone(self.serum.expiration_date)
        self.assertEqual(self.client.post(reorder_url(order)).data["added_count"], 1)

    def test_out_of_stock_variant_is_reported_with_the_stock_reason(self):
        order = make_order_with_items(self.user, [(self.serum, 1), (self.cream, 2)])
        self.cream.stock = 0
        self.cream.save()

        res = self.client.post(reorder_url(order))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["added"], ["Rose Serum"])
        oos = res.data["unavailable"][0]
        self.assertEqual(oos["product_name"], "Day Cream")
        self.assertEqual(oos["reason_code"], "out_of_stock")
        self.assertIn("out of stock", oos["reason"])
        self.assertNotIn(self.cream.id, self.cart_quantities())

    def test_nothing_available_is_still_a_200_with_everything_listed(self):
        order = make_order_with_items(self.user, [(self.serum, 1), (self.cream, 1)])
        self.serum.stock = 0
        self.serum.save()
        self.cream.is_active = False
        self.cream.save()

        res = self.client.post(reorder_url(order))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["added_count"], 0)
        self.assertEqual(
            {u["reason_code"] for u in res.data["unavailable"]},
            {"out_of_stock", "unavailable"},
        )
        self.assertEqual(self.cart_quantities(), {})

    def test_an_order_with_no_items_is_a_clean_empty_result(self):
        order = make_order_with_items(self.user, [])
        res = self.client.post(reorder_url(order))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {"added_count": 0, "added": [], "unavailable": []})


class TestReorderPermissions(ReorderTestBase):
    def test_another_users_order_is_404_and_adds_nothing(self):
        other = make_user(email="other@example.com")
        theirs = make_order_with_items(other, [(self.serum, 2)])

        res = self.client.post(reorder_url(theirs))

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(CartItem.objects.exists())

    def test_guest_order_with_no_owner_is_404(self):
        guest_order = make_order_with_items(self.user, [(self.serum, 1)])
        guest_order.user = None
        guest_order.save(update_fields=["user"])
        self.assertEqual(
            self.client.post(reorder_url(guest_order)).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_unknown_order_is_404(self):
        res = self.client.post(reverse("order:order-reorder", kwargs={"pk": 99999}))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_requires_authentication(self):
        order = make_order_with_items(self.user, [(self.serum, 1)])
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.post(reorder_url(order)).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_post_only(self):
        order = make_order_with_items(self.user, [(self.serum, 1)])
        self.assertEqual(
            self.client.get(reorder_url(order)).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_adds_to_the_requesters_cart_not_the_owners(self):
        """Ownership is enforced, so the order's owner and the cart's owner match."""
        order = make_order_with_items(self.user, [(self.serum, 1)])
        self.client.post(reorder_url(order))
        self.assertEqual(Cart.objects.get(user=self.user).items.count(), 1)
        self.assertEqual(Cart.objects.count(), 1)
