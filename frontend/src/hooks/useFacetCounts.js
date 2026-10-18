// src/hooks/useFacetCounts.js
import { useEffect, useRef, useState } from 'react';
import { getProductFacetCounts } from '../services/api';

export const FACET_COUNTS_DEBOUNCE_MS = 300;

/**
 * Facet counts ("Oily (12)") for the current FILTER params.
 *
 * Pass only the params that change which products match — category, brand,
 * search, skin_type, ... — NOT page, page size or sort: those don't change the
 * counts, and leaving them out is what stops the endpoint being hit when the
 * customer just turns a page or re-sorts.
 *
 * It refetches whenever the filters change, i.e. alongside the product-list
 * fetch, with two differences:
 *  - the first fetch is immediate, later ones are debounced, so a burst of
 *    changes (ticking several boxes, typing in the search box — which already
 *    refetches the list per keystroke) makes one request, not one each;
 *  - a superseded request is aborted and its late response ignored.
 *
 * Returns the latest counts, or null before the first response and after a
 * failed request. Counts are a nicety: a failure (or a missing endpoint)
 * degrades to "no counts" and never affects the listing.
 *
 * @param {Object|null} filterParams  null/undefined disables fetching
 */
export function useFacetCounts(filterParams, { delay = FACET_COUNTS_DEBOUNCE_MS } = {}) {
  // Stable value-based key so a new-but-equal params object doesn't refetch.
  const key = filterParams
    ? JSON.stringify(Object.entries(filterParams).sort(([a], [b]) => (a < b ? -1 : 1)))
    : null;
  const [counts, setCounts] = useState(null);
  const isFirstFetch = useRef(true);

  useEffect(() => {
    if (key === null) return undefined;

    const controller = new AbortController();
    const wait = isFirstFetch.current ? 0 : delay;
    isFirstFetch.current = false;

    const timer = setTimeout(() => {
      const params = Object.fromEntries(JSON.parse(key));
      Promise.resolve()
        .then(() => getProductFacetCounts(params, { signal: controller.signal }))
        .then(({ data }) => {
          if (!controller.signal.aborted) setCounts(data ?? null);
        })
        .catch(() => {
          if (!controller.signal.aborted) setCounts(null);
        });
    }, wait);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [key, delay]);

  return counts;
}
