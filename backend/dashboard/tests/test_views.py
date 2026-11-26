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
        make_order(user=customer, status="delivered", total=750_000)
        res = customer_client.get(SUMMARY_URL)
        assert res.data["total_orders"] >= 1
        assert res.data["total_spent"] >= 750_000


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

    def test_anonymous_get_returns_200_with_empty_list(self, anon_client):
        """
        Replaces test_unauthenticated_returns_401: the wishlist is now
        AllowAny (guests get a session-based wishlist), so that test's
        premise is exactly what this task removes. Full guest coverage
        lives in test_wishlist_guest.py.
        """
        res = anon_client.get(WISHLIST_URL)
        assert res.status_code == status.HTTP_200_OK
        assert len(res.data.get("results", res.data)) == 0


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

    def test_detail_includes_shipment_for_shipped_order(
        self, customer_client, customer, make_order
    ):
        """Task 14.3.3.1: the account order modal reads this endpoint, so the Task 7.2.2.3
        tracking widget needs `shipment` here (it used to be missing -> always 'Not yet
        shipped')."""
        from shipping.models import Shipment, ShippingCarrier

        order = make_order(user=customer, status="shipped")
        carrier, _ = ShippingCarrier.objects.get_or_create(
            code="post", defaults={"display_name": "Iran Post", "is_active": True}
        )
        Shipment.objects.create(
            order=order,
            carrier=carrier,
            tracking_number="RR1234567IR",
            status=Shipment.Status.IN_TRANSIT,
        )
        res = customer_client.get(order_detail(order.pk))
        assert res.status_code == status.HTTP_200_OK
        assert res.data["shipment"]["tracking_number"] == "RR1234567IR"
        assert res.data["shipment"]["status"] == "in_transit"

    def test_detail_shipment_is_null_without_shipment(
        self, customer_client, customer, make_order
    ):
        order = make_order(user=customer)
        res = customer_client.get(order_detail(order.pk))
        assert res.status_code == status.HTTP_200_OK
        assert res.data["shipment"] is None

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
    "payment_method", "subtotal_rial", "shipping_cost_rial", "tax_rial",
    "discount_rial", "total_rial",
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

        o1 = make_order(status="delivered", total=1_205_000)
        o2 = make_order(status="pending", total=300_000)
        Order.objects.filter(pk=o1.pk).update(
            first_name="Alice", last_name="Rahimi", email="alice@example.com",
            phone="09121111111", shipping_city="Tehran", shipping_state="tehran",
            shipping_country="IR", payment_method="paypal",
            subtotal=1_000_000, shipping_cost=155_000,
            tax=100_000, discount=50_000,
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
        assert int(row["subtotal_rial"]) == 1_000_000
        assert int(row["shipping_cost_rial"]) == 155_000
        assert int(row["tax_rial"]) == 100_000
        assert int(row["discount_rial"]) == 50_000
        assert int(row["total_rial"]) == 1_205_000
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
        # Two explicit columns (ADR 0001 §7.3): a percentage XOR a Rial amount.
        "percent_off": "20.00",
        "fixed_amount": None,
        "min_order_amount": 0,
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
            {"percent_off": "25.00", "max_uses": 100},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK, res.data
        assert res.data["percent_off"] == "25.00"
        assert res.data["fixed_amount"] is None
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
        assert coupon.percent_off == Decimal("25.00")

    def test_deactivated_coupon_is_rejected_by_validate_coupon(
        self, admin_client, customer, make_coupon
    ):
        from promotions.services import validate_coupon
        from promotions.tests.factories import make_priced_cart

        coupon = make_coupon(code="LIVE")
        cart = make_priced_cart(customer, 1_000_000)
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

    @pytest.mark.parametrize("percent", ["0", "-5", "100.01", "150"])
    def test_percent_outside_range_rejected(self, admin_client, percent):
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(discount_type="percent", percent_off=percent),
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "percent_off" in res.data

    def test_percent_of_exactly_100_accepted(self, admin_client):
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(discount_type="percent", percent_off="100"),
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED, res.data

    @pytest.mark.parametrize("amount", [0, -10])
    def test_fixed_amount_not_positive_rejected(self, admin_client, amount):
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(
                discount_type="fixed", percent_off=None, fixed_amount=amount
            ),
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "fixed_amount" in res.data

    def test_fixed_coupon_round_trips_a_rial_integer(self, admin_client):
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(
                discount_type="fixed",
                percent_off=None,
                fixed_amount=500_000,
                min_order_amount=2_000_000,
            ),
            format="json",
        )
        assert res.status_code == status.HTTP_201_CREATED, res.data
        # JSON integers (Rial), never strings
        assert res.data["fixed_amount"] == 500_000
        assert res.data["min_order_amount"] == 2_000_000
        assert res.data["percent_off"] is None

    @pytest.mark.parametrize("amount", [500_005, 100_000_000_010])
    def test_fixed_amount_must_be_a_whole_toman_within_the_cap(
        self, admin_client, amount
    ):
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(
                discount_type="fixed", percent_off=None, fixed_amount=amount
            ),
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "fixed_amount" in res.data

    def test_a_percent_coupon_may_not_also_carry_a_fixed_amount(self, admin_client):
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(discount_type="percent", fixed_amount=100_000),
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "fixed_amount" in res.data

    def test_a_fixed_coupon_may_not_also_carry_a_percentage(self, admin_client):
        res = admin_client.post(
            COUPONS_URL,
            _coupon_payload(
                discount_type="fixed", percent_off="10.00", fixed_amount=100_000
            ),
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "percent_off" in res.data

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

        coupon = make_coupon(discount_type="fixed", fixed_amount=5_000_000)
        res = admin_client.patch(
            coupon_detail(coupon.id), {"discount_type": "percent"}, format="json"
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "percent_off" in res.data

    @pytest.mark.parametrize(
        "field,bad",
        [
            ("min_order_amount", -10),
            ("min_order_amount", 5),
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
        for field in ("discount_type", "valid_from", "valid_until"):
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


# ═══════════════════════════════════════════════════════════════════════════════
# Admin review moderation queue
# ═══════════════════════════════════════════════════════════════════════════════

ADMIN_REVIEWS_URL = "/api/dashboard/admin/reviews/"


def admin_review_detail(pk):
    return f"/api/dashboard/admin/reviews/{pk}/"


@pytest.fixture
def make_review(db, make_user, make_product):
    from shop.models import Review

    def _make(product=None, rating=5, is_approved=False, user=None, **extra):
        user = user or make_user()
        return Review.objects.create(
            product=product or make_product(),
            user=user,
            name=extra.pop("name", "Reviewer"),
            rating=rating,
            headline=extra.pop("headline", "Headline"),
            comment=extra.pop("comment", "Original comment"),
            is_approved=is_approved,
            **extra,
        )

    return _make


class TestAdminReviewModeration:
    def test_status_filter_pending_and_approved(self, admin_client, make_review):
        pending = make_review(is_approved=False)
        approved = make_review(is_approved=True)

        def ids(query):
            res = admin_client.get(ADMIN_REVIEWS_URL + query)
            assert res.status_code == status.HTTP_200_OK
            return {r["id"] for r in res.data["results"]}

        assert ids("?status=pending") == {pending.id}
        assert ids("?status=approved") == {approved.id}
        assert ids("") == {pending.id, approved.id}

    def test_list_exposes_moderation_fields(self, admin_client, make_review, make_user):
        reviewer = make_user(email="reviewer@example.com")
        make_review(user=reviewer, is_verified_purchase=True)

        row = admin_client.get(ADMIN_REVIEWS_URL).data["results"][0]

        assert row["user_email"] == "reviewer@example.com"
        assert row["is_approved"] is False
        assert row["is_verified_purchase"] is True
        assert "product_name" in row

    def test_approving_a_pending_review_updates_product_rating_and_count(
        self, admin_client, make_review, make_product
    ):
        from shop.services import refresh_product_review_stats

        product = make_product()
        make_review(product=product, rating=5, is_approved=True)
        pending = make_review(product=product, rating=2, is_approved=False)
        refresh_product_review_stats(product)
        product.refresh_from_db()
        assert (product.reviews_count, product.rating) == (1, 5.0)

        res = admin_client.patch(
            admin_review_detail(pending.id), {"is_approved": True}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK
        pending.refresh_from_db()
        assert pending.is_approved is True
        product.refresh_from_db()
        assert product.reviews_count == 2
        assert product.rating == 3.5  # (5 + 2) / 2

    def test_unapproving_removes_review_from_product_rating(
        self, admin_client, make_review, make_product
    ):
        from shop.services import refresh_product_review_stats

        product = make_product()
        make_review(product=product, rating=4, is_approved=True)
        bad = make_review(product=product, rating=1, is_approved=True)
        refresh_product_review_stats(product)

        admin_client.patch(
            admin_review_detail(bad.id), {"is_approved": False}, format="json"
        )

        product.refresh_from_db()
        assert product.reviews_count == 1
        assert product.rating == 4.0

    def test_deleting_an_approved_review_updates_product_rating(
        self, admin_client, make_review, make_product
    ):
        from shop.services import refresh_product_review_stats

        product = make_product()
        make_review(product=product, rating=4, is_approved=True)
        spam = make_review(product=product, rating=1, is_approved=True)
        refresh_product_review_stats(product)

        res = admin_client.delete(admin_review_detail(spam.id))

        assert res.status_code == status.HTTP_204_NO_CONTENT
        product.refresh_from_db()
        assert product.reviews_count == 1
        assert product.rating == 4.0

    def test_content_fields_cannot_be_changed_through_admin_endpoint(
        self, admin_client, make_review
    ):
        review = make_review(rating=4, comment="Original comment", is_approved=False)

        res = admin_client.patch(
            admin_review_detail(review.id),
            {
                "comment": "Rewritten by admin",
                "rating": 1,
                "headline": "Rewritten",
                "is_approved": True,
            },
            format="json",
        )

        assert res.status_code == status.HTTP_200_OK  # silently ignored, not rejected
        review.refresh_from_db()
        assert review.comment == "Original comment"
        assert review.rating == 4
        assert review.headline == "Headline"
        assert review.is_approved is True  # the one writable field did apply

    def test_create_and_put_are_not_allowed(self, admin_client, make_review):
        review = make_review()
        assert (
            admin_client.post(ADMIN_REVIEWS_URL, {}, format="json").status_code
            == status.HTTP_405_METHOD_NOT_ALLOWED
        )
        assert (
            admin_client.put(
                admin_review_detail(review.id), {"is_approved": True}, format="json"
            ).status_code
            == status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_non_admin_gets_403_on_every_action(self, customer_client, make_review):
        review = make_review()
        calls = [
            customer_client.get(ADMIN_REVIEWS_URL),
            customer_client.get(admin_review_detail(review.id)),
            customer_client.patch(
                admin_review_detail(review.id), {"is_approved": True}, format="json"
            ),
            customer_client.delete(admin_review_detail(review.id)),
        ]
        assert [r.status_code for r in calls] == [status.HTTP_403_FORBIDDEN] * 4

        review.refresh_from_db()
        assert review.is_approved is False  # the forbidden PATCH changed nothing

    def test_anonymous_gets_401(self, anon_client):
        assert (
            anon_client.get(ADMIN_REVIEWS_URL).status_code
            == status.HTTP_401_UNAUTHORIZED
        )


class TestAdminReviewReports:
    @staticmethod
    def _report(review, user, resolved=False, reason="spam"):
        from shop.models import ReviewReport

        return ReviewReport.objects.create(
            review=review, reported_by=user, reason=reason, resolved=resolved
        )

    def test_has_reports_filter_and_report_count(
        self, admin_client, make_review, make_user
    ):
        reported_twice = make_review(is_approved=True)
        reported_once = make_review(is_approved=True)
        only_resolved = make_review(is_approved=True)
        clean = make_review(is_approved=True)
        u1, u2 = make_user(), make_user()
        self._report(reported_twice, u1)
        self._report(reported_twice, u2)
        self._report(reported_once, u1)
        self._report(only_resolved, u1, resolved=True)

        res = admin_client.get(ADMIN_REVIEWS_URL + "?has_reports=true")

        assert res.status_code == status.HTTP_200_OK
        counts = {r["id"]: r["report_count"] for r in res.data["results"]}
        assert counts == {reported_twice.id: 2, reported_once.id: 1}

        # Unfiltered list reports an accurate count (unresolved only) per row.
        all_counts = {
            r["id"]: r["report_count"]
            for r in admin_client.get(ADMIN_REVIEWS_URL).data["results"]
        }
        assert all_counts[reported_twice.id] == 2
        assert all_counts[only_resolved.id] == 0
        assert all_counts[clean.id] == 0

    def test_has_reports_combines_with_status_filter(
        self, admin_client, make_review, make_user
    ):
        hidden = make_review(is_approved=False)
        live = make_review(is_approved=True)
        user = make_user()
        self._report(hidden, user)
        self._report(live, user)

        res = admin_client.get(ADMIN_REVIEWS_URL + "?has_reports=true&status=pending")

        assert {r["id"] for r in res.data["results"]} == {hidden.id}

    def test_resolving_reports_marks_them_resolved_without_reapproving(
        self, admin_client, make_review, make_user, make_product
    ):
        from shop.models import ReviewReport
        from shop.services import refresh_product_review_stats

        product = make_product()
        review = make_review(product=product, rating=1, is_approved=False)
        other = make_review(is_approved=True)
        for _ in range(3):
            self._report(review, make_user())
        other_report = self._report(other, make_user())
        refresh_product_review_stats(product)

        res = admin_client.post(f"{admin_review_detail(review.id)}resolve-reports/")

        assert res.status_code == status.HTTP_200_OK
        assert res.data == {"resolved": 3}
        assert not ReviewReport.objects.filter(review=review, resolved=False).exists()
        other_report.refresh_from_db()
        assert other_report.resolved is False  # other reviews' reports untouched

        review.refresh_from_db()
        assert review.is_approved is False  # NOT re-approved as a side effect
        product.refresh_from_db()
        assert product.reviews_count == 0  # public stats unchanged by resolving

        # Re-approval is its own explicit step.
        admin_client.patch(
            admin_review_detail(review.id), {"is_approved": True}, format="json"
        )
        review.refresh_from_db()
        product.refresh_from_db()
        assert review.is_approved is True
        assert product.reviews_count == 1

    def test_resolved_reports_no_longer_show_in_queue(
        self, admin_client, make_review, make_user
    ):
        review = make_review(is_approved=True)
        self._report(review, make_user())

        admin_client.post(f"{admin_review_detail(review.id)}resolve-reports/")

        res = admin_client.get(ADMIN_REVIEWS_URL + "?has_reports=true")
        assert res.data["results"] == []

    def test_non_admin_cannot_resolve_reports(
        self, customer_client, make_review, make_user
    ):
        from shop.models import ReviewReport

        review = make_review(is_approved=True)
        self._report(review, make_user())

        res = customer_client.post(f"{admin_review_detail(review.id)}resolve-reports/")

        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert ReviewReport.objects.filter(review=review, resolved=False).count() == 1

    def test_post_to_collection_is_still_405(self, admin_client):
        res = admin_client.post(ADMIN_REVIEWS_URL, {}, format="json")
        assert res.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class TestAdminReviewStoreResponse:
    def test_setting_store_response_stamps_current_time(
        self, admin_client, make_review
    ):
        from django.utils import timezone

        review = make_review(is_approved=True)
        assert review.store_response == ""
        assert review.store_response_at is None

        before = timezone.now()
        res = admin_client.patch(
            admin_review_detail(review.id),
            {"store_response": "Thanks for the feedback!"},
            format="json",
        )
        after = timezone.now()

        assert res.status_code == status.HTTP_200_OK
        review.refresh_from_db()
        assert review.store_response == "Thanks for the feedback!"
        assert before <= review.store_response_at <= after
        assert res.data["store_response"] == "Thanks for the feedback!"
        assert res.data["store_response_at"] is not None

    def test_editing_the_response_restamps_the_time(self, admin_client, make_review):
        from datetime import timedelta

        from django.utils import timezone
        from shop.models import Review

        review = make_review(is_approved=True)
        admin_client.patch(
            admin_review_detail(review.id), {"store_response": "First"}, format="json"
        )
        # Pretend the first reply was posted a day ago so a stale timestamp
        # is unmistakable.
        old = timezone.now() - timedelta(days=1)
        Review.objects.filter(pk=review.pk).update(store_response_at=old)

        before = timezone.now()
        admin_client.patch(
            admin_review_detail(review.id), {"store_response": "Second"}, format="json"
        )

        review.refresh_from_db()
        assert review.store_response == "Second"
        assert review.store_response_at >= before
        assert review.store_response_at > old

    def test_resaving_identical_text_does_not_restamp(self, admin_client, make_review):
        from datetime import timedelta

        from django.utils import timezone
        from shop.models import Review

        review = make_review(is_approved=True)
        admin_client.patch(
            admin_review_detail(review.id), {"store_response": "Same"}, format="json"
        )
        old = timezone.now() - timedelta(days=1)
        Review.objects.filter(pk=review.pk).update(store_response_at=old)

        admin_client.patch(
            admin_review_detail(review.id), {"store_response": "Same"}, format="json"
        )

        review.refresh_from_db()
        assert review.store_response_at == old

    def test_clearing_the_response_clears_the_timestamp(
        self, admin_client, make_review
    ):
        review = make_review(is_approved=True)
        admin_client.patch(
            admin_review_detail(review.id), {"store_response": "Oops"}, format="json"
        )

        admin_client.patch(
            admin_review_detail(review.id), {"store_response": "   "}, format="json"
        )

        review.refresh_from_db()
        assert review.store_response == ""
        assert review.store_response_at is None

    def test_only_store_response_applies_when_other_fields_are_sent_too(
        self, admin_client, make_review
    ):
        review = make_review(
            rating=4, comment="Original comment", headline="Headline", is_approved=False
        )

        res = admin_client.patch(
            admin_review_detail(review.id),
            {
                "store_response": "We're sorry to hear that.",
                "comment": "Rewritten by admin",
                "rating": 1,
                "headline": "Rewritten",
                "name": "Someone else",
            },
            format="json",
        )

        assert res.status_code == status.HTTP_200_OK
        review.refresh_from_db()
        assert review.store_response == "We're sorry to hear that."
        assert review.store_response_at is not None
        assert review.comment == "Original comment"
        assert review.rating == 4
        assert review.headline == "Headline"
        assert review.name == "Reviewer"
        assert review.is_approved is False  # untouched

    def test_store_response_at_cannot_be_set_by_the_client(
        self, admin_client, make_review
    ):
        review = make_review(is_approved=True)

        admin_client.patch(
            admin_review_detail(review.id),
            {"store_response_at": "2020-01-01T00:00:00Z"},
            format="json",
        )

        review.refresh_from_db()
        assert review.store_response_at is None

    def test_moderation_patch_without_store_response_leaves_it_alone(
        self, admin_client, make_review
    ):
        review = make_review(is_approved=False)
        admin_client.patch(
            admin_review_detail(review.id), {"store_response": "Hi"}, format="json"
        )
        review.refresh_from_db()
        stamped = review.store_response_at

        admin_client.patch(
            admin_review_detail(review.id), {"is_approved": True}, format="json"
        )

        review.refresh_from_db()
        assert review.is_approved is True
        assert review.store_response == "Hi"
        assert review.store_response_at == stamped

    def test_non_admin_cannot_set_store_response(self, customer_client, make_review):
        review = make_review(is_approved=True)

        res = customer_client.patch(
            admin_review_detail(review.id), {"store_response": "Hi"}, format="json"
        )

        assert res.status_code == status.HTTP_403_FORBIDDEN
        review.refresh_from_db()
        assert review.store_response == ""


# ══════════════════════════════════════════════════════════════════════════════
# Bulk price update (ProductVariant.price — NOT the legacy Product.price)
# ══════════════════════════════════════════════════════════════════════════════

BULK_URL = "/api/dashboard/admin/products/bulk-price-update/"


def _price(variant):
    from shop.models import ProductVariant

    return ProductVariant.objects.get(pk=variant.pk).price


@pytest.fixture
def two_categories(make_category, make_brand, make_product, make_variant):
    """cat_a has brand_x (2 variants) + brand_y (1); cat_b has brand_x (1)."""
    cat_a, cat_b = make_category("Skincare"), make_category("Makeup")
    brand_x, brand_y = make_brand("BrandX"), make_brand("BrandY")
    p_ax = make_product(name="AX", category=cat_a, brand=brand_x)
    p_ay = make_product(name="AY", category=cat_a, brand=brand_y)
    p_bx = make_product(name="BX", category=cat_b, brand=brand_x)
    return {
        "cat_a": cat_a,
        "cat_b": cat_b,
        "brand_x": brand_x,
        "brand_y": brand_y,
        "ax1": make_variant(product=p_ax, price=1_000_000),
        "ax2": make_variant(product=p_ax, price=2_000_000),
        "ay": make_variant(product=p_ay, price=3_000_000),
        "bx": make_variant(product=p_bx, price=4_000_000),
    }


@pytest.mark.django_db
class TestBulkPriceUpdateDryRun:

    def test_default_is_dry_run_and_changes_nothing(self, admin_client, two_categories):
        from dashboard.models import PriceAdjustmentLog

        d = two_categories
        resp = admin_client.post(
            BULK_URL,
            {
                "adjustment_type": "percent_increase",
                "value": 10,
                "category_id": d["cat_a"].id,
            },  # note: dry_run omitted
            format="json",
        )

        assert resp.status_code == 200
        assert resp.data["dry_run"] is True
        assert resp.data["affected_count"] == 3
        by_id = {row["variant_id"]: row for row in resp.data["preview"]}
        assert by_id[d["ax1"].id]["old_price"] == 1_000_000
        assert by_id[d["ax1"].id]["new_price"] == 1_100_000
        assert by_id[d["ay"].id]["new_price"] == 3_300_000
        # …and nothing was written
        assert _price(d["ax1"]) == 1_000_000
        assert _price(d["ax2"]) == 2_000_000
        assert _price(d["ay"]) == 3_000_000
        assert PriceAdjustmentLog.objects.count() == 0

    def test_omitted_dry_run_stays_true_for_form_encoded_requests_too(
        self, admin_client, two_categories
    ):
        """DRF reads an absent BooleanField as False for form bodies — the
        safe default must survive that."""
        d = two_categories
        resp = admin_client.post(
            BULK_URL,
            {
                "adjustment_type": "fixed_decrease",
                "value": 100_000,
                "category_id": d["cat_a"].id,
            },
            format="multipart",
        )
        assert resp.status_code == 200
        assert resp.data["dry_run"] is True
        assert _price(d["ax1"]) == 1_000_000

    def test_explicit_dry_run_true(self, admin_client, two_categories):
        d = two_categories
        resp = admin_client.post(
            BULK_URL,
            {
                "adjustment_type": "percent_decrease",
                "value": 50,
                "brand_id": d["brand_x"].id,
                "dry_run": True,
            },
            format="json",
        )
        assert resp.data["dry_run"] is True and resp.data["affected_count"] == 3
        assert _price(d["bx"]) == 4_000_000

    def test_preview_is_capped_at_50_but_count_is_the_true_total(
        self, admin_client, make_category, make_product, make_variant
    ):
        cat = make_category("Bulk")
        product = make_product(name="Many", category=cat)
        for _ in range(55):
            make_variant(product=product, price=1_000_000)

        resp = admin_client.post(
            BULK_URL,
            {"adjustment_type": "fixed_increase", "value": 10, "category_id": cat.id},
            format="json",
        )

        assert resp.data["affected_count"] == 55
        assert len(resp.data["preview"]) == 50

    def test_dry_run_does_not_fire_price_signals(self, admin_client, two_categories):
        from unittest.mock import patch

        d = two_categories
        with patch("shop.signals.invalidate_product_list_cache") as invalidate:
            admin_client.post(
                BULK_URL,
                {
                    "adjustment_type": "percent_decrease",
                    "value": 10,
                    "category_id": d["cat_a"].id,
                },
                format="json",
            )
        invalidate.assert_not_called()


@pytest.mark.django_db
class TestBulkPriceUpdateCommit:

    def _commit(self, client, **payload):
        return client.post(BULK_URL, {"dry_run": False, **payload}, format="json")

    def test_commit_applies_and_refetch_confirms(self, admin_client, two_categories):
        d = two_categories
        resp = self._commit(
            admin_client,
            adjustment_type="percent_increase",
            value=10,
            category_id=d["cat_a"].id,
        )

        assert resp.status_code == 200
        assert resp.data["dry_run"] is False
        assert resp.data["matched_count"] == 3
        assert resp.data["updated_count"] == 3
        assert _price(d["ax1"]) == 1_100_000
        assert _price(d["ax2"]) == 2_200_000
        assert _price(d["ay"]) == 3_300_000
        assert _price(d["bx"]) == 4_000_000  # other category untouched

    @pytest.mark.parametrize(
        "adjustment_type,value,start,expected",
        [
            ("percent_increase", 10, 1_000_000, 1_100_000),
            ("percent_increase", 100, 1_000_000, 2_000_000),
            ("percent_decrease", 25, 1_000_000, 750_000),
            ("percent_decrease", 100, 500_000, 0),  # fully discounted → 0
            ("fixed_increase", 150_000, 1_000_000, 1_150_000),
            ("fixed_decrease", 300_000, 1_000_000, 700_000),
            ("fixed_decrease", 300_000, 200_000, 0),  # would go negative → floor 0
            ("fixed_decrease", 200_000, 200_000, 0),  # exactly zero
            # percentages land on the whole-Toman grid (DB CHECK: price % 10 = 0):
            ("percent_increase", 7, 999_900, 1_069_890),  # 1,069,893 → …890
            ("percent_decrease", 50, 10_050, 5_030),  # 5,025 → tie rounds UP
            ("percent_increase", 1, 12_340, 12_460),  # 12,463.4 → …460
        ],
    )
    def test_each_adjustment_type_is_mathematically_correct(
        self, admin_client, make_variant, adjustment_type, value, start, expected
    ):
        v = make_variant(price=start)

        resp = self._commit(
            admin_client,
            adjustment_type=adjustment_type,
            value=value,
            variant_ids=[v.id],
        )

        assert resp.status_code == 200
        new_price = _price(v)
        assert new_price == expected
        assert type(new_price) is int
        assert new_price >= 0 and new_price % 10 == 0

    def test_dry_run_preview_matches_what_commit_then_writes(
        self, admin_client, two_categories
    ):
        d = two_categories
        payload = {
            "adjustment_type": "percent_decrease",
            "value": 15,
            "brand_id": d["brand_x"].id,
        }
        preview = admin_client.post(BULK_URL, payload, format="json").data["preview"]
        self._commit(admin_client, **payload)

        for row in preview:
            from shop.models import ProductVariant

            assert (
                ProductVariant.objects.get(pk=row["variant_id"]).price
                == row["new_price"]
            )

    def test_only_active_variants_are_adjusted(
        self, admin_client, make_category, make_product, make_variant
    ):
        cat = make_category("C")
        product = make_product(category=cat)
        active = make_variant(product=product, price=1_000_000)
        inactive = make_variant(product=product, price=1_000_000, is_active=False)

        resp = self._commit(
            admin_client, adjustment_type="fixed_increase", value=10, category_id=cat.id
        )

        assert resp.data["updated_count"] == 1
        assert _price(active) == 1_000_010
        assert _price(inactive) == 1_000_000

    def test_unchanged_variants_are_skipped_but_counted_as_matched(
        self, admin_client, make_variant
    ):
        free = make_variant(price=0)
        resp = self._commit(
            admin_client,
            adjustment_type="fixed_decrease",
            value=100_000,
            variant_ids=[free.id],
        )
        assert resp.data["matched_count"] == 1
        assert resp.data["updated_count"] == 0
        assert _price(free) == 0

    def test_legacy_product_price_is_never_touched(self, admin_client, two_categories):
        from shop.models import Product

        d = two_categories
        product = d["ax1"].product
        before = Product.objects.get(pk=product.pk).price

        self._commit(
            admin_client,
            adjustment_type="percent_increase",
            value=50,
            category_id=d["cat_a"].id,
        )

        assert Product.objects.get(pk=product.pk).price == before

    def test_commit_is_all_or_nothing(self, admin_client, two_categories):
        from unittest.mock import patch

        from dashboard.models import PriceAdjustmentLog
        from shop.models import ProductVariant

        d = two_categories
        real_save = ProductVariant.save
        calls = {"n": 0}

        def flaky_save(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("boom")
            return real_save(self, *args, **kwargs)

        with patch.object(ProductVariant, "save", flaky_save):
            with pytest.raises(RuntimeError):
                self._commit(
                    admin_client,
                    adjustment_type="percent_increase",
                    value=10,
                    category_id=d["cat_a"].id,
                )

        assert _price(d["ax1"]) == 1_000_000  # first save rolled back too
        assert _price(d["ax2"]) == 2_000_000
        assert PriceAdjustmentLog.objects.count() == 0


@pytest.mark.django_db
class TestBulkPriceUpdateScoping:

    def _commit(self, client, **payload):
        return client.post(BULK_URL, {"dry_run": False, **payload}, format="json")

    def test_category_filter_only_affects_that_categorys_variants(
        self, admin_client, two_categories
    ):
        d = two_categories
        self._commit(
            admin_client,
            adjustment_type="fixed_increase",
            value=10,
            category_id=d["cat_b"].id,
        )
        assert _price(d["bx"]) == 4_000_010
        for key in ("ax1", "ax2", "ay"):
            assert (
                _price(d[key])
                == {
                    "ax1": 1_000_000,
                    "ax2": 2_000_000,
                    "ay": 3_000_000,
                }[key]
            )

    def test_brand_filter_only_affects_that_brands_variants(
        self, admin_client, two_categories
    ):
        d = two_categories
        self._commit(
            admin_client,
            adjustment_type="fixed_increase",
            value=10,
            brand_id=d["brand_y"].id,
        )
        assert _price(d["ay"]) == 3_000_010
        assert _price(d["ax1"]) == 1_000_000 and _price(d["bx"]) == 4_000_000

    def test_variant_ids_filter_affects_exactly_those_variants(
        self, admin_client, two_categories
    ):
        d = two_categories
        resp = self._commit(
            admin_client,
            adjustment_type="fixed_increase",
            value=10,
            variant_ids=[d["ax2"].id, d["bx"].id],
        )
        assert resp.data["updated_count"] == 2
        assert _price(d["ax2"]) == 2_000_010
        assert _price(d["bx"]) == 4_000_010
        assert _price(d["ax1"]) == 1_000_000
        assert _price(d["ay"]) == 3_000_000

    def test_filters_combine_with_and(self, admin_client, two_categories):
        d = two_categories
        resp = self._commit(
            admin_client,
            adjustment_type="fixed_increase",
            value=10,
            category_id=d["cat_a"].id,
            brand_id=d["brand_x"].id,
        )
        assert resp.data["updated_count"] == 2  # ax1, ax2 only
        assert _price(d["ay"]) == 3_000_000  # cat_a but brand_y
        assert _price(d["bx"]) == 4_000_000  # brand_x but cat_b

    def test_unknown_variant_ids_match_nothing(self, admin_client, two_categories):
        resp = self._commit(
            admin_client,
            adjustment_type="fixed_increase",
            value=10,
            variant_ids=[999_999],
        )
        assert resp.status_code == 200
        assert resp.data["matched_count"] == 0 and resp.data["updated_count"] == 0


@pytest.mark.django_db
class TestBulkPriceUpdateValidation:

    @pytest.mark.parametrize(
        "extra",
        [
            {},
            {"category_id": None},
            {"brand_id": None, "category_id": None},
            {"variant_ids": []},
        ],
    )
    def test_no_scope_is_rejected_by_the_serializer(
        self, admin_client, two_categories, extra
    ):
        resp = admin_client.post(
            BULK_URL,
            {
                "adjustment_type": "percent_increase",
                "value": 10,
                "dry_run": False,
                **extra,
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "Specify at least one of" in str(resp.data)
        assert _price(two_categories["ax1"]) == 1_000_000

    @pytest.mark.parametrize(
        "payload",
        [
            {"adjustment_type": "percent_increase", "value": 101},
            {"adjustment_type": "percent_decrease", "value": 101},
            {"adjustment_type": "fixed_increase", "value": 15},  # not whole Toman
            {"adjustment_type": "fixed_decrease", "value": 1_005},
            {"adjustment_type": "percent_increase", "value": 0},
            {"adjustment_type": "percent_increase", "value": -5},
            {"adjustment_type": "percent_increase", "value": "ten"},
            {"adjustment_type": "double_it", "value": 10},
            {"value": 10},
            {"adjustment_type": "percent_increase"},
        ],
    )
    def test_bad_parameters_are_rejected_and_change_nothing(
        self, admin_client, two_categories, payload
    ):
        d = two_categories
        resp = admin_client.post(
            BULK_URL,
            {**payload, "category_id": d["cat_a"].id, "dry_run": False},
            format="json",
        )
        assert resp.status_code == 400
        assert _price(d["ax1"]) == 1_000_000

    def test_percent_boundary_100_is_allowed(self, admin_client, two_categories):
        d = two_categories
        resp = admin_client.post(
            BULK_URL,
            {
                "adjustment_type": "percent_increase",
                "value": 100,
                "category_id": d["cat_a"].id,
            },
            format="json",
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize("field", ["category_id", "brand_id"])
    def test_nonexistent_category_or_brand_is_a_400_not_a_silent_noop(
        self, admin_client, field
    ):
        resp = admin_client.post(
            BULK_URL,
            {"adjustment_type": "fixed_increase", "value": 10, field: 999_999},
            format="json",
        )
        assert resp.status_code == 400 and field in resp.data

    @pytest.mark.parametrize("dry_run", [True, False])
    def test_price_above_the_maximum_is_rejected_in_preview_and_commit(
        self, admin_client, make_variant, dry_run
    ):
        from core.money import MAX_RIAL_AMOUNT

        near_cap = make_variant(price=MAX_RIAL_AMOUNT - 100)
        fine = make_variant(price=1_000_000)

        resp = admin_client.post(
            BULK_URL,
            {
                "adjustment_type": "percent_increase",
                "value": 50,
                "variant_ids": [near_cap.id, fine.id],
                "dry_run": dry_run,
            },
            format="json",
        )

        assert resp.status_code == 400
        assert resp.data["variant_ids"] == [near_cap.id]
        assert _price(near_cap) == MAX_RIAL_AMOUNT - 100
        assert _price(fine) == 1_000_000  # whole request rejected, nothing applied


@pytest.mark.django_db
class TestBulkPriceUpdateAuditLog:

    def test_commit_writes_one_log_row_with_actor_and_counts(
        self, admin_client, admin_user, two_categories
    ):
        from dashboard.models import PriceAdjustmentLog

        d = two_categories
        resp = admin_client.post(
            BULK_URL,
            {
                "adjustment_type": "percent_decrease",
                "value": 20,
                "category_id": d["cat_a"].id,
                "dry_run": False,
            },
            format="json",
        )

        assert PriceAdjustmentLog.objects.count() == 1
        log = PriceAdjustmentLog.objects.get()
        assert resp.data["log_id"] == log.id
        assert log.actor == admin_user
        assert log.adjustment_type == "percent_decrease"
        assert log.value == 20
        assert log.category_id == d["cat_a"].id
        assert log.brand_id is None
        assert log.matched_count == 3 and log.affected_count == 3
        assert log.created_at is not None
        # old → new prices are kept, so the change can be audited or reversed
        assert sorted(log.changes) == sorted(
            [
                [d["ax1"].id, 1_000_000, 800_000],
                [d["ax2"].id, 2_000_000, 1_600_000],
                [d["ay"].id, 3_000_000, 2_400_000],
            ]
        )

    def test_log_records_variant_ids_scope(self, admin_client, two_categories):
        from dashboard.models import PriceAdjustmentLog

        d = two_categories
        admin_client.post(
            BULK_URL,
            {
                "adjustment_type": "fixed_increase",
                "value": 10,
                "variant_ids": [d["ax1"].id],
                "dry_run": False,
            },
            format="json",
        )
        assert PriceAdjustmentLog.objects.get().variant_ids == [d["ax1"].id]

    def test_superuser_is_recorded_as_actor(
        self, superuser_client, superuser_user, two_categories
    ):
        from dashboard.models import PriceAdjustmentLog

        superuser_client.post(
            BULK_URL,
            {
                "adjustment_type": "fixed_increase",
                "value": 10,
                "variant_ids": [two_categories["ax1"].id],
                "dry_run": False,
            },
            format="json",
        )
        assert PriceAdjustmentLog.objects.get().actor == superuser_user

    def test_no_log_for_dry_runs_or_rejected_requests(
        self, admin_client, two_categories
    ):
        from dashboard.models import PriceAdjustmentLog

        d = two_categories
        admin_client.post(
            BULK_URL,
            {
                "adjustment_type": "fixed_increase",
                "value": 10,
                "category_id": d["cat_a"].id,
            },
            format="json",
        )
        admin_client.post(
            BULK_URL,
            {"adjustment_type": "fixed_increase", "value": 10, "dry_run": False},
            format="json",
        )
        assert PriceAdjustmentLog.objects.count() == 0

    def test_actor_survives_in_log_row_after_user_deletion(
        self, admin_client, admin_user, two_categories
    ):
        from dashboard.models import PriceAdjustmentLog

        admin_client.post(
            BULK_URL,
            {
                "adjustment_type": "fixed_increase",
                "value": 10,
                "variant_ids": [two_categories["ax1"].id],
                "dry_run": False,
            },
            format="json",
        )
        admin_user.delete()
        log = PriceAdjustmentLog.objects.get()
        assert log.actor is None and log.affected_count == 1


@pytest.mark.django_db
class TestBulkPriceUpdateStillFiresVariantSignals:
    """A queryset .update() would skip these — the reason commit uses save()."""

    def test_product_list_cache_is_invalidated(self, admin_client, two_categories):
        from unittest.mock import patch

        d = two_categories
        with patch("shop.signals.invalidate_product_list_cache") as invalidate:
            admin_client.post(
                BULK_URL,
                {
                    "adjustment_type": "percent_increase",
                    "value": 10,
                    "category_id": d["cat_a"].id,
                    "dry_run": False,
                },
                format="json",
            )
        assert invalidate.called

    def test_price_snapshot_baseline_follows_and_drop_notification_is_queued(
        self,
        admin_client,
        make_product,
        make_variant,
        django_capture_on_commit_callbacks,
    ):
        from unittest.mock import patch

        from shop.models import ProductPriceSnapshot

        product = make_product(name="Serum")
        variant = make_variant(product=product, price=1_000_000)  # baseline snapshot
        assert product.price_snapshots.first().price == 1_000_000

        with patch("shop.signals.notify_price_drop_subscribers") as task:
            with django_capture_on_commit_callbacks(execute=True):
                admin_client.post(
                    BULK_URL,
                    {
                        "adjustment_type": "percent_decrease",
                        "value": 20,
                        "variant_ids": [variant.id],
                        "dry_run": False,
                    },
                    format="json",
                )

        newest = ProductPriceSnapshot.objects.filter(product=product).first()
        assert newest.price == 800_000
        task.delay.assert_called_once_with(product.id, 1_000_000, 800_000)


@pytest.mark.django_db
class TestBulkPriceUpdatePermissions:

    PAYLOAD = {
        "adjustment_type": "fixed_increase",
        "value": 10,
        "variant_ids": [1],
        "dry_run": False,
    }

    def test_non_admin_gets_403_and_nothing_changes(
        self, customer_client, two_categories
    ):
        from dashboard.models import PriceAdjustmentLog

        d = two_categories
        resp = customer_client.post(
            BULK_URL, {**self.PAYLOAD, "variant_ids": [d["ax1"].id]}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert _price(d["ax1"]) == 1_000_000
        assert PriceAdjustmentLog.objects.count() == 0

    def test_anonymous_is_rejected(self, anon_client):
        resp = anon_client.post(BULK_URL, self.PAYLOAD, format="json")
        assert resp.status_code in (401, 403)

    def test_get_is_not_allowed(self, admin_client):
        assert admin_client.get(BULK_URL).status_code == 405

    def test_admin_and_superuser_allowed(
        self, admin_client, superuser_client, two_categories
    ):
        payload = {
            "adjustment_type": "fixed_increase",
            "value": 10,
            "variant_ids": [two_categories["ax1"].id],
        }
        assert admin_client.post(BULK_URL, payload, format="json").status_code == 200
        assert (
            superuser_client.post(BULK_URL, payload, format="json").status_code == 200
        )


# ══════════════════════════════════════════════════════════════════════════════
# Bulk product + variant import (CSV / Excel)
# ══════════════════════════════════════════════════════════════════════════════

import csv as _csv  # noqa: E402
import io as _io  # noqa: E402
from datetime import date as _date  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

IMPORT_URL = "/api/dashboard/admin/products/bulk-import/"
TEMPLATE_URL = "/api/dashboard/admin/products/import-template/"

_NUMERIC = {
    "price", "original_price", "stock", "low_stock_threshold", "volume_ml",
    "weight_g", "spf",
}  # fmt: skip
_BOOLS = {"is_active", "is_cruelty_free", "is_vegan", "is_organic"}
_DATES = {"manufacture_date", "expiration_date"}


def _valid_ean13():
    from shop.validators import _compute_ean13_check_digit

    base = "629104150021"
    return base + str(_compute_ean13_check_digit(base))


def _columns_for(rows):
    """Header: required columns plus any column used by any row (schema order)."""
    from dashboard.product_import import IMPORT_COLUMN_NAMES, REQUIRED_COLUMN_NAMES

    used = set(REQUIRED_COLUMN_NAMES)
    for row in rows:
        used |= set(row)
    return [c for c in IMPORT_COLUMN_NAMES if c in used]


def make_csv(rows, columns=None, delimiter=",", bom=False):
    columns = columns or _columns_for(rows)
    buffer = _io.StringIO()
    writer = _csv.writer(buffer, delimiter=delimiter)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(c, "") for c in columns])
    data = buffer.getvalue().encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if bom else data


def make_xlsx(rows, columns=None):
    """The same rows as real, TYPED Excel cells (ints, floats, bools, dates)."""
    from openpyxl import Workbook

    columns = columns or _columns_for(rows)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(columns)
    for row in rows:
        cells = []
        for column in columns:
            text = row.get(column, "")
            if text == "":
                cells.append(None)
            elif column in _NUMERIC:
                # a float for spf exercises Excel's habit of storing 50 as 50.0
                cells.append(float(text) if column == "spf" else int(text))
            elif column in _BOOLS and text in ("true", "false"):
                cells.append(text == "true")
            elif column in _DATES:
                cells.append(_date.fromisoformat(text))
            else:
                cells.append(text)
        sheet.append(cells)
    buffer = _io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


FORMATS = {
    "csv": (make_csv, "catalog.csv", "text/csv"),
    "xlsx": (
        make_xlsx,
        "catalog.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
}


def post_import(client, content, name="catalog.csv", **fields):
    upload = SimpleUploadedFile(name, content)
    return client.post(IMPORT_URL, {"file": upload, **fields}, format="multipart")


@pytest.fixture
def taxonomy(make_category, make_brand):
    return {
        "skincare": make_category("Skincare"),
        "makeup": make_category("Makeup"),
        "brand": make_brand("BrandX"),
    }


def good_rows():
    """3 valid rows → 2 products (Hydra Serum ×2 variants, Sun Cream ×1)."""
    serum = {
        "product_name": "Hydra Serum",
        "category": "Skincare",
        "brand": "BrandX",
        "skin_type": "dry",
        "gender": "female",
        "is_cruelty_free": "true",
        "is_vegan": "false",
        "is_organic": "yes",
        "ingredients": "Aqua, Glycerin, Sodium Hyaluronate",
        "description": "A hydrating serum.",
        "country_of_origin": "France",
    }
    return [
        {
            **serum,
            "color": "Rose",
            "color_hex": "#E8A0BF",
            "price": "1250000",
            "stock": "25",
            "volume_ml": "30",
            "barcode": _valid_ean13(),
            "manufacture_date": "2026-01-15",
            "expiration_date": "2028-01-15",
            "batch_number": "B2601",
        },
        {
            **serum,
            "color": "Nude",
            "color_hex": "#D2B48C",
            "price": "1850000",
            "stock": "10",
            "volume_ml": "50",
        },
        {
            "product_name": "Sun Cream",
            "category": "Skincare",
            "brand": "BrandX",
            "price": "900000",
            "stock": "5",
            "weight_g": "100",
            "spf": "50",
            "skin_type": "all",
        },
    ]


def catalog_state():
    """Everything the import is supposed to have written, as plain data."""
    from shop.models import Color, Product, ProductVariant

    products = {
        p.name: {
            "category": p.category.name,
            "brand": p.brand.name if p.brand else None,
            "skin_type": p.skin_type,
            "hair_type": p.hair_type,
            "gender": p.gender,
            "spf": p.spf,
            "cruelty_free": p.is_cruelty_free,
            "vegan": p.is_vegan,
            "organic": p.is_organic,
            "ingredients": p.ingredients,
            "country": p.country_of_origin,
            "description": p.description,
            "slug": bool(p.slug),
        }
        for p in Product.objects.select_related("category", "brand")
    }
    variants = sorted(
        (
            v.product.name,
            v.color.name if v.color else None,
            v.price,
            v.stock,
            v.volume_ml,
            v.weight_g,
            v.barcode,
            v.manufacture_date,
            v.expiration_date,
            v.batch_number,
            bool(v.sku),
        )
        for v in ProductVariant.objects.select_related("product", "color")
    )
    colors = sorted(Color.objects.values_list("name", "hex_code"))
    return products, variants, colors


EXPECTED_PRODUCTS = {
    "Hydra Serum": {
        "category": "Skincare",
        "brand": "BrandX",
        "skin_type": "dry",
        "hair_type": "",
        "gender": "female",
        "spf": None,
        "cruelty_free": True,
        "vegan": False,
        "organic": True,
        "ingredients": "Aqua, Glycerin, Sodium Hyaluronate",
        "country": "France",
        "description": "A hydrating serum.",
        "slug": True,
    },
    "Sun Cream": {
        "category": "Skincare",
        "brand": "BrandX",
        "skin_type": "all",
        "hair_type": "",
        "gender": "unisex",  # model default when the column is blank
        "spf": 50,
        "cruelty_free": False,
        "vegan": False,
        "organic": False,
        "ingredients": "",
        "country": "",
        "description": "",
        "slug": True,
    },
}


@pytest.mark.django_db
class TestBulkImportDryRunAndCommit:

    def test_dry_run_previews_and_creates_nothing(self, admin_client, taxonomy):
        from shop.models import Color, Product, ProductVariant

        resp = post_import(admin_client, make_csv(good_rows()))  # dry_run omitted

        assert resp.status_code == 200
        assert resp.data["dry_run"] is True
        assert resp.data["total_rows"] == 3
        assert resp.data["created_count"] == 3
        assert resp.data["updated_count"] == 0
        assert resp.data["products_created_count"] == 2
        assert resp.data["error_count"] == 0
        # a real preview: rows, actions and the SKUs the run generated
        preview = resp.data["preview"]
        assert [r["row"] for r in preview] == [2, 3, 4]
        assert {r["action"] for r in preview} == {"created"}
        assert [r["product_name"] for r in preview] == [
            "Hydra Serum",
            "Hydra Serum",
            "Sun Cream",
        ]
        assert all(r["sku"] for r in preview)
        assert [r["product_created"] for r in preview] == [True, False, True]
        # …and nothing persisted
        assert Product.objects.count() == 0
        assert ProductVariant.objects.count() == 0
        assert Color.objects.count() == 0

    @pytest.mark.parametrize("fmt", ["csv", "xlsx"])
    def test_commit_creates_everything_with_all_attributes(
        self, admin_client, taxonomy, fmt
    ):
        build, name, _ct = FORMATS[fmt]

        resp = post_import(admin_client, build(good_rows()), name=name, dry_run="false")

        assert resp.status_code == 200, resp.data
        assert resp.data["dry_run"] is False
        assert resp.data["created_count"] == 3 and resp.data["error_count"] == 0
        products, variants, colors = catalog_state()
        assert products == EXPECTED_PRODUCTS
        ean = _valid_ean13()
        assert variants == sorted(
            [
                ("Hydra Serum", "Rose", 1_250_000, 25, 30, None, ean,
                 _date(2026, 1, 15), _date(2028, 1, 15), "B2601", True),
                ("Hydra Serum", "Nude", 1_850_000, 10, 50, None, "",
                 None, None, "", True),
                ("Sun Cream", None, 900_000, 5, None, 100, "",
                 None, None, "", True),
            ]
        )  # fmt: skip
        assert colors == [("Nude", "#D2B48C"), ("Rose", "#E8A0BF")]

    def test_csv_and_xlsx_parse_to_identical_rows(self):
        from dashboard.product_import import parse_import_file

        rows = good_rows()
        from_csv = parse_import_file(SimpleUploadedFile("a.csv", make_csv(rows)))
        from_xlsx = parse_import_file(SimpleUploadedFile("a.xlsx", make_xlsx(rows)))
        assert from_csv == from_xlsx

    def test_csv_and_xlsx_dry_runs_report_identically(self, admin_client, taxonomy):
        keys = ("created_count", "updated_count", "products_created_count",
                "error_count", "errors", "total_rows")  # fmt: skip
        out = {}
        for fmt, (build, name, _ct) in FORMATS.items():
            resp = post_import(admin_client, build(good_rows()), name=name)
            out[fmt] = {k: resp.data[k] for k in keys}
        assert out["csv"] == out["xlsx"]

    def test_commit_then_reimport_is_idempotent(self, admin_client, taxonomy):
        from shop.models import ProductVariant

        post_import(admin_client, make_csv(good_rows()), dry_run="false")
        before = catalog_state()

        resp = post_import(admin_client, make_csv(good_rows()), dry_run="false")

        assert resp.data["created_count"] == 0
        assert resp.data["updated_count"] == 3
        assert resp.data["error_count"] == 0
        assert ProductVariant.objects.count() == 3
        assert catalog_state() == before

    @pytest.mark.parametrize("value", ["banana", "maybe"])
    def test_unrecognised_dry_run_is_a_400(self, admin_client, taxonomy, value):
        resp = post_import(admin_client, make_csv(good_rows()), dry_run=value)
        assert resp.status_code == 400 and "dry_run" in resp.data

    @pytest.mark.parametrize("value", ["false", "False", "0"])
    def test_false_spellings_commit(self, admin_client, taxonomy, value):
        resp = post_import(admin_client, make_csv(good_rows()), dry_run=value)
        assert resp.data["dry_run"] is False and resp.data["created_count"] == 3


@pytest.mark.django_db
class TestBulkImportUpdates:

    def _existing(self, make_product, make_variant, taxonomy, **kwargs):
        product = make_product(
            name="Hydra Serum", category=taxonomy["skincare"], brand=taxonomy["brand"]
        )
        return make_variant(product=product, sku="SER-001", price=1_000_000, **kwargs)

    @pytest.mark.parametrize("fmt", ["csv", "xlsx"])
    def test_existing_sku_updates_instead_of_duplicating(
        self, admin_client, taxonomy, make_product, make_variant, fmt
    ):
        from shop.models import ProductVariant

        variant = self._existing(make_product, make_variant, taxonomy, stock=3)
        build, name, _ct = FORMATS[fmt]
        rows = [
            {
                "product_name": "Hydra Serum",
                "category": "Skincare",
                "sku": "SER-001",
                "price": "1400000",
                "stock": "40",
                "volume_ml": "30",
            }
        ]

        resp = post_import(admin_client, build(rows), name=name, dry_run="false")

        assert resp.data["created_count"] == 0 and resp.data["updated_count"] == 1
        assert resp.data["products_created_count"] == 0
        assert ProductVariant.objects.count() == 1  # no duplicate
        variant.refresh_from_db()
        assert (variant.price, variant.stock, variant.volume_ml) == (1_400_000, 40, 30)

    def test_update_without_sku_matches_product_color_and_size(
        self, admin_client, taxonomy, make_product, make_variant
    ):
        from shop.models import Color, ProductVariant

        rose = Color.objects.create(name="Rose", hex_code="#E8A0BF")
        variant = self._existing(make_product, make_variant, taxonomy)
        variant.color, variant.volume_ml = rose, 30
        variant.save()
        rows = [
            {
                "product_name": "Hydra Serum",
                "category": "Skincare",
                "color": "rose",  # case-insensitive
                "volume_ml": "30",
                "price": "1111110",
            }
        ]

        resp = post_import(admin_client, make_csv(rows), dry_run="false")

        assert resp.data["updated_count"] == 1 and resp.data["created_count"] == 0
        assert ProductVariant.objects.count() == 1
        variant.refresh_from_db()
        assert variant.price == 1_111_110 and variant.sku == "SER-001"

    def test_new_size_of_an_existing_product_adds_a_variant(
        self, admin_client, taxonomy, make_product, make_variant
    ):
        from shop.models import Product, ProductVariant

        self._existing(make_product, make_variant, taxonomy)
        rows = [
            {
                "product_name": "Hydra Serum",
                "category": "Skincare",
                "volume_ml": "100",
                "price": "2500000",
            }
        ]
        resp = post_import(admin_client, make_csv(rows), dry_run="false")

        assert resp.data["created_count"] == 1
        assert resp.data["products_created_count"] == 0
        assert Product.objects.count() == 1
        assert ProductVariant.objects.count() == 2

    def test_a_brand_new_color_never_matches_a_colorless_variant(
        self, admin_client, taxonomy, make_product, make_variant
    ):
        from shop.models import ProductVariant

        plain = self._existing(make_product, make_variant, taxonomy)  # no color
        rows = [
            {
                "product_name": "Hydra Serum",
                "category": "Skincare",
                "color": "Coral",
                "color_hex": "#FF7F50",
                "price": "1500000",
            }
        ]
        resp = post_import(admin_client, make_csv(rows), dry_run="false")

        assert resp.data["created_count"] == 1 and resp.data["updated_count"] == 0
        assert ProductVariant.objects.count() == 2
        plain.refresh_from_db()
        assert plain.price == 1_000_000 and plain.color is None

    def test_blank_cells_leave_existing_values_unchanged(
        self, admin_client, taxonomy, make_product, make_variant
    ):
        variant = self._existing(make_product, make_variant, taxonomy, stock=7)
        variant.batch_number = "KEEP-ME"
        variant.save()
        product = variant.product
        product.ingredients = "Original list"
        product.save()
        # A narrow "stock refresh" sheet: required columns present, cells blank.
        rows = [
            {
                "product_name": "Hydra Serum",
                "category": "",
                "sku": "SER-001",
                "price": "",
                "stock": "99",
            }
        ]

        resp = post_import(admin_client, make_csv(rows), dry_run="false")

        assert resp.data["updated_count"] == 1 and resp.data["error_count"] == 0
        variant.refresh_from_db()
        product.refresh_from_db()
        assert variant.stock == 99
        assert variant.price == 1_000_000 and variant.batch_number == "KEEP-ME"
        assert product.ingredients == "Original list"
        assert product.category_id == taxonomy["skincare"].id

    def test_update_changes_product_level_fields(
        self, admin_client, taxonomy, make_product, make_variant
    ):
        variant = self._existing(make_product, make_variant, taxonomy)
        rows = [
            {
                "product_name": "Hydra Serum",
                "category": "Makeup",
                "sku": "SER-001",
                "price": "1000000",
                "skin_type": "oily",
                "spf": "30",
            }
        ]
        post_import(admin_client, make_csv(rows), dry_run="false")
        product = variant.product
        product.refresh_from_db()
        assert product.category_id == taxonomy["makeup"].id
        assert (product.skin_type, product.spf) == ("oily", 30)

    def test_sku_belonging_to_another_product_is_an_error(
        self, admin_client, taxonomy, make_product, make_variant
    ):
        variant = self._existing(make_product, make_variant, taxonomy)
        rows = [
            {
                "product_name": "Some Other Product",
                "category": "Skincare",
                "sku": "SER-001",
                "price": "500000",
            }
        ]
        resp = post_import(admin_client, make_csv(rows), dry_run="false")

        assert resp.data["error_count"] == 1
        assert "belongs to product 'Hydra Serum'" in resp.data["errors"][0]["error"]
        variant.refresh_from_db()
        assert variant.price == 1_000_000  # untouched

    def test_stock_change_is_audited_only_after_commit(
        self,
        admin_client,
        admin_user,
        taxonomy,
        make_product,
        make_variant,
        django_capture_on_commit_callbacks,
    ):
        from unittest.mock import patch

        from shop.models import StockMovement

        variant = self._existing(make_product, make_variant, taxonomy, stock=0)
        rows = [
            {
                "product_name": "Hydra Serum",
                "category": "Skincare",
                "sku": "SER-001",
                "price": "1000000",
                "stock": "12",
            }
        ]

        # Dry run: callbacks are discarded with the rollback → nothing, and
        # in particular no back-in-stock notification.
        with patch("shop.signals.notify_stock_alert_subscribers") as notify:
            with django_capture_on_commit_callbacks(execute=True):
                post_import(admin_client, make_csv(rows))
        assert StockMovement.objects.count() == 0
        notify.delay.assert_not_called()

        with patch("shop.signals.notify_stock_alert_subscribers") as notify:
            with django_capture_on_commit_callbacks(execute=True):
                post_import(admin_client, make_csv(rows), dry_run="false")
        movement = StockMovement.objects.get()
        assert movement.variant == variant
        assert (movement.quantity_delta, movement.stock_after) == (12, 12)
        assert movement.reason == StockMovement.Reason.MANUAL
        assert movement.actor == admin_user and "row 2" in movement.note
        notify.delay.assert_called_once_with(variant.id)  # 0 → 12 restock

    def test_price_drop_alerts_fire_only_for_a_real_import(
        self,
        admin_client,
        taxonomy,
        make_product,
        make_variant,
        django_capture_on_commit_callbacks,
    ):
        """ProductVariant.save() queues a wishlist price-drop task on commit —
        a dry run must never leak that."""
        from unittest.mock import patch

        product = make_product(
            name="Hydra Serum", category=taxonomy["skincare"], brand=taxonomy["brand"]
        )
        variant = make_variant(product=product, sku="SER-001", price=1_000_000)
        rows = [
            {
                "product_name": "Hydra Serum",
                "category": "Skincare",
                "sku": "SER-001",
                "price": "800000",
            }
        ]

        with patch("shop.signals.notify_price_drop_subscribers") as task:
            with django_capture_on_commit_callbacks(execute=True):
                post_import(admin_client, make_csv(rows))  # dry run
        task.delay.assert_not_called()
        variant.refresh_from_db()
        assert variant.price == 1_000_000

        with patch("shop.signals.notify_price_drop_subscribers") as task:
            with django_capture_on_commit_callbacks(execute=True):
                post_import(admin_client, make_csv(rows), dry_run="false")
        task.delay.assert_called_once_with(product.id, 1_000_000, 800_000)


@pytest.mark.django_db
class TestBulkImportPerRowErrors:

    def test_bad_category_is_a_row_error_and_valid_rows_still_succeed(
        self, admin_client, taxonomy
    ):
        from shop.models import Product, ProductVariant

        rows = good_rows()
        rows.insert(
            1,
            {
                "product_name": "Mystery Cream",
                "category": "Skincar",  # typo
                "price": "700000",
            },
        )

        resp = post_import(admin_client, make_csv(rows), dry_run="false")

        assert resp.status_code == 200
        assert resp.data["created_count"] == 3  # the three valid rows
        assert resp.data["error_count"] == 1
        (error,) = resp.data["errors"]
        assert error["row"] == 3  # sheet row: header=1, first data row=2
        assert "category: 'Skincar' does not exist" in error["error"]
        assert "Did you mean 'Skincare'?" in error["error"]
        assert not Product.objects.filter(name="Mystery Cream").exists()
        assert ProductVariant.objects.count() == 3
        assert Product.objects.count() == 2

    @pytest.mark.parametrize("fmt", ["csv", "xlsx"])
    def test_errors_are_identical_for_both_formats(self, admin_client, taxonomy, fmt):
        build, name, _ct = FORMATS[fmt]
        rows = [
            {"product_name": "A", "category": "Nope", "price": "100000"},
            {"product_name": "B", "category": "Skincare", "price": "100005"},
            {"product_name": "C", "category": "Skincare", "price": "100000"},
        ]
        resp = post_import(admin_client, build(rows), name=name)
        assert resp.data["created_count"] == 1
        assert [e["row"] for e in resp.data["errors"]] == [2, 3]

    def test_a_failure_after_the_product_was_written_leaves_no_orphan(
        self, admin_client, taxonomy
    ):
        from shop.models import Product, ProductVariant

        rows = [
            {
                "product_name": "Half Done",
                "category": "Skincare",
                "price": "500000",
                "barcode": "1234567890123",  # bad EAN-13 check digit
            },
            {"product_name": "Fine", "category": "Skincare", "price": "500000"},
        ]
        resp = post_import(admin_client, make_csv(rows), dry_run="false")

        assert resp.data["error_count"] == 1
        assert "barcode" in resp.data["errors"][0]["error"]
        assert not Product.objects.filter(name="Half Done").exists()
        assert Product.objects.filter(name="Fine").exists()
        assert ProductVariant.objects.count() == 1

    def test_a_database_error_does_not_poison_the_rest_of_the_batch(
        self, admin_client, taxonomy
    ):
        from unittest.mock import patch

        from django.db import connection
        from shop.models import Product, ProductVariant

        real_save = ProductVariant.save

        def exploding_save(self, *args, **kwargs):
            if self.sku == "BOOM":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1/0")  # aborts the transaction
            return real_save(self, *args, **kwargs)

        rows = [
            {"product_name": "P1", "category": "Skincare", "price": "100000"},
            {"product_name": "P2", "category": "Skincare", "price": "100000",
             "sku": "BOOM"},
            {"product_name": "P3", "category": "Skincare", "price": "100000"},
        ]  # fmt: skip
        with patch.object(ProductVariant, "save", exploding_save):
            resp = post_import(admin_client, make_csv(rows), dry_run="false")

        assert resp.status_code == 200
        assert resp.data["created_count"] == 2
        assert [e["row"] for e in resp.data["errors"]] == [3]
        assert resp.data["errors"][0]["error"] == (
            "Unexpected error while processing this row."  # no internals leaked
        )
        assert set(Product.objects.values_list("name", flat=True)) == {"P1", "P3"}

    def test_error_list_is_capped_but_the_count_is_true(self, admin_client, taxonomy):
        rows = [
            {"product_name": f"P{i}", "category": "Nope", "price": "100000"}
            for i in range(150)
        ]
        resp = post_import(admin_client, make_csv(rows))
        assert resp.data["error_count"] == 150
        assert len(resp.data["errors"]) == 100

    def test_all_problems_in_one_row_are_reported_together(
        self, admin_client, taxonomy
    ):
        rows = [
            {
                "product_name": "Messy",
                "category": "Skincare",
                "price": "12x",
                "stock": "-3",
                "spf": "150",
                "is_vegan": "maybe",
                "skin_type": "scaly",
                "expiration_date": "1405/03/01",
            }
        ]
        resp = post_import(admin_client, make_csv(rows))
        message = resp.data["errors"][0]["error"]
        for fragment in (
            "price: '12x'",
            "stock: '-3'",
            "spf: 150",
            "is_vegan: 'maybe'",
            "skin_type: 'scaly'",
            "expiration_date: '1405/03/01'",
            "Jalali",
        ):
            assert fragment in message, fragment


@pytest.mark.django_db
class TestBulkImportLookupRules:

    def _one(self, **row):
        base = {"product_name": "X", "category": "Skincare", "price": "100000"}
        return make_csv([{**base, **row}])

    def test_unknown_brand_is_an_error_not_auto_created(self, admin_client, taxonomy):
        from shop.models import Brand

        resp = post_import(admin_client, self._one(brand="BrandXX"), dry_run="false")
        assert "brand: 'BrandXX' does not exist. Did you mean 'BrandX'?" in (
            resp.data["errors"][0]["error"]
        )
        assert Brand.objects.count() == 1

    def test_unknown_category_is_never_auto_created(self, admin_client, taxonomy):
        from shop.models import Category

        before = Category.objects.count()
        post_import(admin_client, self._one(category="Brand New"), dry_run="false")
        assert Category.objects.count() == before

    def test_new_color_is_created_when_a_hex_is_given(self, admin_client, taxonomy):
        from shop.models import Color

        resp = post_import(
            admin_client, self._one(color="Coral", color_hex="#FF7F50"), dry_run="false"
        )
        assert resp.data["created_count"] == 1
        assert Color.objects.get(name="Coral").hex_code == "#FF7F50"

    def test_new_color_without_a_hex_is_an_error(self, admin_client, taxonomy):
        from shop.models import Color

        resp = post_import(admin_client, self._one(color="Coral"), dry_run="false")
        assert "add color_hex" in resp.data["errors"][0]["error"]
        assert Color.objects.count() == 0

    def test_existing_color_with_a_different_hex_is_an_error(
        self, admin_client, taxonomy
    ):
        from shop.models import Color

        Color.objects.create(name="Coral", hex_code="#FF7F50")
        resp = post_import(
            admin_client, self._one(color="coral", color_hex="#000000"), dry_run="false"
        )
        assert "conflicts with the existing color" in resp.data["errors"][0]["error"]

    def test_bad_hex_format(self, admin_client, taxonomy):
        resp = post_import(
            admin_client, self._one(color="Coral", color_hex="orange"), dry_run="false"
        )
        assert "#RRGGBB" in resp.data["errors"][0]["error"]

    def test_category_path_disambiguates(self, admin_client, make_category, make_brand):
        from shop.models import Product

        face = make_category("Face")
        eyes = make_category("Eyes")
        make_category("Care", parent=face)
        under_eyes = make_category("Care", parent=eyes)

        ambiguous = post_import(
            admin_client, make_csv([{"product_name": "A", "category": "Care",
                                     "price": "100000"}])
        )  # fmt: skip
        assert "ambiguous" in ambiguous.data["errors"][0]["error"]
        assert "Eyes > Care" in ambiguous.data["errors"][0]["error"]

        resp = post_import(
            admin_client,
            make_csv([{"product_name": "A", "category": "Eyes > Care",
                       "price": "100000"}]),
            dry_run="false",
        )  # fmt: skip
        assert resp.data["created_count"] == 1
        assert Product.objects.get(name="A").category_id == under_eyes.id

    def test_persian_digits_and_character_variants(self, admin_client, make_category):
        from shop.models import Brand, Product, ProductVariant

        make_category("مراقبت پوست")
        Brand.objects.create(name="کلینیک")
        rows = [
            {
                "product_name": "سرم آبرسان",
                "category": "مراقبت پوست",
                "brand": "كلينيك",  # Arabic kaf/yeh typed by mistake
                "price": "۱٬۲۵۰٬۰۰۰",
                "stock": "۲۵",
            }
        ]
        resp = post_import(admin_client, make_csv(rows), dry_run="false")
        assert resp.data["error_count"] == 0, resp.data["errors"]
        variant = ProductVariant.objects.get()
        assert (variant.price, variant.stock) == (1_250_000, 25)
        assert Product.objects.get().brand.name == "کلینیک"

    def test_duplicate_variant_in_one_file_is_an_error_on_the_second(
        self, admin_client, taxonomy
    ):
        from shop.models import ProductVariant

        rows = [
            {"product_name": "Dup", "category": "Skincare", "price": "100000",
             "volume_ml": "30"},
            {"product_name": "Dup", "category": "Skincare", "price": "200000",
             "volume_ml": "30"},
        ]  # fmt: skip
        resp = post_import(admin_client, make_csv(rows), dry_run="false")
        assert resp.data["created_count"] == 1
        assert resp.data["errors"][0]["row"] == 3
        assert "Duplicate of row 2" in resp.data["errors"][0]["error"]
        assert ProductVariant.objects.get().price == 100_000

    def test_conflicting_product_level_values_across_rows(self, admin_client, taxonomy):
        rows = [
            {"product_name": "Same", "category": "Skincare", "price": "100000",
             "volume_ml": "30", "skin_type": "dry"},
            {"product_name": "Same", "category": "Skincare", "price": "100000",
             "volume_ml": "50", "skin_type": "oily"},
        ]  # fmt: skip
        resp = post_import(admin_client, make_csv(rows), dry_run="false")
        assert resp.data["created_count"] == 1
        assert "skin_type: conflicts with the value given on row 2" in (
            resp.data["errors"][0]["error"]
        )

    def test_new_product_requires_category_and_price(self, admin_client, taxonomy):
        rows = [
            {"product_name": "NoCat", "category": "", "price": "100000"},
            {"product_name": "NoPrice", "category": "Skincare", "price": ""},
            {"product_name": "", "category": "Skincare", "price": "100000"},
        ]
        resp = post_import(admin_client, make_csv(rows))
        messages = [e["error"] for e in resp.data["errors"]]
        assert "category: this is required for a new product." in messages[0]
        assert "price: this is required for a new product." in messages[1]
        assert "product_name: this is required." in messages[2]

    def test_non_toman_price_is_rejected_by_model_validation(
        self, admin_client, taxonomy
    ):
        resp = post_import(admin_client, self._one(price="100005"))
        assert "whole number of Toman" in resp.data["errors"][0]["error"]

    def _one(self, **row):
        base = {"product_name": "X", "category": "Skincare", "price": "100000"}
        return make_csv([{**base, **row}])


@pytest.mark.django_db
class TestBulkImportFileLevelErrors:

    def _assert_file_error(self, resp, fragment):
        assert resp.status_code == 400, resp.data
        assert fragment in str(resp.data["file"])

    def test_no_file(self, admin_client):
        resp = admin_client.post(IMPORT_URL, {}, format="multipart")
        assert resp.status_code == 400 and "file" in resp.data

    def test_unsupported_extension(self, admin_client):
        self._assert_file_error(
            post_import(admin_client, b"x", name="catalog.txt"), "Unsupported file type"
        )

    def test_old_xls_gets_a_helpful_message(self, admin_client):
        self._assert_file_error(
            post_import(admin_client, b"x", name="catalog.xls"), ".xls"
        )

    def test_unknown_column_is_rejected_with_a_pointer_to_the_template(
        self, admin_client
    ):
        content = make_csv(
            [{"product_name": "A", "category": "C", "price": "1", "skin_typ": "dry"}],
            columns=["product_name", "category", "price", "skin_typ"],
        )
        resp = post_import(admin_client, content)
        self._assert_file_error(resp, "Unknown column(s): skin_typ")
        self._assert_file_error(resp, "template")

    def test_missing_required_column(self, admin_client):
        content = make_csv(
            [{"product_name": "A", "category": "C"}],
            columns=["product_name", "category"],
        )
        self._assert_file_error(
            post_import(admin_client, content), "Missing required column(s): price"
        )

    def test_staff_only_fields_are_not_importable(self, admin_client):
        content = make_csv(
            [{"product_name": "A", "category": "C", "price": "1"}],
            columns=["product_name", "category", "price", "regulatory_verified"],
        )
        self._assert_file_error(
            post_import(admin_client, content), "regulatory_verified"
        )

    def test_duplicate_column(self, admin_client):
        content = b"product_name,category,price,price\nA,C,1,2\n"
        self._assert_file_error(post_import(admin_client, content), "Duplicate")

    def test_header_variants_are_forgiven(self, admin_client, taxonomy):
        content = "Product Name,CATEGORY,Price\nA,Skincare,100000\n".encode()
        resp = post_import(admin_client, content)
        assert resp.status_code == 200 and resp.data["created_count"] == 1

    def test_empty_and_header_only_files(self, admin_client):
        self._assert_file_error(post_import(admin_client, b""), "empty")
        self._assert_file_error(
            post_import(admin_client, b"product_name,category,price\n"), "no data rows"
        )

    def test_non_utf8_csv(self, admin_client):
        content = "product_name,category,price\nسرم,C,1\n".encode("cp1256")
        self._assert_file_error(post_import(admin_client, content), "UTF-8")

    def test_corrupt_xlsx(self, admin_client):
        self._assert_file_error(
            post_import(admin_client, b"PK\x03\x04garbage", name="c.xlsx"),
            "valid .xlsx",
        )
        self._assert_file_error(
            post_import(admin_client, b"not a zip", name="c.xlsx"), "valid .xlsx"
        )

    def test_too_many_rows(self, admin_client):
        rows = [
            {"product_name": f"P{i}", "category": "C", "price": "10"}
            for i in range(1001)
        ]
        self._assert_file_error(
            post_import(admin_client, make_csv(rows)), "limit is 1000"
        )

    def test_file_too_large(self, admin_client):
        big = b"product_name,category,price\n" + b"A,C,1\n" * (1024 * 1024)
        self._assert_file_error(post_import(admin_client, big), "larger than 5 MB")

    def test_semicolon_delimiter_and_bom_are_handled(self, admin_client, taxonomy):
        resp = post_import(admin_client, make_csv(good_rows(), delimiter=";", bom=True))
        assert resp.status_code == 200 and resp.data["created_count"] == 3

    def test_blank_rows_are_skipped_but_still_numbered(self, admin_client, taxonomy):
        content = (
            "product_name,category,price\n"
            "A,Skincare,100000\n"
            ",,\n"
            "B,Nope,100000\n"
        ).encode()
        resp = post_import(admin_client, content)
        assert resp.data["total_rows"] == 2
        assert resp.data["errors"][0]["row"] == 4  # the real sheet row


@pytest.mark.django_db
class TestImportTemplate:

    def test_csv_template_header_matches_what_the_importer_expects(self, admin_client):
        from dashboard.product_import import IMPORT_COLUMN_NAMES

        resp = admin_client.get(TEMPLATE_URL)

        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/csv")
        assert "product-import-template.csv" in resp["Content-Disposition"]
        assert resp.content.startswith(b"\xef\xbb\xbf")  # Excel-friendly UTF-8
        records = list(_csv.reader(_io.StringIO(resp.content.decode("utf-8-sig"))))
        assert records[0] == IMPORT_COLUMN_NAMES
        assert len(records) == 2  # header + one example row
        assert len(records[1]) == len(IMPORT_COLUMN_NAMES)

    def test_xlsx_template_has_products_and_instructions_sheets(self, admin_client):
        from dashboard.product_import import IMPORT_COLUMN_NAMES, REQUIRED_COLUMN_NAMES
        from openpyxl import load_workbook

        resp = admin_client.get(TEMPLATE_URL, {"file_type": "xlsx"})

        assert resp.status_code == 200
        assert "spreadsheetml" in resp["Content-Type"]
        workbook = load_workbook(_io.BytesIO(resp.content))
        assert workbook.sheetnames == ["products", "instructions"]
        header = [c.value for c in workbook["products"][1]]
        assert header == IMPORT_COLUMN_NAMES
        guide = {
            row[0].value: row[1].value
            for row in workbook["instructions"].iter_rows(min_row=2)
        }
        assert set(guide) == set(IMPORT_COLUMN_NAMES)
        assert {c for c, req in guide.items() if req == "yes"} == set(
            REQUIRED_COLUMN_NAMES
        )

    @pytest.mark.parametrize("file_type", ["csv", "xlsx"])
    def test_the_template_round_trips_through_the_importer(
        self, admin_client, make_category, make_brand, file_type
    ):
        """The example row must be importable as-is once its category/brand exist."""
        from shop.models import Product, ProductVariant

        make_category("Skincare")
        make_brand("Example Brand")
        template = admin_client.get(TEMPLATE_URL, {"file_type": file_type}).content

        dry = post_import(admin_client, template, name=f"t.{file_type}")
        assert dry.status_code == 200, dry.data
        assert dry.data["error_count"] == 0, dry.data["errors"]
        assert dry.data["created_count"] == 1

        commit = post_import(
            admin_client, template, name=f"t.{file_type}", dry_run="false"
        )
        assert commit.data["created_count"] == 1
        variant = ProductVariant.objects.select_related("product", "color").get()
        assert variant.product.name == "Example Hydrating Serum"
        assert (variant.price, variant.stock, variant.volume_ml) == (1_250_000, 25, 30)
        assert variant.color.hex_code == "#E8A0BF"
        assert variant.expiration_date == _date(2028, 1, 15)
        assert Product.objects.get().is_cruelty_free is True

    def test_template_without_its_categories_fails_per_row_not_per_file(
        self, admin_client
    ):
        template = admin_client.get(TEMPLATE_URL).content
        resp = post_import(admin_client, template)
        assert resp.status_code == 200
        assert resp.data["error_count"] == 1
        assert "category: 'Skincare' does not exist" in resp.data["errors"][0]["error"]

    def test_bad_file_type(self, admin_client):
        assert admin_client.get(TEMPLATE_URL, {"file_type": "pdf"}).status_code == 400

    def test_docs_describe_every_column(self):
        """docs/bulk-product-import.md is part of the contract: keep it complete."""
        from dashboard.product_import import IMPORT_COLUMN_NAMES

        doc = (
            _Path(__file__).resolve().parents[2] / "docs" / "bulk-product-import.md"
        ).read_text(encoding="utf-8")
        missing = [c for c in IMPORT_COLUMN_NAMES if f"`{c}`" not in doc]
        assert not missing, f"undocumented columns: {missing}"


@pytest.mark.django_db
class TestBulkImportPermissions:

    def test_non_admin_gets_403_on_both_endpoints(self, customer_client, taxonomy):
        from shop.models import Product

        resp = post_import(customer_client, make_csv(good_rows()), dry_run="false")
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert Product.objects.count() == 0
        assert (
            customer_client.get(TEMPLATE_URL).status_code == status.HTTP_403_FORBIDDEN
        )

    def test_anonymous_is_rejected(self, anon_client):
        assert post_import(anon_client, b"x").status_code in (401, 403)
        assert anon_client.get(TEMPLATE_URL).status_code in (401, 403)

    def test_admin_and_superuser_allowed(
        self, admin_client, superuser_client, taxonomy
    ):
        for client in (admin_client, superuser_client):
            assert post_import(client, make_csv(good_rows())).status_code == 200
            assert client.get(TEMPLATE_URL).status_code == 200

    def test_wrong_methods(self, admin_client):
        assert admin_client.get(IMPORT_URL).status_code == 405
        assert admin_client.post(TEMPLATE_URL).status_code == 405

    def test_import_only_accepts_multipart(self, admin_client):
        resp = admin_client.post(IMPORT_URL, {"dry_run": True}, format="json")
        assert resp.status_code == 415


# ══════════════════════════════════════════════════════════════════════════════
# Catalog export (the reverse of the bulk import)
# ══════════════════════════════════════════════════════════════════════════════

CATALOG_EXPORT_URL = "/api/dashboard/admin/products/bulk-export/"


@pytest.fixture
def export_catalog(db):
    """
    A catalog exercising every export concern: all cosmetics attributes,
    multi-variant products, a colourless / inactive / out-of-stock variant,
    Persian text, text that looks like a formula, an ambiguous category name
    (Face > Care vs Eyes > Care) and a product with no category or brand.

    The LEGACY Product.price / Product.stock are deliberately junk (10 / 0):
    price and stock filters must read the variants, not those dead fields.
    """
    from shop.models import Brand, Category, Color, Product, ProductVariant

    skincare = Category.objects.create(name="Skincare")
    sun_care = Category.objects.create(name="Sun Care", parent=skincare)
    face = Category.objects.create(name="Face")
    eyes = Category.objects.create(name="Eyes")
    face_care = Category.objects.create(name="Care", parent=face)
    eyes_care = Category.objects.create(name="Care", parent=eyes)
    persian_cat = Category.objects.create(name="مراقبت پوست")
    brand_x = Brand.objects.create(name="BrandX")
    brand_y = Brand.objects.create(name="BrandY")
    persian_brand = Brand.objects.create(name="کلینیک")
    rose = Color.objects.create(name="Rose", hex_code="#E8A0BF")
    nude = Color.objects.create(name="Nude", hex_code="#D2B48C")

    def product(name, **kwargs):
        return Product.objects.create(name=name, price=10, stock=0, **kwargs)

    serum = product(
        "Hydra Serum",
        category=skincare,
        brand=brand_x,
        skin_type="dry",
        gender="female",
        is_cruelty_free=True,
        is_organic=True,
        short_description="Lightweight serum",
        description="- Hydrating, gentle",  # leading "-" → quote-prefixed in CSV
        ingredients="Aqua,\nGlycerin,\nSodium Hyaluronate",  # multi-line
        usage_instructions="Apply 2-3 drops.",
        warnings='=HYPERLINK("http://example.com")',  # looks like a formula
        country_of_origin="France",
        irc_regulatory_code="IRC-123",
        is_sale=True,
    )
    sun = product(
        "Sun Cream",
        category=sun_care,
        brand=brand_y,
        skin_type="all",
        spf=50,
        is_new=True,
    )
    persian = product(
        "سرم آبرسان",
        category=persian_cat,
        brand=persian_brand,
        description="کرم مرطوب کننده، مناسب پوست خشک",
    )
    eye = product("Eye Care Cream", category=eyes_care, brand=brand_x)
    face_gel = product("Face Care Gel", category=face_care, brand=brand_x)
    orphan = product("Orphan Product")  # no category, no brand

    def variant(prod, sku, price, **kwargs):
        return ProductVariant.objects.create(
            product=prod, sku=sku, price=price, **kwargs
        )

    v = {
        "rose": variant(
            serum, "SER-ROSE-30", 1_250_000, color=rose, original_price=1_500_000,
            stock=25, low_stock_threshold=8, volume_ml=30, barcode=_valid_ean13(),
            manufacture_date=_date(2026, 1, 15), expiration_date=_date(2028, 1, 15),
            batch_number="B2601",
        ),
        "nude": variant(
            serum, "SER-NUDE-50", 1_850_000, color=nude, stock=0, volume_ml=50,
            is_active=False,
        ),
        "sun": variant(sun, "SUN-100", 900_000, stock=5, weight_g=100),
        "persian": variant(persian, "PER-1", 700_000, stock=3),
        "eye": variant(eye, "EYE-1", 650_000, stock=2),
        "face": variant(face_gel, "FACE-1", 640_000, stock=4),
        "orphan": variant(orphan, "ORPHAN-1", 500_000, stock=1),
    }  # fmt: skip
    return {
        "variants": v,
        "skincare": skincare,
        "brand_x": brand_x,
        "serum": serum,
    }


def get_export(client, fmt="csv", **params):
    """(response, raw bytes) for an export request."""
    resp = client.get(CATALOG_EXPORT_URL, {"format": fmt, **params})
    if getattr(resp, "streaming", False):
        return resp, b"".join(resp.streaming_content)
    return resp, resp.content


def parsed(content, fmt):
    """An export file as the importer sees it: [(row_number, {column: str})]."""
    from dashboard.product_import import parse_import_file

    return parse_import_file(SimpleUploadedFile(f"export.{fmt}", content))


def by_sku(rows):
    return {cells["sku"]: cells for _, cells in rows}


def db_snapshot():
    """Every importable value, read straight from the models, keyed by SKU."""
    from shop.models import ProductVariant

    out = {}
    for v in ProductVariant.objects.select_related("product", "color"):
        p = v.product
        out[v.sku] = {
            "product": (p.id, p.name, p.category_id, p.brand_id),
            "product_attrs": (
                p.skin_type, p.hair_type, p.gender, p.spf, p.is_cruelty_free,
                p.is_vegan, p.is_organic, p.short_description, p.description,
                p.ingredients, p.usage_instructions, p.warnings,
                p.country_of_origin, p.irc_regulatory_code, p.regulatory_verified,
            ),
            "variant": (
                v.color_id, v.price, v.original_price, v.stock,
                v.low_stock_threshold, v.volume_ml, v.weight_g, v.barcode,
                v.manufacture_date, v.expiration_date, v.batch_number, v.is_active,
            ),
        }  # fmt: skip
    return out


SER_ROSE_EXPECTED = {
    "product_name": "Hydra Serum",
    "category": "Skincare",
    "brand": "BrandX",
    "sku": "SER-ROSE-30",
    "color": "Rose",
    "color_hex": "#E8A0BF",
    "price": "1250000",
    "original_price": "1500000",
    "stock": "25",
    "low_stock_threshold": "8",
    "volume_ml": "30",
    "weight_g": "",
    "barcode": _valid_ean13(),
    "manufacture_date": "2026-01-15",
    "expiration_date": "2028-01-15",
    "batch_number": "B2601",
    "is_active": "true",
    "skin_type": "dry",
    "hair_type": "",
    "gender": "female",
    "spf": "",
    "is_cruelty_free": "true",
    "is_vegan": "false",
    "is_organic": "true",
    "short_description": "Lightweight serum",
    "description": "- Hydrating, gentle",
    "ingredients": "Aqua,\nGlycerin,\nSodium Hyaluronate",
    "usage_instructions": "Apply 2-3 drops.",
    "warnings": '=HYPERLINK("http://example.com")',
    "country_of_origin": "France",
    "irc_regulatory_code": "IRC-123",
}


@pytest.mark.django_db
class TestCatalogExportContent:

    @pytest.mark.parametrize("fmt", ["csv", "xlsx"])
    def test_unfiltered_export_has_every_variant_once_with_every_attribute(
        self, admin_client, export_catalog, fmt
    ):
        from dashboard.product_import import IMPORT_COLUMN_NAMES

        resp, content = get_export(admin_client, fmt)

        assert resp.status_code == 200
        rows = parsed(content, fmt)
        assert len(rows) == 7  # one row per VARIANT, none missing or doubled
        skus = [cells["sku"] for _, cells in rows]
        assert sorted(skus) == sorted(
            ["SER-ROSE-30", "SER-NUDE-50", "SUN-100", "PER-1", "EYE-1", "FACE-1",
             "ORPHAN-1"]
        )  # fmt: skip
        assert all(list(cells) == IMPORT_COLUMN_NAMES for _, cells in rows)
        cells = by_sku(rows)
        # every cosmetics attribute, from the actual Product/ProductVariant data
        assert cells["SER-ROSE-30"] == SER_ROSE_EXPECTED
        # a second variant of the same product repeats the parent's attributes
        nude = cells["SER-NUDE-50"]
        for column in ("product_name", "category", "brand", "skin_type", "gender",
                       "is_cruelty_free", "is_organic", "description", "ingredients",
                       "warnings", "country_of_origin", "irc_regulatory_code"):  # fmt: skip
            assert nude[column] == SER_ROSE_EXPECTED[column], column
        assert (nude["color"], nude["color_hex"], nude["price"], nude["stock"]) == (
            "Nude",
            "#D2B48C",
            "1850000",
            "0",
        )
        assert nude["is_active"] == "false"  # inactive variants are exported
        assert nude["original_price"] == "" and nude["barcode"] == ""
        # colourless, weight-measured, SPF product
        sun = cells["SUN-100"]
        assert (sun["color"], sun["color_hex"], sun["weight_g"], sun["volume_ml"]) == (
            "",
            "",
            "100",
            "",
        )
        assert (sun["spf"], sun["skin_type"], sun["gender"]) == ("50", "all", "unisex")
        assert (sun["category"], sun["brand"]) == ("Sun Care", "BrandY")
        # Persian text survives untouched
        persian = cells["PER-1"]
        assert persian["product_name"] == "سرم آبرسان"
        assert persian["brand"] == "کلینیک" and persian["category"] == "مراقبت پوست"
        assert persian["description"] == "کرم مرطوب کننده، مناسب پوست خشک"
        # no category / brand → blank cells
        assert cells["ORPHAN-1"]["category"] == "" and cells["ORPHAN-1"]["brand"] == ""

    def test_ambiguous_category_names_are_written_as_full_paths(
        self, admin_client, export_catalog
    ):
        cells = by_sku(parsed(get_export(admin_client)[1], "csv"))
        assert cells["EYE-1"]["category"] == "Eyes > Care"
        assert cells["FACE-1"]["category"] == "Face > Care"
        assert cells["SUN-100"]["category"] == "Sun Care"  # unique → plain name

    def test_a_products_variants_are_adjacent(self, admin_client, export_catalog):
        rows = parsed(get_export(admin_client)[1], "csv")
        names = [cells["product_name"] for _, cells in rows]
        assert names == sorted(names, key=lambda n: (n,))  # grouped by name
        serum_positions = [i for i, n in enumerate(names) if n == "Hydra Serum"]
        assert serum_positions == list(
            range(serum_positions[0], serum_positions[0] + 2)
        )

    def test_empty_catalog_exports_just_the_header(self, admin_client, db):
        from dashboard.product_import import IMPORT_COLUMN_NAMES

        _, content = get_export(admin_client)
        lines = content.decode("utf-8-sig").splitlines()
        assert lines == [",".join(IMPORT_COLUMN_NAMES)]
        resp, xlsx = get_export(admin_client, "xlsx")
        assert resp.status_code == 200 and xlsx.startswith(b"PK")

    def test_export_row_covers_exactly_the_import_schema(self, export_catalog):
        from dashboard.product_import import (
            IMPORT_COLUMN_NAMES,
            export_category_labels,
            export_row,
        )

        row = export_row(export_catalog["variants"]["rose"], export_category_labels())
        assert list(row) == IMPORT_COLUMN_NAMES


@pytest.mark.django_db
class TestCatalogExportFilters:

    def _skus(self, client, **params):
        resp, content = get_export(client, "csv", **params)
        assert resp.status_code == 200, content
        records = list(_csv.reader(_io.StringIO(content.decode("utf-8-sig"))))
        sku_col = records[0].index("sku")
        return {record[sku_col] for record in records[1:]}

    def test_category_filter_only_returns_that_categorys_variants(
        self, admin_client, export_catalog
    ):
        skus = self._skus(admin_client, category=export_catalog["skincare"].id)
        # Hydra Serum's two variants; Sun Cream lives in the CHILD category
        # (exact match, same as the admin product list).
        assert skus == {"SER-ROSE-30", "SER-NUDE-50"}

    def test_brand_filter(self, admin_client, export_catalog):
        skus = self._skus(admin_client, brand=export_catalog["brand_x"].id)
        assert skus == {"SER-ROSE-30", "SER-NUDE-50", "EYE-1", "FACE-1"}

    def test_product_flag_filters(self, admin_client, export_catalog):
        assert self._skus(admin_client, is_sale="true") == {
            "SER-ROSE-30",
            "SER-NUDE-50",
        }
        assert self._skus(admin_client, is_new="true") == {"SUN-100"}

    def test_search_uses_the_product_lists_search_fields(
        self, admin_client, export_catalog
    ):
        assert self._skus(admin_client, search="serum") == {
            "SER-ROSE-30",
            "SER-NUDE-50",
        }
        assert self._skus(admin_client, search="BrandY") == {"SUN-100"}  # brand name

    def test_filters_combine(self, admin_client, export_catalog):
        skus = self._skus(
            admin_client, brand=export_catalog["brand_x"].id, is_sale="true"
        )
        assert skus == {"SER-ROSE-30", "SER-NUDE-50"}

    def test_price_and_stock_filters_read_the_variants_not_legacy_product_fields(
        self, admin_client, export_catalog
    ):
        # Every legacy Product.price is 10 and Product.stock 0 in this fixture;
        # these only work if the real variant values are used.
        assert self._skus(admin_client, min_price=1_000_000) == {
            "SER-ROSE-30",
            "SER-NUDE-50",
        }
        assert self._skus(admin_client, max_price=640_000) == {
            "FACE-1",
            "ORPHAN-1",
        }
        assert self._skus(admin_client, min_price=650_000, max_price=900_000) == {
            "SUN-100",
            "PER-1",
            "EYE-1",
        }
        in_stock = self._skus(admin_client, in_stock="true")
        assert "SER-NUDE-50" not in in_stock and "SER-ROSE-30" in in_stock
        assert self._skus(admin_client, in_stock="false") == {"SER-NUDE-50"}

    def test_product_and_variant_level_filters_combine(
        self, admin_client, export_catalog
    ):
        skus = self._skus(
            admin_client, brand=export_catalog["brand_x"].id, min_price=1_500_000
        )
        assert skus == {"SER-NUDE-50"}

    @pytest.mark.parametrize(
        "params",
        [
            {"category": "abc"},
            {"brand": "x"},
            {"min_price": "cheap"},
            {"in_stock": "maybe"},
            {"in_stock": "ture"},
            {"is_sale": "yes"},
            {"is_new": "1"},
        ],
    )
    def test_malformed_filters_are_a_400_not_an_unfiltered_export(
        self, admin_client, export_catalog, params
    ):
        resp = admin_client.get(CATALOG_EXPORT_URL, params)
        assert resp.status_code == 400
        assert list(resp.data)[0] in params

    def test_filtered_to_nothing_is_a_header_only_file(
        self, admin_client, export_catalog
    ):
        assert self._skus(admin_client, search="no-such-product") == set()


@pytest.mark.django_db
class TestCatalogExportRoundTrip:
    """The point of the task: what we export is exactly what the importer reads."""

    @pytest.mark.parametrize("fmt", ["csv", "xlsx"])
    def test_exported_file_reimports_as_pure_updates_with_zero_errors(
        self, admin_client, export_catalog, fmt
    ):
        _, content = get_export(admin_client, fmt)

        resp = post_import(admin_client, content, name=f"export.{fmt}")  # dry run

        assert resp.status_code == 200, resp.data
        assert resp.data["errors"] == [], resp.data["errors"]
        assert resp.data["error_count"] == 0
        assert resp.data["total_rows"] == 7
        assert resp.data["created_count"] == 0  # nothing mistaken for a new row
        assert resp.data["updated_count"] == 7
        assert resp.data["products_created_count"] == 0
        assert {r["action"] for r in resp.data["preview"]} == {"updated"}
        assert {r["sku"] for r in resp.data["preview"]} == {
            "SER-ROSE-30", "SER-NUDE-50", "SUN-100", "PER-1", "EYE-1", "FACE-1",
            "ORPHAN-1",
        }  # fmt: skip

    @pytest.mark.parametrize("fmt", ["csv", "xlsx"])
    def test_committing_the_exported_file_changes_nothing(
        self, admin_client, export_catalog, fmt
    ):
        from shop.models import (
            Brand,
            Category,
            Color,
            Product,
            ProductVariant,
            StockMovement,
        )

        before = db_snapshot()
        counts = (
            Product.objects.count(),
            ProductVariant.objects.count(),
            Category.objects.count(),
            Brand.objects.count(),
            Color.objects.count(),
            StockMovement.objects.count(),
        )
        _, content = get_export(admin_client, fmt)

        resp = post_import(admin_client, content, name=f"export.{fmt}", dry_run="false")

        assert resp.data["error_count"] == 0 and resp.data["updated_count"] == 7
        assert db_snapshot() == before  # every value, byte for byte
        assert counts == (
            Product.objects.count(),
            ProductVariant.objects.count(),
            Category.objects.count(),
            Brand.objects.count(),
            Color.objects.count(),
            StockMovement.objects.count(),
        )

    def test_filtered_exports_round_trip_too(self, admin_client, export_catalog):
        _, content = get_export(admin_client, "csv", brand=export_catalog["brand_x"].id)
        resp = post_import(admin_client, content)
        assert resp.data["error_count"] == 0
        assert (resp.data["created_count"], resp.data["updated_count"]) == (0, 4)

    @pytest.mark.parametrize("fmt", ["csv", "xlsx"])
    def test_export_edit_reimport_changes_only_what_was_edited(
        self, admin_client, export_catalog, fmt
    ):
        from shop.models import ProductVariant

        before = db_snapshot()
        _, content = get_export(admin_client, fmt)
        edited = edit_cell(
            content, fmt, "SER-ROSE-30", {"price": "1300000", "stock": "40"}
        )

        resp = post_import(admin_client, edited, name=f"edited.{fmt}", dry_run="false")

        assert resp.data["error_count"] == 0 and resp.data["updated_count"] == 7
        rose = ProductVariant.objects.get(sku="SER-ROSE-30")
        assert (rose.price, rose.stock) == (1_300_000, 40)
        after = db_snapshot()
        changed = {sku for sku in before if before[sku] != after[sku]}
        assert changed == {"SER-ROSE-30"}  # nothing else moved

    def test_csv_and_xlsx_exports_hold_equivalent_data(
        self, admin_client, export_catalog
    ):
        csv_rows = parsed(get_export(admin_client, "csv")[1], "csv")
        xlsx_rows = parsed(get_export(admin_client, "xlsx")[1], "xlsx")
        assert csv_rows == xlsx_rows


def edit_cell(content, fmt, sku, changes):
    """Edit one variant's cells in an exported file, the way an admin would."""
    from dashboard.product_import import IMPORT_COLUMN_NAMES

    if fmt == "csv":
        records = list(_csv.reader(_io.StringIO(content.decode("utf-8-sig"))))
        sku_col = records[0].index("sku")
        for record in records[1:]:
            if record[sku_col] == sku:
                for column, value in changes.items():
                    record[IMPORT_COLUMN_NAMES.index(column)] = value
        buffer = _io.StringIO()
        _csv.writer(buffer).writerows(records)
        return buffer.getvalue().encode("utf-8")

    from openpyxl import load_workbook

    workbook = load_workbook(_io.BytesIO(content))
    sheet = workbook["products"]
    sku_col = IMPORT_COLUMN_NAMES.index("sku") + 1
    for row in range(2, sheet.max_row + 1):
        if sheet.cell(row=row, column=sku_col).value == sku:
            for column, value in changes.items():
                sheet.cell(
                    row=row, column=IMPORT_COLUMN_NAMES.index(column) + 1
                ).value = int(value)
    buffer = _io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.mark.django_db
class TestCatalogExportFileFormats:

    def test_csv_is_streamed_utf8_with_bom_and_protects_formula_cells(
        self, admin_client, export_catalog
    ):
        resp, content = get_export(admin_client, "csv")

        assert resp.streaming is True
        assert resp["Content-Type"].startswith("text/csv")
        assert resp["Content-Disposition"].startswith(
            'attachment; filename="catalog_export_'
        )
        assert resp["Content-Disposition"].endswith('.csv"')
        assert content.startswith(b"\xef\xbb\xbf")
        text = content.decode("utf-8-sig")
        # spreadsheet apps would execute these; quote-prefixed like the orders export
        assert "'- Hydrating, gentle" in text
        assert "'=HYPERLINK" in text
        # …and the importer reads them back as the original text
        cells = by_sku(parsed(content, "csv"))["SER-ROSE-30"]
        assert cells["description"] == "- Hydrating, gentle"
        assert cells["warnings"] == '=HYPERLINK("http://example.com")'

    def test_xlsx_has_typed_cells_and_stores_formula_lookalikes_as_text(
        self, admin_client, export_catalog
    ):
        from openpyxl import load_workbook

        resp, content = get_export(admin_client, "xlsx")

        assert resp["Content-Type"].endswith("spreadsheetml.sheet")
        assert resp["Content-Disposition"].endswith('.xlsx"')
        sheet = load_workbook(_io.BytesIO(content))["products"]
        from dashboard.product_import import IMPORT_COLUMN_NAMES

        header = [c.value for c in sheet[1]]
        assert header == IMPORT_COLUMN_NAMES
        row = next(
            r
            for r in sheet.iter_rows(min_row=2)
            if r[header.index("sku")].value == "SER-ROSE-30"
        )
        cell = {name: row[i] for i, name in enumerate(header)}
        assert cell["price"].value == 1_250_000 and isinstance(cell["price"].value, int)
        assert cell["is_active"].value is True
        assert cell["is_cruelty_free"].value is True
        assert cell["expiration_date"].value.date() == _date(2028, 1, 15)
        assert isinstance(cell["barcode"].value, str)  # text: keeps leading zeros
        # text that looks like a formula is a string cell, never evaluated
        assert cell["warnings"].data_type == "s"
        assert cell["warnings"].value == '=HYPERLINK("http://example.com")'

    def test_control_characters_do_not_break_the_xlsx_export(
        self, admin_client, export_catalog
    ):
        product = export_catalog["serum"]
        product.description = "bell\x07 and vertical tab\x0b here"
        product.save()
        resp, content = get_export(admin_client, "xlsx")
        assert resp.status_code == 200 and content.startswith(b"PK")

    def test_format_can_be_chosen_by_query_param_file_type_or_accept_header(
        self, admin_client, export_catalog
    ):
        assert get_export(admin_client, "xlsx")[1].startswith(b"PK")
        assert admin_client.get(
            CATALOG_EXPORT_URL, {"file_type": "xlsx"}
        ).content.startswith(b"PK")
        assert admin_client.get(CATALOG_EXPORT_URL).streaming  # default: CSV
        accept_xlsx = admin_client.get(
            CATALOG_EXPORT_URL,
            HTTP_ACCEPT="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert accept_xlsx.content.startswith(b"PK")
        assert admin_client.get(CATALOG_EXPORT_URL, HTTP_ACCEPT="text/csv").streaming

    def test_unknown_formats_are_rejected(self, admin_client, export_catalog):
        assert (
            admin_client.get(CATALOG_EXPORT_URL, {"file_type": "pdf"}).status_code
            == 400
        )
        assert (
            admin_client.get(CATALOG_EXPORT_URL, {"file_type": "json"}).status_code
            == 400
        )
        assert (
            admin_client.get(CATALOG_EXPORT_URL, {"format": "pdf"}).status_code == 404
        )

    def test_xlsx_export_is_capped_but_csv_is_not(
        self, admin_client, export_catalog, monkeypatch
    ):
        from dashboard import product_import

        monkeypatch.setattr(product_import, "MAX_XLSX_EXPORT_ROWS", 3)

        resp = admin_client.get(CATALOG_EXPORT_URL, {"format": "xlsx"})
        assert resp.status_code == 400
        assert (
            "format=csv" in resp.data["detail"] and "7 variants" in resp.data["detail"]
        )
        # a narrower filter fits under the cap
        small = admin_client.get(
            CATALOG_EXPORT_URL, {"format": "xlsx", "is_new": "true"}
        )
        assert small.status_code == 200
        assert len(parsed(get_export(admin_client, "csv")[1], "csv")) == 7


@pytest.mark.django_db
class TestImporterReadsExportedCsvCells:

    def test_quote_prefix_on_formula_characters_is_removed_on_csv_import_only(self):
        from dashboard.product_import import parse_import_file

        csv_bytes = (
            "product_name,category,price,description,warnings,ingredients\n"
            "A,C,1,'- bullet,'=SUM(1),'plain quote\n"
        ).encode()
        ((_, cells),) = parse_import_file(SimpleUploadedFile("a.csv", csv_bytes))
        assert cells["description"] == "- bullet"
        assert cells["warnings"] == "=SUM(1)"
        assert cells["ingredients"] == "'plain quote"  # not a formula lead: untouched

    def test_xlsx_cells_are_never_unprefixed(self):
        from dashboard.product_import import parse_import_file

        content = make_xlsx(
            [
                {
                    "product_name": "A",
                    "category": "C",
                    "price": "1",
                    "description": "'- x",
                }
            ]
        )
        ((_, cells),) = parse_import_file(SimpleUploadedFile("a.xlsx", content))
        assert cells["description"] == "'- x"

    def test_docs_describe_the_export(self):
        doc = (
            _Path(__file__).resolve().parents[2] / "docs" / "bulk-product-import.md"
        ).read_text(encoding="utf-8")
        assert "bulk-export" in doc and "round-trip" in doc.lower()


@pytest.mark.django_db
class TestCatalogExportPermissions:

    def test_non_admin_gets_403(self, customer_client, export_catalog):
        for params in ({}, {"format": "xlsx"}, {"format": "csv"}):
            assert (
                customer_client.get(CATALOG_EXPORT_URL, params).status_code
                == status.HTTP_403_FORBIDDEN
            )

    def test_anonymous_is_rejected(self, anon_client, export_catalog):
        assert anon_client.get(CATALOG_EXPORT_URL).status_code in (401, 403)

    def test_admin_and_superuser_allowed(
        self, admin_client, superuser_client, export_catalog
    ):
        assert admin_client.get(CATALOG_EXPORT_URL).status_code == 200
        assert superuser_client.get(CATALOG_EXPORT_URL).status_code == 200

    def test_write_methods_are_not_allowed(self, admin_client):
        assert admin_client.post(CATALOG_EXPORT_URL).status_code == 405
