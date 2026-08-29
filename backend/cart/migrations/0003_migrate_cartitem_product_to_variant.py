# Step 2 of the CartItem.product -> CartItem.variant rollout (see 0002).
#
# For every existing CartItem, point its new `variant` FK at the
# product's "default" variant — the lowest-id ProductVariant for that
# product (ProductVariant.Meta.ordering = ["id"], so `.first()` is
# deterministic). We have no historical data telling us which specific
# shade/size a pre-variant cart line was "really" for, so the
# lowest-id variant is the least-surprising, deterministic choice
# (it's also what Task 3.1.1.2's own legacy-SKU numbering treats as
# variant index 0 for that product). This is a one-time best-effort
# default; customers with the wrong variant can simply remove/re-add
# after this rollout ships.
#
# By this point in the rollout (Tasks 3.1.1.1 + 3.1.1.2 merged), every
# Product is guaranteed to have at least one ProductVariant, so
# `.first()` should never be None in practice — but we skip
# defensively rather than crash the migration if it somehow is,
# leaving that row's `variant` null for manual follow-up.

from django.db import migrations


def migrate_product_to_variant(apps, schema_editor):
    CartItem = apps.get_model("cart", "CartItem")
    ProductVariant = apps.get_model("shop", "ProductVariant")

    for item in CartItem.objects.filter(variant__isnull=True).select_related("product"):
        default_variant = (
            ProductVariant.objects.filter(product_id=item.product_id)
            .order_by("id")
            .first()
        )
        if default_variant is None:
            # Defensive only — should not happen once 3.1.1.1/3.1.1.2 are
            # merged, since every Product has at least one variant.
            continue
        item.variant_id = default_variant.id
        item.save(update_fields=["variant"])


def reverse_migrate_product_to_variant(apps, schema_editor):
    """
    Null out `variant` on every CartItem. Safe to do unconditionally:
    at this point in the migration history `product` is still present
    on every row, so nothing is lost — re-running 0003 forward would
    simply repopulate `variant` from `product` again.
    """
    CartItem = apps.get_model("cart", "CartItem")
    CartItem.objects.update(variant=None)


class Migration(migrations.Migration):

    dependencies = [
        ("cart", "0002_cartitem_variant_nullable"),
    ]

    operations = [
        migrations.RunPython(
            migrate_product_to_variant,
            reverse_migrate_product_to_variant,
        ),
    ]
