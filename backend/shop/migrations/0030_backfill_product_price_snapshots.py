from django.db import migrations
from django.db.models import Min


def backfill_price_snapshots(apps, schema_editor):
    """
    Give every existing product a baseline ProductPriceSnapshot (its current
    lowest ACTIVE variant price — the same definition as
    Product.lowest_active_price).

    Without this, an existing product has no baseline until its first
    variant change, and handle_variant_price_change would spend that
    first change just recording one — silently swallowing a real price
    drop on every product that predates this feature.

    Products with no active variant get no snapshot (no price to record).
    """
    ProductVariant = apps.get_model("shop", "ProductVariant")
    ProductPriceSnapshot = apps.get_model("shop", "ProductPriceSnapshot")

    rows = (
        ProductVariant.objects.filter(is_active=True)
        .values("product_id")
        .annotate(lowest=Min("price"))
    )
    ProductPriceSnapshot.objects.bulk_create(
        [
            ProductPriceSnapshot(product_id=r["product_id"], price=r["lowest"])
            for r in rows
        ],
        batch_size=1000,
    )


def remove_backfilled_snapshots(apps, schema_editor):
    # The table itself is dropped by 0029's reverse; nothing to do here.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0029_productpricesnapshot"),
    ]

    operations = [
        migrations.RunPython(backfill_price_snapshots, remove_backfilled_snapshots),
    ]
