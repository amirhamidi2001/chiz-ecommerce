from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from promotions.models import FlashSale
from promotions.serializers import PRODUCT_PREVIEW_LIMIT
from shop.models import Product

URL = "/api/promotions/active-flash-sales/"


def make_sale(
    *, name="Sale", percent="25.00", start_h=-1, end_h=1, active=True, products=0
):
    now = timezone.now()
    sale = FlashSale.objects.create(
        name=name,
        discount_percent=Decimal(percent),
        starts_at=now + timedelta(hours=start_h),
        ends_at=now + timedelta(hours=end_h),
        is_active=active,
    )
    if products:
        sale.products.add(*make_products(products))
    return sale


_n = [0]


def make_products(count):
    out = []
    for _ in range(count):
        _n[0] += 1
        out.append(
            Product.objects.create(
                name=f"Flash Product {_n[0]}",
                slug=f"flash-product-{_n[0]}",
                price=Decimal("20.00"),
                stock=5,
            )
        )
    return out


class ActiveFlashSalesEndpointTests(TestCase):
    def test_url_is_routed_by_name(self):
        self.assertEqual(reverse("promotions:active-flash-sales"), URL)

    def test_is_public(self):
        res = self.client.get(URL)  # no authentication
        self.assertEqual(res.status_code, 200)

    def test_no_active_sale_is_an_empty_list_not_an_error(self):
        res = self.client.get(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_returns_a_running_sale_with_its_banner_data(self):
        sale = make_sale(name="Weekend Flash", percent="30.00", products=3)

        data = self.client.get(URL).json()

        self.assertEqual(len(data), 1)
        item = data[0]
        self.assertEqual(item["id"], sale.id)
        self.assertEqual(item["name"], "Weekend Flash")
        self.assertEqual(Decimal(str(item["discount_percent"])), Decimal("30.00"))
        self.assertIn("starts_at", item)
        self.assertTrue(item["ends_at"].endswith("Z") or "+" in item["ends_at"])
        self.assertEqual(item["product_count"], 3)
        self.assertEqual(len(item["products"]), 3)
        self.assertEqual(
            set(item["products"][0]), {"id", "name", "slug", "price", "thumbnail_url"}
        )

    def test_excludes_upcoming_ended_and_deactivated_sales(self):
        make_sale(name="upcoming", start_h=1, end_h=2)
        make_sale(name="ended", start_h=-2, end_h=-1)
        make_sale(name="deactivated", active=False)
        running = make_sale(name="running")

        names = [s["name"] for s in self.client.get(URL).json()]

        self.assertEqual(names, [running.name])

    def test_orders_soonest_ending_first(self):
        make_sale(name="later", end_h=10)
        make_sale(name="soonest", end_h=1)
        make_sale(name="middle", end_h=5)

        names = [s["name"] for s in self.client.get(URL).json()]

        self.assertEqual(names, ["soonest", "middle", "later"])

    def test_product_preview_is_capped_but_the_count_is_the_real_total(self):
        make_sale(products=PRODUCT_PREVIEW_LIMIT + 4)

        item = self.client.get(URL).json()[0]

        self.assertEqual(item["product_count"], PRODUCT_PREVIEW_LIMIT + 4)
        self.assertEqual(len(item["products"]), PRODUCT_PREVIEW_LIMIT)

    def test_a_sale_with_no_products_still_lists_with_a_zero_count(self):
        make_sale(products=0)
        item = self.client.get(URL).json()[0]
        self.assertEqual(item["product_count"], 0)
        self.assertEqual(item["products"], [])

    def test_a_product_in_several_sales_is_counted_in_each_correctly(self):
        shared = make_products(1)[0]
        first = make_sale(name="a", end_h=1)
        second = make_sale(name="b", end_h=2)
        first.products.add(shared)
        second.products.add(shared)
        by_name = {s["name"]: s for s in self.client.get(URL).json()}
        self.assertEqual(by_name["a"]["product_count"], 1)
        self.assertEqual(by_name["b"]["product_count"], 1)

    def test_query_count_is_bounded_per_sale_not_per_product(self):
        make_sale(name="one", end_h=1, products=2)

        def count():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get(URL).status_code, 200)
            return len(ctx)

        baseline = count()
        # Same number of sales, many more products: no extra queries.
        FlashSale.objects.get(name="one").products.add(*make_products(20))
        self.assertEqual(count(), baseline)

    def test_only_get_is_allowed(self):
        self.assertEqual(self.client.post(URL, {}).status_code, 405)
