"""
order/tests/test_checkout_i18n.py
─────────────────────────────────
End-to-end language switching on the real checkout endpoint (Task 14.1.1.4):
the stock error a customer sees must follow the request's Accept-Language
header (resolved by LocaleMiddleware), default to Persian when the header is
absent, and fall back cleanly in both directions.
"""

from cart.models import Cart
from django.test import override_settings
from django.utils import translation
from order.serializers import OrderCreateSerializer
from rest_framework import serializers, status
from rest_framework.test import APITestCase

from .factories import (
    make_cart_with_items,
    make_product,
    make_user,
    make_variant,
    valid_payload,
)

URL = "/api/orders/"

# Persian / English wording of the pre-check stock error (cart wants 2, only
# 1 in stock). Substrings keep the test robust to product-name interpolation.
FA_NOT_AVAILABLE = "به تعداد درخواستی شما موجود نیست"
EN_NOT_AVAILABLE = "is no longer available in the requested quantity"


class CheckoutStockErrorLanguageTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product(name="Velvet Lipstick", price=1_000_000, stock=1)
        self.variant = make_variant(product=self.product, price=1_000_000, stock=1)
        make_cart_with_items(self.user, [{"variant": self.variant, "quantity": 2}])
        self.client.force_authenticate(user=self.user)

    def _post(self, **extra):
        return self.client.post(URL, valid_payload(), format="json", **extra)

    def _cart_error_text(self, res):
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, res.content)
        return " ".join(str(e) for e in res.json()["cart"])

    def test_accept_language_fa_returns_persian_error(self):
        text = self._cart_error_text(self._post(HTTP_ACCEPT_LANGUAGE="fa"))
        self.assertIn(FA_NOT_AVAILABLE, text)
        self.assertIn(self.product.name, text)
        self.assertIn(self.variant.sku, text)
        self.assertNotIn(EN_NOT_AVAILABLE, text)

    def test_accept_language_en_returns_english_error(self):
        text = self._cart_error_text(self._post(HTTP_ACCEPT_LANGUAGE="en"))
        self.assertIn(EN_NOT_AVAILABLE, text)
        self.assertNotIn(FA_NOT_AVAILABLE, text)

    def test_browser_style_header_with_quality_values(self):
        text = self._cart_error_text(
            self._post(HTTP_ACCEPT_LANGUAGE="fa-IR,fa;q=0.9,en;q=0.5")
        )
        self.assertIn(FA_NOT_AVAILABLE, text)

    @override_settings(LANGUAGE_CODE="fa")
    def test_no_header_falls_back_to_persian_site_default(self):
        text = self._cart_error_text(self._post())
        self.assertIn(FA_NOT_AVAILABLE, text)

    def test_unsupported_language_falls_back_to_site_default(self):
        # German is not in LANGUAGES, so LocaleMiddleware must ignore it and
        # use LANGUAGE_CODE (pinned to "en" by conftest; "fa" in production).
        text = self._cart_error_text(self._post(HTTP_ACCEPT_LANGUAGE="de"))
        self.assertIn(EN_NOT_AVAILABLE, text)

    def test_content_language_header_reports_the_language_used(self):
        res = self._post(HTTP_ACCEPT_LANGUAGE="fa")
        self.assertEqual(res.headers.get("Content-Language"), "fa")


class LockedStockErrorLanguageTests(APITestCase):
    """The race-safe check inside create() ("Only N of ... left in stock")."""

    def setUp(self):
        self.user = make_user()
        product = make_product(name="Velvet Lipstick", price=1_000_000, stock=1)
        self.variant = make_variant(product=product, price=1_000_000, stock=1)
        make_cart_with_items(self.user, [{"variant": self.variant, "quantity": 2}])
        self.request = type(
            "Request", (), {"user": self.user, "build_absolute_uri": lambda s, u: u}
        )()

    def _stock_message(self, language):
        payload = valid_payload()
        s = OrderCreateSerializer(data=payload, context={"request": self.request})
        validated = s.to_internal_value(payload)  # skips validate()'s pre-check
        validated["cart"] = Cart.objects.get(user=self.user)
        with translation.override(language):
            with self.assertRaises(serializers.ValidationError) as ctx:
                s.create(validated)
        return str(ctx.exception.detail["stock"])

    def test_persian(self):
        message = self._stock_message("fa")
        self.assertTrue(message.startswith("فقط 1 عدد از «Velvet Lipstick"), message)
        self.assertTrue(message.endswith("در انبار موجود است."), message)

    def test_english(self):
        message = self._stock_message("en")
        self.assertTrue(message.startswith("Only 1 of 'Velvet Lipstick"), message)
        self.assertTrue(message.endswith("left in stock."), message)
