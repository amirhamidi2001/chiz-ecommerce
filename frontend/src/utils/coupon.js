import { formatToman, parseTomanInput, toTomanNumber, tomanToRial } from './money';
/**
 * Coupon helpers for the admin UI.
 *
 * validateCouponForm() mirrors the backend rules (Coupon.clean() plus the
 * AdminCouponSerializer field limits) purely for immediate feedback. The
 * backend remains the source of truth and re-validates everything.
 */

const MONEY_RE = /^\d+(\.\d{1,2})?$/; // PERCENT only: Coupon.percent_off is Decimal(5,2)
const INT_RE = /^\d+$/;

const pad = (n) => String(n).padStart(2, "0");

/** ISO timestamp -> value for <input type="datetime-local"> (local time, minute precision). */
export const toLocalInput = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
};

/** <input type="datetime-local"> value -> ISO timestamp (or "" if empty/invalid). */
export const fromLocalInput = (value) => {
  if (!value) return "";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "" : d.toISOString();
};

export const EMPTY_COUPON_FORM = {
  code: "",
  discount_type: "percent",
  value: "",
  min_order_amount: "0",
  max_uses: "",
  uses_per_user: "1",
  valid_from: "",
  valid_until: "",
  is_active: true,
  categories: [], // [{ id, name }]
  products: [], // [{ id, name }]
};

/** API coupon -> form state (all inputs held as strings). */
export const couponToForm = (coupon) => ({
  code: coupon.code ?? "",
  discount_type: coupon.discount_type ?? "percent",
  // One "Value" input whose unit follows discount_type: a percentage, or TOMAN
  // (the API's fixed_amount / min_order_amount are Rial — converted here only).
  value:
    coupon.discount_type === "fixed"
      ? coupon.fixed_amount != null
        ? String(toTomanNumber(coupon.fixed_amount))
        : ""
      : coupon.percent_off != null
        ? String(parseFloat(coupon.percent_off))
        : "",
  min_order_amount:
    coupon.min_order_amount != null ? String(toTomanNumber(coupon.min_order_amount)) : "0",
  max_uses: coupon.max_uses != null ? String(coupon.max_uses) : "",
  uses_per_user:
    coupon.uses_per_user != null ? String(coupon.uses_per_user) : "1",
  valid_from: toLocalInput(coupon.valid_from),
  valid_until: toLocalInput(coupon.valid_until),
  is_active: coupon.is_active ?? true,
  categories: coupon.categories_detail ?? [],
  products: coupon.products_detail ?? [],
});

/** Form state -> API payload. */
export const buildCouponPayload = (form) => ({
  code: form.code.trim().toUpperCase(),
  discount_type: form.discount_type,
  // percent_off XOR fixed_amount (the API has two explicit columns; ADR 0001 §7.3).
  percent_off: form.discount_type === "percent" ? String(form.value).trim() : null,
  fixed_amount:
    form.discount_type === "fixed"
      ? tomanToRial(parseTomanInput(form.value) ?? 0)
      : null,
  min_order_amount: tomanToRial(parseTomanInput(form.min_order_amount) ?? 0),
  max_uses: String(form.max_uses).trim() === "" ? null : Number(form.max_uses),
  uses_per_user: Number(form.uses_per_user),
  valid_from: fromLocalInput(form.valid_from),
  valid_until: fromLocalInput(form.valid_until),
  is_active: form.is_active,
  categories: form.categories.map((c) => c.id),
  products: form.products.map((p) => p.id),
});

/** Only the payload keys whose value differs from `before` (for PATCH). */
export const changedFields = (before, after) =>
  Object.fromEntries(
    Object.entries(after).filter(
      ([key, value]) => JSON.stringify(value) !== JSON.stringify(before[key]),
    ),
  );

/**
 * Validate form state. Returns { field: message }; an empty object means
 * "nothing obviously wrong" (not "the server will accept it").
 */
export const validateCouponForm = (form) => {
  const errors = {};

  const code = (form.code ?? "").trim();
  if (!code) errors.code = "Coupon code is required.";
  else if (code.length > 32) errors.code = "Code must be 32 characters or fewer.";

  const value = String(form.value ?? "").trim();
  if (!value) {
    errors.value = "Enter a discount value.";
  } else if (form.discount_type === "percent") {
    if (!MONEY_RE.test(value)) {
      errors.value = "Enter a positive number with at most 2 decimal places.";
    } else if (!(Number(value) > 0 && Number(value) <= 100)) {
      errors.value = "Percentage must be greater than 0 and at most 100.";
    }
  } else {
    // Fixed amounts are typed in whole Toman.
    const toman = parseTomanInput(value);
    if (toman === null) errors.value = "Enter a whole number of Toman.";
    else if (!(toman > 0)) errors.value = "Fixed amount must be greater than 0.";
  }

  const minOrder = String(form.min_order_amount ?? "").trim();
  if (minOrder && parseTomanInput(minOrder) === null) {
    errors.min_order_amount = "Enter 0 or a whole number of Toman.";
  }

  const maxUses = String(form.max_uses ?? "").trim();
  if (maxUses && !(INT_RE.test(maxUses) && Number(maxUses) >= 1)) {
    errors.max_uses = "Leave blank for unlimited, or enter a whole number of 1 or more.";
  }

  const perUser = String(form.uses_per_user ?? "").trim();
  if (!(INT_RE.test(perUser) && Number(perUser) >= 1)) {
    errors.uses_per_user = "Enter a whole number of 1 or more.";
  }

  if (!form.valid_from) errors.valid_from = "Start date is required.";
  if (!form.valid_until) errors.valid_until = "End date is required.";
  if (
    form.valid_from &&
    form.valid_until &&
    new Date(form.valid_until) <= new Date(form.valid_from)
  ) {
    errors.valid_until = "End date must be after the start date.";
  }

  return errors;
};

/**
 * DRF error body -> { fieldErrors, formError }. Field errors may be a
 * string or a list of strings; "detail" / "non_field_errors" go to formError.
 */
export const parseCouponApiErrors = (data) => {
  const fieldErrors = {};
  let formError = "";
  if (data && typeof data === "object") {
    Object.entries(data).forEach(([key, val]) => {
      const msg = Array.isArray(val) ? val[0] : val;
      if (typeof msg !== "string") return;
      if (key === "detail" || key === "non_field_errors") formError = msg;
      else fieldErrors[key === "percent_off" || key === "fixed_amount" ? "value" : key] = msg;
    });
  }
  return { fieldErrors, formError };
};

/** "Active" | "Inactive" | "Scheduled" | "Expired" for the list badge. */
export const couponStatus = (coupon, now = new Date()) => {
  if (!coupon.is_active) return "Inactive";
  if (now < new Date(coupon.valid_from)) return "Scheduled";
  if (now > new Date(coupon.valid_until)) return "Expired";
  return "Active";
};

const fmtMoney = (n) => formatToman(n);

/** "20%" or "50,000 Toman" */
export const formatCouponValue = (coupon) =>
  coupon.discount_type === "percent"
    ? `${parseFloat(coupon.percent_off)}%`
    : fmtMoney(coupon.fixed_amount);
