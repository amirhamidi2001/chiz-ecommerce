from decimal import Decimal

import pytest
from rest_framework import status

# ── URL constants ─────────────────────────────────────────────────────────────
PROFILE_URL = "/api/dashboard/profile/"
AVATAR_URL = "/api/dashboard/profile/upload-avatar/"
CHANGE_PW_URL = "/api/dashboard/change-password/"
NOTIFICATIONS_URL = "/api/dashboard/notifications/"
SUMMARY_URL = "/api/dashboard/summary/"
ADDRESSES_URL = "/api/dashboard/addresses/"
WISHLIST_URL = "/api/dashboard/wishlist/"
ORDERS_URL = "/api/dashboard/orders/"


def addr_detail(pk):
    return f"/api/dashboard/addresses/{pk}/"


def wish_detail(pk):
    return f"/api/dashboard/wishlist/{pk}/"


def order_detail(pk):
    return f"/api/dashboard/orders/{pk}/"


def review_detail(pk):
    return f"/api/dashboard/reviews/{pk}/"


# ── address payload helper ─────────────────────────────────────────────────────
def _addr_payload(**override):
    return {
        "label": "home",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "5550001111",
        "address_line": "1 Test Lane",
        "city": "Testville",
        "province": "tehran",
        "postal_code": "9000112345",
        "country": "IR",
        "is_default": False,
        **override,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ProfileView
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDashboardProfileView:

    def test_get_returns_own_profile(self, customer_client, customer):
        customer.profile.first_name = "TestFirst"
        customer.profile.save()
        res = customer_client.get(PROFILE_URL)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["first_name"] == "TestFirst"
        assert res.data["email"] == customer.email

    def test_patch_updates_name(self, customer_client, customer):
        res = customer_client.patch(
            PROFILE_URL, {"first_name": "New", "last_name": "Name"}
        )
        assert res.status_code == status.HTTP_200_OK
        customer.profile.refresh_from_db()
        assert customer.profile.first_name == "New"

    def test_unauthenticated_returns_401(self, anon_client):
        assert anon_client.get(PROFILE_URL).status_code == status.HTTP_401_UNAUTHORIZED

    def test_cannot_access_other_user_profile(self, make_user):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        user_a = make_user(email="a@example.com")
        client = APIClient()
        refresh = RefreshToken.for_user(user_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
        res = client.get(PROFILE_URL)
        assert res.data["email"] == user_a.email  # must be A's data, not B's


# ══════════════════════════════════════════════════════════════════════════════
# NotificationSettingsView
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationsView:

    def test_get_returns_notification_fields(self, customer_client):
        res = customer_client.get(NOTIFICATIONS_URL)
        assert res.status_code == status.HTTP_200_OK
        for field in ("order_updates", "promotions", "newsletter"):
            assert field in res.data

    def test_patch_toggles_newsletter(self, customer_client, customer):
        original = customer.profile.newsletter
        res = customer_client.patch(NOTIFICATIONS_URL, {"newsletter": not original})
        assert res.status_code == status.HTTP_200_OK
        customer.profile.refresh_from_db()
        assert customer.profile.newsletter == (not original)

    def test_unauthenticated_returns_401(self, anon_client):
        assert (
            anon_client.get(NOTIFICATIONS_URL).status_code
            == status.HTTP_401_UNAUTHORIZED
        )


# ══════════════════════════════════════════════════════════════════════════════
# UserSummaryView
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserSummaryView:

    def test_returns_summary_fields(self, customer_client):
        res = customer_client.get(SUMMARY_URL)
        assert res.status_code == status.HTTP_200_OK
        for field in ("total_orders", "total_spent", "wishlist_count"):
            assert field in res.data

    def test_reflects_created_order(self, customer_client, customer, make_order):
        make_order(user=customer, status="delivered", total=Decimal("75.00"))
        res = customer_client.get(SUMMARY_URL)
        assert res.data["total_orders"] >= 1
        assert res.data["total_spent"] >= 75.0


# ══════════════════════════════════════════════════════════════════════════════
# AddressViewSet
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAddressViewSet:

    def test_list_empty_for_new_user(self, customer_client):
        res = customer_client.get(ADDRESSES_URL)
        assert res.status_code == status.HTTP_200_OK
        results = res.data.get("results", res.data)
        assert len(results) == 0

    def test_create_address(self, customer_client):
        res = customer_client.post(ADDRESSES_URL, _addr_payload())
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["city"] == "Testville"

    def test_list_returns_own_addresses_only(
        self, customer_client, customer, make_user
    ):
        from dashboard.models import Address

        # Create address belonging to another user
        other = make_user(email="other@example.com")
        Address.objects.create(user=other, **{k: v for k, v in _addr_payload().items()})
        # Create one for customer
        customer_client.post(ADDRESSES_URL, _addr_payload())
        res = customer_client.get(ADDRESSES_URL)
        results = res.data.get("results", res.data)
        assert all(a["city"] == "Testville" for a in results)
        assert len(results) == 1

    def test_update_address(self, customer_client):
        create_res = customer_client.post(ADDRESSES_URL, _addr_payload())
        pk = create_res.data["id"]
        res = customer_client.patch(addr_detail(pk), {"city": "UpdatedCity"})
        assert res.status_code == status.HTTP_200_OK
        assert res.data["city"] == "UpdatedCity"

    def test_delete_address(self, customer_client):
        create_res = customer_client.post(ADDRESSES_URL, _addr_payload())
        pk = create_res.data["id"]
        res = customer_client.delete(addr_detail(pk))
        assert res.status_code == status.HTTP_204_NO_CONTENT

    def test_cannot_delete_another_users_address(self, make_user):
        from dashboard.models import Address
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        user_a = make_user(email="ua@example.com")
        user_b = make_user(email="ub@example.com")
        addr_b = Address.objects.create(
            user=user_b, **{k: v for k, v in _addr_payload().items()}
        )
        client_a = APIClient()
        refresh = RefreshToken.for_user(user_a)
        client_a.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
        res = client_a.delete(addr_detail(addr_b.pk))
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_setting_default_unsets_previous(self, customer_client):
        r1 = customer_client.post(ADDRESSES_URL, _addr_payload(is_default=True))
        # Patch first back to default to re-trigger the logic
        res = customer_client.patch(addr_detail(r1.data["id"]), {"is_default": True})
        assert res.status_code == status.HTTP_200_OK
        # Fetch list — only one should be default
        list_res = customer_client.get(ADDRESSES_URL)
        results = list_res.data.get("results", list_res.data)
        defaults = [a for a in results if a["is_default"]]
        assert len(defaults) == 1

    def test_unauthenticated_returns_401(self, anon_client):
        assert (
            anon_client.get(ADDRESSES_URL).status_code == status.HTTP_401_UNAUTHORIZED
        )


# ══════════════════════════════════════════════════════════════════════════════
# WishlistViewSet
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWishlistViewSet:

    def test_empty_wishlist(self, customer_client):
        res = customer_client.get(WISHLIST_URL)
        assert res.status_code == status.HTTP_200_OK
        results = res.data.get("results", res.data)
        assert len(results) == 0

    def test_add_product_to_wishlist(self, customer_client, make_product):
        product = make_product()
        res = customer_client.post(WISHLIST_URL, {"product_id": product.pk})
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["product"]["id"] == product.pk

    def test_duplicate_add_returns_400(self, customer_client, make_product):
        product = make_product()
        customer_client.post(WISHLIST_URL, {"product_id": product.pk})
        res = customer_client.post(WISHLIST_URL, {"product_id": product.pk})
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_remove_from_wishlist(self, customer_client, make_product):
        product = make_product()
        add_res = customer_client.post(WISHLIST_URL, {"product_id": product.pk})
        item_pk = add_res.data["id"]
        del_res = customer_client.delete(wish_detail(item_pk))
        assert del_res.status_code == status.HTTP_204_NO_CONTENT

    def test_wishlist_isolated_per_user(self, customer_client, make_user, make_product):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        product = make_product()
        other = make_user(email="other2@example.com")
        other_c = APIClient()
        refresh = RefreshToken.for_user(other)
        other_c.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
        other_c.post(WISHLIST_URL, {"product_id": product.pk})
        # customer's wishlist should be empty
        res = customer_client.get(WISHLIST_URL)
        assert len(res.data.get("results", res.data)) == 0

    def test_unauthenticated_returns_401(self, anon_client):
        assert anon_client.get(WISHLIST_URL).status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════════════
# UserOrderViewSet
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUserOrderViewSet:

    def test_list_own_orders(self, customer_client, customer, make_order):
        make_order(user=customer)
        make_order(user=customer)
        res = customer_client.get(ORDERS_URL)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] >= 2

    def test_list_excludes_other_user_orders(
        self, customer_client, make_order, make_user
    ):
        other = make_user(email="other3@example.com")
        make_order(user=other)
        res = customer_client.get(ORDERS_URL)
        assert res.data["count"] == 0

    def test_retrieve_order_detail(self, customer_client, customer, make_order):
        order = make_order(user=customer)
        res = customer_client.get(order_detail(order.pk))
        assert res.status_code == status.HTTP_200_OK
        assert res.data["order_number"] == order.order_number

    def test_cannot_retrieve_another_users_order(
        self, customer_client, make_order, make_user
    ):
        other = make_user(email="other4@example.com")
        order = make_order(user=other)
        res = customer_client.get(order_detail(order.pk))
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_filter_by_status(self, customer_client, customer, make_order):
        make_order(user=customer, status="delivered")
        make_order(user=customer, status="pending")
        res = customer_client.get(ORDERS_URL + "?status=delivered")
        results = res.data.get("results", [])
        assert all(o["status"] == "delivered" for o in results)

    def test_unauthenticated_returns_401(self, anon_client):
        assert anon_client.get(ORDERS_URL).status_code == status.HTTP_401_UNAUTHORIZED


# ══════════════════════════════════════════════════════════════════════════════
# AdminVariantAdjustStockView
# ══════════════════════════════════════════════════════════════════════════════


def adjust_stock_url(pk):
    return f"/api/dashboard/admin/variants/{pk}/adjust-stock/"


@pytest.mark.django_db
class TestAdminVariantAdjustStockView:

    def test_restock_increases_stock_and_logs_movement(
        self, admin_client, admin_user, make_variant
    ):
        from shop.models import StockMovement

        variant = make_variant(stock=10)
        res = admin_client.post(
            adjust_stock_url(variant.pk),
            {"quantity_delta": 5, "reason": "restock", "note": "New shipment"},
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.data["stock"] == 15

        variant.refresh_from_db()
        assert variant.stock == 15

        movement = StockMovement.objects.get(variant=variant)
        assert movement.reason == StockMovement.Reason.RESTOCK
        assert movement.quantity_delta == 5
        assert movement.stock_after == 15
        assert movement.actor_id == admin_user.id
        assert movement.note == "New shipment"

    def test_manual_writeoff_decreases_stock_and_logs_movement(
        self, admin_client, admin_user, make_variant
    ):
        from shop.models import StockMovement

        variant = make_variant(stock=10)
        res = admin_client.post(
            adjust_stock_url(variant.pk),
            {"quantity_delta": -3, "reason": "manual", "note": "Damaged in storage"},
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.data["stock"] == 7

        variant.refresh_from_db()
        assert variant.stock == 7

        movement = StockMovement.objects.get(variant=variant)
        assert movement.reason == StockMovement.Reason.MANUAL
        assert movement.quantity_delta == -3
        assert movement.stock_after == 7
        assert movement.actor_id == admin_user.id

    def test_adjustment_taking_stock_negative_is_rejected(
        self, admin_client, make_variant
    ):
        from shop.models import StockMovement

        variant = make_variant(stock=5)
        res = admin_client.post(
            adjust_stock_url(variant.pk),
            {"quantity_delta": -10, "reason": "manual"},
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST

        variant.refresh_from_db()
        assert variant.stock == 5
        assert not StockMovement.objects.filter(variant=variant).exists()

    def test_zero_quantity_delta_rejected_by_serializer(
        self, admin_client, make_variant
    ):
        variant = make_variant(stock=10)
        res = admin_client.post(
            adjust_stock_url(variant.pk),
            {"quantity_delta": 0, "reason": "manual"},
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "quantity_delta" in res.data

        variant.refresh_from_db()
        assert variant.stock == 10

    def test_disallowed_reason_is_rejected_by_serializer(
        self, admin_client, make_variant
    ):
        """
        An admin must not be able to forge a fake sale/cancellation/
        expiry movement through this manual-adjustment endpoint — only
        MANUAL/RESTOCK are valid here.
        """
        from shop.models import StockMovement

        variant = make_variant(stock=10)
        res = admin_client.post(
            adjust_stock_url(variant.pk),
            {"quantity_delta": 5, "reason": "sale"},
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "reason" in res.data

        variant.refresh_from_db()
        assert variant.stock == 10
        assert not StockMovement.objects.filter(variant=variant).exists()

    def test_non_admin_customer_gets_403(self, customer_client, make_variant):
        variant = make_variant(stock=10)
        res = customer_client.post(
            adjust_stock_url(variant.pk),
            {"quantity_delta": 5, "reason": "restock"},
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN

        variant.refresh_from_db()
        assert variant.stock == 10


# ══════════════════════════════════════════════════════════════════════════════
# AdminOrderViewSet — status state machine + shared cancellation
# ══════════════════════════════════════════════════════════════════════════════


def admin_order_url(pk):
    return f"/api/dashboard/admin/orders/{pk}/"


@pytest.fixture
def make_order_with_items(make_order, make_variant):
    """
    Factory: order in `status` containing one OrderItem per (variant, qty).
    Mirrors checkout, which has already decremented stock — each variant's
    stock is reduced by qty so cancellation has something real to restore.
    """
    from order.models import OrderItem

    def _make(items, status="pending", user=None):
        order = make_order(status=status, user=user)
        for variant, qty in items:
            variant.stock -= qty
            variant.save(update_fields=["stock"])
            OrderItem.objects.create(
                order=order,
                product=variant.product,
                variant=variant,
                product_name=variant.product.name,
                product_slug=f"slug-{variant.pk}",
                variant_sku=variant.sku,
                unit_price=variant.price,
                quantity=qty,
            )
        return order

    return _make


@pytest.mark.django_db
class TestAdminOrderStatusTransitions:

    def test_invalid_transition_delivered_to_pending_returns_400(
        self, admin_client, make_order
    ):
        order = make_order(status="delivered")
        res = admin_client.patch(
            admin_order_url(order.pk), {"status": "pending"}, format="json"
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot change status from 'delivered' to 'pending'" in str(
            res.data["status"]
        )
        order.refresh_from_db()
        assert order.status == "delivered"

    def test_invalid_transition_cancelled_to_shipped_returns_400(
        self, admin_client, make_order
    ):
        order = make_order(status="cancelled")
        res = admin_client.patch(
            admin_order_url(order.pk), {"status": "shipped"}, format="json"
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        order.refresh_from_db()
        assert order.status == "cancelled"

    def test_unknown_status_value_still_rejected(self, admin_client, make_order):
        order = make_order(status="pending")
        res = admin_client.patch(
            admin_order_url(order.pk), {"status": "teleported"}, format="json"
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        order.refresh_from_db()
        assert order.status == "pending"

    def test_valid_transition_processing_to_shipped_succeeds(
        self, admin_client, make_order
    ):
        order = make_order(status="processing")
        res = admin_client.patch(
            admin_order_url(order.pk), {"status": "shipped"}, format="json"
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.data["status"] == "shipped"
        order.refresh_from_db()
        assert order.status == "shipped"

    def test_processing_to_delivered_allowed_for_carrier_confirmed_delivery(
        self, admin_client, make_order
    ):
        # shipping.tasks.poll_shipment_tracking performs this exact
        # transition in production, so the map must allow it.
        order = make_order(status="processing")
        res = admin_client.patch(
            admin_order_url(order.pk), {"status": "delivered"}, format="json"
        )
        assert res.status_code == status.HTTP_200_OK

    def test_non_admin_cannot_change_status(self, customer_client, make_order):
        order = make_order(status="pending")
        res = customer_client.patch(
            admin_order_url(order.pk), {"status": "processing"}, format="json"
        )
        assert res.status_code == status.HTTP_403_FORBIDDEN
        order.refresh_from_db()
        assert order.status == "pending"


@pytest.mark.django_db
class TestAdminOrderCancellation:

    @pytest.mark.parametrize("start_status", ["pending", "processing"])
    def test_admin_cancel_restores_stock_and_logs_movements_with_actor(
        self,
        admin_client,
        admin_user,
        make_variant,
        make_order_with_items,
        start_status,
    ):
        from shop.models import StockMovement

        v1 = make_variant(stock=10)
        v2 = make_variant(stock=20)
        order = make_order_with_items([(v1, 3), (v2, 5)], status=start_status)

        v1.refresh_from_db()
        v2.refresh_from_db()
        assert (v1.stock, v2.stock) == (7, 15)  # reserved at "checkout"

        res = admin_client.patch(
            admin_order_url(order.pk), {"status": "cancelled"}, format="json"
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.data["status"] == "cancelled"

        order.refresh_from_db()
        v1.refresh_from_db()
        v2.refresh_from_db()
        assert order.status == "cancelled"
        assert (v1.stock, v2.stock) == (10, 20)

        movements = StockMovement.objects.filter(
            related_order=order, reason=StockMovement.Reason.CANCELLATION
        )
        assert movements.count() == 2
        m1 = movements.get(variant=v1)
        m2 = movements.get(variant=v2)
        assert (m1.quantity_delta, m1.stock_after) == (3, 10)
        assert (m2.quantity_delta, m2.stock_after) == (5, 20)
        assert m1.actor_id == admin_user.id
        assert m2.actor_id == admin_user.id

    def test_admin_cancel_shipped_order_rejected_and_stock_untouched(
        self, admin_client, make_variant, make_order_with_items
    ):
        from shop.models import StockMovement

        variant = make_variant(stock=10)
        order = make_order_with_items([(variant, 4)], status="shipped")

        res = admin_client.patch(
            admin_order_url(order.pk), {"status": "cancelled"}, format="json"
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        order.refresh_from_db()
        variant.refresh_from_db()
        assert order.status == "shipped"
        assert variant.stock == 6
        assert not StockMovement.objects.filter(related_order=order).exists()

    def test_resubmitting_cancelled_status_is_noop_and_does_not_double_restore(
        self, admin_client, make_variant, make_order_with_items
    ):
        from shop.models import StockMovement

        variant = make_variant(stock=10)
        order = make_order_with_items([(variant, 4)], status="pending")

        first = admin_client.patch(
            admin_order_url(order.pk), {"status": "cancelled"}, format="json"
        )
        assert first.status_code == status.HTTP_200_OK
        variant.refresh_from_db()
        assert variant.stock == 10

        second = admin_client.patch(
            admin_order_url(order.pk), {"status": "cancelled"}, format="json"
        )
        assert second.status_code == status.HTTP_200_OK

        variant.refresh_from_db()
        assert variant.stock == 10  # not 14
        assert (
            StockMovement.objects.filter(
                related_order=order, reason=StockMovement.Reason.CANCELLATION
            ).count()
            == 1
        )

    def test_noop_resubmission_of_non_cancelled_status_succeeds(
        self, admin_client, make_order
    ):
        order = make_order(status="processing")
        res = admin_client.patch(
            admin_order_url(order.pk), {"status": "processing"}, format="json"
        )
        assert res.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        assert order.status == "processing"

    def test_cancel_order_service_is_idempotent_for_customer_path_too(
        self, customer_client, make_variant, make_order_with_items
    ):
        # Pre-refactor, a customer re-cancelling an already-cancelled order
        # restored stock a second time; the shared service must not.
        variant = make_variant(stock=10)
        order = make_order_with_items([(variant, 4)], status="pending")
        url = f"/api/orders/{order.pk}/"

        for _ in range(2):
            res = customer_client.patch(url, {"status": "cancelled"}, format="json")
            assert res.status_code == status.HTTP_200_OK

        variant.refresh_from_db()
        assert variant.stock == 10


# ══════════════════════════════════════════════════════════════════════════════
# AdminOrderViewSet — CSV export
# ══════════════════════════════════════════════════════════════════════════════

EXPORT_URL = "/api/dashboard/admin/orders/export_csv/"
EXPORT_HEADER = [
    "order_number", "created_at", "status", "first_name", "last_name",
    "email", "phone", "shipping_city", "shipping_state", "shipping_country",
    "payment_method", "subtotal", "shipping_cost", "tax", "discount", "total",
]  # fmt: skip


def read_csv(response):
    """Consume a streaming CSV response -> list of rows (BOM stripped)."""
    import csv
    import io

    body = b"".join(response.streaming_content).decode("utf-8-sig")
    return list(csv.reader(io.StringIO(body)))


def export_rows(response):
    """Rows as dicts keyed by header, keyed again by order_number."""
    rows = read_csv(response)
    assert rows[0] == EXPORT_HEADER
    return {r[0]: dict(zip(rows[0], r)) for r in rows[1:]}


@pytest.mark.django_db
class TestAdminOrderCsvExport:

    def test_returns_streamed_csv_with_header_and_one_row_per_order(
        self, admin_client, make_order
    ):
        from order.models import Order

        o1 = make_order(status="delivered", total=Decimal("120.50"))
        o2 = make_order(status="pending", total=Decimal("30.00"))
        Order.objects.filter(pk=o1.pk).update(
            first_name="Alice", last_name="Rahimi", email="alice@example.com",
            phone="09121111111", shipping_city="Tehran", shipping_state="tehran",
            shipping_country="IR", payment_method="paypal",
            subtotal=Decimal("100.00"), shipping_cost=Decimal("15.50"),
            tax=Decimal("10.00"), discount=Decimal("5.00"),
        )  # fmt: skip

        res = admin_client.get(EXPORT_URL)

        assert res.status_code == 200
        assert res.streaming is True
        assert res["Content-Type"].startswith("text/csv")
        rows = export_rows(res)
        assert set(rows) == {o1.order_number, o2.order_number}

        row = rows[o1.order_number]
        assert row["status"] == "delivered"
        assert row["first_name"] == "Alice"
        assert row["last_name"] == "Rahimi"
        assert row["email"] == "alice@example.com"
        assert row["phone"] == "09121111111"
        assert row["shipping_city"] == "Tehran"
        assert row["shipping_state"] == "tehran"
        assert row["shipping_country"] == "IR"
        assert row["payment_method"] == "paypal"
        assert Decimal(row["subtotal"]) == Decimal("100.00")
        assert Decimal(row["shipping_cost"]) == Decimal("15.50")
        assert Decimal(row["tax"]) == Decimal("10.00")
        assert Decimal(row["discount"]) == Decimal("5.00")
        assert Decimal(row["total"]) == Decimal("120.50")
        # ISO-8601, parseable, timezone-aware
        o1.refresh_from_db()
        assert row["created_at"] == o1.created_at.isoformat()

    def test_empty_result_is_just_the_header(self, admin_client):
        res = admin_client.get(EXPORT_URL)
        assert res.status_code == 200
        assert read_csv(res) == [EXPORT_HEADER]

    def test_status_filter_limits_rows(self, admin_client, make_order):
        d1 = make_order(status="delivered")
        d2 = make_order(status="delivered")
        make_order(status="pending")
        make_order(status="cancelled")

        res = admin_client.get(EXPORT_URL, {"status": "delivered"})

        assert set(export_rows(res)) == {d1.order_number, d2.order_number}

    def test_date_range_search_and_ordering_are_respected(
        self, admin_client, make_order
    ):
        from datetime import datetime
        from datetime import timezone as tz

        from order.models import Order

        old = make_order()
        mid = make_order()
        new = make_order()
        for order, day in ((old, 1), (mid, 15), (new, 28)):
            Order.objects.filter(pk=order.pk).update(
                created_at=datetime(2026, 1, day, 12, tzinfo=tz.utc)
            )

        res = admin_client.get(
            EXPORT_URL, {"date_from": "2026-01-10", "date_to": "2026-01-31"}
        )
        assert set(export_rows(res)) == {mid.order_number, new.order_number}

        res = admin_client.get(EXPORT_URL, {"search": old.order_number})
        assert set(export_rows(res)) == {old.order_number}

        res = admin_client.get(EXPORT_URL, {"ordering": "created_at"})
        assert [r[0] for r in read_csv(res)[1:]] == [
            old.order_number, mid.order_number, new.order_number,
        ]  # fmt: skip

    def test_export_is_not_paginated(self, admin_client, make_order):
        # DashboardPagination.page_size is 10; the export must return all.
        numbers = {make_order().order_number for _ in range(25)}
        assert set(export_rows(admin_client.get(EXPORT_URL))) == numbers

    def test_query_count_does_not_grow_with_row_count(self, admin_client, make_order):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        make_order()
        make_order()
        with CaptureQueriesContext(connection) as small:
            read_csv(admin_client.get(EXPORT_URL))
        for _ in range(25):
            make_order()
        with CaptureQueriesContext(connection) as large:
            read_csv(admin_client.get(EXPORT_URL))
        assert len(large) == len(small)

    def test_invalid_filter_value_is_a_400_not_a_broken_download(self, admin_client):
        res = admin_client.get(EXPORT_URL, {"date_from": "not-a-date"})
        assert res.status_code == 400
        assert not res.streaming

    @pytest.mark.parametrize("accept", ["text/csv", "application/json", "*/*"])
    def test_accept_header_variants(self, admin_client, make_order, accept):
        make_order()
        res = admin_client.get(EXPORT_URL, HTTP_ACCEPT=accept)
        assert res.status_code == 200

    def test_content_disposition_triggers_download_with_dated_filename(
        self, admin_client
    ):
        from django.utils import timezone

        res = admin_client.get(EXPORT_URL)
        today = timezone.now().strftime("%Y-%m-%d")
        assert res["Content-Disposition"] == (
            f'attachment; filename="orders_export_{today}.csv"'
        )

    def test_utf8_bom_and_persian_text_round_trip(self, admin_client, make_order):
        from order.models import Order

        order = make_order()
        Order.objects.filter(pk=order.pk).update(
            first_name="علی", last_name="رحیمی", shipping_city="تهران"
        )
        res = admin_client.get(EXPORT_URL)
        raw = b"".join(res.streaming_content)
        assert raw.startswith(b"\xef\xbb\xbf")  # BOM, so Excel reads UTF-8
        rows = {r[0]: r for r in read_csv_bytes(raw)}
        assert rows[order.order_number][3:5] == ["علی", "رحیمی"]
        assert rows[order.order_number][7] == "تهران"

    def test_spreadsheet_formulas_in_customer_text_are_neutralised(
        self, admin_client, make_order
    ):
        from order.models import Order

        evil = make_order()
        plain = make_order()
        Order.objects.filter(pk=evil.pk).update(
            first_name='=HYPERLINK("http://evil.example","x")',
            last_name="@SUM(1+1)",
            email="-2+3@example.com",
            phone="+98 912 123 4567",  # a legitimate phone must stay untouched
            shipping_city="+cmd|' /C calc'!A0",
        )
        rows = export_rows(admin_client.get(EXPORT_URL))
        row = rows[evil.order_number]
        assert row["first_name"].startswith("'=")
        assert row["last_name"].startswith("'@")
        assert row["email"].startswith("'-")
        assert row["shipping_city"].startswith("'+")
        assert row["phone"] == "+98 912 123 4567"
        assert rows[plain.order_number]["first_name"] == "Test"

    # ── Permissions ──────────────────────────────────────────────────────────

    def test_customer_is_forbidden(self, customer_client, make_order):
        make_order()
        res = customer_client.get(EXPORT_URL)
        assert res.status_code == 403
        assert not res.streaming

    def test_customer_is_forbidden_even_with_csv_accept_header(self, customer_client):
        res = customer_client.get(EXPORT_URL, HTTP_ACCEPT="text/csv")
        assert res.status_code == 403

    def test_anonymous_is_unauthorised(self, db):
        from rest_framework.test import APIClient

        assert APIClient().get(EXPORT_URL).status_code == 401

    def test_superuser_can_export(self, superuser_client, make_order):
        order = make_order()
        assert order.order_number in export_rows(superuser_client.get(EXPORT_URL))


def read_csv_bytes(raw):
    import csv
    import io

    return list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))


# ══════════════════════════════════════════════════════════════════════════════
# AdminCouponViewSet  (Task 9.1.1.8)
# ══════════════════════════════════════════════════════════════════════════════

COUPONS_URL = "/api/dashboard/admin/coupons/"


def coupon_detail(pk):
    return f"/api/dashboard/admin/coupons/{pk}/"


def _coupon_payload(**override):
    from datetime import timedelta

    from django.utils import timezone

    now = timezone.now()
    return {
        "code": "SUMMER20",
        "discount_type": "percent",
        "value": "20.00",
        "min_order_amount": "0.00",
        "max_uses": None,
        "uses_per_user": 1,
        "valid_from": (now - timedelta(days=1)).isoformat(),
        "valid_until": (now + timedelta(days=30)).isoformat(),
        "is_active": True,
        "categories": [],
        "products": [],
        **override,
    }


@pytest.fixture
def make_coupon(db):
    from promotions.tests.factories import make_saved_coupon

    _counter = [0]

    def _make(**overrides):
        _counter[0] += 1
        overrides.setdefault("code", f"CODE{_counter[0]}")
        return make_saved_coupon(**overrides)

    return _make


@pytest.mark.django_db
class TestAdminCouponCrud:
    """Full create / list / retrieve / update / deactivate cycle as an admin."""

    def test_full_crud_cycle(self, admin_client, make_category, make_product):
        category = make_category("Skincare")
        product = make_product(name="Serum")

        # create
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(categories=[category.id], products=[product.id]),
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED, res.data
        coupon_id = res.data["id"]
        assert res.data["code"] == "SUMMER20"
        assert res.data["categories"] == [category.id]
        assert res.data["products"] == [product.id]
        assert res.data["categories_detail"] == [
            {"id": category.id, "name": "Skincare"}
        ]
        assert res.data["products_detail"] == [{"id": product.id, "name": "Serum"}]
        assert res.data["created_at"]

        # list (paginated)
        res = admin_client.get(COUPONS_URL)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 1
        assert [c["id"] for c in res.data["results"]] == [coupon_id]

        # retrieve
        res = admin_client.get(coupon_detail(coupon_id))
        assert res.status_code == status.HTTP_200_OK
        assert res.data["code"] == "SUMMER20"
        assert res.data["is_active"] is True

        # update
        res = admin_client.patch(
            coupon_detail(coupon_id),
            {"value": "25.00", "max_uses": 100},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK, res.data
        assert res.data["value"] == "25.00"
        assert res.data["max_uses"] == 100
        assert res.data["code"] == "SUMMER20"  # untouched by a partial update

        # deactivate
        res = admin_client.patch(
            coupon_detail(coupon_id), {"is_active": False}, format="json"
        )
        assert res.status_code == status.HTTP_200_OK, res.data
        assert res.data["is_active"] is False

        from promotions.models import Coupon

        coupon = Coupon.objects.get(pk=coupon_id)
        assert coupon.is_active is False
        assert coupon.value == Decimal("25.00")

    def test_deactivated_coupon_is_rejected_by_validate_coupon(
        self, admin_client, customer, make_coupon
    ):
        from promotions.services import validate_coupon
        from promotions.tests.factories import make_priced_cart

        coupon = make_coupon(code="LIVE")
        cart = make_priced_cart(customer, "100.00")
        assert validate_coupon("LIVE", customer, cart).valid

        admin_client.patch(
            coupon_detail(coupon.id), {"is_active": False}, format="json"
        )

        result = validate_coupon("LIVE", customer, cart)
        assert not result.valid
        assert result.error == "This coupon is no longer active."

    def test_superuser_has_access(self, superuser_client):
        assert superuser_client.get(COUPONS_URL).status_code == status.HTTP_200_OK

    def test_restrictions_can_be_cleared(
        self, admin_client, make_coupon, make_category
    ):
        coupon = make_coupon()
        coupon.categories.add(make_category("Skincare"))

        res = admin_client.patch(
            coupon_detail(coupon.id), {"categories": []}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK, res.data
        assert res.data["categories"] == []
        assert res.data["categories_detail"] == []

    def test_search_by_code(self, admin_client, make_coupon):
        make_coupon(code="SUMMER20")
        make_coupon(code="WINTER10")

        res = admin_client.get(COUPONS_URL, {"search": "summer"})

        assert [c["code"] for c in res.data["results"]] == ["SUMMER20"]

    def test_default_ordering_is_newest_first_and_overridable(
        self, admin_client, make_coupon
    ):
        first = make_coupon(code="FIRST")
        second = make_coupon(code="SECOND")

        res = admin_client.get(COUPONS_URL)
        assert [c["id"] for c in res.data["results"]] == [second.id, first.id]

        res = admin_client.get(COUPONS_URL, {"ordering": "created_at"})
        assert [c["id"] for c in res.data["results"]] == [first.id, second.id]

    def test_list_query_count_does_not_grow_with_restrictions(
        self, admin_client, make_coupon, make_category, make_product
    ):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def count_list_queries():
            with CaptureQueriesContext(connection) as ctx:
                assert admin_client.get(COUPONS_URL).status_code == 200
            return len(ctx)

        first = make_coupon()
        first.categories.add(make_category())
        first.products.add(make_product())
        baseline = count_list_queries()

        for _ in range(5):
            coupon = make_coupon()
            coupon.categories.add(make_category(), make_category())
            coupon.products.add(make_product(), make_product())

        assert count_list_queries() == baseline


@pytest.mark.django_db
class TestAdminCouponValidation:
    """The API must enforce the Coupon.clean() rules itself."""

    @pytest.mark.parametrize("value", ["0", "-5", "100.01", "150"])
    def test_percent_value_outside_range_rejected(self, admin_client, value):
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(discount_type="percent", value=value),
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "value" in res.data

    def test_percent_value_of_exactly_100_accepted(self, admin_client):
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(discount_type="percent", value="100"),
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED, res.data

    @pytest.mark.parametrize("value", ["0", "-10"])
    def test_fixed_value_not_positive_rejected(self, admin_client, value):
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(discount_type="fixed", value=value),
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "value" in res.data

    def test_valid_until_not_after_valid_from_rejected(self, admin_client):
        from django.utils import timezone

        now = timezone.now().isoformat()
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(valid_from=now, valid_until=now),
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "valid_until" in res.data

    def test_partial_update_is_validated_against_stored_fields(
        self, admin_client, make_coupon
    ):
        from datetime import timedelta

        from django.utils import timezone

        coupon = make_coupon()  # valid_from = yesterday
        # PATCH sends only valid_until, earlier than the STORED valid_from.
        res = admin_client.patch(
            coupon_detail(coupon.id),
            {"valid_until": (timezone.now() - timedelta(days=5)).isoformat()},
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "valid_until" in res.data

    def test_changing_type_to_percent_rechecks_the_stored_value(
        self, admin_client, make_coupon
    ):
        from decimal import Decimal

        coupon = make_coupon(discount_type="fixed", value=Decimal("500.00"))
        res = admin_client.patch(
            coupon_detail(coupon.id), {"discount_type": "percent"}, format="json"
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "value" in res.data

    @pytest.mark.parametrize(
        "field,bad",
        [
            ("min_order_amount", "-1.00"),
            ("uses_per_user", 0),
            ("max_uses", 0),
        ],
    )
    def test_nonsensical_limits_rejected(self, admin_client, field, bad):
        res = admin_client.post(
            COUPONS_URL, _coupon_payload(**{field: bad}), format="json"
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert field in res.data

    def test_missing_required_fields_rejected(self, admin_client):
        res = admin_client.post(COUPONS_URL, {"code": "X"}, format="json")
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        for field in ("discount_type", "value", "valid_from", "valid_until"):
            assert field in res.data


@pytest.mark.django_db
class TestAdminCouponCode:
    def test_code_is_normalised_to_uppercase(self, admin_client):
        res = admin_client.post(
            COUPONS_URL, _coupon_payload(code="  summer20 "), format="json"
        )
        assert res.status_code == status.HTTP_201_CREATED, res.data
        assert res.data["code"] == "SUMMER20"

    def test_case_variant_of_existing_code_is_a_400_not_a_500(
        self, admin_client, make_coupon
    ):
        make_coupon(code="SUMMER20")
        res = admin_client.post(
            COUPONS_URL, _coupon_payload(code="summer20"), format="json"
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "code" in res.data

    def test_resaving_a_coupons_own_code_is_allowed(self, admin_client, make_coupon):
        coupon = make_coupon(code="SUMMER20")
        res = admin_client.patch(
            coupon_detail(coupon.id), {"code": "summer20"}, format="json"
        )
        assert res.status_code == status.HTTP_200_OK, res.data

    def test_renaming_to_another_coupons_code_is_rejected(
        self, admin_client, make_coupon
    ):
        make_coupon(code="TAKEN")
        coupon = make_coupon(code="MINE")
        res = admin_client.patch(
            coupon_detail(coupon.id), {"code": "taken"}, format="json"
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "code" in res.data


@pytest.mark.django_db
class TestAdminCouponDelete:
    def test_unused_coupon_can_be_deleted(self, admin_client, make_coupon):
        coupon = make_coupon()
        res = admin_client.delete(coupon_detail(coupon.id))
        assert res.status_code == status.HTTP_204_NO_CONTENT

        from promotions.models import Coupon

        assert not Coupon.objects.filter(pk=coupon.pk).exists()

    def test_redeemed_coupon_cannot_be_deleted(
        self, admin_client, make_coupon, customer
    ):
        from promotions.models import Coupon, CouponRedemption
        from promotions.tests.factories import make_completed_redemption

        coupon = make_coupon()
        make_completed_redemption(coupon, customer)

        res = admin_client.delete(coupon_detail(coupon.id))

        assert res.status_code == status.HTTP_409_CONFLICT
        assert "Deactivate" in res.data["detail"]
        assert Coupon.objects.filter(pk=coupon.pk).exists()
        assert CouponRedemption.objects.filter(coupon=coupon).count() == 1


@pytest.mark.django_db
class TestAdminCouponPermissions:
    def test_customer_gets_403_on_every_endpoint(self, customer_client, make_coupon):
        coupon = make_coupon()
        calls = [
            customer_client.get(COUPONS_URL),
            customer_client.post(COUPONS_URL, _coupon_payload(), format="json"),
            customer_client.get(coupon_detail(coupon.id)),
            customer_client.patch(
                coupon_detail(coupon.id), {"is_active": False}, format="json"
            ),
            customer_client.delete(coupon_detail(coupon.id)),
        ]
        assert [r.status_code for r in calls] == [status.HTTP_403_FORBIDDEN] * 5

        coupon.refresh_from_db()
        assert coupon.is_active is True  # the forbidden PATCH changed nothing

    def test_forbidden_create_and_delete_leave_data_untouched(
        self, customer_client, make_coupon
    ):
        from promotions.models import Coupon

        coupon = make_coupon()
        customer_client.post(COUPONS_URL, _coupon_payload(code="NEW"), format="json")
        customer_client.delete(coupon_detail(coupon.id))
        assert list(Coupon.objects.values_list("code", flat=True)) == [coupon.code]

    def test_anonymous_gets_401(self, anon_client, make_coupon):
        coupon = make_coupon()
        assert anon_client.get(COUPONS_URL).status_code == status.HTTP_401_UNAUTHORIZED
        assert (
            anon_client.patch(
                coupon_detail(coupon.id), {"is_active": False}, format="json"
            ).status_code
            == status.HTTP_401_UNAUTHORIZED
        )
