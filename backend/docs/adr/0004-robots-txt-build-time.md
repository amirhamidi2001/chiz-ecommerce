# ADR 0004 — robots.txt: generated at build time, blocked unless explicitly opted in

| | |
|---|---|
| **Status** | **Accepted** (2026-11-14) |
| **Date** | 2026-11-14 |
| **Epic / task** | Epic 15 — Task 15.1.2.2. Related: ADR 0003 (hreflang), Task 15.1.4 (canonical / `noindex`) |
| **Scope** | `frontend/robots.js` (generator + Vite plugin), `frontend/Dockerfile`, `docker-compose.prod.yml` |

---

## 1. Context

`frontend/public/robots.txt` was one static file with three problems: a never-replaced
`https://yourdomain.com` sitemap, only `/admin/` disallowed, and identical content in every
environment (so a staging build advertised itself as crawlable).

Facts about how this project is actually deployed, which decided the design:

* The frontend is **static files behind a bare nginx** (`location /` only, SPA fallback to
  `index.html`). The SPA calls the API on a **separate origin** (absolute `VITE_API_BASE_URL`).
  Nothing on the frontend host can reach Django.
* There is **no staging or preview concept** in the repo: only `development` and `production`
  settings. A staging build is the production build with different settings, so `DEBUG`, the Django
  settings module and Vite's `import.meta.env.PROD` (true for *every* `vite build`) cannot tell them apart.

## 2. Decision

**D1. Static file, generated at build time** by a Vite plugin (`frontend/robots.js`); it is emitted
into `dist/` and served by the dev server. `public/robots.txt` is removed.

**D2. Blocked unless explicitly opted in.** A build is crawlable only when `VITE_ALLOW_INDEXING` is
exactly `true`. Anything else (dev, staging, preview, an unconfigured production build, a typo such
as `True`) gets `User-agent: *` / `Disallow: /` and **no `Sitemap:` line**, even when a site URL is
set. The opt-in is the only thing that can differ between two otherwise identical builds, and a
forgotten setting fails *safe*.

**D3. Opting in with unusable config fails the build** (`VITE_SITE_URL` missing, not https, or
localhost; same for `VITE_SITEMAP_URL`), instead of shipping a placeholder or wrong sitemap.

**D4. The private-route list comes from the live routes**, not a guess. Disallowed (prefix rules):
`/admin /cart /checkout /account /change-password /order-confirmation /login /forgot-password
/reset-password /confirm-email`. A test re-derives the guarded routes from `src/App.jsx` and fails
if one is missing, if a rule matches no route, or if a public route would be blocked.
Deliberately **not** blocked: `/search` (it is `noindex, follow`; a noindex is only visible on a
fetchable page), filter/sort URLs on `/category` (their canonicals must be crawlable), `/assets/`
(Google renders the SPA, which needs its JS/CSS).

**D5. `Crawl-delay` is removed.** Google ignores it, Bing treats it as a loose time window, Yandex
dropped it. It protects nothing here: the pages are static nginx files, and the API, the only
expensive surface, is a separate origin this file does not govern and is throttled by DRF (Epic 2:
`anon 100/min`, `user 300/min`).

**D6. Sitemap URL** is `VITE_SITEMAP_URL` if set, else `<VITE_SITE_URL>/sitemap.xml`. A sitemap on a
different host than the URLs it lists is allowed when the site's own `robots.txt` references it.

## 3. Alternatives considered

| Option | Verdict |
|---|---|
| **Django view at `/robots.txt`** | Rejected. Needs a new nginx upstream (and `Host`/`ALLOWED_HOSTS` handling) or edge rules outside the repo, plus a Vite dev proxy. Worse, if the route is missing, nginx's SPA fallback answers `/robots.txt` with `index.html` and HTTP 200, which crawlers read as "no rules, allow everything", the opposite of fail-safe. |
| **Static file per environment** | Rejected: relies on remembering to edit it, the exact failure being fixed. |
| **`import.meta.env.PROD` as the signal** | Rejected: true for staging builds too. |

## 4. Consequences and operations

* **Production must set `VITE_ALLOW_INDEXING=true` and `VITE_SITE_URL=https://<real domain>`** in its
  build args (`docker compose build`), and `VITE_SITEMAP_URL` if the sitemap is served from the API host.
  Until then production's `robots.txt` is `Disallow: /`. After every production deploy:
  `curl https://<domain>/robots.txt` and confirm the `Allow:` and the real `Sitemap:` line.
* `/sitemap.xml` (served by Django) must actually be reachable at the `Sitemap:` URL; the frontend's
  nginx cannot serve it. Route it at the edge, or set `VITE_SITEMAP_URL` to the backend's URL.
* Build args and `ENV` take precedence over `frontend/.env.*` files, even when empty (Vite `loadEnv`).
* `Disallow` blocks **crawling**, not necessarily **indexing**: a blocked URL that other sites link
  to can still be listed (without a snippet). Keep staging behind authentication as well. Do not add
  a `noindex` meta there: a crawler that is blocked can never read it.
