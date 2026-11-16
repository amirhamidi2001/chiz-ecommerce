// Canonical URLs (Task 15.1.4).
//
// A <link rel="canonical"> tells search engines which URL is THE address of a page, so the many
// URLs that show the same thing (?utm_source=…, filters, sort order, parameter order, a trailing
// slash) consolidate their ranking signals onto one. The rules, in one place:
//
//  • The origin is fixed configuration (VITE_SITE_URL), not "whatever host served this request",
//    so http/https and www/apex variants all point at the one real address. When it isn't set
//    (dev, tests) it falls back to the current origin.
//  • By default a page canonicalizes to origin + path with NO query string and no trailing slash.
//    That is right only when the query string does not change WHAT the page shows.
//  • On this site two routes keep their identity in the query string, and a path-only canonical
//    would merge them all into one URL, so they build theirs from the parameters that matter:
//      /category?category=<slug>   (the category IS a query parameter, not part of the path)
//      /blog?category=<slug>
//    Both keep `category`, keep `page` only from page 2 on (each page of a listing has different
//    content, so page 2 canonicalizes to ITSELF, never to page 1), and drop everything else
//    (filters, sort, page size, flash sale, …), whose views are the same content rearranged.
//    Parameters are written in one fixed order, so ?a=1&b=2 and ?b=2&a=1 yield the same URL.
//  • Internal search views are not canonicalized at all; they are noindex (see <Seo robots>).

/** Site origin: VITE_SITE_URL if it is a valid http(s) URL (path ignored), else the current origin. */
export const siteOrigin = () => {
  const configured = import.meta.env?.VITE_SITE_URL;
  if (typeof configured === 'string' && configured.trim()) {
    try {
      const url = new URL(configured.trim());
      if (url.protocol === 'http:' || url.protocol === 'https:') return url.origin;
    } catch {
      /* not a URL: fall through to the current origin */
    }
  }
  return (typeof window !== 'undefined' && window.location && window.location.origin) || '';
};

/** Paths whose URL carries a one-time secret; they never get a canonical link. */
const NO_CANONICAL_PREFIXES = ['/reset-password'];

/**
 * Clean, percent-encoded path: collapses repeated slashes, drops a trailing slash (except the
 * root), and encodes Persian segments consistently whether or not they arrive already encoded.
 * Returns '' for anything that is not an absolute path.
 */
export const normalizePath = (pathname) => {
  if (typeof pathname !== 'string' || !pathname.startsWith('/')) return '';
  try {
    const { pathname: encoded } = new URL(pathname.replace(/\/{2,}/g, '/'), 'http://localhost');
    return encoded.length > 1 ? encoded.replace(/\/+$/, '') : encoded;
  } catch {
    return '';
  }
};

const buildUrl = (origin, path, pairs = []) => {
  const query = pairs
    .filter(([, value]) => value !== undefined && value !== null && String(value).trim() !== '')
    .map(([key, value]) => `${key}=${encodeURIComponent(String(value).trim())}`)
    .join('&');
  return `${origin}${path}${query ? `?${query}` : ''}`;
};

/** Pagination is only part of the identity from page 2 on ("?page=1" is just the page itself). */
const pageParam = (page) => {
  const n = Number(page);
  return Number.isInteger(n) && n > 1 ? n : undefined;
};

/** Default canonical for any page: origin + clean path. '' when there should be none. */
export const buildPageCanonical = (pathname, { origin = siteOrigin() } = {}) => {
  const path = normalizePath(pathname);
  if (!origin || !path) return '';
  if (NO_CANONICAL_PREFIXES.some((p) => path === p || path.startsWith(`${p}/`))) return '';
  return buildUrl(origin, path);
};

/**
 * Canonical for the shop listing. `category` is the slug from ?category=; `page` the current page.
 * Every filter/sort variant of a category collapses to the same URL; page N (N > 1) keeps its own.
 */
export const buildCategoryCanonical = ({ category, page } = {}, { origin = siteOrigin() } = {}) =>
  origin ? buildUrl(origin, '/category', [['category', category], ['page', pageParam(page)]]) : '';

/** Canonical for the blog index: same policy as the shop listing. */
export const buildBlogCanonical = ({ category, page } = {}, { origin = siteOrigin() } = {}) =>
  origin ? buildUrl(origin, '/blog', [['category', category], ['page', pageParam(page)]]) : '';
