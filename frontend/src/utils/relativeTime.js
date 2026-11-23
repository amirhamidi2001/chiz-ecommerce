// Relative-time DISPLAY helper for the notification bell ("2 hours ago").
//
// Recent instants read relatively; anything a week or older reads better as a
// calendar date, and for this site that is the Jalali date (formatJalaliDate,
// Task 14.2.1.3) — not a Gregorian one and not "37 days ago".
//
// The wording comes from Intl.RelativeTimeFormat in the document's language
// (index.html is lang="fa", so "۲ ساعت پیش"); pass `locale` to override. As with
// every date on the client, the input is the API's ISO string.

import { formatJalaliDate } from './jalaliDate';

export const RELATIVE_TIME_MAX_DAYS = 7;

const MINUTE = 60;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

const documentLocale = () =>
  (typeof document !== 'undefined' && document.documentElement.lang) || 'en';

const makeFormatter = (locale) => {
  try {
    return new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });
  } catch {
    return new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  }
};

/**
 * @param {string|Date|number} value  ISO string / Date / epoch ms
 * @param {{now?: number, locale?: string}} [options]
 * @returns {string} '' for a missing or unparseable value (safe inline in JSX)
 */
export function formatRelativeTime(value, { now = Date.now(), locale } = {}) {
  if (value === null || value === undefined || value === '') return '';
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return '';

  // A timestamp slightly in the future (client clock behind the server) is
  // "now", never "in 3 minutes".
  const seconds = Math.max(0, Math.floor((now - then) / 1000));
  const formatter = makeFormatter(locale || documentLocale());

  if (seconds < MINUTE) return formatter.format(0, 'second'); // "now"
  if (seconds < HOUR) return formatter.format(-Math.floor(seconds / MINUTE), 'minute');
  if (seconds < DAY) return formatter.format(-Math.floor(seconds / HOUR), 'hour');
  if (seconds < RELATIVE_TIME_MAX_DAYS * DAY) {
    return formatter.format(-Math.floor(seconds / DAY), 'day');
  }
  return formatJalaliDate(value);
}
