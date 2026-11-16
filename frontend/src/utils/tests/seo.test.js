// Task 15.1.1.2: page-specific <title>/<meta description> builders.
import { describe, it, expect } from 'vitest';
import { STORE_NAME } from '../../constants/store';
import {
  META_DESCRIPTION_MAX,
  buildListingDescription,
  buildListingHeading,
  buildProductOpenGraph,
  buildProductStructuredData,
  defaultOgImage,
  buildListingTitle,
  buildProductMetaDescription,
  buildProductTitle,
  buildSearchDescription,
  buildSearchTitle,
  findCategoryName,
  truncateAtWord,
} from '../seo';

// Persian text full of ZWNJ-joined words («می‌کند», «دسته‌بندی»), the risky case for splitting.
const LONG_FA =
  'این سرم ویتامین سی با فرمولی سبک و بدون چربی پوست را روشن و یکنواخت می\u200cکند ' +
  'و برای استفاده روزانه در هر نوع پوست مناسب است و لکه\u200cهای تیره را به\u200cتدریج کم می\u200cکند ' +
  'همچنین پوست را در برابر عوامل محیطی محافظت می\u200cکند و ظاهری شاداب می\u200cبخشد';

const wordsOf = (text) => new Set(text.split(/\s+/));

describe('truncateAtWord', () => {
  it('returns text within the limit unchanged, with no ellipsis', () => {
    expect(truncateAtWord('سرم ویتامین سی', 155)).toBe('سرم ویتامین سی');
    const exact = 'ب'.repeat(META_DESCRIPTION_MAX);
    expect(truncateAtWord(exact)).toBe(exact);
  });

  it('never exceeds the limit and ends with an ellipsis when it cuts', () => {
    expect(LONG_FA.length).toBeGreaterThan(META_DESCRIPTION_MAX);
    const out = truncateAtWord(LONG_FA);
    expect(out.length).toBeLessThanOrEqual(META_DESCRIPTION_MAX);
    expect(out.endsWith('…')).toBe(true);
  });

  it('never ends mid-word, whatever the limit (sweeps every cut position, ZWNJ words included)', () => {
    const original = wordsOf(LONG_FA);
    for (let max = 60; max <= 160; max++) {
      const out = truncateAtWord(LONG_FA, max);
      expect(out.length).toBeLessThanOrEqual(max);
      const body = out.slice(0, -1); // drop the ellipsis
      const lastWord = body.split(/\s+/).pop();
      expect(original.has(lastWord), `max=${max}: "${lastWord}" is a fragment`).toBe(true);
    }
  });

  it('cuts exactly at a boundary when the limit lands right after a word', () => {
    // 'abcd efgh ijkl': index 9 is the space after 'efgh'
    expect(truncateAtWord('abcd efgh ijkl', 10)).toBe('abcd efgh…');
  });

  it('removes dangling punctuation before the ellipsis', () => {
    expect(truncateAtWord('سرم، ویتامین سی، عالی', 14)).toBe('سرم، ویتامین…');
  });

  it('hard-cuts only when a single word is longer than the budget', () => {
    const out = truncateAtWord('ا'.repeat(300), 50);
    expect(out).toHaveLength(50);
    expect(out.endsWith('…')).toBe(true);
  });

  it('strips HTML tags and collapses whitespace', () => {
    expect(truncateAtWord('<p>سرم\n\n  ویتامین   <b>سی</b></p>')).toBe('سرم ویتامین سی');
  });

  it('returns an empty string for non-strings', () => {
    expect(truncateAtWord(undefined)).toBe('');
    expect(truncateAtWord(null)).toBe('');
  });
});

describe('buildProductTitle', () => {
  it('is "name | brand | store"', () => {
    expect(buildProductTitle({ name: 'سرم ویتامین سی', brand: { name: 'کلینیک' } })).toBe(
      `سرم ویتامین سی | کلینیک | ${STORE_NAME}`,
    );
  });

  it('omits the brand segment (no empty "|  |") when there is no brand', () => {
    expect(buildProductTitle({ name: 'سرم ویتامین سی' })).toBe(`سرم ویتامین سی | ${STORE_NAME}`);
    expect(buildProductTitle({ name: 'سرم', brand: { name: '' } })).toBe(`سرم | ${STORE_NAME}`);
  });

  it('returns "" (never "undefined | …") without a usable name', () => {
    expect(buildProductTitle(undefined)).toBe('');
    expect(buildProductTitle({})).toBe('');
    expect(buildProductTitle({ name: '   ' })).toBe('');
  });
});

describe('buildProductMetaDescription', () => {
  const base = { name: 'سرم ویتامین سی', brand: { name: 'کلینیک' }, category: { name: 'مراقبت پوست' } };

  it('uses a long short_description, cut cleanly at a word boundary within ~150-155 chars', () => {
    const out = buildProductMetaDescription({ ...base, short_description: LONG_FA });
    expect(out.length).toBeLessThanOrEqual(META_DESCRIPTION_MAX);
    expect(out.length).toBeGreaterThanOrEqual(140);
    expect(out.endsWith('…')).toBe(true);
    expect(wordsOf(LONG_FA).has(out.slice(0, -1).split(/\s+/).pop())).toBe(true);
    expect(LONG_FA.startsWith(out.slice(0, 40))).toBe(true); // it IS the merchant's text
  });

  it('returns a reasonably sized short_description untouched', () => {
    const short = 'سرم سبک و بدون چربی با ویتامین سی برای روشن کردن و شادابی پوست';
    expect(short.length).toBeGreaterThanOrEqual(50);
    expect(buildProductMetaDescription({ ...base, short_description: short })).toBe(short);
  });

  it('falls back to the template when short_description is missing', () => {
    const out = buildProductMetaDescription(base);
    expect(out).toContain('سرم ویتامین سی');
    expect(out).toContain('کلینیک');
    expect(out).toContain('مراقبت پوست');
    expect(out).toContain(STORE_NAME);
    expect(out.length).toBeLessThanOrEqual(META_DESCRIPTION_MAX);
  });

  it('falls back to the template when short_description is too short to be useful', () => {
    const out = buildProductMetaDescription({ ...base, short_description: 'جدید!' });
    expect(out).toContain('کلینیک');
    expect(out).not.toBe('جدید!');
  });

  it('leaves out the brand / category clauses it does not have, with no "undefined"', () => {
    const out = buildProductMetaDescription({ name: 'سرم ویتامین سی' });
    expect(out).not.toMatch(/undefined|null/);
    expect(out).not.toContain('از برند');
    expect(out).not.toContain('در دسته');
    expect(out).toContain('سرم ویتامین سی');
  });

  it('keeps the template within the limit even for a very long product name', () => {
    const name = 'سرم ویتامین سی با فرمول پیشرفته و عصاره\u200cهای گیاهی '.repeat(6).trim();
    const out = buildProductMetaDescription({ ...base, name });
    expect(out.length).toBeLessThanOrEqual(META_DESCRIPTION_MAX);
  });

  it('returns "" without a product name so the sitewide description is used', () => {
    expect(buildProductMetaDescription(undefined)).toBe('');
    expect(buildProductMetaDescription({ short_description: LONG_FA })).toBe('');
  });
});

describe('findCategoryName', () => {
  const cats = [
    { id: 1, name: 'مراقبت پوست', slug: 'skincare', children: [{ id: 2, name: 'سرم', slug: 'serum' }] },
    { id: 3, name: 'آرایش', slug: 'makeup', children: [] },
  ];
  it('finds top-level categories and children by slug', () => {
    expect(findCategoryName(cats, 'skincare')).toBe('مراقبت پوست');
    expect(findCategoryName(cats, 'serum')).toBe('سرم');
  });
  it('returns "" for an unknown slug, empty slug or bad input', () => {
    expect(findCategoryName(cats, 'nope')).toBe('');
    expect(findCategoryName(cats, '')).toBe('');
    expect(findCategoryName(undefined, 'serum')).toBe('');
  });
});

describe('listing and search titles', () => {
  it('category listing: "<category> | store"', () => {
    expect(buildListingTitle({ categoryName: 'مراقبت پوست' })).toBe(`مراقبت پوست | ${STORE_NAME}`);
  });
  it('all products when nothing is selected', () => {
    expect(buildListingTitle({})).toBe(`همه محصولات | ${STORE_NAME}`);
  });
  it('search term, with and without a category', () => {
    expect(buildListingTitle({ search: 'سرم' })).toBe(`نتایج جستجو برای «سرم» | ${STORE_NAME}`);
    expect(buildListingTitle({ search: 'سرم', categoryName: 'مراقبت پوست' })).toBe(
      `نتایج جستجو برای «سرم» در مراقبت پوست | ${STORE_NAME}`,
    );
  });
  it('caps an absurdly long search term', () => {
    const t = buildListingTitle({ search: 'سرم '.repeat(100) });
    expect(t.length).toBeLessThan(120);
  });
  it('search page title/description reflect the query; empty query gets a generic title', () => {
    expect(buildSearchTitle('سرم')).toBe(`نتایج جستجو برای «سرم» | ${STORE_NAME}`);
    expect(buildSearchTitle('')).toBe(`جستجوی محصولات | ${STORE_NAME}`);
    expect(buildSearchDescription('سرم')).toContain('«سرم»');
    expect(buildSearchDescription('')).toBe('');
  });
  it('listing descriptions are within the limit and mention what they describe', () => {
    const d = buildListingDescription({ categoryName: 'مراقبت پوست' });
    expect(d).toContain('مراقبت پوست');
    expect(d.length).toBeLessThanOrEqual(META_DESCRIPTION_MAX);
    expect(buildListingDescription({ search: 'سرم' })).toContain('«سرم»');
    expect(buildListingDescription({})).not.toMatch(/undefined/);
  });
});

// ─── Open Graph (Task 15.1.3) ───────────────────────────────────────────────────────────────
const OG_ORIGIN = 'https://shop.example';
const OG_PRODUCT = {
  name: 'سرم ویتامین سی',
  slug: 'serum-vitamin-c',
  short_description: 'سرم سبک و بدون چربی با ویتامین سی برای روشن کردن و شادابی پوست در استفاده روزانه',
  price: 4_990_000,
  brand: { name: 'کلینیک' },
  category: { name: 'مراقبت پوست' },
  thumbnail_url: `${OG_ORIGIN}/media/products/thumb.jpg`,
  images: [{ id: 1, image: `${OG_ORIGIN}/media/products/a.jpg` }],
  variants: [{ id: 1, sku: 'A', price: 4_990_000, stock: 3, is_active: true }],
};
const og = (overrides = {}) =>
  buildProductOpenGraph({ ...OG_PRODUCT, ...overrides }, { origin: OG_ORIGIN });

describe('buildProductOpenGraph', () => {
  it('describes the product: type, bare name, real route, price in raw Rial', () => {
    expect(og()).toMatchObject({
      type: 'product',
      title: 'سرم ویتامین سی',
      url: `${OG_ORIGIN}/product/serum-vitamin-c`, // the real route, NOT /products/<slug>/
      price: { amount: '4990000', currencyCode: 'IRR' },
    });
  });

  it('reuses buildProductMetaDescription for the og description (one source of truth)', () => {
    expect(og().description).toBe(buildProductMetaDescription({ ...OG_PRODUCT }));
    const templated = og({ short_description: '' });
    expect(templated.description).toBe(buildProductMetaDescription({ ...OG_PRODUCT, short_description: '' }));
    expect(templated.description).toContain('کلینیک');
  });

  it('uses the main product image, as an absolute URL', () => {
    const { image, imageAlt } = og();
    expect(image).toBe(`${OG_ORIGIN}/media/products/thumb.jpg`); // thumbnail = what the page shows first
    expect(() => new URL(image)).not.toThrow();
    expect(imageAlt).toBe('سرم ویتامین سی');
  });

  it('falls back to the first gallery image when there is no thumbnail', () => {
    expect(og({ thumbnail_url: null }).image).toBe(`${OG_ORIGIN}/media/products/a.jpg`);
  });

  it('resolves a RELATIVE image path against the site origin instead of emitting it as-is', () => {
    const { image } = og({ thumbnail_url: null, images: [{ id: 1, image: '/media/products/rel.jpg' }] });
    expect(image).toBe(`${OG_ORIGIN}/media/products/rel.jpg`);
  });

  it.each([
    ['no images at all', { thumbnail_url: null, images: [] }],
    ['images undefined', { thumbnail_url: undefined, images: undefined }],
    ['only empty image fields', { thumbnail_url: '', images: [{ id: 1, image: null }, { id: 2, image: '' }] }],
  ])('falls back to the branded default image for %s', (_label, overrides) => {
    expect(og(overrides)).toMatchObject({
      image: `${OG_ORIGIN}/og-default.jpg`,
      imageAlt: 'Chiz',
      imageWidth: 1200,
      imageHeight: 630,
    });
  });

  it('does not attach the default image’s size to a real product image', () => {
    const data = og();
    expect(data).not.toHaveProperty('imageWidth');
    expect(data).not.toHaveProperty('imageHeight');
  });

  it('states the LOWEST regular price across active variants, ignoring inactive ones', () => {
    const data = og({
      variants: [
        { id: 1, price: 7_500_000, stock: 1, is_active: true },
        { id: 2, price: 4_990_000, stock: 1, is_active: true },
        { id: 3, price: 100_000, stock: 9, is_active: false },
      ],
    });
    expect(data.price).toEqual({ amount: '4990000', currencyCode: 'IRR' });
  });

  it('is never Toman-converted', () => {
    expect(og().price.amount).not.toBe('499000');
  });

  it('uses the legacy price when there are no variants, and omits price when there is none', () => {
    expect(og({ variants: [], price: 3_000_000 }).price.amount).toBe('3000000');
    const data = og({ variants: [], price: null });
    expect(data).not.toHaveProperty('price');
    expect(JSON.stringify(data)).not.toMatch(/undefined|null/);
  });

  it('keeps the price and URL in agreement with the JSON-LD builder', () => {
    const ld = buildProductStructuredData({ ...OG_PRODUCT }, { origin: OG_ORIGIN });
    expect(og().url).toBe(ld.offers.url);
    expect(Number(og().price.amount)).toBe(ld.offers.price);
  });

  it('returns null without a product name, so nothing is rendered', () => {
    expect(buildProductOpenGraph(undefined)).toBeNull();
    expect(og({ name: '  ' })).toBeNull();
  });
});

describe('defaultOgImage', () => {
  it('is an absolute URL on the given origin with the standard 1200x630 size', () => {
    expect(defaultOgImage(OG_ORIGIN)).toEqual({
      image: `${OG_ORIGIN}/og-default.jpg`,
      imageAlt: 'Chiz',
      imageWidth: 1200,
      imageHeight: 630,
    });
  });
  it('is empty when there is no origin to make it absolute (a relative og:image would not work)', () => {
    expect(defaultOgImage('')).toEqual({});
  });
});

describe('buildListingHeading', () => {
  it('is the bare category name / search heading, and buildListingTitle adds only the store name', () => {
    expect(buildListingHeading({ categoryName: 'مراقبت پوست' })).toBe('مراقبت پوست');
    expect(buildListingHeading({})).toBe('همه محصولات');
    expect(buildListingHeading({ search: 'سرم' })).toBe('نتایج جستجو برای «سرم»');
    expect(buildListingTitle({ categoryName: 'مراقبت پوست' })).toBe(
      `${buildListingHeading({ categoryName: 'مراقبت پوست' })} | ${STORE_NAME}`,
    );
  });
});
