"""
Carrier provider interface + factory (Feature 7.1.1 / mirrors Feature
6.1.1's PaymentGateway pattern one layer over in the shipping domain).

Concrete carrier backends never get referenced directly by callers —
the checkout/fulfillment code in Phase 7.2 only ever depends on the
abstract CarrierProvider contract and resolves a concrete instance
through get_carrier_provider().

Like PAYMENT_GATEWAY_CLASSES (and unlike SMS_PROVIDER_CLASS, which is a
single active provider), carrier providers are looked up by code via
CARRIER_PROVIDER_CLASSES, a dict of {code: dotted_path} — multiple
carriers (Post, Tipax, SnapBox, AloPeyk) are simultaneously available,
with the specific one to use resolved per-order from the customer's
selected ShippingCarrier (Task 7.1.1.2), not a single global default.

No concrete provider is implemented here — see Tasks 7.2.1.2 through
7.2.1.5 for the first ones. CARRIER_PROVIDER_CLASSES starts out empty
in settings and is populated incrementally as each of those lands.
"""

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from .base import CarrierProvider, RateQuoteResult, ShipmentCreateResult, TrackingResult

__all__ = [
    "CarrierProvider",
    "RateQuoteResult",
    "ShipmentCreateResult",
    "TrackingResult",
    "get_carrier_provider",
]


def get_carrier_provider(code: str) -> CarrierProvider:
    """
    Resolve and instantiate a configured carrier provider by code, based
    on the dotted import path registered for it in
    settings.CARRIER_PROVIDER_CLASSES.

    Args:
        code: Key into settings.CARRIER_PROVIDER_CLASSES — matches
            ShippingCarrier.Code (e.g. "post", "tipax", "snapbox",
            "alopeyk").

    Raises:
        ImproperlyConfigured: with a clear, actionable message (not a
            bare ImportError/TypeError) if `code`:
              - isn't a registered key in CARRIER_PROVIDER_CLASSES,
              - maps to a dotted path that isn't valid/importable,
              - can't be instantiated with no arguments, or
              - doesn't actually implement the CarrierProvider interface
                (verified via isinstance(), not just duck-typing/name
                matching) — this catches a class that merely happens to
                be importable but forgot to subclass CarrierProvider, or
                only implements part of the contract.
    """
    from django.conf import settings

    provider_classes = settings.CARRIER_PROVIDER_CLASSES

    if code not in provider_classes:
        raise ImproperlyConfigured(f"Unknown carrier provider: {code}")

    dotted_path = provider_classes[code]

    try:
        provider_class = import_string(dotted_path)
    except ImportError as exc:
        raise ImproperlyConfigured(
            f"CARRIER_PROVIDER_CLASSES[{code!r}]={dotted_path!r} could not "
            f"be imported ({exc}). Check that the dotted path is correct "
            "and that the module and class both exist."
        ) from exc

    try:
        instance = provider_class()
    except TypeError as exc:
        raise ImproperlyConfigured(
            f"CARRIER_PROVIDER_CLASSES[{code!r}]={dotted_path!r} could not "
            f"be instantiated ({exc}). This usually means either the "
            "class requires constructor arguments (carrier provider "
            "classes must support ProviderClass() with no arguments), or "
            "it's missing a concrete implementation of an abstract method "
            "(e.g. get_rate()/create_shipment()/track())."
        ) from exc

    if not isinstance(instance, CarrierProvider):
        raise ImproperlyConfigured(
            f"{dotted_path} does not implement CarrierProvider "
            "(shipping.providers.base.CarrierProvider). It must subclass "
            "CarrierProvider and implement get_rate(), create_shipment(), "
            "and track()."
        )

    return instance
