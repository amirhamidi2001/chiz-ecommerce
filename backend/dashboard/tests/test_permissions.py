"""
Tests for dashboard/permissions.py.

TestIsAdminOrSuperuser uses lightweight hand-rolled fake request objects
(these permission classes only ever read `request.user`, so a minimal
stand-in is enough there).

TestIsOwnerOrAdmin below is built on DRF's own
`rest_framework.test.APIRequestFactory` + `force_authenticate` instead,
per this task's requirement — constructing real DRF `Request` objects
so `request.user` resolves exactly the way it does in production (an
`AnonymousUser` instance when unauthenticated, not `None` — confirmed
empirically via a throwaway shell check before writing these tests,
since DRF's actual unauthenticated-user value is easy to get wrong by
assumption).

Note on usage: `IsOwnerOrAdmin` is not currently wired to any real
view's `permission_classes` anywhere in the codebase (confirmed via
`grep -rn "IsOwnerOrAdmin"` across the whole backend — the only hits
are this class's own definition and these tests). There is therefore no
existing endpoint to add a representative integration-level test
through (the style shop/tests/test_views.py uses for permission-gated
endpoints, via a real APIClient + URL round-trip) — these are
deliberately unit tests of the permission logic in isolation, calling
`has_object_permission()` directly, matching this task's explicit
"faster and more precise" framing. If/when a real view starts using
this permission class, an integration-level test should be added
alongside that view's own test file at that point.
"""

import pytest
from dashboard.permissions import IsAdminOrSuperuser, IsOwnerOrAdmin
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate


class _FakeRequest:
    def __init__(self, user):
        self.user = user


class _AnonymousUser:
    is_authenticated = False


class _FakeObj:
    def __init__(self, user):
        self.user = user


@pytest.mark.django_db
class TestIsAdminOrSuperuser:
    permission = IsAdminOrSuperuser()

    def test_customer_is_denied(self, customer):
        request = _FakeRequest(customer)
        assert self.permission.has_permission(request, None) is False

    def test_admin_is_granted(self, admin_user):
        request = _FakeRequest(admin_user)
        assert self.permission.has_permission(request, None) is True

    def test_superuser_is_granted(self, superuser_user):
        request = _FakeRequest(superuser_user)
        assert self.permission.has_permission(request, None) is True

    def test_unauthenticated_user_is_denied(self):
        request = _FakeRequest(_AnonymousUser())
        assert self.permission.has_permission(request, None) is False

    def test_none_user_is_denied(self):
        request = _FakeRequest(None)
        assert self.permission.has_permission(request, None) is False


def _build_request(user=None):
    """
    Build a real DRF Request via APIRequestFactory, matching production
    request shape exactly:
      - user=None -> unauthenticated request; request.user resolves to
        a genuine django.contrib.auth.models.AnonymousUser instance
        (NOT None — confirmed empirically), the same as any real
        unauthenticated API request.
      - user=<User instance> -> force_authenticate() on the underlying
        HttpRequest before wrapping it in a DRF Request, so
        request.user resolves to that exact user.
    """
    factory = APIRequestFactory()
    django_request = factory.get("/fake-owner-check/")
    if user is not None:
        force_authenticate(django_request, user=user)
    return Request(django_request)


class _PlausibleOwnedObject:
    """
    A generic stand-in for "some object with a `.user` FK" — the only
    thing IsOwnerOrAdmin actually inspects via getattr(obj, "user",
    None). Since this permission class isn't yet applied to any real
    model/view in the codebase, there's no single "real" object shape
    to mirror; this is intentionally minimal and matches exactly what
    the permission code reads.
    """

    def __init__(self, user):
        self.user = user


@pytest.mark.django_db
class TestIsOwnerOrAdmin:
    permission = IsOwnerOrAdmin()

    def test_unauthenticated_request_is_denied_regardless_of_object(self, customer):
        request = _build_request(user=None)
        obj = _PlausibleOwnedObject(user=customer)

        assert self.permission.has_object_permission(request, None, obj) is False

    def test_customer_is_denied_for_an_object_they_do_not_own(
        self, customer, make_user
    ):
        other_user = make_user(email="other-owner@example.com")
        request = _build_request(user=customer)
        obj = _PlausibleOwnedObject(user=other_user)

        assert self.permission.has_object_permission(request, None, obj) is False

    def test_customer_is_granted_for_an_object_they_own(self, customer):
        request = _build_request(user=customer)
        obj = _PlausibleOwnedObject(user=customer)

        assert self.permission.has_object_permission(request, None, obj) is True

    def test_admin_is_granted_regardless_of_ownership(self, admin_user, customer):
        request = _build_request(user=admin_user)
        obj = _PlausibleOwnedObject(user=customer)  # admin does NOT own this

        assert self.permission.has_object_permission(request, None, obj) is True

    def test_superuser_is_granted_regardless_of_ownership(
        self, superuser_user, customer
    ):
        request = _build_request(user=superuser_user)
        obj = _PlausibleOwnedObject(user=customer)  # superuser does NOT own this

        assert self.permission.has_object_permission(request, None, obj) is True

    def test_object_with_no_user_attribute_does_not_crash_and_is_denied(self, customer):
        """
        getattr(obj, "user", None) == request.user: for an object with
        no `user` attribute at all, this becomes `None == request.user`.
        Since the unauthenticated case is already excluded earlier in
        has_object_permission() (request.user is a real, authenticated
        User by this point — never None itself), this comparison is
        always False for a real authenticated non-admin user, and
        crucially never raises (no AttributeError from the missing
        attribute) — confirmed here directly rather than just reading
        the code, per this task's requirement.
        """

        class ObjectWithoutUserAttribute:
            pass

        request = _build_request(user=customer)

        result = self.permission.has_object_permission(
            request, None, ObjectWithoutUserAttribute()
        )

        assert result is False
