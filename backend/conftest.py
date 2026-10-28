"""
backend/conftest.py
───────────────────
Project-wide pytest fixtures.

LANGUAGE PIN (Epic 14): the site default is Persian (LANGUAGE_CODE = "fa")
and LocaleMiddleware now serves Persian to any request without an
Accept-Language header. The pre-Epic-14 suite asserts on English message
text, so by default every test runs under English. Tests that exercise
translation opt in explicitly — by sending an Accept-Language header,
wrapping code in translation.override("fa"), or using override_settings —
exactly as production clients would.

This applies to pytest runs (the project's runner, see pytest.ini); it is
not applied when running `manage.py test`.
"""

import pytest
from django.utils import translation


@pytest.fixture(autouse=True)
def _english_by_default(settings):
    settings.LANGUAGE_CODE = "en"
    translation.activate("en")
    yield
    translation.deactivate()
