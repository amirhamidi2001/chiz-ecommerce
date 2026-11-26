"""
dashboard/product_import.py
───────────────────────────
Bulk product + variant import from CSV / Excel (.xlsx).

THE FILE CONTRACT
=================
`IMPORT_COLUMNS` below is the single source of truth for the import schema.
The template download, the parser's header check, the row processor and the
docs (backend/docs/bulk-product-import.md) all derive from / are tested
against it, so they cannot drift apart.

One row = one purchasable VARIANT. Rows sharing a `product_name` are variants
(shades / sizes) of one Product. Where a column lives:

  Product-level (the formulation — repeat it consistently, or put it on the
  product's first row; a conflicting value on a later row is a row error):
      category, brand, skin_type, hair_type, gender, spf, is_cruelty_free,
      is_vegan, is_organic, short_description, description, ingredients,
      usage_instructions, warnings, country_of_origin, irc_regulatory_code
  Variant-level (differs per shade / size / batch):
      sku, color(+color_hex), price, original_price, stock,
      low_stock_threshold, volume_ml, weight_g, barcode, manufacture_date,
      expiration_date, batch_number, is_active

REQUIRED vs OPTIONAL — deliberate choices
-----------------------------------------
* Header: `product_name`, `category` and `price` must be present as columns.
* Cell values: required when the row CREATES something — `category` for a new
  product, `price` for a new variant. On an UPDATE of an existing
  product/variant a blank cell means "leave unchanged", so a narrow sheet
  (e.g. product_name + sku + stock) can refresh one field. (Consequence:
  an import can set or change a value but never clear one.)
* `brand` is optional (Product.brand is nullable) but must exist if given.
* Everything else is optional; blank on create = the model default.
* NOT importable on purpose: `regulatory_verified` (a staff verification,
  not data), images, ratings, and the is_new / is_sale marketing flags.

LOOKUP RULES (CREATE vs UPDATE)
-------------------------------
* `category` / `brand`: must already exist — an unknown one is a row ERROR
  (with a "did you mean" hint), never auto-created: a typo silently creating
  a garbage taxonomy entry is worse than a clear error. Match is by name,
  ignoring case and Persian/Arabic character variants. Category names that
  exist under several parents are ambiguous → use "Parent > Child".
* `color`: auto-created when new, but then `color_hex` (#RRGGBB) is
  required — a made-up swatch would be shown to customers.
* Variant with `sku`: matched by SKU (globally unique). If found, its product
  must be the one named in `product_name` (else error) and the variant is
  UPDATED. If not found, a variant with exactly that SKU is created.
* Variant without `sku`: the product is matched by name; within it a variant
  is matched by (color, volume_ml, weight_g) — blank = none — and UPDATED,
  otherwise created with an auto-generated SKU. Re-importing the same sheet
  is therefore idempotent.
* Two rows in one file that resolve to the same variant are an error on the
  second.

UNITS & FORMATS
---------------
* price / original_price are integer RIAL (as everywhere in the API), a
  multiple of 10. Persian/Arabic digits and thousands separators are
  accepted.
* Dates are Gregorian YYYY-MM-DD. Years before 1900 are rejected with a
  hint, because a Jalali date typed here would otherwise be stored as
  year 14xx.
* Booleans: true/false, yes/no, 1/0 (also بله/خیر).
* skin_type / hair_type / gender: the stored value or its English label.

SIDE EFFECTS
------------
Changing `stock` on an existing variant records a StockMovement (reason
"manual", the importing admin as actor) like the adjust-stock endpoint does —
but only AFTER the surrounding transaction commits, so a dry run can never
trigger back-in-stock notifications. Variants are saved through save(), so
price signals (cache invalidation, price snapshots, price-drop alerts) run
as for any other price change.
"""

import csv
import difflib
import io
import logging
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from shop.models import (
    Brand,
    Category,
    Color,
    HairType,
    Product,
    ProductGender,
    ProductVariant,
    SkinType,
    StockMovement,
)
from shop.text_utils import normalize_persian_text

logger = logging.getLogger(__name__)

MAX_IMPORT_BYTES = 5 * 1024 * 1024
# Each row costs several queries inside one long transaction; larger catalogs
# should be split into files (and each file's dry run reviewed) rather than
# risking a request timeout.
MAX_IMPORT_ROWS = 1000
MAX_BLANK_ROWS_IN_A_ROW = 1000  # xlsx sheets often carry endless empty rows


# ─── The schema ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Column:
    name: str
    required: bool
    level: str  # "product" | "variant"
    description: str
    example: str  # the template's example row (a string, as typed in a CSV)


IMPORT_COLUMNS = [
    Column(
        "product_name",
        True,
        "product",
        "Product name; rows with the same name are variants of one product.",
        "Example Hydrating Serum",
    ),
    Column(
        "category",
        True,
        "product",
        "Existing category name, or 'Parent > Child'. Unknown = error.",
        "Skincare",
    ),
    Column(
        "brand",
        False,
        "product",
        "Existing brand name. Unknown = error.",
        "Example Brand",
    ),
    Column(
        "sku",
        False,
        "variant",
        "Blank = match/auto-generate; given = match that SKU, or create it.",
        "",
    ),
    Column(
        "color",
        False,
        "variant",
        "Colour/shade name. Created if new (needs color_hex).",
        "Rose",
    ),
    Column(
        "color_hex",
        False,
        "variant",
        "#RRGGBB — required only when `color` does not exist yet.",
        "#E8A0BF",
    ),
    Column(
        "price", True, "variant", "Integer RIAL (multiple of 10), NOT Toman.", "1250000"
    ),
    Column("original_price", False, "variant", "Compare-at price, integer Rial.", ""),
    Column(
        "stock",
        False,
        "variant",
        "Units in stock (whole number). Blank = 0 on create / unchanged on update.",
        "25",
    ),
    Column(
        "low_stock_threshold",
        False,
        "variant",
        "Low-stock alert level (default 5).",
        "5",
    ),
    Column("volume_ml", False, "variant", "Volume in ml (liquids).", "30"),
    Column("weight_g", False, "variant", "Weight in grams (solids).", ""),
    Column("barcode", False, "variant", "EAN-13 with a valid check digit.", ""),
    Column("manufacture_date", False, "variant", "Gregorian YYYY-MM-DD.", "2026-01-15"),
    Column(
        "expiration_date",
        False,
        "variant",
        "Gregorian YYYY-MM-DD; must be after manufacture_date.",
        "2028-01-15",
    ),
    Column("batch_number", False, "variant", "Free text lot number.", "B2601"),
    Column(
        "is_active", False, "variant", "Sellable? true/false (default true).", "true"
    ),
    Column(
        "skin_type",
        False,
        "product",
        "oily, dry, combination, sensitive, normal, all.",
        "dry",
    ),
    Column("hair_type", False, "product", "straight, wavy, curly, coily, all.", ""),
    Column("gender", False, "product", "unisex (default), female, male.", "unisex"),
    Column("spf", False, "product", "SPF 0–100; blank = not applicable.", ""),
    Column(
        "is_cruelty_free",
        False,
        "product",
        "Certified cruelty-free? true/false.",
        "true",
    ),
    Column("is_vegan", False, "product", "Certified vegan? true/false.", "false"),
    Column("is_organic", False, "product", "Certified organic? true/false.", "false"),
    Column(
        "short_description",
        False,
        "product",
        "One-line summary (max 500 chars).",
        "Lightweight hyaluronic serum",
    ),
    Column(
        "description",
        False,
        "product",
        "Full description.",
        "A daily hydrating serum for all-day moisture.",
    ),
    Column(
        "ingredients",
        False,
        "product",
        "Raw INCI ingredient list.",
        "Aqua, Glycerin, Sodium Hyaluronate",
    ),
    Column(
        "usage_instructions",
        False,
        "product",
        "How to use.",
        "Apply 2-3 drops to clean skin.",
    ),
    Column("warnings", False, "product", "Safety warnings.", "For external use only."),
    Column("country_of_origin", False, "product", "Free text.", "France"),
    Column(
        "irc_regulatory_code",
        False,
        "product",
        "IRC registration code (not verified by import).",
        "",
    ),
]

IMPORT_COLUMN_NAMES = [c.name for c in IMPORT_COLUMNS]
REQUIRED_COLUMN_NAMES = [c.name for c in IMPORT_COLUMNS if c.required]
_COLUMN_SET = set(IMPORT_COLUMN_NAMES)

PRODUCT_TEXT_FIELDS = (
    "short_description",
    "description",
    "ingredients",
    "usage_instructions",
    "warnings",
    "country_of_origin",
    "irc_regulatory_code",
)
PRODUCT_BOOL_FIELDS = ("is_cruelty_free", "is_vegan", "is_organic")


class RowError(Exception):
    """A problem with one row, with an admin-readable message."""


class FileError(ValueError):
    """The whole file is unusable (shown as a 400 on the `file` field)."""


# ─── File parsing ─────────────────────────────────────────────────────────────


def _cell_to_str(value) -> str:
    """One spreadsheet cell as the string a CSV cell would have held."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _normalise_header(name) -> str:
    text = _cell_to_str(name).lstrip("\ufeff").strip().lower()
    return re.sub(r"[\s\-]+", "_", text)


def _validated_header(raw_header) -> list:
    header = [_normalise_header(h) for h in raw_header]
    while header and not header[-1]:  # trailing empty header cells
        header.pop()
    if not header:
        raise FileError("The file is empty (no header row).")
    if "" in header:
        raise FileError("The header row has an empty column name.")
    duplicates = sorted({h for h in header if header.count(h) > 1})
    if duplicates:
        raise FileError(f"Duplicate column(s): {', '.join(duplicates)}.")
    unknown = [h for h in header if h not in _COLUMN_SET]
    if unknown:
        raise FileError(
            f"Unknown column(s): {', '.join(unknown)}. "
            "Download the import template for the exact column names."
        )
    missing = [c for c in REQUIRED_COLUMN_NAMES if c not in header]
    if missing:
        raise FileError(f"Missing required column(s): {', '.join(missing)}.")
    return header


# The catalog CSV export prefixes cells that start with a formula character
# with a quote (see views._csv_safe — spreadsheet apps would execute them).
# Undo exactly that on the way back in, so export → edit → re-import never
# changes a description like "- Hydrating" into "'- Hydrating". A real value
# that itself begins with a quote + formula character is indistinguishable
# from an escaped one; that is the same convention Excel uses.
_FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r")


def _undo_csv_safe(cell: str) -> str:
    if len(cell) > 1 and cell[0] == "'" and cell[1] in _FORMULA_LEADS:
        return cell[1:]
    return cell


def _parse_csv(data: bytes):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise FileError(
            "The CSV must be UTF-8 encoded (in Excel: Save As → CSV UTF-8)."
        ) from None
    first_line = text.split("\n", 1)[0]
    delimiter = max(",;\t", key=first_line.count)  # Excel locales differ
    try:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        records = list(reader)
    except csv.Error as exc:
        raise FileError(f"Could not read the CSV: {exc}") from None
    return records[:1] + [[_undo_csv_safe(cell) for cell in row] for row in records[1:]]


def _parse_xlsx(data: bytes):
    from openpyxl import load_workbook
    from openpyxl.utils.exceptions import InvalidFileException

    if not data.startswith(b"PK"):
        raise FileError("This is not a valid .xlsx file.")
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError):
        raise FileError("This is not a valid .xlsx file.") from None
    try:
        sheet = workbook.worksheets[0]  # the first sheet; others are ignored
        records, blanks = [], 0
        for values in sheet.iter_rows(values_only=True):
            records.append(list(values))
            blanks = blanks + 1 if not any(v not in (None, "") for v in values) else 0
            if blanks > MAX_BLANK_ROWS_IN_A_ROW:
                break
    finally:
        workbook.close()
    return records


def parse_import_file(uploaded_file) -> list:
    """
    Parse an uploaded .csv or .xlsx into [(row_number, {column: str})].

    Both formats are reduced to the same shape — every cell a stripped string
    exactly as a CSV would hold it — so a given sheet imports identically
    either way. `row_number` is the spreadsheet row (header = 1); fully blank
    rows are skipped but still counted. Raises FileError for anything that
    makes the whole file unusable.
    """
    name = (getattr(uploaded_file, "name", "") or "").lower()
    if getattr(uploaded_file, "size", 0) > MAX_IMPORT_BYTES:
        raise FileError(
            f"The file is larger than {MAX_IMPORT_BYTES // (1024 * 1024)} MB; "
            "split it into smaller files."
        )
    data = uploaded_file.read()
    if name.endswith(".csv"):
        records = _parse_csv(data)
    elif name.endswith(".xlsx"):
        records = _parse_xlsx(data)
    elif name.endswith(".xls"):
        raise FileError("Old .xls files are not supported; save as .xlsx or .csv.")
    else:
        raise FileError("Unsupported file type; upload a .csv or .xlsx file.")

    if not records:
        raise FileError("The file is empty (no header row).")
    header = _validated_header(records[0])

    rows = []
    for row_number, record in enumerate(records[1:], start=2):
        cells = [_cell_to_str(v) for v in record[: len(header)]]
        cells += [""] * (len(header) - len(cells))
        if not any(cells):
            continue
        # Every schema column is always present (blank when the sheet has no
        # such column), so row processing never has to care which were sent.
        rows.append(
            (
                row_number,
                {**dict.fromkeys(IMPORT_COLUMN_NAMES, ""), **dict(zip(header, cells))},
            )
        )
    if not rows:
        raise FileError("The file has a header but no data rows.")
    if len(rows) > MAX_IMPORT_ROWS:
        raise FileError(
            f"The file has {len(rows)} data rows; the limit is {MAX_IMPORT_ROWS} "
            "per import. Split it into smaller files."
        )
    return rows


# ─── Cell parsing ─────────────────────────────────────────────────────────────

_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٬،", "01234567890123456789,,")
_TRUE = {"true", "yes", "y", "1", "بله"}
_FALSE = {"false", "no", "n", "0", "خیر"}
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _key(text: str) -> str:
    """Comparison key for names: normalised Persian/Arabic variants, no case."""
    return normalize_persian_text(text or "").strip().casefold()


def _parse_int(text: str, column: str, errors: list, maximum=None):
    """Whole number ≥ 0, or None for a blank cell (error appended if bad)."""
    if text == "":
        return None
    cleaned = text.translate(_DIGIT_TABLE).replace(",", "").replace(" ", "")
    if not re.fullmatch(r"\d+", cleaned):
        errors.append(f"{column}: '{text}' is not a whole number.")
        return None
    value = int(cleaned)
    if maximum is not None and value > maximum:
        errors.append(f"{column}: {value} is above the maximum of {maximum}.")
        return None
    return value


def _parse_bool(text: str, column: str, errors: list):
    if text == "":
        return None
    lowered = text.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    errors.append(f"{column}: '{text}' is not true/false (or yes/no, 1/0).")
    return None


def _parse_date(text: str, column: str, errors: list):
    if text == "":
        return None
    cleaned = text.translate(_DIGIT_TABLE).replace("/", "-")
    try:
        parsed = date.fromisoformat(cleaned)
    except ValueError:
        errors.append(f"{column}: '{text}' is not a valid YYYY-MM-DD date.")
        return None
    if not 1900 <= parsed.year <= 2200:
        errors.append(
            f"{column}: '{text}' — dates must be Gregorian YYYY-MM-DD "
            "(this looks like a Jalali date)."
        )
        return None
    return parsed


def _parse_choice(text: str, choices, column: str, errors: list):
    if text == "":
        return None
    wanted = text.strip().casefold()
    for value, label in choices.choices:
        if wanted in (str(value).casefold(), str(label).casefold()):
            return value
    allowed = ", ".join(str(v) for v, _ in choices.choices)
    errors.append(f"{column}: '{text}' is not one of: {allowed}.")
    return None


# ─── Row processing ───────────────────────────────────────────────────────────


class ProductImporter:
    """
    Applies parsed rows to the database, one row at a time.

    Every row runs in its own savepoint (`transaction.atomic()`): a row that
    fails — including with a database error, which would otherwise poison the
    surrounding transaction — rolls back ALL of its own writes (no
    half-created product) and the next row carries on. The caller decides
    whether the whole run is kept (see BulkProductImportView).

    Lookup tables are loaded once. They are only updated after a row
    SUCCEEDS, so a rolled-back row can never leave a phantom entry behind.
    """

    def __init__(self, actor=None):
        self.actor = actor
        self._categories = list(Category.objects.select_related("parent"))
        self._brands = list(Brand.objects.all())
        self._colors = list(Color.objects.all())
        self._products_by_key = {}
        for pk, name in Product.objects.values_list("id", "name"):
            self._products_by_key.setdefault(_key(name), []).append(pk)
        self._seen_variants = {}  # identity → first row number
        self._product_claims = {}  # product id → {field: (value, row)}

    # --- taxonomy lookups -----------------------------------------------------

    def _category_path(self, category) -> str:
        parts, node, guard = [], category, 0
        while node is not None and guard < 20:
            parts.append(_key(node.name))
            node, guard = node.parent, guard + 1
        return " > ".join(reversed(parts))

    def _resolve_category(self, text: str):
        if ">" in text:
            wanted = " > ".join(_key(p) for p in text.split(">"))
            matches = [c for c in self._categories if self._category_path(c) == wanted]
        else:
            wanted = _key(text)
            matches = [c for c in self._categories if _key(c.name) == wanted]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            paths = ", ".join(
                " > ".join(n for n in (c.parent.name if c.parent else "", c.name) if n)
                for c in matches
            )
            raise RowError(
                f"category: '{text}' is ambiguous ({paths}). "
                "Use the full 'Parent > Child' form."
            )
        close = difflib.get_close_matches(
            wanted, [_key(c.name) for c in self._categories], n=1, cutoff=0.75
        )
        hint = ""
        if close:
            nearest = next(c for c in self._categories if _key(c.name) == close[0])
            hint = f" Did you mean '{nearest.name}'?"
        raise RowError(
            f"category: '{text}' does not exist.{hint} "
            "Fix the spelling or create the category first."
        )

    def _resolve_brand(self, text: str):
        wanted = _key(text)
        matches = [b for b in self._brands if _key(b.name) == wanted]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise RowError(f"brand: '{text}' matches more than one brand.")
        close = difflib.get_close_matches(
            wanted, [_key(b.name) for b in self._brands], n=1, cutoff=0.75
        )
        hint = ""
        if close:
            nearest = next(b for b in self._brands if _key(b.name) == close[0])
            hint = f" Did you mean '{nearest.name}'?"
        raise RowError(
            f"brand: '{text}' does not exist.{hint} "
            "Fix the spelling or create the brand first."
        )

    def _resolve_color(self, name: str, hex_code: str):
        """(Color, created). Unknown colours are created — with a real hex."""
        wanted = _key(name)
        matches = [c for c in self._colors if _key(c.name) == wanted]
        if len(matches) > 1:
            raise RowError(f"color: '{name}' matches more than one color.")
        if matches:
            existing = matches[0]
            if hex_code and existing.hex_code.lower() != hex_code.lower():
                raise RowError(
                    f"color_hex: '{hex_code}' conflicts with the existing color "
                    f"'{existing.name}' ({existing.hex_code})."
                )
            return existing, False
        if not hex_code:
            raise RowError(
                f"color: '{name}' does not exist yet — add color_hex "
                "(#RRGGBB) to create it, or fix the spelling."
            )
        return Color(name=name, hex_code=hex_code), True

    # --- one row ----------------------------------------------------------------

    def _parse_cells(self, cells: dict):
        """Typed product- and variant-level values from one row's strings."""
        errors = []
        product, variant = {}, {}

        for field in PRODUCT_TEXT_FIELDS:
            if cells[field]:
                product[field] = cells[field]
        for field in PRODUCT_BOOL_FIELDS:
            value = _parse_bool(cells[field], field, errors)
            if value is not None:
                product[field] = value
        for field, choices in (
            ("skin_type", SkinType),
            ("hair_type", HairType),
            ("gender", ProductGender),
        ):
            value = _parse_choice(cells[field], choices, field, errors)
            if value is not None:
                product[field] = value
        spf = _parse_int(cells["spf"], "spf", errors, maximum=100)
        if spf is not None:
            product["spf"] = spf

        for field in (
            "price",
            "original_price",
            "stock",
            "low_stock_threshold",
            "volume_ml",
            "weight_g",
        ):
            value = _parse_int(cells[field], field, errors)
            if value is not None:
                variant[field] = value
        for field in ("manufacture_date", "expiration_date"):
            value = _parse_date(cells[field], field, errors)
            if value is not None:
                variant[field] = value
        active = _parse_bool(cells["is_active"], "is_active", errors)
        if active is not None:
            variant["is_active"] = active
        for field in ("barcode", "batch_number"):
            if cells[field]:
                variant[field] = cells[field].translate(_DIGIT_TABLE)
        if cells["color_hex"] and not _HEX.match(cells["color_hex"]):
            errors.append(f"color_hex: '{cells['color_hex']}' must look like #RRGGBB.")
        if cells["color_hex"] and not cells["color"]:
            errors.append("color_hex: given without a color name.")
        return product, variant, errors

    def _find_product(self, name: str):
        ids = self._products_by_key.get(_key(name), [])
        if len(ids) > 1:
            raise RowError(
                f"product_name: more than one product is named '{name}'; "
                "identify the variant by its sku."
            )
        return Product.objects.get(pk=ids[0]) if ids else None

    def _find_variant(self, cells, product, color, color_is_new, variant_values):
        """The existing variant this row targets, or None."""
        sku = cells["sku"]
        if sku:
            found = (
                ProductVariant.objects.select_for_update(of=("self",))
                .select_related("product", "color")
                .filter(sku=sku)
                .first()
            )
            if found and _key(found.product.name) != _key(cells["product_name"]):
                raise RowError(
                    f"sku: '{sku}' belongs to product '{found.product.name}', "
                    f"not '{cells['product_name']}'."
                )
            return found
        if product is None or color_is_new:
            return None  # nothing can match a new product / a brand-new colour
        candidates = list(
            ProductVariant.objects.select_for_update(of=("self",))
            .select_related("color")
            .filter(
                product=product,
                color=color,
                volume_ml=variant_values.get("volume_ml"),
                weight_g=variant_values.get("weight_g"),
            )
        )
        if len(candidates) > 1:
            raise RowError(
                "More than one existing variant matches this product/color/size; "
                "identify it by its sku."
            )
        return candidates[0] if candidates else None

    @staticmethod
    def _clean(instance, exclude=()):
        try:
            instance.full_clean(exclude=list(exclude))
        except ValidationError as exc:
            if hasattr(exc, "message_dict"):
                parts = [
                    f"{field}: {' '.join(messages)}"
                    for field, messages in exc.message_dict.items()
                ]
            else:
                parts = list(exc.messages)
            raise RowError("; ".join(parts)) from None

    def process_row(self, row_number: int, cells: dict) -> dict:
        """
        Create or update one variant (and its product). Returns a result dict;
        raises RowError for a bad row. Wrapped by the caller's `except`, and
        runs in its own savepoint so a failure leaves nothing behind.
        """
        if not cells["product_name"]:
            raise RowError("product_name: this is required.")
        product_values, variant_values, errors = self._parse_cells(cells)
        if errors:
            raise RowError(" ".join(errors))

        with transaction.atomic():
            category = (
                self._resolve_category(cells["category"]) if cells["category"] else None
            )
            brand = self._resolve_brand(cells["brand"]) if cells["brand"] else None
            color, color_is_new = (None, False)
            if cells["color"]:
                color, color_is_new = self._resolve_color(
                    cells["color"], cells["color_hex"]
                )

            product = self._find_product(cells["product_name"])
            variant = self._find_variant(
                cells, product, color, color_is_new, variant_values
            )
            if variant is not None:
                product = variant.product

            # Same variant twice in one file? Checked by what the row says
            # (stable even when the first occurrence created the product) and
            # by the variant it actually resolved to.
            identity = (
                ("sku", cells["sku"])
                if cells["sku"]
                else (
                    "variant",
                    _key(cells["product_name"]),
                    _key(cells["color"]),
                    variant_values.get("volume_ml"),
                    variant_values.get("weight_g"),
                )
            )
            resolved = ("pk", variant.pk) if variant is not None else None
            for seen_key in (identity, resolved):
                if seen_key is not None and seen_key in self._seen_variants:
                    raise RowError(
                        f"Duplicate of row {self._seen_variants[seen_key]} "
                        "(same variant listed twice in this file)."
                    )

            product_created = product is None
            if product_created:
                if category is None:
                    raise RowError("category: this is required for a new product.")
                if "price" not in variant_values:
                    raise RowError("price: this is required for a new product.")
                product = Product(
                    name=cells["product_name"],
                    category=category,
                    brand=brand,
                    # Legacy field (the storefront prices from variants); a new
                    # product just needs a valid, consistent value.
                    price=variant_values["price"],
                    **product_values,
                )
                self._clean(product, exclude=("slug", "search_vector"))
                product.save()
            else:
                claims = self._product_claims.setdefault(product.pk, {})
                claimed = dict(product_values)
                if category is not None:
                    claimed["category"] = category.pk
                if brand is not None:
                    claimed["brand"] = brand.pk
                for field, value in claimed.items():
                    if field in claims and claims[field][0] != value:
                        raise RowError(
                            f"{field}: conflicts with the value given on row "
                            f"{claims[field][1]} for the same product."
                        )
                changed = False
                for field, value in product_values.items():
                    if getattr(product, field) != value:
                        setattr(product, field, value)
                        changed = True
                if category is not None and product.category_id != category.pk:
                    product.category, changed = category, True
                if brand is not None and product.brand_id != brand.pk:
                    product.brand, changed = brand, True
                if changed:
                    self._clean(product, exclude=("slug", "search_vector"))
                    product.save()

            if color_is_new:
                self._clean(color)
                color.save()

            if variant is None:
                if "price" not in variant_values:
                    raise RowError("price: this is required for a new variant.")
                variant = ProductVariant(
                    product=product, color=color, sku=cells["sku"], **variant_values
                )
                self._clean(variant, exclude=() if cells["sku"] else ("sku",))
                variant.save()  # generates the SKU when blank
                action = "created"
            else:
                old_stock = variant.stock
                for field, value in variant_values.items():
                    setattr(variant, field, value)
                if color is not None:
                    variant.color = color
                self._clean(variant)
                variant.save()
                action = "updated"
                if "stock" in variant_values and variant.stock != old_stock:
                    self._record_stock_movement(variant, old_stock, row_number)

        # Success: only now touch the in-memory state (a rolled-back row must
        # leave no trace in it).
        self._seen_variants[identity] = row_number
        self._seen_variants[("pk", variant.pk)] = row_number
        claims = self._product_claims.setdefault(product.pk, {})
        claimed = dict(product_values)
        if category is not None:
            claimed["category"] = category.pk
        if brand is not None:
            claimed["brand"] = brand.pk
        for field, value in claimed.items():
            claims[field] = (value, row_number)
        ids = self._products_by_key.setdefault(_key(product.name), [])
        if product.pk not in ids:
            ids.append(product.pk)
        if color_is_new:
            self._colors.append(color)
        return {
            "row": row_number,
            "action": action,
            "product_created": product_created,
            "product_name": product.name,
            "sku": variant.sku,
        }

    def _record_stock_movement(self, variant, old_stock: int, row_number: int):
        """Audit a stock change — after commit, so a dry run notifies no one."""
        new_stock = variant.stock
        actor = self.actor

        def record():
            StockMovement.objects.create(
                variant=variant,
                reason=StockMovement.Reason.MANUAL,
                quantity_delta=new_stock - old_stock,
                stock_after=new_stock,
                actor=actor,
                note=f"Bulk import (row {row_number})",
            )

        transaction.on_commit(record)


def run_import(rows, actor, dry_run: bool) -> dict:
    """
    Process every row; keep the result only if not a dry run.

    The SAME code runs for a dry run and a real import — a dry run just rolls
    the transaction back at the end — so a preview cannot drift from what a
    commit would do. The broad per-row `except` is deliberate: one row's
    unexpected failure must not abort the other rows.

    Why `atomic()` + `set_rollback(True)` rather than a manual
    `connection.savepoint()` / `savepoint_rollback()` pair: Django only
    tracks `transaction.on_commit()` callbacks against savepoints opened by
    `atomic()`. After a manual savepoint_rollback() the callbacks registered
    meanwhile (the price-drop notification fired by ProductVariant.save(),
    this module's stock audit) would survive and run when the outer
    transaction commits — a DRY RUN would then notify real subscribers about
    changes that never happened. Rolling back an `atomic()` block discards
    them. (Tested: TestBulkImportUpdates.)
    """
    results = {"succeeded": [], "errors": []}
    with transaction.atomic():
        importer = ProductImporter(actor=actor)
        for row_number, cells in rows:
            try:
                results["succeeded"].append(importer.process_row(row_number, cells))
            except RowError as exc:
                results["errors"].append({"row": row_number, "error": str(exc)})
            except Exception:  # noqa: BLE001 — collect per-row errors, keep going
                logger.exception("Bulk import: unexpected error on row %s", row_number)
                results["errors"].append(
                    {
                        "row": row_number,
                        "error": "Unexpected error while processing this row.",
                    }
                )
        if dry_run:
            transaction.set_rollback(True)
    return results


# ─── Template files ───────────────────────────────────────────────────────────

_NUMERIC_EXAMPLES = {
    "price",
    "original_price",
    "stock",
    "low_stock_threshold",
    "volume_ml",
    "weight_g",
    "spf",
}
_BOOL_EXAMPLES = {"is_active", *PRODUCT_BOOL_FIELDS}
_DATE_EXAMPLES = {"manufacture_date", "expiration_date"}


def build_template_csv() -> bytes:
    """Header + one example row, UTF-8 with BOM so Excel shows Persian text."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(IMPORT_COLUMN_NAMES)
    writer.writerow([c.example for c in IMPORT_COLUMNS])
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def build_template_xlsx() -> bytes:
    """
    Sheet 1 "products": header + typed example row (numbers/booleans/dates as
    real Excel cells, the way an admin's own sheet will have them).
    Sheet 2 "instructions": column / required / level / description. Only the
    first sheet is ever imported.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "products"
    sheet.append(IMPORT_COLUMN_NAMES)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    example = []
    for column in IMPORT_COLUMNS:
        text = column.example
        if text == "":
            example.append(None)
        elif column.name in _NUMERIC_EXAMPLES:
            example.append(int(text))
        elif column.name in _BOOL_EXAMPLES:
            example.append(text == "true")
        elif column.name in _DATE_EXAMPLES:
            example.append(date.fromisoformat(text))
        else:
            example.append(text)
    sheet.append(example)

    guide = workbook.create_sheet("instructions")
    guide.append(["column", "required", "applies_to", "description"])
    for cell in guide[1]:
        cell.font = Font(bold=True)
    for column in IMPORT_COLUMNS:
        guide.append(
            [
                column.name,
                "yes" if column.required else "no",
                column.level,
                column.description,
            ]
        )
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# ─── Export (the reverse of import) ───────────────────────────────────────────
#
# One row per VARIANT, in exactly the IMPORT_COLUMNS schema, with the parent
# product's attributes repeated on every one of its variant rows. Every row
# carries its SKU, so re-importing the file identifies each variant and
# UPDATES it — never creates a duplicate.

# openpyxl has to assemble the whole workbook before it can write the zip, so
# an .xlsx export is bounded by memory, unlike the streamed CSV. Write-only
# mode keeps the working set small, but the finished file is still built in
# memory — past this many variants the admin is pointed at the CSV export.
MAX_XLSX_EXPORT_ROWS = 20_000


def export_category_labels() -> dict:
    """
    {category_id: the text for the `category` column}.

    A category name that is unique is written as-is. One that exists under
    several parents is written as its full "Parent > Child" path — the
    importer rejects a bare ambiguous name, so a plain name here would break
    the round trip.
    """
    rows = list(Category.objects.values_list("id", "name", "parent_id"))
    by_id = {pk: (name, parent_id) for pk, name, parent_id in rows}
    name_counts = Counter(_key(name) for _, name, _ in rows)

    def path(pk) -> str:
        parts, seen = [], set()
        while pk is not None and pk in by_id and pk not in seen:
            seen.add(pk)
            name, parent_id = by_id[pk]
            parts.append(name)
            pk = parent_id
        return " > ".join(reversed(parts))

    return {
        pk: name if name_counts[_key(name)] == 1 else path(pk) for pk, name, _ in rows
    }


def export_row(variant, category_labels: dict) -> dict:
    """
    One variant as {column: typed value} for every IMPORT column (None = blank).

    Typed (ints, bools, dates) so the xlsx export can hold real Excel cells;
    csv_text() renders the same values the way a CSV cell is written.
    """
    product = variant.product
    color = variant.color
    return {
        "product_name": product.name,
        "category": category_labels.get(product.category_id),
        "brand": product.brand.name if product.brand_id else None,
        "sku": variant.sku,
        "color": color.name if color else None,
        "color_hex": color.hex_code if color else None,
        "price": variant.price,
        "original_price": variant.original_price,
        "stock": variant.stock,
        "low_stock_threshold": variant.low_stock_threshold,
        "volume_ml": variant.volume_ml,
        "weight_g": variant.weight_g,
        "barcode": variant.barcode,
        "manufacture_date": variant.manufacture_date,
        "expiration_date": variant.expiration_date,
        "batch_number": variant.batch_number,
        "is_active": variant.is_active,
        "skin_type": product.skin_type,
        "hair_type": product.hair_type,
        "gender": product.gender,
        "spf": product.spf,
        "is_cruelty_free": product.is_cruelty_free,
        "is_vegan": product.is_vegan,
        "is_organic": product.is_organic,
        "short_description": product.short_description,
        "description": product.description,
        "ingredients": product.ingredients,
        "usage_instructions": product.usage_instructions,
        "warnings": product.warnings,
        "country_of_origin": product.country_of_origin,
        "irc_regulatory_code": product.irc_regulatory_code,
    }


def csv_text(value) -> str:
    """A typed export value as the string a CSV cell holds (inverse of parsing)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def build_export_xlsx(rows) -> bytes:
    """
    A one-sheet workbook ("products") of export_row() dicts, as typed cells.

    Text that merely LOOKS like a formula ("=...") is stored as a string so
    Excel never evaluates it, and characters XML cannot hold are dropped
    (openpyxl would otherwise raise).
    """
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.styles import Font

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("products")
    header = []
    for name in IMPORT_COLUMN_NAMES:
        cell = WriteOnlyCell(sheet, value=name)
        cell.font = Font(bold=True)
        header.append(cell)
    sheet.append(header)
    for row in rows:
        cells = []
        for name in IMPORT_COLUMN_NAMES:
            value = row[name]
            if value is None or value == "":
                cells.append(None)
            elif isinstance(value, str):
                value = ILLEGAL_CHARACTERS_RE.sub("", value)
                cell = WriteOnlyCell(sheet, value=value)
                if value.startswith("="):
                    cell.data_type = "s"  # text, not a formula
                cells.append(cell)
            else:
                cells.append(value)
        sheet.append(cells)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
