from django.core.management.base import BaseCommand
from shop.models import Product
from shop.search import refresh_product_search_vectors


class Command(BaseCommand):
    help = (
        "Recompute Product.search_vector for every product. Needed only after "
        "something bypassed Product.save() (queryset.update() on name/"
        "description/brand/category, bulk_create, raw SQL, a restored dump)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Products per UPDATE statement (keeps lock time short on big catalogs).",
        )

    def handle(self, *args, batch_size, **options):
        pks = list(Product.objects.order_by("pk").values_list("pk", flat=True))
        for start in range(0, len(pks), batch_size):
            refresh_product_search_vectors(
                Product.objects.filter(pk__in=pks[start : start + batch_size])
            )
        self.stdout.write(
            self.style.SUCCESS(f"Rebuilt search_vector for {len(pks)} products.")
        )
