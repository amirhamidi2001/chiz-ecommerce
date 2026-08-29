# Step 3 (final) of the CartItem.product -> CartItem.variant rollout
# (see 0002/0003). By this point every existing CartItem row has had
# `variant` populated by 0003's data migration, so it's now safe to:
#   1. Swap the unique_together constraint from (cart, product) to
#      (cart, variant) — must happen before dropping `product`, since
#      the old constraint still references it.
#   2. Enforce NOT NULL on `variant`.
#   3. Drop the now-redundant `product` FK entirely.
#
# Reversibility note: `product` was originally a NOT NULL FK (see
# 0001_initial). A naive `RemoveField('product')` is forward-safe but
# NOT cleanly reversible on a table with existing rows — Django's
# auto-generated reverse of RemoveField just re-adds the column with
# no way to populate it, and a bare NOT NULL FK with no data violates
# the constraint immediately. Since we *can* recover the right value
# (`variant.product_id`), we make `product` nullable first and
# populate/depopulate it via RunPython around the RemoveField, so that
# reversing this migration all the way down actually restores working
# `product_id` values instead of just failing or leaving nulls.
from django.db import migrations, models
import django.db.models.deletion


def repopulate_product_from_variant(apps, schema_editor):
    """
    Reverse-only step: after `product` has been re-added (nullable) by
    reversing the RemoveField below, backfill it from each row's
    `variant.product_id` before the following reverse operation
    re-enforces NOT NULL on `product`.
    """
    CartItem = apps.get_model("cart", "CartItem")
    for item in CartItem.objects.select_related("variant").filter(product__isnull=True):
        item.product_id = item.variant.product_id
        item.save(update_fields=["product"])


def clear_product_field(apps, schema_editor):
    """
    Forward-only step: `product` is being retired in favor of
    `variant`; null it out (it's already nullable at this point in the
    migration, see the preceding AlterField) so the column is empty
    before it's dropped by the following RemoveField.
    """
    CartItem = apps.get_model("cart", "CartItem")
    CartItem.objects.update(product=None)


class Migration(migrations.Migration):

    dependencies = [
        ("cart", "0003_migrate_cartitem_product_to_variant"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="cartitem",
            unique_together={("cart", "variant")},
        ),
        migrations.AlterField(
            model_name="cartitem",
            name="variant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cart_items",
                to="shop.productvariant",
            ),
        ),
        # Make `product` nullable before touching its data/dropping it,
        # so the reverse path (re-add -> repopulate -> re-enforce
        # NOT NULL) has a valid intermediate state to run RunPython
        # against.
        migrations.AlterField(
            model_name="cartitem",
            name="product",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cart_items",
                to="shop.product",
            ),
        ),
        migrations.RunPython(
            clear_product_field,
            repopulate_product_from_variant,
        ),
        migrations.RemoveField(
            model_name="cartitem",
            name="product",
        ),
    ]
