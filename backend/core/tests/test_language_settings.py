"""
core/tests/test_language_settings.py
────────────────────────────────────
Guards the Persian-default localisation settings (Tasks 14.1.1.1 / 14.1.1.4).
Settings-only; needs no database.

The default language is read from the settings MODULE rather than the live
`settings` object: the root conftest.py deliberately pins LANGUAGE_CODE to
"en" at runtime so the pre-Epic-14 suite (which asserts English text) keeps
working, which would otherwise make this check meaningless.
"""

from core.settings import base as base_settings
from django.conf import settings
from django.test import SimpleTestCase


class LanguageSettingsTests(SimpleTestCase):
    def test_default_language_is_persian(self):
        self.assertEqual(base_settings.LANGUAGE_CODE, "fa")

    def test_persian_is_a_supported_language(self):
        self.assertIn("fa", dict(base_settings.LANGUAGES))

    def test_english_remains_available(self):
        self.assertIn("en", dict(settings.LANGUAGES))

    def test_i18n_enabled(self):
        self.assertTrue(settings.USE_I18N)

    def test_locale_paths_points_at_backend_locale_dir(self):
        self.assertEqual(
            [str(p) for p in settings.LOCALE_PATHS],
            [str(settings.BASE_DIR / "locale")],
        )

    def test_locale_middleware_installed_in_the_required_position(self):
        """
        Per-request language switching from Accept-Language needs
        LocaleMiddleware, and Django requires it AFTER SessionMiddleware and
        BEFORE CommonMiddleware.
        """
        mw = list(settings.MIDDLEWARE)
        locale_mw = "django.middleware.locale.LocaleMiddleware"
        self.assertIn(locale_mw, mw)
        self.assertGreater(
            mw.index(locale_mw),
            mw.index("django.contrib.sessions.middleware.SessionMiddleware"),
        )
        self.assertLess(
            mw.index(locale_mw), mw.index("django.middleware.common.CommonMiddleware")
        )
