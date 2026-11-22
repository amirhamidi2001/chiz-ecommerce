"""
Trivial smoke test for the `notifications` app scaffold.

There's no functional code here yet beyond the relocated SMS provider
package (models, views, etc. start in a later task) — this just locks in
that the app-registration wiring itself (INSTALLED_APPS entry +
AppConfig) doesn't silently break in a future refactor.
"""

import django.apps
from django.test import SimpleTestCase


class NotificationsAppRegistrationTests(SimpleTestCase):
    def test_notifications_app_is_installed(self):
        installed_app_labels = [
            app_config.split(".")[0] for app_config in django.apps.apps.app_configs
        ]
        self.assertIn("notifications", installed_app_labels)


class NotificationTemplateAdminRegistrationTests(SimpleTestCase):
    def test_notification_template_is_registered_in_admin(self):
        from django.contrib import admin
        from notifications.models import NotificationTemplate

        self.assertIn(NotificationTemplate, admin.site._registry)
