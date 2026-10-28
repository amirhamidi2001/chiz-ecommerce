# ADR 0001 — Currency storage: whole-Toman amounts held as integer Rial

| | |
|---|---|
| **Status** | **Accepted** (2026-10-23) — implemented by Task 14.1.2.2; see §15 |
| **Date** | 2026-10-20 |
| **Epic / task** | Epic 14, Task 14.1.2.1 (this decision) -> 14.1.2.2 (migration that implements it) |
| **Scope** | Every monetary value in `backend/` and the SPA that consumes it |
| **Blocking open questions** | none — OQ-1 resolved, see §15 |

---

## 1. Context

Every monetary field built through Epic 13 is `DecimalField(max_digits=N, decimal_places=2)`:
a USD-shaped template with no real currency semantics. Iran's currency has two everyday
units: the **Rial** (ISO 4217 `IRR`, official, no practical fractional subunit) and the
**Toman** (colloquial; **1 Toman = 10 Rial**), which is what customers read and think in.

Facts established from the codebase (not assumed):

* All three payment-gateway adapters already send **integer Rial** and say so in their own
  docstrings (`payments/gateways/zarinpal.py`, `zibal.py`, `idpay.py` — each does
  `"amount": int(amount)`). ZarinPal's note records that its *dashboard* shows Toman while
  its *API* expects Rial and that mixing them up "under- or over-charges customers".
* AloPeyk quotes prices in **Toman** (`shipping/providers/alopeyk.py`, SDK comment, lines
  ~55 and ~118); SnapBox's `totalFare` unit is **not stated** (`snapbox.py` ~67–69, ~403).
  Both providers' docstrings flag the need to reconcile with the Rial-based gateways.
* The frontend has **no shared currency formatter**: about 25 non-test files each carry their own
  `$${n.toFixed(2)}` / `Intl.NumberFormat('en-US', {currency:'USD'})` (see §8.5), and
  `Checkout.jsx` re-implements the pricing formula in floating point
  (`const TAX_RATE = 0.10; const tax = subtotal * TAX_RATE;`).
* `REST_FRAMEWORK` sets no decimal options, so DRF currently serialises every money value
  as a **string** (`"25.00"`).
* **External event — currency redenomination (see §9).** Iran has legislated removing four
  zeros from the currency. This does not change the decision below, but it makes the choice
  of storage unit more important and the *display* unit something to isolate carefully.

## 2. Decision

| # | Decision |
|---|----------|
| **D1** | **Store** every monetary amount as an **integer number of Rial** (legacy IRR). No decimals, no floats, ever. |
| **D2** | Column type: **`PositiveBigIntegerField`** for *every* money field. Not `PositiveIntegerField` (see §4). No field needs a negative value (§4), so no plain `BigIntegerField`. |
| **D3** | **Granularity is whole Toman:** every stored/transmitted amount is a **multiple of 10 Rial**. Enforced by one rounding helper, a serializer validator and a DB `CheckConstraint` (§5). |
| **D4** | The **API exposes Rial** as JSON integers — single source of truth, unit-explicit. It never returns Toman. |
| **D5** | **Display unit is Toman**, computed at the presentation layer only (`rial // 10`, exact by D3), in **one** shared frontend utility. Server-rendered output (PDF invoice, emails) uses one small Python counterpart, not ad-hoc formatting. |
| **D6** | **Percentages are not money.** They stay `DecimalField(max_digits=5, decimal_places=2)`. `Coupon.value`, which today mixes both meanings in one column, is **split** (§7). |
| **D7** | A marker field `core.fields.RialField(PositiveBigIntegerField)` makes the money-field set machine-checkable (registry test, §7.4). *Recommended*; plain `PositiveBigIntegerField` + the same constraints is an acceptable fallback if rejected in review. |
| **D8** | Unit conversion happens only at **system boundaries**: carrier adapters (AloPeyk: x10), the SPA input/output util, and Python render helpers. Gateways receive the stored integer unchanged. |

## 3. Invariants (hard rules for Task 14.1.2.2 and all later work)

* **I-1** Money is a Python `int` of Rial everywhere — models, services, serializers, tasks,
  JSON. Never `Decimal`, `float`, or `str` for a money amount.
* **I-2** Every money amount is a **multiple of 10** (whole Toman). Violations are bugs,
  rejected on input (400) and by the database.
* **I-3** Any calculation that can yield a non-multiple of 10 (tax, percentage coupon,
  flash-sale price, any future proration) rounds **at that step, once, through
  `core.money.to_whole_toman_rial`**. A fractional intermediate is never carried into the
  next step.
* **I-4** The identity `total = subtotal + shipping_cost + tax - discount` holds **exactly**
  on stored values, and displayed components always sum to the displayed total.
* **I-5** Rial<->Toman conversion exists in exactly two code locations: `frontend/src/utils/money.js`
  and `backend/core/money.py`. Nowhere else may multiply or divide by 10 for currency.
* **I-6** Percent values never touch the money type: `Decimal` in, `to_whole_toman_rial(...)` out.
* **I-7** Gateway amounts equal the stored `amount` byte-for-byte (no conversion, no `int()` coercion).
* **I-8** Every surface where a human *types* a price states its unit; API write endpoints
  accept Rial only.
* **I-9** Every stored/transmitted amount is `<= MAX_RIAL_AMOUNT = 10**11` (see §4).

## 4. Data type and sizing

* **Why integer, not `Decimal(decimal_places=0)`:** Rial has no practical subunit, so
  `decimal_places=2` was always semantically wrong; and `Decimal` keeps the door open to
  fractional arithmetic, string serialisation, and `float()` leaks (the dashboard already
  does `float(total_spent)`). An `int` makes I-1 a type, not a convention.
* **Why `BigInteger`:** `PositiveIntegerField` is a Postgres `integer` (max **2,147,483,647
  Rial = 214,748,364 Toman**). A single order of ten 25M-Toman items already needs
  2.5 billion Rial. `bigint` tops out at 9.22 x 10^18.
* **Why cap at `10**11` Rial (10 billion Toman):** the binding limit is the **browser**, not
  Postgres — JS integers are exact only to 2^53-1 = 9.007 x 10^15. With a 10^11 cap, even
  `amount * 10_000` (basis-point math in the SPA) stays below that. Aggregates (revenue sums)
  are computed in Postgres and are nowhere near the limit. Enforced via `RialField` validators.
* **Why `Positive` for every field (the per-field decision):** no field stores a signed
  amount. `Order.discount` is a positive subtrahend; refunds are separate
  `RefundRequest.amount` rows (positive); `StockMovement` quantities are not money. If a
  signed ledger is ever added, that single field may use `BigIntegerField` by amendment.
  `0` is valid for `Positive*` (`Order.discount`, `min_order_amount`, free shipping).

Empirically verified on this repo's stack (Postgres 16, Django 5.2.11): `Sum()` over a
`PositiveBigIntegerField` returns a Python `int` even past int32, `Coalesce(Sum(...), 0)`
works, and **`Avg()` returns a `float`** — any average (e.g. average order value) must be
explicitly rounded through the helper.

## 5. Rounding rule

**Rule:** round to the **nearest whole Toman (nearest multiple of 10 Rial), ties up
(`ROUND_HALF_UP`)**, at every step, in one helper. A non-multiple of 10 reaching storage or
the display layer is a **bug prevented upstream**, never papered over.

> **Correction to the original framing of this task.** "Round to whole Rial at each step" does
> **not** make Toman division clean — whole Rial is not whole Toman. Example: subtotal
> 1,234,560 Rial, 10% tax = 123,456 Rial = **12,345.6 Toman**. Only rounding to a multiple of
> 10 Rial makes `rial // 10` exact. Python's current `Decimal.quantize` also defaults to
> `ROUND_HALF_EVEN`; the rule above makes the mode explicit.

Why whole-Toman granularity rather than whole-Rial plus rounding at display: it guarantees I-4
(on screen, subtotal + shipping + tax - discount equals the total to the digit) and it is the
granularity customers and prices already live at.

```python
# backend/core/money.py  (reference implementation — 14.1.2.2 creates this module)
from decimal import Decimal, ROUND_HALF_UP

RIAL_PER_TOMAN = 10
MAX_RIAL_AMOUNT = 10**11

def to_whole_toman_rial(value) -> int:
    """Round any exact Rial value (int/Decimal) to the nearest multiple of 10, ties up."""
    tomans = (Decimal(value) / RIAL_PER_TOMAN).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(tomans) * RIAL_PER_TOMAN

def percent_of(amount_rial: int, percent: Decimal) -> int:
    return to_whole_toman_rial(Decimal(amount_rial) * percent / Decimal(100))

def rial_to_toman(rial: int) -> int:
    assert rial % RIAL_PER_TOMAN == 0, "invariant I-2 violated"
    return rial // RIAL_PER_TOMAN

def toman_to_rial(toman: int) -> int:
    return toman * RIAL_PER_TOMAN
```

**Golden vectors** (must pass identically in Python and JS tests):

| input (Rial) | `to_whole_toman_rial` |
|---:|---:|
| 0 | 0 |
| 4 | 0 |
| 5 | 10 |
| 14 | 10 |
| 15 | 20 |
| 125 | 130 |
| 123 456 | 123 460 |
| 185 184 | 185 180 |

Worked checkout: subtotal 1,234,560; shipping 500,000; tax = `percent_of(subtotal, 10)` =
123,460; discount 0 -> total 1,858,020 (= 185,802 Toman, exact). A 15% coupon on the same
subtotal = `percent_of(1_234_560, 15)` = 185,180 (exact value 185,184), capped by existing
logic at the eligible subtotal.

**The formula itself is unchanged** (`tax` on `subtotal`, then `total`); only the arithmetic
type and rounding change. Whether `TAX_RATE = 10%` and its base are correct for Iranian VAT is
a separate, pre-existing question from the USD template (OQ-4).

## 6. Display rule (presentation layer only)

* `toman = rial / 10` (exact by I-2). Group thousands. Unit label after the number.
* **Default: Western digits with the Persian unit label** — `formatToman(299900)` ->
  `29,990 تومان`. **Digit script and unit label are independent options** of the one util:
  `persianDigits` picks the digit script (default taken from the **price** context in
  `frontend/src/constants/numerals.js`, i.e. Western) and `unit` picks the label (`'fa'` ->
  `تومان` default; `'en'` -> `Toman`). `persianDigits: true` runs `toPersianDigits()` over the
  finished string (`۲۹,۹۹۰ تومان`; the thousands separator stays `,`). There is deliberately no
  `locale` option: `Intl`'s own `fa-IR` output uses a different separator (`٬`), and two routes to
  "Persian digits" would drift (OQ-2, resolved by Tasks 14.1.2.3 / 14.1.2.4).
* **Digit script is a per-context decision, not a global switch** (Task 14.1.2.4): prices stay
  Western (exact amounts read clearest and match invoices, bank and gateway); product ratings and
  review counts are Persian. The table lives in one place (`constants/numerals.js`) and anything
  unlisted falls back to Western. Admin pages and the account dashboard stat tiles are Western by
  decision. Jalali dates will get their own context row when Feature 14.2.1 lands.
* Empty state: `null` / `undefined` / `''` / `NaN` / `Infinity` / non-numeric text render `—`;
  the formatter never throws on them and never prints `NaN`. `-0` renders `0`. A negative amount
  keeps its sign (`formatToman(-50000)` -> `-5,000 تومان`).
* Rendering vectors:

| Rial | default | `persianDigits: true` | `unit: 'en'` |
|---:|---|---|---|
| 0 | `0 تومان` | `۰ تومان` | `0 Toman` |
| 10 | `1 تومان` | `۱ تومان` | `1 Toman` |
| 299 900 | `29,990 تومان` | `۲۹,۹۹۰ تومان` | `29,990 Toman` |
| 1 250 000 | `125,000 تومان` | `۱۲۵,۰۰۰ تومان` | `125,000 Toman` |
| -50 000 | `-5,000 تومان` | | `-5,000 Toman` |

* **Invariant-violation behaviour:** in development/test the util **throws**; in production it
  falls back to `Math.ceil(rial / 10)` (never display *less* than will be charged) **and reports
  the error loudly**. It must never silently normalise. For a *negative* amount "never less"
  means rounding **away from zero** (a refund line must not shrink). Flooring (`Math.floor`) was
  considered and rejected: 123,456 Rial is 12,345.6 Toman, so flooring would show 12,345 while the
  gateway charges 12,345.6.
* Frontend API (`frontend/src/utils/money.js`): `rialToToman`, `tomanToRial`, `formatToman(rial,
  {locale, withUnit})`, and — only while client-side math survives — `roundToWholeToman`
  implemented with **integer arithmetic only** (never `x * 0.1`):

  ```js
  // value = num/den Rial, rounded to a multiple of 10, ties up
  export const roundToWholeToman = (num, den = 1) =>
    Math.floor((2 * num + 10 * den) / (20 * den)) * 10;
  // tax 10% = 1000 basis points: roundToWholeToman(subtotal * 1000, 10000)
  ```

* **Server-rendered output** (WeasyPrint invoice `order/templates/order/invoice.html`, currently
  `floatformat:2`; email bodies) uses a `core.money` template filter so Python never formats
  ad hoc. Invoice denomination is OQ-3.
* **Input surfaces:** the SPA admin forms let staff type **Toman** and submit `tomanToRial(x)`;
  Django admin edits Rial directly, so its field help-text must say "Rial (multiple of 10)".

## 7. Enumeration — what this decision changes

Compiled by grepping the whole backend for `DecimalField` (models **and** serializers),
`Decimal(`, `quantize`, `float(`, aggregates, filters, templates, gateways and carrier
adapters, then confirming each by reading it. **This is Task 14.1.2.2's checklist.**

### 7.1 Model fields -> `RialField` (17)

| # | Model.field | Today | Notes |
|--:|---|---|---|
| 1 | `order.Order.subtotal` | Decimal(12,2) | |
| 2 | `order.Order.shipping_cost` | Decimal(8,2) | |
| 3 | `order.Order.tax` | Decimal(10,2) | rounded per §5 |
| 4 | `order.Order.discount` | Decimal(10,2), default 0 | `default=0` retained |
| 5 | `order.Order.total` | Decimal(12,2) | |
| 6 | `order.OrderItem.unit_price` | Decimal(10,2), `MinValue(0)` | historical snapshot — drop the `MinValueValidator` (positive type covers it) |
| 7 | `shipping.ShippingRate.price` | Decimal(10,2) | |
| 8 | `promotions.Coupon.min_order_amount` | Decimal(10,2), default 0 | |
| 9 | `promotions.Coupon.value` -> **split** | Decimal(10,2) | see §7.3 |
| 10 | `promotions.CouponRedemption.discount_amount` | Decimal(10,2) | |
| 11 | `shop.Product.price` | Decimal(10,2) | legacy product-level mirror; still filtered on |
| 12 | `shop.Product.original_price` | Decimal(10,2), null | stays nullable |
| 13 | `shop.ProductVariant.price` | Decimal(10,2) | authoritative price |
| 14 | `shop.ProductVariant.original_price` | Decimal(10,2), null | stays nullable |
| 15 | `shop.ProductPriceSnapshot.price` | Decimal(10,2) | |
| 16 | `payments.PaymentTransaction.amount` | Decimal(12,2) | gateway amount |
| 17 | `payments.RefundRequest.amount` | Decimal(12,2) | |

(Row 9 yields one new `RialField` — `fixed_amount` — so 17 rows = 17 money columns after the split.)

### 7.2 `DecimalField`s that are **deliberately NOT converted**

| Field | Why it stays |
|---|---|
| `shop.Product.rating` Decimal(3,1) | A star rating, not currency |
| `promotions.FlashSale.discount_percent` Decimal(5,2) | A percentage (validators 0.01–100) |
| `promotions.Coupon` percent branch -> new `percent_off` Decimal(5,2) | A percentage; mirrors the `FlashSale` precedent |

No other model in any app (`accounts`, `blog`, `cart`, `chat`, `contact`, `dashboard`,
`shipping.Shipment`, `payments.PaymentGatewayConfig`/`PaymentAdminOverride`, ...) holds money;
verified by grep for non-`Decimal` money-named fields as well — none exist.

### 7.3 `Coupon.value` — the one decision that is not mechanical

`Coupon.value` is a percentage when `discount_type == "percent"` and a currency amount when
`"fixed"`. One column cannot be both an integer Rial amount and a 2-decimal percentage without
reintroducing exactly the unit ambiguity this ADR removes.

**Decision:** replace it with two explicit columns, keep `discount_type`:

* `percent_off` — `DecimalField(5, 2, null=True)`
* `fixed_amount` — `RialField(null=True)`
* DB constraints: `percent` => `0 < percent_off <= 100` and `fixed_amount IS NULL`;
  `fixed` => `fixed_amount > 0` and `percent_off IS NULL`. `Coupon.clean()` mirrors them.
* API (`promotions/serializers.py`, `dashboard` coupon serializers) and `frontend/src/utils/coupon.js`
  + admin coupon UI switch from `value` to the two fields. The apply-coupon response's
  `discount_amount` becomes an int (`cart/views.py:223` currently does `str(...)`).

Rejected: keeping one integer `value` with percent stored in basis points (still a dual-unit
column); leaving `value` as `Decimal` (leaves fixed money in Decimal, violating I-1).

### 7.4 Making this list self-verifying (D7)

Task 14.1.2.2 adds a test that walks the app registry and asserts: (a) the set of
`RialField`s equals §7.1; (b) the only remaining `DecimalField`s in the project are exactly the
three rows of §7.2; (c) every `RialField` has the `x % 10 = 0` check constraint. A forgotten
field then fails CI instead of surfacing mid-migration.

DB constraint form, verified on Postgres 16 / Django 5.2.11 (rejects `1_250_005` with
`IntegrityError`):

```python
models.CheckConstraint(condition=Exact(Mod("price", 10), 0), name="<model>_<field>_whole_toman")
```

### 7.5 Backend code that does money arithmetic, formatting or typing (not fields)

| Site | Change |
|---|---|
| `order/services/pricing.py` | `Decimal` -> `int`; delete `TWO_PLACES`; `tax = percent_of(subtotal, TAX_RATE_PERCENT)`; `PricingError` checks unchanged; `TAX_RATE` constant becomes a `Decimal` *percent* (e.g. `Decimal("10")`), not a multiplier |
| `promotions/services.py` (`validate_coupon`, ~l.141, 164–170) | `Decimal("0")` start -> `0`; percent via `percent_of`; fixed via `min(coupon.fixed_amount, eligible_subtotal)`; `CouponValidationResult.discount_amount: int` |
| `promotions/models.py` | `Coupon.clean()` per §7.3; default `Decimal("0")` -> `0` |
| `shop/models.py` `discounted_price()` (l.19–22) | `(price * multiplier).quantize(0.01)` -> `percent_of(price, 100 - sale.discount_percent)` |
| `shop/models.py` `FlashSaleCardPricing`, `lowest_active_price`, `effective_price` | type hints Decimal -> int |
| `shop/models.py` `discount_percent` property (l.~396) | derived ratio, unit-independent; keep, but it must stay an integer percent |
| `order/serializers.py` (l.~407, ~499) | `Decimal("0")` accumulators -> `0` |
| `cart/models.py`, `cart/serializers.py` | `Cart.subtotal`/`CartItem.subtotal` are `sum()` of ints — verify `sum(..., 0)`; serializer fields below |
| `cart/views.py:223` | `str(result.discount_amount)` -> int |
| `shop/signals.py` (price-change compare) | compares `previous.price != instance.price`; fine for ints |
| `shop/tasks.py:83–123` | `notify_price_drop_subscribers` documents `old_price`/`new_price` as **decimal strings** — now ints |
| `dashboard/services.py` l.51, 54, 89, 139, 160–161, 236–252 | `Coalesce(Sum(...), Decimal("0"))` -> `0`; `Sum(F("unit_price") * F("quantity"), output_field=DecimalField())` -> `BigIntegerField()`; **remove `float(...)`** (`total_spent`); any `Avg` of money goes through the helper |
| `dashboard/serializers.py` (`get_total_spent`, `subtotal` l.225) | int |
| `dashboard/filters.py` l.24–25, 58–59; `shop/filters.py` l.10–11 | `min_total/max_total/min_price/max_price` `NumberFilter`s now take **Rial**; SPA price sliders must convert Toman->Rial |
| `order/templates/order/invoice.html` l.86–98 | `floatformat:2` -> `core.money` filter |
| `shop/management/commands/seed_shop.py` | re-author prices as realistic Rial multiples of 10 |
| `core/settings` | no decimal settings exist; none to remove. API now emits JSON numbers for money |

### 7.6 Serializer declarations (explicit `DecimalField`s)

| File:line | Field | Action |
|---|---|---|
| `order/serializers.py:28` | `subtotal` | `IntegerField(read_only=True)` |
| `cart/serializers.py:48,49,59,62,120` | `price`, `original_price`, `unit_price`, `subtotal` x2 | `IntegerField` |
| `shop/serializers.py:70–72` | `_money()` helper ("format like every other DecimalField") | delete helper; return ints |
| `shop/serializers.py:82` | `effective_price` | `IntegerField(read_only=True)` |
| `shop/serializers.py:361` | `flash_sale_discount_percent` (5,2) | **keep** — percentage |
| `payments/serializers.py:38` | `amount` | `IntegerField` |
| `dashboard/serializers.py:225` | `subtotal` | `IntegerField(read_only=True)` |

All `ModelSerializer`-generated money fields change automatically to integers. Write
serializers that accept money (`AdminProduct*`, coupon, shipping-rate admin) add
`validate_whole_toman` and the `MAX_RIAL_AMOUNT` bound.

### 7.7 External boundaries

| Boundary | Today | Required |
|---|---|---|
| ZarinPal / Zibal / IDPay (`payments/gateways/*.py`) | take `Decimal`, send `int(amount)` Rial | signature `amount: int`; drop `int()` coercion; **I-7** |
| `shipping/providers/base.py:26` `price: Decimal = Decimal("0")` | Decimal | `int` Rial |
| `shipping/providers/alopeyk.py:~418` `Decimal(str(data["price"]))` | **Toman** per SDK | `to_rial = toman * 10` at the adapter |
| `shipping/providers/snapbox.py:~384` `Decimal(str(data["totalFare"]))` | unit **unstated** | confirm unit before any live use (OQ-5); until confirmed, keep unconverted and flagged |

### 7.8 Frontend (impact summary — implemented by the frontend counterpart of 14.1.2.2)

* **About 25 non-test files** carry their own formatter and must all switch to `utils/money.js`:
  `components/` BestSellers, Cards, Countdown, CouponInput, FlashSalePrice, Hero, OrdersTab,
  PaymentMethodsTab, SearchBox, ShippingOptionPicker, VariantPicker, WishlistTab;
  `pages/` Account, Cart, Category, Checkout, OrderConfirmation, ProductDetails, SearchResults;
  `pages/admin/` AdminAnalytics, AdminDashboard, AdminOrders, AdminProducts, AdminUsers;
  `utils/coupon.js`. Also `Header.jsx` (USD selector / `bi-currency-dollar` icon) and
  `AdminDashboard`/`AdminAnalytics` currency icons.
* **`Checkout.jsx` float math** (`TAX_RATE = 0.10`, `tax = subtotal * TAX_RATE`, `total = ...`):
  must not survive as float arithmetic. Short term: replace with `roundToWholeToman` and the
  shared golden vectors. Preferred follow-up: server-computed totals so there is a single
  implementation of the pricing formula.
* **27 frontend test files** assert `$`-formatted or `toFixed` money and need updating.

## 8. Alternatives considered

| Option | Verdict |
|---|---|
| **A. Keep `Decimal(…,2)`, reinterpret as Toman** | Rejected. Keeps the wrong data type; every gateway call needs a `x10` that the repo's own docstrings call "easy to get backwards"; still string-serialised. |
| **B. `Decimal(…, decimal_places=0)` in Rial** | Rejected as the end state. Right unit, but still `Decimal` (I-1 unenforceable), strings in JSON, fractional arithmetic still expressible. |
| **C. Integer Toman** | Rejected. Gateways and the ISO code are Rial-denominated (conversion at every boundary); and the redenomination (§9) makes "Toman" the *ambiguous* word — storing the unit with the least ambiguity is safer. |
| **D. `float`** | Rejected outright. |
| **E. Integer Rial, whole-Toman granularity (chosen)** | Gateway amounts are identity; arithmetic is exact integers; display division is exact; DB-enforceable. |
| **F. API returns Toman (server converts)** | Rejected: puts the conversion in two languages and makes the wire unit disagree with the stored/gateway unit. |

## 9. External risk — Iran's currency redenomination

Reported facts (sources at the end): parliament approved removing four zeros in October 2025
(**10,000 current rials = 1 new unit**) and the Guardian Council approved it in November 2025,
with a multi-year transition in which old and new currency circulate together; the central
bank has talked of dual price labelling and full withdrawal of the old rial by 2030, and one
account says the process begins in the Iranian year 21 Mar 2026 – 20 Mar 2027.
**Sources disagree on the new unit's name** — some say "new toman", others say it keeps the
name "rial" with a 100-qiran subunit.

Consequences for this ADR:

* **Storage is redenomination-proof.** Integer *legacy* Rial is the finest practical unit
  (1 qiran = 100 legacy rial), so no stored value ever needs rewriting when the transition
  happens — only display and gateway-adapter units change.
* **The word "Toman" will become ambiguous** (colloquial Toman = 10 rial; a "new toman" would
  be 10,000 rial). Throughout code and UI this ADR defines **Toman = 10 legacy IRR**. Name the
  stored unit **legacy Rial / `IRR`** in docs and help-text.
* **Display is isolated** behind `formatToman` / one Python filter, so dual labelling or a new
  unit is a one-place change.
* **Trigger for a new ADR:** the central bank announces the transition start date, or a
  gateway (ZarinPal/Zibal/IDPay) changes its `amount` unit. Until then, 14.1.2.2 proceeds.

## 10. Open questions

| # | Question | Blocking? | Default if unanswered |
|---|---|---|---|
| **OQ-1** | Does any environment hold **real** price/order data, or only test/seed data? The old numbers have no currency meaning, so no automatic scale factor is defensible. | **Yes — blocks 14.1.2.2** | Assume pre-launch: migrate structurally (value read as Rial, rounded per §5), re-seed prices; abort the migration on a non-empty production DB unless an explicit factor is supplied. |
| OQ-2 | Storefront digit script: Persian digits (`fa-IR`) or Latin? | No | **Resolved (14.1.2.3 / 14.1.2.4):** Latin by default; Persian digits opt-in via `persianDigits`, per context. |
| OQ-3 | PDF invoice denomination: Rial, Toman, or both? Confirm with the accountant. | No | Rial primary (matches bank/gateway statements) with Toman total in parentheses. |
| OQ-4 | `PricingService.TAX_RATE = 10%` applied to `subtotal` only is a USD-template placeholder; confirm the real VAT rate/base. Out of scope here, but 14.1.2.2 edits that code. | No | Preserve formula as-is. |
| OQ-5 | SnapBox `totalFare` unit; confirm AloPeyk's Toman against live docs. | No | AloPeyk x10; SnapBox flagged "do not use live". |
| OQ-6 | Redenomination naming/timing (§9). | No | Monitor. |

## 11. Guidance for Task 14.1.2.2

1. Add `core/money.py`, `core/fields.py` (`RialField`), the DRF `RialSerializerField`, template filter.
2. Per-field migration, in this order: (a) data step — round to a multiple of 10 (and apply
   the OQ-1 policy); (b) `AlterField` Decimal -> `RialField` (Postgres rewrites the table
   under an `ACCESS EXCLUSIVE` lock — acceptable now, schedule for `order_orderitem`/`order_order`
   if data has grown); (c) `AddConstraint` (`x % 10 = 0`). `Coupon` splits into add-columns ->
   copy by `discount_type` -> drop `value`.
3. Existing migration files are history — never edited.
4. Ship backend and SPA **together**: field names do not change but their *unit* does
   (`"25.00"` -> `250000`); a stale cached bundle would show wrong magnitudes. Cache-bust the SPA.
5. Update **54 backend test files** and `seed_shop`; add: the registry test (§7.4);
   property tests (random subtotal/percent => multiples of 10, identity I-4, discount <= eligible);
   shared golden vectors (§5/§6) in Python and JS; gateway test asserting sent amount ==
   stored amount; DB test rejecting `1_250_005`.

## 12. Consequences

**Positive:** exact integer arithmetic; no float/Decimal leaks; gateway amounts are identity;
one conversion point per language; DB-enforced invariant; redenomination-proof storage;
self-verifying field inventory.
**Negative / costs:** large cross-cutting change (17 columns, ~25 SPA files, ~80 test files);
API money values change from strings to numbers with unchanged field names; `Coupon` API break;
table rewrites during migration; a second (small) Python formatter alongside the JS one.
**Risks:** wrong-unit bugs during the cut-over (mitigated by shipping together and by the
golden vectors); AloPeyk/SnapBox unit mistakes (mitigated by I-7/D8 and OQ-5).

## 13. Verification performed while writing this ADR

On the project's stack (Postgres 16, Django 5.2.11), against a scratch table:
`CheckConstraint(condition=Exact(Mod("amount", 10), 0))` is accepted and enforced
(`1_250_005` -> `IntegrityError`); `Sum()` over `PositiveBigIntegerField` returns `int` for
values beyond int32; `Coalesce(Sum(...), 0)` returns `0` on an empty table; `Avg()` returns
`float`. PositiveIntegerField's ceiling is 2,147,483,647 Rial (214,748,364 Toman).

The §5 reference helpers were also executed: the Python implementation reproduces every
golden vector and the worked checkout; the JS `roundToWholeToman` agrees with the Python
`percent_of` on **1,000,000 random (subtotal <= 10^11, percent) cases with zero mismatches**,
with a worst-case JS intermediate of ~2.0 x 10^15 (< 2^53 ~ 9.0 x 10^15, which is why the
cap is `10**11`); and `Intl.NumberFormat` renders the §6 vectors exactly as listed (checked for the default and `persianDigits: true`).

## 14. References

* In-repo: `payments/gateways/{zarinpal,zibal,idpay}.py` (Rial integer amounts);
  `shipping/providers/{alopeyk,snapbox}.py` (unit notes); `order/services/pricing.py`;
  `promotions/services.py`; `frontend/src/pages/Checkout.jsx`;
  `frontend/src/components/ShippingOptionPicker.jsx` (comment: no shared currency formatter).
* Redenomination (accessed 2026-10-20; names conflict — verify against the law/CBI before
  acting on §9): Rudaw, 2025-11-08, "Iran's Guardian Council approves bill to slash four zeroes
  from currency"; Gulf News/AFP, Oct 2025, "Iran approves plan to slash four zeros from
  currency"; bne IntelliNews, 2026-02-24, "Iran to phase out old rial by 2030 in four-zero
  redenomination"; Planet Banknote, Aug 2026, "Iran Rial Redenomination: A Collector's Guide".

## 15. Implementation record (Task 14.1.2.2)

**What was built.** `core/money.py`, `core/fields.py` (`RialField`), `core/serializers.py`
(`RialSerializerField`), `core/templatetags/money.py`, `frontend/src/utils/money.js` and
`frontend/src/constants/pricing.js`; all 17 columns of §7.1 are `RialField`s with a
`x % 10 = 0` `CHECK` each; `PricingService`, coupon validation, flash-sale pricing, gateways,
carrier adapters, serializers, filters, dashboard aggregates, invoice and CSV export follow §7.5-§7.7.

**Migration shape (per app, 3 steps; promotions 5).** Mixing row updates and `ALTER TABLE` in
one Postgres transaction can fail ("pending trigger events"), so each app runs:
`widen` (Decimal -> `Decimal(24,2)`, lossless) -> `rebaseline` (data, `RunPython`, x10,000,
reversible) -> `to_integer_rial` (Decimal -> `RialField` + constraints). Promotions inserts the
`Coupon.value` split between them (`0007` add columns, `0008` copy by `discount_type`, `0009`
drop `value` + constraints). Verified against a populated legacy database built from the
pre-Epic-14 code: forward, reverse (original data restored exactly), and forward again.

**OQ-1 resolved — and the migration refuses to run on live data by accident.**
The existing numbers are seed/test data in a dollar-shaped scheme, so they are *re-baselined*
with one documented, arbitrary factor: `new_rial = round(old * 10_000)` to a whole Toman
(old 29.99 -> 299,900 Rial = 29,990 Toman). The factor is a constant at the top of each data
migration. **If a target database holds real financial records this factor is wrong** and the
migration must not be run as a routine schema change: every data migration aborts unless
`MONEY_REBASELINE_CONFIRMED=true` is set whenever it finds rows in the tables it would rewrite.
For real data, obtain a business-signed conversion (or freeze historical orders as a legacy
reference and apply the new scheme only to new data) first.

**Other open questions.** OQ-2 (resolved by Tasks 14.1.2.3 / 14.1.2.4): Western digits by default; Persian digits
are the opt-in `persianDigits` toggle, configured per context in `constants/numerals.js`. OQ-3: invoice shows Rial per line with the grand total also in Toman. OQ-4: the 10%
`TAX_RATE` formula is unchanged (still an unverified USD-template placeholder). OQ-5: AloPeyk x10
at the adapter; SnapBox `totalFare` is treated as Rial and rounded to a whole Toman until its unit
is confirmed. OQ-6: still to monitor (§9).

**Deviations / decisions made while implementing.** (1) The `Coupon` columns are named
`percent_off` / `fixed_amount` (as in §7.3). (2) Rounding uses `core.money.to_whole_toman_rial`
(half-up), not Python's `round()`, which is banker's rounding. (3) Customer-facing coupon and
refund messages state their unit (`... %(amount)s Toman.`), so their Persian translations were
updated in the same change. (4) CSV order export money columns carry a `_rial` suffix
(`total_rial`, ...), per invariant I-8. (5) The frontend rejects non-whole-Toman values loudly in
development/test (§6) — which is how stale dollar-shaped test fixtures were caught.
