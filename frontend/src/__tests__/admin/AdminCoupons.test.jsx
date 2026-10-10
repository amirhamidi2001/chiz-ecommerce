/**
 * AdminCoupons.test.jsx — coupon list, quick-deactivate action and the
 * create/edit form (AdminCoupons.jsx + CouponModal.jsx).
 *
 * Stack: Vitest · React Testing Library · user-event.
 *
 *  1. List            – heading/total, rows (code, discount, scope, status,
 *                       date range), mount params, search, empty, load error
 *  2. Deactivate      – PATCH is_active=false via adminAPI.updateCoupon,
 *                       Activate for inactive coupons, error toast
 *  3. Form validation – obviously-invalid input is caught client-side and
 *                       NO request is sent
 *  4. Create          – exact payload, success flow, server field errors
 *  5. Edit            – pre-fill, PATCH of changed fields only
 *  6. Pickers         – categories (all pages) and product search
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AdminCoupons from "../../pages/admin/AdminCoupons";

// ─── Mock: DataTable (renders every cell + row actions) ───────────────────────
vi.mock("../../components/admin/DataTable", () => ({
  default: ({ columns, data, loading, emptyText, rowActions, onSearch, totalCount }) => {
    if (loading) return <div data-testid="dt-loading">Loading…</div>;
    return (
      <div data-testid="data-table">
        <input
          data-testid="dt-search"
          placeholder="search"
          onChange={(e) => onSearch?.(e.target.value)}
        />
        <span data-testid="dt-total">{totalCount}</span>
        {data.length === 0 && <div data-testid="dt-empty">{emptyText}</div>}
        {data.map((row, ri) => (
          <div key={row.id ?? ri} data-testid={`row-${row.id}`}>
            {columns.map((col) => (
              <div key={col.key} data-testid={`cell-${col.key}`}>
                {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? "")}
              </div>
            ))}
            {rowActions && <div data-testid="row-actions">{rowActions(row)}</div>}
          </div>
        ))}
      </div>
    );
  },
}));

// ─── Mock: Toast / useToast ───────────────────────────────────────────────────
let capturedToasts = [];
vi.mock("../../components/admin/Toast", () => ({
  default: () => null,
  useToast: () => ({
    toast: null,
    show: (message, type = "success") => capturedToasts.push({ message, type }),
    dismiss: () => {},
  }),
}));

// ─── Mock: adminAPI ───────────────────────────────────────────────────────────
vi.mock("../../services/api", () => ({
  adminAPI: {
    getCoupons: vi.fn(),
    createCoupon: vi.fn(),
    updateCoupon: vi.fn(),
    getCategories: vi.fn(),
    getProducts: vi.fn(),
  },
}));
import { adminAPI } from "../../services/api";

// ─── Fixtures ─────────────────────────────────────────────────────────────────
const DAY = 24 * 60 * 60 * 1000;
const iso = (offsetDays) => new Date(Date.now() + offsetDays * DAY).toISOString();

const makeCoupon = (overrides = {}) => ({
  id: 1,
  code: "SUMMER20",
  discount_type: "percent",
  value: "20.00",
  min_order_amount: "0.00",
  max_uses: null,
  uses_per_user: 1,
  valid_from: "2026-01-01T00:00:00Z",
  valid_until: "2099-01-01T00:00:00Z",
  is_active: true,
  categories: [],
  products: [],
  categories_detail: [],
  products_detail: [],
  created_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

const paged = (results, extra = {}) => ({
  data: { results, count: results.length, next: null, ...extra },
});

const okCoupons = (coupons = [makeCoupon()]) =>
  adminAPI.getCoupons.mockResolvedValue(paged(coupons));

const renderPage = async (coupons) => {
  okCoupons(coupons);
  const user = userEvent.setup();
  render(<AdminCoupons />);
  await screen.findByTestId("data-table");
  return user;
};

const dialog = () => screen.getByRole("dialog");
const field = (label) => within(dialog()).getByLabelText(label);
const submitButton = (name) => within(dialog()).getByRole("button", { name });

/** Fill the required fields of a valid percentage coupon. */
const fillValid = async (user, overrides = {}) => {
  const v = {
    code: "summer20",
    value: "20",
    from: "2030-01-01T10:00",
    until: "2030-02-01T10:00",
    ...overrides,
  };
  await user.type(field(/^code/i), v.code);
  await user.type(field(/^value/i), v.value);
  fireEvent.change(field(/valid from/i), { target: { value: v.from } });
  fireEvent.change(field(/valid until/i), { target: { value: v.until } });
};

beforeEach(() => {
  vi.clearAllMocks();
  capturedToasts = [];
  adminAPI.getCategories.mockResolvedValue(paged([]));
  adminAPI.getProducts.mockResolvedValue(paged([]));
});

// ═════════════════════════════════════════════════════════════════════════════
// 1. List
// ═════════════════════════════════════════════════════════════════════════════
describe("AdminCoupons — list", () => {
  it("renders the heading, total and existing coupons", async () => {
    await renderPage([
      makeCoupon({ id: 1, code: "SUMMER20" }),
      makeCoupon({ id: 2, code: "FIVEOFF", discount_type: "fixed", value: "5.00" }),
    ]);

    expect(screen.getByRole("heading", { name: "Coupons" })).toBeInTheDocument();
    expect(screen.getByText("2 total coupons")).toBeInTheDocument();

    const first = within(screen.getByTestId("row-1"));
    expect(first.getByText("SUMMER20")).toBeInTheDocument();
    expect(first.getByText("20%")).toBeInTheDocument();
    const second = within(screen.getByTestId("row-2"));
    expect(second.getByText("FIVEOFF")).toBeInTheDocument();
    expect(second.getByText("$5.00")).toBeInTheDocument();
  });

  it("shows the valid-from / valid-until range", async () => {
    await renderPage([
      makeCoupon({
        valid_from: "2026-03-15T12:00:00Z",
        valid_until: "2099-07-20T12:00:00Z",
      }),
    ]);
    const row = within(screen.getByTestId("row-1"));
    expect(within(row.getByTestId("cell-valid_from")).getByText(/2026/)).toBeInTheDocument();
    expect(within(row.getByTestId("cell-valid_until")).getByText(/2099/)).toBeInTheDocument();
  });

  it("derives a status badge: Active / Inactive / Expired / Scheduled", async () => {
    await renderPage([
      makeCoupon({ id: 1 }),
      makeCoupon({ id: 2, is_active: false }),
      makeCoupon({ id: 3, valid_from: iso(-30), valid_until: iso(-1) }),
      makeCoupon({ id: 4, valid_from: iso(1), valid_until: iso(30) }),
    ]);
    const status = (id) =>
      within(within(screen.getByTestId(`row-${id}`)).getByTestId("cell-is_active"));
    expect(status(1).getByText("Active")).toBeInTheDocument();
    expect(status(2).getByText("Inactive")).toBeInTheDocument();
    expect(status(3).getByText("Expired")).toBeInTheDocument();
    expect(status(4).getByText("Scheduled")).toBeInTheDocument();
  });

  it("describes what a coupon applies to", async () => {
    await renderPage([
      makeCoupon({ id: 1 }),
      makeCoupon({ id: 2, categories: [7], products: [3, 4] }),
      makeCoupon({ id: 3, categories: [7, 8] }),
    ]);
    const scope = (id) =>
      within(within(screen.getByTestId(`row-${id}`)).getByTestId("cell-scope"));
    expect(scope(1).getByText("Whole cart")).toBeInTheDocument();
    expect(scope(2).getByText("1 category + 2 products")).toBeInTheDocument();
    expect(scope(3).getByText("2 categories")).toBeInTheDocument();
  });

  it("requests the first page newest-first on mount", async () => {
    await renderPage();
    expect(adminAPI.getCoupons).toHaveBeenCalledWith({
      page: 1,
      search: "",
      ordering: "-created_at",
      page_size: 15,
    });
  });

  it("re-fetches with the search term", async () => {
    const user = await renderPage();
    await user.type(screen.getByTestId("dt-search"), "w");
    await waitFor(() =>
      expect(adminAPI.getCoupons).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "w", page: 1 }),
      ),
    );
  });

  it("shows the empty state when there are no coupons", async () => {
    await renderPage([]);
    expect(screen.getByTestId("dt-empty")).toHaveTextContent("No coupons found");
  });

  it("shows an error toast when loading fails", async () => {
    adminAPI.getCoupons.mockRejectedValue(new Error("boom"));
    render(<AdminCoupons />);
    await waitFor(() =>
      expect(capturedToasts).toContainEqual({
        message: "Failed to load coupons",
        type: "error",
      }),
    );
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 2. Quick deactivate
// ═════════════════════════════════════════════════════════════════════════════
describe("AdminCoupons — deactivate action", () => {
  it("PATCHes is_active=false for an active coupon, without opening the form", async () => {
    adminAPI.updateCoupon.mockResolvedValue({ data: {} });
    const user = await renderPage([makeCoupon({ id: 5, code: "SUMMER20" })]);

    await user.click(screen.getByRole("button", { name: "Deactivate" }));

    expect(adminAPI.updateCoupon).toHaveBeenCalledTimes(1);
    expect(adminAPI.updateCoupon).toHaveBeenCalledWith(5, { is_active: false });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(capturedToasts).toContainEqual({
        message: "SUMMER20 deactivated",
        type: "success",
      }),
    );
  });

  it("refreshes the list after deactivating", async () => {
    adminAPI.updateCoupon.mockResolvedValue({ data: {} });
    const user = await renderPage();
    adminAPI.getCoupons.mockClear();

    await user.click(screen.getByRole("button", { name: "Deactivate" }));

    await waitFor(() => expect(adminAPI.getCoupons).toHaveBeenCalledTimes(1));
  });

  it("offers Activate for an inactive coupon and PATCHes is_active=true", async () => {
    adminAPI.updateCoupon.mockResolvedValue({ data: {} });
    const user = await renderPage([makeCoupon({ id: 9, is_active: false })]);

    expect(screen.queryByRole("button", { name: "Deactivate" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Activate" }));

    expect(adminAPI.updateCoupon).toHaveBeenCalledWith(9, { is_active: true });
  });

  it("shows an error toast when the PATCH fails", async () => {
    adminAPI.updateCoupon.mockRejectedValue(new Error("nope"));
    const user = await renderPage();

    await user.click(screen.getByRole("button", { name: "Deactivate" }));

    await waitFor(() =>
      expect(capturedToasts).toContainEqual({
        message: "Failed to update coupon",
        type: "error",
      }),
    );
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 3. Form validation (client-side, before any request)
// ═════════════════════════════════════════════════════════════════════════════
describe("CouponModal — validation catches invalid input before submitting", () => {
  const openCreate = async () => {
    const user = await renderPage();
    await user.click(screen.getByRole("button", { name: /add coupon/i }));
    return user;
  };

  it("flags every required field on an empty submit and sends nothing", async () => {
    const user = await openCreate();
    await user.click(submitButton("Add Coupon"));

    const msgs = within(dialog()).getAllByRole("alert").map((n) => n.textContent);
    expect(msgs).toEqual(
      expect.arrayContaining([
        "Coupon code is required.",
        "Enter a discount value.",
        "Start date is required.",
        "End date is required.",
      ]),
    );
    expect(adminAPI.createCoupon).not.toHaveBeenCalled();
  });

  it.each([
    ["0", /percentage must be greater than 0 and at most 100/i],
    ["100.5", /percentage must be greater than 0 and at most 100/i],
    ["150", /percentage must be greater than 0 and at most 100/i],
    ["-5", /positive number with at most 2 decimal places/i],
  ])("rejects a percentage of %s", async (value, message) => {
    const user = await openCreate();
    await fillValid(user, { value });
    await user.click(submitButton("Add Coupon"));

    expect(within(dialog()).getByText(message)).toBeInTheDocument();
    expect(adminAPI.createCoupon).not.toHaveBeenCalled();
  });

  it("accepts a percentage of exactly 100", async () => {
    adminAPI.createCoupon.mockResolvedValue({ data: {} });
    const user = await openCreate();
    await fillValid(user, { value: "100" });
    await user.click(submitButton("Add Coupon"));
    await waitFor(() => expect(adminAPI.createCoupon).toHaveBeenCalled());
  });

  it("rejects a fixed amount of 0 but allows one above 100", async () => {
    adminAPI.createCoupon.mockResolvedValue({ data: {} });
    const user = await openCreate();
    await user.selectOptions(field(/discount type/i), "fixed");
    await fillValid(user, { value: "0" });
    await user.click(submitButton("Add Coupon"));
    expect(
      within(dialog()).getByText(/fixed amount must be greater than 0/i),
    ).toBeInTheDocument();
    expect(adminAPI.createCoupon).not.toHaveBeenCalled();

    await user.clear(field(/^value/i));
    await user.type(field(/^value/i), "250");
    await user.click(submitButton("Add Coupon"));
    await waitFor(() => expect(adminAPI.createCoupon).toHaveBeenCalled());
  });

  it("rejects an end date that is not after the start date", async () => {
    const user = await openCreate();
    await fillValid(user, { from: "2030-02-01T10:00", until: "2030-02-01T10:00" });
    await user.click(submitButton("Add Coupon"));

    expect(
      within(dialog()).getByText("End date must be after the start date."),
    ).toBeInTheDocument();
    expect(adminAPI.createCoupon).not.toHaveBeenCalled();
  });

  it("rejects non-positive usage limits and a negative minimum order", async () => {
    const user = await openCreate();
    await fillValid(user);
    fireEvent.change(field(/uses per customer/i), { target: { value: "0" } });
    fireEvent.change(field(/total uses/i), { target: { value: "0" } });
    fireEvent.change(field(/minimum order/i), { target: { value: "-1" } });
    await user.click(submitButton("Add Coupon"));

    const msgs = within(dialog()).getAllByRole("alert").map((n) => n.textContent);
    expect(msgs).toEqual(
      expect.arrayContaining([
        "Enter a whole number of 1 or more.",
        "Leave blank for unlimited, or enter a whole number of 1 or more.",
        "Enter 0 or a positive amount with at most 2 decimal places.",
      ]),
    );
    expect(adminAPI.createCoupon).not.toHaveBeenCalled();
  });

  it("clears a field's error as soon as the user edits it", async () => {
    const user = await openCreate();
    await user.click(submitButton("Add Coupon"));
    expect(within(dialog()).getByText("Coupon code is required.")).toBeInTheDocument();

    await user.type(field(/^code/i), "A");

    expect(within(dialog()).queryByText("Coupon code is required.")).not.toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 4. Create
// ═════════════════════════════════════════════════════════════════════════════
describe("CouponModal — create", () => {
  const openCreate = async () => {
    const user = await renderPage();
    await user.click(screen.getByRole("button", { name: /add coupon/i }));
    return user;
  };

  it("submits a normalised payload, then closes, refreshes and toasts", async () => {
    adminAPI.createCoupon.mockResolvedValue({ data: {} });
    const user = await openCreate();
    await fillValid(user, { code: "  summer20 ", value: "20" });
    adminAPI.getCoupons.mockClear();

    await user.click(submitButton("Add Coupon"));

    await waitFor(() => expect(adminAPI.createCoupon).toHaveBeenCalledTimes(1));
    expect(adminAPI.createCoupon).toHaveBeenCalledWith({
      code: "SUMMER20",
      discount_type: "percent",
      value: "20",
      min_order_amount: "0",
      max_uses: null,
      uses_per_user: 1,
      valid_from: new Date("2030-01-01T10:00").toISOString(),
      valid_until: new Date("2030-02-01T10:00").toISOString(),
      is_active: true,
      categories: [],
      products: [],
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(adminAPI.getCoupons).toHaveBeenCalled();
    expect(capturedToasts).toContainEqual({
      message: "Coupon saved successfully",
      type: "success",
    });
  });

  it("shows a server-side field error and keeps the form open", async () => {
    adminAPI.createCoupon.mockRejectedValue({
      response: { data: { code: ["A coupon with this code already exists."] } },
    });
    const user = await openCreate();
    await fillValid(user);

    await user.click(submitButton("Add Coupon"));

    expect(
      await within(dialog()).findByText("A coupon with this code already exists."),
    ).toBeInTheDocument();
    expect(submitButton("Add Coupon")).toBeEnabled();
  });

  it("shows a general error when the failure isn't field-specific", async () => {
    adminAPI.createCoupon.mockRejectedValue(new Error("network"));
    const user = await openCreate();
    await fillValid(user);

    await user.click(submitButton("Add Coupon"));

    expect(await within(dialog()).findByText("Failed to save coupon.")).toBeInTheDocument();
  });

  it("closes without saving on Cancel", async () => {
    const user = await openCreate();
    await user.click(submitButton("Cancel"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(adminAPI.createCoupon).not.toHaveBeenCalled();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 5. Edit
// ═════════════════════════════════════════════════════════════════════════════
describe("CouponModal — edit", () => {
  const coupon = makeCoupon({
    id: 3,
    code: "SUMMER20",
    max_uses: 100,
    categories: [7],
    products: [11],
    categories_detail: [{ id: 7, name: "Skincare" }],
    products_detail: [{ id: 11, name: "Vitamin C Serum" }],
  });

  const openEdit = async () => {
    const user = await renderPage([coupon]);
    await user.click(screen.getByRole("button", { name: "Edit" }));
    return user;
  };

  it("pre-fills the form, including the selected restrictions", async () => {
    await openEdit();
    expect(field(/^code/i)).toHaveValue("SUMMER20");
    expect(field(/^value/i)).toHaveValue(20);
    expect(field(/total uses/i)).toHaveValue(100);
    expect(within(screen.getByTestId("selected-categories")).getByText("Skincare")).toBeInTheDocument();
    expect(within(screen.getByTestId("selected-products")).getByText("Vitamin C Serum")).toBeInTheDocument();
    expect(submitButton("Save Changes")).toBeInTheDocument();
  });

  it("PATCHes only the fields that changed", async () => {
    adminAPI.updateCoupon.mockResolvedValue({ data: {} });
    const user = await openEdit();

    await user.clear(field(/^value/i));
    await user.type(field(/^value/i), "25");
    await user.click(submitButton("Save Changes"));

    await waitFor(() => expect(adminAPI.updateCoupon).toHaveBeenCalledTimes(1));
    expect(adminAPI.updateCoupon).toHaveBeenCalledWith(3, { value: "25" });
  });

  it("sends no request when nothing changed", async () => {
    const user = await openEdit();
    await user.click(submitButton("Save Changes"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(adminAPI.updateCoupon).not.toHaveBeenCalled();
  });

  it("can remove a restriction chip and sends the new id list", async () => {
    adminAPI.updateCoupon.mockResolvedValue({ data: {} });
    const user = await openEdit();

    await user.click(screen.getByRole("button", { name: "Remove Vitamin C Serum" }));
    await user.click(submitButton("Save Changes"));

    await waitFor(() =>
      expect(adminAPI.updateCoupon).toHaveBeenCalledWith(3, { products: [] }),
    );
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 6. Category / product pickers
// ═════════════════════════════════════════════════════════════════════════════
describe("CouponModal — restriction pickers", () => {
  const openCreate = async () => {
    const user = await renderPage();
    await user.click(screen.getByRole("button", { name: /add coupon/i }));
    return user;
  };

  it("loads every page of categories and labels sub-categories with their parent", async () => {
    adminAPI.getCategories
      .mockResolvedValueOnce({
        data: { results: [{ id: 1, name: "Skincare", parent_name: "" }], next: "page-2" },
      })
      .mockResolvedValueOnce({
        data: { results: [{ id: 2, name: "Serums", parent_name: "Skincare" }], next: null },
      });
    await openCreate();

    expect(await within(dialog()).findByText("Skincare › Serums")).toBeInTheDocument();
    expect(within(dialog()).getByText("Skincare")).toBeInTheDocument();
    expect(adminAPI.getCategories).toHaveBeenCalledTimes(2);
    expect(adminAPI.getCategories).toHaveBeenNthCalledWith(2, { page: 2, page_size: 100 });
  });

  it("submits the ids of ticked categories", async () => {
    adminAPI.createCoupon.mockResolvedValue({ data: {} });
    adminAPI.getCategories.mockResolvedValue(
      paged([{ id: 4, name: "Skincare", parent_name: "" }]),
    );
    const user = await openCreate();
    await fillValid(user);

    await user.click(await within(dialog()).findByLabelText("Skincare"));
    await user.click(submitButton("Add Coupon"));

    await waitFor(() =>
      expect(adminAPI.createCoupon).toHaveBeenCalledWith(
        expect.objectContaining({ categories: [4], products: [] }),
      ),
    );
  });

  it("searches products, adds one as a chip and submits its id", async () => {
    adminAPI.createCoupon.mockResolvedValue({ data: {} });
    adminAPI.getProducts.mockResolvedValue(
      paged([{ id: 21, name: "Vitamin C Serum" }]),
    );
    const user = await openCreate();
    await fillValid(user);

    await user.type(within(dialog()).getByLabelText("Search products"), "serum");
    const result = await within(dialog()).findByRole("button", { name: "Vitamin C Serum" });
    expect(adminAPI.getProducts).toHaveBeenCalledWith({ search: "serum", page_size: 8 });

    await user.click(result);
    expect(
      within(screen.getByTestId("selected-products")).getByText("Vitamin C Serum"),
    ).toBeInTheDocument();

    await user.click(submitButton("Add Coupon"));
    await waitFor(() =>
      expect(adminAPI.createCoupon).toHaveBeenCalledWith(
        expect.objectContaining({ products: [21] }),
      ),
    );
  });

  it("doesn't add the same product twice", async () => {
    adminAPI.getProducts.mockResolvedValue(paged([{ id: 21, name: "Vitamin C Serum" }]));
    const user = await openCreate();

    await user.type(within(dialog()).getByLabelText("Search products"), "serum");
    const result = await within(dialog()).findByRole("button", { name: /Vitamin C Serum/ });
    await user.click(result);

    expect(within(screen.getByTestId("selected-products")).getAllByText("Vitamin C Serum")).toHaveLength(1);
    expect(result).toBeDisabled();
  });
});
