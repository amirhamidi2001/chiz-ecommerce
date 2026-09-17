"""
Payment gateway interface + factory (Feature 6.1.1).

Mirrors the SMSProvider interface established in Epic 2 Task 2.2.1.1
(accounts.sms.base.SMSProvider + get_sms_provider()): concrete gateway
backends never get referenced directly by callers — the initiate/
callback views in Phase 6.2 only ever depend on the abstract
PaymentGateway contract and resolve a concrete instance through
get_payment_gateway().

Unlike SMS_PROVIDER_CLASS (a single dotted-path string, since only one
SMS provider is ever active at a time), payment gateways are looked up
by name via PAYMENT_GATEWAY_CLASSES, a dict of {name: dotted_path}.
This is deliberate, not an inconsistency with the SMS pattern: Phase
6.3 (Task 6.3.1.3) adds admin-configurable gateway selection/fallback
across MULTIPLE simultaneously-available gateways (ZarinPal, Zibal,
IDPay), so callers need to resolve "the gateway named X", not just
"the one configured gateway".

No concrete gateway is implemented here — see Task 6.2.1.1 for the
first one (ZarinPal).
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from .base import PaymentGateway, PaymentRequestResult, PaymentVerifyResult

__all__ = [
    "PaymentGateway",
    "PaymentRequestResult",
    "PaymentVerifyResult",
    "get_payment_gateway",
]


def get_payment_gateway(name: str | None = None) -> PaymentGateway:
    """
    Resolve and instantiate a configured payment gateway by name, based
    on the dotted import path registered for it in
    settings.PAYMENT_GATEWAY_CLASSES.

    Args:
        name: Key into settings.PAYMENT_GATEWAY_CLASSES (e.g.
            "zarinpal"). Defaults to settings.DEFAULT_PAYMENT_GATEWAY
            when not given.

    Raises:
        ImproperlyConfigured: with a clear, actionable message (not a
            bare ImportError/TypeError) if `name`:
              - isn't a registered key in PAYMENT_GATEWAY_CLASSES,
              - maps to a dotted path that isn't valid/importable,
              - can't be instantiated with no arguments, or
              - doesn't actually implement the PaymentGateway interface
                (verified via isinstance(), not just duck-typing/name
                matching) — this catches a class that merely happens to
                be importable but forgot to subclass PaymentGateway, or
                only implements part of the contract.
    """
    name = name or settings.DEFAULT_PAYMENT_GATEWAY
    gateway_classes = settings.PAYMENT_GATEWAY_CLASSES

    if name not in gateway_classes:
        raise ImproperlyConfigured(f"Unknown payment gateway: {name}")

    dotted_path = gateway_classes[name]

    try:
        gateway_class = import_string(dotted_path)
    except ImportError as exc:
        raise ImproperlyConfigured(
            f"PAYMENT_GATEWAY_CLASSES[{name!r}]={dotted_path!r} could not "
            f"be imported ({exc}). Check that the dotted path is correct "
            "and that the module and class both exist."
        ) from exc

    try:
        instance = gateway_class()
    except TypeError as exc:
        raise ImproperlyConfigured(
            f"PAYMENT_GATEWAY_CLASSES[{name!r}]={dotted_path!r} could not "
            f"be instantiated ({exc}). This usually means either the "
            "class requires constructor arguments (gateway classes must "
            "support GatewayClass() with no arguments), or it's missing "
            "a concrete implementation of an abstract method (e.g. "
            "request_payment()/verify_payment())."
        ) from exc

    if not isinstance(instance, PaymentGateway):
        raise ImproperlyConfigured(
            f"{dotted_path} does not implement the PaymentGateway "
            "interface (payments.gateways.base.PaymentGateway). It must "
            "subclass PaymentGateway and implement request_payment() and "
            "verify_payment()."
        )

    return instance
