// src/utils/categoryFilters.js
//
// The Category (shop) page keeps ALL of its filter state in the URL query
// string. These helpers read it back into a clean, validated object, and turn
// that object into the product-list API params.
//
// URL param names are the API's own (category, search, brand, color, min_price,
// max_price, skin_type, ..., ordering, page, page_size, flash_sale), so a
// shared link reads like the request it produces. Multi-value filters use ONE
// comma-separated value (?brand=acme,zen&skin_type=oily,dry) — the format the
// backend's ProductFilter splits and matches with __in — never repeated keys.
// Defaults are omitted from the URL (page 1, newest-first, 12 per page, the
// full price range).

import {
  COSMETIC_PARAM_KEYS,
  cosmeticFiltersFromSearchParams,
  cosmeticFiltersToParams,
} from './cosmeticFilters';

export const DEFAULT_SORT = '-created_at';
export const SORT_VALUES = [
  '-created_at', 'created_at', 'price', '-price', '-rating', 'name', '-name',
];
export const PAGE_SIZES = [12, 24, 48];
export const DEFAULT_PAGE_SIZE = 12;
export const PRICE_MIN = 0;
export const PRICE_MAX = 1000;

/** Params "Clear all" removes. (flash_sale and page_size are not filters.) */
export const FILTER_URL_KEYS = [
  'category', 'search', 'brand', 'color', 'min_price', 'max_price',
  'ordering', ...COSMETIC_PARAM_KEYS,
];

const readList = (sp, key) => {
  const values = (sp.get(key) || '').split(',').map((v) => v.trim()).filter(Boolean);
  return [...new Set(values)];
};

const readPrice = (raw, fallback) => {
  if (raw === null || raw === '') return fallback;
  const n = Number(raw);
  return Number.isFinite(n) ? Math.min(Math.max(n, PRICE_MIN), PRICE_MAX) : fallback;
};

/** URLSearchParams -> validated filter state. Junk values fall back to defaults. */
export const parseCategoryFilters = (sp) => {
  let min = readPrice(sp.get('min_price'), PRICE_MIN);
  let max = readPrice(sp.get('max_price'), PRICE_MAX);
  if (min > max) [min, max] = [max, min];

  const page = /^\d+$/.test(sp.get('page') || '') ? Math.max(1, Number(sp.get('page'))) : 1;
  const pageSize = Number(sp.get('page_size'));
  const ordering = sp.get('ordering');

  return {
    category: sp.get('category') || '',
    search: sp.get('search') || '',
    brands: readList(sp, 'brand'),
    colors: readList(sp, 'color'),
    priceRange: { min, max },
    cosmetic: cosmeticFiltersFromSearchParams(sp),
    sortBy: SORT_VALUES.includes(ordering) ? ordering : DEFAULT_SORT,
    page,
    pageSize: PAGE_SIZES.includes(pageSize) ? pageSize : DEFAULT_PAGE_SIZE,
    flashSaleId: sp.get('flash_sale') || '',
  };
};

/**
 * The params that decide WHICH products match (no paging / sort) — what the
 * list fetch and the facet-count fetch share.
 */
export const toApiFilterParams = (f) => {
  const params = {};
  if (f.category) params.category = f.category;
  if (f.search.trim()) params.search = f.search.trim();
  if (f.brands.length) params.brand = f.brands.join(',');
  if (f.colors.length) params.color = f.colors.join(',');
  if (f.priceRange.min > PRICE_MIN) params.min_price = f.priceRange.min;
  if (f.priceRange.max < PRICE_MAX) params.max_price = f.priceRange.max;
  if (f.flashSaleId) params.flash_sale = f.flashSaleId;
  Object.assign(params, cosmeticFiltersToParams(f.cosmetic));
  return params;
};

/** Toggle `value` in `list`, returning the comma-joined URL value (null when empty). */
export const toggleListParam = (list, value) => {
  const next = list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
  return next.length ? next.join(',') : null;
};
