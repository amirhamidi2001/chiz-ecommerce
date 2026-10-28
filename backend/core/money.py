"""
core/money.py
─────────────
The ONE place money rules live (ADR 0001, docs/adr/0001-currency-storage.md).

  * Every monetary amount is a plain Python ``int`` of legacy Rial (IRR).
  * Every stored/transmitted amount is a multiple of 10 Rial = whole Toman
    (invariant I-2), so ``rial // 10`` is always exact.
  * Anything that can produce a non-multiple (tax, a percentage coupon, a
    flash-sale price) rounds ONCE, at that step, through
    :func:`to_whole_toman_rial` — never carry a fractional intermediate on.
  * Rial <-> Toman conversion exists only here and in
    ``frontend/src/utils/money.js`` (invariant I-5).

Rounding is nearest whole Toman, ties up (ROUND_HALF_UP). Python's
``Decimal.quantize`` default is ROUND_HALF_EVEN, so the mode is explicit.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Union

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

RIAL_PER_TOMAN = 10

# Largest amount the application accepts anywhere (ADR §4): 10 billion Toman.
# Chosen so basis-point math in the browser (amount * 10_000) stays below
# Number.MAX_SAFE_INTEGER (2**53 - 1); BigInteger storage is far larger.
MAX_RIAL_AMOUNT = 10**11

Number = Union[int, Decimal]


def to_whole_toman_rial(value: Number) -> int:
    """Round an exact Rial value to the nearest multiple of 10, ties up."""
    tomans = (Decimal(value) / RIAL_PER_TOMAN).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    )
    return int(tomans) * RIAL_PER_TOMAN


def percent_of(amount_rial: int, percent: Number) -> int:
    """``percent`` % of ``amount_rial`` as a whole-Toman Rial integer.

    ``percent`` is a Decimal/int percentage (``Decimal("12.50")``), never a
    float. The product is exact in Decimal and rounded exactly once.
    """
    return to_whole_toman_rial(Decimal(amount_rial) * Decimal(percent) / Decimal(100))


def rial_to_toman(rial: int) -> int:
    if rial % RIAL_PER_TOMAN:
        raise ValueError(f"{rial} Rial is not a whole number of Toman (invariant I-2).")
    return rial // RIAL_PER_TOMAN


def toman_to_rial(toman: int) -> int:
    return int(toman) * RIAL_PER_TOMAN


def validate_whole_toman(value) -> None:
    """Django/DRF validator for invariant I-2."""
    if value is not None and int(value) % RIAL_PER_TOMAN:
        raise ValidationError(
            _("Amount must be a whole number of Toman (a multiple of 10 Rial)."),
            code="not_whole_toman",
        )


def validate_max_rial(value) -> None:
    if value is not None and int(value) > MAX_RIAL_AMOUNT:
        raise ValidationError(
            _("Amount cannot exceed %(max)s Rial."),
            code="amount_too_large",
            params={"max": MAX_RIAL_AMOUNT},
        )


def format_rial(value) -> str:
    """``1858020`` -> ``'1,858,020 Rial'`` (staff-facing admin; stored unit)."""
    return f"{int(value):,} Rial"
