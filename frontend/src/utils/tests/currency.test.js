import { afterEach, describe, it, expect, vi } from 'vitest';
import { formatToman, rialToToman } from '../money';

// Task 14.1.2.3 — formatToman() / rialToToman() acceptance criteria, plus a
// permanent guard that the whole frontend keeps using them (the sweep below).
// Both functions live in money.js — the SPA's one money utility (ADR 0001) —
// rather than in a second currency.js that would have to be kept in step.
describe('Task 14.1.2.3 — acceptance criteria', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('1. formatToman(299900) -> "29,990 تومان"', () => {
    expect(formatToman(299_900)).toBe('29,990 تومان');
  });

  it('2. formatToman(0) -> "0 تومان" (and never "-0")', () => {
    expect(formatToman(0)).toBe('0 تومان');
    expect(formatToman(-0)).toBe('0 تومان');
    expect(rialToToman(-0)).toBe(0);
    expect(Object.is(rialToToman(-0), -0)).toBe(false);
  });

  it('3. missing / non-numeric values show the empty state: never throw, never "NaN"', () => {
    for (const bad of [null, undefined, '', NaN, Infinity, -Infinity, 'abc']) {
      let out;
      expect(() => {
        out = formatToman(bad);
      }).not.toThrow();
      expect(out).toBe('—');
      expect(out).not.toMatch(/NaN|undefined|null|Infinity/);
    }
  });

  it('4. negative amounts keep their sign (refund / discount lines)', () => {
    expect(formatToman(-50_000)).toBe('-5,000 تومان');
    expect(formatToman(-299_900)).toBe('-29,990 تومان');
    expect(formatToman(-299_900, { withUnit: false })).toBe('-29,990');
    expect(rialToToman(-50_000)).toBe(-5_000);
  });

  it('5. rialToToman divides by 10 (exact, for every amount the system can hold)', () => {
    expect(rialToToman(299_900)).toBe(29_990);
    expect(rialToToman(10)).toBe(1);
    expect(rialToToman(0)).toBe(0);
    expect(rialToToman(100_000_000_000)).toBe(10_000_000_000); // MAX_RIAL_AMOUNT
    expect(rialToToman(null)).toBe(0); // "no amount" contributes nothing to a calculation
    expect(rialToToman(undefined)).toBe(0);
    expect(rialToToman('')).toBe(0);
  });

  describe('5b. a non-multiple of 10 Rial is a BUG upstream, never silently floored', () => {
    // 123,456 Rial = 12,345.6 Toman. Flooring would display 12,345 while the
    // gateway charges 12,345.6 — i.e. show LESS than is charged (ADR 0001 §6).
    it('dev/test: throws', () => {
      expect(() => rialToToman(123_456)).toThrow(/whole number of Toman/);
      expect(() => rialToToman(-123_456)).toThrow(/whole number of Toman/);
      expect(() => rialToToman(12.5)).toThrow(/integer number of Rial/);
      expect(() => rialToToman(NaN)).toThrow(/not a number of Rial/);
      expect(() => formatToman(123_456)).toThrow();
    });

    it('production: reports loudly and rounds AWAY from zero (never down)', () => {
      vi.stubEnv('PROD', true);
      const report = vi.spyOn(console, 'error').mockImplementation(() => {});
      expect(rialToToman(123_456)).toBe(12_346); // not 12,345
      expect(rialToToman(-123_456)).toBe(-12_346); // magnitude never shrinks
      expect(formatToman(123_456)).toBe('12,346 تومان');
      expect(formatToman(-123_456)).toBe('-12,346 تومان');
      expect(rialToToman(NaN)).toBe(0);
      expect(report).toHaveBeenCalled();
    });
  });

  it('digit script is a separate, opt-in concern (persianDigits)', () => {
    expect(formatToman(299_900)).toBe('29,990 تومان');
    expect(formatToman(299_900, { persianDigits: true })).toBe('۲۹,۹۹۰ تومان');
    expect(formatToman(-50_000, { persianDigits: true })).toBe('-۵,۰۰۰ تومان');
  });
});


// ── The sweep, as a test: no ad-hoc price formatting anywhere in src/ ────────
// A one-off grep proves today; this keeps "formatToman() is the ONLY way a
// price is displayed" true. It reads every non-test source file as raw text.
const SOURCES = import.meta.glob('/src/**/*.{js,jsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
});

const stripComments = (code) =>
  code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');

const productionFiles = Object.entries(SOURCES)
  .filter(([path]) => !/\/(__tests__|tests)\//.test(path) && !/\.test\.[jt]sx?$/.test(path))
  .filter(([path]) => !path.endsWith('/src/utils/money.js'))
  .map(([path, code]) => [path.replace('/src/', ''), stripComments(code)]);

const offenders = (regex) =>
  productionFiles
    .flatMap(([path, code]) =>
      code
        .split('\n')
        .map((line, i) => (regex.test(line) ? `${path}:${i + 1}: ${line.trim().slice(0, 90)}` : null))
        .filter(Boolean)
    );

describe('Task 14.1.2.3 — the sweep: nothing formats a price except formatToman()', () => {
  it('scans a realistic number of production files', () => {
    expect(productionFiles.length).toBeGreaterThan(60);
  });

  it('no .toFixed(2) (the dollars-and-cents idiom)', () => {
    expect(offenders(/\.toFixed\(\s*2\s*\)/)).toEqual([]);
  });

  it('no Intl currency formatting and no Intl.NumberFormat outside money.js', () => {
    expect(offenders(/style:\s*['"]currency['"]|\bcurrency\s*:|Intl\.NumberFormat/)).toEqual([]);
  });

  it('no "$" used as a currency symbol (literal, or before a digit / ${interpolation})', () => {
    expect(
      offenders(/['"`]\$['"`]|\$\$\{|>\s*\$\s*\{|\$\s?\d|['"`]\s*\$\s*['"`]\s*\+|\+\s*['"`]\$/)
    ).toEqual([]);
  });

  it('no dollar-sign icon or USD/EUR labels', () => {
    expect(offenders(/bi-currency-dollar|\bUSD\b|\bEUR\b|€|£/)).toEqual([]);
  });

  it('no money arithmetic by 10 outside money.js (Rial<->Toman is converted in one place)', () => {
    expect(
      offenders(/\b(price|total|amount|subtotal|rial|toman|cost|fee|discount|tax)\w*\s*[/*]\s*10\b/i)
    ).toEqual([]);
  });

  it('every local money helper is a pure alias of formatToman (no private formatter)', () => {
    const defs = productionFiles.flatMap(([path, code]) =>
      [...code.matchAll(/(?:const|let|function)\s+(fmt|formatPrice|fmtMoney|money|formatMoney|formatCurrency)\b[^\n;]*/g)].map(
        (m) => `${path}: ${m[0].trim()}`
      )
    );
    expect(defs.length).toBeGreaterThan(5); // the aliases exist...
    const bad = defs.filter((d) => !/=>\s*formatToman\(\s*\w+\s*\)\s*$/.test(d));
    expect(bad).toEqual([]); // ...and each one just delegates
  });
});
