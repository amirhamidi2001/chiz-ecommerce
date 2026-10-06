"""
Tests for PDF invoice generation + download (Task 8.1.2.1).
"""

import io
import re
from decimal import Decimal

from accounts.models import UserType
from order.models import Order, OrderItem
from order.services.invoice import generate_invoice_pdf
from pypdf import PdfReader
from rest_framework.test import APITestCase

from .factories import make_user, make_variant


def squash(text):
    return re.sub(r"\s+", "", text)


def pdf_text(pdf_bytes):
    """
    Extractable text of the PDF with ALL whitespace removed. Text extraction
    inserts spurious spaces at kerning pairs ("T ehran"), so assertions use
    `squash(expected)` against this squashed text.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return squash("\n".join(page.extract_text() for page in reader.pages))


def make_invoice_order(user, variant, *, quantity=2, unit_price="25.00", **extra):
    unit = Decimal(unit_price)
    order = Order.objects.create(
        user=user,
        status=Order.Status.PROCESSING,
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        phone="09121234567",
        shipping_address="12 Valiasr St",
        shipping_apartment="Unit 4",
        shipping_city="Tehran",
        shipping_state="tehran",
        shipping_zip="1234567890",
        shipping_country="IR",
        payment_method="credit_card",
        card_last_four="4242",
        subtotal=unit * quantity,
        shipping_cost=Decimal("9.99"),
        tax=Decimal("4.50"),
        discount=Decimal("3.00"),
        total=unit * quantity + Decimal("9.99") + Decimal("4.50") - Decimal("3.00"),
        **extra,
    )
    OrderItem.objects.create(
        order=order,
        product=variant.product,
        variant=variant,
        product_name=variant.product.name,
        product_slug=variant.product.slug,
        variant_sku=variant.sku,
        variant_attributes_json={"color": "Rose"},
        unit_price=unit,
        quantity=quantity,
    )
    return order


class OrderInvoiceEndpointTests(APITestCase):
    def setUp(self):
        self.owner = make_user(email="owner@example.com")
        self.other = make_user(email="other@example.com")
        self.admin = make_user(email="admin@example.com")
        self.admin.type = UserType.ADMIN
        self.admin.save(update_fields=["type"])
        self.staff = make_user(email="staff@example.com", is_staff=True)

        self.variant = make_variant(name="Silk Scarf", slug="silk-scarf", price="25.00")
        self.order = make_invoice_order(self.owner, self.variant)
        self.url = f"/api/orders/{self.order.pk}/invoice/"

    def assertIsPdf(self, res):
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF"))
        self.assertGreater(len(res.content), 1000)

    def test_owner_can_download_own_invoice(self):
        self.client.force_authenticate(self.owner)
        res = self.client.get(self.url)
        self.assertIsPdf(res)
        self.assertEqual(
            res["Content-Disposition"],
            f'attachment; filename="invoice_{self.order.order_number}.pdf"',
        )

    def test_admin_can_download_any_customers_invoice(self):
        self.client.force_authenticate(self.admin)
        self.assertIsPdf(self.client.get(self.url))

    def test_django_staff_can_download_any_customers_invoice(self):
        self.client.force_authenticate(self.staff)
        self.assertIsPdf(self.client.get(self.url))

    def test_other_customer_gets_403(self):
        self.client.force_authenticate(self.other)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 403)
        self.assertNotIn("application/pdf", res["Content-Type"])

    def test_anonymous_gets_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_unknown_order_is_404(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.get("/api/orders/999999/invoice/").status_code, 404
        )

    def test_order_without_user_is_admin_only(self):
        orphan = make_invoice_order(None, self.variant)
        url = f"/api/orders/{orphan.pk}/invoice/"
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_accept_application_pdf_header_is_not_a_406(self):
        self.client.force_authenticate(self.owner)
        self.assertIsPdf(self.client.get(self.url, HTTP_ACCEPT="application/pdf"))

    def test_403_with_pdf_accept_header_is_not_a_500(self):
        self.client.force_authenticate(self.other)
        res = self.client.get(self.url, HTTP_ACCEPT="application/pdf")
        self.assertEqual(res.status_code, 403)


class InvoiceContentTests(APITestCase):
    def setUp(self):
        self.user = make_user(email="buyer@example.com")
        self.variant = make_variant(name="Silk Scarf", slug="silk-scarf", price="25.00")
        self.order = make_invoice_order(self.user, self.variant)

    def test_invoice_contains_order_customer_items_and_totals(self):
        text = pdf_text(generate_invoice_pdf(self.order))
        for expected in (
            self.order.order_number,
            "Jane Smith",
            "12 Valiasr St",
            "Unit 4",
            "Tehran",
            "Silk Scarf",
            "Color: Rose",
            self.variant.sku,
            "25.00",  # unit price
            "50.00",  # line total (2 x 25.00)
            "9.99",  # shipping
            "4.50",  # tax
            "3.00",  # discount
            "61.49",  # grand total
            "**** 4242",
        ):
            self.assertIn(squash(expected), text, f"missing from invoice: {expected!r}")

    def test_invoice_reflects_frozen_snapshot_not_current_product(self):
        """Reprice/rename the product AFTER the order: invoice must not change."""
        product = self.variant.product
        product.name = "Renamed Scarf Deluxe"
        product.price = Decimal("99.00")
        product.save()
        self.variant.price = Decimal("99.00")
        self.variant.save(update_fields=["price"])

        text = pdf_text(generate_invoice_pdf(Order.objects.get(pk=self.order.pk)))

        self.assertIn(squash("Silk Scarf"), text)
        self.assertIn(squash("25.00"), text)
        self.assertNotIn(squash("Renamed Scarf Deluxe"), text)
        self.assertNotIn(squash("99.00"), text)

    def test_invoice_survives_deleted_product_and_variant(self):
        self.variant.product.delete()  # FKs are SET_NULL; snapshot remains
        text = pdf_text(generate_invoice_pdf(Order.objects.get(pk=self.order.pk)))
        self.assertIn(squash("Silk Scarf"), text)
        self.assertIn(squash("25.00"), text)

    def test_discount_row_omitted_when_no_discount(self):
        Order.objects.filter(pk=self.order.pk).update(discount=Decimal("0"))
        text = pdf_text(generate_invoice_pdf(Order.objects.get(pk=self.order.pk)))
        self.assertNotIn(squash("Discount"), text)

    def test_customer_text_is_escaped_not_interpreted_as_html(self):
        Order.objects.filter(pk=self.order.pk).update(
            first_name="<b>Eve</b>", last_name="<script>x</script>"
        )
        text = pdf_text(generate_invoice_pdf(Order.objects.get(pk=self.order.pk)))
        self.assertIn(squash("<b>Eve</b>"), text)

    def test_persian_customer_name_renders(self):
        Order.objects.filter(pk=self.order.pk).update(
            first_name="علی", last_name="رحیمی"
        )
        pdf = generate_invoice_pdf(Order.objects.get(pk=self.order.pk))
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_many_items_paginate_without_error(self):
        for i in range(60):
            OrderItem.objects.create(
                order=self.order,
                product_name=f"Bulk item {i}",
                product_slug=f"bulk-{i}",
                unit_price=Decimal("1.00"),
                quantity=1,
            )
        pdf = generate_invoice_pdf(Order.objects.get(pk=self.order.pk))
        self.assertGreater(len(PdfReader(io.BytesIO(pdf)).pages), 1)
        self.assertIn(squash("Bulk item 59"), pdf_text(pdf))
