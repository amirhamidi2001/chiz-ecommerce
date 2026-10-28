# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  MONEY RE-BASELINING — READ BEFORE RUNNING AGAINST ANY REAL DATA          ║
# ╚══════════════════════════════════════════════════════════════════════════╝
# Task 14.1.2.2 / ADR 0001 (docs/adr/0001-currency-storage.md).
#
# Every money value in this system was a dollar-shaped DecimalField (e.g.
# 29.99) holding TEST / SEED data — never real Rial. This step RE-BASELINES it:
#
#       new_rial = ROUND(old_decimal * 10_000, -1)      # nearest multiple of 10
#
# i.e. an old "$29.99" becomes 299,900 Rial. The factor is ARBITRARY but
# documented and CONSISTENT across every money column (and the seed command
# uses the same one), so test data keeps its relative magnitudes and its
# arithmetic relationships. Every legacy 2-decimal value x 10,000 is already a
# multiple of 100, so the rounding only matters for malformed legacy values.
#
# THIS IS NOT A CURRENCY CONVERSION. If the target database holds REAL
# customer financial history, STOP: the factor is wrong for real money. A real
# conversion (or freezing historical orders as a legacy reference while only
# new data uses the new scheme) must be designed and signed off by whoever
# owns the business's pricing data. To make that impossible to do by accident,
# this migration refuses to modify a non-empty money table unless
# MONEY_REBASELINE_CONFIRMED=true is set in the environment.
#
# Step 2/3 for `order`. Reversible (divides by 10,000 and rounds to 2 places).

from django.conf import settings
from django.db import migrations
from django.db.models import F
from django.db.models.functions import Round

APP = "order"
FACTOR = 10_000

# (model, money fields) re-baselined by this migration.
TARGETS = [
    ("Order", ["subtotal", "shipping_cost", "tax", "discount", "total"]),
    ("OrderItem", ["unit_price"]),
]


def _guard(apps):
    populated = {name: apps.get_model(APP, name).objects.count() for name, _ in TARGETS}
    populated = {k: v for k, v in populated.items() if v}
    if populated and not getattr(settings, "MONEY_REBASELINE_CONFIRMED", False):
        raise RuntimeError(
            "Refusing to re-baseline money columns: these tables already contain "
            f"rows ({populated}). This migration multiplies legacy dollar-shaped "
            "TEST/SEED values by 10,000 to produce Rial and is NOT valid for real "
            "financial data. If (and only if) this database holds seed/test data "
            "only, set MONEY_REBASELINE_CONFIRMED=true and re-run."
        )


def forwards(apps, schema_editor):
    _guard(apps)
    for model_name, fields in TARGETS:
        Model = apps.get_model(APP, model_name)
        for field in fields:
            qs = Model.objects.exclude(**{field + "__isnull": True})
            qs.update(**{field: Round(F(field) * FACTOR, precision=-1)})


def backwards(apps, schema_editor):
    for model_name, fields in TARGETS:
        Model = apps.get_model(APP, model_name)
        for field in fields:
            qs = Model.objects.exclude(**{field + "__isnull": True})
            qs.update(**{field: Round(F(field) / FACTOR, precision=2)})


class Migration(migrations.Migration):

    dependencies = [
        ("order", "0004_money_widen_decimals"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
