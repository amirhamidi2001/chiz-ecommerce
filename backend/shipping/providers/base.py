"""
CarrierProvider interface.

Defines a small, swappable interface any shipping carrier backend can
implement, so the checkout/fulfillment code built in Phase 7.2 depends
only on this abstract contract — never a specific carrier SDK/API
directly. This mirrors Epic 6 Task 6.1.1.4's PaymentGateway interface
exactly, one layer over in the shipping domain: a plain ABC with the
minimal set of methods every carrier backend must support, plus small
dataclass result types instead of dicts/tuples so the contract is
explicit and self-documenting for whoever implements a concrete
provider next (Tasks 7.2.1.2 through 7.2.1.5).

No concrete provider is implemented here — see those tasks for the
first ones (Post, Tipax, SnapBox, AloPeyk).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class RateQuoteResult:
    success: bool
    price: Decimal = Decimal("0")
    estimated_days_min: int = 0
    estimated_days_max: int = 0
    error_message: str = ""


@dataclass
class ShipmentCreateResult:
    success: bool
    tracking_number: str = ""
    label_url: str = ""
    error_message: str = ""


@dataclass
class TrackingResult:
    success: bool
    status: str = ""
    status_description: str = ""
    error_message: str = ""


class CarrierProvider(ABC):
    """Abstract interface every shipping carrier backend must implement."""

    @abstractmethod
    def get_rate(
        self, origin: dict, destination: dict, weight_g: int
    ) -> RateQuoteResult:
        """
        Get a live rate quote from the carrier's API, if supported.

        IMPORTANT: many Iranian courier services are priced via a
        published, static rate card (see Task 7.1.1.3's ShippingRate
        table) rather than exposing a live quoting API at all. For such
        a carrier, `RateQuoteResult(success=False, error_message=...)`
        is a VALID, EXPECTED outcome here — not a bug, and not something
        the implementation should fake by inventing a price. Concrete
        implementations for carriers with no live-quoting API should
        either:

          - raise NotImplementedError, or
          - return RateQuoteResult(success=False, error_message=
            "Live quoting not supported; use rate table.")

        Callers must be prepared for get_rate() to come back
        success=False and fall back to ShippingRate.find_rate() in that
        case, rather than assuming every carrier can always produce a
        live quote.
        """
        raise NotImplementedError

    @abstractmethod
    def create_shipment(self, order, destination: dict) -> ShipmentCreateResult:
        """Book an actual shipment with the carrier and get a tracking number/label."""
        raise NotImplementedError

    @abstractmethod
    def track(self, tracking_number: str) -> TrackingResult:
        """Get current delivery status for a tracking number."""
        raise NotImplementedError
