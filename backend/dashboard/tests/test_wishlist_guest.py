"""
Guest (session-based) wishlist — mirrors the structure of the Epic 5
Task 5.1.1.2 / 5.1.1.3 cart tests (cart/tests/test_cart.py and the
login/register/OTP merge tests in accounts/tests).

Sections:
  1. Model constraints         (acceptance criterion 5)
  2. Owner-kwargs helper
  3. Anonymous API behaviour   (criteria 1 + 2)
  4. merge_session_wishlist_into_user_wishlist() unit tests
  5. Merge through the real login / register / OTP endpoints (criterion 3)
  6. Authenticated behaviour unchanged (criterion 4 — the pre-existing
     TestWishlistViewSet in test_views.py is the main regression net and
     is unmodified apart from the 401 -> 200 permission assumption)
"""

from datetime import timedelta

import pytest
from accounts.models import OTPCode
from accounts.services.otp import generate_otp
from dashboard.models import Wishlist
from dashboard.services import (
    get_wishlist_owner_kwargs,
    merge_session_wishlist_into_user_wishlist,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import RequestFactory
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

WISHLIST_URL = "/api/dashboard/wishlist/"
LOGIN_URL = "/api/auth/login/"
REGISTER_URL = "/api/auth/register/"
OTP_REQUEST_URL = "/api/auth/otp/request/"
OTP_VERIFY_URL = "/api/auth/otp/verify/"
PASSWORD = "testPass123!"  # make_user's default


def wish_detail(pk):
    return f"{WISHLIST_URL}{pk}/"


def _results(res):
    return res.data.get("results", res.data)


@pytest.fixture(autouse=True)
def _clear_cache():
    """AnonRateThrottle / AuthSensitiveRateThrottle accumulate in the cache."""
    cache.clear()
    yield
    cache.clear()


def _request_with_session(user=None):
    request = RequestFactory().get(WISHLIST_URL)
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    request.user = user or AnonymousUser()
    return request


# ══════════════════════════════════════════════════════════════════════════════
# 1. Model constraints
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWishlistConstraints:

    def test_session_only_row_saves(self, make_product):
        item = Wishlist.objects.create(session_key="sess-a", product=make_product())
        item.refresh_from_db()
        assert item.user is None
        assert item.session_key == "sess-a"

    def test_row_with_both_user_and_session_key_fails(self, customer, make_product):
        with pytest.raises(IntegrityError), transaction.atomic():
            Wishlist.objects.create(
                user=customer, session_key="sess-a", product=make_product()
            )

    def test_row_with_neither_user_nor_session_key_fails(self, make_product):
        with pytest.raises(IntegrityError), transaction.atomic():
            Wishlist.objects.create(product=make_product())

    def test_two_session_rows_same_session_and_product_fail(self, make_product):
        product = make_product()
        Wishlist.objects.create(session_key="sess-a", product=product)
        with pytest.raises(IntegrityError), transaction.atomic():
            Wishlist.objects.create(session_key="sess-a", product=product)

    def test_same_product_in_different_sessions_is_allowed(self, make_product):
        product = make_product()
        Wishlist.objects.create(session_key="sess-a", product=product)
        Wishlist.objects.create(session_key="sess-b", product=product)
        assert Wishlist.objects.filter(product=product).count() == 2

    def test_different_products_in_same_session_is_allowed(self, make_product):
        Wishlist.objects.create(session_key="sess-a", product=make_product())
        Wishlist.objects.create(session_key="sess-a", product=make_product())
        assert Wishlist.objects.filter(session_key="sess-a").count() == 2

    def test_same_product_for_a_user_and_a_session_is_allowed(
        self, customer, make_product
    ):
        product = make_product()
        Wishlist.objects.create(user=customer, product=product)
        Wishlist.objects.create(session_key="sess-a", product=product)
        assert Wishlist.objects.filter(product=product).count() == 2

    def test_user_product_uniqueness_still_enforced(self, customer, make_product):
        product = make_product()
        Wishlist.objects.create(user=customer, product=product)
        with pytest.raises(IntegrityError), transaction.atomic():
            Wishlist.objects.create(user=customer, product=product)

    def test_str_for_session_row_does_not_crash(self, make_product):
        item = Wishlist.objects.create(
            session_key="sess-a", product=make_product(name="Lipstick")
        )
        assert "sess-a" in str(item)
        assert "Lipstick" in str(item)


# ══════════════════════════════════════════════════════════════════════════════
# 2. get_wishlist_owner_kwargs()
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGetWishlistOwnerKwargs:

    def test_authenticated_request_returns_user(self, customer):
        request = _request_with_session(user=customer)
        assert get_wishlist_owner_kwargs(request) == {"user": customer}

    def test_anonymous_request_returns_existing_session_key(self):
        request = _request_with_session()
        assert get_wishlist_owner_kwargs(request) == {
            "session_key": request.session.session_key
        }

    def test_anonymous_request_creates_a_session_if_none_exists(self):
        request = RequestFactory().get(WISHLIST_URL)
        SessionMiddleware(lambda r: None).process_request(request)
        request.user = AnonymousUser()
        assert request.session.session_key is None

        kwargs = get_wishlist_owner_kwargs(request)

        assert kwargs["session_key"]
        assert kwargs["session_key"] == request.session.session_key


# ══════════════════════════════════════════════════════════════════════════════
# 3. Anonymous API behaviour
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAnonymousWishlistAPI:

    # ── criterion 1: add / list / remove via session, with persistence ──────

    def test_anonymous_get_returns_200_and_empty_list(self, anon_client):
        res = anon_client.get(WISHLIST_URL)
        assert res.status_code == status.HTTP_200_OK
        assert _results(res) == []

    def test_anonymous_get_sets_a_session_cookie(self, anon_client):
        res = anon_client.get(WISHLIST_URL)
        assert res.cookies[settings.SESSION_COOKIE_NAME].value

    def test_anonymous_add_creates_a_session_owned_row(self, anon_client, make_product):
        product = make_product()
        res = anon_client.post(WISHLIST_URL, {"product_id": product.pk})
        assert res.status_code == status.HTTP_201_CREATED
        assert res.data["product"]["id"] == product.pk

        item = Wishlist.objects.get(pk=res.data["id"])
        assert item.user is None
        assert item.session_key == anon_client.session.session_key

    def test_anonymous_session_persists_across_requests(
        self, anon_client, make_product
    ):
        """Same APIClient = same session cookie is reused."""
        p1, p2 = make_product(), make_product()
        anon_client.post(WISHLIST_URL, {"product_id": p1.pk})
        anon_client.post(WISHLIST_URL, {"product_id": p2.pk})

        res = anon_client.get(WISHLIST_URL)

        assert res.status_code == status.HTTP_200_OK
        assert {i["product"]["id"] for i in _results(res)} == {p1.pk, p2.pk}

    def test_anonymous_can_remove_own_item(self, anon_client, make_product):
        product = make_product()
        item_id = anon_client.post(WISHLIST_URL, {"product_id": product.pk}).data["id"]

        del_res = anon_client.delete(wish_detail(item_id))

        assert del_res.status_code == status.HTTP_204_NO_CONTENT
        assert _results(anon_client.get(WISHLIST_URL)) == []
        assert not Wishlist.objects.filter(pk=item_id).exists()

    def test_anonymous_duplicate_add_returns_400(self, anon_client, make_product):
        product = make_product()
        anon_client.post(WISHLIST_URL, {"product_id": product.pk})
        res = anon_client.post(WISHLIST_URL, {"product_id": product.pk})
        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "product_id" in res.data
        assert Wishlist.objects.count() == 1

    def test_anonymous_add_unknown_product_returns_400(self, anon_client):
        res = anon_client.post(WISHLIST_URL, {"product_id": 999999})
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    # ── criterion 2: independent sessions ───────────────────────────────────

    def test_two_anonymous_sessions_have_independent_wishlists(self, make_product):
        client_a, client_b = APIClient(), APIClient()
        product = make_product()

        assert (
            client_a.post(WISHLIST_URL, {"product_id": product.pk}).status_code
            == status.HTTP_201_CREATED
        )

        assert len(_results(client_a.get(WISHLIST_URL))) == 1
        assert _results(client_b.get(WISHLIST_URL)) == []

        # Both may independently save the very same product.
        assert (
            client_b.post(WISHLIST_URL, {"product_id": product.pk}).status_code
            == status.HTTP_201_CREATED
        )
        assert Wishlist.objects.filter(product=product).count() == 2
        assert client_a.session.session_key != client_b.session.session_key

    def test_removing_in_one_session_does_not_affect_another(self, make_product):
        client_a, client_b = APIClient(), APIClient()
        product = make_product()
        id_a = client_a.post(WISHLIST_URL, {"product_id": product.pk}).data["id"]
        client_b.post(WISHLIST_URL, {"product_id": product.pk})

        client_a.delete(wish_detail(id_a))

        assert _results(client_a.get(WISHLIST_URL)) == []
        assert len(_results(client_b.get(WISHLIST_URL))) == 1

    def test_anonymous_cannot_delete_another_sessions_item(
        self, anon_client, make_product
    ):
        other = Wishlist.objects.create(
            session_key="someone-else", product=make_product()
        )
        res = anon_client.delete(wish_detail(other.pk))
        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert Wishlist.objects.filter(pk=other.pk).exists()

    def test_anonymous_cannot_delete_an_authenticated_users_item(
        self, anon_client, customer, make_product
    ):
        others = Wishlist.objects.create(user=customer, product=make_product())
        res = anon_client.delete(wish_detail(others.pk))
        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert Wishlist.objects.filter(pk=others.pk).exists()

    def test_anonymous_list_never_includes_user_owned_rows(
        self, anon_client, customer, make_product
    ):
        """filter(session_key=...) must never degrade to `user IS NULL`-style
        matching that leaks other people's rows."""
        Wishlist.objects.create(user=customer, product=make_product())
        Wishlist.objects.create(session_key="someone-else", product=make_product())
        assert _results(anon_client.get(WISHLIST_URL)) == []


# ══════════════════════════════════════════════════════════════════════════════
# 4. merge_session_wishlist_into_user_wishlist() — unit level
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMergeSessionWishlistService:

    def test_moves_session_items_onto_user(self, customer, make_product):
        request = _request_with_session()
        key = request.session.session_key
        p1, p2 = make_product(), make_product()
        Wishlist.objects.create(session_key=key, product=p1)
        Wishlist.objects.create(session_key=key, product=p2)

        merge_session_wishlist_into_user_wishlist(request, customer)

        mine = Wishlist.objects.filter(user=customer)
        assert {i.product_id for i in mine} == {p1.pk, p2.pk}
        assert all(i.session_key is None for i in mine)
        assert not Wishlist.objects.filter(session_key=key).exists()

    def test_does_not_double_add_a_product_already_on_the_account(
        self, customer, make_product
    ):
        request = _request_with_session()
        key = request.session.session_key
        shared, guest_only = make_product(), make_product()
        existing = Wishlist.objects.create(user=customer, product=shared)
        Wishlist.objects.create(session_key=key, product=shared)
        Wishlist.objects.create(session_key=key, product=guest_only)

        merge_session_wishlist_into_user_wishlist(request, customer)

        assert Wishlist.objects.filter(user=customer, product=shared).count() == 1
        # The account's original row survives untouched.
        assert Wishlist.objects.get(user=customer, product=shared).pk == existing.pk
        assert Wishlist.objects.filter(user=customer, product=guest_only).count() == 1
        assert Wishlist.objects.filter(user=customer).count() == 2
        # Skipped duplicate session row is cleaned up too.
        assert not Wishlist.objects.filter(session_key=key).exists()

    def test_preserves_added_at_of_moved_items(self, customer, make_product):
        request = _request_with_session()
        key = request.session.session_key
        item = Wishlist.objects.create(session_key=key, product=make_product())
        long_ago = timezone.now() - timedelta(days=30)
        Wishlist.objects.filter(pk=item.pk).update(added_at=long_ago)

        merge_session_wishlist_into_user_wishlist(request, customer)

        moved = Wishlist.objects.get(user=customer)
        assert moved.added_at == long_ago

    def test_leaves_other_sessions_and_users_untouched(
        self, customer, make_user, make_product
    ):
        request = _request_with_session()
        key = request.session.session_key
        Wishlist.objects.create(session_key=key, product=make_product())
        other_session = Wishlist.objects.create(
            session_key="other-sess", product=make_product()
        )
        other_user = Wishlist.objects.create(
            user=make_user(email="bystander@example.com"), product=make_product()
        )

        merge_session_wishlist_into_user_wishlist(request, customer)

        other_session.refresh_from_db()
        other_user.refresh_from_db()
        assert other_session.session_key == "other-sess"
        assert other_user.user.email == "bystander@example.com"

    def test_no_session_items_is_a_noop(self, customer, make_product):
        request = _request_with_session()
        mine = Wishlist.objects.create(user=customer, product=make_product())
        merge_session_wishlist_into_user_wishlist(request, customer)  # no raise
        assert list(Wishlist.objects.all()) == [mine]

    def test_no_session_key_at_all_does_not_error(self, customer):
        request = RequestFactory().get(WISHLIST_URL)
        SessionMiddleware(lambda r: None).process_request(request)
        # No .save() — session_key is None.
        merge_session_wishlist_into_user_wishlist(request, customer)  # no raise
        assert not Wishlist.objects.exists()

    def test_calling_twice_in_a_row_is_safe(self, customer, make_product):
        request = _request_with_session()
        Wishlist.objects.create(
            session_key=request.session.session_key, product=make_product()
        )
        merge_session_wishlist_into_user_wishlist(request, customer)
        merge_session_wishlist_into_user_wishlist(request, customer)  # no raise
        assert Wishlist.objects.filter(user=customer).count() == 1


# ══════════════════════════════════════════════════════════════════════════════
# 5. Merge through the real entry points (criterion 3)
# ══════════════════════════════════════════════════════════════════════════════


def _guest_saves(client, *products):
    for product in products:
        res = client.post(WISHLIST_URL, {"product_id": product.pk})
        assert res.status_code == status.HTTP_201_CREATED
    return client.session.session_key


@pytest.mark.django_db
class TestLoginMergesGuestWishlist:

    def test_login_merges_session_wishlist_into_account(
        self, anon_client, customer, make_product
    ):
        p1, p2 = make_product(), make_product()
        session_key = _guest_saves(anon_client, p1, p2)

        res = anon_client.post(
            LOGIN_URL, {"email": customer.email, "password": PASSWORD}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK
        assert {i.product_id for i in Wishlist.objects.filter(user=customer)} == {
            p1.pk,
            p2.pk,
        }
        assert not Wishlist.objects.filter(session_key=session_key).exists()

    def test_login_does_not_double_add_already_wishlisted_product(
        self, anon_client, customer, make_product
    ):
        shared, guest_only = make_product(), make_product()
        existing = Wishlist.objects.create(user=customer, product=shared)
        session_key = _guest_saves(anon_client, shared, guest_only)

        res = anon_client.post(
            LOGIN_URL, {"email": customer.email, "password": PASSWORD}, format="json"
        )

        assert res.status_code == status.HTTP_200_OK
        assert Wishlist.objects.filter(user=customer, product=shared).count() == 1
        assert Wishlist.objects.get(user=customer, product=shared).pk == existing.pk
        assert Wishlist.objects.filter(user=customer).count() == 2
        assert not Wishlist.objects.filter(session_key=session_key).exists()

    def test_merged_items_are_visible_to_the_now_authenticated_user(
        self, anon_client, customer, make_product
    ):
        product = make_product()
        _guest_saves(anon_client, product)

        login = anon_client.post(
            LOGIN_URL, {"email": customer.email, "password": PASSWORD}, format="json"
        )
        authed = APIClient()
        authed.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        res = authed.get(WISHLIST_URL)

        assert [i["product"]["id"] for i in _results(res)] == [product.pk]

    def test_failed_login_does_not_merge_or_discard_the_guest_wishlist(
        self, anon_client, customer, make_product
    ):
        session_key = _guest_saves(anon_client, make_product())

        res = anon_client.post(
            LOGIN_URL,
            {"email": customer.email, "password": "wrong-password"},
            format="json",
        )

        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert Wishlist.objects.filter(session_key=session_key).count() == 1
        assert not Wishlist.objects.filter(user=customer).exists()

    def test_login_with_no_guest_wishlist_is_unaffected(self, anon_client, customer):
        res = anon_client.post(
            LOGIN_URL, {"email": customer.email, "password": PASSWORD}, format="json"
        )
        assert res.status_code == status.HTTP_200_OK
        assert not Wishlist.objects.exists()


@pytest.mark.django_db
class TestRegisterMergesGuestWishlist:

    def test_register_merges_session_wishlist_into_new_account(
        self, anon_client, make_product
    ):
        product = make_product()
        session_key = _guest_saves(anon_client, product)

        res = anon_client.post(
            REGISTER_URL,
            {
                "email": "newshopper@example.com",
                "first_name": "New",
                "last_name": "Shopper",
                "password": "SecurePass123!",
            },
            format="json",
        )

        assert res.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email="newshopper@example.com")
        assert [i.product_id for i in Wishlist.objects.filter(user=user)] == [
            product.pk
        ]
        assert not Wishlist.objects.filter(session_key=session_key).exists()


@pytest.mark.django_db
class TestOTPVerifyMergesGuestWishlist:

    def _otp_verify(self, client, phone):
        client.post(OTP_REQUEST_URL, {"phone_number": phone}, format="json")
        OTPCode.objects.filter(phone_number=phone).delete()
        code = generate_otp(phone, "login")
        return client.post(
            OTP_VERIFY_URL, {"phone_number": phone, "code": code}, format="json"
        )

    def test_otp_login_merges_into_existing_account(self, anon_client, make_product):
        phone = "09121110099"
        existing_user = User.objects.create_user(
            email=None, phone_number=phone, is_verified=True
        )
        shared, guest_only = make_product(), make_product()
        Wishlist.objects.create(user=existing_user, product=shared)
        session_key = _guest_saves(anon_client, shared, guest_only)

        res = self._otp_verify(anon_client, phone)

        assert res.status_code == status.HTTP_200_OK
        assert Wishlist.objects.filter(user=existing_user).count() == 2
        assert Wishlist.objects.filter(user=existing_user, product=shared).count() == 1
        assert not Wishlist.objects.filter(session_key=session_key).exists()

    def test_otp_signup_merges_into_brand_new_account(self, anon_client, make_product):
        """The is_new_user=True branch gets the same merge treatment."""
        phone = "09121110088"
        product = make_product()
        _guest_saves(anon_client, product)

        res = self._otp_verify(anon_client, phone)

        assert res.status_code == status.HTTP_201_CREATED
        new_user = User.objects.get(phone_number=phone)
        assert [i.product_id for i in Wishlist.objects.filter(user=new_user)] == [
            product.pk
        ]


# ══════════════════════════════════════════════════════════════════════════════
# 6. Authenticated behaviour unchanged (criterion 4, in addition to the
#    unmodified TestWishlistViewSet in test_views.py)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAuthenticatedWishlistStillUserOwned:

    def test_authenticated_add_creates_a_user_owned_row(
        self, customer_client, customer, make_product
    ):
        res = customer_client.post(WISHLIST_URL, {"product_id": make_product().pk})
        assert res.status_code == status.HTTP_201_CREATED
        item = Wishlist.objects.get(pk=res.data["id"])
        assert item.user == customer
        assert item.session_key is None

    def test_authenticated_user_never_sees_guest_rows(
        self, customer_client, customer, make_product
    ):
        Wishlist.objects.create(session_key="some-guest", product=make_product())
        mine = Wishlist.objects.create(user=customer, product=make_product())
        res = customer_client.get(WISHLIST_URL)
        assert [i["id"] for i in _results(res)] == [mine.pk]

    def test_authenticated_user_cannot_delete_a_guest_row(
        self, customer_client, make_product
    ):
        guest = Wishlist.objects.create(
            session_key="some-guest", product=make_product()
        )
        res = customer_client.delete(wish_detail(guest.pk))
        assert res.status_code == status.HTTP_404_NOT_FOUND
        assert Wishlist.objects.filter(pk=guest.pk).exists()

    def test_authenticated_duplicate_still_returns_400(
        self, customer_client, make_product
    ):
        product = make_product()
        customer_client.post(WISHLIST_URL, {"product_id": product.pk})
        res = customer_client.post(WISHLIST_URL, {"product_id": product.pk})
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_authenticated_client_with_stale_session_cookie_still_uses_user_rows(
        self, customer, make_product
    ):
        """A logged-in user who also carries a session cookie must be keyed
        on the user — never on the session."""
        client = APIClient()
        client.get(WISHLIST_URL)  # picks up a session cookie as a guest
        from rest_framework_simplejwt.tokens import RefreshToken

        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(customer).access_token}"
        )
        res = client.post(WISHLIST_URL, {"product_id": make_product().pk})
        assert res.status_code == status.HTTP_201_CREATED
        item = Wishlist.objects.get(pk=res.data["id"])
        assert item.user == customer
        assert item.session_key is None
