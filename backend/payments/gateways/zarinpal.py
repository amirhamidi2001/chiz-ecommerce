"""
ZarinPal payment gateway (Task 6.2.1.1 — request_payment only;
verify_payment lands in Task 6.2.1.3).

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
    def _extract_error_message(errors) -> str:
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
        return "ZarinPal payment request failed."

    def verify_payment(self, authority: str, amount: Decimal) -> PaymentVerifyResult:
        raise NotImplementedError  # implemented in Task 6.2.1.3
