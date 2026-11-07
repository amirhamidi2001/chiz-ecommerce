"""
core/tests/test_jalali_admin.py
───────────────────────────────
Task 14.2.1.2 — Jalali (Solar Hijri) DISPLAY in the Django admin.

Two layers:
  * unit tests (no database) call each targeted admin class's real display
    method on an unsaved object and compare against reference Jalali strings;
  * integration tests drive Django's actual admin pages (changelist and change
    form) and check the columns, the rendered values, their placement, sorting
    and the Persian/English labels.

The reference timestamps are NOT produced by the code under test. Staff read
Tehran time (UTC+3:30, no DST), so a stored UTC instant has to be converted to
local time BEFORE it becomes a Jalali date:

  2026-03-20 20:30 UTC = 2026-03-21 00:00 Tehran = 1 Farvardin 1405  (Nowruz 1405;
                         the UTC day would wrongly give 29 Esfand 1404)
  2025-03-20 20:30 UTC = 2025-03-21 00:00 Tehran = 1 Farvardin 1404  (Nowruz 1404)
  2024-03-19 20:30 UTC = 2024-03-20 00:00 Tehran = 1 Farvardin 1403  (Nowruz 1403)
  2025-03-20 00:00 UTC = 2025-03-20 03:30 Tehran = 30 Esfand 1403    (leap-year extra day)
  2026-03-20 05:05 UTC = 2026-03-20 08:35 Tehran = 29 Esfand 1404    (last day of a common year)
"""

import datetime
from decimal import Decimal
from types import SimpleNamespace

from accounts.models import User
from core.jalali import to_jalali_string
from django.contrib.admin import AdminSite
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from order.admin import OrderAdmin
from order.models import Order
from order.tests.factories import make_shipping_carrier, make_user
from payments.admin import PaymentTransactionAdmin
from payments.models import PaymentTransaction
from promotions.admin import CouponAdmin, FlashSaleAdmin
from promotions.models import Coupon, FlashSale
from promotions.tests.factories import make_order
from shipping.admin import ShipmentAdmin
from shipping.models import Shipment

UTC = datetime.timezone.utc

# (stored UTC instant, expected Jalali string as shown to Tehran staff, why)
REFERENCE_INSTANTS = [
    (
        datetime.datetime(2026, 3, 20, 20, 30, tzinfo=UTC),
        "1405/01/01 00:00",
        "Nowruz 1405 at Tehran midnight",
    ),
    (
        datetime.datetime(2025, 3, 20, 20, 30, tzinfo=UTC),
        "1404/01/01 00:00",
        "Nowruz 1404 at Tehran midnight",
    ),
    (
        datetime.datetime(2024, 3, 19, 20, 30, tzinfo=UTC),
        "1403/01/01 00:00",
        "Nowruz 1403 at Tehran midnight",
    ),
    (
        datetime.datetime(2025, 3, 20, 0, 0, tzinfo=UTC),
        "1403/12/30 03:30",
        "30 Esfand 1403 (leap day)",
    ),
    (
        datetime.datetime(2026, 3, 20, 5, 5, tzinfo=UTC),
        "1404/12/29 08:35",
        "29 Esfand 1404 (common-year last day)",
    ),
]

# (admin class, model, display method name, underlying Gregorian field, Persian label)
ADMIN_COLUMNS = [
    (OrderAdmin, Order, "created_at_jalali", "created_at", "تاریخ ایجاد (شمسی)"),
    (OrderAdmin, Order, "updated_at_jalali", "updated_at", "تاریخ به‌روزرسانی (شمسی)"),
    (
        ShipmentAdmin,
        Shipment,
        "last_tracked_at_jalali",
        "last_tracked_at",
        "آخرین پیگیری (شمسی)",
    ),
    (
        PaymentTransactionAdmin,
        PaymentTransaction,
        "created_at_jalali",
        "created_at",
        "تاریخ ایجاد (شمسی)",
    ),
    (CouponAdmin, Coupon, "valid_from_jalali", "valid_from", "اعتبار از (شمسی)"),
    (CouponAdmin, Coupon, "valid_until_jalali", "valid_until", "اعتبار تا (شمسی)"),
    (FlashSaleAdmin, FlashSale, "starts_at_jalali", "starts_at", "شروع (شمسی)"),
    (FlashSaleAdmin, FlashSale, "ends_at_jalali", "ends_at", "پایان (شمسی)"),
]


@override_settings(USE_TZ=True, TIME_ZONE="Asia/Tehran")
class ToJalaliStringTests(SimpleTestCase):
    def test_converts_to_tehran_time_before_converting_to_jalali(self):
        for instant, expected, why in REFERENCE_INSTANTS:
            with self.subTest(why):
                self.assertEqual(to_jalali_string(instant), expected)

    def test_none_stays_none(self):
        self.assertIsNone(to_jalali_string(None))

    def test_naive_datetime_is_taken_as_already_local(self):
        self.assertEqual(
            to_jalali_string(datetime.datetime(2026, 3, 21, 0, 0)), "1405/01/01 00:00"
        )

    def test_plain_date_has_no_time_part(self):
        self.assertEqual(to_jalali_string(datetime.date(2025, 3, 21)), "1404/01/01")
        self.assertEqual(
            to_jalali_string(datetime.date(1979, 2, 11)), "1357/11/22"
        )  # 22 Bahman

    def test_custom_format(self):
        instant = REFERENCE_INSTANTS[0][0]
        self.assertEqual(to_jalali_string(instant, "%Y-%m-%d"), "1405-01-01")

    def test_rejects_things_that_are_not_dates(self):
        with self.assertRaises(TypeError):
            to_jalali_string("2026-03-21")

    def test_the_naive_shortcut_would_be_wrong_by_a_day(self):
        """Documents why the helper exists (the pitfall from Task 14.2.1.1)."""
        import jdatetime

        instant = REFERENCE_INSTANTS[0][0]
        naive = jdatetime.datetime.fromgregorian(datetime=instant).strftime(
            "%Y/%m/%d %H:%M"
        )
        self.assertEqual(naive, "1404/12/29 20:30")  # the UTC day — not what staff see
        self.assertNotEqual(naive, to_jalali_string(instant))


@override_settings(USE_TZ=True, TIME_ZONE="Asia/Tehran")
class AdminDisplayMethodTests(SimpleTestCase):
    """Each targeted admin's display method, on an unsaved object (no database)."""

    def _admin(self, admin_cls, model):
        return admin_cls(model, AdminSite())

    def test_every_targeted_column_converts_every_reference_instant(self):
        for admin_cls, model, method, field, _label in ADMIN_COLUMNS:
            model_admin = self._admin(admin_cls, model)
            for instant, expected, why in REFERENCE_INSTANTS:
                with self.subTest(f"{admin_cls.__name__}.{method} — {why}"):
                    obj = model(**{field: instant})
                    self.assertEqual(getattr(model_admin, method)(obj), expected)

    def test_a_missing_timestamp_shows_the_admins_empty_value(self):
        """Shipment.last_tracked_at is null until the carrier is first polled."""
        model_admin = self._admin(ShipmentAdmin, Shipment)
        self.assertEqual(
            model_admin.last_tracked_at_jalali(Shipment(last_tracked_at=None)), "-"
        )

    def test_columns_sort_by_the_underlying_gregorian_field(self):
        for admin_cls, model, method, field, _label in ADMIN_COLUMNS:
            with self.subTest(f"{admin_cls.__name__}.{method}"):
                fn = getattr(self._admin(admin_cls, model), method)
                self.assertEqual(fn.admin_order_field, field)

    def test_labels_are_translated(self):
        for admin_cls, model, method, _field, persian in ADMIN_COLUMNS:
            fn = getattr(self._admin(admin_cls, model), method)
            with self.subTest(f"{admin_cls.__name__}.{method}"):
                with translation.override("fa"):
                    self.assertEqual(str(fn.short_description), persian)
                with translation.override("en"):
                    self.assertIn("(Jalali)", str(fn.short_description))

    def test_the_created_label_is_the_one_from_the_task_brief(self):
        fn = OrderAdmin(Order, AdminSite()).created_at_jalali
        with translation.override("fa"):
            self.assertEqual(str(fn.short_description), "تاریخ ایجاد (شمسی)")

    def test_storage_fields_are_still_plain_gregorian_datetime_fields(self):
        from django.db import models

        for _admin, model, _method, field, _label in ADMIN_COLUMNS:
            with self.subTest(f"{model.__name__}.{field}"):
                self.assertIs(type(model._meta.get_field(field)), models.DateTimeField)

    def test_wiring_list_display_and_detail_fields(self):
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(
            is_active=True, is_superuser=True, is_staff=True, has_perm=lambda *a: True
        )
        cases = [
            (OrderAdmin, Order, "created_at", "created_at_jalali"),
            (ShipmentAdmin, Shipment, "last_tracked_at", "last_tracked_at_jalali"),
            (
                PaymentTransactionAdmin,
                PaymentTransaction,
                "created_at",
                "created_at_jalali",
            ),
            (CouponAdmin, Coupon, "valid_from", "valid_from_jalali"),
            (CouponAdmin, Coupon, "valid_until", "valid_until_jalali"),
            (FlashSaleAdmin, FlashSale, "starts_at", "starts_at_jalali"),
            (FlashSaleAdmin, FlashSale, "ends_at", "ends_at_jalali"),
        ]
        for admin_cls, model, source, companion in cases:
            model_admin = admin_cls(model, AdminSite())
            with self.subTest(f"{admin_cls.__name__}: {companion}"):
                shown = list(model_admin.get_list_display(request))
                self.assertEqual(
                    shown[shown.index(source) + 1], companion
                )  # right beside its twin
                self.assertIn(companion, model_admin.get_readonly_fields(request))
                detail = [
                    f
                    for _title, opts in model_admin.get_fieldsets(request)
                    for f in opts["fields"]
                ]
                flat = [
                    x
                    for f in detail
                    for x in (f if isinstance(f, (list, tuple)) else [f])
                ]
                self.assertIn(companion, flat)
                self.assertEqual(
                    flat[flat.index(source) + 1], companion
                )  # ...and on the detail page


@override_settings(USE_TZ=True, TIME_ZONE="Asia/Tehran")
class AdminPagesIntegrationTests(TestCase):
    """The real admin screens, through the test client."""

    NOWRUZ_1405, NOWRUZ_1404, NOWRUZ_1403 = (r[0] for r in REFERENCE_INSTANTS[:3])

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(
            email="root@example.com", password="Admin12345!"
        )
        buyer = make_user("buyer@example.com")
        cls.order = make_order(user=buyer)
        Order.objects.filter(pk=cls.order.pk).update(
            created_at=cls.NOWRUZ_1405, updated_at=cls.NOWRUZ_1404
        )
        cls.txn = PaymentTransaction.objects.create(
            order=cls.order, gateway="zarinpal", amount=800_000
        )
        PaymentTransaction.objects.filter(pk=cls.txn.pk).update(
            created_at=cls.NOWRUZ_1404
        )
        carrier = make_shipping_carrier()
        cls.tracked = Shipment.objects.create(
            order=cls.order, carrier=carrier, last_tracked_at=cls.NOWRUZ_1403
        )
        cls.untracked = Shipment.objects.create(
            order=make_order(user=buyer), carrier=carrier
        )
        cls.coupon = Coupon.objects.create(
            code="NOWRUZ1405",
            discount_type="percent",
            percent_off=Decimal("15.00"),
            valid_from=cls.NOWRUZ_1405,
            valid_until=cls.NOWRUZ_1404,
        )
        cls.early = FlashSale.objects.create(
            name="Early",
            discount_percent=Decimal("10.00"),
            starts_at=cls.NOWRUZ_1403,
            ends_at=cls.NOWRUZ_1404,
        )
        cls.late = FlashSale.objects.create(
            name="Late",
            discount_percent=Decimal("20.00"),
            starts_at=cls.NOWRUZ_1405,
            ends_at=cls.NOWRUZ_1405,
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def _changelist(self, name, **extra):
        res = self.client.get(reverse(f"admin:{name}_changelist"), **extra)
        self.assertEqual(res.status_code, 200)
        return res.content.decode()

    def _change(self, name, pk, **extra):
        res = self.client.get(reverse(f"admin:{name}_change", args=[pk]), **extra)
        self.assertEqual(res.status_code, 200)
        return res.content.decode()

    # ── list views ───────────────────────────────────────────────────────────
    def test_order_changelist_shows_a_jalali_column_beside_the_gregorian_one(self):
        html = self._changelist("order_order")
        self.assertIn("column-created_at", html)
        self.assertIn("column-created_at_jalali", html)
        self.assertIn("1405/01/01 00:00", html)

    def test_shipment_changelist_shows_jalali_or_a_dash_when_never_tracked(self):
        html = self._changelist("shipping_shipment")
        self.assertIn(
            '<td class="field-last_tracked_at_jalali">1403/01/01 00:00</td>', html
        )
        self.assertIn('<td class="field-last_tracked_at_jalali">-</td>', html)

    def test_payment_transaction_changelist(self):
        html = self._changelist("payments_paymenttransaction")
        self.assertIn("column-created_at_jalali", html)
        self.assertIn("1404/01/01 00:00", html)

    def test_coupon_changelist_shows_both_ends_of_the_window(self):
        html = self._changelist("promotions_coupon")
        self.assertIn('<td class="field-valid_from_jalali">1405/01/01 00:00</td>', html)
        self.assertIn(
            '<td class="field-valid_until_jalali">1404/01/01 00:00</td>', html
        )

    def test_flash_sale_changelist_and_sorting_by_a_jalali_column(self):
        html = self._changelist("promotions_flashsale")
        self.assertIn("1403/01/01 00:00", html)
        self.assertIn("1405/01/01 00:00", html)
        index = (
            list(FlashSaleAdmin(FlashSale, AdminSite()).list_display).index(
                "starts_at_jalali"
            )
            + 1
        )
        asc = self.client.get(
            reverse("admin:promotions_flashsale_changelist"), {"o": str(index)}
        ).content.decode()
        desc = self.client.get(
            reverse("admin:promotions_flashsale_changelist"), {"o": f"-{index}"}
        ).content.decode()
        self.assertLess(
            asc.index("Early"), asc.index("Late")
        )  # by the Gregorian starts_at
        self.assertLess(desc.index("Late"), desc.index("Early"))

    # ── detail views ─────────────────────────────────────────────────────────
    def test_order_detail_shows_both_timestamps_in_the_timestamps_section(self):
        html = self._change("order_order", self.order.pk)
        self.assertIn("1405/01/01 00:00", html)  # created_at
        self.assertIn("1404/01/01 00:00", html)  # updated_at
        positions = [
            html.index(f"field-{n}")
            for n in (
                "created_at",
                "created_at_jalali",
                "updated_at",
                "updated_at_jalali",
            )
        ]
        self.assertEqual(positions, sorted(positions))

    def test_coupon_form_puts_each_jalali_value_right_after_its_gregorian_input(self):
        html = self._change("promotions_coupon", self.coupon.pk)
        positions = [
            html.index(f"field-{n}")
            for n in (
                "valid_from",
                "valid_from_jalali",
                "valid_until",
                "valid_until_jalali",
            )
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("1405/01/01 00:00", html)

    def test_flash_sale_shipment_and_payment_detail_pages(self):
        self.assertIn(
            "1405/01/01 00:00", self._change("promotions_flashsale", self.late.pk)
        )
        self.assertIn(
            "1403/01/01 00:00", self._change("shipping_shipment", self.tracked.pk)
        )
        self.assertIn(
            "1404/01/01 00:00", self._change("payments_paymenttransaction", self.txn.pk)
        )

    # ── language ─────────────────────────────────────────────────────────────
    def test_column_headers_follow_the_request_language(self):
        persian = self._changelist("order_order", HTTP_ACCEPT_LANGUAGE="fa")
        english = self._changelist("order_order", HTTP_ACCEPT_LANGUAGE="en")
        self.assertIn("تاریخ ایجاد (شمسی)", persian)
        self.assertIn("Created (Jalali)", english)
        self.assertNotIn("Created (Jalali)", persian)

    # ── storage is untouched ────────────────────────────────────────────────
    def test_the_stored_value_is_still_the_utc_instant(self):
        stored = Order.objects.get(pk=self.order.pk).created_at
        self.assertEqual(stored, self.NOWRUZ_1405)
        self.assertEqual(stored.utcoffset(), datetime.timedelta(0))
