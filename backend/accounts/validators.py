"""
Validation and normalization for Iranian mobile phone numbers.

Iranian mobile numbers are commonly written in three equivalent formats:
    - Local:          09123456789      (11 digits, leading 0)
    - International:  +989123456789    (with + country prefix)
    - International:  00989123456789   (with 00 trunk prefix instead of +)

In every case, once any country/trunk prefix is stripped, what's left is
a 10-digit subscriber number starting with 9 (e.g. "9123456789").
"""

import re

from django.core.validators import RegexValidator

# Accepts: 09123456789, +989123456789, 00989123456789 — rejects anything
# that doesn't start with 9 (after any recognized prefix) followed by
# exactly 9 more digits (10 digits total after the prefix).
iranian_phone_regex = RegexValidator(
    regex=r"^(\+98|0098|0)?9\d{9}$",
    message="Enter a valid Iranian mobile number (e.g. 09123456789).",
)

_PREFIX_RE = re.compile(r"^(\+98|0098|0)?(9\d{9})$")


def normalize_iranian_phone(value: str) -> str:
    """
    Normalize any accepted Iranian mobile number format to a single
    canonical stored form: local format, "09XXXXXXXXX" (11 digits,
    leading zero).

    This matches Kavenegar's documented/SDK-example input format for SMS
    `receptor` numbers, which consistently show local-format numbers
    like "09123456789" or "09361234567" across their REST, Node, PHP,
    and Ruby examples/docs — not the "98XXXXXXXXXX" (no leading zero)
    form. Using the same format we'll hand to the SMS gateway avoids an
    extra conversion step at send time.

    Raises ValueError if `value` doesn't match the expected Iranian
    mobile format — callers that need a friendly, user-facing message
    should validate with `iranian_phone_regex` (e.g. via a model/
    serializer field) before calling this function.
    """
    match = _PREFIX_RE.match(value or "")
    if not match:
        raise ValueError(f"{value!r} is not a valid Iranian mobile number.")
    subscriber_number = match.group(2)  # e.g. "9123456789"
    return f"0{subscriber_number}"
