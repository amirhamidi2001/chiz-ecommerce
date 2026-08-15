"""
Lightweight SMS provider interface (Feature 2.2.1).

Placement decision: this lives under backend/accounts/sms/ as a plain
Python package rather than a new Django app. The interface defined
here (SMSProvider + get_sms_provider()) has no models and needs no
migrations — accounts is currently its only consumer (via the OTP
service, Feature 2.1.2). The project backlog's Epic 16 plans a full
`notifications` Django app later (covering more than just SMS); when
that lands, this package can be relocated/absorbed into it wholesale
with a simple import-path update, without having carried an unused
Django app (empty migrations/, apps.py, INSTALLED_APPS entry) in the
meantime. This mirrors the existing accounts/services/ package in this
same app, which follows the same "plain package, no models" pattern.
"""

from .base import SMSProvider, get_sms_provider

__all__ = ["SMSProvider", "get_sms_provider"]
