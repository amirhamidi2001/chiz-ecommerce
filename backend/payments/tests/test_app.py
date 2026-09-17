"""
Trivial smoke test for the `payments` app scaffold.

There's no functional code here yet (models, views, etc. start in a
later task) — this just locks in that the app-registration wiring
itself (INSTALLED_APPS entry + AppConfig) doesn't silently break in a
future refactor.
"""

import django.apps
from django.test import SimpleTestCase


class PaymentsAppRegistrationTests(SimpleTestCase):
    def test_payments_app_is_installed(self):
        installed_app_labels = [
            app_config.split(".")[0] for app_config in django.apps.apps.app_configs
        ]
        self.assertIn("payments", installed_app_labels)
