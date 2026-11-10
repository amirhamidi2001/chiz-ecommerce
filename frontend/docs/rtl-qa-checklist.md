# RTL QA checklist — executed (Task 14.3.3.1)

Manual QA pass of the storefront, account area and admin SPA, rendered in a real Chromium with
`dir="rtl"` / `lang="fa"`, against the **real backend** (PostgreSQL 16, Redis, Django) loaded with
Persian seed data. Run date: 2026-11-07/08. Tasks 14.3.1.1–14.3.1.4 are assumed merged (the `dir`
attribute, logical-property classes, `icon-directional` mirroring and their guard tests are all
present in the tree).

> **Read this first — the biggest caveat.** The storefront's UI copy is **English** (no i18n library;
> Persian appears only in data, units such as تومان, and `About.jsx` / `Faq.jsx`). So this run verified
> an *English interface laid out right-to-left* with Persian *data*. Layout, direction and icon
> semantics are verified; **text widths, bidi behaviour of real Persian UI strings, and Vazirmatn
> metrics on UI chrome are not**. Section 5 separates findings that will persist after translation
> (group A) from ones that are artifacts of English copy and must be **re-verified** once Persian
> copy lands (group B). A pseudo-localization run (every English word replaced by a same-length
> Persian word) was used as a proxy; it is not a substitute.

## 1. Method

| | |
|---|---|
| Browser | Chromium (Playwright), `locale fa-IR`, `Asia/Tehran`. **Firefox and Safari were not tested.** |
| Viewports | Desktop 1366×900 and mobile 390×844 for every route (51 routes, incl. `/login?mode=register`) |
| Roles | anonymous, customer (`customer@qa.test`), admin (`admin@qa.test`) |
| Data | `seed_fa.py` (in the harness zip): long/mixed-script product names, color + volume variants, review photos, a store reply, an active flash sale, coupons, orders in every status with shipments, wishlist, 2 addresses. The repo's own `seed_shop`/`seed_blog` are stale (see FUNC-04) and were not usable. |
| Automated probe | In-page script on every route: horizontal page overflow; elements leaking outside the viewport; Persian text laid out LTR; Persian text hugging the physical left edge; form-control direction; horizontal scrollers and where they start; **visual** direction of every directional icon + the name of its control. **The probe was validated against injected known-bad elements and caught all of them**, so its zeros are meaningful for those categories. |
| Interactions | PDP gallery/variants/tabs, header search + account menu, mobile menus/drawers, chat widget, admin modals, Jalali picker, price slider (keyboard), toggles, bidi typing in inputs |
| Visual review | Screenshots reviewed by a person/agent for the pages marked 👁 below. Pages marked 🤖 were **probe-only: spacing and aesthetics were not judged**. |

Legend — **Verified:** 👁 screenshot reviewed · 🖱 interaction exercised · 🤖 automated probe only.
**Result:** ✅ pass · ⚠️ issue found (ID) · ❌ open defect · ➖ not applicable · ❓ not judged / not exercised.
Screenshots are in `rtl-qa-screenshots/`. Shots 01–08 were taken **before** the fixes in §6 (they still show the scrambled phone number and the unflipped gradient); 25 is after.

The six checks per page: **A**lignment (text reads naturally RTL) · **S**pacing (intentional, not mirrored-wrong) · **I**cons (semantic direction) · **F**orms (inputs/labels) · **O**verlays (modals/dropdowns on-screen) · **H** horizontal scroll (RTL-correct direction).

## 2. Executive summary

* **No page overflows horizontally, at desktop or at 390px.** No element clips outside the viewport except the one admin-analytics card fixed here (RTL-06).
* **Direction-sensitive widgets behave correctly:** next/previous/back/exit icons all point the right way; the PDP gallery, Jalali picker, price slider (native range, `ArrowLeft` increases), toggles (OFF = start edge, ON = end), order-tracking stepper, review store-reply box, admin sidebar and both mobile drawers all behave RTL-correctly. Every horizontal scroller starts at the right edge.
* **Issues found (§5):** 10 layout/bidi items (group A) — 4 fixed, 4 open defects (RTL-04, 05, 07, 08), 2 design checks — plus 4 localization prerequisites (group L), 5 English-copy artifacts to re-verify (group B) and 9 non-RTL defects (group F, 3 fixed). The most important non-RTL one: the Epic 7 tracking widget could never show real shipment data in the account area (FUNC-01, fixed).
* **Zero-issue run did not happen**, as expected. A prioritised follow-up list is in §7.

## 3. Per-page results

### 3.1 Storefront

| Page / flow | Verified | A | S | I | F | O | H | Notes / issues |
|---|---|---|---|---|---|---|---|---|
| **Home** `/` — hero/banner | 👁 | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | RTL-03 (fixed). B1 trailing punctuation on the English tagline. Shots 01, 02 |
| Home — product grids / popularity columns | 👁 | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | Grids start at the right; ratings fill from the right; B4 "From" label order |
| Home — category cards (PromoCards) | 👁 | ✅ | ⚠️ | ✅ | ➖ | ➖ | ➖ | RTL-03 (fixed, shot 25); RTL-08 description overlaps image mosaic (open, P3) |
| Home — flash-sale banner (Epic 9) | 👁 | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | Countdown reads correctly; the old hardcoded `Countdown` section no longer exists. Physical gradient: RTL-04 (cosmetic) |
| Home — "Recommended For You" (Epic 13) | 🤖🖱 | ✅ | ❓ | ✅ | ➖ | ➖ | ❓ | Renders for a user with history; probe clean; **not viewed** |
| **Category / listing** `/category` — filter sidebar (Epic 12) | 👁🖱 | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | Sidebar on the right, accent bars on the start edge. Price slider verified by keyboard. B2 "12 per page" / "0 products found". Facets *below* the colour filter (skin type, SPF, …) were probe-only. Shot 03/03b |
| Category — mobile | 🤖 | ✅ | ❓ | ✅ | ✅ | ➖ | ➖ | Facets stack inline (no filter drawer exists); no overflow |
| **Search** `/search?q=` + suggest dropdown | 🤖🖱 | ✅ | ❓ | ✅ | ✅ | ✅ | ➖ | Dropdown stays inside the viewport. **Not viewed** (shot 26 captured) |
| **PDP** — gallery/carousel | 👁🖱 | ✅ | ✅ | ✅ | ➖ | ➖ | ✅ | "Next" at the left pointing left, "Previous" at the right pointing right; counter 1/3→2/3→3/3→wraps; thumbnails start at the right. Shot 04 |
| PDP — variant (colour) selector | 👁 | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | Swatches ordered from the right. **Clicking a swatch to confirm the price update was not exercised (script selector missed)** |
| PDP — price / quantity / trust badges | 👁 | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | B2 "30-Day Returns" draws "Day Returns-30" (`ProductDetails.jsx:940`); B1 `:Available Colors`; RTL-10 stepper puts "+" on the left (design check) |
| PDP — reviews incl. photos, store reply (Epic 10) | 👁🤖 | ⚠️ | ✅ | ✅ | ➖ | ➖ | ➖ | RTL-05 open: Latin reviewer name "Reza K." draws ".Reza K". Store-reply box correct (accent bar on the start edge, date at the end). Review **photo thumbnails were probe-only** |
| PDP — Related / Customers Also Bought (Epic 13) | 👁 | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | Grids start at the right; "View All ←" points left |
| **Cart** — table, summary | 👁 | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | Summary on the left, table anchored right, radios on the start edge. B2 "30-day returns" (`Cart.jsx:471`); RTL-10 |
| Cart — coupon UI (Epic 9) | 👁 | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | Input right, button left. **Apply (valid/invalid code) flow was NOT exercised** (script selector missed); only the layout was reviewed |
| **Checkout** — address form / saved-address picker (Epic 5) | 👁 | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | Radios on the start edge, "Default" badge. L3 province shows as English ("Tehran 1234567890"). The "new address" form was not opened |
| Checkout — carrier selection (Epic 7) | 👁 | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | Persian carrier names, price at the end |
| Checkout — terms / place order / **payment redirect (Epic 6)** | 👁 | ⚠️ | ✅ | ✅ | ✅ | ➖ | ➖ | B3 terms sentence reorders. **Place-order and the gateway redirect were NOT exercised** (no gateway sandbox/network here) |
| Checkout failed `/checkout/failed` | 🤖 | ✅ | ❓ | ✅ | ➖ | ➖ | ➖ | |
| **Order confirmation** (Epic 7) | 👁 | ⚠️ | ✅ | ✅ | ➖ | ➖ | ➖ | Layout correct. B1 "?Need Help", B2 "CHZ-2026-1003#". B5 delivery-date line looked reordered (**unconfirmed**) |
| **Global chrome** — header, ticker, nav | 👁 | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | Ticker has an `rtl:` animation variant; RTL-01 phone (fixed) |
| Global — account menu / search dropdown / chat widget | 🤖🖱 | ✅ | ❓ | ✅ | ➖ | ✅ | ➖ | Open within the viewport. Shots 26/27 captured, not viewed |
| Global — footer | 👁 | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | RTL-01 (fixed); B1 trailing period on © line |
| Global — mobile menu | 👁🖱 | ✅ | ✅ | ✅ | ➖ | ✅ | ➖ | List right-aligned; RTL-09 hamburger sits at the end (left) |
| Product lists `/product-lists` | 🤖 | ✅ | ❓ | ✅ | ➖ | ➖ | ➖ | |

### 3.2 Account (customer)

| Page | Verified | A | S | I | F | O | H | Notes |
|---|---|---|---|---|---|---|---|---|
| Overview `/account` | 🤖 | ✅ | ❓ | ✅ | ➖ | ➖ | ➖ | Breadcrumb shows the raw tab key (FUNC-08) |
| Orders + order modal + **tracking widget** (Epic 7) | 👁🖱 | ✅ | ✅ | ✅ | ➖ | ✅ | ➖ | Stepper runs right→left, fill bar grows from the right, close button at the left (shot 10). **FUNC-01 and FUNC-02 fixed here** |
| Wishlist (Epic 11) | 👁 (low-res) | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | Grid from the right; "Move to Cart" buttons |
| Addresses | 👁 (low-res) | ✅ | ✅ | ✅ | ❓ | ❓ | ➖ | RTL-07 phone/postal are `type="text"`. The add/edit modal was not opened |
| My Reviews | 👁 (low-res) | ✅ | ✅ | ➖ | ➖ | ➖ | ➖ | Only the empty state exists in the seed |
| Settings | 👁🖱 | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | First name on the right; toggle knob geometry verified |
| Payment methods `/account?tab=payments` | 👁 (low-res) | ✅ | ✅ | ✅ | ➖ | ➖ | ✅ | Table columns start at the right |
| Change password | 🤖 | ✅ | ❓ | ✅ | ✅ | ➖ | ➖ | |

### 3.3 Auth and content pages

| Page | Verified | A | S | I | F | O | H | Notes |
|---|---|---|---|---|---|---|---|---|
| Login | 🤖 | ✅ | ❓ | ✅ | ✅ | ➖ | ➖ | Email typing verified fixed (RTL-02) |
| Register `/login?mode=register` | 👁 (low-res) | ✅ | ✅ | ✅ | ✅ | ➖ | ➖ | Last name left / first name right; field icons at the start edge. Standalone `Register.jsx` is orphaned (FUNC-08) |
| Forgot / reset / confirm-email | 🤖 | ✅ | ❓ | ✅ | ✅ | ➖ | ➖ | Functional flows were not exercised |
| Blog list / post | 🤖 | ✅ | ❓ | ✅ | ➖ | ➖ | ➖ | |
| About / Contact / FAQ / Support | 🤖 | ✅ | ❓ | ✅ | ✅ | ➖ | ➖ | Support phone fixed (RTL-01); Contact map iframe could not load offline |
| Shipping / Returns / Payment methods / Privacy / Terms / 404 | 🤖 | ✅ | ❓ | ✅ | ➖ | ➖ | ➖ | Physical gradients: RTL-04 |

### 3.4 Admin dashboard

| Screen | Verified | A | S | I | F | O | H | Notes |
|---|---|---|---|---|---|---|---|---|
| Overview | 👁 (low-res) | ✅ | ✅ | ✅ | ➖ | ➖ | ➖ | Sidebar on the right |
| Analytics — desktop | 🤖 | ✅ | ❓ | ✅ | ✅ | ➖ | ➖ | |
| Analytics — mobile | 👁 | ✅ | ✅ | ✅ | ✅ | ➖ | ✅ | **RTL-06 fixed** (card was 554px wide, left edge at −188px). B2 "12-month chart" (`AdminAnalytics.jsx:171`) |
| **Order management** | 👁 (low-res) | ✅ | ✅ | ✅ | ✅ | ❓ | ✅ | Table anchored right, Actions at the left; scroller starts at the right. Row-detail modal: probe clean, **not viewed** |
| Products / Categories / Reviews | 👁 (low-res) | ✅ | ✅ | ✅ | ✅ | ➖ | ✅ | Edit/create modals not opened |
| **Coupon management** — list | 👁 (low-res) | ✅ | ✅ | ✅ | ➖ | ➖ | ✅ | |
| Coupon modal + **Jalali date picker** | 🖱 | ✅ | ❓ | ✅ | ✅ | ✅ | ➖ | Saturday first at the right; Previous at the right/Next at the left; popover fits (bottom 887/900px). **Modal screenshot not viewed.** L2 romanized month/weekday names |
| Brands / Users / Messages / Chats / Blog | 🤖 | ✅ | ❓ | ✅ | ➖ | ➖ | ✅ | |
| Mobile admin drawer | 👁🖱 | ✅ | ✅ | ✅ | ➖ | ✅ | ➖ | Opens from the right; icons on the start edge; RTL-09 |

## 4. Not covered by this run (do these before launch)

1. **Payment redirect flow (Epic 6) and Place Order** — needs a gateway sandbox.
2. **Real Persian UI copy** (see the caveat) and a re-run of this checklist afterwards.
3. **Firefox and Safari** (notably `type=tel` direction, `unicode-bidi: plaintext` on inputs, and the `rtl:` Tailwind variants).
4. Cart coupon apply (valid/invalid), PDP variant click → price update, address add/edit modal, admin create/edit modals, ConfirmModal and toasts, forgot/reset/confirm functional flows.
5. Screenshots 26, 27 and the admin order-detail/coupon-modal screenshots were captured but **not viewed**; "Recommended For You" and review photo thumbnails were probe-only.
6. The **invoice PDF** (`Download Invoice`) and transactional emails — RTL rendering of backend-generated documents was not examined.
7. Keyboard focus order, screen readers, print styles, touch gestures.

## 5. Issue register

Priority: **P1** blocks a credible Persian launch · **P2** visible defect · **P3** polish / design check. Status: FIXED = in `rtl-qa-fixes.patch`.

### Group L — localization prerequisite

| ID | Pri | Issue | Where |
|---|---|---|---|
| **L1** | **P1** | Storefront/account/admin UI copy is English; no frontend i18n layer. Blocks validation of every group-B item and of real text metrics. | all of `frontend/src` (only `About.jsx`, `Faq.jsx`, `utils/money.js`, numerals, jalali utils contain Persian) |
| L2 | P2 | Jalali picker shows romanized month names (`Aban`, `Azar`) and English weekday abbreviations (`Su Mo Tu`) | `components/JalaliDatePicker.jsx`, `utils/jalaliCalendar.js` |
| L3 | P2 | Province labels are English, so a Persian address ends in "Tehran 1234567890" | `constants/provinces.js` |
| L4 | P3 | Mixed-language status UI: backend label "در مسیر" next to English step labels in the tracking widget | `ShipmentTrackingWidget.jsx` |

### Group A — RTL defects that persist after translation

| ID | Pri | Status | Page / component | Expected vs actual | Fix |
|---|---|---|---|---|---|
| RTL-01 | P2 | **FIXED** | Header top bar, Footer, Support page — phone numbers | Expected `+1 (234) 567-890`; actual drew `567-890 (234) 1+` (digits and `+` reordered by the RTL paragraph) | `dir="ltr"` on the element (an isolate). Guard: `rtlBidiGuards.test.js` (it found the Support instance the manual pass had missed) |
| RTL-02 | P2 | **FIXED** | Every `type=email` / `type=url` input (login, register, contact, checkout) | Typing `ali.reza@example.com.` drew `.ali.reza@example.com` | Global `unicode-bidi: plaintext` rule in `index.css`. `dir="ltr"` on the input was tried and rejected (it flips `ps-`/`pe-`, putting text under the field icon). `type=tel` is already forced LTR by Chromium (Firefox/Safari unverified) |
| RTL-03 | P2 | **FIXED** | `PromoCards` (both card variants), `Hero` — image-fade gradients | Image anchored at `end-0` (left in RTL) but gradient was physical `to-l`, fading the *outer* edge, so text sat on an unfaded image | `rtl:bg-gradient-to-r` / `rtl:bg-gradient-to-l`. Verified in the browser (shot 25) |
| **RTL-05** | **P2** | **OPEN** | PDP reviews (reviewer name, headline, body, store reply); likely also admin review/user tables, addresses | Latin user-generated text with trailing punctuation: reviewer "Reza K." draws ".Reza K". Persists after translation because user content stays Latin | Wrap user-supplied strings in `<bdi>` (names) / `dir="auto"` (headline, body, store reply). Add a guard test like RTL-01. Size: S |
| RTL-06 | P2 | **FIXED** | Admin analytics, 390px | Card 554px wide, left edge −188px, spilling off-screen. Cause: grid items without `min-w-0` (12 bars × `min-w-[20px]` + labels). Not RTL-specific, but invisible in RTL because it overflows to the left | `[&>*]:min-w-0` on both grids (`AdminAnalytics.jsx`); snapshot updated. Verified `scrollWidth == clientWidth == 390` |
| RTL-07 | P3 | OPEN | Address book `Field` (phone, postal code) | Plain `type="text"`: no browser LTR isolation, no numeric keyboard; a `+98…` number would reorder | `type="tel"` (+ `inputMode="numeric"` for postal code); `AddressesTab.jsx` `Field` takes a `type` prop already |
| RTL-04 | P3 | OPEN | `FlashSaleBanner`, Account header, PaymentMethods, ReturnPolicy, Terms, Privacy — decorative `bg-gradient-to-r` | Colour wash runs the "wrong" way in RTL; purely cosmetic (no text/image relationship) | Add `rtl:bg-gradient-to-l` where the direction matters; consider extending the guard test |
| RTL-08 | P3 | OPEN | Large "آرایش" category card | Description paragraph is wider than the text column and runs over the image mosaic (it does in LTR too; now sits on the faded edge) | Constrain the text column width, or give it a solid backing |
| RTL-09 | P3 | design check | Storefront mobile header, admin top bar | Hamburger sits at the end (left) while the drawer opens from the right | Confirm intent; Persian sites usually put it at the start (right) |
| RTL-10 | P3 | design check | PDP and cart quantity stepper | "+" on the left, "−" on the right | Confirm intent with design |

### Group B — artifacts of English copy: **re-verify after translation**

| ID | Observation | Source |
|---|---|---|
| B1 | Trailing colons/periods/ellipses/question marks land at the wrong end: `:Available Colors`, `:Quantity`, `.Django REST Framework & React`, `…Search products`, `?Need Help`, `.Chiz. All Rights Reserved ©` | many components; `Header.jsx:54` |
| B2 | Digit-hyphen labels reorder: "30-Day Returns" → "Day Returns-30" (`ProductDetails.jsx:940`, `Cart.jsx:471`), "12-month chart" → "month chart-12" (`AdminAnalytics.jsx:171`), "12 per page" (`Category.jsx:824`), "0 products found", "Order #…" → "CHZ-2026-1003#" | |
| B3 | Checkout terms sentence renders as "Privacy Policy \| I agree to the Terms and Conditions and": the trailing inline `<button>` is a bidi-neutral at the paragraph end and resolves to RTL | `Checkout.jsx` (terms checkbox label). Likely correct once the whole sentence is Persian; **re-verify** |
| B4 | "From" label sits after the price ("371,250 تومان From") | product cards |
| B5 | Order-confirmation delivery window / "Estimated:" line looked reordered. **Unconfirmed** — seen once | `OrderConfirmation` page |

The pseudo-Persian run confirmed B1 vanishes with Persian words (shot 24) while RTL-01 (phone) and RTL-08 persist.

### Group F — non-RTL defects found along the way

| ID | Pri | Status | Issue |
|---|---|---|---|
| **FUNC-01** | **P1** | **FIXED** | Account order modal calls `/dashboard/orders/<id>/` (`UserOrderDetailSerializer`) which had **no `shipment` field**, so the Epic 7 tracking widget always said "Not yet shipped", even for in-transit orders. Added `shipment` to the serializer and `select_related("shipment")` to the view; 2 backend tests. Verified in the browser (shot 10) |
| FUNC-02 | P2 | **FIXED** | `OrdersTab` list rendered `<img src="">` for items with a blank `product_image` snapshot: empty bordered boxes + a React warning per image. Blank snapshots are now skipped; 2 tests |
| FUNC-03 | P2 | **FIXED** | `npm ci` fails: `@testing-library/dom` (required peer of `@testing-library/react@16`) is in neither `package.json` nor the lockfile. Added as a devDependency |
| FUNC-04 | P2 | OPEN | `seed_blog` crashes (`User(username=…)`; the model has no `username`). `seed_shop` is stale: English electronics, products without variants, fails without a real Redis (`get_redis_connection`) |
| FUNC-05 | P2 | OPEN | Auto-generated SKUs from Persian names are Persian with stray spaces (`رژ -گلد-24`): bidi-hostile on labels/admin and unusable for barcodes. Same family as the earlier slug/`allow_unicode` finding |
| FUNC-06 | P2 | OPEN | Bootstrap Icons are loaded from the cdnjs CDN in `index.html`: an external dependency in a market where reliability is a stated platform concern. Self-host (npm `bootstrap-icons`) |
| FUNC-07 | P3 | OPEN | Observed, intent unverified: the checkout "Email Address" field was empty for a logged-in customer |
| FUNC-08 | P3 | OPEN | Orphan `pages/Register.jsx` (registration lives at `/login?mode=register`); dead, un-imported `src/App.css` (Vite template); account breadcrumb prints the raw tab key; cart title has no space before "(4 items)" |
| FUNC-09 | P3 | OPEN | Existing ESLint `react-hooks/set-state-in-effect` errors at `AdminAnalytics.jsx:128` and `OrdersTab.jsx:214` (not introduced here) |

## 6. What was changed in this task (all in `rtl-qa-fixes.patch`)

| Change | Files |
|---|---|
| Phone numbers isolated (RTL-01) | `Header.jsx`, `Footer.jsx`, `pages/Support.jsx` |
| Email/url inputs laid out by content (RTL-02) | `index.css` |
| Direction-aware fade gradients (RTL-03) | `PromoCards.jsx`, `Hero.jsx` |
| Analytics grid `min-w-0` (RTL-06) | `pages/admin/AdminAnalytics.jsx` + updated snapshot (only the two class strings changed) |
| Skip blank order thumbnails (FUNC-02) | `components/OrdersTab.jsx` |
| Shipment on the account order detail (FUNC-01) | `backend/dashboard/serializers.py`, `views.py` |
| Missing peer dependency (FUNC-03) | `package.json`, `package-lock.json` |
| New tests | `__tests__/rtlBidiGuards.test.js` (phone isolation, `from-transparent` gradients need an `rtl:` counterpart, email/url bidi rule), `__tests__/OrdersTabPreviewImages.test.jsx`, 2 tests in `backend/dashboard/tests/test_views.py` |

**Test status after the changes:** frontend **78 files / 2,451 tests, all passing** (baseline before: 76 files / 2,443); backend `dashboard` + `order` suites run with no failures (requires compiled Persian catalogs: `python manage.py compilemessages`; `msgfmt` must be installed). No new lint errors were introduced; the two existing errors in FUNC-09 remain (they are in files this task edited, outside the edited lines).

## 7. Recommended follow-up tasks (prioritised)

1. **P1 — Frontend Persian translation** (L1, with L2–L4). Then **re-run this checklist** (harness in `rtl-qa-harness.zip`; `stress_fa.mjs` is only a proxy) and re-verify group B.
2. **P1/P2 — User-generated Latin text isolation** (RTL-05): `<bdi>`/`dir="auto"` across review, address, admin table cells; add a guard test. *Size S.*
3. **P2 — Cross-browser pass** (Firefox, Safari): `type=tel`, `unicode-bidi: plaintext`, `rtl:` variants, native range sliders.
4. **P2 — Exercise the unexercised flows** (§4): payment redirect, place order, coupon apply, variant click, address modal, admin modals; view the captured-but-unviewed screenshots.
5. **P2 — Self-host Bootstrap Icons** (FUNC-06); **fix SKU generation for Persian names** (FUNC-05); **repair or delete stale seed commands** (FUNC-04).
6. **P2 — Invoice PDF / email RTL review** (§4.6).
7. **P3 — Polish batch:** RTL-04, 07, 08, 09, 10; FUNC-07, 08, 09.

## 8. Re-running

See `rtl-qa-harness.zip` → `README.md`. Run `probe_test.mjs` first to confirm the probe still catches known-bad elements, then `run_pages.mjs`, then the interaction scripts. A clean probe means *no overflow / clipping / left-hugging / LTR-Persian / mis-started scrollers*; it does not mean the page looks right. Spacing and aesthetics still need eyes on the screenshots.
