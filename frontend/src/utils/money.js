// src/utils/money.js
// ─────────────────────────────────────────────────────────────────────────────
// The ONE place the SPA converts and formats money (ADR 0001, backend/docs/adr/
// 0001-currency-storage.md). Mirrors backend/core/money.py — keep the two in
// step; both are pinned by the same golden vectors in their test suites.
//
//   • The API sends and accepts RIAL, as plain JSON integers.
//   • Every amount is a multiple of 10 Rial (whole Toman), so Toman = Rial / 10
//     is always exact.
//   • Customers read TOMAN (1 Toman = 10 Rial). All Rial <-> Toman conversion
//     in the SPA happens in this file and nowhere else (invariant I-5).
//   • "Toman" here means exactly 10 legacy Rial (IRR) — the colloquial unit —
//     NOT the "new toman"/redenominated unit (10,000 Rial); see ADR §9.
//
// Never do money arithmetic with floats (`x * 0.1`): use roundToWholeToman()
// / percentOfRial(), which use integer math only.

import { NUMERAL_CONTEXT } from '../constants/numerals';
import { toPersianDigits, toWesternDigits, usesPersianDigits } from './numerals';

export const RIAL_PER_TOMAN = 10;
// Largest amount the application accepts anywhere (ADR §4). With this cap even
// `amount * 10_000` (basis-point math below) stays under 2**53 - 1.
export const MAX_RIAL_AMOUNT = 100_000_000_000;

const UNIT_LABEL = { fa: 'تومان', en: 'Toman' };
// What a price slot shows when there is no amount to show (null / undefined / ''
// / NaN / junk). A dash is visibly "nothing here" without breaking the layout.
const EMPTY = '—';

// An invariant violation (a non-integer / non-multiple-of-10 Rial value) is a
// BUG upstream, never something to normalise silently. Dev & test: throw. In
// production a customer must not see a crash, so the caller falls back to a
// safe value and the error is reported loudly.
function violation(message) {
  const text = `[money] ${message}`;
  if (import.meta.env?.PROD) {
    console.error(text);
    return;
  }
  throw new Error(text);
}

const isBlank = (v) => v === null || v === undefined || v === '';
// Blank, NaN, ±Infinity, or text that is not a number: nothing displayable.
const isUnusable = (v) => isBlank(v) || !Number.isFinite(Number(v));
// Math.floor(-0)/-0 survive arithmetic and Intl prints them as "-0".
const noNegativeZero = (n) => (n === 0 ? 0 : n);
// Round a Toman fraction AWAY from zero: a displayed amount (refund and
// discount lines can be negative) must never be smaller than what is charged.
const roundUpMagnitude = (toman) => Math.sign(toman) * Math.ceil(Math.abs(toman));

/**
 * Rial -> whole Toman (an integer), for calculations and display.
 *   rialToToman(299900)  ->  29990        rialToToman(-50000) -> -5000
 *   rialToToman(null | undefined | '')  ->  0   (no amount contributes nothing)
 * A value that is not a whole number of Toman is an upstream BUG (ADR 0001, I-2):
 * dev/test throw; production reports it and rounds away from zero, never down.
 */
export function rialToToman(rial) {
  if (isBlank(rial)) return 0;
  const n = Number(rial);
  if (!Number.isFinite(n)) {
    violation(`${String(rial)} is not a number of Rial.`);
    return 0;
  }
  if (!Number.isInteger(n)) {
    violation(`${String(rial)} is not an integer number of Rial.`);
    return noNegativeZero(roundUpMagnitude(n / RIAL_PER_TOMAN));
  }
  if (n % RIAL_PER_TOMAN !== 0) {
    violation(`${n} Rial is not a whole number of Toman (must be a multiple of 10).`);
    return noNegativeZero(roundUpMagnitude(n / RIAL_PER_TOMAN));
  }
  return noNegativeZero(n / RIAL_PER_TOMAN);
}

/** Whole Toman (int) -> Rial (int). Used when a human TYPES a price. */
export function tomanToRial(toman) {
  const n = Number(toman);
  if (!Number.isInteger(n) || n < 0) {
    throw new Error(`[money] ${String(toman)} is not a non-negative whole number of Toman.`);
  }
  return n * RIAL_PER_TOMAN;
}

/**
 * Format a Rial amount for display as Toman.
 *   formatToman(299900)                       ->  "29,990 تومان"
 *   formatToman(-50000)                       ->  "-5,000 تومان"   (sign preserved)
 *   formatToman(0)                            ->  "0 تومان"
 *   formatToman(null | undefined | NaN | '')  ->  "—"              (never throws, never "NaN تومان")
 *   formatToman(299900, { unit: 'en' })       ->  "29,990 Toman"
 *   formatToman(299900, { withUnit: false })  ->  "29,990"
 *
 *   formatToman(299900, { persianDigits: true }) -> "۲۹,۹۹۰ تومان"
 *
 * DIGIT SCRIPT is a separate concern from the unit label. `persianDigits`
 * converts the finished string with toPersianDigits(); it defaults to whatever
 * the PRICE context is configured as (constants/numerals.js) — Western, so
 * "29,990", unless that table is changed. The thousands separator stays ",".
 */
export function formatToman(
  rial,
  { unit = 'fa', withUnit = true, persianDigits = usesPersianDigits(NUMERAL_CONTEXT.PRICE) } = {}
) {
  if (isUnusable(rial)) return EMPTY;
  const digits = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 0,
    useGrouping: true,
  }).format(rialToToman(rial));
  const text = withUnit ? `${digits} ${UNIT_LABEL[unit] ?? UNIT_LABEL.fa}` : digits;
  return persianDigits ? toPersianDigits(text) : text;
}

/** Rial -> Toman number for places that need the raw number (e.g. a price slider). Unusable -> null. */
export function toTomanNumber(rial) {
  return isUnusable(rial) ? null : rialToToman(rial);
}

/**
 * value = num/den Rial, rounded to the nearest multiple of 10 (whole Toman),
 * ties up — the exact rule of backend core.money.to_whole_toman_rial.
 * Integer arithmetic only.
 */
export function roundToWholeToman(num, den = 1) {
  return Math.floor((2 * num + 10 * den) / (20 * den)) * 10;
}

/** percent given in BASIS POINTS (10% = 1000): the backend's percent_of() without floats. */
export function percentOfRial(amountRial, basisPoints) {
  if (amountRial * basisPoints > Number.MAX_SAFE_INTEGER) {
    throw new Error('[money] amount too large for safe integer percent math.');
  }
  return roundToWholeToman(amountRial * basisPoints, 10_000);
}

/**
 * Parse what a person typed into a price field (Latin / Persian / Arabic
 * digits, with "," "٬" "،" or spaces as separators) into whole Toman.
 * Returns null for blank or non-numeric input — never guesses.
 */
export function parseTomanInput(text) {
  if (isBlank(text)) return null;
  const latin = toWesternDigits(text).replace(/[,٬،\s]/g, '');
  if (!/^\d+$/.test(latin)) return null;
  return Number(latin);
}

// ── Tolerant variants for UNTRUSTED input (hand-edited URL params) ───────────
// Query strings like ?min_price=123456 can be typed by anyone, so they must
// never crash the page the way an upstream invariant violation should. These
// round UP to the next whole Toman instead of throwing. Server data and
// anything that is about to be charged uses the strict functions above.

/** Rial (maybe junk) -> whole Toman number, rounded up; null if not a number. */
export function toTomanLoose(rial) {
  if (isBlank(rial)) return null;
  const n = Number(rial);
  return Number.isFinite(n) && n >= 0 ? Math.ceil(n / RIAL_PER_TOMAN) : null;
}

/** formatToman() for untrusted input; blank/junk -> "—". */
export function formatTomanLoose(rial, options) {
  const toman = toTomanLoose(rial);
  return toman === null ? '—' : formatToman(toman * RIAL_PER_TOMAN, options);
}
