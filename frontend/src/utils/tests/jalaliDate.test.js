/* global process */
import { describe, expect, it } from 'vitest';
import { formatJalaliDate } from '../jalaliDate';
import { KNOWN_PAIRS } from './jalaliReferenceDates';

describe('formatJalaliDate — known reference dates', () => {
  it.each(KNOWN_PAIRS)('%s -> %s (%s)', (gregorian, jalali) => {
    expect(formatJalaliDate(gregorian)).toBe(jalali);
  });

  it('converts a full ISO timestamp (the API shape) the same way', () => {
    expect(formatJalaliDate('2025-03-21T10:00:00Z')).toBe('1404/01/01');
    expect(formatJalaliDate('2025-03-21T10:00:00+00:00')).toBe('1404/01/01');
  });
});

describe('formatJalaliDate — Tehran day boundary (mirrors the backend test)', () => {
  // 20:30 UTC on 20 Mar 2026 is 00:00 on 21 Mar in Tehran (UTC+3:30).
  const INSTANT = '2026-03-20T20:30:00Z';

  it('uses the Tehran day, not the UTC day', () => {
    expect(formatJalaliDate(INSTANT)).toBe('1405/01/01');
    expect(formatJalaliDate('2026-03-20T20:29:59Z')).toBe('1404/12/29');
  });

  it('does not depend on the browser time zone', () => {
    // Node reads TZ lazily, so changing it here changes how `new Date` resolves
    // local fields, which is what a visitor's browser zone does.
    const original = process.env.TZ;
    try {
      for (const zone of ['America/Los_Angeles', 'Asia/Tehran', 'Pacific/Auckland']) {
        process.env.TZ = zone;
        expect(formatJalaliDate(INSTANT)).toBe('1405/01/01');
        expect(formatJalaliDate('1979-02-11')).toBe('1357/11/22'); // date-only: no shift
      }
    } finally {
      if (original === undefined) delete process.env.TZ;
      else process.env.TZ = original;
    }
  });
});

describe('formatJalaliDate — empty and invalid input', () => {
  it('returns "" for null/undefined/empty without throwing', () => {
    expect(() => formatJalaliDate(null)).not.toThrow();
    expect(formatJalaliDate(null)).toBe('');
    expect(formatJalaliDate(undefined)).toBe('');
    expect(formatJalaliDate('')).toBe('');
  });

  it('returns "" for an unparseable string rather than "NaN/NaN/NaN"', () => {
    expect(formatJalaliDate('not a date')).toBe('');
  });
});

describe('formatJalaliDate — custom format', () => {
  it('respects a custom format string', () => {
    expect(formatJalaliDate('2026-03-21', 'YYYY-MM-DD')).toBe('1405-01-01');
    expect(formatJalaliDate('2026-03-21', 'D MMMM YYYY')).toBe('1 فروردین 1405');
    expect(formatJalaliDate('2026-03-21', 'D MMM YYYY')).toBe('1 فروردین 1405'); // no short form
    expect(formatJalaliDate('2026-03-21', '[Day] D')).toBe('Day 1'); // [escaped] text
    expect(formatJalaliDate('2026-03-21', 'M/D')).toBe('1/1');
    expect(formatJalaliDate('2026-03-20T20:30:00Z', 'YYYY/MM/DD HH:mm')).toBe('1405/01/01 00:00');
  });

  it('defaults to YYYY/MM/DD', () => {
    expect(formatJalaliDate('2026-03-21')).toBe('1405/01/01');
  });
});
