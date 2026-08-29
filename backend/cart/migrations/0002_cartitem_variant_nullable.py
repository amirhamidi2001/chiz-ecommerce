# Hand-written migration (see 0003/0004 for the rest of this rollout).
#
# Step 1 of a 3-part, non-destructive rollout from CartItem.product to
# CartItem.variant:
#   0002 (this file): add the new `variant` FK as NULLABLE, alongside the
#        still-present `product` FK. Pure additive schema change — no
#        existing data is touched or at risk.
#   0003: data migration — populate `variant` on every existing CartItem
#        from its `product`'s variants (Tasks 3.1.1.1/3.1.1.2 guarantee
#        every Product has at least one ProductVariant by this point).
#   0004: now that every row has a variant, make `variant` non-nullable,
#        drop the old `product` FK, and swap the unique_together
#        constraint from (cart, product) to (cart, variant).
#
# Splitting it this way means at every intermediate step the table is in
# a valid, queryable state, and the destructive parts (NOT NULL
# enforcement, dropping `product`) only happen once we've positively
# confirmed (via 0003) that every row already has a variant.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cart", "0001_initial"),
        ("shop", "0006_migrate_products_to_variants"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartitem",
            name="variant",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cart_items",
                to="shop.productvariant",
            ),
        ),
    ]
