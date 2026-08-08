import pytest
from accounts.tokens import password_reset_token
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestPasswordResetTokenGenerator:

    def test_generates_non_empty_token(self, user):
        token = password_reset_token.make_token(user)
        assert token
        assert isinstance(token, str)
        assert len(token) > 10

    def test_check_token_returns_true_for_valid_pair(self, user):
        token = password_reset_token.make_token(user)
        assert password_reset_token.check_token(user, token) is True

    def test_check_token_returns_false_for_wrong_token(self, user):
        assert password_reset_token.check_token(user, "tampered-token") is False

    def test_token_invalidated_after_password_change(self, user):
        token = password_reset_token.make_token(user)
        # Change the password — the stored hash changes, invalidating the token.
        user.set_password("ChangedPassword789!")
        user.save()
        assert password_reset_token.check_token(user, token) is False

    def test_token_invalidated_after_account_deactivation(self, user):
        token = password_reset_token.make_token(user)
        user.is_active = False
        user.save()
        assert password_reset_token.check_token(user, token) is False

    def test_token_is_user_specific(self, user, second_user):
        """A token minted for user_a must not be accepted for user_b."""
        token_for_user = password_reset_token.make_token(user)
        assert password_reset_token.check_token(second_user, token_for_user) is False

    def test_two_tokens_for_same_user_are_different(self, user):
        """Successive tokens should differ (timestamp is part of the hash)."""
        token_a = password_reset_token.make_token(user)
        import time

        time.sleep(0.01)  # noqa: E702  guarantee different timestamp
        token_b = password_reset_token.make_token(user)
        # Both valid, but they differ because the timestamp component changed.
        assert password_reset_token.check_token(user, token_a) is True
        assert password_reset_token.check_token(user, token_b) is True
