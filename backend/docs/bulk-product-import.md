# Bulk product + variant import

Admin tool: `POST /api/dashboard/admin/products/bulk-import/` (multipart:
`file`, `dry_run`). Download a ready-made file from
`GET /api/dashboard/admin/products/import-template/?file_type=csv|xlsx`.

The schema lives in code — `IMPORT_COLUMNS` in
`backend/dashboard/product_import.py` — and the template, the parser's header
check and this document are all tested against it.

## How it behaves

* **`dry_run` defaults to true**: the run is fully executed and then rolled
  back, so the preview (counts, row errors, generated SKUs) is exactly what a
  real import would do. Send `dry_run=false` to keep the result.
* **Per row, not all-or-nothing**: a bad row is reported with its spreadsheet
  row number (header = row 1) and skipped; every valid row still goes through.
  Each row is atomic on its own — no half-created products.
* **One row = one variant.** Rows with the same `product_name` are variants
  of one product.
* Limits: `.csv` (UTF-8; `,` `;` or tab) or `.xlsx` (first sheet only),
  at most 5 MB and 1,000 data rows per file. Excel's "CSV UTF-8" works.

## Columns

Required: `product_name`, `category`, `price` must exist as columns. A cell
is only mandatory when the row *creates* something (`category` for a new
product, `price` for a new variant); on updates a blank cell means "leave
unchanged" (so an import can set or change a value but never clear one).

| Column | Required | Applies to | Notes |
|---|---|---|---|
| `product_name` | yes | product | Identity of the product. |
| `category` | yes | product | Must exist (name, or `Parent > Child`). Unknown = row error, never auto-created. |
| `brand` | no | product | Must exist. Unknown = row error. |
| `sku` | no | variant | Blank: match by product + color + volume/weight, else auto-generate. Given: match that SKU (its product must be `product_name`), else create with it. |
| `color` | no | variant | Created if new — but then `color_hex` is required. |
| `color_hex` | no | variant | `#RRGGBB`. |
| `price` | yes | variant | Integer **Rial**, a multiple of 10 (not Toman). |
| `original_price` | no | variant | Compare-at price, Rial. |
| `stock` | no | variant | Whole number. Changing it on an existing variant records a stock movement. |
| `low_stock_threshold` | no | variant | Default 5. |
| `volume_ml` | no | variant | |
| `weight_g` | no | variant | |
| `barcode` | no | variant | EAN-13 with valid check digit. |
| `manufacture_date` | no | variant | Gregorian `YYYY-MM-DD`. |
| `expiration_date` | no | variant | Gregorian; after `manufacture_date`. |
| `batch_number` | no | variant | |
| `is_active` | no | variant | true/false. |
| `skin_type` | no | product | oily, dry, combination, sensitive, normal, all. |
| `hair_type` | no | product | straight, wavy, curly, coily, all. |
| `gender` | no | product | unisex (default), female, male. |
| `spf` | no | product | 0–100. |
| `is_cruelty_free` | no | product | true/false. |
| `is_vegan` | no | product | true/false. |
| `is_organic` | no | product | true/false. |
| `short_description` | no | product | Max 500 characters. |
| `description` | no | product | |
| `ingredients` | no | product | Raw INCI list. |
| `usage_instructions` | no | product | |
| `warnings` | no | product | |
| `country_of_origin` | no | product | |
| `irc_regulatory_code` | no | product | Stored as typed; never marked verified. |

Product-level columns describe the formulation: put them on a product's first
row or repeat them identically — a conflicting value on a later row is an
error for that row.

Not importable, deliberately: `regulatory_verified` (a staff verification),
images, ratings, `is_new`/`is_sale`.

## Matching (create vs update)

* With `sku`: that variant is updated; if the SKU is new, a variant with that
  exact SKU is created.
* Without `sku`: within the named product, a variant with the same
  (`color`, `volume_ml`, `weight_g`) is updated — blank means "none" — otherwise a new variant
  is created. Re-importing a sheet is therefore idempotent.
* The same variant twice in one file is an error on the second occurrence.
* Names match ignoring case and Persian/Arabic character variants
  (`ك`/`ک`, `ي`/`ی`). Persian digits and thousands separators are accepted in
  numbers.
* Dates must be Gregorian: a year before 1900 is rejected (it is almost
  certainly a Jalali date).

## Exporting the catalog (and the round trip)

`GET /api/dashboard/admin/products/bulk-export/?format=csv|xlsx` (default
CSV; `?file_type=` is accepted too) downloads the catalog in **exactly the
import schema above** — one row per variant, each with its `sku`, the parent
product's shared attributes repeated on every row. Re-importing the file
therefore *updates* every variant it contains and creates nothing:
export → edit in Excel → re-import is a supported round-trip workflow (and
the test suite proves an unedited export re-imports with zero errors and
changes nothing).

Filters: `category`, `brand`, `is_sale`, `is_new` and `search` behave as on
the admin product list. `min_price`, `max_price` and `in_stock` are applied to
the **variants** (the admin product list's versions look at the legacy
`Product.price` / `Product.stock` fields, which are no longer the real data).
A malformed filter is a 400, never an unfiltered export. Inactive variants are
included.

Details worth knowing:

* CSV is streamed (UTF-8 with BOM, so Excel shows Persian correctly). Cells
  starting with `=`, `+`, `-` or `@` get a leading `'` so spreadsheet apps
  don't execute them; the importer removes that `'` again on CSV import.
* XLSX holds real typed cells (numbers, booleans, dates); text that looks
  like a formula is stored as text. It is built in memory, so it is limited
  to 20,000 variants — use CSV (or filters) beyond that.
* A category name that exists under several parents is exported as its full
  `Parent > Child` path so the importer can resolve it.
* The importer accepts at most 1,000 rows per file: filter a larger export
  into pieces before re-importing it.
