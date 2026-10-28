// Which digit script each KIND of number is displayed in.
//
// There is no single correct answer for Persian interfaces, so this is a
// per-context decision, not a global switch (Task 14.1.2.4):
//   • money stays WESTERN ("125,000") — exact amounts are easiest to read and
//     compare in Latin digits, and they match the invoice, bank and gateway;
//   • ratings and review counts are PERSIAN ("۴.۵", "۱۲۸") — there the Persian-
//     native feel matters more than split-second numeric precision.
// Anything not listed falls back to DEFAULT_NUMERAL_STYLE. To change a
// decision, edit this table only; no component hard-codes a choice.

export const NUMERAL_STYLE = Object.freeze({ WESTERN: 'western', PERSIAN: 'persian' });

// Names for the kinds of number the SPA displays. Add a context here (and a row
// below) when a new kind of number needs its own decision — e.g. `DATE`, once the
// Jalali calendar work (Feature 14.2.1) lands.
export const NUMERAL_CONTEXT = Object.freeze({
  PRICE: 'price',
  RATING: 'rating',
  REVIEW_COUNT: 'reviewCount',
});

/** The site-wide default for any context that has no explicit row below. */
export const DEFAULT_NUMERAL_STYLE = NUMERAL_STYLE.WESTERN;

export const NUMERAL_STYLE_BY_CONTEXT = Object.freeze({
  [NUMERAL_CONTEXT.PRICE]: NUMERAL_STYLE.WESTERN,
  [NUMERAL_CONTEXT.RATING]: NUMERAL_STYLE.PERSIAN,
  [NUMERAL_CONTEXT.REVIEW_COUNT]: NUMERAL_STYLE.PERSIAN,
});
