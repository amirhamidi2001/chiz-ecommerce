import { describe, it, expect } from 'vitest';
import { formatRelativeTime } from '../relativeTime';
import { formatJalaliDate } from '../jalaliDate';

const NOW = Date.parse('2026-11-22T12:00:00Z');
const ago = (seconds) => new Date(NOW - seconds * 1000).toISOString();
const rel = (seconds, locale = 'en') =>
  formatRelativeTime(ago(seconds), { now: NOW, locale });

describe('formatRelativeTime', () => {
  it('says "now" for the last minute', () => {
    expect(rel(0)).toBe('now');
    expect(rel(59)).toBe('now');
  });

  it('counts minutes, hours and days (flooring, never rounding up)', () => {
    expect(rel(60)).toBe('1 minute ago');
    expect(rel(59 * 60 + 59)).toBe('59 minutes ago');
    expect(rel(2 * 3600)).toBe('2 hours ago');
    expect(rel(23 * 3600 + 3599)).toBe('23 hours ago');
    expect(rel(24 * 3600)).toBe('yesterday');
    expect(rel(3 * 86400)).toBe('3 days ago');
  });

  it('falls back to the Jalali date from a week onwards', () => {
    const iso = ago(7 * 86400);
    expect(formatRelativeTime(iso, { now: NOW, locale: 'en' })).toBe(formatJalaliDate(iso));
    expect(rel(7 * 86400)).toMatch(/^\d{4}\/\d{2}\/\d{2}$/);
    expect(rel(6 * 86400 + 86399)).toBe('6 days ago');
  });

  it('treats a timestamp in the future (clock skew) as "now"', () => {
    expect(formatRelativeTime(ago(-300), { now: NOW, locale: 'en' })).toBe('now');
  });

  it('returns "" for missing or unparseable input', () => {
    expect(formatRelativeTime(null)).toBe('');
    expect(formatRelativeTime(undefined)).toBe('');
    expect(formatRelativeTime('')).toBe('');
    expect(formatRelativeTime('not a date')).toBe('');
  });

  it('accepts a Date or epoch milliseconds', () => {
    expect(formatRelativeTime(new Date(NOW - 7200_000), { now: NOW, locale: 'en' })).toBe('2 hours ago');
    expect(formatRelativeTime(NOW - 7200_000, { now: NOW, locale: 'en' })).toBe('2 hours ago');
  });

  it('uses Persian wording and digits for the fa locale', () => {
    const text = rel(2 * 3600, 'fa');
    expect(text).toMatch(/[۰-۹]/);
    expect(text).not.toMatch(/ago/);
  });

  it('defaults to the document language', () => {
    const previous = document.documentElement.lang;
    document.documentElement.lang = 'fa';
    try {
      expect(formatRelativeTime(ago(7200), { now: NOW })).toMatch(/[۰-۹]/);
    } finally {
      document.documentElement.lang = previous;
    }
  });

  it('survives an unsupported locale tag by falling back to English', () => {
    expect(formatRelativeTime(ago(7200), { now: NOW, locale: 'xx-INVALID-@@' })).toBe('2 hours ago');
  });
});
