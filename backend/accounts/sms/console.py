"""
Console SMS provider — local development / CI only.

"Sends" SMS by printing to the terminal and logging, with no network
call and no vendor credentials required. This is what makes the OTP
flow developable, demoable, and testable end-to-end today, ahead of
real vendor integration (Kavenegar, tracked separately in Epic 16).
"""

import logging

from .base import SMSProvider

logger = logging.getLogger("accounts.sms")


class ConsoleSMSProvider(SMSProvider):
    """
    Dev/CI-only SMSProvider that prints and logs instead of sending a
    real SMS.

    !! MUST NEVER BE USED IN PRODUCTION !! — `send()` always returns
    True without actually delivering anything, so relying on this in a
    live deployment would silently "succeed" while no SMS is ever sent
    to any real phone. `core/settings/production.py` deliberately does
    NOT set SMS_PROVIDER_CLASS to this class (see that file / Task
    2.2.1.3 / Epic 16 for the real vendor decision) — only
    `core/settings/development.py` does.
    """

    def send(self, phone_number: str, message: str) -> bool:
        logger.info("SMS to %s: %s", phone_number, message)
        print(f"[DEV SMS] To: {phone_number} | Message: {message}")
        return True
