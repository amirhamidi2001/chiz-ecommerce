# ADR 0003 — hreflang: self-reference only; multi-language support deferred

| | |
|---|---|
| **Status** | **Accepted** (2026-11-13) |
| **Date** | 2026-11-13 |
| **Epic / task** | Epic 15 — Task 15.1.5 (P3). Builds on Epic 14 Task 14.1.1.1 (`LANGUAGES`) and Task 15.1.4 (canonical URLs) |
| **Scope** | Frontend `<head>` tags only. No backend, URL-structure or content change |

---

## 1. Context

`hreflang` tells search engines "this page has equivalent versions in these other languages". It only means
something once those versions really exist, at distinct URLs, with genuinely translated content.

Today they do not:

* The storefront is **Persian-only** (`<html lang="fa" dir="rtl">`, `LANGUAGE_CODE = "fa"`).
* Django's `LANGUAGES` also lists `"en"`, but the settings comment is explicit: it is "kept available for
  admin/staff convenience and any future i18n expansion". It is not a public English storefront, and no
  `/en/...` URL space, translated catalog or language switcher exists.

## 2. Decision

**D1.** Every indexable page declares only itself, as the Persian (Iran) version and as the fallback:

```html
<link rel="alternate" hreflang="fa-ir"     href="<canonical URL of this page>">
<link rel="alternate" hreflang="x-default" href="<canonical URL of this page>">
```

**D2.** The `href` is the page's **canonical URL** (the Task 15.1.4 canonical rule), not `origin + pathname`:
hreflang must reference canonical URLs, and on this site the category lives in the query string
(`/category?category=<slug>`), so the path alone would name every category `/category`. A page with no canonical
(noindex search views, one-time-token URLs) gets no hreflang.

**D3.** **No `hreflang="en"` (or any other language) is emitted.** Full multi-language `hreflang` support is
**deferred** until, and unless, a real English storefront is built.

## 3. Alternatives considered

| Option | Verdict |
|---|---|
| **A. `hreflang="en"` pointing at the same page, or at a not-yet-existing `/en/...` URL** | Rejected. States something false; the target is a 404 or identical Persian content. Misleading search engines is worse than no tag. |
| **B. No hreflang at all** | Acceptable, but a self-reference costs nothing, is correct, and is the shape the final markup will have. |
| **C. Build the `fa`/`en` URL structure now** | Rejected as speculative: no English content, no owner, no consumer. |

## 4. Consequences

* **No ranking or targeting effect today.** A lone self-reference is valid and harmless; it is groundwork only.
* One shared helper (`frontend/src/components/hreflangLinks.jsx`) renders the pair for both the sitewide default
  and every page-level `<Seo>`, so the two cannot drift.
* `fa-ir` scopes the page to Persian-in-Iran. If Persian speakers elsewhere (Afghanistan, the diaspora) become a
  target, the language-only `fa` is the broader value.

## 5. Revisit when an English storefront is actually built

Not before. At that point, together and not piecemeal:

- [ ] Decide the URL structure (path prefix `/en/...` vs subdomain) and **supersede** this ADR (do not edit it).
- [ ] Every page lists **all** its variants, reciprocally: `fa-ir`, `en`, and `x-default`, each pointing at that
      variant's own canonical URL. One-way annotations are ignored by search engines.
- [ ] Each variant has its own canonical, `<html lang>`, `og:locale` (currently fixed to `fa_IR`) and
      `og:locale:alternate`, and its own sitemap entries.
- [ ] Re-read the slug strategy (ADR 0002): translated slugs change the URL for every page.
- [ ] Only pages that really have a translation declare one; never point `en` at a Persian page.
