# Prerendering evaluation (spike), Task 15.1.2.3

| | |
|---|---|
| **Status** | Recommendation for review. Not an ADR yet: promote to `backend/docs/adr/0005-…` once accepted |
| **Date** | 2026-11-15 |
| **Type** | Investigation spike. A small proof of concept (PoC) of the narrow option is included and marked exploratory |
| **Knowledge cutoff note** | Vendor/pricing/maintenance facts were researched on 2026-11-15 and can change; section 10 lists sources and what could **not** be verified |

---

## 1. Recommendation (read this first)

1. **Do not build full prerendering or SSR now.** The case for it is weak for *search* and strong only for
   *link previews*, which have a much cheaper fix. Revisit on the triggers in section 9.
2. **Do build the narrow social-crawler fix, as a follow-up task.** Today a product link shared in
   Telegram, WhatsApp or a similar app gets no title, image or description, because those crawlers don't run
   JavaScript and the tags added by `react-helmet-async` (Task 15.1.3) never reach them. The PoC in this spike
   fixes that for product URLs with ~120 lines of Django code, ~35 nginx directives and no new service. Section 8
   lists what a production version must still do.
3. **Design the fix to be user-agent-*agnostic* if it can be.** The market evidence below says a
   crawler allowlist will be incomplete here: Telegram and WhatsApp are blocked by Iranian ISPs (VPN only) in 2026,
   and the domestic messengers (Bale, Eitaa, Rubika, Soroush Plus) don't publish their link-preview
   crawlers. Start with the allowlist (it's the smallest safe step and is what the PoC does), **log unmatched
   non-browser user agents**, and move to head-tag injection for every client (option N2) if the allowlist keeps missing.
4. **Fix the real page-weight problem separately and cheaply:** the production bundle is one 883 kB
   (220 kB gzip) JavaScript file with **no route-level code splitting**. Prerendering would not remove that
   download; `React.lazy` routes would.
5. **Measure before escalating.** Search Console coverage and organic traffic, share click-through (Epic 27), Core Web Vitals.
6. **Check four things only you can answer** (section 9) before the follow-up: where the site is hosted,
   whether foreign crawlers can reach it, whether product images are publicly served, and which messengers customers
   really share on.

---

## 2. What the problem actually is (it is four problems)

"No SSR" is being asked to explain four different concerns, which have different answers:

| # | Concern | Who is affected | Does it need prerendering? |
|---|---|---|---|
| A | Search-engine **indexing** of client-rendered pages | Googlebot, Bingbot | No, not today (section 4) |
| B | **Link previews** in messengers/social apps | Telegram, WhatsApp, Meta, X, Slack, Bale/Eitaa/Rubika… | They need the tags **in the raw HTML**; not full prerendering (section 5) |
| C | **AI-assistant / answer-engine crawlers** | GPTBot, ClaudeBot, PerplexityBot and similar | Raw HTML only; a business decision (section 4.3) |
| D | **Initial load performance** | Everyone | Partly; a bundle fix is cheaper (section 6) |

### Evidence from this repo

* Stack: React 19, `react-router-dom` 7 in *declarative* mode (`<BrowserRouter>` + `<Routes>`), Vite 8, client-side only.
  `react-helmet-async` 3.0.0 adds head tags in the browser.
* Deployment: Docker; the frontend image is **static files behind a bare nginx** (`location /` with an SPA
  fallback to `index.html`). The API is a separate origin (Daphne, port 8000, compose service `backend`).
  Nothing on the frontend host can reach Django today.
* **Measured (Task 15.1.3, repeated here):** requesting a product URL from the repo's own nginx with a WhatsApp or
  Telegram user agent returns the 2 kB `index.html` shell with **zero `og:` tags**. Tags added by React exist only after JavaScript runs.
* **Bundle (`vite build`, 2026-11-15):** `index-*.js` 882.7 kB (219.8 kB gzip), `index-*.css` 62.8 kB (11.2 kB gzip).
  Zero `React.lazy`/`lazy()` calls in `App.jsx`; Vite itself warns about the chunk size.
* Catalog size is unknown to me. It decides whether build-time static generation is feasible (section 3, O3).

---

## 3. Options evaluated

Criteria: **(a)** maintained today? **(b)** fit with this Docker/nginx deployment, **(c)** cost, **(d)** does it
serve non-JavaScript crawlers such as Telegram's and WhatsApp's?

| Option | (a) Maintained | (b) Fit here | (c) Cost | (d) Non-JS crawlers | Verdict |
|---|---|---|---|---|---|
| **O1. Hosted prerender service** (Prerender.io) | Yes: pricing revised 2026-09-15 | Easy on paper (nginx rule per bot UA, then their render). Needs the site **publicly reachable from their cloud**; adds an external dependency in the request path | Paid, per render: Starter $59/mo for 30k renders, then $169 (100k), $419 (500k); desktop and mobile renders count separately by default; free tier ended Oct 2025 | **Yes**, for any UA you route to it | **No.** See "Iran-specific blockers" below |
| **O2. Self-hosted render server** (Rendertron, open-source `prerender`, headless Chrome) | **No**: Rendertron archived (2022). Upstream `prerender/prerender` status **unverified** (one 2026 post says the repo is gone; I could not confirm). Docker images of it I found are pinned to 2021-era Chromium | Needs a Chrome container, memory, a cache and a purge strategy, plus the nginx bot routing | Server cost + ops | Yes | **No.** Don't adopt an unmaintained renderer |
| **O3. Build-time static generation** (`vite-react-ssg`, React Router 7 `prerender`, TanStack Start prerender) | Yes. `vite-react-ssg` 0.9.2 targets React Router **v6** and points v7 users at React Router's built-in SSG; TanStack's prerender skips parameterized routes unless they're linked | Needs routes moved to data-router/framework mode and **product/blog data fetched at build time**. Every price/stock/content change needs a rebuild + redeploy | No service cost; real engineering + a rebuild pipeline | Yes (HTML is in the file) | **No for products** (stale data, rebuild per change). Fine for the few static pages (About/FAQ/policies) if ever wanted |
| **O4. Real SSR** (React Router 7 framework mode, Vike, TanStack Start, Next.js) | Yes | A migration, not an integration: new Node runtime container, routing/data-loading rewrite, hydration constraints, new failure modes | Highest (engineering + running a Node tier) | Yes | **Not now.** The right answer if SEO becomes the main growth channel (section 9) |
| **N1. Narrow: bot allowlist → tiny backend page** (the PoC) | n/a (≈120 lines you own) | Small: one nginx `map` + one Django view; no new service | ~Free | **Yes** for listed crawlers; unknown ones still get the plain shell | **Recommended first step** |
| **N2. Narrow, universal: inject head tags into the HTML shell for every client** on product/blog/category URLs | n/a | A server must answer those URLs (Django or small edge function) and splice tags into `index.html`. The SPA must then **de-duplicate** tags (React 19 hoists its own beside static ones, we hit this in Tasks 15.1.1–15.1.3) | ~Free | **Yes, for every fetcher**, with no user-agent list. Also helps Googlebot and AI crawlers | **Likely end state** if N1's allowlist keeps missing |
| **N0. Do nothing** | n/a | n/a | $0 | **No** | Rejected: previews stay blank (concern B is real and measured) |

### Iran-specific blockers for O1 (verify, don't assume)

* Prerender.io is a foreign SaaS billed internationally. Sanctions compliance and Iranian-issued cards commonly
  prevent signing up from Iran; **check their terms and your billing path before spending any time on it.**
* A hosted renderer fetches your site **from abroad**. If the site is hosted inside Iran with restricted foreign
  access (section 5.3) it simply can't render it.

---

## 4. The case for doing nothing (about search)

### 4.1 Googlebot renders JavaScript, and Google says so

* Google's JavaScript SEO documentation covers client-rendered pages as normal and supports canonical
  and robots tags that are added by JavaScript (with the caveat that a conflicting value in the *original* HTML is
  what counts; our `index.html` has none, so there is nothing to conflict with).
* Google's own dynamic-rendering page now calls serving separate prerendered HTML to crawlers **a
  workaround and not a recommended solution**, to be replaced by SSR, static rendering or hydration. (It also says
  it is *not* cloaking if the content is equivalent; relevant to N1 below.)
* Large-sample crawl data (Vercel/MERJ, Dec 2024, read here via several write-ups, not the primary post) found Google
  rendering essentially all HTML pages including JavaScript-heavy ones, with a median render delay around ten seconds
  and a long tail. That is slower than static HTML, not broken.

### 4.2 Persian-market search (the Yandex question)

StatCounter's Iran figures (2026) show **Google at roughly 99.3–99.8% across desktop, mobile and tablet, Bing
under 1%, and Yandex around 0.04%.** There is no evidence that Yandex or Bing matter here. Caveat: StatCounter only counts
referrals to sites using its tracker and shows no local Iranian engines at all; if the business believes domestic
engines matter, that is a separate question for them. Net: the search-engine side of this decision is a
**Googlebot-only** decision, and Googlebot is the engine that renders JavaScript.

### 4.3 The one growing exception: AI crawlers

The same Vercel research found that the major AI crawlers (OpenAI's, Anthropic's, Perplexity's and others) fetch
raw HTML and **do not execute JavaScript**, so a client-rendered site is effectively empty to them. Whether that
matters is a business call ("do we want to be cited by AI assistants?"), not a technical one. If yes, it
strengthens N2 (universal head/body content in the raw HTML) and eventually O4.

### 4.4 Risks of doing nothing about search
* Slower, less certain indexing than static HTML (hours of tail latency, "Discovered, currently not indexed").
* Everything we ship that matters to Google (canonical, `noindex`, JSON-LD, hreflang, OG) depends on rendering succeeding.

These are measurable (section 9), not assumed.

---

## 5. Link previews, the real problem

### 5.1 How the crawlers behave

* **Telegram.** Telegram's own bug tracker (2026) shows the crawler's user agents in the wild:
  `TelegramBot (like TwitterBot)` **and** `TelegramBot/1.0 like Linux` (so match on a substring, not the whole string);
  requests come from Telegram's own IP ranges; and a ~2 kB server-rendered page with OG tags is enough. The same
  tracker has threads from 2026 about Telegram **suppressing** previews for pages that look perfect, so test
  with Telegram's `@WebpageBot` and expect some noise that isn't ours.
* **WhatsApp.** Meta's official link-preview doc (updated 2026-05) says WhatsApp makes a plain HTTP GET with a
  `WhatsApp/2.x.x.x A|I|N` user agent, **explicitly tells site owners they may recognize these requests and customize
  the markup**, requires the OG tags within the first **300 kB** of HTML, and sets an image size limit (the doc says
  under 600 kB; community reports say ~300 kB in practice). Facebook's `facebookexternalhit`/`Facebot` also appears.
* None of them execute JavaScript. That is the whole problem.

### 5.2 Why a *narrow* fix beats full prerendering here
The previews need five facts per page (title, description, image, URL, price). That is a 1.5 kB document, not a
rendered application. Building the heavy machinery (headless Chrome, a render cache, a rebuild pipeline) to produce
that is disproportionate, and a renderer would still need a bot allowlist to know who to serve.

### 5.3 The Iran-2026 context changes who is on the other end
Reporting through May–June 2026 (Al Jazeera, Iran International, NPR, Gizmodo, filter.watch):
* Iran had a near-total internet shutdown of roughly 88 days, restored from late May 2026 with heavy
  restrictions, including whitelist-style treatment of foreign addresses.
* Telegram is blocked by Iranian ISPs and WhatsApp is reported blocked again; both are used through VPNs. Domestic messengers
  (Bale, Rubika, Soroush Plus, Eitaa) are growing.

Consequences for this decision (my inference, to be verified with real traffic):
1. **A user-agent allowlist will miss the domestic messengers.** I found no public documentation of their link-preview
   crawlers. This is the main reason to log unmatched user agents and to prefer N2 later.
2. **Reachability is a prerequisite for everything in this document.** If the site is hosted inside Iran behind
   restrictions on foreign IPs, then Telegram's servers (which fetch from abroad) and Googlebot may not reach it at all,
   and no rendering strategy helps. Verify with a simple external fetch (section 9).
3. Premise update for Task 15.1.3: "WhatsApp and Telegram are the key channels" is still plausible (VPN use is high,
   and the diaspora uses them freely) but is **no longer safe to assume**. Look at what customers actually share on.

### 5.4 A separate failure mode no rendering approach fixes: image size
`Product.thumbnail` is an ordinary upload with **no resizing**. A multi-megabyte product photo can exceed
WhatsApp's thumbnail limit and silently yield a preview with no image, however perfect the HTML. A real fix needs a
generated ~1200×630 derivative under ~300 kB. (The branded fallback `og-default.jpg` from Task 15.1.3 is 91 kB.)

---

## 6. Performance (concern D), honestly

* Prerendered HTML improves *first paint / LCP* (content is in the HTML) but the **same 220 kB gzip JS bundle still
  has to download and hydrate**. It would not cure the cost the Vite warning is pointing at.
* The cheaper, higher-leverage fix is **route-level code splitting** (`React.lazy` per route; admin and checkout never need
  to ship with the storefront home page). It helps every user, requires no new infrastructure, and is orthogonal to SEO.
  Recommend it as its own small task.
* I could not measure Core Web Vitals in this sandbox. Run PageSpeed Insights / CrUX on the live site before and
  after, so the "performance is a ranking factor" argument is evidence, not assumption.

---

## 7. Proof of concept (exploratory: do not ship as is)

**What it does:** for `GET /product/<slug>`, nginx checks the `User-Agent` against a short allowlist of link-preview
crawlers. A match is answered by a new Django view, `GET /share/product/<slug>`, that returns a script-free HTML page
with the OG tags. Everything else gets the normal SPA shell, byte for byte as today.

**Files**

| File | Role |
|---|---|
| `backend/shop/social_preview.py` | The view + HTML builder (marked EXPLORATORY) |
| `backend/core/urls.py` | One import + one route (`share/product/<str:slug>`) |
| `backend/shop/tests/test_social_preview_poc.py` | 15 tests; 5 mutation checks all caught |
| `frontend/poc/nginx.social-preview.conf` | The nginx side. **Not** wired into `frontend/nginx.conf` |
| `frontend/poc/README.md` | How to run the demo |

**Verified end to end** with real nginx (the PoC config) in front of the built SPA and a running Django (migrated DB,
a Persian-named product):

| Request to `/product/serum-vitamin-c` | Result |
|---|---|
| `WhatsApp/2.23.20.72 A` | 200, **1.5 kB OG page in ~20 ms**: title, `og:*`, canonical, `product:price:amount=4990000`/`IRR` |
| `TelegramBot (like TwitterBot)` and `TelegramBot/1.0 like Linux` | same OG page (both variants matched) |
| `facebookexternalhit/1.1` | same OG page |
| Chrome | normal SPA shell, 0 `og:` tags, `Vary: User-Agent` |
| **Googlebot** | normal SPA shell: search engines are *not* given the snippet |
| WhatsApp, **unknown product** | falls back to the SPA shell (200), not an error |
| WhatsApp, **backend stopped** | falls back to the SPA shell immediately |
| WhatsApp, `/category?…` or `/faq` | untouched SPA |
| Hostile product name (`"><script>…`) | escaped; no `<script>` in the output (unit tested) |

**Defects found by actually running it (fixed in the PoC; each is a trap for the real task)**

1. **`error_page` chains silently don't run.** My first design routed bots with `return 418` + `error_page 418 = @preview`,
   and an upstream 404 then produced a bare nginx 404 instead of the SPA fallback, because nginx refuses a second
   `error_page` redirect while handling the first (`recursive_error_pages` is off by default). The final design uses
   `rewrite … last` into an `internal` location, so the fallback is a first-level redirect.
2. **`Vary: User-Agent` was missing on the SPA branch.** `try_files … /index.html` is an internal redirect that drops
   `add_header`. The same URL now returns different bytes per user agent, so without `Vary` a CDN in front could cache
   one variant and serve it to everyone. Fixed by routing the SPA branch through a named location. **Anything
   caching HTML in front of this must honor `Vary`.**
3. **`og:image` came out as `http://127.0.0.1:8000/media/…`**: the PoC builds image URLs from the `Host` header nginx
   forwards, which is an internal address. The real task must use a configured *public* media origin.

**Known shortcuts (a real follow-up must fix, see section 8):** the title/description/price rules are a Python copy of
`frontend/src/utils/seo.js` and will drift; no caching; products only; no image derivative; `Host` header handling;
allowlist is hand-written.

---

## 8. What a real follow-up task must cover

1. **One source of truth for SEO text.** Move title/description/OG/price rules into the backend and expose them as a
   `seo` object in the product/blog/category APIs; have the SPA's `buildProductOpenGraph` consume it and the preview
   view render it. Otherwise the two copies *will* diverge (price, brand names, truncation).
2. **Coverage:** blog posts (`/blog/<slug>`) and category/brand listings (`/category?category=…`), plus the home page. Same
   facts as the SPA; canonical = the SPA URL.
3. **Public media origin.** Image URLs must be absolute, public, https and not derived from the proxy `Host`. Confirm product media is
   actually reachable by crawlers: today the frontend nginx serves nothing but `/`, so I could not tell where `/media/…` is
   served from in production.
4. **Image derivative** ≈1200×630, under ~300 kB, for every product that can be shared.
5. **Caching.** `proxy_cache` keyed by slug with a short TTL (the PoC sends `max-age=300`), and a purge or short TTL when a
   product's price/stock/name changes. Previews that show a stale price are a trust problem on a commerce site.
6. **The user-agent list as a maintained asset.** Log (user agent, path) for non-browser fetches of `/product/*` for a few
   weeks to discover Bale/Eitaa/Rubika/Soroush and others; decide on N2 if the list keeps growing.
7. **Never serve the snippet to search engines** (Googlebot, Bingbot, Applebot). They render JavaScript and should see the real page.
   Also keep `Vary: User-Agent` on both branches and make sure any CDN honors it.
8. **Deployment wiring.** The nginx file replaces `frontend/nginx.conf` in the image; `backend` must resolve from the frontend container
   (it does on the compose network) and be in Django's `ALLOWED_HOSTS`; give the proxy short timeouts (the PoC uses 1 s connect, 3 s read).
9. **Tests:** an nginx-config test in CI (the two defects above would have been caught by one), the full product/blog/category
   view matrix, escaping, 404/5xx fallback, and a smoke test with Telegram's `@WebpageBot`.
10. **Security:** slug validation, rate limiting on the preview route, no user-controlled data reflected unescaped (the PoC escapes everything).

Rough size for N1 as specified: a few days of work; N2 is a larger, more careful change because of tag de-duplication.

---

## 9. Measure, then revisit

**Add now (cheap):** Search Console (coverage, "Crawled/Discovered – not indexed", sitemap submitted vs indexed), a periodic
`curl -A WhatsApp …` check, and access-log counts of non-browser user agents on product URLs.

**Revisit full prerendering/SSR (O4) when any of these is true:**
* Search Console shows a meaningful share of sitemap URLs stuck in *Discovered/Crawled – not indexed*, or indexing lags days behind new products.
* Organic traffic is falling or flat while catalog and content grow (once Epic 27 analytics exists to see it).
* The business decides AI-assistant visibility (concern C) is a growth goal.
* Core Web Vitals on real devices are poor **after** code splitting.
* Search becomes the primary acquisition channel (then SSR is simply the correct architecture).

**Revisit the share-preview approach (N1→N2)** if the logged unmatched user agents show real messenger traffic, or if share click-through from
Telegram/WhatsApp/domestic apps looks abnormally low.

### Questions for the team (blocking the follow-up)
1. **Where is production hosted, and can Googlebot and Telegram's servers reach it from outside Iran?** (Test with an external fetch.)
2. **Is there a CDN or edge cache in front of nginx?** It must honor `Vary`.
3. **Where are product images served from publicly?** Is the URL in `thumbnail_url` fetchable by an outside crawler?
4. **Which messengers do customers actually share product links in?** That decides the allowlist and whether N2 comes first.
5. How many products/posts exist and how often do prices change? (Sizes the caching/purge work and rules out O3 definitively.)

---

## 10. Sources and confidence

Researched 2026-11-15. "Not fetched" means I saw the claim in search results/secondary write-ups but did not open the primary page.

| Claim | Source | Confidence |
|---|---|---|
| Dynamic rendering is "a workaround", not cloaking if content is similar | Google Search Central, *Dynamic rendering as a workaround* (developers.google.com/search/docs/crawling-indexing/javascript/dynamic-rendering) | High |
| Canonical/robots via JavaScript supported; mismatch with original HTML is the risk | Google Search Central, *JavaScript SEO basics* | High |
| Google rendered all HTML pages incl. JS-heavy; median render delay ~10 s; AI crawlers don't run JS | Vercel/MERJ crawler studies (Dec 2024) via secondary write-ups. Primary not fetched | Medium |
| Telegram crawler user agents, source IPs, minimal server-rendered page works, 2026 preview-suppression reports | bugs.telegram.org/c/61650 (several threads) | Medium–High |
| WhatsApp plain GET, `WhatsApp/2.x.x.x A\|I\|N`, may customize per request, 300 kB head rule, image limit | developers.facebook.com/documentation/business-messaging/whatsapp/link-previews/ (updated May 2026) | High (image limit varies by source) |
| Iran search share: Google ≈99%+, Bing <1%, Yandex ≈0.04% | gs.statcounter.com/search-engine-market-share/all/iran | Medium (tracker-based) |
| Prerender.io pricing and free-tier end | prerender.io/pricing, docs.prerender.io pricing-update-2026 | High as of the date |
| Rendertron archived | github.com/GoogleChrome/rendertron | High |
| Upstream `prerender/prerender` status | One 2026 blog says repo gone; **could not confirm** | Low |
| `vite-react-ssg` 0.9.2 / React Router v6; TanStack Start prerender skips param routes | github.com/Daydreamer-riri/vite-react-ssg, tanstack.com/start docs | Medium–High |
| Iran 2026 shutdown/restrictions, Telegram/WhatsApp blocked, domestic messengers | Al Jazeera (2026-05-31), Iran International (2026-05-25), NPR (2026-05-28), Gizmodo, filter.watch (2026-01) | Medium: fast-moving situation |
| Domestic messengers' crawler user agents | **No public documentation found** | n/a |
| Sanctions/billing obstacles to Prerender.io | General knowledge; **not verified, check their terms** | Low |

Everything about *this repo* (bundle sizes, deployment shape, absence of staging/lazy loading, the zero-OG raw HTML) was measured directly.
