"""
Test-double SMS provider classes used by accounts/tests/test_sms.py.

These live in their own normal, importable module (rather than being
defined inline inside the test functions) specifically because
get_sms_provider() needs a real dotted import path to resolve via
Django's import_string — a class defined inside a test function isn't
reliably importable by dotted path.
"""

from accounts.sms.base import SMSProvider


class ValidTestProvider(SMSProvider):
    """A minimal, fully-conforming SMSProvider implementation."""

    def send(self, phone_number: str, message: str) -> bool:
        return True


class NotAnSMSProvider:
    """
    Looks like a provider (has a matching send() method signature) but
    does NOT subclass SMSProvider — used to prove get_sms_provider()
    checks isinstance(), not just duck-typing/attribute presence.
    """

    def send(self, phone_number, message):
        return True


class ProviderRequiringConstructorArgs(SMSProvider):
    """
    A real SMSProvider subclass, but one that can't be instantiated with
    no arguments — used to prove get_sms_provider() surfaces a clear
    ImproperlyConfigured error rather than a bare TypeError.
    """

    def __init__(self, api_key):
        self.api_key = api_key

    def send(self, phone_number: str, message: str) -> bool:
        return True


class IncompleteProvider(SMSProvider):
    """
    Subclasses SMSProvider but never implements the abstract send()
    method — Python itself will refuse to instantiate this (TypeError:
    Can't instantiate abstract class ... with abstract method send).
    """
