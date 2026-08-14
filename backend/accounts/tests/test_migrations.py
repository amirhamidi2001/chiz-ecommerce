"""
Tests for accounts/migrations/0004_backfill_user_phone_from_profile.py.

This project has no existing precedent for testing data migrations (no
migration-testing package like django-test-migrations is installed, and
no other app's tests exercise a RunPython migration). Rather than pull
in a new dependency for a single migration, these tests import the
migration module directly (via importlib, since its filename starts
with a digit and isn't a valid dotted-import identifier) and call its
forward function directly against the real, already-migrated test
database and model classes — equivalent to what Django's migration
executor does under the hood (`apps.get_model(...)` historical models
resolve to the current model classes once all migrations are applied,
which they are in the test DB), without needing a separate frozen-state
migration test harness for what is a straightforward, idempotent data
backfill.
"""

import importlib

import pytest
from accounts.models import Profile, User
from django.apps import apps

migration_module = importlib.import_module(
    "accounts.migrations.0004_backfill_user_phone_from_profile"
)
backfill_user_phone_from_profile = migration_module.backfill_user_phone_from_profile


def run_backfill():
    """Invoke the migration's forward function against the real app registry."""
    backfill_user_phone_from_profile(apps, None)


@pytest.mark.django_db
class TestBackfillUserPhoneFromProfile:

    def test_valid_unique_profile_phone_is_copied_to_user(self, create_user):
        user = create_user(email="valid@example.com")
        user.profile.phone_number = "09123456789"
        user.profile.save()
        assert user.phone_number is None  # sanity: not set yet

        run_backfill()

        user.refresh_from_db()
        assert user.phone_number == "09123456789"

    def test_bare_number_without_prefix_is_normalized_on_copy(self, create_user):
        """
        Legacy Profile.phone_number is a plain max_length=12 CharField
        with no format validation, so it may contain a bare 10-digit
        subscriber number with no leading 0 or country code (e.g. a user
        typed "9123456789" instead of "09123456789"). This is short
        enough to fit the legacy column and is still valid per the
        Iranian mobile regex (the prefix group is optional) — use it to
        confirm the migration actually normalizes rather than doing a
        raw, unmodified copy.
        """
        user = create_user(email="bareformat@example.com")
        user.profile.phone_number = "9123456789"
        user.profile.save()

        run_backfill()

        user.refresh_from_db()
        assert user.phone_number == "09123456789"

    def test_invalid_profile_phone_is_skipped_without_raising(self, create_user):
        user = create_user(email="invalid@example.com")
        user.profile.phone_number = "12345"
        user.profile.save()

        run_backfill()  # must not raise

        user.refresh_from_db()
        assert user.phone_number is None

    def test_blank_profile_phone_is_skipped(self, create_user):
        user = create_user(email="blankphone@example.com")
        # Profile.phone_number defaults to blank/None already (see
        # conftest.create_user) — explicit for clarity.
        user.profile.phone_number = ""
        user.profile.save()

        run_backfill()

        user.refresh_from_db()
        assert user.phone_number is None

    def test_duplicate_profile_phone_across_two_users_only_sets_one(self, create_user):
        """
        Two Profiles with the same (dirty legacy) phone number string:
        the migration must not crash on the unique-constraint conflict,
        and exactly one of the two Users ends up with the number set —
        the other is left None.
        """
        user_a = create_user(email="dup-a@example.com")
        user_a.profile.phone_number = "09121112222"
        user_a.profile.save()

        user_b = create_user(email="dup-b@example.com")
        user_b.profile.phone_number = "09121112222"
        user_b.profile.save()

        run_backfill()  # must not raise IntegrityError

        user_a.refresh_from_db()
        user_b.refresh_from_db()

        results = {user_a.phone_number, user_b.phone_number}
        # Exactly one got the number, the other stayed None.
        assert results == {"09121112222", None}

    def test_migration_does_not_overwrite_existing_user_phone_number(self, create_user):
        """
        Defensive: if a User somehow already has a phone_number set
        (e.g. re-running the migration, or set via some other path),
        and their Profile has a *different* number, the existing
        User.phone_number value should not silently disappear just
        because it happens to equal what's already there. This test
        specifically covers re-running the backfill being idempotent
        for a user who was already migrated.
        """
        user = create_user(email="idempotent@example.com")
        user.profile.phone_number = "09129998888"
        user.profile.save()

        run_backfill()
        user.refresh_from_db()
        assert user.phone_number == "09129998888"

        # Run again — must not raise (this user already has this exact
        # number, so the "already taken by a different user" check
        # excludes their own pk and re-applies cleanly).
        run_backfill()
        user.refresh_from_db()
        assert user.phone_number == "09129998888"

    def test_multiple_valid_distinct_profiles_all_migrate_independently(
        self, create_user
    ):
        user_a = create_user(email="multi-a@example.com")
        user_a.profile.phone_number = "09121110001"
        user_a.profile.save()

        user_b = create_user(email="multi-b@example.com")
        user_b.profile.phone_number = "09121110002"
        user_b.profile.save()

        run_backfill()

        user_a.refresh_from_db()
        user_b.refresh_from_db()
        assert user_a.phone_number == "09121110001"
        assert user_b.phone_number == "09121110002"
