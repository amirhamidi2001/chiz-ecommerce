// Persian-digit conversion, with a per-context toggle (Task 14.1.2.4).
//
// This is a DISPLAY concern only: the API, state and every calculation stay in
// Western digits / JS numbers. Convert at the last moment, on the string you
// are about to render, and never feed a converted string back into arithmetic
// (use toWesternDigits() first if you must parse one).
import {
  DEFAULT_NUMERAL_STYLE,
  NUMERAL_CONTEXT,
  NUMERAL_STYLE,
  NUMERAL_STYLE_BY_CONTEXT,
} from '../constants/numerals';

const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

/**
 * Convert Western Arabic digits (0-9) in a string to Persian digits.
 * Non-digit characters (including ".", "," and letters) are left untouched.
 *   toPersianDigits('Order #12345') -> 'Order #۱۲۳۴۵'
 * null / undefined -> ''.
 */
export function toPersianDigits(input) {
  if (input == null) return '';
  return String(input).replace(/[0-9]/g, (digit) => PERSIAN_DIGITS[Number(digit)]);
}

/**
 * The inverse: Persian (۰-۹) and Arabic-Indic (٠-٩) digits -> Western 0-9.
 * Everything else is untouched. For parsing what a person typed.
 */
export function toWesternDigits(input) {
  if (input == null) return '';
  return String(input)
    .replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));
}

/** 'western' | 'persian' — the configured style for this kind of number. */
export function numeralStyleFor(context) {
  return NUMERAL_STYLE_BY_CONTEXT[context] ?? DEFAULT_NUMERAL_STYLE;
}

export const usesPersianDigits = (context) => numeralStyleFor(context) === NUMERAL_STYLE.PERSIAN;

/**
 * Show `input` in the digit script configured for `context`.
 *   localizeDigits(4.5, 'rating')  ->  '۴.۵'     (rating: persian)
 *   localizeDigits(4.5, 'price')   ->  '4.5'     (price: western)
 */
export function localizeDigits(input, context) {
  if (input == null) return '';
  return usesPersianDigits(context) ? toPersianDigits(input) : String(input);
}

/** A product rating, e.g. 4.5 -> "۴.۵". */
export const formatRating = (rating) => localizeDigits(rating, NUMERAL_CONTEXT.RATING);

/** A review count, e.g. 128 -> "۱۲۸". */
export const formatReviewCount = (count) => localizeDigits(count, NUMERAL_CONTEXT.REVIEW_COUNT);
