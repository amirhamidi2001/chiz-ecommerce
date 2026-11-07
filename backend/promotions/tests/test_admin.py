from django.contrib import admin
from django.test import SimpleTestCase
from promotions.models import Coupon, FlashSale


class CouponAdminTests(SimpleTestCase):
    def test_restrictions_use_the_horizontal_multiselect_widget(self):
        coupon_admin = admin.site._registry[Coupon]
        self.assertEqual(coupon_admin.filter_horizontal, ("categories", "products"))


class FlashSaleAdminTests(SimpleTestCase):
    def test_is_registered_with_the_specified_options(self):
        sale_admin = admin.site._registry[FlashSale]
        # Each Gregorian window column is followed by its Jalali (Solar Hijri) twin
        # (Task 14.2.1.2) — display only; the stored fields are unchanged.
        self.assertEqual(
            sale_admin.list_display,
            (
                "name",
                "discount_percent",
                "starts_at",
                "starts_at_jalali",
                "ends_at",
                "ends_at_jalali",
                "is_active",
            ),
        )
        self.assertEqual(sale_admin.list_filter, ("is_active",))
        self.assertEqual(sale_admin.filter_horizontal, ("products",))
