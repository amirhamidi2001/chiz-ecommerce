import re

from django.contrib.postgres.search import SearchVector
from django.db import migrations
from django.db.models import OuterRef, Subquery

# FROZEN copy of shop.text_utils (a migration must keep doing what it did
# when it was written, even if text_utils changes later).
_MAP = str.maketrans(
    {
        "\u0643": "\u06a9",  # ARABIC KAF -> KEHEH
        "\u064a": "\u06cc",  # ARABIC YEH -> FARSI YEH
        "\u0649": "\u06cc",  # ALEF MAKSURA -> FARSI YEH
        "\u06c0": "\u0647",  # HEH WITH YEH ABOVE -> HEH
    }
)
_ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\ufeff]")

BATCH = 1000


def _normalize(text):
    if not text:
        return text
    return _ZERO_WIDTH.sub("", text.translate(_MAP))


def _normalize_model(Model, fields):
    """Rewrite only rows whose text actually changes; returns how many."""
    changed = 0
    batch = []
    for obj in Model.objects.only("pk", *fields).iterator(chunk_size=2000):
        dirty = False
        for field in fields:
            old = getattr(obj, field)
            new = _normalize(old)
            if new != old:
                setattr(obj, field, new)
                dirty = True
        if dirty:
            batch.append(obj)
            changed += 1
        if len(batch) >= BATCH:
            Model.objects.bulk_update(batch, fields)
            batch = []
    if batch:
        Model.objects.bulk_update(batch, fields)
    return changed


def normalize_catalog_text(apps, schema_editor):
    """
    Canonicalise EXISTING catalog text, as Product/Brand/Category.save() now
    does for future writes, then rebuild every search_vector.

    Historical models don't run the live save() override, so instead of
    calling instance.save() per row (slow, and it wouldn't normalise here
    anyway) this normalises in Python, writes only rows that changed, and
    rebuilds all vectors with ONE UPDATE statement at the end. Slugs are
    deliberately left alone (they're public URLs). Signals (cache
    invalidation, price snapshots) do not fire; the product-list cache has a
    short TTL.

    IRREVERSIBLE: the original characters (including ZWNJ) are not kept.
    """
    Product = apps.get_model("shop", "Product")
    Brand = apps.get_model("shop", "Brand")
    Category = apps.get_model("shop", "Category")

    _normalize_model(Brand, ["name"])
    _normalize_model(Category, ["name"])
    _normalize_model(Product, ["name", "short_description", "description"])

    # Rebuild vectors (frozen copy of the 0032 expression).
    brand_name = Subquery(
        Brand.objects.filter(pk=OuterRef("brand_id")).values("name")[:1]
    )
    category_name = Subquery(
        Category.objects.filter(pk=OuterRef("category_id")).values("name")[:1]
    )
    Product.objects.update(
        search_vector=(
            SearchVector("name", weight="A", config="simple")
            + SearchVector(brand_name, weight="A", config="simple")
            + SearchVector(category_name, weight="B", config="simple")
            + SearchVector("short_description", weight="B", config="simple")
            + SearchVector("description", weight="C", config="simple")
        )
    )


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0032_backfill_product_search_vectors"),
    ]

    operations = [
        migrations.RunPython(normalize_catalog_text, migrations.RunPython.noop),
    ]
