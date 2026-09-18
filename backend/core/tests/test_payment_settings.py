"""
core/tests/test_payment_settings.py
─────────────────────────────────────
Confirms the safe-by-default posture of the payment-gateway settings added
across Epic 6: with no ZARINPAL_SANDBOX environment variable set (the
common case for a fresh checkout, dev/CI environment), the app must default
to sandbox/test mode — never silently to production/live payments.

This directly encodes the guarantee Task 6.2.1.6 was about: a missing env
var should fail toward "collects no real money," not the other way around.
"""

import os

from django.conf import settings
from django.test import TestCase


class PaymentSettingsDefaultsTests(TestCase):
    def test_zarinpal_sandbox_defaults_to_true(self):
        """
        This test only proves something if ZARINPAL_SANDBOX isn't
        explicitly set in the environment this test runs in — assert that
        precondition explicitly so a failure here can't be silently
        misread as "the default is fine" when it's actually just an env
        var override making the real default untested.
        """
        self.assertNotIn(
            "ZARINPAL_SANDBOX",
            os.environ,
            "ZARINPAL_SANDBOX is set in this test environment's env vars — "
            "this test needs it UNSET to actually exercise the default.",
        )
        self.assertIs(settings.ZARINPAL_SANDBOX, True)

    def test_zarinpal_merchant_id_defaults_to_empty_string(self):
        """
        No ZARINPAL_MERCHANT_ID configured must not crash settings import
        (see Task 6.2.1.6's manual verification: the app should only fail
        when an actual payment is attempted, via ZarinPalGateway's existing
        request_payment() error handling — not at server boot).
        """
        if "ZARINPAL_MERCHANT_ID" not in os.environ:
            self.assertEqual(settings.ZARINPAL_MERCHANT_ID, "")

    def test_default_payment_gateway_defaults_to_zarinpal(self):
        if "DEFAULT_PAYMENT_GATEWAY" not in os.environ:
            self.assertEqual(settings.DEFAULT_PAYMENT_GATEWAY, "zarinpal")
