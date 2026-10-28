"""
order/tests/test_money_pipeline.py
──────────────────────────────────
End-to-end consistency of ONE purchase through the whole money pipeline
(Task 14.1.2.2 / ADR 0001):

    product page -> cart -> coupon -> checkout -> payment gateway -> invoice PDF

Every figure is asserted against every other: the same integer Rial must appear
in the API, the stored order, the payload actually POSTed to the gateway, and
the invoice — with no truncation, no drift, and nothing left to round at
display time. Real endpoints and the real ZarinPalGateway adapter are used;
only the outbound HTTP call to ZarinPal is stubbed (to capture its payload).
"""

import io
from decimal import Decimal
from unittest.mock import MagicMock, patch

from cart.models import Cart
from core.money import percent_of, rial_to_toman
from django.test import override_settings
from order.models import Order
from payments.models import PaymentTransaction
from promotions.models import Coupon
from promotions.tests.factories import make_saved_coupon
from pypdf import PdfReader
from rest_framework import status
from rest_framework.test import APITestCase

from .factories import (
    make_product,
    make_shipping_rate,
    make_user,
    make_variant,
    valid_payload,
)
from .test_invoice import pdf_text, squash

AUTHORITY = "A" + "0" * 35


def _zarinpal_ok():
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "data": {"code": 100, "authority": AUTHORITY},
        "errors": [],
    }
    return response


@override_settings(ZARINPAL_MERCHANT_ID="x" * 36)
class MoneyPipelineEndToEndTests(APITestCase):
    PRICE = (
        1_234_560  # 123,456 Toman — chosen so tax and a 15% coupon BOTH need rounding
    )
    SHIPPING = 500_000
    PERCENT = Decimal("15.00")

    def setUp(self):
        self.user = make_user()
        self.product = make_product(price=self.PRICE)
        self.variant = make_variant(product=self.product, price=self.PRICE, stock=10)
        self.rate = make_shipping_rate(price=self.SHIPPING)
        self.coupon = make_saved_coupon(
            code="SAVE15",
            discount_type=Coupon.DiscountType.PERCENT,
            percent_off=self.PERCENT,
        )
        self._login(self.client, self.user)

    def _login(self, client, user, password="TestPass123!"):
        """
        Authenticate through the REAL JWT login endpoint, so every later request
        loads its user afresh from the database, exactly as in production. (DRF's
        force_authenticate reuses one in-memory user across requests, whose cached
        reverse relations — e.g. ``user.cart`` — go stale after another request
        changes them, which would hide the coupon attached by apply-coupon.)
        """
        res = client.post(
            "/api/auth/login/",
            {"email": user.email, "password": password},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.json()['access']}")

    # -- the whole chain ------------------------------------------------------
    def test_one_purchase_is_consistent_from_product_page_to_invoice(self):
        # Hand-computed expectations (integer Rial, whole-Toman rounding, ties up)
        expected_tax = 123_460  # 10% of 1,234,560 = 123,456 -> 12,346 Toman
        expected_discount = 185_180  # 15% = 185,184 -> 18,518 Toman
        expected_total = (
            self.PRICE + self.SHIPPING + expected_tax - expected_discount
        )  # 1,672,840
        self.assertEqual(expected_total, 1_672_840)

        # 1. Product page: a JSON INTEGER of Rial, never a string / decimal.
        page = self.client.get(f"/api/products/{self.product.slug}/")
        self.assertEqual(page.status_code, status.HTTP_200_OK, page.content)
        self.assertEqual(page.json()["price"], self.PRICE)
        self.assertIs(type(page.json()["price"]), int)
        self.assertEqual(rial_to_toman(self.PRICE), 123_456)  # what the shopper reads

        # 2. Add to cart
        res = self.client.post(
            "/api/cart/", {"variant_id": self.variant.id, "quantity": 1}, format="json"
        )
        self.assertIn(
            res.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED), res.content
        )
        cart = self.client.get("/api/cart/").json()
        self.assertEqual(cart["subtotal"], self.PRICE)
        self.assertEqual(cart["items"][0]["unit_price"], self.PRICE)
        self.assertEqual(cart["items"][0]["subtotal"], self.PRICE)

        # 3. Apply the percentage coupon: rounded ONCE, to a whole Toman
        res = self.client.post(
            "/api/cart/apply-coupon/", {"code": "SAVE15"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        self.assertEqual(res.json()["discount_amount"], expected_discount)
        self.assertIs(type(res.json()["discount_amount"]), int)
        self.assertEqual(
            self.client.get("/api/cart/").json()["coupon_discount"], expected_discount
        )

        # 4. Checkout
        res = self.client.post(
            "/api/orders/",
            valid_payload(
                shipping_rate_id=self.rate.id, shipping_carrier_id=self.rate.carrier_id
            ),
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        body = res.json()
        order = Order.objects.get(pk=body["id"])
        for field, value in (
            ("subtotal", self.PRICE),
            ("shipping_cost", self.SHIPPING),
            ("tax", expected_tax),
            ("discount", expected_discount),
            ("total", expected_total),
        ):
            with self.subTest(field=field):
                self.assertEqual(getattr(order, field), value)  # stored
                self.assertEqual(body[field], value)  # API echo, same integer
                self.assertIs(type(body[field]), int)
                self.assertEqual(
                    value % 10, 0
                )  # whole Toman: nothing to round at display
        # The pricing identity (ADR I-4) holds exactly on the stored row
        self.assertEqual(
            order.total,
            order.subtotal + order.shipping_cost + order.tax - order.discount,
        )
        self.assertEqual(order.items.get().unit_price, self.PRICE)  # frozen snapshot

        # 5. Payment: the amount POSTed to ZarinPal is the stored total, unchanged
        with patch(
            "payments.gateways.zarinpal.requests.post", return_value=_zarinpal_ok()
        ) as post:
            res = self.client.post(
                "/api/payments/initiate/", {"order_id": order.id}, format="json"
            )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["amount"], expected_total)
        self.assertIs(
            type(sent["amount"]), int
        )  # not Decimal, not a string, not x10 / ÷10
        txn = PaymentTransaction.objects.get(order=order)
        self.assertEqual(txn.amount, expected_total)
        self.assertEqual(txn.amount, order.total)

        # 6. Invoice PDF: same figures, grouped; Toman total derived exactly
        pdf = self.client.get(f"/api/orders/{order.id}/invoice/")
        self.assertEqual(pdf.status_code, status.HTTP_200_OK)
        text = pdf_text(pdf.content)
        for shown in (
            "1,234,560",
            "500,000",
            "123,460",
            "185,180",
            "1,672,840",
            "167,284Toman",
        ):
            self.assertIn(squash(shown), text, f"missing from invoice: {shown}")
        self.assertNotIn(
            squash("1,672,840.00"), text
        )  # no leftover 2-decimal formatting
        self.assertEqual(len(PdfReader(io.BytesIO(pdf.content)).pages) >= 1, True)

    # -- no fractional-precision bug, across several roundings ---------------
    def test_percentage_discounts_always_yield_a_whole_toman_total(self):
        cases = [
            (999_900, "15.00"),  # exact tie (149,985 -> rounds up)
            (333_330, "10.00"),  # rounds down
            (1_999_990, "33.33"),  # awkward repeating fraction
            (7_654_320, "7.50"),
        ]
        for price, percent in cases:
            with self.subTest(price=price, percent=percent):
                user = make_user(email=f"u{price}@example.com")
                variant = make_variant(
                    product=make_product(
                        price=price, name=f"P{price}", slug=f"p-{price}"
                    ),
                    price=price,
                    stock=5,
                )
                coupon = make_saved_coupon(
                    code=f"C{price}",
                    discount_type=Coupon.DiscountType.PERCENT,
                    percent_off=Decimal(percent),
                )
                client = self.client_class()
                self._login(client, user)
                client.post(
                    "/api/cart/",
                    {"variant_id": variant.id, "quantity": 1},
                    format="json",
                )
                client.post(
                    "/api/cart/apply-coupon/", {"code": coupon.code}, format="json"
                )
                res = client.post(
                    "/api/orders/",
                    valid_payload(
                        shipping_rate_id=self.rate.id,
                        shipping_carrier_id=self.rate.carrier_id,
                    ),
                    format="json",
                )
                self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
                order = Order.objects.get(pk=res.json()["id"])

                discount = percent_of(price, Decimal(percent))
                tax = percent_of(price, Decimal("10"))
                self.assertEqual(order.discount, discount)
                self.assertEqual(order.tax, tax)
                self.assertEqual(order.total, price + self.SHIPPING + tax - discount)
                for value in (
                    order.subtotal,
                    order.shipping_cost,
                    order.tax,
                    order.discount,
                    order.total,
                ):
                    self.assertEqual(value % 10, 0)
                self.assertEqual(
                    rial_to_toman(order.total) * 10, order.total
                )  # exact conversion
                Cart.objects.filter(user=user).delete()
