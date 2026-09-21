from datetime import timedelta
from decimal import Decimal

from cart.models import Cart, CartItem
from dashboard.models import Address
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from order.models import Order, OrderItem
from rest_framework import serializers, status
from rest_framework.test import APITestCase
from shop.models import Category, Product, StockMovement

from .factories import (
    SHIPPING_COST,
    TAX_RATE,
    VALID_PAYLOAD,
    make_cart_with_items,
    make_category,
    make_color,
    make_product,
    make_user,
    make_variant,
)

User = get_user_model()


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

    # ── OrderItem: variant fields (this task) ───────────────────────────────────

    def test_order_item_variant_field_links_to_variant(self):
        order = self._make_order()
        variant = make_variant(product=self.product, sku="VARIANT-1")
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            product_slug=self.product.slug,
            variant=variant,
            variant_sku=variant.sku,
            unit_price=variant.price,
            quantity=1,
        )
        self.assertEqual(item.variant, variant)
        self.assertEqual(item.variant_sku, "VARIANT-1")

    def test_order_item_variant_attributes_json_default_is_empty_dict(self):
        order = self._make_order()
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            product_slug=self.product.slug,
            unit_price=self.product.price,
            quantity=1,
        )
        self.assertEqual(item.variant_attributes_json, {})

    def test_order_item_variant_attributes_json_stores_color(self):
        order = self._make_order()
        color = make_color(name="Shade 320 - Warm Beige")
        variant = make_variant(product=self.product, color=color)
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            product_slug=self.product.slug,
            variant=variant,
            variant_sku=variant.sku,
            variant_attributes_json={"color": color.name},
            unit_price=variant.price,
            quantity=1,
        )
        self.assertEqual(
            item.variant_attributes_json, {"color": "Shade 320 - Warm Beige"}
        )

    def test_order_item_variant_null_on_variant_deletion(self):
        """
        When the ProductVariant is deleted the FK becomes NULL
        (SET_NULL) — same survivability guarantee as `product` — but
        the frozen `variant_sku`/`variant_attributes_json` snapshots
        must remain intact, since that's the whole point of freezing
        them.
        """
        order = self._make_order()
        color = make_color(name="Matte Red")
        variant = make_variant(product=self.product, sku="DOOMED-SKU", color=color)
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            product_slug=self.product.slug,
            variant=variant,
            variant_sku=variant.sku,
            variant_attributes_json={"color": color.name},
            unit_price=variant.price,
            quantity=1,
        )
        variant.delete()
        item.refresh_from_db()
        self.assertIsNone(item.variant)
        self.assertEqual(item.variant_sku, "DOOMED-SKU")
        self.assertEqual(item.variant_attributes_json, {"color": "Matte Red"})


# ══════════════════════════════════════════════════════════════════════════════
# 2. OrderCreateSerializer Tests
# ══════════════════════════════════════════════════════════════════════════════


class OrderCreateSerializerTests(TestCase):
    """Validate the create serializer's financial math and business rules."""

    def setUp(self):
        self.user = make_user()
        self.product = make_product(price="100.00", stock=5)
        # ProductVariant.stock is the real, authoritative inventory count
        # (Tasks 3.1.1.1–3.1.1.4) — deliberately different from
        # self.product.stock so any test that accidentally asserts
        # against the wrong (superseded) field would fail loudly.
        self.variant = make_variant(product=self.product, price="100.00", stock=5)
        make_cart_with_items(self.user, [{"variant": self.variant, "quantity": 2}])
        self.request = type(
            "Request", (), {"user": self.user, "build_absolute_uri": lambda s, u: u}
        )()

    def _serialize(self, data=None):
        from order.serializers import OrderCreateSerializer

        payload = {**VALID_PAYLOAD, **(data or {})}
        s = OrderCreateSerializer(data=payload, context={"request": self.request})
        return s

    def _create_bypassing_stock_precheck(self, cart, data=None):
        """
        Build validated_data via to_internal_value() (real per-field
        coercion, same as is_valid() uses internally) WITHOUT invoking
        the object-level validate() method — i.e. without this task's
        stock pre-check. Used by tests that specifically exercise
        create()'s OWN atomic, select_for_update()-locked stock check
        (Epic 1/3), which — for a genuinely out-of-stock variant in a
        single, non-concurrent request — this task's earlier pre-check
        would now otherwise catch first, since both layers legitimately
        cover the same non-concurrent scenario by design (the pre-check
        is fast UX feedback; create()'s check is the actual race-safe
        guarantee for genuine concurrent races, which is what these
        tests are proxies for).
        """
        from order.serializers import OrderCreateSerializer

        payload = {**VALID_PAYLOAD, **(data or {})}
        s = OrderCreateSerializer(data=payload, context={"request": self.request})
        validated_data = s.to_internal_value(payload)
        validated_data["cart"] = cart
        return s, validated_data

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

    def test_payment_method_omitted_entirely_defaults_to_credit_card(self):
        # Task 6.4.1.3: the frontend checkout form no longer asks the
        # customer to pick a payment method at all (real payment happens
        # on the gateway's hosted page) and stopped sending this field
        # entirely (Task 6.4.1.1). Omitting it must NOT reject the
        # checkout — it must default, not 400.
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "payment_method"}
        from order.serializers import OrderCreateSerializer

        s = OrderCreateSerializer(data=payload, context={"request": self.request})
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()
        self.assertEqual(order.payment_method, Order.PaymentMethod.CREDIT_CARD)

    def test_discount_field_removed_client_input_is_ignored(self):
        """
        Security fix (this task): `discount` is no longer a declared field
        on OrderCreateSerializer at all — a client can no longer control
        the discount applied at checkout by sending an arbitrary
        `discount` value in the POST body. DRF silently ignores unknown
        input keys, so submitting `discount` here must not raise a
        validation error (it's simply not read), and full lock-in
        coverage (asserting the resulting Order really does get
        discount=0 regardless of what a malicious client sends) lives in
        the dedicated security-regression test added alongside this fix.
        """
        s = self._serialize({"discount": "-10.00"})
        self.assertTrue(s.is_valid(), s.errors)

        s2 = self._serialize({"discount": "999999.00"})
        self.assertTrue(s2.is_valid(), s2.errors)

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

    # ── Stock/availability pre-check (this task) ────────────────────────────────

    def test_out_of_stock_variant_fails_with_400_identifying_the_item(self):
        self.variant.stock = 1  # cart wants 2
        self.variant.save(update_fields=["stock"])

        s = self._serialize()
        self.assertFalse(s.is_valid())
        self.assertIn("cart", s.errors)
        errors = [str(e) for e in s.errors["cart"]]
        self.assertTrue(
            any(self.product.name in e and self.variant.sku in e for e in errors),
            errors,
        )

    def test_deactivated_variant_fails_with_clear_message(self):
        self.variant.is_active = False
        self.variant.save(update_fields=["is_active"])

        s = self._serialize()
        self.assertFalse(s.is_valid())
        self.assertIn("cart", s.errors)
        errors = [str(e) for e in s.errors["cart"]]
        self.assertTrue(
            any(self.product.name in e and self.variant.sku in e for e in errors),
            errors,
        )

    def test_multiple_problem_items_all_surfaced_in_one_response(self):
        out_of_stock_variant = make_variant(
            name="OOS Item", slug="oos-item", price="50.00", stock=0
        )
        inactive_variant = make_variant(
            name="Inactive Item",
            slug="inactive-item",
            price="30.00",
            stock=10,
            is_active=False,
        )
        cart = Cart.objects.get(user=self.user)
        CartItem.objects.create(cart=cart, variant=out_of_stock_variant, quantity=1)
        CartItem.objects.create(cart=cart, variant=inactive_variant, quantity=1)
        # self.variant (from setUp) still has sufficient stock and is
        # active, so it should NOT appear in the errors.

        s = self._serialize()
        self.assertFalse(s.is_valid())
        errors = [str(e) for e in s.errors["cart"]]
        self.assertEqual(len(errors), 2)
        self.assertTrue(any(out_of_stock_variant.sku in e for e in errors))
        self.assertTrue(any(inactive_variant.sku in e for e in errors))
        self.assertFalse(any(self.variant.sku in e for e in errors))

    def test_no_problems_passes_validate_and_proceeds_to_create(self):
        """Regression check: the happy path must still work exactly as before."""
        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()
        self.assertIsNotNone(order.pk)

    def test_stock_precheck_does_not_use_select_for_update(self):
        """
        This check is explicitly non-locking — only create()'s existing
        logic should ever take row locks. Confirmed by inspecting the
        actual SQL Django issues for the pre-check's queryset.
        """
        self.variant.stock = 0
        self.variant.save(update_fields=["stock"])

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            s = self._serialize()
            s.is_valid()

        cart_queries = [
            q["sql"]
            for q in ctx.captured_queries
            if "cart_cartitem" in q["sql"].lower()
        ]
        self.assertTrue(
            cart_queries, "Expected at least one query against cart_cartitem"
        )
        self.assertFalse(
            any("FOR UPDATE" in q.upper() for q in cart_queries),
            "Stock pre-check must not use select_for_update()",
        )

    # ── Iran province / postal code validation at checkout (Task 5.2.1.4) ────

    def test_checkout_with_invalid_province_is_rejected(self):
        """
        The manual (non-saved-address) checkout path must apply the same
        validation rigor as the now-constrained Address model — a
        customer typing a free-text address at checkout shouldn't be
        able to submit a province that no saved address could hold.
        """
        s = self._serialize({"state": "california"})
        self.assertFalse(s.is_valid())
        self.assertIn("state", s.errors)

    def test_checkout_with_valid_iran_province_is_accepted(self):
        s = self._serialize({"state": "isfahan"})
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()
        self.assertEqual(order.shipping_state, "isfahan")

    def test_checkout_rejects_postal_code_that_is_too_short(self):
        s = self._serialize({"zip": "123456789"})  # 9 digits
        self.assertFalse(s.is_valid())
        self.assertIn("zip", s.errors)

    def test_checkout_rejects_postal_code_that_is_too_long(self):
        s = self._serialize({"zip": "12345678901"})  # 11 digits
        self.assertFalse(s.is_valid())
        self.assertIn("zip", s.errors)

    def test_checkout_rejects_postal_code_containing_letters(self):
        s = self._serialize({"zip": "12345678ab"})
        self.assertFalse(s.is_valid())
        self.assertIn("zip", s.errors)

    def test_checkout_accepts_valid_10_digit_postal_code(self):
        s = self._serialize({"zip": "9876543210"})
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()
        self.assertEqual(order.shipping_zip, "9876543210")

    def test_save_address_from_checkout_produces_a_model_valid_address(self):
        """
        End-to-end consistency: an Address created via checkout's
        save_address path must itself pass the Address model's own
        full_clean() — i.e. the checkout-layer validation genuinely
        matches the model-layer constraints rather than merely
        resembling them.
        """
        s = self._serialize({"save_address": True})
        self.assertTrue(s.is_valid(), s.errors)
        s.save()

        saved = Address.objects.filter(user=self.user).latest("id")
        saved.full_clean()  # must not raise

    # ── Checkout via saved address (address_id / save_address) ──────────────

    def test_checkout_with_valid_address_id_uses_saved_address_fields(self):
        address = Address.objects.create(
            user=self.user,
            first_name="Saved",
            last_name="Recipient",
            phone="555-9999",
            address_line="99 Saved Ave",
            apartment="Unit 5",
            city="Saved City",
            province="tehran",
            postal_code="0000000000",
            country="US",
        )
        # _serialize() merges its argument ON TOP OF VALID_PAYLOAD, so this
        # payload actually still contains VALID_PAYLOAD's manual address
        # fields underneath address_id — this deliberately tests the
        # "address_id overrides manual fields when both are present"
        # precedence rule. See the next test for the "manual fields
        # omitted entirely" case.
        payload = {"address_id": address.id}
        s = self._serialize(payload)
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()

        self.assertEqual(order.first_name, "Saved")
        self.assertEqual(order.last_name, "Recipient")
        self.assertEqual(order.phone, "555-9999")
        self.assertEqual(order.shipping_address, "99 Saved Ave")
        self.assertEqual(order.shipping_apartment, "Unit 5")
        self.assertEqual(order.shipping_city, "Saved City")
        self.assertEqual(order.shipping_state, "tehran")
        self.assertEqual(order.shipping_zip, "0000000000")
        self.assertEqual(order.shipping_country, "US")

    def test_checkout_with_address_id_and_manual_fields_entirely_omitted(self):
        """
        Unlike the previous test (which goes through _serialize()'s
        merge-with-VALID_PAYLOAD), this constructs the payload directly
        to prove manual address fields can be OMITTED ENTIRELY when
        checking out via address_id — the actual real-world shape of an
        address_id-based checkout request.
        """
        from order.serializers import OrderCreateSerializer

        address = Address.objects.create(
            user=self.user,
            first_name="Saved",
            last_name="Recipient",
            phone="555-9999",
            address_line="99 Saved Ave",
            city="Saved City",
            province="tehran",
            postal_code="0000000000",
            country="US",
        )
        payload = {
            "email": VALID_PAYLOAD["email"],
            "billing_same": True,
            "payment_method": VALID_PAYLOAD["payment_method"],
            "card_last_four": VALID_PAYLOAD["card_last_four"],
            "address_id": address.id,
        }
        s = OrderCreateSerializer(data=payload, context={"request": self.request})
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()

        self.assertEqual(order.first_name, "Saved")
        self.assertEqual(order.shipping_address, "99 Saved Ave")
        self.assertEqual(order.shipping_city, "Saved City")

    def test_checkout_with_another_users_address_id_is_rejected(self):
        """The most important test in this task: the ownership check."""
        other_user = make_user(email="someone-else@example.com")
        other_users_address = Address.objects.create(
            user=other_user,
            first_name="Not",
            last_name="Yours",
            phone="555-0000",
            address_line="1 Private Lane",
            city="Nowhere",
            province="fars",
            postal_code="1111111111",
            country="US",
        )

        s = self._serialize({"address_id": other_users_address.id})
        self.assertFalse(s.is_valid())
        self.assertIn("address_id", s.errors)

        # Confirm nothing about the other user's address leaked into an
        # order at all.
        self.assertFalse(
            Order.objects.filter(shipping_address="1 Private Lane").exists()
        )

    def test_checkout_with_no_address_id_and_full_manual_fields_still_works(self):
        """Regression check: the pre-existing manual-fields path is untouched."""
        s = self._serialize()  # VALID_PAYLOAD has no address_id
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()

        self.assertEqual(order.first_name, VALID_PAYLOAD["first_name"])
        self.assertEqual(order.shipping_address, VALID_PAYLOAD["address"])
        self.assertEqual(order.shipping_city, VALID_PAYLOAD["city"])

    def test_checkout_with_neither_address_id_nor_complete_manual_fields_fails(self):
        from order.serializers import OrderCreateSerializer

        # Built directly (not via self._serialize(), which MERGES its
        # argument ON TOP OF VALID_PAYLOAD — so passing a dict with a key
        # removed wouldn't actually unset it; a real client request
        # simply omitting "city" is a genuinely different payload shape).
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "city"}
        s = OrderCreateSerializer(data=payload, context={"request": self.request})
        self.assertFalse(s.is_valid())
        self.assertIn("city", s.errors)

    def test_checkout_with_manual_fields_and_save_address_creates_new_address(self):
        addresses_before = Address.objects.filter(user=self.user).count()

        payload = {**VALID_PAYLOAD, "save_address": True}
        s = self._serialize(payload)
        self.assertTrue(s.is_valid(), s.errors)
        s.save()

        self.assertEqual(
            Address.objects.filter(user=self.user).count(), addresses_before + 1
        )
        saved = Address.objects.filter(user=self.user).latest("id")
        self.assertEqual(saved.first_name, VALID_PAYLOAD["first_name"])
        self.assertEqual(saved.last_name, VALID_PAYLOAD["last_name"])
        self.assertEqual(saved.phone, VALID_PAYLOAD["phone"])
        self.assertEqual(saved.address_line, VALID_PAYLOAD["address"])
        self.assertEqual(saved.apartment, VALID_PAYLOAD["apartment"])
        self.assertEqual(saved.city, VALID_PAYLOAD["city"])
        self.assertEqual(saved.province, VALID_PAYLOAD["state"])
        self.assertEqual(saved.postal_code, VALID_PAYLOAD["zip"])
        self.assertEqual(saved.country, VALID_PAYLOAD["country"])

    def test_checkout_with_address_id_and_save_address_does_not_duplicate(self):
        """
        save_address is only meaningful for the manual-fields path — an
        address_id-based checkout references an address that's already
        saved by definition, so save_address=True there should not
        create a second, duplicate Address row.
        """
        address = Address.objects.create(
            user=self.user,
            first_name="Saved",
            last_name="Recipient",
            phone="555-9999",
            address_line="99 Saved Ave",
            city="Saved City",
            province="tehran",
            postal_code="0000000000",
            country="US",
        )
        addresses_before = Address.objects.filter(user=self.user).count()

        payload = {
            "email": VALID_PAYLOAD["email"],
            "payment_method": VALID_PAYLOAD["payment_method"],
            "card_last_four": VALID_PAYLOAD["card_last_four"],
            "address_id": address.id,
            "save_address": True,
        }
        s = self._serialize(payload)
        self.assertTrue(s.is_valid(), s.errors)
        s.save()

        self.assertEqual(
            Address.objects.filter(user=self.user).count(), addresses_before
        )

    # ── Price integrity (this task) ──────────────────────────────────────────

    def test_serializer_has_no_client_writable_price_fields(self):
        """
        Structural guard, mirroring Epic 1 Task 1.2.1.2's discount
        regression test but at the schema level: OrderCreateSerializer
        must never declare a price/subtotal/unit_price field a client
        could populate. All monetary values are derived server-side from
        the cart, never trusted from the request body.
        """
        from order.serializers import OrderCreateSerializer

        fields = OrderCreateSerializer().fields
        self.assertNotIn("price", fields)
        self.assertNotIn("subtotal", fields)
        self.assertNotIn("unit_price", fields)
        self.assertNotIn("total", fields)

    def test_price_change_between_cart_add_and_checkout_uses_current_price(self):
        """
        The variant's price is updated via the ORM AFTER the item is
        already in the cart (simulating an admin price change landing
        mid-flight) — the resulting Order's subtotal/total AND the
        OrderItem's unit_price must reflect the NEW price, proving
        there's no stale/cached pricing anywhere in the flow (cart
        subtotal, order subtotal, and the per-item snapshot are all
        derived from the same single, freshly-read value — see this
        task's create() restructuring).
        """
        self.variant.price = Decimal("150.00")
        self.variant.save(update_fields=["price"])

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()

        # setUp's cart has quantity=2 of self.variant.
        expected_subtotal = Decimal("150.00") * 2
        self.assertEqual(order.subtotal, expected_subtotal)

        order_item = order.items.get(variant=self.variant)
        self.assertEqual(order_item.unit_price, Decimal("150.00"))

        expected_tax = (expected_subtotal * TAX_RATE).quantize(Decimal("0.01"))
        self.assertEqual(order.tax, expected_tax)

    def test_order_subtotal_and_orderitem_unit_prices_are_internally_consistent(self):
        """
        Order.subtotal must equal sum(OrderItem.unit_price × quantity)
        for every item — the exact property this task's restructuring
        (deriving both from one captured per-item price, read after the
        row lock is acquired) exists to guarantee.
        """
        second_variant = make_variant(
            name="Second Item", slug="second-item", price="75.00", stock=10
        )
        cart = Cart.objects.get(user=self.user)
        CartItem.objects.create(cart=cart, variant=second_variant, quantity=3)

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()

        computed_subtotal = sum(
            item.unit_price * item.quantity for item in order.items.all()
        )
        self.assertEqual(order.subtotal, computed_subtotal)

    def test_price_change_in_the_narrow_window_between_lock_acquisition_uses_locked_value(
        self,
    ):
        """
        Deterministically simulates the specific TOCTOU gap this task's
        restructuring closes: a price change landing in the narrow
        window AFTER cart_items is fetched (unlocked) but BEFORE
        locked_variants is fetched (select_for_update()) — the exact
        scenario a real concurrent request could produce, reproduced
        here without needing actual threads (unlike
        test_stock_concurrency.py's approach for stock, since triggering
        it via genuine concurrency for a single ORM call is harder to
        pin down deterministically for this narrower gap).

        Before this task, OrderItem.unit_price came from
        cart_item.unit_price (the UNLOCKED, earlier-queried object) —
        so this exact scenario would have produced an OrderItem
        reflecting the STALE pre-race price, inconsistent with
        Order.subtotal if that had instead been computed fresh. After
        this task, both are derived solely from locked_variant.price,
        so the LOCKED, later value must win.
        """
        from unittest.mock import patch

        from shop.models import ProductVariant

        original_select_for_update = ProductVariant.objects.select_for_update

        def side_effect(*args, **kwargs):
            # Fires exactly once cart_items has already been fetched
            # (with the OLD price still attached to that queryset's
            # objects) but before the locked variants query runs.
            ProductVariant.objects.filter(pk=self.variant.pk).update(
                price=Decimal("999.00")
            )
            return original_select_for_update(*args, **kwargs)

        with patch.object(
            ProductVariant.objects, "select_for_update", side_effect=side_effect
        ):
            s = self._serialize()
            self.assertTrue(s.is_valid(), s.errors)
            order = s.save()

        order_item = order.items.get(variant=self.variant)
        self.assertEqual(order_item.unit_price, Decimal("999.00"))
        self.assertEqual(order.subtotal, Decimal("999.00") * 2)  # setUp's quantity=2

    # ── Financial calculations ────────────────────────────────────────────────

    def test_order_subtotal_matches_cart_subtotal(self):
        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()
        # Order subtotal = 2 × $100 — captured as a snapshot at checkout
        # time, independent of the cart's own state afterward (Task
        # 6.4.1.2: the cart is deliberately preserved, not cleared, at
        # order-creation time any more).
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
        # discount is no longer a real input (see this task's security
        # fix) — sending one is simply ignored, and the formula always
        # uses discount=0.
        s = self._serialize({"discount": "10.00"})
        s.is_valid()
        order = s.save()
        expected = (order.subtotal + SHIPPING_COST + order.tax).quantize(
            Decimal("0.01")
        )
        self.assertEqual(order.total, expected)
        self.assertEqual(order.discount, Decimal("0.00"))

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

    # ── Variant snapshot fields (this task) ───────────────────────────────────

    def test_order_item_snapshots_variant_and_sku(self):
        """
        OrderCreateSerializer.create() must read cart_item.variant
        (not cart_item.product, which no longer exists on CartItem
        after Task 3.1.1.3) and populate variant/variant_sku on the
        resulting OrderItem.
        """
        Cart.objects.filter(user=self.user).delete()
        color = make_color(name="Shade 320 - Warm Beige")
        variant = make_variant(
            product=self.product, sku="FOUND-320", color=color, price="100.00"
        )
        make_cart_with_items(self.user, [{"variant": variant, "quantity": 2}])

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()

        item = order.items.first()
        self.assertEqual(item.variant, variant)
        self.assertEqual(item.variant_sku, "FOUND-320")

    def test_order_item_snapshots_variant_attributes_json_with_color(self):
        Cart.objects.filter(user=self.user).delete()
        color = make_color(name="Shade 320 - Warm Beige")
        variant = make_variant(product=self.product, color=color, price="100.00")
        make_cart_with_items(self.user, [{"variant": variant, "quantity": 1}])

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()

        item = order.items.first()
        self.assertEqual(
            item.variant_attributes_json, {"color": "Shade 320 - Warm Beige"}
        )

    def test_order_item_snapshots_variant_attributes_json_without_color(self):
        """A colorless variant must snapshot color=None, not omit the key."""
        Cart.objects.filter(user=self.user).delete()
        variant = make_variant(product=self.product, color=None, price="100.00")
        make_cart_with_items(self.user, [{"variant": variant, "quantity": 1}])

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()

        item = order.items.first()
        self.assertEqual(item.variant_attributes_json, {"color": None})

    def test_order_item_still_populates_parent_product_fields(self):
        """
        Product-level snapshot fields (product/product_name/product_slug)
        must still be populated correctly — just sourced through
        cart_item.variant.product instead of cart_item.product now.
        """
        Cart.objects.filter(user=self.user).delete()
        variant = make_variant(product=self.product, price="100.00")
        make_cart_with_items(self.user, [{"variant": variant, "quantity": 1}])

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()

        item = order.items.first()
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.product_name, self.product.name)
        self.assertEqual(item.product_slug, self.product.slug)

    def test_ordering_two_color_variants_of_same_product_creates_two_order_items(self):
        """
        A customer ordering two different shades of the SAME product
        (two separate cart lines, per Task 3.1.1.3) must end up with
        two separate OrderItem rows — distinct variant_sku and
        variant_attributes_json — both correctly linked back to the
        same underlying product.
        """
        Cart.objects.filter(user=self.user).delete()
        shade_a_color = make_color(name="Shade 110 - Porcelain")
        shade_b_color = make_color(name="Shade 320 - Warm Beige")
        shade_a = make_variant(
            product=self.product, sku="FOUND-110", color=shade_a_color, price="100.00"
        )
        shade_b = make_variant(
            product=self.product, sku="FOUND-320", color=shade_b_color, price="100.00"
        )
        make_cart_with_items(
            self.user,
            [
                {"variant": shade_a, "quantity": 1},
                {"variant": shade_b, "quantity": 1},
            ],
        )

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()

        self.assertEqual(order.items.count(), 2)

        items_by_sku = {item.variant_sku: item for item in order.items.all()}
        self.assertEqual(set(items_by_sku.keys()), {"FOUND-110", "FOUND-320"})

        item_a = items_by_sku["FOUND-110"]
        item_b = items_by_sku["FOUND-320"]

        self.assertNotEqual(
            item_a.variant_attributes_json, item_b.variant_attributes_json
        )
        self.assertEqual(
            item_a.variant_attributes_json, {"color": "Shade 110 - Porcelain"}
        )
        self.assertEqual(
            item_b.variant_attributes_json, {"color": "Shade 320 - Warm Beige"}
        )

        # Both lines trace back to the same underlying product.
        self.assertEqual(item_a.product_id, self.product.id)
        self.assertEqual(item_b.product_id, self.product.id)
        self.assertEqual(item_a.variant_id, shade_a.id)
        self.assertEqual(item_b.variant_id, shade_b.id)

    def test_cart_preserved_after_order_creation(self):
        # Task 6.4.1.2: the cart is deliberately NOT cleared at order
        # creation any more — only on CONFIRMED payment success (see
        # PaymentCallbackView). Clearing it here, before the customer
        # ever reaches the gateway, meant a failed/cancelled payment lost
        # the cart entirely.
        s = self._serialize()
        s.is_valid()
        s.save()
        cart = Cart.objects.get(user=self.user)
        self.assertGreater(cart.items.count(), 0)

    def test_order_status_is_pending_after_creation(self):
        s = self._serialize()
        s.is_valid()
        order = s.save()
        self.assertEqual(order.status, Order.Status.PENDING)

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

        with patch(
            "order.serializers.OrderItem.objects.create", side_effect=flaky_create
        ):
            with self.assertRaises(RuntimeError):
                s.save()

        # No orphaned Order row was committed.
        self.assertEqual(Order.objects.count(), orders_before)

        # Cart items were not deleted.
        cart.refresh_from_db()
        self.assertEqual(cart.items.count(), items_before)

    # ── Row-level locking on checkout ─────────────────────────────────────────

    def test_checkout_locks_only_the_variants_in_the_cart(self):
        """
        select_for_update() must be invoked on the ProductVariant
        queryset, scoped to exactly the variant ids referenced by the
        cart being checked out — not the whole table. Locking moved
        from Product to ProductVariant in this task, since
        ProductVariant.stock is now the real, authoritative inventory
        count.
        """
        from unittest.mock import patch

        from shop.models import ProductVariant

        other_variant = make_variant(
            name="Untouched", slug="untouched", price="15.00"
        )  # not in the cart — must not be locked

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)

        real_qs = ProductVariant.objects.select_for_update(of=("self",))
        with patch(
            "order.serializers.ProductVariant.objects.select_for_update",
            return_value=real_qs,
        ) as mock_select_for_update:
            order = s.save()

        mock_select_for_update.assert_called_once_with(of=("self",))

        locked_variant_ids = set(order.items.values_list("variant_id", flat=True))
        self.assertEqual(locked_variant_ids, {self.variant.id})
        self.assertNotIn(other_variant.id, locked_variant_ids)

    def test_checkout_variant_query_uses_for_update(self):
        """
        The locking queryset's compiled SQL must contain FOR UPDATE. This
        only has real meaning on Postgres (the project's configured engine
        in core/settings/base.py); skip on backends where SELECT ... FOR
        UPDATE isn't part of the compiled SQL the same way.

        `of=("self",)` scopes the lock to just the ProductVariant table
        (not any select_related joins) — required because `color` is a
        nullable FK, and Postgres rejects `FOR UPDATE` across the
        nullable side of an outer join.
        """
        from django.db import connection
        from shop.models import ProductVariant

        if connection.vendor == "sqlite":
            self.skipTest("SELECT ... FOR UPDATE semantics differ on SQLite")

        qs = ProductVariant.objects.select_for_update(of=("self",)).filter(
            id=self.variant.id
        )
        self.assertIn("FOR UPDATE", str(qs.query))

    def test_order_item_variant_is_the_locked_instance(self):
        """
        The ProductVariant referenced on the created OrderItem must be
        the same row fetched (and locked) by the select_for_update()
        query, not a stale copy obtained earlier via the cart's
        select_related.
        """
        s = self._serialize()
        s.is_valid()
        order = s.save()
        item = order.items.first()
        self.assertEqual(item.variant_id, self.variant.id)
        self.assertEqual(item.variant_sku, self.variant.sku)
        # And the parent product snapshot fields still trace back
        # correctly, one level deeper through the locked variant.
        self.assertEqual(item.product_id, self.product.id)
        self.assertEqual(item.product_name, self.product.name)

    # ── Stock validation + decrement ──────────────────────────────────────────

    def test_sufficient_stock_decrements_by_ordered_quantity(self):
        """
        Ordering a quantity within available stock succeeds, and the
        VARIANT's stock is reduced by exactly the ordered quantity.
        ProductVariant.stock is the real, authoritative inventory count
        now — Product.stock is superseded and must be left untouched by
        checkout.
        """
        # self.variant has stock=5, cart quantity=2 (see setUp).
        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        s.save()

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5 - 2)

        # Product.stock is superseded and must be untouched by checkout.
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_insufficient_stock_raises_and_rolls_back_everything(self):
        """
        Ordering more than available stock must raise a ValidationError,
        and afterward: no Order or OrderItem rows exist, and the
        variant's stock is completely unchanged — proving the atomic
        rollback covers the new stock-decrement logic too.
        """
        low_stock_variant = make_variant(
            name="Scarce Item", slug="scarce-item", price="40.00", stock=1
        )
        Cart.objects.filter(user=self.user).delete()
        cart = make_cart_with_items(
            self.user, [{"variant": low_stock_variant, "quantity": 3}]
        )

        orders_before = Order.objects.count()
        items_before = OrderItem.objects.count()
        stock_before = low_stock_variant.stock

        s, validated_data = self._create_bypassing_stock_precheck(cart)

        with self.assertRaises(serializers.ValidationError) as ctx:
            s.create(validated_data)
        self.assertIn("stock", ctx.exception.detail)

        self.assertEqual(Order.objects.count(), orders_before)
        self.assertEqual(OrderItem.objects.count(), items_before)

        low_stock_variant.refresh_from_db()
        self.assertEqual(low_stock_variant.stock, stock_before)

    def test_insufficient_stock_error_message_identifies_specific_variant(self):
        """
        The stock-shortage error must name the SPECIFIC variant that's
        short (color if set, else SKU) — not just the base product name
        — so a customer/support team knows exactly which shade is out.
        """
        color = make_color(name="Shade 320 - Warm Beige")
        low_stock_variant = make_variant(
            product=self.product, sku="FOUND-320", color=color, stock=1
        )
        Cart.objects.filter(user=self.user).delete()
        cart = make_cart_with_items(
            self.user, [{"variant": low_stock_variant, "quantity": 3}]
        )

        s, validated_data = self._create_bypassing_stock_precheck(cart)

        with self.assertRaises(serializers.ValidationError) as ctx:
            s.create(validated_data)
        message = str(ctx.exception.detail["stock"])
        self.assertIn(self.product.name, message)
        self.assertIn("Shade 320 - Warm Beige", message)

    def test_insufficient_stock_error_message_falls_back_to_sku_without_color(self):
        """Colorless variants identify themselves by SKU in the error."""
        colorless_variant = make_variant(
            product=self.product, sku="COLORLESS-SKU", color=None, stock=1
        )
        Cart.objects.filter(user=self.user).delete()
        cart = make_cart_with_items(
            self.user, [{"variant": colorless_variant, "quantity": 3}]
        )

        s, validated_data = self._create_bypassing_stock_precheck(cart)

        with self.assertRaises(serializers.ValidationError) as ctx:
            s.create(validated_data)
        message = str(ctx.exception.detail["stock"])
        self.assertIn("COLORLESS-SKU", message)

    def test_second_item_out_of_stock_prevents_first_item_decrement_too(self):
        """
        Cart with two items: the first has enough stock, the second does
        not. Neither variant's stock should be decremented — partial
        success across items is not allowed.
        """
        healthy_variant = make_variant(
            name="Plenty", slug="plenty", price="10.00", stock=10
        )
        scarce_variant = make_variant(
            name="Scarce Two", slug="scarce-two", price="20.00", stock=1
        )
        Cart.objects.filter(user=self.user).delete()
        cart = make_cart_with_items(
            self.user,
            [
                {"variant": healthy_variant, "quantity": 2},
                {"variant": scarce_variant, "quantity": 5},
            ],
        )

        orders_before = Order.objects.count()
        healthy_stock_before = healthy_variant.stock
        scarce_stock_before = scarce_variant.stock

        s, validated_data = self._create_bypassing_stock_precheck(cart)

        with self.assertRaises(serializers.ValidationError):
            s.create(validated_data)

        self.assertEqual(Order.objects.count(), orders_before)

        healthy_variant.refresh_from_db()
        scarce_variant.refresh_from_db()
        self.assertEqual(healthy_variant.stock, healthy_stock_before)
        self.assertEqual(scarce_variant.stock, scarce_stock_before)

    def test_two_different_variants_of_same_product_do_not_contend_for_stock(self):
        """
        Ordering two different color variants of the SAME product in one
        cart must decrement each variant's stock independently — they
        must not be treated as sharing one pooled stock number (that
        would be the old, incorrect Product-level behavior).
        """
        shade_a = make_variant(product=self.product, sku="SHADE-A", stock=3)
        shade_b = make_variant(product=self.product, sku="SHADE-B", stock=3)
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(
            self.user,
            [
                {"variant": shade_a, "quantity": 2},
                {"variant": shade_b, "quantity": 1},
            ],
        )

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        s.save()

        shade_a.refresh_from_db()
        shade_b.refresh_from_db()
        self.assertEqual(shade_a.stock, 1)  # 3 - 2
        self.assertEqual(shade_b.stock, 2)  # 3 - 1

    # ── StockMovement audit trail (Task 4.1.1.2) ─────────────────────────────

    def test_successful_order_creates_one_stock_movement_per_variant(self):
        """
        Placing a successful order creates exactly one StockMovement per
        distinct variant ordered, with reason="sale", a negative
        quantity_delta matching the ordered quantity, stock_after
        matching the variant's real post-order stock, and related_order
        pointing at the created order.
        """
        shade_a = make_variant(product=self.product, sku="SHADE-A", stock=5)
        shade_b = make_variant(product=self.product, sku="SHADE-B", stock=5)
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(
            self.user,
            [
                {"variant": shade_a, "quantity": 2},
                {"variant": shade_b, "quantity": 1},
            ],
        )

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        order = s.save()

        shade_a.refresh_from_db()
        shade_b.refresh_from_db()

        movements = StockMovement.objects.filter(related_order=order)
        self.assertEqual(movements.count(), 2)

        movement_a = movements.get(variant=shade_a)
        self.assertEqual(movement_a.reason, StockMovement.Reason.SALE)
        self.assertEqual(movement_a.quantity_delta, -2)
        self.assertEqual(movement_a.stock_after, shade_a.stock)
        self.assertEqual(movement_a.related_order_id, order.id)

        movement_b = movements.get(variant=shade_b)
        self.assertEqual(movement_b.reason, StockMovement.Reason.SALE)
        self.assertEqual(movement_b.quantity_delta, -1)
        self.assertEqual(movement_b.stock_after, shade_b.stock)
        self.assertEqual(movement_b.related_order_id, order.id)

    def test_failed_order_creates_zero_stock_movements(self):
        """
        The single most important test in this task: an order that
        fails (insufficient stock, triggering the existing Epic 3
        validation error) must create ZERO StockMovement rows. The
        movement is written inside the same atomic block as the stock
        decrement, so if the transaction rolls back, the audit entry
        must be discarded right along with it — an audit log entry for
        a decrement that never actually happened would be a lie.
        """
        low_stock_variant = make_variant(
            name="Scarce Item", slug="scarce-item", price="40.00", stock=1
        )
        Cart.objects.filter(user=self.user).delete()
        cart = make_cart_with_items(
            self.user, [{"variant": low_stock_variant, "quantity": 3}]
        )

        movements_before = StockMovement.objects.count()

        s, validated_data = self._create_bypassing_stock_precheck(cart)

        with self.assertRaises(serializers.ValidationError):
            s.create(validated_data)

        self.assertEqual(StockMovement.objects.count(), movements_before)
        self.assertFalse(
            StockMovement.objects.filter(variant=low_stock_variant).exists()
        )

    # ── Expiration validation at checkout (defense in depth) ────────────────

    def test_checkout_with_already_expired_variant_fails(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        expired_variant = make_variant(
            name="Expired Toner",
            slug="expired-toner",
            stock=5,
            expiration_date=yesterday,
        )
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(self.user, [{"variant": expired_variant, "quantity": 1}])

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)

        with self.assertRaises(serializers.ValidationError) as ctx:
            s.save()
        self.assertIn("expired_item", ctx.exception.detail)

    def test_checkout_error_identifies_the_expired_item(self):
        color = make_color(name="Shade 320 - Warm Beige")
        yesterday = timezone.now().date() - timedelta(days=1)
        expired_variant = make_variant(
            product=self.product,
            sku="FOUND-320",
            color=color,
            expiration_date=yesterday,
        )
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(self.user, [{"variant": expired_variant, "quantity": 1}])

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)

        with self.assertRaises(serializers.ValidationError) as ctx:
            s.save()
        message = str(ctx.exception.detail["expired_item"])
        self.assertIn(self.product.name, message)
        self.assertIn("Shade 320 - Warm Beige", message)

    def test_checkout_with_variant_expiring_today_succeeds(self):
        """Boundary check: expiring exactly today is still purchasable at checkout."""
        today = timezone.now().date()
        variant = make_variant(
            name="Expires Today",
            slug="expires-today",
            stock=5,
            expiration_date=today,
        )
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(self.user, [{"variant": variant, "quantity": 1}])

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        s.save()  # must not raise

        variant.refresh_from_db()
        self.assertEqual(variant.stock, 4)

    def test_checkout_with_no_expiration_date_succeeds(self):
        """Regression: a variant with expiration_date=None is unaffected."""
        variant = make_variant(
            name="No Expiry", slug="no-expiry", stock=5, expiration_date=None
        )
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(self.user, [{"variant": variant, "quantity": 1}])

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        s.save()  # must not raise

        variant.refresh_from_db()
        self.assertEqual(variant.stock, 4)

    def test_checkout_with_future_expiration_date_succeeds(self):
        tomorrow = timezone.now().date() + timedelta(days=1)
        variant = make_variant(
            name="Fresh Toner",
            slug="fresh-toner",
            stock=5,
            expiration_date=tomorrow,
        )
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(self.user, [{"variant": variant, "quantity": 1}])

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        s.save()  # must not raise

    def test_item_expired_after_being_added_to_cart_blocks_checkout_atomically(self):
        """
        The critical scenario: a cart item was VALID when added (no
        expiration_date, or a future one) but the variant has since
        expired by the time checkout happens — simulated here by
        creating the CartItem first with a valid variant, then updating
        that variant's expiration_date into the past afterward, exactly
        as the task describes.

        Must fail with 400 identifying the expired item, and — the
        critical all-or-nothing guarantee — NO Order/OrderItem rows may
        exist afterward, and NO other (non-expired) item's stock in the
        same cart may have been decremented either, proving the new
        expiration check participates correctly in the SAME atomic
        rollback as the pre-existing stock check, not some separate,
        weaker guarantee.
        """
        healthy_variant = make_variant(
            name="Still Good", slug="still-good", price="15.00", stock=10
        )
        soon_to_expire_variant = make_variant(
            name="Will Expire", slug="will-expire", price="20.00", stock=8
        )
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(
            self.user,
            [
                {"variant": healthy_variant, "quantity": 2},
                {"variant": soon_to_expire_variant, "quantity": 3},
            ],
        )

        # The variant was valid (no expiration_date) when added to the
        # cart above. Now simulate time passing / the variant's
        # expiration being set after the fact — it's since expired.
        soon_to_expire_variant.expiration_date = timezone.now().date() - timedelta(
            days=1
        )
        soon_to_expire_variant.save(update_fields=["expiration_date"])

        orders_before = Order.objects.count()
        order_items_before = OrderItem.objects.count()
        healthy_stock_before = healthy_variant.stock
        expired_stock_before = soon_to_expire_variant.stock

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)

        with self.assertRaises(serializers.ValidationError) as ctx:
            s.save()
        self.assertIn("expired_item", ctx.exception.detail)
        message = str(ctx.exception.detail["expired_item"])
        self.assertIn("Will Expire", message)

        # Nothing committed at all.
        self.assertEqual(Order.objects.count(), orders_before)
        self.assertEqual(OrderItem.objects.count(), order_items_before)

        # Neither variant's stock moved — including the healthy one,
        # proving this is a genuine all-or-nothing rollback, not a
        # partial per-item commit.
        healthy_variant.refresh_from_db()
        soon_to_expire_variant.refresh_from_db()
        self.assertEqual(healthy_variant.stock, healthy_stock_before)
        self.assertEqual(soon_to_expire_variant.stock, expired_stock_before)

    def test_expired_item_checked_before_stock_decrement_of_earlier_items(self):
        """
        Cart-item ordering matters for proving the atomicity claim: put
        the expired item AFTER a healthy item so the healthy item's
        stock would already have been decremented by the time the loop
        reaches the expired one, if the transaction weren't rolled back
        correctly.
        """
        healthy_variant = make_variant(
            name="Processed First", slug="processed-first", stock=10
        )
        expired_variant = make_variant(
            name="Processed Second",
            slug="processed-second",
            stock=5,
            expiration_date=timezone.now().date() - timedelta(days=2),
        )
        Cart.objects.filter(user=self.user).delete()
        make_cart_with_items(
            self.user,
            [
                {"variant": healthy_variant, "quantity": 1},
                {"variant": expired_variant, "quantity": 1},
            ],
        )

        s = self._serialize()
        self.assertTrue(s.is_valid(), s.errors)
        with self.assertRaises(serializers.ValidationError):
            s.save()

        healthy_variant.refresh_from_db()
        self.assertEqual(healthy_variant.stock, 10)  # untouched despite being "first"


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

    def test_post_preserves_cart_after_order(self):
        # Task 6.4.1.2: cart-clearing moved to PaymentCallbackView's
        # success path — see order/serializers.py's create() for why.
        self._post_order()
        cart = Cart.objects.get(user=self.user)
        self.assertGreater(cart.items.count(), 0)

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
        low_stock_variant = make_variant(
            name="API Scarce", slug="api-scarce", price="12.00", stock=1
        )
        make_cart_with_items(self.user, [{"variant": low_stock_variant, "quantity": 2}])

        orders_before = Order.objects.count()
        stock_before = low_stock_variant.stock

        res = self._post_order()

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        # This exact scenario (insufficient stock, no real concurrency) is
        # now caught by validate()'s non-locking pre-check (this task)
        # rather than reaching create()'s atomic path — surfaced under
        # "cart" per that check's error shape, not "stock" (create()'s
        # own key, still exercised directly in
        # OrderCreateSerializerTests via _create_bypassing_stock_precheck
        # for the genuine-concurrent-race scenario that check exists for).
        self.assertIn("cart", res.data)
        self.assertEqual(Order.objects.count(), orders_before)

        low_stock_variant.refresh_from_db()
        self.assertEqual(low_stock_variant.stock, stock_before)

    def test_post_multiple_orders_each_get_unique_numbers(self):
        res1 = self._post_order()
        make_cart_with_items(self.user, [{"product": self.product, "quantity": 1}])
        res2 = self._post_order()
        self.assertNotEqual(res1.data["order_number"], res2.data["order_number"])

    def test_post_discount_in_payload_is_ignored_not_applied_to_total(self):
        """
        Security fix (this task): a client sending `discount` in the
        checkout POST payload must have no effect — the field is not
        part of OrderCreateSerializer's declared inputs anymore, so it's
        silently ignored (unknown-field passthrough), and the resulting
        order's discount is always $0.
        """
        payload = {**VALID_PAYLOAD, "discount": "5.00"}
        res = self.client.post(self.URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(res.data["discount"]), Decimal("0.00"))
        order = Order.objects.get(user=self.user)
        subtotal = order.subtotal
        expected = (subtotal + SHIPPING_COST + order.tax).quantize(Decimal("0.01"))
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
        # ProductVariant.stock is authoritative now; keep it distinct
        # from Product.stock so any assertion against the wrong field
        # fails loudly rather than passing by coincidence.
        self.variant = make_variant(product=self.product, price="30.00", stock=10)
        make_cart_with_items(self.user, [{"variant": self.variant, "quantity": 2}])
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
        Cancelling an order returns every OrderItem's quantity back to
        its VARIANT's stock — ProductVariant.stock is the real,
        authoritative inventory count now (this task), not
        Product.stock.
        """
        # setUp() created self.order for 2 units of self.variant (stock
        # started at 10, and checkout's decrement left it at 8).
        self.variant.refresh_from_db()
        stock_after_purchase = self.variant.stock
        self.assertEqual(stock_after_purchase, 8)

        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, stock_after_purchase + 2)
        self.assertEqual(self.variant.stock, 10)

        # Product.stock is superseded and was never touched.
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_patch_cancel_with_deleted_variant_skips_gracefully(self):
        """
        If one of the order's OrderItem.variant rows was deleted after
        the order was placed (SET_NULL), cancelling must not raise, and
        stock restoration should still happen for the remaining valid
        items.
        """
        second_variant = make_variant(
            name="Backpack", slug="backpack", price="45.00", stock=10
        )
        make_cart_with_items(
            self.user,
            [
                {"variant": self.variant, "quantity": 1},
                {"variant": second_variant, "quantity": 3},
            ],
        )
        res = self.client.post("/api/orders/", VALID_PAYLOAD, format="json")
        order = Order.objects.get(pk=res.data["id"])

        second_variant.refresh_from_db()
        self.assertEqual(second_variant.stock, 7)  # 10 - 3

        # Simulate the variant having been deleted after the order was
        # placed — OrderItem.variant is SET_NULL, so this leaves the
        # OrderItem with variant=None.
        second_variant.delete()

        other_item = order.items.exclude(variant__isnull=True).first()
        self.assertIsNotNone(other_item)
        restored_variant = other_item.variant
        stock_before_cancel = restored_variant.stock

        res = self.client.patch(
            self._detail_url(order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        restored_variant.refresh_from_db()
        self.assertEqual(
            restored_variant.stock, stock_before_cancel + other_item.quantity
        )

    def test_patch_cancel_with_deleted_product_cascades_and_skips_gracefully(self):
        """
        ProductVariant.product is on_delete=CASCADE (a variant can't
        outlive its parent product), so deleting the Product also
        deletes the ProductVariant, which in turn SET_NULLs
        OrderItem.variant. Confirms the graceful-skip check — now keyed
        on `variant`, not `product` — correctly catches this
        transitive case too, without raising.
        """
        self.variant.refresh_from_db()

        self.product.delete()  # cascades: Product -> ProductVariant

        item = self.order.items.first()
        item.refresh_from_db()
        self.assertIsNone(item.product_id)
        self.assertIsNone(item.variant_id)  # cascaded away, not just SET_NULL'd

        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        # Must not raise — gracefully skips restoration for this item.
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_patch_cancel_shipped_order_does_not_modify_stock(self):
        """
        Regression: the shipped/delivered guard clause must still run
        before any stock-restoration logic, so a rejected cancellation
        leaves variant stock untouched.
        """
        self.variant.refresh_from_db()
        stock_before = self.variant.stock

        self.order.status = Order.Status.SHIPPED
        self.order.save()

        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, stock_before)

    # ── StockMovement audit trail (Task 4.1.1.3) ─────────────────────────────

    def test_patch_cancel_creates_one_stock_movement_per_restored_variant(self):
        """
        Cancelling a pending order with variant-backed items creates
        exactly one StockMovement per restored variant, with
        reason="cancellation", a positive quantity_delta equal to the
        restored quantity, correct stock_after, actor matching the
        cancelling user, and related_order pointing at the cancelled
        order.
        """
        # setUp() already placed self.order for 2 units of self.variant
        # via checkout, which itself logged one SALE movement (Task
        # 4.1.1.2) — that movement isn't relevant here, only the new
        # CANCELLATION one this cancellation should create.
        self.variant.refresh_from_db()
        stock_before_cancel = self.variant.stock

        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.variant.refresh_from_db()

        cancellation_movements = StockMovement.objects.filter(
            related_order=self.order, reason=StockMovement.Reason.CANCELLATION
        )
        self.assertEqual(cancellation_movements.count(), 1)

        movement = cancellation_movements.get(variant=self.variant)
        self.assertEqual(movement.quantity_delta, 2)
        self.assertEqual(movement.stock_after, self.variant.stock)
        self.assertEqual(movement.stock_after, stock_before_cancel + 2)
        self.assertEqual(movement.actor_id, self.user.id)
        self.assertEqual(movement.related_order_id, self.order.id)

    def test_patch_cancel_with_deleted_variant_creates_no_movement_for_that_item(self):
        """
        Mirrors test_patch_cancel_with_deleted_variant_skips_gracefully:
        when one order item's variant was deleted (variant=None), no
        StockMovement can (or should) be logged for that item, but the
        other valid item still gets its restoration movement.
        """
        second_variant = make_variant(
            name="Backpack", slug="backpack", price="45.00", stock=10
        )
        make_cart_with_items(
            self.user,
            [
                {"variant": self.variant, "quantity": 1},
                {"variant": second_variant, "quantity": 3},
            ],
        )
        res = self.client.post("/api/orders/", VALID_PAYLOAD, format="json")
        order = Order.objects.get(pk=res.data["id"])

        second_variant_id = second_variant.id
        second_variant.delete()

        other_item = order.items.exclude(variant__isnull=True).first()
        self.assertIsNotNone(other_item)
        restored_variant = other_item.variant

        res = self.client.patch(
            self._detail_url(order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        movements = StockMovement.objects.filter(
            related_order=order, reason=StockMovement.Reason.CANCELLATION
        )
        self.assertEqual(movements.count(), 1)

        movement = movements.get()
        self.assertEqual(movement.variant_id, restored_variant.id)
        self.assertEqual(movement.quantity_delta, other_item.quantity)

        # No movement can exist for the deleted variant's id — it no
        # longer exists to be referenced at all.
        self.assertFalse(
            StockMovement.objects.filter(variant_id=second_variant_id).exists()
        )

    def test_patch_cancel_shipped_order_creates_no_stock_movements(self):
        """
        Attempting to cancel an already-shipped order (rejected with
        400 by the existing guard clause) must create ZERO
        StockMovement rows — nothing was actually restored, so nothing
        should be logged.
        """
        self.order.status = Order.Status.SHIPPED
        self.order.save()

        movements_before = StockMovement.objects.count()

        res = self.client.patch(
            self._detail_url(self.order.pk), {"status": "cancelled"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(StockMovement.objects.count(), movements_before)
        self.assertFalse(
            StockMovement.objects.filter(
                related_order=self.order, reason=StockMovement.Reason.CANCELLATION
            ).exists()
        )


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
