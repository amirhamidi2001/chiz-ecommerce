// Pure Jalali (Solar Hijri) calendar math, shared by formatJalaliDate (display) and
// JalaliDatePicker (input) — Tasks 14.2.1.3 / 14.2.1.4.
//
// Library: jalaali-js, which matches ICU's Persian calendar on every day from 1921
// to 2100 (jalaliCalendar.test.js re-checks that against Intl, and pins the same
// reference pairs as backend/core/tests/test_jalali_smoke.py). jalaliday, the
// dayjs plugin first chosen in 14.2.1.3, was REJECTED: it is a day off for every
// date from 1 Jan to 29 Feb of a Gregorian leap year (e.g. it says 11 Feb 2024 is
// 23 Bahman 1402; Revolution Day, 22 Bahman, was that day).
//
// All of this is calendar-DAY arithmetic on plain {year, month, day} objects, so
// no browser time zone can shift a day. Time zones are handled by the callers.

import { isValidJalaaliDate, jalaaliMonthLength, toGregorian, toJalaali } from 'jalaali-js';

const pad2 = (n) => String(n).padStart(2, '0');

export const JALALI_MONTH_NAMES = Object.freeze([
  'Farvardin', 'Ordibehesht', 'Khordad', 'Tir', 'Mordad', 'Shahrivar',
  'Mehr', 'Aban', 'Azar', 'Dey', 'Bahman', 'Esfand',
]);

export const JALALI_MONTH_NAMES_FA = Object.freeze([
  'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
]);

// Saturday-first, as in Iran. Index = column in the month grid.
export const JALALI_WEEKDAY_LABELS = Object.freeze(['Sa', 'Su', 'Mo', 'Tu', 'We', 'Th', 'Fr']);

/** { year, month, day } (Gregorian) -> { year, month, day } (Jalali). */
export function gregorianToJalali({ year, month, day }) {
  const { jy, jm, jd } = toJalaali(year, month, day);
  return { year: jy, month: jm, day: jd };
}

/**
 * { year, month, day } (Jalali) -> { year, month, day } (Gregorian), or null when
 * that Jalali date does not exist (e.g. 30 Esfand 1404, a common year).
 */
export function jalaliToGregorian({ year, month, day }) {
  if (!isValidJalaaliDate(year, month, day)) return null;
  const { gy, gm, gd } = toGregorian(year, month, day);
  return { year: gy, month: gm, day: gd };
}

/** 31 for months 1-6, 30 for 7-11, and 29 or 30 for Esfand (30 only in a leap year). */
export const jalaliMonthLength = (year, month) => jalaaliMonthLength(year, month);

/** Weeks of a Jalali month, Saturday-first; each week is 7 cells: a day number or null. */
export function buildMonthGrid(year, month) {
  const first = jalaliToGregorian({ year, month, day: 1 });
  const weekday = new Date(Date.UTC(first.year, first.month - 1, first.day)).getUTCDay(); // 0 = Sunday
  const lead = (weekday + 1) % 7; // Saturday -> 0
  const cells = [
    ...Array(lead).fill(null),
    ...Array.from({ length: jalaliMonthLength(year, month) }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks;
}

/** Today's Jalali date (from the browser clock's calendar day). */
export function todayJalali(now = new Date()) {
  return gregorianToJalali({
    year: now.getFullYear(),
    month: now.getMonth() + 1,
    day: now.getDate(),
  });
}

export const formatJalaliParts = ({ year, month, day }) => `${year}/${pad2(month)}/${pad2(day)}`;
