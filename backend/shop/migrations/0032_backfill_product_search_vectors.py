from django.contrib.postgres.search import SearchVector
from django.db import migrations
from django.db.models import OuterRef, Subquery


def backfill_search_vectors(apps, schema_editor):
    """
    Populate search_vector for every EXISTING product (Product.save() only
    maintains it for future saves, so pre-existing rows are NULL — and a
    NULL vector matches no search at all).

    This is a FROZEN copy of shop.search.product_search_vector_expression
    on purpose (see that module's note). Works on historical models because
    brand/category names come from correlated Subqueries, not from
    SearchVector("brand__name"): QuerySet.update() forbids joined-field
    references, and that restriction has nothing to do with historical
    models. One UPDATE statement; fine for catalogs of up to many tens of
    thousands of products.
    """
    Product = apps.get_model("shop", "Product")
    Brand = apps.get_model("shop", "Brand")
    Category = apps.get_model("shop", "Category")

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
        ("shop", "0031_product_search_vector"),
    ]

    operations = [
        # Reverse is a no-op: 0031's reverse drops the column itself.
        migrations.RunPython(backfill_search_vectors, migrations.RunPython.noop),
    ]
