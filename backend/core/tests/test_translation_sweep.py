"""
core/tests/test_translation_sweep.py
────────────────────────────────────
Regression tests for the gettext sweep (Task 14.1.1.3).

Three things are proven here, none of which needs a database:

  1. END-TO-END: real customer-facing messages change language when "fa" is
     activated. Task 14.1.1.4's real .po/.mo files may not exist yet, so the
     tests compile a tiny catalog of their own into a temp LOCALE_PATHS
     directory — this proves the wrapping mechanism works, independent of
     whatever translations the project eventually ships.
  2. PLACEHOLDERS: a message with a %(name)s placeholder is translated as a
     *template* and interpolated afterwards (the f-string pitfall).
  3. STATIC GUARD: no translation call anywhere in the backend wraps an
     f-string / pre-interpolated string, which makemessages cannot extract.
"""

import ast
import struct
import tempfile
from pathlib import Path
from types import SimpleNamespace

from cart.serializers import CartItemSerializer
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import SimpleTestCase, override_settings
from django.utils import translation
from order.models import Order
from shop.validators import REVIEW_IMAGE_MAX_BYTES, validate_review_image

FA_QUANTITY = "تعداد باید حداقل ۱ باشد."
FA_IMAGE_TOO_LARGE = "حجم تصویر باید کمتر از %(max_mb)s مگابایت باشد."
FA_PENDING = "در انتظار"

TEST_CATALOG = {
    "Quantity must be at least 1.": FA_QUANTITY,
    "Image must be under %(max_mb)s MB.": FA_IMAGE_TOO_LARGE,
    "Pending": FA_PENDING,
}


def _build_mo(messages: dict) -> bytes:
    """Minimal GNU .mo writer (same layout as CPython's Tools/i18n/msgfmt.py),
    so the test doesn't depend on the `msgfmt` binary being installed."""
    messages = {"": "Content-Type: text/plain; charset=UTF-8\n", **messages}
    keys = sorted(messages)
    ids = strs = b""
    offsets = []
    for key in keys:
        kb, vb = key.encode("utf-8"), messages[key].encode("utf-8")
        offsets.append((len(ids), len(kb), len(strs), len(vb)))
        ids += kb + b"\0"
        strs += vb + b"\0"
    keystart = 7 * 4 + 16 * len(keys)
    valuestart = keystart + len(ids)
    koffsets, voffsets = [], []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]
    header = struct.pack(
        "Iiiiiii", 0x950412DE, 0, len(keys), 7 * 4, 7 * 4 + len(keys) * 8, 0, 0
    )
    return (
        header
        + struct.pack(f"{len(koffsets)}i", *koffsets)
        + struct.pack(f"{len(voffsets)}i", *voffsets)
        + ids
        + strs
    )


class TranslationMechanismTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory()
        mo_dir = Path(cls._tmp.name) / "fa" / "LC_MESSAGES"
        mo_dir.mkdir(parents=True)
        (mo_dir / "django.mo").write_bytes(_build_mo(TEST_CATALOG))
        cls._override = override_settings(LOCALE_PATHS=[cls._tmp.name])
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        cls._tmp.cleanup()
        super().tearDownClass()

    def _quantity_error(self):
        with self.assertRaises(Exception) as ctx:
            CartItemSerializer().validate_quantity(0)
        return str(ctx.exception.detail[0])

    def test_cart_quantity_error_is_english_when_english_active(self):
        with translation.override("en"):
            self.assertEqual(self._quantity_error(), "Quantity must be at least 1.")

    def test_cart_quantity_error_is_translated_when_persian_active(self):
        with translation.override("fa"):
            self.assertEqual(self._quantity_error(), FA_QUANTITY)

    def test_placeholder_message_is_translated_then_interpolated(self):
        too_big = SimpleNamespace(size=REVIEW_IMAGE_MAX_BYTES + 1)
        with translation.override("fa"):
            with self.assertRaises(DjangoValidationError) as ctx:
                validate_review_image(too_big)
        self.assertEqual(
            ctx.exception.messages[0], "حجم تصویر باید کمتر از 5 مگابایت باشد."
        )
        # The error `code` is a stable, untranslated machine value.
        self.assertEqual(ctx.exception.error_list[0].code, "image_too_large")

    def test_choice_label_is_translated_but_stored_value_is_stable(self):
        with translation.override("fa"):
            self.assertEqual(str(Order.Status.PENDING.label), FA_PENDING)
            self.assertEqual(Order.Status.PENDING.value, "pending")
            self.assertIn(("pending", Order.Status.PENDING.label), Order.Status.choices)
        with translation.override("en"):
            self.assertEqual(str(Order.Status.PENDING.label), "Pending")

    def test_insufficient_stock_message_is_a_translatable_template(self):
        """
        The checkout stock error needs a database to raise for real, so this
        pins the shape instead: it must be a %-placeholder template inside a
        translation call in order/serializers.py (the f-string form it used
        before the sweep cannot be extracted or translated).
        """
        source = (Path(settings.BASE_DIR) / "order" / "serializers.py").read_text()
        wanted = "Only %(stock)s of '%(product)s — %(variant)s' left in stock."
        found = [
            node.args[0].value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and _call_name(node) in TRANSLATION_FUNCS
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ]
        self.assertIn(wanted, found)


TRANSLATION_FUNCS = {"_", "gettext", "gettext_lazy", "ngettext", "ngettext_lazy"}
SKIP_PARTS = {"migrations", "tests", "locale", "venv", ".venv", "node_modules"}


def _call_name(node: ast.Call) -> str:
    fn = node.func
    return fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")


class NoPreInterpolatedTranslationsTests(SimpleTestCase):
    """Static guard against the f-string pitfall (and its %/.format cousins)."""

    def test_no_translation_call_wraps_an_interpolated_string(self):
        offenders = []
        for path in Path(settings.BASE_DIR).rglob("*.py"):
            if SKIP_PARTS & set(path.relative_to(settings.BASE_DIR).parts):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and _call_name(node) in TRANSLATION_FUNCS
                    and node.args
                ):
                    continue
                arg = node.args[0]
                bad = (
                    isinstance(arg, ast.JoinedStr)  # _(f"...")
                    or (isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mod))
                    or (  # _("...".format(...))
                        isinstance(arg, ast.Call)
                        and getattr(arg.func, "attr", "") == "format"
                    )
                )
                if bad:
                    rel = path.relative_to(settings.BASE_DIR)
                    offenders.append(f"{rel}:{node.lineno}")
        self.assertEqual(
            offenders,
            [],
            "Translate a static %(name)s template, then interpolate: "
            "_('Only %(n)s left') % {'n': n}",
        )
