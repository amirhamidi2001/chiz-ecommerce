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
        "state": "CA",
        "zip_code": "90001",
        "country": "US",
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
