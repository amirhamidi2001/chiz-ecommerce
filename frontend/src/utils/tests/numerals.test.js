import { afterEach, describe, it, expect, vi } from 'vitest';
import { formatToman } from '../money';
import {
  formatRating,
  formatReviewCount,
  localizeDigits,
  numeralStyleFor,
  toPersianDigits,
  toWesternDigits,
  usesPersianDigits,
} from '../numerals';
import {
  DEFAULT_NUMERAL_STYLE,
  NUMERAL_CONTEXT,
  NUMERAL_STYLE,
  NUMERAL_STYLE_BY_CONTEXT,
} from '../../constants/numerals';

const PERSIAN = /[۰-۹]/;

describe('toPersianDigits', () => {
  it('converts every Western digit', () => {
    expect(toPersianDigits('12345')).toBe('۱۲۳۴۵');
    expect(toPersianDigits('0123456789')).toBe('۰۱۲۳۴۵۶۷۸۹');
  });

  it('converts only the digits and leaves every other character untouched', () => {
    expect(toPersianDigits('Order #12345')).toBe('Order #۱۲۳۴۵');
    expect(toPersianDigits('29,990 تومان')).toBe('۲۹,۹۹۰ تومان');
    expect(toPersianDigits('-5,000.5')).toBe('-۵,۰۰۰.۵');
    expect(toPersianDigits('no digits here')).toBe('no digits here');
  });

  it('returns "" for null / undefined without throwing', () => {
    expect(() => toPersianDigits(null)).not.toThrow();
    expect(toPersianDigits(null)).toBe('');
    expect(toPersianDigits(undefined)).toBe('');
  });

  it('accepts numbers (including 0) and is idempotent', () => {
    expect(toPersianDigits(0)).toBe('۰');
    expect(toPersianDigits(4.5)).toBe('۴.۵');
    expect(toPersianDigits('۱۲۳')).toBe('۱۲۳');
    expect(toPersianDigits(toPersianDigits('42'))).toBe('۴۲');
  });
});

describe('toWesternDigits (the inverse, for parsing typed input)', () => {
  it('maps Persian and Arabic-Indic digits back to 0-9', () => {
    expect(toWesternDigits('۰۱۲۳۴۵۶۷۸۹')).toBe('0123456789');
    expect(toWesternDigits('٠١٢٣٤٥٦٧٨٩')).toBe('0123456789');
    expect(toWesternDigits('Order #۱۲۳')).toBe('Order #123');
    expect(toWesternDigits(null)).toBe('');
  });

  it('round-trips', () => {
    expect(toWesternDigits(toPersianDigits('1234567890'))).toBe('1234567890');
  });
});

describe('formatToman — the persianDigits toggle', () => {
  it('persianDigits: true gives the Persian-digit version of the formatted string', () => {
    expect(formatToman(299_900, { persianDigits: true })).toBe(toPersianDigits(formatToman(299_900)));
    expect(formatToman(299_900, { persianDigits: true })).toBe('۲۹,۹۹۰ تومان');
  });

  it('the DEFAULT stays Western digits (prices: exact amounts read clearest)', () => {
    expect(formatToman(299_900)).toBe('29,990 تومان');
    expect(formatToman(299_900)).not.toMatch(PERSIAN);
    expect(formatToman(299_900, { persianDigits: false })).toBe('29,990 تومان');
  });

  it('composes with the other options and keeps the sign / empty state', () => {
    expect(formatToman(299_900, { persianDigits: true, unit: 'en' })).toBe('۲۹,۹۹۰ Toman');
    expect(formatToman(299_900, { persianDigits: true, withUnit: false })).toBe('۲۹,۹۹۰');
    expect(formatToman(-50_000, { persianDigits: true })).toBe('-۵,۰۰۰ تومان');
    expect(formatToman(0, { persianDigits: true })).toBe('۰ تومان');
    expect(formatToman(null, { persianDigits: true })).toBe('—');
  });

  it('follows the configured PRICE style — one table controls it, an explicit option overrides', async () => {
    vi.resetModules();
    vi.doMock('../../constants/numerals', async (importOriginal) => {
      const real = await importOriginal();
      return {
        ...real,
        NUMERAL_STYLE_BY_CONTEXT: { ...real.NUMERAL_STYLE_BY_CONTEXT, price: real.NUMERAL_STYLE.PERSIAN },
      };
    });
    const flipped = await import('../money');
    expect(flipped.formatToman(299_900)).toBe('۲۹,۹۹۰ تومان'); // config says price -> persian
    expect(flipped.formatToman(299_900, { persianDigits: false })).toBe('29,990 تومان'); // explicit wins
    vi.doUnmock('../../constants/numerals');
    vi.resetModules();
  });
});

describe('numeral style configuration (per context, not one global choice)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('the site-wide default is western', () => {
    expect(DEFAULT_NUMERAL_STYLE).toBe('western');
    expect(DEFAULT_NUMERAL_STYLE).toBe(NUMERAL_STYLE.WESTERN);
  });

  it('prices are western; ratings and review counts are persian', () => {
    expect(numeralStyleFor(NUMERAL_CONTEXT.PRICE)).toBe('western');
    expect(numeralStyleFor(NUMERAL_CONTEXT.RATING)).toBe('persian');
    expect(numeralStyleFor(NUMERAL_CONTEXT.REVIEW_COUNT)).toBe('persian');
    expect(usesPersianDigits(NUMERAL_CONTEXT.PRICE)).toBe(false);
    expect(usesPersianDigits(NUMERAL_CONTEXT.RATING)).toBe(true);
  });

  it('an unlisted or missing context falls back to the default', () => {
    expect(numeralStyleFor('something-new')).toBe(DEFAULT_NUMERAL_STYLE);
    expect(numeralStyleFor(undefined)).toBe(DEFAULT_NUMERAL_STYLE);
    expect(localizeDigits(128, 'something-new')).toBe('128');
  });

  it('every configured context names a valid style, and every context has a row', () => {
    const valid = new Set(Object.values(NUMERAL_STYLE));
    for (const style of Object.values(NUMERAL_STYLE_BY_CONTEXT)) expect(valid.has(style)).toBe(true);
    for (const ctx of Object.values(NUMERAL_CONTEXT)) expect(NUMERAL_STYLE_BY_CONTEXT).toHaveProperty(ctx);
  });

  it('the configuration objects cannot be mutated at runtime', () => {
    expect(Object.isFrozen(NUMERAL_STYLE_BY_CONTEXT)).toBe(true);
    expect(Object.isFrozen(NUMERAL_CONTEXT)).toBe(true);
  });
});

describe('the chosen non-monetary contexts', () => {
  it('formatRating', () => {
    expect(formatRating(4.5)).toBe('۴.۵');
    expect(formatRating('4.0')).toBe('۴.۰');
    expect(formatRating(5)).toBe('۵');
    expect(formatRating(null)).toBe('');
  });

  it('formatReviewCount', () => {
    expect(formatReviewCount(128)).toBe('۱۲۸');
    expect(formatReviewCount(0)).toBe('۰');
    expect(formatReviewCount('1204')).toBe('۱۲۰۴');
    expect(formatReviewCount(undefined)).toBe('');
  });

  it('localizeDigits applies the style of the context it is given', () => {
    expect(localizeDigits(128, NUMERAL_CONTEXT.REVIEW_COUNT)).toBe('۱۲۸');
    expect(localizeDigits(128, NUMERAL_CONTEXT.PRICE)).toBe('128');
    expect(localizeDigits(null, NUMERAL_CONTEXT.RATING)).toBe('');
  });
});


// ── The sweep, as a test: storefront ratings / review counts go through the helper ──
// Digit script is a per-context decision (constants/numerals.js). A component
// that renders `{product.rating}` or `{product.reviews_count}` directly would
// silently ignore it, so this reads every source file and fails on that.
const SOURCES = import.meta.glob('/src/**/*.{js,jsx}', { query: '?raw', import: 'default', eager: true });

// Deliberately NOT converted (documented decisions, not oversights):
//   • admin pages: staff chrome stays Western;
//   • the account dashboard's stat tiles, where "Reviews" sits in one row beside
//     the Orders and Wishlist counts — converting only one tile would mix scripts.
const EXEMPT = [/\/pages\/admin\//, /\/components\/admin\//, /\/pages\/Account\.jsx$/, /\/components\/AccountSidebar\.jsx$/];

const strip = (code) => code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');

describe('storefront ratings and review counts are rendered through the numeral helpers', () => {
  const files = Object.entries(SOURCES).filter(
    ([path]) =>
      path.endsWith('.jsx') &&
      !/\/(__tests__|tests)\//.test(path) &&
      !EXEMPT.some((re) => re.test(path))
  );

  it('scans a realistic number of components', () => {
    expect(files.length).toBeGreaterThan(30);
  });

  it('no JSX text interpolation of a raw rating or reviews_count', () => {
    // `{product.rating}` / `{p.reviews_count ?? 0}` as text. `rating={...}` props
    // (preceded by "=") are fine: they hand the number to a component.
    const raw = /(?<!=)\{\s*[\w.?]+\.(?:reviews_count|rating)\b(?![\w(])[^}]*\}/;
    const offenders = files.flatMap(([path, code]) =>
      strip(code)
        .split('\n')
        .map((line, i) => (raw.test(line) && !/format(Rating|ReviewCount)/.test(line) ? `${path}:${i + 1}: ${line.trim().slice(0, 90)}` : null))
        .filter(Boolean)
    );
    expect(offenders).toEqual([]);
  });

  it('the converted sites really do use the helpers (the sweep above is not vacuous)', () => {
    const using = files.filter(([, code]) => /formatReviewCount\(|formatRating\(/.test(code)).map(([p]) => p);
    expect(using.length).toBeGreaterThanOrEqual(8);
  });

  it('only numerals.js defines a Persian-digit table (one source of truth)', () => {
    const digitChars = /[۰-۹٠-٩]/;
    const holders = Object.entries(SOURCES)
      .filter(([path]) => !/\/(__tests__|tests)\//.test(path))
      .filter(([, code]) => digitChars.test(strip(code)))
      .map(([path]) => path);
    expect(holders).toEqual(['/src/utils/numerals.js']);
  });
});
