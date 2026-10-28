"""Template filters for server-rendered money (PDF invoice, emails). ADR 0001 §6."""

from core.money import RIAL_PER_TOMAN
from django import template

register = template.Library()


@register.filter
def rial(value):
    """1858020 -> '1,858,020' (Rial, Latin digits, grouped)."""
    return f"{int(value):,}"


@register.filter
def toman(value):
    """1858020 -> '185,802' (Toman = Rial / 10, exact by invariant I-2)."""
    value = int(value)
    if value % RIAL_PER_TOMAN:
        raise ValueError(f"{value} Rial is not a whole number of Toman (I-2).")
    return f"{value // RIAL_PER_TOMAN:,}"
