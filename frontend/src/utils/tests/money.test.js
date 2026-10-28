import { describe, it, expect } from 'vitest';
import {
  formatToman,
  MAX_RIAL_AMOUNT,
  parseTomanInput,
  percentOfRial,
  rialToToman,
  roundToWholeToman,
  toTomanNumber,
  tomanToRial,
} from '../money';

// GOLDEN VECTORS — identical to backend/core/tests/test_money.py and ADR 0001 §5.
const ROUND_VECTORS = [
  [0, 0], [4, 0], [5, 10], [14, 10], [15, 20], [125, 130], [123456, 123460], [185184, 185180],
];

describe('roundToWholeToman (integer-only, ties up)', () => {
  it.each(ROUND_VECTORS)('%i Rial -> %i', (input, expected) => {
    expect(roundToWholeToman(input)).toBe(expected);
  });

  it('matches the ADR worked checkout (10% tax / 15% coupon on 1,234,560)', () => {
    expect(percentOfRial(1_234_560, 1000)).toBe(123_460);
    expect(percentOfRial(1_234_560, 1500)).toBe(185_180);
    expect(1_234_560 + 500_000 + 123_460).toBe(1_858_020);
  });

  it('never returns a fractional result, even where float math drifts', () => {
    for (const subtotal of [1_234_560, 99_999_990, 7, 31_337_130, MAX_RIAL_AMOUNT]) {
      for (const bp of [100, 500, 750, 1000, 1250, 1500, 2500, 10000]) {
        const result = percentOfRial(subtotal, bp);
        expect(Number.isInteger(result)).toBe(true);
        expect(result % 10).toBe(0);
      }
    }
    // The float trap this replaces: 86419.20000000001 (not a whole number).
    expect(1_234_560 * 0.07).not.toBe(86_419);
    expect(percentOfRial(1_234_560, 700)).toBe(86_420);
  });

  it('stays within safe-integer range at the application cap', () => {
    expect(() => percentOfRial(MAX_RIAL_AMOUNT, 10_000)).not.toThrow();
    expect(() => percentOfRial(Number.MAX_SAFE_INTEGER, 10_000)).toThrow();
  });
});

describe('formatToman', () => {
  it.each([
    [0, '0 تومان', '۰ تومان', '0 Toman'],
    [10, '1 تومان', '۱ تومان', '1 Toman'],
    [1_250_000, '125,000 تومان', '۱۲۵,۰۰۰ تومان', '125,000 Toman'],
  ])('%i Rial', (rial, latin, persian, english) => {
    // default: Western digits + the Persian unit label
    expect(formatToman(rial)).toBe(latin);
    // the Persian-digit toggle (Task 14.1.2.4); the separator stays ","
    expect(formatToman(rial, { persianDigits: true })).toBe(persian);
    // the unit label is independent of the digit script
    expect(formatToman(rial, { unit: 'en' })).toBe(english);
  });

  it('can omit the unit', () => {
    expect(formatToman(1_250_000, { withUnit: false })).toBe('125,000');
  });

  it('shows a dash for missing values', () => {
    expect(formatToman(null)).toBe('—');
    expect(formatToman(undefined)).toBe('—');
    expect(formatToman('')).toBe('—');
  });

  it('accepts the numeric strings some responses/mocks still carry', () => {
    expect(formatToman('1250000')).toBe('125,000 تومان');
  });

  it('THROWS (dev/test) on an invariant violation instead of papering over it', () => {
    expect(() => formatToman(123_456)).toThrow(/whole number of Toman/);
    expect(() => formatToman(29.99)).toThrow(/integer number of Rial/);
  });
});

describe('Rial <-> Toman conversion', () => {
  it('round-trips', () => {
    expect(rialToToman(1_858_020)).toBe(185_802);
    expect(tomanToRial(185_802)).toBe(1_858_020);
    expect(toTomanNumber(null)).toBeNull();
    expect(toTomanNumber(500)).toBe(50);
  });

  it('refuses to convert garbage typed Toman', () => {
    expect(() => tomanToRial(12.5)).toThrow();
    expect(() => tomanToRial(-1)).toThrow();
    expect(() => tomanToRial('abc')).toThrow();
  });
});

describe('parseTomanInput', () => {
  it.each([
    ['125000', 125000],
    ['125,000', 125000],
    ['۱۲۵٬۰۰۰', 125000],
    ['١٢٥٠٠٠', 125000],
    ['1 250 000', 1250000],
    ['', null],
    ['12.5', null],
    ['abc', null],
    [null, null],
  ])('%s -> %s', (text, expected) => {
    expect(parseTomanInput(text)).toBe(expected);
  });
});

import { formatTomanLoose, toTomanLoose } from '../money';

describe('tolerant helpers for untrusted URL params', () => {
  it('rounds UP instead of throwing', () => {
    expect(toTomanLoose('123456')).toBe(12346);
    expect(toTomanLoose('500')).toBe(50);
    expect(formatTomanLoose('123456')).toBe('12,346 تومان');
    expect(formatTomanLoose('123456', { unit: 'en' })).toBe('12,346 Toman');
  });
  it('returns null / dash for junk', () => {
    expect(toTomanLoose('abc')).toBeNull();
    expect(toTomanLoose('-5')).toBeNull();
    expect(toTomanLoose('')).toBeNull();
    expect(formatTomanLoose('abc')).toBe('—');
  });
});

