# Step 3/5 of the Task 14.1.2.2 money migration for `promotions` (ADR 0001 §7.3).
#
# SCHEMA ONLY. Coupon.value was dual-purpose (a 0-100 percentage for PERCENT
# coupons, a currency amount for FIXED ones). It is split into two explicit
# columns — `percent_off` (decimal percentage) and `fixed_amount` (integer
# Rial) — added here as nullable. `value` is made nullable now so that REVERSING
# the later RemoveField can re-add it on a populated table. The next migration
# copies the data across; the one after drops `value` and adds the constraints.
# The two plain Rial columns are converted to integers here (their values were
# already re-baselined to whole-Toman multiples by 0006).

from decimal import Decimal

import core.fields
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0006_money_rebaseline_to_rial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="coupon",
            name="value",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=24, null=True
            ),
        ),
        migrations.AddField(
            model_name="coupon",
            name="fixed_amount",
            field=core.fields.RialField(
                blank=True,
                help_text="Fixed discount in Rial (a multiple of 10); used only when discount_type=fixed.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="coupon",
            name="percent_off",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Percentage (0.01-100); used only when discount_type=percent.",
                max_digits=5,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.01")),
                    django.core.validators.MaxValueValidator(Decimal("100")),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="coupon",
            name="min_order_amount",
            field=core.fields.RialField(
                default=0,
                help_text="Cart subtotal must be at least this amount for the coupon to apply.",
            ),
        ),
        migrations.AlterField(
            model_name="couponredemption",
            name="discount_amount",
            field=core.fields.RialField(
                help_text="Actual currency amount discounted by this redemption (frozen at redemption time)."
            ),
        ),
    ]
