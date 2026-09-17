"""
Tests for dashboard/migrations/0003_clear_invalid_province_and_postal_code_data.py.

Following the precedent established in shop/tests/test_migrations.py
and accounts/tests/test_migrations.py: this project has no
migration-testing package installed, so rather than pull in a new
dependency for two small data-cleanup functions, these tests import
the migration module directly (via importlib, since its filename
starts with a digit and isn't a valid dotted-import identifier) and
call its functions directly against the real, already-migrated test
database and model classes.
"""

import importlib

import pytest
from dashboard.models import Address
from django.apps import apps

migration_module = importlib.import_module(
    "dashboard.migrations.0003_clear_invalid_province_and_postal_code_data"
)
clear_invalid_provinces = migration_module.clear_invalid_provinces
clear_invalid_postal_codes = migration_module.clear_invalid_postal_codes


def run_province_cleanup():
    clear_invalid_provinces(apps, None)


def run_postal_code_cleanup():
    clear_invalid_postal_codes(apps, None)


@pytest.mark.django_db
class TestClearInvalidProvinceAndPostalCodeData:

    def _make_addr(self, user, **overrides):
        defaults = dict(
            label="home",
            first_name="John",
            last_name="Doe",
            phone="5550001111",
            address_line="1 Test Lane",
            apartment="Suite 2",
            city="Testville",
            province="tehran",
            postal_code="1234567890",
            country="IR",
        )
        defaults.update(overrides)
        return Address.objects.create(user=user, **defaults)

    # ── province cleanup ─────────────────────────────────────────────────────

    def test_invalid_province_value_is_cleared_to_blank(self, customer):
        addr = self._make_addr(customer, province="california")

        run_province_cleanup()

        addr.refresh_from_db()
        assert addr.province == ""

    def test_valid_province_value_is_left_untouched(self, customer):
        addr = self._make_addr(customer, province="fars")

        run_province_cleanup()

        addr.refresh_from_db()
        assert addr.province == "fars"

    def test_already_blank_province_is_left_untouched(self, customer):
        addr = self._make_addr(customer, province="")

        run_province_cleanup()  # must not raise

        addr.refresh_from_db()
        assert addr.province == ""

    # ── postal code cleanup ──────────────────────────────────────────────────
    # NOTE: "too long" (>10 char) legacy values can't be constructed here at
    # all, since postal_code's max_length=10 constraint (from migration 0004)
    # is already active on this test database's current schema — that
    # specific scenario (an old zip_code value that would violate the
    # SHRUNK max_length) was verified manually against the pre-migration
    # schema directly: a real ALTER COLUMN failure was reproduced, then
    # fixed by running this exact cleanup function first. See this task's
    # summary/migration comments for that verification.

    @pytest.mark.parametrize(
        "bad_value",
        ["90001", "abcdefghij", ""],
    )
    def test_invalid_postal_code_is_cleared_to_blank(self, customer, bad_value):
        addr = self._make_addr(customer, postal_code=bad_value)

        run_postal_code_cleanup()

        addr.refresh_from_db()
        assert addr.postal_code == ""

    def test_valid_10_digit_postal_code_is_left_untouched(self, customer):
        addr = self._make_addr(customer, postal_code="9876543210")

        run_postal_code_cleanup()

        addr.refresh_from_db()
        assert addr.postal_code == "9876543210"

    # ── other fields are never touched by either cleanup function ───────────

    def test_cleanup_preserves_every_other_field_untouched(self, customer):
        """
        The migration's whole point is to fix ONLY province/postal_code
        — every other field on an existing Address row (including ones
        that were never renamed) must survive completely unchanged.
        """
        addr = self._make_addr(
            customer,
            province="not-a-real-province",
            postal_code="123456789",  # 9 digits — invalid, but fits max_length=10
            first_name="Original",
            last_name="Name",
            phone="5551234567",
            address_line="42 Original Ave",
            apartment="Unit 9",
            city="Originalburg",
            country="IR",
        )

        run_province_cleanup()
        run_postal_code_cleanup()

        addr.refresh_from_db()
        assert addr.first_name == "Original"
        assert addr.last_name == "Name"
        assert addr.phone == "5551234567"
        assert addr.address_line == "42 Original Ave"
        assert addr.apartment == "Unit 9"
        assert addr.city == "Originalburg"
        assert addr.country == "IR"
        # ...only these two were actually invalid and got cleared.
        assert addr.province == ""
        assert addr.postal_code == ""
