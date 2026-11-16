# Social-crawler preview PoC (exploratory)

**Exploratory proof of concept from the Task 15.1.2.3 spike. Not production code, and not wired into the real
`nginx.conf`.** Read `../docs/prerendering-evaluation.md` first (sections 7 and 8).

## What is here

* `nginx.social-preview.conf`: the nginx side. Routes link-preview crawlers (by User-Agent allowlist) requesting
  `/product/<slug>` to the backend preview page; everyone else gets the normal SPA. Falls back to the SPA if the
  backend is down, slow, or has no such product.
* Backend (outside this folder): `backend/shop/social_preview.py`, the `share/product/<slug>` route in
  `backend/core/urls.py`, and `backend/shop/tests/test_social_preview_poc.py`.

## Reproduce the demo

1. Build the SPA: `cd frontend && npx vite build`
2. Run Django against a migrated database with at least one product, with
   `FRONTEND_URL=https://chiz.example ALLOWED_HOSTS=localhost,127.0.0.1`:
   `python manage.py runserver 127.0.0.1:8000 --noreload`
3. Adapt the nginx file for local use: set `root` to `frontend/dist`, `listen` to a free port, and
   `set $preview_backend "127.0.0.1:8000";`, then run nginx with it as the `http`-context include.
4. Compare clients on the same URL:
   ```bash
   U=http://localhost:8092/product/<slug>
   curl -s -A "WhatsApp/2.23.20.72 A"          $U | grep og:      # tags present
   curl -s -A "TelegramBot (like TwitterBot)"  $U | grep og:      # tags present
   curl -s -A "Mozilla/5.0 Chrome/126"         $U | grep -c og:   # 0: normal SPA
   curl -s -A "Googlebot/2.1"                  $U | grep -c og:   # 0: search engines get the SPA
   ```
5. Stop Django and repeat the WhatsApp request: you get the SPA shell, not an error.

## Run the tests

`cd backend && pytest shop/tests/test_social_preview_poc.py` (needs PostgreSQL and Redis like the rest of the suite).

## Before this becomes a real feature

See section 8 of the evaluation: single source of truth for the SEO text, blog/category coverage, a public media
origin and image derivative, caching with purge, a maintained user-agent list, an nginx-config test in CI.
