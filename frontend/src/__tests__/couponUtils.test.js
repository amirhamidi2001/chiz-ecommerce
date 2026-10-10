import { describe, it, expect } from "vitest";
import {
  EMPTY_COUPON_FORM,
  buildCouponPayload,
  changedFields,
  couponStatus,
  couponToForm,
  formatCouponValue,
  fromLocalInput,
  parseCouponApiErrors,
  toLocalInput,
  validateCouponForm,
} from "../utils/coupon";

const valid = (overrides = {}) => ({
  ...EMPTY_COUPON_FORM,
  code: "SUMMER20",
  value: "20",
  valid_from: "2030-01-01T10:00",
  valid_until: "2030-02-01T10:00",
  ...overrides,
});

describe("validateCouponForm", () => {
  it("accepts a valid percentage coupon", () => {
    expect(validateCouponForm(valid())).toEqual({});
  });

  it.each(["0", "-1", "100.01", "abc", "10.123"])("rejects percentage value %s", (value) => {
    expect(validateCouponForm(valid({ value })).value).toBeTruthy();
  });

  it.each(["0.01", "50", "100", "99.99"])("accepts percentage value %s", (value) => {
    expect(validateCouponForm(valid({ value })).value).toBeUndefined();
  });

  it("applies the >0 (no upper bound) rule to fixed amounts", () => {
    const fixed = (value) => validateCouponForm(valid({ discount_type: "fixed", value }));
    expect(fixed("0").value).toBeTruthy();
    expect(fixed("-5").value).toBeTruthy();
    expect(fixed("500").value).toBeUndefined();
  });

  it("requires a code of at most 32 characters", () => {
    expect(validateCouponForm(valid({ code: "  " })).code).toBeTruthy();
    expect(validateCouponForm(valid({ code: "X".repeat(33) })).code).toBeTruthy();
    expect(validateCouponForm(valid({ code: "X".repeat(32) })).code).toBeUndefined();
  });

  it("requires valid_until to be strictly after valid_from", () => {
    const same = validateCouponForm(valid({ valid_until: "2030-01-01T10:00" }));
    const before = validateCouponForm(valid({ valid_until: "2029-12-31T10:00" }));
    expect(same.valid_until).toBe("End date must be after the start date.");
    expect(before.valid_until).toBe("End date must be after the start date.");
  });

  it("requires both dates", () => {
    const errors = validateCouponForm(valid({ valid_from: "", valid_until: "" }));
    expect(errors.valid_from).toBeTruthy();
    expect(errors.valid_until).toBeTruthy();
  });

  it("validates the optional limits", () => {
    expect(validateCouponForm(valid({ max_uses: "" })).max_uses).toBeUndefined();
    expect(validateCouponForm(valid({ max_uses: "0" })).max_uses).toBeTruthy();
    expect(validateCouponForm(valid({ max_uses: "1.5" })).max_uses).toBeTruthy();
    expect(validateCouponForm(valid({ uses_per_user: "0" })).uses_per_user).toBeTruthy();
    expect(validateCouponForm(valid({ min_order_amount: "-1" })).min_order_amount).toBeTruthy();
    expect(validateCouponForm(valid({ min_order_amount: "" })).min_order_amount).toBeUndefined();
  });
});

describe("buildCouponPayload / couponToForm", () => {
  it("normalises the code, converts dates and flattens restrictions to ids", () => {
    const payload = buildCouponPayload(
      valid({
        code: " summer20 ",
        max_uses: "50",
        categories: [{ id: 3, name: "Skincare" }],
        products: [{ id: 9, name: "Serum" }],
      }),
    );
    expect(payload).toMatchObject({
      code: "SUMMER20",
      max_uses: 50,
      uses_per_user: 1,
      categories: [3],
      products: [9],
    });
    expect(payload.valid_from).toBe(new Date("2030-01-01T10:00").toISOString());
  });

  it("round-trips an API coupon through the form unchanged", () => {
    const coupon = {
      code: "X",
      discount_type: "fixed",
      value: "5.00",
      min_order_amount: "10.00",
      max_uses: 3,
      uses_per_user: 2,
      valid_from: "2030-01-01T10:00:00.000Z",
      valid_until: "2030-02-01T10:00:00.000Z",
      is_active: false,
      categories_detail: [{ id: 1, name: "A" }],
      products_detail: [],
    };
    const form = couponToForm(coupon);
    expect(form).toMatchObject({ value: "5.00", max_uses: "3", is_active: false });
    expect(changedFields(buildCouponPayload(form), buildCouponPayload(form))).toEqual({});
  });

  it("changedFields keeps only differing keys", () => {
    expect(changedFields({ a: 1, b: [1] }, { a: 1, b: [] })).toEqual({ b: [] });
  });
});

describe("date helpers", () => {
  it("toLocalInput / fromLocalInput round-trip at minute precision", () => {
    const local = "2030-06-15T08:30";
    expect(toLocalInput(fromLocalInput(local))).toBe(local);
  });
  it("handles empty / invalid input", () => {
    expect(toLocalInput("")).toBe("");
    expect(toLocalInput("not a date")).toBe("");
    expect(fromLocalInput("")).toBe("");
  });
});

describe("parseCouponApiErrors", () => {
  it("maps list and string field errors", () => {
    const { fieldErrors, formError } = parseCouponApiErrors({
      code: ["Taken."],
      value: "Bad.",
    });
    expect(fieldErrors).toEqual({ code: "Taken.", value: "Bad." });
    expect(formError).toBe("");
  });
  it("routes detail / non_field_errors to the form-level error", () => {
    expect(parseCouponApiErrors({ detail: "Nope." }).formError).toBe("Nope.");
    expect(parseCouponApiErrors({ non_field_errors: ["Bad."] }).formError).toBe("Bad.");
  });
  it("tolerates a missing body", () => {
    expect(parseCouponApiErrors(undefined)).toEqual({ fieldErrors: {}, formError: "" });
  });
});

describe("couponStatus / formatCouponValue", () => {
  const base = { is_active: true, valid_from: "2026-01-01T00:00:00Z", valid_until: "2026-12-31T00:00:00Z" };
  it("derives the status from the flag and the dates", () => {
    expect(couponStatus(base, new Date("2026-06-01"))).toBe("Active");
    expect(couponStatus({ ...base, is_active: false }, new Date("2026-06-01"))).toBe("Inactive");
    expect(couponStatus(base, new Date("2025-06-01"))).toBe("Scheduled");
    expect(couponStatus(base, new Date("2027-06-01"))).toBe("Expired");
  });
  it("formats percent and fixed values", () => {
    expect(formatCouponValue({ discount_type: "percent", value: "20.00" })).toBe("20%");
    expect(formatCouponValue({ discount_type: "percent", value: "12.50" })).toBe("12.5%");
    expect(formatCouponValue({ discount_type: "fixed", value: "5" })).toBe("$5.00");
  });
});
