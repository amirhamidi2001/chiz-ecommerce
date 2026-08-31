"""
Validation for product barcodes.

EAN-13 (European Article Number, 13 digits) is the barcode standard used
on virtually all retail packaging, including cosmetics — the format
`ProductVariant.barcode` is expected to hold for warehouse/POS scanning
integration and eventual Iranian regulatory barcode requirements.

An EAN-13 barcode is 13 digits: 12 data digits followed by 1 check digit.
The check digit isn't arbitrary — it's a checksum computed from the first
12 digits, specifically so that transposed-digit typos and other common
data-entry mistakes are almost always caught (a bare "is this 13 digits?"
regex would silently accept a barcode with two digits swapped, defeating
the entire point of having a check digit).
"""

from django.core.exceptions import ValidationError

EAN13_LENGTH = 13


def _compute_ean13_check_digit(first_12_digits: str) -> int:
    """
    Given the first 12 digits of an EAN-13 barcode (as a string),
    compute the expected 13th (check) digit using the standard EAN-13
    algorithm:

        1. Sum the digits at odd positions (1st, 3rd, 5th, ... 11th,
           i.e. 1-indexed odd positions).
        2. Sum the digits at even positions (2nd, 4th, ... 12th) and
           multiply that sum by 3.
        3. Add the two sums together.
        4. The check digit is whatever value, when added to that total,
           makes it a multiple of 10 — i.e. `(10 - (total % 10)) % 10`.
    """
    odd_sum = sum(int(d) for d in first_12_digits[0::2])  # positions 1,3,...,11
    even_sum = sum(int(d) for d in first_12_digits[1::2])  # positions 2,4,...,12
    total = odd_sum + (even_sum * 3)
    return (10 - (total % 10)) % 10


def validate_ean13(value):
    """
    Django/DRF-style validator: raises ValidationError if `value` isn't
    a well-formed EAN-13 barcode (exactly 13 digits, with a correct
    check digit), otherwise returns None.

    A plain module-level function, matching the style already
    established in accounts/validators.py (iranian_phone_regex /
    normalize_iranian_phone) for this project's per-app validators.py
    convention. Django serializes a reference to this function by its
    import path in migrations, so no extra decoration is needed for it
    to work inside `validators=[...]` on a model field.
    """
    value = str(value)
    if len(value) != EAN13_LENGTH or not value.isdigit():
        raise ValidationError(
            "Enter a valid EAN-13 barcode (13 digits with a valid check digit).",
            code="invalid_ean13",
        )

    expected_check_digit = _compute_ean13_check_digit(value[:12])
    actual_check_digit = int(value[12])
    if actual_check_digit != expected_check_digit:
        raise ValidationError(
            "Enter a valid EAN-13 barcode (13 digits with a valid check digit).",
            code="invalid_ean13",
        )
