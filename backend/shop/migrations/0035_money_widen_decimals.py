# Step 1/3 of the Task 14.1.2.2 money migration for `shop` (ADR 0001).
#
# Widen the legacy DecimalFields so the x10,000 re-baseline in the NEXT
# migration cannot overflow their old max_digits (e.g. Decimal(10,2) tops out
# at 99,999,999.99, below 10,000 x $9,999,999.99). Schema-only on purpose:
# Postgres will not ALTER a table that has pending trigger events from an
# UPDATE in the same transaction, which is why the data step is its own
# migration (the same two-step pattern as Epic 5 Task 5.2.1.4).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0034_searchquerylog"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="price",
            field=models.DecimalField(decimal_places=2, max_digits=24),
        ),
        migrations.AlterField(
            model_name="product",
            name="original_price",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=24, null=True
            ),
        ),
        migrations.AlterField(
            model_name="productvariant",
            name="price",
            field=models.DecimalField(decimal_places=2, max_digits=24),
        ),
        migrations.AlterField(
            model_name="productvariant",
            name="original_price",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=24, null=True
            ),
        ),
        migrations.AlterField(
            model_name="productpricesnapshot",
            name="price",
            field=models.DecimalField(decimal_places=2, max_digits=24),
        ),
    ]
