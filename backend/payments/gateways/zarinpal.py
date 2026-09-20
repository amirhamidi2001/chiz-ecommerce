"""
ZarinPal payment gateway: request_payment() (Task 6.2.1.1) and
verify_payment() (Task 6.2.1.3).

Endpoint URLs, request field names and response shape below were
verified against ZarinPal's current official REST API documentation
(zarinpal.com/docs/paymentGateway/connectToGateway) at the time this
was written:

- The v4 payment-request endpoint's production host is
  ``payment.zarinpal.com`` — NOT ``api.zarinpal.com`` (that host is
  used for ZarinPal's older/other services; several third-party
  wrapper libraries get this wrong, which is why it's worth calling
  out explicitly here).
- ``amount`` is sent as an integer number of Iranian Rials (IRR), not
  Toman and not a decimal. This is easy to get backwards — ZarinPal's
  own dashboard displays amounts in Toman, but the v4 REST API itself
  expects Rial. Getting this wrong under- or over-charges customers by
  a factor of 10.
- On success, the response looks like::

      {
        "data": {
          "code": 100,
          "message": "Success",
          "authority": "A0000000000000000000000000000wwOGYpd",
          "fee_type": "Merchant",
          "fee": 100
        },
        "errors": []
      }

  (note: ``errors`` is an empty *list* on success — that's a genuine
  quirk of ZarinPal's API, not a typo.)
- On failure, ``data`` is typically an empty list/object and
  ``errors`` is an object shaped like
  ``{"code": ..., "message": ..., "validations": {...}}``.
- ``verify_payment()``'s success response has the same
  ``{"data": {"code", ...}}`` shape, plus ``ref_id``. Codes ``100``
  (verified just now) and ``101`` (already verified — e.g. the
  customer hit the callback URL twice) are BOTH treated as success,
  confirmed against ZarinPal's official SDK docs and maintainer
  guidance (a second verify call for an already-settled authority is
  not a payment failure).
"""

from decimal import Decimal

import requests
from django.conf import settings

from .base import PaymentGateway, PaymentRequestResult, PaymentVerifyResult


class ZarinPalGateway(PaymentGateway):
    REQUEST_URL = (
        "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
        if settings.ZARINPAL_SANDBOX
        else "https://payment.zarinpal.com/pg/v4/payment/request.json"
    )
    START_PAY_URL = (
        "https://sandbox.zarinpal.com/pg/StartPay/{authority}"
        if settings.ZARINPAL_SANDBOX
        else "https://www.zarinpal.com/pg/StartPay/{authority}"
    )

    REQUEST_TIMEOUT_SECONDS = 15

    VERIFY_URL = (
        "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
        if settings.ZARINPAL_SANDBOX
        else "https://payment.zarinpal.com/pg/v4/payment/verify.json"
    )
    # Same production-host correction as REQUEST_URL above: the verify
    # endpoint's canonical production host is payment.zarinpal.com, not
    # api.zarinpal.com — confirmed against current ZarinPal docs.

    def request_payment(
        self, amount: Decimal, callback_url: str, description: str = ""
    ) -> PaymentRequestResult:
        # ZarinPal's v4 REST API expects `amount` as an integer number of
        # Rials (IRR) — see module docstring. This platform's internal
        # currency unit is decided in the project's localization work;
        # `amount` here is assumed to already be in Rial by the time it
        # reaches this gateway (no unit conversion is applied here).
        payload = {
            "merchant_id": settings.ZARINPAL_MERCHANT_ID,
            "amount": int(amount),
            "callback_url": callback_url,
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

        result_data = data.get("data") or {}
        if isinstance(result_data, dict) and result_data.get("code") == 100:
            authority = result_data["authority"]
            return PaymentRequestResult(
                success=True,
                authority=authority,
                redirect_url=self.START_PAY_URL.format(authority=authority),
            )

        return PaymentRequestResult(
            success=False,
            error_message=self._extract_error_message(data.get("errors")),
        )

    @staticmethod
    def _extract_error_message(
        errors, default: str = "ZarinPal payment request failed."
    ) -> str:
        """
        ZarinPal's `errors` field is an empty list on success and, on
        failure, an object shaped like {"code", "message",
        "validations"} — but this isn't guaranteed byte-accurate across
        every failure mode, so fall back to stringifying whatever came
        back rather than assuming a key is always present.
        """
        if isinstance(errors, dict):
            message = errors.get("message")
            code = errors.get("code")
            if message:
                return f"{message} (code: {code})" if code is not None else message
        if errors:
            return str(errors)
        return default

    def verify_payment(self, authority: str, amount: Decimal) -> PaymentVerifyResult:
        # IMPORTANT: `amount` must be the exact same value (and unit —
        # Rial, per request_payment()) that was sent when the payment was
        # first requested. A mismatched amount is itself grounds for
        # ZarinPal to reject the verification, so the caller must pass
        # the same order total used at request time, not a recomputed or
        # reformatted value.
        payload = {
            "merchant_id": settings.ZARINPAL_MERCHANT_ID,
            "authority": authority,
            "amount": int(amount),
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

        result_data = data.get("data") or {}
        # Codes 100 (verified just now) and 101 (already verified) are
        # BOTH valid non-error outcomes for an idempotent verify call —
        # confirmed against ZarinPal's own SDK docs and maintainer
        # guidance. A customer double-hitting the callback URL (e.g. via
        # browser back-button/refresh) triggers a second verify call for
        # an already-settled authority, which comes back as 101 — that
        # must NOT be treated as a payment failure.
        if isinstance(result_data, dict) and result_data.get("code") in (100, 101):
            return PaymentVerifyResult(
                success=True,
                ref_id=str(result_data.get("ref_id", "")),
                raw_response=data,
            )

        return PaymentVerifyResult(
            success=False,
            error_message=self._extract_error_message(
                data.get("errors"), default="ZarinPal payment verification failed."
            ),
            raw_response=data,
        )

    def extract_callback_params(self, request) -> dict:
        """
        ZarinPal's documented callback query parameters (confirmed
        against multiple independent SDKs — see Task 6.2.1.4's original
        research): ``Authority`` (the same authority returned from
        request_payment()) and ``Status``, whose value is the literal
        string "OK" or "NOK". "NOK" is ZarinPal's own definitive
        "customer cancelled/failed before verification" signal — moved
        here from PaymentCallbackView's original inline extraction
        (Task 6.2.1.4/6.2.1.5) once Zibal/IDPay's very different
        parameter conventions made clear that logic needed to live on
        the gateway, not the view (Task 6.3.1.4).
        """
        authority = request.GET.get("Authority") or request.GET.get("authority")
        status_param = request.GET.get("Status") or request.GET.get("status")
        return {
            "authority": authority,
            "is_customer_cancelled": status_param == "NOK",
        }
