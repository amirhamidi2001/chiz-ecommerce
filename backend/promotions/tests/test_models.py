from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from order.models import Order
from promotions.models import Coupon, CouponRedemption, FlashSale
from shop.models import Product

User = get_user_model()


def make_coupon(**overrides):
    now = timezone.now()
    defaults = {
        "code": "SUMMER20",
        "discount_type": Coupon.DiscountType.PERCENT,
        "value": Decimal("20.00"),
        "valid_from": now,
        "valid_until": now + timedelta(days=30),
    }
    defaults.update(overrides)
    return Coupon(**defaults)


class CouponCodeNormalizationTests(TestCase):
    def test_code_is_uppercased_and_stripped_on_save(self):
        for raw in ("summer20", "Summer20", "SUMMER20", "  summer20  "):
            with self.subTest(raw=raw):
                coupon = make_coupon(code=raw)
                coupon.save()
                coupon.refresh_from_db()
                self.assertEqual(coupon.code, "SUMMER20")
                coupon.delete()

    def test_case_variant_of_existing_code_fails_validation_not_integrity(self):
        make_coupon(code="SUMMER20").save()
        duplicate = make_coupon(code="summer20")
        with self.assertRaises(ValidationError) as ctx:
            duplicate.full_clean()
        self.assertIn("code", ctx.exception.message_dict)


class CouponCleanTests(TestCase):
    def test_rejects_valid_until_equal_to_valid_from(self):
        now = timezone.now()
        coupon = make_coupon(valid_from=now, valid_until=now)
        with self.assertRaises(ValidationError) as ctx:
            coupon.clean()
        self.assertIn("valid_until", ctx.exception.message_dict)

    def test_rejects_valid_until_before_valid_from(self):
        now = timezone.now()
        coupon = make_coupon(valid_from=now, valid_until=now - timedelta(days=1))
        with self.assertRaises(ValidationError) as ctx:
            coupon.clean()
        self.assertIn("valid_until", ctx.exception.message_dict)

    def test_rejects_percent_value_outside_zero_to_hundred(self):
        for bad in (Decimal("0"), Decimal("-5"), Decimal("100.01"), Decimal("150")):
            with self.subTest(value=bad):
                coupon = make_coupon(
                    discount_type=Coupon.DiscountType.PERCENT, value=bad
                )
                with self.assertRaises(ValidationError) as ctx:
                    coupon.clean()
                self.assertIn("value", ctx.exception.message_dict)

    def test_accepts_percent_value_at_upper_bound(self):
        coupon = make_coupon(
            discount_type=Coupon.DiscountType.PERCENT, value=Decimal("100")
        )
        coupon.clean()  # must not raise

    def test_rejects_fixed_value_zero_or_negative(self):
        for bad in (Decimal("0"), Decimal("-10")):
            with self.subTest(value=bad):
                coupon = make_coupon(discount_type=Coupon.DiscountType.FIXED, value=bad)
                with self.assertRaises(ValidationError) as ctx:
                    coupon.clean()
                self.assertIn("value", ctx.exception.message_dict)

    def test_full_clean_with_missing_dates_reports_field_errors_not_typeerror(self):
        coupon = Coupon(
            code="X",
            discount_type=Coupon.DiscountType.PERCENT,
            value=Decimal("10"),
        )
        with self.assertRaises(ValidationError) as ctx:
            coupon.full_clean()
        self.assertIn("valid_from", ctx.exception.message_dict)
        self.assertIn("valid_until", ctx.exception.message_dict)


class CouponSaveTests(TestCase):
    def test_valid_percent_coupon_saves(self):
        coupon = make_coupon(
            code="PCT10",
            discount_type=Coupon.DiscountType.PERCENT,
            value=Decimal("10"),
        )
        coupon.full_clean()
        coupon.save()
        self.assertIsNotNone(coupon.pk)
        self.assertEqual(str(coupon), "PCT10")

    def test_valid_fixed_coupon_saves(self):
        coupon = make_coupon(
            code="FIX50",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("50000.00"),
        )
        coupon.full_clean()
        coupon.save()
        self.assertIsNotNone(coupon.pk)
        self.assertEqual(coupon.uses_per_user, 1)
        self.assertIsNone(coupon.max_uses)
        self.assertEqual(coupon.min_order_amount, Decimal("0"))


def make_order(**overrides):
    data = dict(
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        phone="5550001234",
        shipping_address="1 Test St",
        shipping_city="Testville",
        shipping_state="CA",
        shipping_zip="90001",
        shipping_country="US",
        subtotal=Decimal("100.00"),
        shipping_cost=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=Decimal("80.00"),
    )
    data.update(overrides)
    return Order.objects.create(**data)


class CouponRedemptionTests(TestCase):
    def setUp(self):
        self.coupon = make_coupon(code="SUMMER20")
        self.coupon.save()
        self.user = User.objects.create_user(
            email="buyer@example.com", password="TestPass123!"
        )

    def test_can_create_without_order_then_attach_order_at_checkout(self):
        redemption = CouponRedemption.objects.create(
            coupon=self.coupon, user=self.user, discount_amount=Decimal("20.00")
        )
        redemption.refresh_from_db()
        self.assertIsNone(redemption.order)
        self.assertIsNotNone(redemption.redeemed_at)

        order = make_order(user=self.user)
        redemption.order = order
        redemption.save()

        redemption.refresh_from_db()
        self.assertEqual(redemption.order, order)
        self.assertEqual(order.coupon_redemption, redemption)
        self.assertEqual(list(self.coupon.redemptions.all()), [redemption])
        self.assertEqual(list(self.user.coupon_redemptions.all()), [redemption])

    def test_str_for_authenticated_user(self):
        redemption = CouponRedemption.objects.create(
            coupon=self.coupon, user=self.user, discount_amount=Decimal("20.00")
        )
        self.assertEqual(str(redemption), "SUMMER20 redeemed by buyer@example.com")

    def test_str_for_user_none(self):
        redemption = CouponRedemption.objects.create(
            coupon=self.coupon, user=None, discount_amount=Decimal("20.00")
        )
        self.assertEqual(str(redemption), "SUMMER20 redeemed by guest")

    def test_many_in_progress_redemptions_can_have_null_order(self):
        for _ in range(2):
            CouponRedemption.objects.create(
                coupon=self.coupon, user=self.user, discount_amount=Decimal("5.00")
            )
        self.assertEqual(self.coupon.redemptions.filter(order__isnull=True).count(), 2)

    def test_an_order_can_carry_only_one_redemption(self):
        order = make_order(user=self.user)
        CouponRedemption.objects.create(
            coupon=self.coupon,
            user=self.user,
            order=order,
            discount_amount=Decimal("20.00"),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CouponRedemption.objects.create(
                coupon=self.coupon,
                user=self.user,
                order=order,
                discount_amount=Decimal("20.00"),
            )

    def test_deleting_user_keeps_redemption_history(self):
        redemption = CouponRedemption.objects.create(
            coupon=self.coupon, user=self.user, discount_amount=Decimal("20.00")
        )
        self.user.delete()
        redemption.refresh_from_db()
        self.assertIsNone(redemption.user)


class CouponRestrictionFieldTests(TestCase):
    def test_new_coupon_has_no_restrictions_by_default(self):
        coupon = make_coupon(code="OPEN")
        coupon.save()
        self.assertFalse(coupon.categories.exists())
        self.assertFalse(coupon.products.exists())

    def test_coupon_can_be_restricted_to_categories_and_products(self):
        from shop.models import Category, Product

        category = Category.objects.create(name="Skincare")
        product = Product.objects.create(
            name="Serum", slug="serum", price=Decimal("20.00"), stock=5
        )
        coupon = make_coupon(code="SCOPED")
        coupon.save()
        coupon.categories.add(category)
        coupon.products.add(product)
        self.assertEqual(list(category.coupon_set.all()), [coupon])
        self.assertEqual(list(product.coupon_set.all()), [coupon])


def make_flash_sale(**overrides):
    now = timezone.now()
    defaults = {
        "name": "Weekend Flash Sale",
        "discount_percent": Decimal("25.00"),
        "starts_at": now - timedelta(hours=1),
        "ends_at": now + timedelta(hours=1),
        "is_active": True,
    }
    defaults.update(overrides)
    return FlashSale(**defaults)


class FlashSaleIsCurrentlyActiveTests(TestCase):
    def test_true_when_active_and_now_is_inside_the_window(self):
        self.assertTrue(make_flash_sale().is_currently_active)

    def test_false_when_not_yet_started(self):
        now = timezone.now()
        sale = make_flash_sale(
            starts_at=now + timedelta(hours=1), ends_at=now + timedelta(hours=2)
        )
        self.assertFalse(sale.is_currently_active)

    def test_false_when_already_ended(self):
        now = timezone.now()
        sale = make_flash_sale(
            starts_at=now - timedelta(hours=2), ends_at=now - timedelta(hours=1)
        )
        self.assertFalse(sale.is_currently_active)

    def test_false_when_manually_deactivated_even_inside_the_window(self):
        self.assertFalse(make_flash_sale(is_active=False).is_currently_active)

    def test_window_is_inclusive_at_both_ends_and_exclusive_just_outside(self):
        start = timezone.now().replace(microsecond=0)
        end = start + timedelta(hours=1)
        sale = make_flash_sale(starts_at=start, ends_at=end)
        cases = [
            (start - timedelta(microseconds=1), False),
            (start, True),
            (end, True),
            (end + timedelta(microseconds=1), False),
        ]
        for pinned_now, expected in cases:
            with self.subTest(now=pinned_now.isoformat()):
                with mock.patch(
                    "promotions.models.timezone.now", return_value=pinned_now
                ):
                    self.assertIs(sale.is_currently_active, expected)

    def test_deactivated_sale_stays_false_at_every_point_in_the_window(self):
        start = timezone.now().replace(microsecond=0)
        sale = make_flash_sale(
            starts_at=start, ends_at=start + timedelta(hours=1), is_active=False
        )
        for pinned_now in (
            start,
            start + timedelta(minutes=30),
            start + timedelta(hours=1),
        ):
            with mock.patch("promotions.models.timezone.now", return_value=pinned_now):
                self.assertFalse(sale.is_currently_active)


class FlashSaleCleanTests(TestCase):
    def test_rejects_ends_at_equal_to_starts_at(self):
        now = timezone.now()
        sale = make_flash_sale(starts_at=now, ends_at=now)
        with self.assertRaises(ValidationError) as ctx:
            sale.clean()
        self.assertIn("ends_at", ctx.exception.message_dict)

    def test_rejects_ends_at_before_starts_at(self):
        now = timezone.now()
        sale = make_flash_sale(starts_at=now, ends_at=now - timedelta(days=1))
        with self.assertRaises(ValidationError) as ctx:
            sale.clean()
        self.assertIn("ends_at", ctx.exception.message_dict)
        self.assertEqual(
            ctx.exception.message_dict["ends_at"], ["Must be after starts_at."]
        )

    def test_accepts_ends_at_after_starts_at(self):
        make_flash_sale().clean()  # must not raise

    def test_full_clean_with_missing_dates_reports_field_errors_not_typeerror(self):
        sale = FlashSale(name="X", discount_percent=Decimal("10"))
        with self.assertRaises(ValidationError) as ctx:
            sale.full_clean()
        self.assertIn("starts_at", ctx.exception.message_dict)
        self.assertIn("ends_at", ctx.exception.message_dict)


class FlashSaleFieldTests(TestCase):
    def test_discount_percent_validators_enforce_0_01_to_100(self):
        for bad in ("0", "-5", "100.01", "150"):
            with self.subTest(value=bad):
                sale = make_flash_sale(discount_percent=Decimal(bad))
                with self.assertRaises(ValidationError) as ctx:
                    sale.full_clean(exclude=["products"])
                self.assertIn("discount_percent", ctx.exception.message_dict)
        for good in ("0.01", "50", "100"):
            with self.subTest(value=good):
                make_flash_sale(discount_percent=Decimal(good)).full_clean(
                    exclude=["products"]
                )

    def test_products_relation_and_reverse_accessor(self):
        product = Product.objects.create(
            name="Serum", slug="flash-serum", price=Decimal("20.00"), stock=5
        )
        sale = make_flash_sale()
        sale.save()
        sale.products.add(product)
        self.assertEqual(list(sale.products.all()), [product])
        self.assertEqual(list(product.flash_sales.all()), [sale])

    def test_str_is_the_name(self):
        self.assertEqual(str(make_flash_sale(name="Black Friday")), "Black Friday")

    def test_default_ordering_is_newest_start_first(self):
        now = timezone.now()
        older = make_flash_sale(
            name="Older", starts_at=now - timedelta(days=5), ends_at=now
        )
        newer = make_flash_sale(
            name="Newer", starts_at=now - timedelta(days=1), ends_at=now
        )
        older.save()
        newer.save()
        self.assertEqual([s.name for s in FlashSale.objects.all()], ["Newer", "Older"])
