// Page-specific SEO text builders (Task 15.1.1.2).
//
// Pure functions: given API data, return the <title> / meta description strings. They never
// return "undefined" fragments; when the data needed for a sensible string is missing they
// return '' and the caller (<Seo>) falls back to the sitewide default.
import { STORE_NAME } from '../constants/store';
import { siteOrigin } from './canonical';
import {
  DEFAULT_OG_IMAGE_HEIGHT,
  DEFAULT_OG_IMAGE_PATH,
  DEFAULT_OG_IMAGE_WIDTH,
} from '../constants/seo';

// Search engines show roughly 155-160 characters of a description before cutting it off.
export const META_DESCRIPTION_MAX = 155;
// A short_description shorter than this ("جدید!") says too little to be a useful snippet.
export const META_DESCRIPTION_MIN_USEFUL = 50;
// Search terms are user input; keep an absurdly long query from bloating the <title>.
const SEARCH_TERM_MAX = 60;

/** Strip tags, collapse all whitespace (incl. newlines/NBSP) to single spaces, trim. */
const normalizeText = (value) =>
  typeof value === 'string' ? value.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim() : '';

/**
 * Shorten `text` to at most `max` characters, cutting at a WORD boundary and appending '…'.
 * Text already within `max` is returned unchanged (no ellipsis).
 *
 * Persian notes: words are separated by ordinary spaces, so splitting on whitespace is right.
 * The zero-width non-joiner (U+200C, as in «می‌شود» or «دسته‌بندی») is NOT whitespace to
 * JavaScript's \s, so a ZWNJ-joined word is never split in two. Raw UTF-16 length equals
 * character count for Persian script (no astral characters), so counting by length is fine.
 * Only a single word longer than half the budget is hard-cut, since there's no boundary.
 */
export const truncateAtWord = (text, max = META_DESCRIPTION_MAX) => {
  const clean = normalizeText(text);
  if (clean.length <= max) return clean;

  const room = max - 1; // leave one slot for the ellipsis
  let cut = clean.slice(0, room);
  if (!/\s/.test(clean[room])) {
    // The cut landed inside a word: back up to the previous space.
    const lastSpace = cut.search(/\s\S*$/);
    if (lastSpace > room / 2) cut = cut.slice(0, lastSpace);
  }
  cut = cut.replace(/[\uD800-\uDBFF]$/, ''); // never leave half an emoji
  cut = cut.replace(/[\s،,;؛:\-–—.]+$/u, ''); // no dangling punctuation before the ellipsis
  return `${cut}…`;
};

/** "<name> | <brand> | <store>"; the brand segment is omitted when the product has none. */
export const buildProductTitle = (product) => {
  const name = normalizeText(product?.name);
  if (!name) return '';
  return [name, normalizeText(product?.brand?.name), STORE_NAME].filter(Boolean).join(' | ');
};

/**
 * ~150-155 character description for a product page.
 * Prefers the merchant's short_description (cleanly truncated) when it is long enough to be
 * useful on its own; otherwise builds a sentence from the product's name, brand and category.
 */
export const buildProductMetaDescription = (product) => {
  const name = normalizeText(product?.name);
  if (!name) return '';

  const short = normalizeText(product?.short_description);
  if (short.length >= META_DESCRIPTION_MIN_USEFUL) return truncateAtWord(short);

  const brand = normalizeText(product?.brand?.name);
  const category = normalizeText(product?.category?.name);
  const sentence =
    `خرید آنلاین ${name}` +
    (brand ? ` از برند ${brand}` : '') +
    (category ? ` در دسته ${category}` : '') +
    ` از ${STORE_NAME}. مشخصات، قیمت و نظرات کاربران را ببینید و با اطمینان سفارش دهید.`;
  return truncateAtWord(sentence);
};

/** Find a category by slug among top-level categories AND their children. */
export const findCategoryName = (categories, slug) => {
  if (!slug || !Array.isArray(categories)) return '';
  for (const cat of categories) {
    if (cat.slug === slug) return cat.name || '';
    const child = cat.children?.find((c) => c.slug === slug);
    if (child) return child.name || '';
  }
  return '';
};

const searchTerm = (raw) => truncateAtWord(raw, SEARCH_TERM_MAX);

/**
 * Title for the category / product-listing page. `categoryName` is the resolved display name
 * (not the slug), `search` the free-text search term; both optional.
 */
export const buildListingHeading = ({ categoryName, search } = {}) => {
  const term = searchTerm(search);
  const category = normalizeText(categoryName);
  if (term && category) return `نتایج جستجو برای «${term}» در ${category}`;
  if (term) return `نتایج جستجو برای «${term}»`;
  if (category) return category;
  return 'همه محصولات';
};

export const buildListingTitle = (parts = {}) => `${buildListingHeading(parts)} | ${STORE_NAME}`;

export const buildListingDescription = ({ categoryName, search } = {}) => {
  const term = searchTerm(search);
  const category = normalizeText(categoryName);
  let sentence;
  if (term) {
    sentence =
      `نتایج جستجوی «${term}»` +
      (category ? ` در دسته ${category}` : '') +
      ` در فروشگاه ${STORE_NAME}. محصولات مرتبط را مقایسه کنید و با اطمینان سفارش دهید.`;
  } else if (category) {
    sentence =
      `خرید آنلاین ${category} از ${STORE_NAME}؛ محصولات را بر اساس برند، قیمت و رنگ ` +
      'فیلتر کنید و با اطمینان سفارش دهید.';
  } else {
    sentence =
      `همه محصولات آرایشی و بهداشتی ${STORE_NAME} را ببینید؛ بر اساس دسته\u200cبندی، برند ` +
      'و قیمت فیلتر کنید و با اطمینان سفارش دهید.';
  }
  return truncateAtWord(sentence);
};

/** Title / description for the dedicated search-results page (/search?q=). */
export const buildSearchTitle = (query) => {
  const term = searchTerm(query);
  return term ? `نتایج جستجو برای «${term}» | ${STORE_NAME}` : `جستجوی محصولات | ${STORE_NAME}`;
};

export const buildSearchDescription = (query) => {
  const term = searchTerm(query);
  return term
    ? truncateAtWord(
        `نتایج جستجوی «${term}» در فروشگاه ${STORE_NAME}. محصولات مرتبط را مقایسه کنید و با اطمینان سفارش دهید.`,
      )
    : '';
};

// ─── Structured data (Schema.org JSON-LD) — Task 15.1.2 ───────────────────────────────────
//
// Money: the platform transacts in RIAL (ADR 0001, backend/docs/adr/0001-currency-storage.md):
// the API sends plain integer Rial and the ISO 4217 code for it is IRR. Schema.org's `price`
// must be a plain number in the declared `priceCurrency`, so we emit RAW RIAL with 'IRR'.
// "Toman" is only a display unit (1 Toman = 10 Rial) with no ISO code of its own; it must never
// reach structured data, so rialToToman() is deliberately NOT used anywhere in this section.

const PRODUCT_PRICE_CURRENCY = 'IRR';
const IN_STOCK = 'https://schema.org/InStock';
const OUT_OF_STOCK = 'https://schema.org/OutOfStock';

/** Non-negative finite number from a number or numeric string ("4.5"), else null. */
const toAmount = (value) => {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : null;
};

/** Drop undefined / null / '' / empty arrays / empty objects, recursively. */
const compact = (value) => {
  if (Array.isArray(value)) {
    const items = value.map(compact).filter((v) => v !== undefined);
    return items.length ? items : undefined;
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value)
      .map(([k, v]) => [k, compact(v)])
      .filter(([, v]) => v !== undefined);
    return entries.length ? Object.fromEntries(entries) : undefined;
  }
  return value === null || value === undefined || value === '' ? undefined : value;
};

// One origin for every absolute URL we emit (canonical, JSON-LD, Open Graph): VITE_SITE_URL when
// configured, else the current origin. See utils/canonical.js.
const currentOrigin = siteOrigin;

/** Absolute URL for `src`, or '' when it is relative and there is no origin to resolve it. */
const toAbsoluteUrl = (src, origin) => {
  if (!src || typeof src !== 'string') return '';
  try {
    return new URL(src, origin || undefined).href;
  } catch {
    return '';
  }
};

/** A product's canonical storefront URL (the real route is /product/:slug), or ''. */
const productPageUrl = (product, origin) =>
  origin && product?.slug ? `${origin}/product/${encodeURIComponent(product.slug)}` : '';

/**
 * Absolute image URLs, main image first: the same order the product page shows (thumbnail, then
 * the gallery). The API already returns absolute URLs (pinned by a backend test); a relative one
 * is resolved against `origin` rather than emitted as-is, and an unresolvable one is dropped.
 */
const productImageUrls = (product, origin) => [
  ...new Set(
    [product?.thumbnail_url, ...(product?.images ?? []).map((img) => img?.image)]
      .map((src) => toAbsoluteUrl(src, origin))
      .filter(Boolean),
  ),
];

/** Active variants only: the detail endpoint also returns inactive ones. */
const activeVariantsOf = (product) =>
  (Array.isArray(product?.variants) ? product.variants.filter(Boolean) : []).filter(
    (v) => v.is_active !== false,
  );

/** Lowest REGULAR price in Rial ("starting at"), from active variants, else the legacy field. */
const lowestRegularPrice = (product) => {
  const prices = activeVariantsOf(product)
    .map((v) => toAmount(v.price))
    .filter((p) => p !== null);
  return prices.length ? Math.min(...prices) : toAmount(product?.price);
};

/**
 * Schema.org Product (+ Offer / AggregateOffer + AggregateRating) for a product-detail payload.
 * Returns a plain object, or null when the product can't form a valid rich result: no name, or
 * nothing to state about price/availability or ratings (Google needs offers or aggregateRating).
 * Pass `{ origin }` to build absolute URLs without touching `window` (tests, prerendering).
 *
 *  • Variants are the source of truth (Product.price / .stock are a legacy mirror, ADR 0001).
 *    Only ACTIVE variants count: the detail endpoint also returns inactive ones. A product with
 *    no variants at all falls back to the legacy product.price / product.stock.
 *  • Price is each variant's regular `price`, not the flash-sale `effective_price`: a sale price
 *    cached by a search engine would still be advertised after the sale ends, and the regular
 *    price is the same "starting at" figure product cards use (Product.lowest_active_price).
 *  • Active variants at DIFFERING prices → AggregateOffer (lowPrice/highPrice/offerCount);
 *    one variant, or all at the same price → a plain Offer.
 *  • aggregateRating exists only with at least one review and a real rating, never a 0/null stub.
 */
export function buildProductStructuredData(product, { origin = currentOrigin() } = {}) {
  const name = normalizeText(product?.name);
  if (!name) return null;

  const allVariants = Array.isArray(product.variants) ? product.variants.filter(Boolean) : [];
  const variants = activeVariantsOf(product);

  // Availability: any purchasable (active) variant with stock. Legacy stock only when the
  // product has no variants at all.
  const inStock = allVariants.length
    ? variants.some((v) => Number(v.stock) > 0)
    : Number(product.stock) > 0;
  const availability = inStock ? IN_STOCK : OUT_OF_STOCK;

  const prices = variants.map((v) => toAmount(v.price)).filter((p) => p !== null);
  const url = productPageUrl(product, origin) || undefined;

  let offers;
  if (prices.length > 0) {
    const lowPrice = Math.min(...prices);
    const highPrice = Math.max(...prices);
    offers =
      lowPrice !== highPrice
        ? {
            '@type': 'AggregateOffer',
            priceCurrency: PRODUCT_PRICE_CURRENCY,
            lowPrice,
            highPrice,
            offerCount: prices.length,
            availability,
            url,
          }
        : {
            '@type': 'Offer',
            priceCurrency: PRODUCT_PRICE_CURRENCY,
            price: lowPrice,
            availability,
            url,
          };
  } else if (toAmount(product.price) !== null) {
    offers = {
      '@type': 'Offer',
      priceCurrency: PRODUCT_PRICE_CURRENCY,
      price: toAmount(product.price),
      availability,
      url,
    };
  } // else: no price to state; an Offer without one is invalid, so there is no `offers` at all.

  const brandName = normalizeText(product.brand?.name);
  const sku = variants.length === 1 ? normalizeText(variants[0].sku) : '';
  const images = productImageUrls(product, origin);

  const data = {
    '@context': 'https://schema.org/',
    '@type': 'Product',
    name,
    description: normalizeText(product.short_description) || normalizeText(product.description),
    sku, // one variant's SKU only: with several, a product-level SKU would be arbitrary
    brand: brandName ? { '@type': 'Brand', name: brandName } : undefined,
    image: images,
    offers,
  };

  const reviewCount = Number(product.reviews_count);
  const ratingValue = Number(product.rating); // DRF sends the decimal as a string ("4.5")
  if (reviewCount > 0 && Number.isFinite(reviewCount) && ratingValue > 0 && ratingValue <= 5) {
    data.aggregateRating = { '@type': 'AggregateRating', ratingValue, reviewCount };
  }

  // Google's Product rich result needs name AND at least one of offers / review / aggregateRating.
  // A name-only Product is reported as an error in Search Console, so emit nothing instead.
  if (!data.offers && !data.aggregateRating) return null;

  return compact(data);
}

/**
 * JSON for a <script type="application/ld+json"> body. JSON.stringify leaves "<" alone, so a
 * product name containing "</script>" would end the script element early as soon as the markup
 * is serialized (prerender/SSR, innerHTML copy). Escaping "<" (and the two line-separator
 * characters) as \uXXXX keeps the output identical for JSON.parse and safe to embed.
 */
export const serializeJsonLd = (data) =>
  data
    ? JSON.stringify(data)
        .replace(/</g, '\\u003c')
        .replace(/\u2028/g, '\\u2028')
        .replace(/\u2029/g, '\\u2029')
    : '';

// ─── Open Graph — Task 15.1.3 ─────────────────────────────────────────────────────────────

/**
 * The branded fallback share image as { image, imageAlt, imageWidth, imageHeight }, or {} when
 * there is no origin to make it absolute (og:image must be absolute for crawlers to fetch it).
 */
export const defaultOgImage = (origin = currentOrigin()) =>
  origin
    ? {
        image: `${origin}${DEFAULT_OG_IMAGE_PATH}`,
        imageAlt: STORE_NAME,
        imageWidth: DEFAULT_OG_IMAGE_WIDTH,
        imageHeight: DEFAULT_OG_IMAGE_HEIGHT,
      }
    : {};

/**
 * Open Graph fields for a product page (rendered by <Seo og={...}>), or null without a name.
 *
 *  • title is the bare product name (the card shows og:site_name beside it); description is the
 *    SAME buildProductMetaDescription() that feeds <meta name="description">, so they can't drift.
 *  • image: the main product image (same order the page shows) as an absolute URL; a product
 *    with no usable image gets the branded default instead of a missing or broken tag.
 *  • url is the real /product/:slug route, identical to the JSON-LD offer url.
 *  • price: raw Rial with currency IRR (ADR 0001), the same lowest regular price as the JSON-LD;
 *    left out entirely when no price can be determined (never "undefined").
 */
export function buildProductOpenGraph(product, { origin = currentOrigin() } = {}) {
  const name = normalizeText(product?.name);
  if (!name) return null;

  const productImage = productImageUrls(product, origin)[0];
  const price = lowestRegularPrice(product);

  return compact({
    type: 'product',
    title: name,
    description: buildProductMetaDescription(product),
    url: productPageUrl(product, origin),
    ...(productImage ? { image: productImage, imageAlt: name } : defaultOgImage(origin)),
    price: price !== null ? { amount: String(price), currencyCode: PRODUCT_PRICE_CURRENCY } : undefined,
  });
}

/** Canonical for a product page: the real /product/:slug route, never the query string. */
export const buildProductCanonical = (product, { origin = currentOrigin() } = {}) =>
  productPageUrl(product, origin);
