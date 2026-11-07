// Jalali (Solar Hijri) DISPLAY helper for customer-facing dates (Task 14.2.1.3).
//
// Jalali is a display concern only: the API always sends Gregorian/UTC ISO
// strings (the project's storage convention) and nothing on the client stores or
// sends a Jalali value.
//
// Two rules make the output correct, and both mirror backend/core/jalali.py:
//   1. Convert to TEHRAN time first. 20:30 UTC on 20 Mar 2026 is already 00:00 on
//      21 Mar in Tehran = 1 Farvardin 1405, not 29 Esfand 1404. Without this the
//      day would depend on the visitor's browser time zone.
//   2. A date-only value ("2026-03-21", no time) is a calendar day, not an instant,
//      so it is converted as-is with no time-zone shift.
// Digits stay WESTERN ("1405/01/01"), matching the admin and the money display;
// Persian digits for dates would be a separate, per-context decision in
// constants/numerals.js.
//
// The calendar conversion itself lives in jalaliCalendar.js (jalaali-js); dayjs is
// used only for the time-zone step.

import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { JALALI_MONTH_NAMES_FA, gregorianToJalali } from './jalaliCalendar';

dayjs.extend(utc);
dayjs.extend(timezone);

export const JALALI_TIME_ZONE = 'Asia/Tehran'; // keep in sync with settings.TIME_ZONE
export const JALALI_DATE_FORMAT = 'YYYY/MM/DD';
export const JALALI_DATETIME_FORMAT = 'YYYY/MM/DD HH:mm';

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
const WALL_CLOCK = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})$/;
// Longest alternatives first; [text] is an escaped literal, as in dayjs.
const TOKENS = /\[([^\]]*)]|YYYY|MMMM|MMM|MM|M|DD|D|HH|mm|ss/g;

const pad2 = (n) => String(n).padStart(2, '0');

function renderTokens(format, jalali, time) {
  return format.replace(TOKENS, (token, literal) => {
    switch (token) {
      case 'YYYY': return String(jalali.year);
      case 'MMMM':
      case 'MMM': return JALALI_MONTH_NAMES_FA[jalali.month - 1]; // no short Persian form
      case 'MM': return pad2(jalali.month);
      case 'M': return String(jalali.month);
      case 'DD': return pad2(jalali.day);
      case 'D': return String(jalali.day);
      case 'HH': return pad2(time.hour);
      case 'mm': return pad2(time.minute);
      case 'ss': return pad2(time.second);
      default: return literal; // [escaped]
    }
  });
}

/**
 * Format an ISO date string (as returned by the API, always Gregorian/UTC) as a
 * Jalali date string for customer-facing display.
 *
 * Accepts an ISO string, a Date or epoch milliseconds. Returns '' for a missing
 * or unparseable value, so it is safe to call inline in JSX. `format` takes
 * dayjs-style tokens: YYYY MM M DD D MMMM (Persian month name) HH mm ss, and
 * [literal text].
 */
export function formatJalaliDate(isoString, format = JALALI_DATE_FORMAT) {
  if (isoString === null || isoString === undefined || isoString === '') return '';

  let fields; // the Tehran calendar date + time of day, as plain numbers
  if (typeof isoString === 'string' && DATE_ONLY.test(isoString)) {
    const [year, month, day] = isoString.split('-').map(Number);
    fields = [year, month, day, 0, 0, 0];
  } else {
    const instant = dayjs(isoString);
    if (!instant.isValid()) return '';
    const m = WALL_CLOCK.exec(instant.tz(JALALI_TIME_ZONE).format('YYYY-MM-DDTHH:mm:ss'));
    if (!m) return '';
    fields = m.slice(1).map(Number);
  }

  const [year, month, day, hour, minute, second] = fields;
  let jalali;
  try {
    jalali = gregorianToJalali({ year, month, day });
  } catch {
    return ''; // e.g. "2026-13-45"
  }
  return renderTokens(format, jalali, { hour, minute, second });
}
