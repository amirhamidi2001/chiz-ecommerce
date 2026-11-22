"""
Kavenegar SMS provider — the real, production SMSProvider.

Endpoint, request fields and response shape below were verified against
Kavenegar's official client code (github.com/kavenegar/kavenegar-python,
``kavenegar.py``, which names kavenegar.com/rest.html as its API reference)
at the time this was written:

- ``POST https://api.kavenegar.com/v1/{API-KEY}/sms/send.json`` — the API key
  travels in the URL *path* (there is no auth header).
- The body is form-encoded: ``receptor`` (required), ``message`` (required) and
  ``sender`` (optional — when omitted Kavenegar uses the account's default
  line). Local-format numbers like ``09123456789`` are what their docs use,
  and what ``accounts.validators.normalize_iranian_phone`` already produces.
- Success is ``{"return": {"status": 200, "message": "..."}, "entries": [...]}``.
  Any other ``return.status`` is a rejection, with a (Persian) reason in
  ``return.message``.

NOT verified — kavenegar.com/rest.html itself could not be fetched: the full
table of error codes, and whether API-level errors arrive as HTTP 4xx or as
HTTP 200 with the code in the body (sources disagree: the official SDK treats
4xx/5xx as errors; a third-party client documents 200-with-body-status). This
provider is written to be correct either way: the JSON body is parsed whatever
the HTTP status, and success requires BOTH a non-error HTTP status and
``return.status == 200``.
No specific error code is hardcoded; whatever Kavenegar says is logged.

Two properties worth keeping if you edit this file:

* The API key must never reach a log. ``requests`` exception messages contain
  the full request URL — i.e. the key — so every exception text goes through
  ``_scrub()``, the same masking Kavenegar's own client applies.
* The message body is never logged: for OTP it is the verification code.

``send()`` never raises; it logs and returns False (same discipline as the
payment gateways), so callers see only the SMSProvider bool contract.
"""

import logging
from urllib.parse import quote

import requests
from django.conf import settings

from .base import SMSProvider

logger = logging.getLogger("notifications.sms")


class KavenegarSMSProvider(SMSProvider):
    BASE_URL = "https://api.kavenegar.com/v1"
    REQUEST_TIMEOUT_SECONDS = 15

    def send(self, phone_number: str, message: str) -> bool:
        try:
            return self._send(phone_number, message)
        except Exception as exc:  # noqa: BLE001 — send() must never raise
            logger.error(
                "Kavenegar send to %s raised unexpectedly: %s: %s",
                phone_number,
                type(exc).__name__,
                self._scrub(exc),
            )
            return False

    def _send(self, phone_number: str, message: str) -> bool:
        api_key = getattr(settings, "KAVENEGAR_API_KEY", "")
        if not api_key:
            logger.error(
                "KAVENEGAR_API_KEY is not configured; SMS to %s was not sent.",
                phone_number,
            )
            return False

        payload = {"receptor": phone_number, "message": message}
        # `sender` is optional; omit it (rather than send "") to use the
        # account's default line.
        sender = getattr(settings, "KAVENEGAR_SENDER_LINE", "")
        if sender:
            payload["sender"] = sender

        url = f"{self.BASE_URL}/{api_key}/sms/send.json"

        try:
            response = requests.post(
                url, data=payload, timeout=self.REQUEST_TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            logger.error(
                "Kavenegar request for %s failed (%s): %s",
                phone_number,
                type(exc).__name__,
                self._scrub(exc),
            )
            return False

        # Parse the body BEFORE judging the HTTP status: Kavenegar's
        # actionable reason lives in the JSON body, even on a 4xx.
        try:
            data = response.json()
        except ValueError:
            logger.error(
                "Kavenegar returned a non-JSON response for %s (HTTP %s).",
                phone_number,
                response.status_code,
            )
            return False

        result = data.get("return") if isinstance(data, dict) else None
        if not isinstance(result, dict):
            result = {}
        status = result.get("status")

        if response.ok and status == 200:
            return True

        # Only status + message are logged — never the whole body, which can
        # echo the SMS text (the OTP code) back in `entries`.
        logger.error(
            "Kavenegar rejected SMS to %s: HTTP %s, return.status=%s, message=%s",
            phone_number,
            response.status_code,
            status,
            result.get("message"),
        )
        return False

    @staticmethod
    def _scrub(value) -> str:
        """str(value) with the API key (raw or URL-quoted) masked."""
        text = str(value)
        key = getattr(settings, "KAVENEGAR_API_KEY", "") or ""
        if key:
            masked = f"{key[:2]}********{key[-2:]}" if len(key) > 8 else "********"
            for variant in {key, quote(key, safe="")}:
                text = text.replace(variant, masked)
        return text
