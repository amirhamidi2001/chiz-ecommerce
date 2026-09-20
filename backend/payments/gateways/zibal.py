"""
Zibal payment gateway (Task 6.3.1.1), implementing the same PaymentGateway
interface as ZarinPalGateway (Tasks 6.2.1.1/6.2.1.3).

Endpoint URLs, request/response field names, result codes, and sandbox
mechanism below were verified against Zibal's official Node.js SDK
(https://github.com/zibalco/gateway-nodejs) and cross-checked against
several independent third-party client libraries (a .NET client, a Rust
SDK explicitly citing the same Node.js SDK as its source of truth, and
multiple community Laravel/PHP packages that all agree on the same
shapes) at the time this was written:

- Zibal has a SINGLE set of URLs — unlike ZarinPal, there is no separate
  sandbox subdomain. Request, verify, and the redirect/start URL all use
  the same production host (gateway.zibal.ir) in every mode:
    - Request:  POST https://gateway.zibal.ir/v1/request
    - Verify:   POST https://gateway.zibal.ir/v1/verify
    - Redirect: https://gateway.zibal.ir/start/{trackId}
- Zibal's documented sandbox/test mechanism is a special, literal
  merchant value: setting the merchant field to the literal string
  "zibal" (not a real merchant ID) puts the gateway itself into test
  mode against those SAME URLs above. This is why there's no
  ZIBAL_SANDBOX setting mirroring ZARINPAL_SANDBOX — Zibal doesn't have
  the URL-switching mechanism that setting would imply. To run against
  Zibal's sandbox, set ZIBAL_MERCHANT_ID=zibal in the environment.
- Request payload: {"merchant", "amount", "callbackUrl", "description"}.
  `amount` is an integer number of Iranian Rials (IRR) — same unit as
  ZarinPal, confirmed via the Node.js SDK's usage examples (e.g.
  `Zibal.request(1500)`) and the Rust SDK's explicit `amount_rials`
  naming.
- Request success response: {"trackId": <int>, "result": 100, "message":
  "success"}. `trackId` is Zibal's equivalent of ZarinPal's `authority` —
  note it's natively an INTEGER, not a string; this gateway stores it as
  a string (via PaymentRequestResult.authority: str) for interface
  consistency, matching how third-party client libraries handle it
  (confirmed a stored string trackId still verifies correctly against
  Zibal's API).
- Verify payload: {"merchant", "trackId"}.
- Verify response: {"result", "message", "refNumber", "paidAt",
  "cardNumber", "status", "amount", ...}. Confirmed result codes (cross-
  checked across the Node.js SDK and multiple independent Laravel
  packages, which all agree on this exact table):
    100 = successful operation (first-time verify)
    201 = "processed before" — Zibal's equivalent of ZarinPal's 101
          "already verified". Treated as success here for the same
          reason as ZarinPal: a customer double-hitting the callback URL
          must not be treated as a payment failure on the second call.
    102/103/104 = merchant not found/inactive/invalid
    105/106/113 = amount too small/invalid callback/amount too large
    202 = payment failed (see accompanying `status`)
    203 = invalid trackId
  Anything other than 100/201 is treated as a failure here, using
  Zibal's own `message` field for the error text.
"""

from decimal import Decimal

import requests
from django.conf import settings

from .base import PaymentGateway, PaymentRequestResult, PaymentVerifyResult


class ZibalGateway(PaymentGateway):
    REQUEST_URL = "https://gateway.zibal.ir/v1/request"
    VERIFY_URL = "https://gateway.zibal.ir/v1/verify"
    START_PAY_URL = "https://gateway.zibal.ir/start/{track_id}"

    REQUEST_TIMEOUT_SECONDS = 15

    def request_payment(
        self, amount: Decimal, callback_url: str, description: str = ""
    ) -> PaymentRequestResult:
        # Zibal's API expects `amount` as an integer number of Rials
        # (IRR) — see module docstring. Same assumption as
        # ZarinPalGateway: `amount` here is assumed to already be in
        # Rial by the time it reaches this gateway; no unit conversion
        # happens in this class.
        payload = {
            "merchant": settings.ZIBAL_MERCHANT_ID,
            "amount": int(amount),
            "callbackUrl": callback_url,
            "description": description or "Order payment",
        }

        try:
            response = requests.post(
                self.REQUEST_URL,
                json=payload,
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            return PaymentRequestResult(success=False, error_message=str(exc))

        if isinstance(data, dict) and data.get("result") == 100 and "trackId" in data:
            track_id = str(data["trackId"])
            return PaymentRequestResult(
                success=True,
                authority=track_id,
                redirect_url=self.START_PAY_URL.format(track_id=track_id),
            )

        return PaymentRequestResult(
            success=False,
            error_message=self._extract_error_message(
                data, default="Zibal payment request failed."
            ),
        )

    def verify_payment(self, authority: str, amount: Decimal) -> PaymentVerifyResult:
        # `authority` here is the trackId returned from request_payment()
        # above, stored as a string on PaymentTransaction — Zibal's API
        # tolerates a string trackId in the verify payload (confirmed via
        # third-party client libraries; Zibal's backend parses it either
        # way), so no int conversion is needed here.
        payload = {
            "merchant": settings.ZIBAL_MERCHANT_ID,
            "trackId": authority,
        }

        try:
            response = requests.post(
                self.VERIFY_URL,
                json=payload,
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            return PaymentVerifyResult(
                success=False, error_message=str(exc), raw_response=None
            )

        result_code = data.get("result") if isinstance(data, dict) else None
        # 100 = verified just now; 201 = "processed before" (already
        # verified) — both are valid, non-error outcomes for an
        # idempotent verify call. See module docstring.
        if result_code in (100, 201):
            return PaymentVerifyResult(
                success=True,
                ref_id=str(data.get("refNumber", "")),
                raw_response=data,
            )

        return PaymentVerifyResult(
            success=False,
            error_message=self._extract_error_message(
                data, default="Zibal payment verification failed."
            ),
            raw_response=data,
        )

    @staticmethod
    def _extract_error_message(data, default: str) -> str:
        """
        Zibal reports errors via the same top-level `message` field used
        on success, rather than a separate errors object like ZarinPal —
        but this isn't guaranteed to be present on every failure mode, so
        fall back to a generic default rather than assuming the key is
        always there.
        """
        if isinstance(data, dict):
            message = data.get("message")
            result_code = data.get("result")
            if message:
                return (
                    f"{message} (result: {result_code})"
                    if result_code is not None
                    else message
                )
        return default

    def extract_callback_params(self, request) -> dict:
        """
        Zibal's documented callback query parameters (confirmed against
        Zibal's own official npm package README, which gives the exact
        callback URL shape:
        ``https://yourwebsite.com/ipg/cb?trackId=10000&success=1&status=2&orderId=1``,
        and explicitly instructs verifying only "if success === true &&
        status === 2"):
        - ``trackId``: Zibal's transaction identifier — same value
          returned from request_payment() as PaymentRequestResult.authority.
        - ``success``: "1" if the customer completed payment at Zibal's
          page, "0" (or absent) if they cancelled/abandoned before
          completing it. This — not `status`, which is a richer, numeric
          detail code shared with the verify response — is Zibal's own
          definitive "customer cancelled" signal, mirroring ZarinPal's
          Status=NOK.
        - ``status``, ``orderId``: not needed here; `status` is
          re-confirmed authoritatively via verify_payment(), and
          `orderId` isn't part of this gateway's authority (unlike
          IDPay, Zibal's authority is trackId alone).
        """
        authority = request.GET.get("trackId")
        success_param = request.GET.get("success")
        return {
            "authority": authority,
            "is_customer_cancelled": success_param != "1",
        }
