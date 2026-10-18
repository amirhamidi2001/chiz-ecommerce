// src/utils/cosmeticFilters.js
//
// Cosmetics-specific product filters (skin type, hair type, SPF, gender and
// the three certification flags) and their mapping to the product-list API:
//
//   skin_type, hair_type   comma-separated, e.g. ?skin_type=oily,dry   (OR within a facet)
//   gender                 single value,    e.g. ?gender=female
//   min_spf, max_spf       whole numbers
//   is_cruelty_free / is_vegan / is_organic
//                          sent ONLY as "true". Never "false": the backend
//                          treats an absent parameter as "no restriction",
//                          while ?is_vegan=false would mean "only products
//                          that are NOT vegan".
//
// Different facets combine with AND on the backend.
//
// The option values are the backend's choice values (shop.models.SkinType,
// HairType, ProductGender) — the backend filters with exact matches, so they
// must be spelled exactly.

export const SKIN_TYPE_OPTIONS = [
  { value: 'oily', label: 'Oily' },
  { value: 'dry', label: 'Dry' },
  { value: 'combination', label: 'Combination' },
  { value: 'sensitive', label: 'Sensitive' },
  { value: 'normal', label: 'Normal' },
  { value: 'all', label: 'All Skin Types' },
];

export const HAIR_TYPE_OPTIONS = [
  { value: 'straight', label: 'Straight' },
  { value: 'wavy', label: 'Wavy' },
  { value: 'curly', label: 'Curly' },
  { value: 'coily', label: 'Coily' },
  { value: 'all', label: 'All Hair Types' },
];

export const GENDER_OPTIONS = [
  { value: 'unisex', label: 'Unisex' },
  { value: 'female', label: 'Female' },
  { value: 'male', label: 'Male' },
];

export const CERTIFICATION_OPTIONS = [
  { key: 'is_cruelty_free', label: 'Cruelty-Free' },
  { key: 'is_vegan', label: 'Vegan' },
  { key: 'is_organic', label: 'Organic' },
];

/** The unfiltered state. Treat as immutable (never mutate its arrays). */
export const EMPTY_COSMETIC_FILTERS = Object.freeze({
  skin_type: [],
  hair_type: [],
  gender: '',
  min_spf: '',
  max_spf: '',
  is_cruelty_free: false,
  is_vegan: false,
  is_organic: false,
});

const LIST_FACETS = {
  skin_type: { options: SKIN_TYPE_OPTIONS, title: 'Skin Type' },
  hair_type: { options: HAIR_TYPE_OPTIONS, title: 'Hair Type' },
};
const BOOLEAN_KEYS = CERTIFICATION_OPTIONS.map((o) => o.key);
const COSMETIC_KEYS = [
  'skin_type', 'hair_type', 'gender', 'min_spf', 'max_spf', ...BOOLEAN_KEYS,
];

// ─── Small helpers ────────────────────────────────────────────────────────────

/**
 * Keep only known option values, in the options' own order. The canonical
 * order means the same selection always produces the same request URL
 * regardless of click order (and so the same server-side cache key).
 */
export const canonicalList = (list, options) => {
  const wanted = new Set(Array.isArray(list) ? list : []);
  return options.filter((o) => wanted.has(o.value)).map((o) => o.value);
};

/** Add `value` to `list` if absent, remove it if present (canonical order). */
export const toggleListValue = (list, value, options) => {
  const current = canonicalList(list, options);
  return canonicalList(
    current.includes(value) ? current.filter((v) => v !== value) : [...current, value],
    options,
  );
};

export const SPF_MAX = 100; // mirrors Product.spf's MaxValueValidator(100)

/**
 * Parse an SPF input. '' for blank, a whole number from 0 to 100 as a string,
 * or null if the text is not a valid SPF (negative, fractional, non-numeric,
 * or above 100).
 */
export const parseSpf = (raw) => {
  const text = String(raw ?? '').trim();
  if (text === '') return '';
  if (!/^\d+$/.test(text)) return null;
  const n = Number(text);
  return n <= SPF_MAX ? String(n) : null;
};

const validGender = (g) => GENDER_OPTIONS.some((o) => o.value === g);

/** Coerce arbitrary input into a clean, complete filter-state object. */
export const normalizeCosmeticFilters = (raw = {}) => ({
  skin_type: canonicalList(raw.skin_type, SKIN_TYPE_OPTIONS),
  hair_type: canonicalList(raw.hair_type, HAIR_TYPE_OPTIONS),
  gender: validGender(raw.gender) ? raw.gender : '',
  // A minimum of 0 means "no minimum". Sending min_spf=0 would NOT be a
  // no-op: Product.spf is nullable (None = not applicable, e.g. most haircare)
  // and `spf >= 0` excludes those NULL rows.
  min_spf: parseSpf(raw.min_spf) === '0' ? '' : (parseSpf(raw.min_spf) ?? ''),
  max_spf: parseSpf(raw.max_spf) ?? '',
  is_cruelty_free: raw.is_cruelty_free === true,
  is_vegan: raw.is_vegan === true,
  is_organic: raw.is_organic === true,
});

// ─── State -> API query params ────────────────────────────────────────────────

/**
 * The query params for the product-list endpoint. Only filters that are
 * actually set are included; every unset/false filter is OMITTED entirely.
 */
export const cosmeticFiltersToParams = (filters) => {
  const f = normalizeCosmeticFilters(filters);
  const params = {};
  if (f.skin_type.length) params.skin_type = f.skin_type.join(',');
  if (f.hair_type.length) params.hair_type = f.hair_type.join(',');
  if (f.gender) params.gender = f.gender;
  if (f.min_spf !== '') params.min_spf = Number(f.min_spf);
  if (f.max_spf !== '') params.max_spf = Number(f.max_spf);
  BOOLEAN_KEYS.forEach((key) => {
    if (f[key]) params[key] = 'true';
  });
  return params;
};

// ─── URL search params <-> state (for URL-driven pages) ──────────────────────

/** Read filter state from a URLSearchParams. Unknown values are ignored. */
export const cosmeticFiltersFromSearchParams = (sp) => {
  const list = (key) => (sp.get(key) || '').split(',').map((v) => v.trim()).filter(Boolean);
  return normalizeCosmeticFilters({
    skin_type: list('skin_type'),
    hair_type: list('hair_type'),
    gender: sp.get('gender') || '',
    min_spf: sp.get('min_spf') || '',
    max_spf: sp.get('max_spf') || '',
    is_cruelty_free: sp.get('is_cruelty_free') === 'true',
    is_vegan: sp.get('is_vegan') === 'true',
    is_organic: sp.get('is_organic') === 'true',
  });
};

/**
 * Turn a state patch (e.g. { skin_type: ['oily'], is_vegan: false }) into URL
 * param updates: a string to set, or null to REMOVE the param.
 */
export const cosmeticPatchToUrlUpdates = (patch) => {
  const updates = {};
  Object.entries(patch).forEach(([key, value]) => {
    if (key === 'skin_type' || key === 'hair_type') {
      const list = canonicalList(value, LIST_FACETS[key].options);
      updates[key] = list.length ? list.join(',') : null;
    } else if (BOOLEAN_KEYS.includes(key)) {
      updates[key] = value === true ? 'true' : null;
    } else if (key === 'gender') {
      updates[key] = validGender(value) ? value : null;
    } else if (key === 'min_spf' || key === 'max_spf') {
      const normalized = normalizeCosmeticFilters({ [key]: value })[key];
      updates[key] = normalized === '' ? null : normalized;
    }
  });
  return updates;
};

// ─── Active filters (count + removable chips) ────────────────────────────────

/**
 * Number of ACTIVE FILTER GROUPS among the cosmetic facets (the same
 * one-per-group counting SearchResults uses for price): skin type, hair type,
 * gender and SPF count once each; every certification counts on its own.
 */
export const countActiveCosmeticFilters = (filters) => {
  const f = normalizeCosmeticFilters(filters);
  let count = 0;
  if (f.skin_type.length) count++;
  if (f.hair_type.length) count++;
  if (f.gender) count++;
  if (f.min_spf !== '' || f.max_spf !== '') count++;
  BOOLEAN_KEYS.forEach((key) => { if (f[key]) count++; });
  return count;
};

/**
 * Removable chips, one per selected value: [{ key, type, value, patch }].
 * `patch` is the state change that removes just that chip.
 */
export const getActiveCosmeticChips = (filters) => {
  const f = normalizeCosmeticFilters(filters);
  const chips = [];

  Object.entries(LIST_FACETS).forEach(([facet, { options, title }]) => {
    f[facet].forEach((value) => {
      chips.push({
        key: `${facet}:${value}`,
        type: title,
        value: options.find((o) => o.value === value).label,
        patch: { [facet]: f[facet].filter((v) => v !== value) },
      });
    });
  });

  if (f.gender) {
    chips.push({
      key: 'gender',
      type: 'Gender',
      value: GENDER_OPTIONS.find((o) => o.value === f.gender).label,
      patch: { gender: '' },
    });
  }

  if (f.min_spf !== '' || f.max_spf !== '') {
    const value =
      f.min_spf !== '' && f.max_spf !== '' ? `${f.min_spf} – ${f.max_spf}`
        : f.min_spf !== '' ? `${f.min_spf}+`
          : `up to ${f.max_spf}`;
    chips.push({ key: 'spf', type: 'SPF', value, patch: { min_spf: '', max_spf: '' } });
  }

  CERTIFICATION_OPTIONS.forEach(({ key, label }) => {
    if (f[key]) {
      chips.push({ key, type: 'Certification', value: label, patch: { [key]: false } });
    }
  });

  return chips;
};

/** The URL params owned by the cosmetic filters (for clearing them). */
export const COSMETIC_PARAM_KEYS = COSMETIC_KEYS;
