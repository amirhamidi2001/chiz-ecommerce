# Step 1/3 of the Task 14.1.2.2 money migration for `promotions` (ADR 0001).
#
# Widen the legacy DecimalFields so the x10,000 re-baseline in the NEXT
# migration cannot overflow their old max_digits (e.g. Decimal(10,2) tops out
# at 99,999,999.99, below 10,000 x $9,999,999.99). Schema-only on purpose:
# Postgres will not ALTER a table that has pending trigger events from an
# UPDATE in the same transaction, which is why the data step is its own
# migration (the same two-step pattern as Epic 5 Task 5.2.1.4).

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0004_flashsale"),
    ]

    operations = [
        migrations.AlterField(
            model_name="coupon",
            name="value",
            field=models.DecimalField(decimal_places=2, max_digits=24),
        ),
        migrations.AlterField(
            model_name="coupon",
            name="min_order_amount",
            field=models.DecimalField(
                default=Decimal("0"), decimal_places=2, max_digits=24
            ),
        ),
        migrations.AlterField(
            model_name="couponredemption",
            name="discount_amount",
            field=models.DecimalField(decimal_places=2, max_digits=24),
        ),
    ]
