"""
SMSProvider interface + factory.

Defines a small, swappable interface any SMS backend can implement, so
the OTP service (and anything else that needs to send an SMS later)
depends only on this abstract contract — never a specific vendor SDK
directly. The concrete provider actually used is entirely
settings/env-driven via SMS_PROVIDER_CLASS, resolved dynamically with
Django's own import_string helper (the same mechanism Django uses to
resolve things like AUTH_USER_MODEL).

No concrete provider is implemented here — see Task 2.2.1.2 for the
console/dev backend (accounts.sms.console.ConsoleSMSProvider, which
SMS_PROVIDER_CLASS defaults to).
"""

from abc import ABC, abstractmethod

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


class SMSProvider(ABC):
    """Abstract interface every SMS backend must implement."""

    @abstractmethod
    def send(self, phone_number: str, message: str) -> bool:
        """Send `message` to `phone_number`. Returns True on success."""
        raise NotImplementedError


def get_sms_provider() -> SMSProvider:
    """
    Resolve and instantiate the currently configured SMS provider, based
    on the dotted import path in settings.SMS_PROVIDER_CLASS.

    Raises:
        ImproperlyConfigured: with a clear, actionable message (not a
            bare ImportError/TypeError) if SMS_PROVIDER_CLASS:
              - isn't a valid/importable dotted path,
              - can't be instantiated with no arguments, or
              - doesn't actually implement the SMSProvider interface
                (verified via isinstance(), not just duck-typing/name
                matching) — this catches a class that merely happens to
                be importable but forgot to subclass SMSProvider, or
                only implements part of the contract.
    """
    dotted_path = settings.SMS_PROVIDER_CLASS

    try:
        provider_class = import_string(dotted_path)
    except ImportError as exc:
        raise ImproperlyConfigured(
            f"SMS_PROVIDER_CLASS={dotted_path!r} could not be imported "
            f"({exc}). Check that the dotted path is correct and that "
            "the module and class both exist."
        ) from exc

    try:
        instance = provider_class()
    except TypeError as exc:
        raise ImproperlyConfigured(
            f"SMS_PROVIDER_CLASS={dotted_path!r} could not be "
            f"instantiated ({exc}). This usually means either the class "
            "requires constructor arguments (provider classes must "
            "support ProviderClass() with no arguments), or it's missing "
            "a concrete implementation of an abstract method (e.g. "
            "send())."
        ) from exc

    if not isinstance(instance, SMSProvider):
        raise ImproperlyConfigured(
            f"SMS_PROVIDER_CLASS={dotted_path!r} does not implement the "
            "SMSProvider interface (accounts.sms.base.SMSProvider). It "
            "must subclass SMSProvider and implement send()."
        )

    return instance
