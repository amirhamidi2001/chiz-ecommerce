"""
SMS provider interface (Feature 2.2.1, relocated in Epic 16).

Originally built under backend/accounts/sms/ as a plain package because
accounts (via the OTP service) was its only consumer and a full Django
app wasn't yet warranted. Epic 16 introduced the `notifications` app,
and this package was moved here wholesale — same internal structure
(base.py, console.py), no behavior change — so all notification-domain
code (SMS, and later email and in-app notifications) has a single home.
The only things that changed are import paths, the SMS_PROVIDER_CLASS
default (now notifications.sms.console.ConsoleSMSProvider) and the
logger name used by the console provider.
"""

from .base import SMSProvider, get_sms_provider

__all__ = ["SMSProvider", "get_sms_provider"]
