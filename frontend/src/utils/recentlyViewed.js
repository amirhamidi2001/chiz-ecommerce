/**
 * Recently-viewed products — device-local (localStorage) tracking.
 *
 * DECISION (Option A, localStorage-only): works for every visitor including
 * guests, needs zero backend changes, and the feature's value (jogging a
 * customer's memory of what they just looked at) doesn't depend on
 * cross-device sync. Trade-offs: the list is per-browser (a phone's history
 * won't appear on a laptop) and disappears if the user clears site data.
 * A backend-persisted version (RecentlyViewedProduct + record-view/ and
 * recently-viewed/ endpoints) remains a reasonable follow-up IF user research
 * shows the device-local limit is costing conversions — it would still need
 * this module as the guest fallback, so it is intentionally not built yet.
 *
 * This module is the single source of truth: ProductDetails.jsx records views
 * with addRecentlyViewed(); any consumer (e.g. the homepage section) reads via
 * getRecentlyViewed(). Consumers that render the list ON a product page must
 * exclude the product currently being viewed.
 *
 * Stored entries are display snapshots ({id, slug, name, thumbnail, price,
 * viewedAt}) and can go stale (renamed, repriced, deleted product). Treat
 * `price` as a hint, never as the source of truth for money.
 *
 * All storage access is wrapped in try/catch: localStorage can throw in
 * Safari private mode, when quota is full, or when storage is disabled, and a
 * non-critical feature must never crash the page.
 */

export const STORAGE_KEY = 'chiz_recently_viewed';
export const MAX_ITEMS = 20;

/** Most-recent-first list of viewed products; [] if empty, unreadable or malformed. */
export function getRecentlyViewed() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    // Valid JSON of the wrong shape (e.g. "{}" or "null") is also "malformed".
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    return [];
  }
}

/**
 * Record a view: moves the product to the front (no duplicates, viewedAt
 * refreshed), caps the list at MAX_ITEMS, persists. Never throws.
 *
 * Accepts the API product shape: the thumbnail is read from `thumbnail_url`
 * (what ProductListSerializer/ProductDetailSerializer return), falling back to
 * `thumbnail`.
 */
export function addRecentlyViewed(product) {
  if (!product || product.id == null) return;
  try {
    const existing = getRecentlyViewed();
    const filtered = existing.filter((p) => p && p.id !== product.id);
    const updated = [
      {
        id: product.id,
        slug: product.slug,
        name: product.name,
        thumbnail: product.thumbnail_url ?? product.thumbnail ?? null,
        price: product.price,
        viewedAt: Date.now(),
      },
      ...filtered,
    ].slice(0, MAX_ITEMS);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch (e) {
    // Private-browsing mode / quota exceeded: fail silently.
  }
}

export function clearRecentlyViewed() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch (e) {
    /* ignore */
  }
}
