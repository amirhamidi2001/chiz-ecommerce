"""
core/fields.py
──────────────
``RialField`` marks every monetary column (ADR 0001, decision D7). It IS a
``PositiveBigIntegerField`` underneath — the marker exists so the set of money
columns is machine-checkable (MoneyFieldRegistryTests in core/tests/test_money.py) and so the
validators and the DB constraint cannot be forgotten.
"""

from django.db import models
from django.db.models.functions import Mod
from django.db.models.lookups import Exact

from .money import RIAL_PER_TOMAN, validate_max_rial, validate_whole_toman


class RialField(models.PositiveBigIntegerField):
    """An amount of legacy Rial, whole-Toman granularity, 0..MAX_RIAL_AMOUNT."""

    description = "Amount in Rial (a multiple of 10)"
    default_validators = [validate_whole_toman, validate_max_rial]


def whole_toman_constraint(field_name: str) -> models.CheckConstraint:
    """DB-level guard for invariant I-2: ``field % 10 = 0`` (NULL passes)."""
    return models.CheckConstraint(
        condition=Exact(Mod(field_name, RIAL_PER_TOMAN), 0),
        name=f"%(app_label)s_%(class)s_{field_name}_whole_toman",
    )
