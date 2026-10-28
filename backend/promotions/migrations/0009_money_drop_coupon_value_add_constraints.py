# Step 5/5 of the Task 14.1.2.2 money migration for `promotions` (ADR 0001).
#
# SCHEMA ONLY: drop the legacy dual-purpose `value` column and add the
# whole-Toman (multiple of 10) CHECK constraints plus the constraint that ties
# the two coupon columns to `discount_type`. The type-match constraint is
# validated against the rows copied by 0008, so inconsistent legacy coupons
# (e.g. a PERCENT coupon over 100) fail loudly here instead of being kept.

import django.db.models.functions.math
import django.db.models.lookups
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0008_money_split_coupon_data"),
    ]

    operations = [
        migrations.RemoveField(model_name="coupon", name="value"),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.CheckConstraint(
                condition=django.db.models.lookups.Exact(
                    django.db.models.functions.math.Mod("min_order_amount", 10), 0
                ),
                name="promotions_coupon_min_order_amount_whole_toman",
            ),
        ),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.CheckConstraint(
                condition=django.db.models.lookups.Exact(
                    django.db.models.functions.math.Mod("fixed_amount", 10), 0
                ),
                name="promotions_coupon_fixed_amount_whole_toman",
            ),
        ),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("discount_type", "percent"),
                        ("fixed_amount__isnull", True),
                        ("percent_off__gt", 0),
                        ("percent_off__lte", 100),
                    ),
                    models.Q(
                        ("discount_type", "fixed"),
                        ("fixed_amount__gt", 0),
                        ("percent_off__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="promotions_coupon_discount_fields_match_type",
            ),
        ),
        migrations.AddConstraint(
            model_name="couponredemption",
            constraint=models.CheckConstraint(
                condition=django.db.models.lookups.Exact(
                    django.db.models.functions.math.Mod("discount_amount", 10), 0
                ),
                name="promotions_couponredemption_discount_amount_whole_toman",
            ),
        ),
    ]
