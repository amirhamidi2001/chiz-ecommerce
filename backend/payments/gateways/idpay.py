"""
IDPay payment gateway (Task 6.3.1.2), implementing the same PaymentGateway
interface as ZarinPalGateway (Tasks 6.2.1.1/6.2.1.3) and ZibalGateway
(Task 6.3.1.1).

Endpoint URLs, auth mechanism, field names, and status codes below were
verified against IDPay's own official documentation
(https://idpay.ir/web-service/v1.1/ — includes a live curl example for
the verify call) and cross-checked against several independent
third-party client libraries (Go, .NET, PHP/CodeIgniter, a Drupal
payment module) that all agree on the same shapes, at the time this was
written:

- Auth is via HTTP HEADERS, not payload fields — a THIRD distinct
  mechanism among this codebase's three gateways: ZarinPal uses a
  separate sandbox subdomain (Task 6.2.1.1), Zibal uses a special
  literal merchant value (Task 6.3.1.1), and IDPay uses:
    Content-Type: application/json
    X-API-KEY: <IDPAY_API_KEY>
    X-SANDBOX: "1" or "0"
  X-SANDBOX is IDPay's actual sandbox/production toggle — confirmed
  directly from IDPay's own curl example. This is why IDPAY_SANDBOX
  exists as a genuine boolean setting here (unlike Zibal, which has no
  such setting) — IDPay really does have a mode flag, it's just sent as
  a header instead of encoded in the URL.
- Endpoints (single host in every mode — the header controls sandbox,
  not the URL):
    Create: POST https://api.idpay.ir/v1.1/payment
    Verify: POST https://api.idpay.ir/v1.1/payment/verify
- Create request payload: {"order_id", "amount", "callback", "desc"}
  (optional "name"/"phone"/"mail" omitted — this codebase's
  PaymentGateway interface doesn't carry customer contact details).
  `amount` is an integer number of Rials (IRR) — same unit as
  ZarinPal/Zibal.
- Create success response: {"id": "<idpay transaction id>", "link":
  "<full redirect URL>"}. Unlike ZarinPal/Zibal, IDPay returns the
  COMPLETE redirect URL directly as `link` — there's no
  authority/trackId-to-URL template to build client-side.
- Verify request payload: {"id", "order_id"} — BOTH fields, confirmed
  required together by IDPay's own curl example. This is a genuine
  interface mismatch worth calling out: this codebase's
  PaymentGateway.verify_payment(authority, amount) has no `order_id`
  parameter, because ZarinPal/Zibal only need a single authority/
  trackId value to verify. IDPay's `order_id` is a value >>we<< choose
  at request time (a merchant-supplied identifier, not something IDPay
  generates), so it isn't retrievable from IDPay's `id` alone at verify
  time. Rather than adding an IDPay-specific parameter to the shared
  interface (which ZarinPal/Zibal don't need and shouldn't have to
  accept), this gateway packs BOTH values into the single `authority`
  string it returns from request_payment(), as "{id}:{order_id}", and
  unpacks them again in verify_payment(). PaymentTransaction.authority
  is a max_length=100 CharField; IDPay's `id` and a uuid4 hex `order_id`
  together comfortably fit (32 + 1 + 32 = 65 chars).
- Verify success response includes `status` and `track_id` (IDPay's
  settlement reference, used here as ref_id). Confirmed success codes —
  per a maintained third-party library that explicitly documents this
  exact rule after auditing IDPay's behavior — are status 100, 101, AND
  200 (three distinct "this payment is genuinely settled" values, more
  than ZarinPal's two or Zibal's two).
- Error envelope on both endpoints: {"error_code": ..., "error_message":
  ...}. This gateway deliberately does NOT call
  response.raise_for_status(): unlike ZarinPal/Zibal (confirmed to
  always return HTTP 200 with an internal result code even on failure),
  IDPay's exact HTTP-status-on-error convention could not be confirmed
  with the same confidence — its error envelope is clearly documented,
  but whether it's always delivered on a 200 or sometimes on a 4xx/5xx
  wasn't. Parsing the JSON body regardless of status is safe either way
  and avoids discarding a genuinely informative error body in favor of
  a generic HTTP error string.
"""

import uuid
from decimal import Decimal

import requests
from django.conf import settings

from .base import PaymentGateway, PaymentRequestResult, PaymentVerifyResult

_VERIFY_SUCCESS_STATUSES = (100, 101, 200)


class IDPayGateway(PaymentGateway):
    REQUEST_URL = "https://api.idpay.ir/v1.1/payment"
    VERIFY_URL = "https://api.idpay.ir/v1.1/payment/verify"

    REQUEST_TIMEOUT_SECONDS = 15

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "X-API-KEY": settings.IDPAY_API_KEY,
            "X-SANDBOX": "1" if settings.IDPAY_SANDBOX else "0",
        }

    def request_payment(
        self, amount: Decimal, callback_url: str, description: str = ""
    ) -> PaymentRequestResult:
        # IDPay requires a merchant-supplied, unique `order_id` per
        # transaction — this codebase's generic PaymentGateway interface
        # doesn't carry a domain order id into this call, so a fresh
        # opaque one is generated here purely to satisfy IDPay's
        # uniqueness requirement. It's packed into the returned
        # `authority` (see module docstring) so verify_payment() can
        # send it back later.
        order_id = uuid.uuid4().hex
        payload = {
            "order_id": order_id,
            "amount": int(amount),
            "callback": callback_url,
            "desc": description or "Order payment",
        }

        try:
            response = requests.post(
                self.REQUEST_URL,
                json=payload,
                headers=self._headers(),
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            # Deliberately NOT calling response.raise_for_status() here.
            # Unlike ZarinPal/Zibal — where multiple independent sources
            # confirmed errors always come back as HTTP 200 with an
            # internal result code — IDPay's exact HTTP-status-on-error
            # convention could not be confirmed with the same confidence
            # (its error envelope {"error_code", "error_message"} is
            # clearly documented, but whether it always arrives on a 200
            # response or sometimes on a 4xx/5xx wasn't). Parsing the
            # body regardless of status code is safe either way: if
            # IDPay does send a real error JSON body alongside a non-200
            # status, raise_for_status() would have discarded it in
            # favor of a generic "400 Client Error" message, which is
            # strictly worse. Connection errors/timeouts are still
            # raised by requests.post() itself and caught below either
            # way.
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            return PaymentRequestResult(success=False, error_message=str(exc))

        if isinstance(data, dict) and data.get("id") and data.get("link"):
            authority = f"{data['id']}:{order_id}"
            return PaymentRequestResult(
                success=True,
                authority=authority,
                redirect_url=data["link"],
            )

        return PaymentRequestResult(
            success=False,
            error_message=self._extract_error_message(
                data, default="IDPay payment request failed."
            ),
        )

    def verify_payment(self, authority: str, amount: Decimal) -> PaymentVerifyResult:
        idpay_id, _, order_id = authority.partition(":")
        if not idpay_id or not order_id:
            return PaymentVerifyResult(
                success=False,
                error_message=f"Malformed IDPay authority: {authority!r}",
                raw_response=None,
            )

        payload = {"id": idpay_id, "order_id": order_id}

        try:
            response = requests.post(
                self.VERIFY_URL,
                json=payload,
                headers=self._headers(),
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            # See request_payment() above for why raise_for_status() is
            # deliberately not called here.
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            return PaymentVerifyResult(
                success=False, error_message=str(exc), raw_response=None
            )

        status_code = data.get("status") if isinstance(data, dict) else None
        # 100/101/200 are all valid, non-error "this payment is settled"
        # outcomes for an idempotent verify call — see module docstring.
        if status_code in _VERIFY_SUCCESS_STATUSES:
            return PaymentVerifyResult(
                success=True,
                ref_id=str(data.get("track_id", "")),
                raw_response=data,
            )

        return PaymentVerifyResult(
            success=False,
            error_message=self._extract_error_message(
                data, default="IDPay payment verification failed."
            ),
            raw_response=data,
        )

    @staticmethod
    def _extract_error_message(data, default: str) -> str:
        """
        IDPay reports errors via a dedicated {"error_code",
        "error_message"} envelope, distinct from its success-response
        shape — but this isn't guaranteed present on every failure mode,
        so fall back to a generic default rather than assuming the key
        is always there.
        """
        if isinstance(data, dict):
            message = data.get("error_message")
            code = data.get("error_code")
            if message:
                return (
                    f"{message} (error_code: {code})" if code is not None else message
                )
        return default

    def extract_callback_params(self, request) -> dict:
        """
        IDPay's documented callback query parameters — confirmed against
        an independent CodeIgniter client library (which reads exactly
        ``status``, ``track_id``, ``id``, ``order_id`` off the callback
        request) and cross-checked against a Go client library's
        callback handler signature, which takes the same four fields.

        ``id`` and ``order_id`` together reconstruct the SAME composite
        authority this gateway returns from request_payment() and
        expects back in verify_payment() (see module docstring for why
        IDPay's authority is a composite "{id}:{order_id}" string —
        IDPay's own API genuinely requires both values together).

        ``status`` here uses the SAME numeric status-code space as the
        verify response. Per IDPay's documented status table, code 1
        means "Payment has not been done" — this is IDPay's own
        definitive "the customer never completed payment" signal
        (mirroring ZarinPal's Status=NOK and Zibal's success=0). Any
        other status value still goes through verify_payment() for an
        authoritative answer, rather than trusting a client-controlled
        redirect parameter — including status values that look like
        failures, since verify_payment() gives a proper, specific error
        message rather than a generic "cancelled" one.
        """
        idpay_id = request.GET.get("id")
        order_id = request.GET.get("order_id")
        status_param = request.GET.get("status")
        authority = f"{idpay_id}:{order_id}" if idpay_id and order_id else ""
        return {
            "authority": authority,
            "is_customer_cancelled": status_param == "1",
        }
