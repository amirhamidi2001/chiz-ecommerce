import { describe, expect, it } from 'vitest';
import {
  buildMonthGrid,
  formatJalaliParts,
  gregorianToJalali,
  jalaliMonthLength,
  jalaliToGregorian,
  todayJalali,
} from '../jalaliCalendar';
import { KNOWN_PAIRS } from './jalaliReferenceDates';

const G = (iso) => {
  const [year, month, day] = iso.split('-').map(Number);
  return { year, month, day };
};
const J = (text) => {
  const [year, month, day] = text.split('/').map(Number);
  return { year, month, day };
};

describe('Gregorian <-> Jalali — the backend reference dates', () => {
  it.each(KNOWN_PAIRS)('%s <-> %s (%s)', (gregorian, jalali) => {
    expect(gregorianToJalali(G(gregorian))).toEqual(J(jalali));
    expect(jalaliToGregorian(J(jalali))).toEqual(G(gregorian));
  });
});

// ICU's Persian calendar is an independent implementation, and is what the backend
// pin (jdatetime) was cross-checked against. Skipped only where the runtime has no
// Persian calendar at all (a Node built without full ICU).
const icuPersian = new Intl.DateTimeFormat('en-u-ca-persian-nu-latn', {
  timeZone: 'UTC', year: 'numeric', month: 'numeric', day: 'numeric',
});
const hasPersianIcu = icuPersian.resolvedOptions().calendar === 'persian';

describe.runIf(hasPersianIcu)('against ICU\'s Persian calendar, every day 1921-2100', () => {
  it('agrees on every day, and every day round-trips', () => {
    const wrong = [];
    for (let ms = Date.UTC(1921, 0, 1); ms <= Date.UTC(2100, 11, 31); ms += 86400000) {
      const d = new Date(ms);
      const g = { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() };
      const parts = Object.fromEntries(icuPersian.formatToParts(d).map((p) => [p.type, p.value]));
      const expected = { year: +(parts.relatedYear || parts.year), month: +parts.month, day: +parts.day };
      const actual = gregorianToJalali(g);
      if (JSON.stringify(actual) !== JSON.stringify(expected)) wrong.push(`${ms}: got ${JSON.stringify(actual)}`);
      else if (JSON.stringify(jalaliToGregorian(actual)) !== JSON.stringify(g)) wrong.push(`${ms}: no round trip`);
    }
    expect(wrong.slice(0, 5)).toEqual([]);
  });
});

describe('jalaliToGregorian', () => {
  it('returns null for a Jalali date that does not exist', () => {
    expect(jalaliToGregorian(J('1404/12/30'))).toBeNull(); // 1404 is a common year
    expect(jalaliToGregorian(J('1405/07/31'))).toBeNull(); // Mehr has 30 days
    expect(jalaliToGregorian(J('1405/13/01'))).toBeNull();
    expect(jalaliToGregorian(J('1403/12/30'))).toEqual(G('2025-03-20')); // 1403 is leap
  });
});

describe('jalaliMonthLength', () => {
  it('is 31 / 30 / 29-or-30 by month, with Esfand following the leap rule', () => {
    expect(jalaliMonthLength(1405, 1)).toBe(31);
    expect(jalaliMonthLength(1405, 6)).toBe(31);
    expect(jalaliMonthLength(1405, 7)).toBe(30);
    expect(jalaliMonthLength(1405, 11)).toBe(30);
    expect(jalaliMonthLength(1403, 12)).toBe(30); // leap
    expect(jalaliMonthLength(1404, 12)).toBe(29);
  });
});

describe('buildMonthGrid (Saturday-first)', () => {
  it('lays out Farvardin 1405, which starts on a Saturday (21 Mar 2026)', () => {
    const weeks = buildMonthGrid(1405, 1);
    expect(weeks[0]).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(weeks.at(-1)).toEqual([29, 30, 31, null, null, null, null]);
  });

  it('pads the first week with blanks when the month starts mid-week', () => {
    // 1 Ordibehesht 1405 = 21 Apr 2026, a Tuesday -> 3 blanks (Sat, Sun, Mon)
    expect(buildMonthGrid(1405, 2)[0]).toEqual([null, null, null, 1, 2, 3, 4]);
  });

  it('always yields whole weeks of 7 and every day of the month exactly once', () => {
    for (const [y, m] of [[1403, 12], [1404, 12], [1405, 6], [1405, 7]]) {
      const weeks = buildMonthGrid(y, m);
      expect(weeks.every((w) => w.length === 7)).toBe(true);
      const days = weeks.flat().filter(Boolean);
      expect(days).toEqual(Array.from({ length: jalaliMonthLength(y, m) }, (_, i) => i + 1));
    }
  });
});

describe('helpers', () => {
  it('formats parts as YYYY/MM/DD', () => {
    expect(formatJalaliParts({ year: 1405, month: 1, day: 5 })).toBe('1405/01/05');
  });

  it('todayJalali uses the given moment\'s local calendar day', () => {
    expect(todayJalali(new Date(2026, 2, 21, 12, 0))).toEqual(J('1405/01/01'));
  });
});
