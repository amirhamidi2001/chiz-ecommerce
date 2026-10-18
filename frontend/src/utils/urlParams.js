// src/utils/urlParams.js

/**
 * Apply a set of query-string updates to `prev` and return a NEW
 * URLSearchParams (never mutates `prev`).
 *
 * `updates` maps param name -> string to set, or null / undefined / '' to
 * REMOVE it, so absent params keep meaning "no filter" and URLs stay clean.
 * With `resetPage` (default), the `page` param is dropped too: changing a
 * filter must send the customer back to page 1 of the new results.
 */
export const applyParamUpdates = (prev, updates, { resetPage = true } = {}) => {
  const next = new URLSearchParams(prev);
  Object.entries(updates).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') next.delete(key);
    else next.set(key, String(value));
  });
  if (resetPage) next.delete('page');
  return next;
};
