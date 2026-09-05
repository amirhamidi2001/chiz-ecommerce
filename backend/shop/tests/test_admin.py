"""
Tests for backend/shop/admin.py's NearExpiryFilter.

This project has no established precedent for testing admin
configuration in general (list_display/list_filter/search_fields
tuples aren't unit-tested elsewhere, per earlier tasks' findings), but
NearExpiryFilter is a genuine piece of custom filtering *logic* (a
queryset method with date-boundary conditions), not just declarative
config — exactly the kind of thing this project's own testing
philosophy (see e.g. order/tests/test_stock_concurrency.py) would
cover directly rather than skip. Django admin filter classes can be
tested directly by calling `.queryset()` with a constructed request
and pre-built test data, without going through the full admin HTTP
stack.
"""

import datetime

import pytest
from django.test import RequestFactory
from shop.admin import NearExpiryFilter
from shop.models import ProductVariant
from shop.tests.factories import ProductVariantFactory


def make_request(expiry_status=None):
    """
    Build a request carrying expiry_status as a real query-string
    param, so request.GET is a genuine QueryDict — SimpleListFilter's
    __init__ does `value = params.pop(name); value[-1]`, which expects
    QueryDict-style list values, not a plain dict. Passing a plain
    dict silently breaks value parsing (it ends up grabbing the last
    *character* of the string, not the value).
    """
    path = "/admin/shop/productvariant/"
    if expiry_status is not None:
        path += f"?expiry_status={expiry_status}"
    return RequestFactory().get(path)


def apply_filter(value):
    """
    Helper: construct a NearExpiryFilter with expiry_status=value (or
    no param at all if value is None) and run its queryset() over
    every ProductVariant.
    """
    request = make_request(value)
    f = NearExpiryFilter(
        request=request,
        params=request.GET.copy(),
        model=ProductVariant,
        model_admin=None,
    )
    return f.queryset(request, ProductVariant.objects.all())


@pytest.mark.django_db
class TestNearExpiryFilter:

    def test_lookups_offers_near_and_expired_options(self):
        request = make_request()
        f = NearExpiryFilter(
            request=request,
            params=request.GET.copy(),
            model=ProductVariant,
            model_admin=None,
        )
        lookups = f.lookups(request, None)
        values = [value for value, _label in lookups]
        assert values == ["near", "expired"]

    def test_variant_expiring_in_30_days_included_in_near(self):
        today = datetime.date.today()
        variant = ProductVariantFactory(
            expiration_date=today + datetime.timedelta(days=30)
        )
        qs = apply_filter("near")
        assert variant in qs

    def test_variant_expiring_in_200_days_excluded_from_near(self):
        today = datetime.date.today()
        variant = ProductVariantFactory(
            expiration_date=today + datetime.timedelta(days=200)
        )
        qs = apply_filter("near")
        assert variant not in qs

    def test_expired_variant_included_in_expired_and_excluded_from_near(self):
        today = datetime.date.today()
        variant = ProductVariantFactory(
            expiration_date=today - datetime.timedelta(days=5)
        )
        near_qs = apply_filter("near")
        expired_qs = apply_filter("expired")
        assert variant not in near_qs
        assert variant in expired_qs

    def test_variant_with_no_expiration_date_excluded_from_both(self):
        """
        A variant with expiration_date=None must never show up under
        either "near" or "expired" — having no date at all is neither.
        """
        variant = ProductVariantFactory(expiration_date=None)
        near_qs = apply_filter("near")
        expired_qs = apply_filter("expired")
        assert variant not in near_qs
        assert variant not in expired_qs

    def test_exactly_90_days_out_is_included_in_near(self):
        """Boundary check: the filter uses <=, so day 90 itself counts as near."""
        today = datetime.date.today()
        variant = ProductVariantFactory(
            expiration_date=today + datetime.timedelta(days=90)
        )
        qs = apply_filter("near")
        assert variant in qs

    def test_expiring_today_is_included_in_near_not_expired(self):
        """Boundary check: expiring exactly today is "near" (>=), not yet expired (<)."""
        today = datetime.date.today()
        variant = ProductVariantFactory(expiration_date=today)
        near_qs = apply_filter("near")
        expired_qs = apply_filter("expired")
        assert variant in near_qs
        assert variant not in expired_qs

    def test_no_filter_value_returns_all_variants_unfiltered(self):
        """No expiry_status param at all (self.value() is None) — queryset passes through."""
        v1 = ProductVariantFactory(expiration_date=None)
        v2 = ProductVariantFactory(
            expiration_date=datetime.date.today() + datetime.timedelta(days=10)
        )
        v3 = ProductVariantFactory(
            expiration_date=datetime.date.today() - datetime.timedelta(days=10)
        )
        qs = apply_filter(None)
        assert v1 in qs
        assert v2 in qs
        assert v3 in qs

    def test_near_and_expired_are_mutually_exclusive_for_same_variant(self):
        """A single variant can never appear in both filtered result sets."""
        expired_variant = ProductVariantFactory(
            expiration_date=datetime.date.today() - datetime.timedelta(days=1)
        )
        near_variant = ProductVariantFactory(
            expiration_date=datetime.date.today() + datetime.timedelta(days=1)
        )
        near_qs = apply_filter("near")
        expired_qs = apply_filter("expired")

        assert expired_variant in expired_qs
        assert expired_variant not in near_qs
        assert near_variant in near_qs
        assert near_variant not in expired_qs
