// robots.txt for the storefront (Task 15.1.2.2), generated at BUILD time by a Vite plugin.
// Why static + build-time rather than a Django view, and the full reasoning:
// backend/docs/adr/0004-robots-txt-build-time.md
//
// THE RULE: a build is crawlable only if it explicitly says so. Everything else (local dev, a
// staging or preview build, a production build somebody forgot to configure) gets
//
//     User-agent: *
//     Disallow: /
//
// There is no per-environment file to remember to edit: the environment's own build settings
// decide, and the default is "blocked". The repo has no staging/preview concept and a staging
// build is otherwise identical to production (same settings module, same `vite build`), so
// nothing but an explicit opt-in can tell them apart.
//
//   VITE_ALLOW_INDEXING=true   opt in (exactly "true"); set ONLY for the real production site
//   VITE_SITE_URL              the public https origin (also used for canonical / JSON-LD / OG)
//   VITE_SITEMAP_URL           optional; where the sitemap is served. Default: <VITE_SITE_URL>/sitemap.xml
//
// Opting in without a usable VITE_SITE_URL / sitemap URL FAILS THE BUILD instead of shipping a
// robots.txt that points at a wrong or placeholder sitemap.
//
// A robots.txt block stops CRAWLING, not necessarily INDEXING (a blocked URL that other sites
// link to can still be listed, without a snippet). Keep staging behind authentication too.
import { loadEnv } from 'vite';

// Routes that are private, transactional or auth flows. Derived from the live route table in
// src/App.jsx (guarded by ProtectedRoute / GuestRoute / AdminRoute, plus /cart, which is
// per-user state with no guard); a test re-derives them from App.jsx and fails when a route
// is missing here. robots.txt rules are PREFIX matches, so one entry covers a whole subtree
// (/checkout also covers /checkout/failed; /order-confirmation covers /order-confirmation/:id).
export const PRIVATE_PATHS = [
  '/admin', //              admin SPA (AdminRoute)
  '/cart', //               per-user cart
  '/checkout', //           + /checkout/failed
  '/account', //            profile, orders, addresses, wishlist ...
  '/change-password', //    ProtectedRoute
  '/order-confirmation', // /order-confirmation/:id
  '/login', //              GuestRoute
  '/forgot-password', //    GuestRoute
  '/reset-password', //     /reset-password/:uid/:token: the path carries a one-time token
  '/confirm-email', //      GuestRoute, token in the query string
];

// Deliberately NOT blocked:
//  * /search: it is `noindex, follow` (Task 15.1.4), and a crawler can only see a noindex on a
//    page it is allowed to fetch. Blocking it would leave the bare URL indexable with no content.
//  * filter/sort query parameters on /category: their canonical tags (also 15.1.4) are only read
//    if the variants can be crawled.
//  * /assets/: the SPA only renders once its JS and CSS load, and Google renders pages.
// Crawl-delay is intentionally absent: Google ignores it, Bing reads it as a loose time window,
// Yandex dropped it, and it protects nothing here (the HTML/JS are static nginx files; the API
// is a separate origin this file does not govern and is throttled by DRF: Epic 2).

const BLOCK_ALL = [
  '# robots.txt is generated at build time (frontend/robots.js). Non-production build: not crawlable.',
  'User-agent: *',
  'Disallow: /',
  '',
].join('\n');

const LOCAL_HOST = /^(localhost|.*\.localhost|.*\.local|0\.0\.0\.0|127\.[\d.]+|\[?::1\]?)$/i;

/** A real, public https URL, or a thrown Error naming the variable. */
const requirePublicHttps = (value, name) => {
  let url;
  try {
    url = new URL((value ?? '').trim());
  } catch {
    url = null;
  }
  if (!url || url.protocol !== 'https:' || LOCAL_HOST.test(url.hostname)) {
    throw new Error(
      `robots.txt: VITE_ALLOW_INDEXING=true needs ${name} to be the real public https URL ` +
        `(e.g. https://example.com); got ${JSON.stringify(value ?? '')}. ` +
        'Remove VITE_ALLOW_INDEXING to build a non-crawlable (staging/dev) site.',
    );
  }
  return url;
};

/**
 * Decide, from the build's VITE_* env, whether this build is crawlable.
 * Returns { indexable: false } (the default), or { indexable: true, sitemapUrl }.
 * Throws if indexing is requested but the site/sitemap URL is not a usable public https URL.
 */
export function resolveRobotsConfig(env = {}) {
  const flag = (env.VITE_ALLOW_INDEXING ?? '').trim();
  if (flag !== 'true') {
    return {
      indexable: false,
      warning: flag
        ? `VITE_ALLOW_INDEXING=${JSON.stringify(flag)} is not exactly "true": robots.txt blocks all crawling.`
        : undefined,
    };
  }
  const site = requirePublicHttps(env.VITE_SITE_URL, 'VITE_SITE_URL');
  const sitemap = env.VITE_SITEMAP_URL?.trim()
    ? requirePublicHttps(env.VITE_SITEMAP_URL, 'VITE_SITEMAP_URL')
    : new URL('/sitemap.xml', site.origin);
  return { indexable: true, sitemapUrl: sitemap.href };
}

/** The robots.txt text for a resolved config. */
export function buildRobotsTxt(config = { indexable: false }) {
  if (!config.indexable) return BLOCK_ALL;
  return [
    '# robots.txt is generated at build time (frontend/robots.js); edit PRIVATE_PATHS there.',
    'User-agent: *',
    ...PRIVATE_PATHS.map((path) => `Disallow: ${path}`),
    // Last, so a first-match parser meets the specific Disallows before it; for
    // longest-match parsers (Google, RFC 9309) the order makes no difference.
    'Allow: /',
    '',
    `Sitemap: ${config.sitemapUrl}`,
    '',
  ].join('\n');
}

/** Vite plugin: serves robots.txt in the dev server and emits it into dist/ on build. */
export function robotsPlugin() {
  let content = BLOCK_ALL;
  return {
    name: 'chiz-robots-txt',
    configResolved(config) {
      const resolved = resolveRobotsConfig(loadEnv(config.mode, config.envDir, 'VITE_'));
      if (resolved.warning) config.logger.warn(`[robots.txt] ${resolved.warning}`);
      content = buildRobotsTxt(resolved);
      config.logger.info(
        `[robots.txt] mode "${config.mode}": ${resolved.indexable ? `crawlable, sitemap ${resolved.sitemapUrl}` : 'blocked (Disallow: /)'}`,
      );
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if ((req.url ?? '').split('?')[0] !== '/robots.txt') return next();
        res.setHeader('Content-Type', 'text/plain; charset=utf-8');
        res.end(content);
      });
    },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'robots.txt', source: content });
    },
  };
}
