"""
core/tests/test_persian_catalog.py
──────────────────────────────────
Tests the REAL Persian catalog shipped in locale/fa/LC_MESSAGES (Task
14.1.1.4) — unlike test_translation_sweep.py, which proves the wrapping
mechanism with a throwaway catalog of its own. Needs no database.

The compiled .mo is gitignored and built at deploy time, so on a fresh
checkout it may not exist yet; setUpModule compiles it (needs the GNU gettext
binaries — the same system dependency the Dockerfile installs).
"""

import gettext as gettext_module
import re
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase
from django.utils import translation
from django.utils.translation import gettext, trans_real

LOCALE_DIR = Path(settings.BASE_DIR) / "locale" / "fa" / "LC_MESSAGES"
PO, MO = LOCALE_DIR / "django.po", LOCALE_DIR / "django.mo"

STOCK_MSGID = "Only %(stock)s of '%(product)s — %(variant)s' left in stock."
PLACEHOLDER = re.compile(r"%\([a-z_]+\)[sd]")
# Keep Persian letters; a Persian message must not still be the English text.
PERSIAN_LETTERS = re.compile(r"[\u0600-\u06FF]")


def setUpModule():
    if not MO.exists() or MO.stat().st_mtime < PO.stat().st_mtime:
        call_command("compilemessages", locale=["fa"], verbosity=0)
    # Drop any catalog cached before the .mo existed / was rebuilt.
    trans_real._translations.clear()
    trans_real._default = None


def _catalog():
    """This project's own compiled fa catalog, as {msgid: msgstr}. Read from
    the .mo directly: the catalog Django serves also merges in Django's and
    third-party apps' entries, which are not ours to police."""
    with MO.open("rb") as fh:
        cat = gettext_module.GNUTranslations(fh)._catalog
    return {k: v for k, v in cat.items() if isinstance(k, str) and k}


class StockErrorLanguageSwitchTests(SimpleTestCase):
    """The same checkout stock message, switched in both directions."""

    values = {"stock": 3, "product": "Velvet Lipstick", "variant": "Rose"}

    def tearDown(self):
        translation.deactivate()

    def test_persian_when_fa_activated(self):
        translation.activate("fa")
        message = gettext(STOCK_MSGID) % self.values
        self.assertEqual(
            message, "فقط 3 عدد از «Velvet Lipstick — Rose» در انبار موجود است."
        )
        self.assertNotIn("left in stock", message)

    def test_english_when_en_activated(self):
        translation.activate("en")
        message = gettext(STOCK_MSGID) % self.values
        self.assertEqual(message, "Only 3 of 'Velvet Lipstick — Rose' left in stock.")

    def test_switching_back_and_forth_in_one_process(self):
        for lang, needle in (
            ("fa", "در انبار"),
            ("en", "in stock"),
            ("fa", "در انبار"),
        ):
            translation.activate(lang)
            self.assertIn(needle, gettext(STOCK_MSGID) % self.values)


class CatalogIntegrityTests(SimpleTestCase):
    """Guards against future .po edits silently breaking customer messages."""

    def test_catalog_is_not_empty(self):
        self.assertGreater(len(_catalog()), 200)

    def test_every_message_is_translated_into_persian_script(self):
        # Brand-ish values may legitimately contain Latin text, but every
        # entry must contain at least some Persian-script letters.
        untranslated = [
            msgid
            for msgid, msgstr in _catalog().items()
            if not PERSIAN_LETTERS.search(msgstr)
        ]
        self.assertEqual(untranslated, [])

    def test_placeholders_survive_translation_exactly(self):
        broken = [
            msgid
            for msgid, msgstr in _catalog().items()
            if sorted(PLACEHOLDER.findall(msgid)) != sorted(PLACEHOLDER.findall(msgstr))
        ]
        self.assertEqual(broken, [])

    def test_every_translated_message_interpolates_cleanly(self):
        for msgid, msgstr in _catalog().items():
            names = {m[2:-2] for m in PLACEHOLDER.findall(msgid)}
            if names:
                msgstr % {name: 1 for name in names}  # raises on a bad format

    def test_key_customer_messages_are_translated(self):
        with translation.override("fa"):
            for msgid in (
                "Your cart is empty.",
                "Invalid coupon code.",
                "Quantity must be at least 1.",
                "This coupon has expired.",
                "Incorrect code.",
            ):
                self.assertNotEqual(gettext(msgid), msgid)

    def test_choice_keys_untouched_but_labels_translated(self):
        from order.models import Order

        with translation.override("fa"):
            self.assertEqual(str(Order.Status.PENDING.label), "در انتظار")
            self.assertEqual(Order.Status.PENDING.value, "pending")
        with translation.override("en"):
            self.assertEqual(str(Order.Status.PENDING.label), "Pending")


# ── Source <-> .po synchronisation ────────────────────────────────────────────
# The tests above inspect the COMPILED catalog, which silently omits fuzzy and
# empty entries — so a changed msgid (e.g. a message that gained "Toman") could
# fall back to English in production without any test noticing. These read the
# .po itself and the source tree.

SKIP_PARTS = {"migrations", "tests", "locale", "venv", ".venv", "node_modules"}
TRANSLATION_FUNCS = {"_", "gettext", "gettext_lazy"}


def _parse_po(path):
    """[(msgid, msgstr, flags)] for every live (non-obsolete) entry, header excluded."""
    import ast as _ast

    entries = []
    for block in path.read_text(encoding="utf-8").split("\n\n"):
        lines = block.strip().split("\n")
        if any(line.startswith("#~") for line in lines):
            continue
        flags, msgid, msgstr, target = [], [], [], None
        for line in lines:
            if line.startswith("#,"):
                flags += [f.strip() for f in line[2:].split(",")]
            elif line.startswith("msgid "):
                target = msgid
                target.append(_ast.literal_eval(line[6:]))
            elif line.startswith("msgstr "):
                target = msgstr
                target.append(_ast.literal_eval(line[7:]))
            elif line.startswith('"') and target is not None:
                target.append(_ast.literal_eval(line))
        if msgid and "".join(msgid):
            entries.append(("".join(msgid), "".join(msgstr), flags))
    return entries


class PoFileSyncTests(SimpleTestCase):
    def test_every_po_entry_is_translated_and_not_fuzzy(self):
        entries = _parse_po(PO)
        self.assertGreater(len(entries), 200)
        self.assertEqual([m for m, s, f in entries if not s.strip()], [])
        self.assertEqual([m for m, s, f in entries if "fuzzy" in f], [])

    def test_every_translated_string_in_the_source_is_in_the_po(self):
        """Run makemessages + translate whenever this fails."""
        import ast as _ast

        base = Path(settings.BASE_DIR)
        in_po = {m for m, s, f in _parse_po(PO)}
        missing = {}
        for path in base.rglob("*.py"):
            if SKIP_PARTS & set(path.relative_to(base).parts):
                continue
            for node in _ast.walk(_ast.parse(path.read_text(encoding="utf-8"))):
                if not (isinstance(node, _ast.Call) and node.args):
                    continue
                fn = node.func
                name = fn.id if isinstance(fn, _ast.Name) else getattr(fn, "attr", "")
                arg = node.args[0]
                if (
                    name in TRANSLATION_FUNCS
                    and isinstance(arg, _ast.Constant)
                    and isinstance(arg.value, str)
                    and arg.value not in in_po
                ):
                    missing[arg.value] = f"{path.relative_to(base)}:{node.lineno}"
        self.assertEqual(
            missing, {}, "wrapped in code but absent from locale/fa django.po"
        )
