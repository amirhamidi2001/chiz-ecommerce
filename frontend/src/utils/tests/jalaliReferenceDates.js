// Reference Gregorian -> Jalali pairs, shared by jalaliDate.test.js and
// jalaliCalendar.test.js. Same pairs as KNOWN_PAIRS in
// backend/core/tests/test_jalali_smoke.py, so a disagreement between the two stacks on
// any of them is a real bug. They are NOT derived from the library under test.
// [gregorian ISO date, jalali YYYY/MM/DD, why it is a good reference]
export const KNOWN_PAIRS = [
  ['1979-02-11', '1357/11/22', '22 Bahman 1357 — Islamic Revolution day'],
  ['2000-03-20', '1379/01/01', 'Nowruz 1379'],
  ['2021-03-21', '1400/01/01', 'Nowruz 1400'],
  ['2024-03-20', '1403/01/01', 'Nowruz 1403'],
  ['2025-03-20', '1403/12/30', '30 Esfand 1403 — leap-year extra day'],
  ['2025-03-21', '1404/01/01', 'Nowruz 1404'],
  ['2026-03-20', '1404/12/29', '29 Esfand 1404 — last day of a common year'],
  ['2026-03-21', '1405/01/01', 'Nowruz 1405'],
  ['2027-03-21', '1406/01/01', 'Nowruz 1406'],
  ['2028-03-20', '1407/01/01', 'Nowruz 1407'],
  // 1 Jan-29 Feb of a Gregorian LEAP year: the window jalaliday got wrong.
  ['2024-01-01', '1402/10/11', '11 Dey 1402 — 1 Jan of a Gregorian leap year'],
  ['2024-02-11', '1402/11/22', '22 Bahman 1402 — Revolution day, leap Gregorian year'],
  ['2024-02-29', '1402/12/10', '10 Esfand 1402 — 29 Feb'],
  ['2028-02-11', '1406/11/22', '22 Bahman 1406 — Revolution day, leap Gregorian year'],
];
