# ADR 0002 — Slug strategy: Latin-script slugs for Persian-named catalog and blog content

| | |
|---|---|
| **Status** | **Proposed** (2026-11-09) — awaiting review; becomes binding on acceptance |
| **Date** | 2026-11-09 |
| **Epic / task** | Epic 14 — this decision -> Task 14.4.1.2 (implements it). Feeds Epic 15 (SEO) |
| **Scope** | `Product`, `Category`, `Brand` (`shop`) and, because it is the same bug, blog `Category` and `Post` (`blog`) |
| **Blocking open questions** | none. OQ-1 (quality gate) is answered *during* 14.4.1.2 with real catalog data; it does not block starting |

> **Numbering note.** The task brief places this "alongside Task 14.1.2.1's ADR (`0002-slug-strategy.md`)".
> In the tree this was written against, Task 14.1.2.1 is ADR **0001** (currency) and no `0002` exists, so this
> ADR takes `0002` at the path the brief names. If another `0002` exists on a branch that was not in the tree,
> renumber **before merge** (the README forbids renumbering after).

---

## 1. Context

### 1.1 The bug — confirmed, and worse than "garbage slugs"

`Product.save()`, `Category.save()`, `Brand.save()` (`shop/models.py`) and the blog `Category`/`Post` models
(`blog/models.py`) all do `if not self.slug: self.slug = slugify(self.name)` with Django's default
`slugify`, which is ASCII-only: it **deletes every non-ASCII character**.

Measured on 2026-11-09 against this codebase (Django 5.2.11, PostgreSQL 16), not assumed:

| Name | Current slug (`slugify`) |
|---|---|
| `سرم ویتامین سی` | `''` (empty) |
| `کرم مرطوب‌کننده روزانه` | `''` |
| `رژ لب مایع ۱۵۰ میلی‌لیتر` | `''` (Persian digits are dropped too) |
| `ماسک مو کراتین` | `''` |
| `سرم ویتامین C` | `'c'` |
| `ضدآفتاب بی‌رنگ SPF50+ مناسب پوست چرب` | `'spf50'` |
| `L'Oréal Paris کرم پودر مات` | `'loreal-paris'` (the product word is lost) |

5 of 8 realistic names yield an **empty** slug and the rest silently keep only their Latin fragment. What that
does in the database (reproduced in a rolled-back transaction):

* **Brand / Category:** the first Persian-named row gets slug `''`; the **second raises `IntegrityError`**
  (`shop_brand_slug_key` / `shop_category_slug_key`) — a 500 in admin. These two `save()`s have **no collision
  handling at all**.
* **Product:** five products produced `['', '-1', '-2', 'spf50', 'spf50-1']`. A product with slug `''` is
  **unreachable**: Django's `<slug:slug>` converter needs at least one character. `-1`/`-2` are routable but meaningless.
* Lossy-but-valid slugs (`c`, `spf50`) make whole product *families* collide (every sunscreen named "… SPF50+").

### 1.2 Other facts that constrain the decision

* **Slugs cannot be corrected by staff today.** `slug` is `read_only` in `AdminProductSerializer`,
  `AdminCategorySerializer`, `AdminBrandSerializer`, `BlogCategorySerializer` and `AdminPostSerializer` (`dashboard/serializers.py`) — i.e. for all five models.
* **Routing is ASCII-only.** There are **9** `<slug:slug>` path converters (6 in `shop/urls.py`, 3 in
  `blog/urls.py`); Django's converter regex is `[-a-zA-Z0-9_]+`. Model `SlugField` (default `allow_unicode=False`)
  also rejects non-ASCII. Five `SlugField`s: Category/Brand 220, Product 320, blog Category 120, Post 280.
* **Reserved path words.** `shop/urls.py` documents that `suggest` and `home-recommendations` "are valid slugs"
  and must stay *above* `products/<slug:slug>/`: a product whose slug equals one of them is shadowed by the route.
  Nothing prevents that today.
* **`normalize_persian_text` runs first and strips ZWNJ** (`shop/text_utils.py`; lossy by design, documented
  there). By the time `slugify` runs, `میلی‌لیتر` is already `میلیلیتر`, so the word boundary the slug needs is gone
  unless the slug is derived from the *raw* name.
* **Frontend** builds links as `` `/product/${slug}` `` (no encoding). **Sitemaps** exist
  (`shop/sitemaps.py`, `blog/sitemaps.py`) and are built from `slug`. Measured: a Persian slug is emitted as a
  **raw Unicode IRI** in `<loc>` (the sitemap protocol references RFC 3987, so this is not necessarily wrong, but no
  consumer was tested).
* **Epic 15 (SEO)** builds on these URLs next.
* The backend is already Persian-localized (`locale/fa`); any new user-facing validation message needs a `.po` entry.

### 1.3 What the candidate fixes actually produce — measured

`Django slugify(allow_unicode=True)` is option (b); the other rows are the common transliteration libraries
(`unidecode`, `anyascii`, `python-slugify`), i.e. option (a) done "the easy way":

| Name | (b) native Persian | `unidecode` | `anyascii` | `python-slugify` |
|---|---|---|---|---|
| `سرم ویتامین سی` | `سرم-ویتامین-سی` | `srm-wytmyn-sy` | `srm-wytmyn-sy` | `srm-wytmyn-sy` |
| `کرم مرطوب‌کننده روزانه` | `کرم-مرطوبکننده-روزانه` | `khrm-mrtwbkhnndh-rwznh` | `krm-mrtwbknndh-rwznh` | `khrm-mrtwbkhnndh-rwznh` |
| `رژ لب مایع ۱۵۰ میلی‌لیتر` | `رژ-لب-مایع-۱۵۰-میلیلیتر` | `rj-lb-my-150-mylylytr` | `rzh-lb-my-150-mylylytr` | `rj-lb-my-150-mylylytr` |

**Two consequences the task brief does not anticipate and this ADR must be honest about:**

1. **No character-level transliterator can produce `serum-vitamin-c`.** Persian does not write short vowels, so
   every library emits a consonant skeleton (`srm-wytmyn-sy`). Getting `serum-vitamin-c` needs *knowledge of the
   word* (a loanword/vocabulary lookup), not a better algorithm. The brief's example is therefore the target for
   the *glossary path* (D4), not something a library gives for free.
2. **The libraries disagree with each other** (`khrm`/`krm`, `rj`/`rzh`) — a dependency upgrade would silently change
   generated slugs.

The same table shows the cost of (b) in URL length: percent-encoded, `سرم-ویتامین-سی` is 14 characters in the
database and **74** on the wire (≈5×); `کرم-مرطوبکننده-روزانه` is 21 -> **116**.

## 2. Decision

**Slugs are Latin-script, ASCII-only (`^[a-z0-9]+(-[a-z0-9]+)*$`), and are produced by a staff-correctable,
vocabulary-aware transliteration — not by a bare library call.**

| # | Decision |
|---|----------|
| **D1** | Product, Category, Brand **and blog Category and Post** use ASCII Latin slugs. One URL language across the site; deciding per model would split it, and the blog has the identical bug. |
| **D2** | **Do not enable `allow_unicode`.** `SlugField`, DRF slug validation and all 9 `<slug:slug>` converters stay exactly as they are. (This is a major benefit of the decision: **zero routing change**.) |
| **D3** | Slug source, in order of precedence: **(1)** a slug supplied by staff (new — slug becomes writable in the admin API/forms, §7); **(2)** otherwise derived from the name by one shared function, `core.slugs.slugify_fa`, defined in D4. |
| **D4** | `slugify_fa(name) -> str` is a **deterministic, dependency-free** pipeline: normalise -> tokenise by script -> *glossary* for known Persian vocabulary -> *letter table* fallback for the rest -> join. Rules below. |
| **D5** | **Uniqueness** lives in one helper used by all five models (including Category/Brand, which have none today): suffix `-2`, `-3`, … (never `-1`), room reserved for the suffix, race-safe via the DB constraint + bounded retry. |
| **D6** | **Reserved words** (route segments such as `suggest`, `home-recommendations`) are treated as already taken for derived slugs and rejected (400) for staff-supplied ones. The list is derived from `urls.py` by a test, not hand-maintained. |
| **D7** | **A slug is generated once and never regenerated on rename** (today's behaviour, now an explicit invariant): published URLs get shared. |
| **D8** | **Existing rows:** a data migration regenerates only *invalid* slugs (`''`, `-1`, `-2`, …). Valid-but-lossy slugs (`c`, `spf50`) are **left alone** and surfaced by a report command for staff to decide. |

### D4 — the `slugify_fa` rules (normative)

1. **Canonicalise:** NFKC; map the Arabic variants `ك ي ى ۀ` to their Persian forms (reuse
   `shop/text_utils._CHAR_TRANSLATION_TABLE`); strip ZWSP/ZWJ/BOM. **Keep ZWNJ** — it becomes a word boundary (rule 3).
   Consequence for callers: **derive the slug from the raw name, before `normalize_persian_text` strips ZWNJ**
   (`raw = self.name` first in `save()`).
2. **Digits:** Persian (`۰-۹`) and Arabic-Indic (`٠-٩`) digits -> ASCII.
3. **Tokenise** on whitespace, **ZWNJ**, and any non-letter/digit; **delete** apostrophes/quotes (so `L'Oréal` is one token,
   not two); split glued tokens at Persian<->Latin/digit boundaries (`ویتامینC` -> `ویتامین`, `C`).
4. **Per token, by script:**
   * **Latin / digits:** keep verbatim, diacritics folded (NFKD -> ASCII), **case-folded to lower**. *This is the
     mixed-script requirement:* `C`, `SPF50`, `Oréal`, brand names embedded in Persian text are passed through,
     never routed into the Persian letter table.
   * **Persian:** (i) **glossary** lookup, **longest phrase first** (3 -> 2 -> 1 tokens); (ii) otherwise the
     **letter table** (fixed, ASCII-only, deterministic; one-way; every letter in the Persian alphabet plus the
     variants in rule 1 must be covered, enforced by test).
5. **Join** with `-`, collapse repeats, trim, and truncate at a hyphen boundary to `max_length - 8`.
6. **Nothing usable left** (punctuation/emoji only) -> the model prefix (`product`, `category`, `brand`, `post`),
   which D5 then makes unique (`product`, `product-2`). The function **never returns `''`**.

**The glossary** (`core/data/slug_glossary_fa.json`, reviewed in PRs like code) maps Persian-script **loanwords and
brand names to their conventional Latin spelling**: `سرم -> serum`, `ویتامین -> vitamin`, … It must support
**multi-word phrases**, because some Persian words are ambiguous alone: `سی` means both the letter *C* and the
number *thirty*, so it must be matched as the phrase `ویتامین سی -> vitamin-c`, never as a bare word. Words not in the
glossary fall through to the letter table; that output is deliberately a **safety net, not the quality path** — the
quality path is the glossary plus staff editing (D3).

#### Normative test corpus for Task 14.4.1.2

The tokenisation rules above were prototyped and these cases checked before being written down. *Group 1 must hold
with an **empty** glossary; group 2 with the seed glossary `{سرم: serum, ویتامین: vitamin, "ویتامین سی": vitamin-c}`.*

| # | Input | Required result |
|---|---|---|
| 1a | `سرم ویتامین C` (empty glossary) | non-empty ASCII slug whose **last token is exactly `c`** (prototype: `srm-vytamyn-c`) |
| 1b | `L'Oréal Paris` | exactly `loreal-paris` |
| 1c | `ضدآفتاب SPF50+` | ends with `-spf50` |
| 1d | `۱۵۰ ml` | exactly `150-ml` |
| 1e | `میلی‌لیتر` (with ZWNJ) | **identical** to the slug of `میلی لیتر` (with a space), containing exactly one hyphen |
| 1f | `ویتامینC` (glued) | token split at the script boundary (`…-c`) |
| 1g | `serum-vitamin-c` | unchanged (idempotent on valid slugs) |
| 1h | `!!! 😀` | the model prefix, never `''` |
| 1i | any input, incl. 400 × `ا` | matches `^[a-z0-9]+(-[a-z0-9]+)*$`, length ≤ `max_length` |
| 2a | `سرم ویتامین سی` | exactly `serum-vitamin-c` (phrase entry) |
| 2b | `سرم ویتامین C` | exactly `serum-vitamin-c` (mixed script) |
| 2c | 2a then 2b saved as two products | `serum-vitamin-c`, `serum-vitamin-c-2` |
| 3a | two Persian-named Brands, two Persian-named Categories | no `IntegrityError` (this is the reproduced crash) |
| 3b | derived slug equal to a reserved route word | suffixed (`suggest-2`), never shadowed |
| 3c | product renamed after creation | slug unchanged |

> **Case convention.** The brief says a literal Latin `C` "should stay as `C`". The Latin *letter* is preserved
> un-mangled, but slugs are lowercase (`c`): uppercase slugs make `/products/C/` and `/products/c/` two URLs.

## 3. Invariants (hard rules for Task 14.4.1.2 and later work)

* **I-1** Every stored slug matches `^[a-z0-9]+(-[a-z0-9]+)*$`. Enforced by a model validator **and** a DB `CheckConstraint`.
* **I-2** A slug is never `''`, never starts/ends with `-`, never equals a reserved route word.
* **I-3** One implementation: all five models call `core.slugs`; no model calls Django's `slugify` for slugs again
  (a guard test greps for it, in the spirit of the existing `rtl*` guard tests).
* **I-4** Slugs are write-once by the system (D7). Only a deliberate staff edit changes one.
* **I-5** No third-party transliteration dependency. The letter table is ours, covered by tests, and a library upgrade can never change a slug.
* **I-6** Slug derivation reads the **raw** name (ZWNJ intact), not the `normalize_persian_text` output.

## 4. Alternatives considered

### (b) Native Persian-script slugs (`allow_unicode=True`) — considered seriously, **not** dismissed

This is a legitimate, widely used choice, and it has the single strongest argument in this whole ADR:

* **It is lossless.** No vocabulary problem, no glossary to maintain, no skeleton slugs, no staff correction
  needed. `سرم-ویتامین-سی` is exactly the product name. Option (a) has a real quality weakness (§1.3) that (b) simply does not have.
* Fully valid (IRIs/percent-encoding) and increasingly well supported; Persian-language sites use it successfully
  (stated in the task brief; not surveyed here). Readable to a Persian user in the address bar and in results.

Its costs, in this codebase:

* **Sharing.** Wherever a URL is copied as raw text it can appear percent-encoded: measured 14 -> 74 and 21 -> 116 characters
  (≈5×). The "clean shareable URL" that slugs exist for is exactly what degrades (older chat apps, some social
  platforms, SMS gateways, plain-text mail — *reported behaviour; not tested here, no network access*).
* **SEO / analytics / ad-tracking tooling** has historically been rougher with non-ASCII URLs (*reported; not tested
  here*). This matters directly for Epic 15; (a) sidesteps the whole category.
* **Mixed-direction URLs.** A slug mixing Persian, Latin (`c`) and digits sits in an LTR URL context and can display
  in a visually confusing order in some UIs.
* **Engineering cost, measured:** 5 `SlugField` migrations (`allow_unicode=True`), replace 9 `<slug:slug>` converters
  (`<str:slug>` or a custom Unicode converter — and re-audit the route-ordering hazards they guard), DRF validators, and
  validate the sitemap output (raw IRIs today) for Epic 15. Digit/letter-variant canonicalisation (`۱۵۰` vs `150`,
  `ی` vs `ي`) is still required, so (b) is not free of normalisation work either.

**Why (a) wins anyway:** compatibility with the sharing and SEO-tooling surface the slugs are *for*, and no routing
change. **This is a close call, not a clear-cut one** — and it is only the right call if the quality of Latin slugs is
managed (D3/D4). If it is not, (b) is the better option. See OQ-1 for the measurable trigger.

### (a′) Library-only transliteration, no glossary, no staff editing — **rejected**
Produces `srm-wytmyn-sy` (§1.3): hard to read, poor for SEO, un-correctable (slugs are read-only today), and the
libraries disagree and can drift across upgrades. This is what "transliteration" would mean if implemented naively, and the brief's own
example (`serum-vitamin-c`) is unreachable this way.

### (c) ID-prefixed hybrid — `/product/123-serum-vitamin-c` — **not now; the designated fallback**
The id is authoritative, the slug cosmetic: no uniqueness problem, rename-safe, tolerant of low-quality slugs, and a
common pattern. Not chosen because it changes the URL scheme in the API (`lookup_field = "slug"`), the SPA routes,
the sitemap and every existing link. It is the cheapest hedge if the OQ-1 gate fails.

### (d) Opaque slugs (`p-8f3k2`) — **rejected**
Removes the readability/SEO value slugs exist to provide.

### (e) A dedicated `name_latin` / `name_en` field as the slug source — **deferred**
Likely the highest-quality source, but adds a content field and a staff workflow. D3 (editable slug) captures most
of the benefit with no schema change; revisit if OQ-1 fails.

## 5. Consequences

**Positive**
* Fixes the confirmed bug: no empty slugs, no `IntegrityError`, no unreachable products, no family-wide `spf50` collisions.
* **No routing, `SlugField`, serializer-validator or frontend-URL change** (D2). Sitemaps stay ASCII. Epic 15 is unblocked.
* Clean, shareable, bidi-safe URLs.

**Negative / costs**
* **Slug quality for words outside the glossary is mediocre** (`mrtvb-knndh`). Mitigated by the glossary and staff editing, not eliminated.
* A **glossary needs an owner** and review process (OQ-3).
* Staff UX changes: slug becomes visible and editable (§7).
* Transliteration is one-way (irrelevant for lookup; the name is the source of truth).
* A one-time data migration and a decision on redirects (OQ-2).

## 6. Open questions

| # | Question | Recommended default |
|---|---|---|
| **OQ-1** | **Quality gate.** What share of *real* catalog names fall through to the letter table? | 14.4.1.2 measures this on **real** product names (the QA seed is synthetic). If, after seeding the glossary, **≥ 30 %** of names still produce fallback-only slugs, stop and adopt (c) or (b) via a superseding ADR. The 30 % figure is a starting proposal for review, not a measured value |
| **OQ-2** | Redirects for changed or pre-existing bad slugs? | Old garbage slugs (`''` unreachable, `-1`) never worked -> no redirects. For future *staff edits* of a published slug, add a small `SlugRedirect` (old -> current) for Product and Post before Epic 15 indexing begins |
| **OQ-3** | Who owns the glossary, and where does it live? | A JSON file in the repo, changed by PR; product/content owner nominates terms, engineering reviews format. Add a startup test that it parses and has no duplicate keys |
| **OQ-4** | Confirm lowercase-only (the `C` -> `c` convention above). | Yes |
| **OQ-5** | Sitemap `location()` returns `/products/{slug}/` and `/category/{slug}/`, while the SPA routes are `/product/:slug`. Intentional (backend vs SPA host) or a mismatch? | Not a slug-strategy question; **flag for Epic 15** — verify before submitting sitemaps |
| **OQ-6** | Blog is included (D1) although the brief names only product/category/brand. Confirm. | Yes — same bug, same helper |

## 7. Everything affected (checklist for Task 14.4.1.2)

**Code**
* [ ] New `core/slugs.py`: `slugify_fa`, `unique_slug` (suffix from 2, truncation room, `IntegrityError` retry in `atomic`), reserved-word set.
* [ ] New `core/data/slug_glossary_fa.json` (seed: serum, vitamin, vitamin-c/e/d phrases, common cosmetic loanwords, top brands).
* [ ] `shop/models.py`: `Category.save` (l.58), `Brand.save` (l.78), `Product.save` (l.285) — capture `raw_name` **before** `normalize_persian_text`; call `core.slugs`; remove the inline counter loop.
* [ ] `blog/models.py`: `Category.save` (l.17), `Post.save` (l.69), same change.
* [ ] `shop/management/commands/seed_shop.py` (l.183/189/201) — already stale (FUNC-04); fix or delete, but do not leave a third `slugify` call site.
* [ ] `dashboard/serializers.py`: make `slug` **writable** in `AdminProductSerializer` (l.475), `AdminCategorySerializer` (l.518), `AdminBrandSerializer` (l.542), `BlogCategorySerializer` (l.692) and `AdminPostSerializer` (l.701+); validate ASCII/regex/reserved/uniqueness -> field-level 400. New messages go through `_()` and `locale/fa`.
* [ ] Admin frontend (`AdminProducts`, `AdminCategories`, `AdminBrands`, `AdminBlog` forms): a slug input pre-filled with the server-suggested value (a small preview endpoint is recommended so the glossary exists in one place).

**Database**
* [ ] Data migration: regenerate rows whose slug fails I-1 (`''`, `-1`, `-2`, …); idempotent; reversible no-op.
* [ ] `CheckConstraint` for I-1 (after the data migration); model validator.
* [ ] Management command `regenerate_slugs --dry-run [--only-invalid]` + a report of valid-but-lossy slugs for staff review.

**Tests** (the corpus in §2 plus)
* [ ] Reproduce-the-bug regression: two Persian Brands, two Persian Categories, five Persian Products — no error, unique valid slugs.
* [ ] Reserved words derived from `shop/urls.py`/`blog/urls.py`, not hand-copied.
* [ ] Letter table covers the full alphabet and every variant from rule 1.
* [ ] Guard test: no `django.utils.text.slugify` import in `shop/models.py` / `blog/models.py` (I-3).
* [ ] Slug survives rename (D7); ZWNJ name yields the hyphenated slug (I-6).

**Explicitly unchanged:** the 9 `<slug:slug>` converters, all `SlugField(allow_unicode=False)` definitions, frontend `/product/${slug}` links, sitemap code.

## 8. Evidence and limits

Measured here: current `slugify` behaviour, the `IntegrityError`s and slug sequences, converter/validator regexes,
library outputs, encoded lengths, sitemap output, the read-only serializer fields, and the internal consistency of
the D4 rules (prototype, not committed). **Not** verified here (no network access): how specific third-party chat apps,
social platforms, SMS gateways, SEO and ad-tracking tools actually treat percent-encoded Persian URLs — those points
rest on the task brief and general experience and are labelled "reported". The Persian **letter table**
and **glossary contents** are intentionally left to Task 14.4.1.2; this ADR fixes their constraints and tests, not their entries.

## 9. Implementation notes (Task 14.4.1.2) — where the build differs from §2/§7

The decision (Latin ASCII slugs, no `allow_unicode`, no routing change) is implemented as written. These details
were settled by the implementation task and **supersede** the corresponding wording above:

| Topic | ADR text | As built |
|---|---|---|
| Location | `core/slugs.py`, glossary in `core/data/*.json` | `shop/text_utils.py` (extends Epic 12's Persian text module); glossary is the `LOANWORD_GLOSSARY` dict in that module, reviewed in PRs |
| Collision suffix (D5) | `-2`, `-3` … (never `-1`) | **`-1`, `-2` …**: Product's existing loop is kept verbatim; `unique_slug()` applies the same pattern to Category, Brand and the blog models, which had no loop |
| Underscores (I-1 regex) | `^[a-z0-9]+(-[a-z0-9]+)*$` | underscores are preserved inside words (Django `slugify` parity); the DB `CheckConstraint` in §7 must allow `_` if it is ever added |
| Punctuation | not specified | `' ’ ʼ `` ` and `.` are deleted (so `L'Oréal` is one word); every other non-letter/digit is a separator |
| Letter table | "left to 14.4.1.2" | ASCII table + 4 positional rules (و, ی, ه, ع) chosen for readability: `پوست -> pust`, `ویتامین -> vitamin`, `روزانه -> ruzane` |
| Library vs table | I-5: own table | confirmed by evaluation (recorded in the `text_utils.py` header): `trans` broken, `transliterate` no Persian, ICU needs a C build and leaves ا/آ untransliterated, generic libraries disagree and drop ع |
| Fallbacks | model prefix | `product`, `category`, `brand`, `post` (then the usual `-N` suffix) |
| Length | truncate at word boundary | base is cut to `max_length - 8`, leaving room for the suffix |
| Existing data (D8) | regenerate only *invalid* slugs, leave valid-but-lossy | **regenerates every slug the old generator produced from an Arabic-script name**, including valid-but-lossy ones (`c`, `spf50`), as the task required. Hand-set slugs and Latin-named rows are never touched. **No redirects** are created (OQ-2 stays open); URLs such as `/product/spf50` change |
| ZWNJ for existing rows | — | stored names already lost ZWNJ at save time, so existing rows get glued words (`cream-mrtubknnde`); only rows created from now on get `mrtub-knnde` |

**Still open from the §7 checklist** (not part of 14.4.1.2): slug writable in the admin API/forms (D3 step 1),
reserved-word protection (D6), the `CheckConstraint` (I-1), a `regenerate_slugs` management command, redirects (OQ-2),
OQ-1's real-catalog quality measurement. Until D3 step 1 lands, a poor auto-generated slug cannot be corrected by staff.
