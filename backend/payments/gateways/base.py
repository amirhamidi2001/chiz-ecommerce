"""
PaymentGateway interface.

Defines a small, swappable interface any payment gateway backend can
implement, so the initiate/callback views built in Phase 6.2 depend
only on this abstract contract — never a specific gateway SDK
directly. This mirrors the SMSProvider interface established in Epic
2 Task 2.2.1.1 (accounts.sms.base.SMSProvider): a plain ABC with the
minimal set of methods every backend must support, plus small
dataclass result types instead of dicts/tuples so the contract is
explicit and self-documenting for whoever implements a concrete
gateway next.

No concrete gateway is implemented here — see Task 6.2.1.1 for the
first one (ZarinPal).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PaymentRequestResult:
    success: bool
    authority: str = ""
    redirect_url: str = ""
    error_message: str = ""


@dataclass
class PaymentVerifyResult:
    success: bool
    ref_id: str = ""
    error_message: str = ""
    raw_response: dict | None = None


class PaymentGateway(ABC):
    """Abstract interface every payment gateway backend must implement."""

    @abstractmethod
    def request_payment(
        self, amount: Decimal, callback_url: str, description: str = ""
    ) -> PaymentRequestResult:
        """Ask the gateway to initiate a payment. Returns an authority
        code and a URL to redirect the customer to."""
        raise NotImplementedError

    @abstractmethod
    def verify_payment(self, authority: str, amount: Decimal) -> PaymentVerifyResult:
        """Confirm a payment was actually completed successfully after
        the customer returns from the gateway."""
        raise NotImplementedError
