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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest


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

    @abstractmethod
    def extract_callback_params(self, request: "HttpRequest") -> dict:
        """
        Parse this gateway's own callback query-parameter convention out
        of an inbound Django request and return it in a normalized,
        gateway-agnostic shape:

            {"authority": str, "is_customer_cancelled": bool}

        Added in Task 6.3.1.4, once a second and third gateway (Zibal,
        IDPay) existed and made it clear PaymentCallbackView's original
        inline `request.GET.get("Authority")`/`"Status"`/`"NOK"`
        extraction was accidentally ZarinPal-shaped rather than
        genuinely gateway-agnostic. Each concrete gateway uses its own
        actual documented query-parameter names/values here (they are
        NOT the same across gateways) and normalizes them to this one
        shape, so PaymentCallbackView never needs to know or branch on
        which gateway it's handling.

        `authority` must exactly match whatever this gateway's
        request_payment() returned as PaymentRequestResult.authority —
        it's used to look up the PaymentTransaction row. `is_customer_
        cancelled` should be True only for this gateway's own definitive
        "the customer did not complete payment" signal (mirroring
        ZarinPal's Status=NOK) — for anything else, PaymentCallbackView
        still calls verify_payment() to get an authoritative answer
        rather than guessing from callback params alone, since callback
        query parameters are client-controlled and not proof of
        anything on their own.
        """
        raise NotImplementedError
