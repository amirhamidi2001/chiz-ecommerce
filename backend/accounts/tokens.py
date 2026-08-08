from django.contrib.auth.tokens import PasswordResetTokenGenerator


class _PasswordResetTokenGenerator(PasswordResetTokenGenerator):
    """
    Ties the token to the user's current password hash so it is
    automatically invalidated after a successful reset.
    """

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.password}{timestamp}{user.is_active}"


password_reset_token = _PasswordResetTokenGenerator()
