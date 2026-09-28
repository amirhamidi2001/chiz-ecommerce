from django.db import migrations

# Carriers are seeded inactive-by-default: a carrier shouldn't become
# live/selectable at checkout until its actual integration task (Phase
# 7.2) is done and an admin deliberately flips is_active on. Seeding
# active-by-default rows with no working integration behind them yet
# would be unsafe.
CARRIERS = [
    ("post", "Iran Post"),
    ("tipax", "Tipax"),
    ("snapbox", "SnapBox"),
    ("alopeyk", "AloPeyk"),
]


def seed_shipping_carriers(apps, schema_editor):
    ShippingCarrier = apps.get_model("shipping", "ShippingCarrier")
    for code, display_name in CARRIERS:
        ShippingCarrier.objects.get_or_create(
            code=code,
            defaults={"display_name": display_name, "is_active": False},
        )


def unseed_shipping_carriers(apps, schema_editor):
    ShippingCarrier = apps.get_model("shipping", "ShippingCarrier")
    ShippingCarrier.objects.filter(code__in=[code for code, _ in CARRIERS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("shipping", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_shipping_carriers, unseed_shipping_carriers),
    ]
