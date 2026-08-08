/**
 * AdminBrands.test.jsx
 *
 * Comprehensive unit & integration tests for AdminBrands.jsx
 * Stack : Vitest · React Testing Library · @testing-library/user-event v14
 *
 * ── Coverage areas ────────────────────────────────────────────────────────────
 *  1.  Page structure    – heading, subtitle with total, "Add Brand" button
 *  2.  fetchBrands       – mount params, loading state, paginated response,
 *                          flat-array response, error toast
 *  3.  COLUMNS renderers – logo_url (img vs placeholder), name, slug,
 *                          product_count badge
 *  4.  Search            – re-fetch with search param, page reset to 1
 *  5.  Sort              – re-fetch with new ordering
 *  6.  Pagination        – re-fetch with new page number
 *  7.  Empty state       – "No brands found"
 *  8.  Delete flow       – ConfirmModal message, deleteBrand(id),
 *                          success toast, modal close, re-fetch
 *  9.  Delete error      – linked-products error toast
 * 10.  Delete cancel     – modal closes, API not called
 * 11.  Deleting state    – confirm button disabled while in-flight
 * 12.  BrandModal (new)  – heading, fields, validation, createBrand FormData,
 *                          onSaved/onClose, re-fetch, toast, API error paths,
 *                          saving state, backdrop/cancel close
 * 13.  BrandModal (edit) – heading, pre-fill name, pre-fill logo preview,
 *                          updateBrand(id, FormData), "Save Changes" label
 * 14.  Logo upload       – preview shown, button label "Change", FormData entry
 * 15.  Logo remove       – preview cleared, placeholder restored, "Upload Logo"
 * 16.  Snapshot          – stable rendered output after data loads
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  waitFor,
  within,
  fireEvent,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AdminBrands from "../../pages/admin/AdminBrands";

// ─── jsdom stubs ──────────────────────────────────────────────────────────────
global.URL.createObjectURL = vi.fn(() => "blob:mock-preview-url");
global.URL.revokeObjectURL = vi.fn();

// ─── Mock: DataTable ──────────────────────────────────────────────────────────
// Renders every column cell and row-actions so column render-fns are exercised.
vi.mock("../../components/admin/DataTable", () => ({
  default: ({
    columns,
    data,
    loading,
    emptyText,
    rowActions,
    search,
    onSearch,
    onSort,
    onPageChange,
    searchPlaceholder,
    totalCount,
    page,
  }) => {
    if (loading) return <div data-testid="dt-loading">Loading…</div>;
    return (
      <div data-testid="data-table">
        {/* search */}
        <input
          data-testid="dt-search"
          placeholder={searchPlaceholder}
          value={search ?? ""}
          onChange={(e) => onSearch?.(e.target.value)}
        />
        {/* sort trigger – exposes onSort for testing */}
        <button
          data-testid="dt-sort"
          onClick={() => onSort?.("-name")}
        >
          sort
        </button>
        {/* page trigger – exposes onPageChange */}
        <button
          data-testid="dt-next-page"
          onClick={() => onPageChange?.(page + 1)}
        >
          next
        </button>
        {/* total count */}
        <span data-testid="dt-total">{totalCount}</span>

        {data.length === 0 && (
          <div data-testid="dt-empty">{emptyText}</div>
        )}

        {data.map((row, ri) => (
          <div key={row.id ?? ri} data-testid={`dt-row-${ri}`}>
            {columns.map((col) => (
              <div key={col.key} data-testid={`cell-${col.key}`}>
                {col.render
                  ? col.render(row[col.key], row)
                  : String(row[col.key] ?? "")}
              </div>
            ))}
            {rowActions && (
              <div data-testid="row-actions">{rowActions(row)}</div>
            )}
          </div>
        ))}
      </div>
    );
  },
}));

// ─── Mock: ConfirmModal ───────────────────────────────────────────────────────
vi.mock("../../components/admin/ConfirmModal", () => ({
  default: ({ isOpen, title, message, confirmLabel, onConfirm, onClose, loading }) =>
    isOpen ? (
      <div data-testid="confirm-modal">
        <p data-testid="confirm-title">{title}</p>
        <p data-testid="confirm-message">{message}</p>
        <button
          data-testid="confirm-btn"
          onClick={onConfirm}
          disabled={loading}
        >
          {loading ? "Deleting…" : confirmLabel}
        </button>
        <button data-testid="confirm-cancel" onClick={onClose}>
          Cancel
        </button>
      </div>
    ) : null,
}));

// ─── Mock: Toast / useToast ───────────────────────────────────────────────────
// capturedToasts lets every test inspect show() calls without DOM assertions.
let capturedToasts = [];

vi.mock("../../components/admin/Toast", () => ({
  default: ({ toast, onDismiss }) =>
    toast ? (
      <div data-testid="toast" data-type={toast.type}>
        {toast.message}
        <button data-testid="toast-dismiss" onClick={onDismiss}>×</button>
      </div>
    ) : null,

  useToast: () => ({
    toast: null,
    show: (message, type = "success") => {
      capturedToasts.push({ message, type });
    },
    dismiss: () => { },
  }),
}));

// ─── Mock: adminAPI ───────────────────────────────────────────────────────────
vi.mock("../../services/api", () => ({
  adminAPI: {
    getBrands: vi.fn(),
    createBrand: vi.fn(),
    updateBrand: vi.fn(),
    deleteBrand: vi.fn(),
  },
}));

import { adminAPI } from "../../services/api";

// ─── Fixture factories ────────────────────────────────────────────────────────
const makeBrand = (overrides = {}) => ({
  id: 1,
  name: "Nike",
  slug: "nike",
  product_count: 42,
  logo_url: null,
  ...overrides,
});

const makeBrands = (n = 3) =>
  Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    name: `Brand ${i + 1}`,
    slug: `brand-${i + 1}`,
    product_count: (i + 1) * 5,
    logo_url: i === 0 ? `https://cdn.example.com/logo-${i + 1}.png` : null,
  }));

/** Paginated response shape { data: { results, count } } */
const paged = (results, count) => ({ data: { results, count } });
/** Flat array response shape { data: [...] } */
const flat = (arr) => ({ data: arr });

// ─── Setup helpers ────────────────────────────────────────────────────────────
const okBrands = (brands = makeBrands()) =>
  adminAPI.getBrands.mockResolvedValue(paged(brands, brands.length));

const setup = () => userEvent.setup();

// Modal DOM helper – returns the inner card element (stops propagation).
// The modal backdrop is `.fixed.inset-0`; the card is `.rounded-2xl` inside it.
const getModalCard = () =>
  document.querySelector(".fixed.inset-0 .rounded-2xl");

// ─────────────────────────────────────────────────────────────────────────────

describe("AdminBrands", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedToasts = [];
    okBrands();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. Page structure ────────────────────────────────────────────────────
  describe("Page structure", () => {
    it("renders the 'Brands' heading", async () => {
      render(<AdminBrands />);
      expect(
        screen.getByRole("heading", { name: /^brands$/i })
      ).toBeInTheDocument();
    });

    it("renders the 'Add Brand' button", async () => {
      render(<AdminBrands />);
      expect(
        screen.getByRole("button", { name: /add brand/i })
      ).toBeInTheDocument();
    });

    it("shows '0 total brands' before data loads", () => {
      // Keep the promise pending so we can inspect the initial state
      adminAPI.getBrands.mockReturnValue(new Promise(() => { }));
      render(<AdminBrands />);
      expect(screen.getByText(/0 total brands/i)).toBeInTheDocument();
    });

    it("shows total count in subtitle after data loads", async () => {
      okBrands(makeBrands(7));
      adminAPI.getBrands.mockResolvedValue(paged(makeBrands(7), 7));
      render(<AdminBrands />);
      await waitFor(() =>
        expect(screen.getByText("7 total brands")).toBeInTheDocument()
      );
    });
  });

  // ── 2. fetchBrands ───────────────────────────────────────────────────────
  describe("fetchBrands – initial fetch", () => {
    it("calls getBrands on mount with correct default params", async () => {
      render(<AdminBrands />);
      await waitFor(() =>
        expect(adminAPI.getBrands).toHaveBeenCalledWith({
          page: 1,
          search: "",
          ordering: "name",
          page_size: 15,
        })
      );
    });

    it("passes loading=true to DataTable while fetching", () => {
      adminAPI.getBrands.mockReturnValue(new Promise(() => { }));
      render(<AdminBrands />);
      expect(screen.getByTestId("dt-loading")).toBeInTheDocument();
    });

    it("removes loading state after data resolves", async () => {
      render(<AdminBrands />);
      await waitFor(() =>
        expect(screen.queryByTestId("dt-loading")).not.toBeInTheDocument()
      );
    });

    it("renders brand rows from paginated response", async () => {
      render(<AdminBrands />);
      await waitFor(() => {
        expect(screen.getByText("Brand 1")).toBeInTheDocument();
        expect(screen.getByText("Brand 2")).toBeInTheDocument();
        expect(screen.getByText("Brand 3")).toBeInTheDocument();
      });
    });

    it("handles flat array API response", async () => {
      adminAPI.getBrands.mockResolvedValue(flat(makeBrands(2)));
      render(<AdminBrands />);
      await waitFor(() => {
        expect(screen.getByText("Brand 1")).toBeInTheDocument();
        expect(screen.getByText("Brand 2")).toBeInTheDocument();
      });
    });

    it("shows 'Failed to load brands' error toast on getBrands failure", async () => {
      adminAPI.getBrands.mockRejectedValue(new Error("net"));
      render(<AdminBrands />);
      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === "Failed to load brands" && t.type === "error"
          )
        ).toBe(true)
      );
    });

    it("removes loading state even after API error", async () => {
      adminAPI.getBrands.mockRejectedValue(new Error("net"));
      render(<AdminBrands />);
      await waitFor(() =>
        expect(screen.queryByTestId("dt-loading")).not.toBeInTheDocument()
      );
    });

    it("sets total from paginated count field", async () => {
      adminAPI.getBrands.mockResolvedValue(paged(makeBrands(3), 99));
      render(<AdminBrands />);
      await waitFor(() =>
        expect(screen.getByText("99 total brands")).toBeInTheDocument()
      );
    });

    it("derives total from flat array length when count is absent", async () => {
      adminAPI.getBrands.mockResolvedValue(flat(makeBrands(5)));
      render(<AdminBrands />);
      await waitFor(() =>
        expect(screen.getByText("5 total brands")).toBeInTheDocument()
      );
    });
  });

  // ── 3. COLUMNS render functions ──────────────────────────────────────────
  describe("Column renderers", () => {
    describe("logo_url column", () => {
      it("renders <img> with brand name as alt when logo_url is present", async () => {
        adminAPI.getBrands.mockResolvedValue(
          paged([makeBrand({ name: "Nike", logo_url: "https://cdn.test/nike.png" })], 1)
        );
        render(<AdminBrands />);
        await waitFor(() => {
          const img = screen.getByRole("img", { name: "Nike" });
          expect(img).toHaveAttribute("src", "https://cdn.test/nike.png");
        });
      });

      it("renders placeholder icon when logo_url is null", async () => {
        adminAPI.getBrands.mockResolvedValue(
          paged([makeBrand({ logo_url: null })], 1)
        );
        const { container } = render(<AdminBrands />);
        await waitFor(() => {
          // logo_url cell should contain the fallback icon, not an img
          const logoCell = screen.getByTestId("cell-logo_url");
          expect(within(logoCell).queryByRole("img")).not.toBeInTheDocument();
          expect(
            container.querySelector(".bi-award")
          ).toBeInTheDocument();
        });
      });

      it("does NOT render <img> when logo_url is empty string", async () => {
        adminAPI.getBrands.mockResolvedValue(
          paged([makeBrand({ logo_url: "" })], 1)
        );
        render(<AdminBrands />);
        await waitFor(() => {
          const logoCell = screen.getByTestId("cell-logo_url");
          expect(within(logoCell).queryByRole("img")).not.toBeInTheDocument();
        });
      });
    });

    describe("name column", () => {
      it("renders brand name inside a <span>", async () => {
        adminAPI.getBrands.mockResolvedValue(
          paged([makeBrand({ name: "Adidas" })], 1)
        );
        render(<AdminBrands />);
        await waitFor(() => {
          const nameCell = screen.getByTestId("cell-name");
          const span = within(nameCell).getByText("Adidas");
          expect(span.tagName).toBe("SPAN");
        });
      });
    });

    describe("slug column", () => {
      it("renders slug inside a <code> element", async () => {
        adminAPI.getBrands.mockResolvedValue(
          paged([makeBrand({ slug: "adidas" })], 1)
        );
        render(<AdminBrands />);
        await waitFor(() => {
          const slugCell = screen.getByTestId("cell-slug");
          const code = within(slugCell).getByText("adidas");
          expect(code.tagName).toBe("CODE");
        });
      });
    });

    describe("product_count column", () => {
      it("renders product_count with teal badge styles", async () => {
        adminAPI.getBrands.mockResolvedValue(
          paged([makeBrand({ product_count: 17 })], 1)
        );
        const { container } = render(<AdminBrands />);
        await waitFor(() => {
          const badge = container.querySelector(".bg-teal-50");
          expect(badge).toBeInTheDocument();
          expect(badge).toHaveTextContent("17");
        });
      });
    });
  });

  // ── 4. Search ────────────────────────────────────────────────────────────
  describe("Search", () => {
    it("re-fetches with search param when user types", async () => {
      const user = setup();
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));

      vi.clearAllMocks();
      okBrands();

      // Use fireEvent to set the value instantly
      fireEvent.change(screen.getByPlaceholderText("Search brands…"), {
        target: { value: "Nike" },
      });

      await waitFor(() =>
        expect(adminAPI.getBrands).toHaveBeenCalledWith(
          expect.objectContaining({ search: "Nike" })
        )
      );
    });

    it("resets page to 1 when search changes", async () => {
      const user = setup();
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));

      // Advance to page 2 first
      await user.click(screen.getByTestId("dt-next-page"));
      await waitFor(() =>
        expect(adminAPI.getBrands).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );

      vi.clearAllMocks();
      okBrands();

      await user.type(screen.getByPlaceholderText("Search brands…"), "x");

      await waitFor(() =>
        expect(adminAPI.getBrands).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1 })
        )
      );
    });
  });

  // ── 5. Sort ──────────────────────────────────────────────────────────────
  describe("Sort", () => {
    it("re-fetches with new ordering when sort changes", async () => {
      const user = setup();
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));

      vi.clearAllMocks();
      okBrands();

      // The DataTable mock exposes a sort button that calls onSort("-name")
      await user.click(screen.getByTestId("dt-sort"));

      await waitFor(() =>
        expect(adminAPI.getBrands).toHaveBeenCalledWith(
          expect.objectContaining({ ordering: "-name" })
        )
      );
    });
  });

  // ── 6. Pagination ────────────────────────────────────────────────────────
  describe("Pagination", () => {
    it("re-fetches with page 2 when next-page is clicked", async () => {
      const user = setup();
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));

      vi.clearAllMocks();
      okBrands();

      await user.click(screen.getByTestId("dt-next-page"));

      await waitFor(() =>
        expect(adminAPI.getBrands).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );
    });
  });

  // ── 7. Empty state ───────────────────────────────────────────────────────
  describe("Empty state", () => {
    it("shows 'No brands found' when results are empty", async () => {
      adminAPI.getBrands.mockResolvedValue(paged([], 0));
      render(<AdminBrands />);
      await waitFor(() =>
        expect(screen.getByTestId("dt-empty")).toHaveTextContent("No brands found")
      );
    });
  });

  // ── 8. Delete – happy path ────────────────────────────────────────────────
  describe("Delete – success", () => {
    const openDeleteConfirm = async (user) => {
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
    };

    it("opens ConfirmModal when Delete action is clicked", async () => {
      const user = setup();
      await openDeleteConfirm(user);
      expect(screen.getByTestId("confirm-modal")).toBeInTheDocument();
    });

    it("ConfirmModal title is 'Delete Brand'", async () => {
      const user = setup();
      await openDeleteConfirm(user);
      expect(screen.getByTestId("confirm-title")).toHaveTextContent("Delete Brand");
    });

    it("ConfirmModal message includes the brand name", async () => {
      const user = setup();
      await openDeleteConfirm(user);
      expect(screen.getByTestId("confirm-message")).toHaveTextContent(
        `Delete "Brand 1"?`
      );
    });

    it("ConfirmModal message warns about product association loss", async () => {
      const user = setup();
      await openDeleteConfirm(user);
      expect(screen.getByTestId("confirm-message")).toHaveTextContent(
        "Products linked to this brand will lose their brand association."
      );
    });

    it("calls deleteBrand with the correct brand id on confirm", async () => {
      adminAPI.deleteBrand.mockResolvedValue({});
      const user = setup();
      await openDeleteConfirm(user);
      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(adminAPI.deleteBrand).toHaveBeenCalledWith(1)
      );
    });

    it("shows 'Brand deleted' success toast after confirm", async () => {
      adminAPI.deleteBrand.mockResolvedValue({});
      const user = setup();
      await openDeleteConfirm(user);
      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === "Brand deleted" && t.type === "success")
        ).toBe(true)
      );
    });

    it("closes ConfirmModal after successful delete", async () => {
      adminAPI.deleteBrand.mockResolvedValue({});
      const user = setup();
      await openDeleteConfirm(user);
      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(screen.queryByTestId("confirm-modal")).not.toBeInTheDocument()
      );
    });

    it("re-fetches brand list after successful delete", async () => {
      adminAPI.deleteBrand.mockResolvedValue({});
      const user = setup();
      await openDeleteConfirm(user);

      vi.clearAllMocks();
      okBrands();

      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(adminAPI.getBrands).toHaveBeenCalledTimes(1)
      );
    });
  });

  // ── 9. Delete – error path ────────────────────────────────────────────────
  describe("Delete – error", () => {
    it("shows linked-products error toast when deleteBrand fails", async () => {
      adminAPI.deleteBrand.mockRejectedValue(new Error("409 conflict"));
      const user = setup();
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));
      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) =>
              t.message === "Failed to delete. Brand may have linked products." &&
              t.type === "error"
          )
        ).toBe(true)
      );
    });

    it("keeps ConfirmModal open after a failed delete", async () => {
      adminAPI.deleteBrand.mockRejectedValue(new Error("500"));
      const user = setup();
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));
      // Modal should remain because setConfirm(null) is only called on success
      await waitFor(() =>
        expect(screen.getByTestId("confirm-modal")).toBeInTheDocument()
      );
    });
  });

  // ── 10. Delete – cancel ───────────────────────────────────────────────────
  describe("Delete – cancel", () => {
    it("closes ConfirmModal when Cancel is clicked", async () => {
      const user = setup();
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-cancel"));
      await waitFor(() =>
        expect(screen.queryByTestId("confirm-modal")).not.toBeInTheDocument()
      );
    });

    it("does NOT call deleteBrand when Cancel is clicked", async () => {
      const user = setup();
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-cancel"));
      expect(adminAPI.deleteBrand).not.toHaveBeenCalled();
    });
  });

  // ── 11. Deleting state ────────────────────────────────────────────────────
  describe("Deleting in-flight state", () => {
    it("disables confirm button while delete is in-flight", async () => {
      let resolveDelete;
      adminAPI.deleteBrand.mockReturnValue(
        new Promise((res) => { resolveDelete = res; })
      );
      const user = setup();
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));

      await waitFor(() =>
        expect(screen.getByTestId("confirm-btn")).toBeDisabled()
      );

      resolveDelete({}); // cleanup
    });

    it("shows 'Deleting…' label on confirm button while in-flight", async () => {
      let resolveDelete;
      adminAPI.deleteBrand.mockReturnValue(
        new Promise((res) => { resolveDelete = res; })
      );
      const user = setup();
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));
      await user.click(within(screen.getByTestId("dt-row-0")).getByTitle("Delete"));
      await user.click(screen.getByTestId("confirm-btn"));

      await waitFor(() =>
        expect(screen.getByTestId("confirm-btn")).toHaveTextContent("Deleting…")
      );

      resolveDelete({});
    });
  });

  // ── 12. BrandModal – creating a new brand ────────────────────────────────
  describe("BrandModal – new brand", () => {
    const openNew = async (user) => {
      render(<AdminBrands />);
      await waitFor(() =>
        expect(screen.getByRole("button", { name: /add brand/i })).toBeInTheDocument()
      );
      await user.click(screen.getByRole("button", { name: /add brand/i }));
      await waitFor(() =>
        expect(screen.getByRole("heading", { name: /add brand/i })).toBeInTheDocument()
      );
    };

    it("opens BrandModal with 'Add Brand' heading", async () => {
      const user = setup();
      await openNew(user);
      expect(screen.getByRole("heading", { name: /add brand/i })).toBeInTheDocument();
    });

    it("shows the name input with placeholder 'e.g. Nike'", async () => {
      const user = setup();
      await openNew(user);
      expect(
        within(getModalCard()).getByPlaceholderText("e.g. Nike")
      ).toBeInTheDocument();
    });

    it("submit button label is 'Add Brand' for new modal", async () => {
      const user = setup();
      await openNew(user);
      expect(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      ).toBeInTheDocument();
    });

    // ── Validation ──────────────────────────────────────────────────────────
    it("shows 'Brand name is required.' when submitting with blank name", async () => {
      const user = setup();
      await openNew(user);
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );
      await waitFor(() =>
        expect(screen.getByText("Brand name is required.")).toBeInTheDocument()
      );
    });

    it("does NOT call createBrand when name is blank", async () => {
      const user = setup();
      await openNew(user);
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );
      expect(adminAPI.createBrand).not.toHaveBeenCalled();
    });

    it("clears validation error when user types in name field", async () => {
      const user = setup();
      await openNew(user);

      // Trigger error
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );
      await waitFor(() =>
        expect(screen.getByText("Brand name is required.")).toBeInTheDocument()
      );

      // Fix it
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "A"
      );
      await waitFor(() =>
        expect(screen.queryByText("Brand name is required.")).not.toBeInTheDocument()
      );
    });

    it("trims whitespace-only input and shows validation error", async () => {
      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "   "
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );
      await waitFor(() =>
        expect(screen.getByText("Brand name is required.")).toBeInTheDocument()
      );
    });

    // ── Successful create ───────────────────────────────────────────────────
    it("calls createBrand with a FormData containing the trimmed name", async () => {
      adminAPI.createBrand.mockResolvedValue({ data: { id: 10 } });
      const user = setup();
      await openNew(user);

      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "  Puma  "
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );

      await waitFor(() => {
        expect(adminAPI.createBrand).toHaveBeenCalledWith(expect.any(FormData));
        const fd = adminAPI.createBrand.mock.calls[0][0];
        expect(fd.get("name")).toBe("Puma");
      });
    });

    it("does NOT append logo to FormData when no file is selected", async () => {
      adminAPI.createBrand.mockResolvedValue({ data: {} });
      const appendSpy = vi.spyOn(FormData.prototype, "append");

      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "Reebok"
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );

      await waitFor(() => expect(adminAPI.createBrand).toHaveBeenCalled());

      const logoCalls = appendSpy.mock.calls.filter(([key]) => key === "logo");
      expect(logoCalls).toHaveLength(0);
    });

    it("appends logo file to FormData when a file is selected", async () => {
      adminAPI.createBrand.mockResolvedValue({ data: {} });
      const appendSpy = vi.spyOn(FormData.prototype, "append");

      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "NewBrand"
      );

      const file = new File(["pixel"], "logo.png", { type: "image/png" });
      const fileInput = getModalCard().querySelector('input[type="file"]');
      await user.upload(fileInput, file);

      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );

      await waitFor(() => {
        const logoCalls = appendSpy.mock.calls.filter(([key]) => key === "logo");
        expect(logoCalls).toHaveLength(1);
        expect(logoCalls[0][1]).toBeInstanceOf(File);
      });
    });

    it("closes modal after successful create", async () => {
      adminAPI.createBrand.mockResolvedValue({ data: {} });
      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "Converse"
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );
      await waitFor(() =>
        expect(
          screen.queryByRole("heading", { name: /add brand/i })
        ).not.toBeInTheDocument()
      );
    });

    it("shows 'Brand saved successfully' toast after successful create", async () => {
      adminAPI.createBrand.mockResolvedValue({ data: {} });
      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "Converse"
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === "Brand saved successfully")
        ).toBe(true)
      );
    });

    it("re-fetches brand list after successful create", async () => {
      adminAPI.createBrand.mockResolvedValue({ data: {} });
      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "Converse"
      );

      vi.clearAllMocks();
      okBrands();

      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );

      await waitFor(() =>
        expect(adminAPI.getBrands).toHaveBeenCalledTimes(1)
      );
    });

    // ── API error paths ─────────────────────────────────────────────────────
    it("shows name error from API response data.name[0]", async () => {
      adminAPI.createBrand.mockRejectedValue({
        response: { data: { name: ["A brand with this name already exists."] } },
      });
      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "Nike"
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );
      await waitFor(() =>
        expect(
          screen.getByText("A brand with this name already exists.")
        ).toBeInTheDocument()
      );
    });

    it("shows generic fallback error when API error has no name field", async () => {
      adminAPI.createBrand.mockRejectedValue({ response: { data: {} } });
      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "Oops"
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );
      await waitFor(() =>
        expect(screen.getByText("Failed to save brand.")).toBeInTheDocument()
      );
    });

    it("shows generic fallback error when error has no response object", async () => {
      adminAPI.createBrand.mockRejectedValue(new Error("Network error"));
      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "Oops"
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );
      await waitFor(() =>
        expect(screen.getByText("Failed to save brand.")).toBeInTheDocument()
      );
    });

    // ── Saving in-flight state ──────────────────────────────────────────────
    it("disables submit button while request is in-flight", async () => {
      let resolve;
      adminAPI.createBrand.mockReturnValue(new Promise((r) => { resolve = r; }));
      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "Puma"
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );

      await waitFor(() =>
        expect(
          within(getModalCard()).getByRole("button", { name: /saving…/i })
        ).toBeDisabled()
      );

      resolve({ data: {} });
    });

    it("shows 'Saving…' on submit button while in-flight", async () => {
      let resolve;
      adminAPI.createBrand.mockReturnValue(new Promise((r) => { resolve = r; }));
      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "Puma"
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );

      await waitFor(() =>
        expect(
          within(getModalCard()).getByRole("button", { name: /saving…/i })
        ).toBeInTheDocument()
      );

      resolve({ data: {} });
    });

    // ── Close behaviours ────────────────────────────────────────────────────
    it("closes modal when backdrop is clicked", async () => {
      const user = setup();
      await openNew(user);

      fireEvent.click(document.querySelector(".fixed.inset-0"));

      await waitFor(() =>
        expect(
          screen.queryByRole("heading", { name: /add brand/i })
        ).not.toBeInTheDocument()
      );
    });

    it("clicking inner modal card does NOT close the modal", async () => {
      const user = setup();
      await openNew(user);

      fireEvent.click(getModalCard());

      expect(
        screen.getByRole("heading", { name: /add brand/i })
      ).toBeInTheDocument();
    });

    it("closes modal when Cancel button is clicked", async () => {
      const user = setup();
      await openNew(user);

      await user.click(
        within(getModalCard()).getByRole("button", { name: /^cancel$/i })
      );

      await waitFor(() =>
        expect(
          screen.queryByRole("heading", { name: /add brand/i })
        ).not.toBeInTheDocument()
      );
    });

    it("closes modal when the × icon button is clicked", async () => {
      const user = setup();
      await openNew(user);

      // The × close button is in the modal header (contains .bi-x-lg)
      const closeBtn = getModalCard().querySelector(".bi-x-lg")?.closest("button");
      expect(closeBtn).not.toBeNull();
      await user.click(closeBtn);

      await waitFor(() =>
        expect(
          screen.queryByRole("heading", { name: /add brand/i })
        ).not.toBeInTheDocument()
      );
    });

    it("does NOT call createBrand when Cancel is clicked", async () => {
      const user = setup();
      await openNew(user);
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "Puma"
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^cancel$/i })
      );
      expect(adminAPI.createBrand).not.toHaveBeenCalled();
    });
  });

  // ── 13. BrandModal – editing an existing brand ────────────────────────────
  describe("BrandModal – edit brand", () => {
    const openEdit = async (user, brandOverrides = {}) => {
      adminAPI.getBrands.mockResolvedValue(
        paged([makeBrand({ name: "Nike", slug: "nike", ...brandOverrides })], 1)
      );
      render(<AdminBrands />);
      await waitFor(() => screen.getByText("Nike"));
      await user.click(
        within(screen.getByTestId("dt-row-0")).getByTitle("Edit")
      );
      await waitFor(() =>
        expect(
          screen.getByRole("heading", { name: /edit brand/i })
        ).toBeInTheDocument()
      );
    };

    it("opens modal with 'Edit Brand' heading", async () => {
      const user = setup();
      await openEdit(user);
      expect(screen.getByRole("heading", { name: /edit brand/i })).toBeInTheDocument();
    });

    it("pre-fills name input with the brand's existing name", async () => {
      const user = setup();
      await openEdit(user);
      expect(
        within(getModalCard()).getByPlaceholderText("e.g. Nike")
      ).toHaveValue("Nike");
    });

    it("submit button label is 'Save Changes' for edit modal", async () => {
      const user = setup();
      await openEdit(user);
      expect(
        within(getModalCard()).getByRole("button", { name: /save changes/i })
      ).toBeInTheDocument();
    });

    it("calls updateBrand with the brand id and FormData", async () => {
      adminAPI.updateBrand.mockResolvedValue({ data: {} });
      const user = setup();
      await openEdit(user);

      // Name is pre-filled; just submit
      await user.click(
        within(getModalCard()).getByRole("button", { name: /save changes/i })
      );

      await waitFor(() =>
        expect(adminAPI.updateBrand).toHaveBeenCalledWith(1, expect.any(FormData))
      );
    });

    it("sends the correct name in FormData on update", async () => {
      adminAPI.updateBrand.mockResolvedValue({ data: {} });
      const user = setup();
      await openEdit(user);

      const nameInput = within(getModalCard()).getByPlaceholderText("e.g. Nike");
      await user.clear(nameInput);
      await user.type(nameInput, "Renamed Brand");
      await user.click(
        within(getModalCard()).getByRole("button", { name: /save changes/i })
      );

      await waitFor(() => {
        const fd = adminAPI.updateBrand.mock.calls[0][1];
        expect(fd.get("name")).toBe("Renamed Brand");
      });
    });

    it("does NOT call createBrand when editing", async () => {
      adminAPI.updateBrand.mockResolvedValue({ data: {} });
      const user = setup();
      await openEdit(user);
      await user.click(
        within(getModalCard()).getByRole("button", { name: /save changes/i })
      );
      await waitFor(() => expect(adminAPI.updateBrand).toHaveBeenCalled());
      expect(adminAPI.createBrand).not.toHaveBeenCalled();
    });

    it("shows existing logo_url as preview image when brand has a logo", async () => {
      const user = setup();
      await openEdit(user, { logo_url: "https://cdn.test/nike-logo.png" });

      const preview = within(getModalCard()).getByAltText("Logo preview");
      expect(preview).toHaveAttribute("src", "https://cdn.test/nike-logo.png");
    });

    it("shows 'Change' button label when existing logo is present", async () => {
      const user = setup();
      await openEdit(user, { logo_url: "https://cdn.test/nike-logo.png" });

      expect(
        // Add ^ and $ anchors to target exactly "Change"
        within(getModalCard()).getByRole("button", { name: /^change$/i })
      ).toBeInTheDocument();
    });

    it("shows placeholder icon (not img) when brand has no logo", async () => {
      const user = setup();
      await openEdit(user, { logo_url: null });

      expect(
        within(getModalCard()).queryByAltText("Logo preview")
      ).not.toBeInTheDocument();
      expect(
        within(getModalCard()).getByRole("button", { name: /upload logo/i })
      ).toBeInTheDocument();
    });

    it("shows 'Brand saved successfully' toast after successful update", async () => {
      adminAPI.updateBrand.mockResolvedValue({ data: {} });
      const user = setup();
      await openEdit(user);
      await user.click(
        within(getModalCard()).getByRole("button", { name: /save changes/i })
      );
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === "Brand saved successfully")
        ).toBe(true)
      );
    });

    it("closes modal after successful update", async () => {
      adminAPI.updateBrand.mockResolvedValue({ data: {} });
      const user = setup();
      await openEdit(user);
      await user.click(
        within(getModalCard()).getByRole("button", { name: /save changes/i })
      );
      await waitFor(() =>
        expect(
          screen.queryByRole("heading", { name: /edit brand/i })
        ).not.toBeInTheDocument()
      );
    });
  });

  // ── 14. Logo upload ───────────────────────────────────────────────────────
  describe("Logo upload", () => {
    const openNewModal = async (user) => {
      render(<AdminBrands />);
      await waitFor(() =>
        expect(screen.getByRole("button", { name: /add brand/i })).toBeInTheDocument()
      );
      await user.click(screen.getByRole("button", { name: /add brand/i }));
      await waitFor(() =>
        expect(screen.getByRole("heading", { name: /add brand/i })).toBeInTheDocument()
      );
    };

    it("shows preview image after a file is uploaded", async () => {
      const user = setup();
      await openNewModal(user);

      const fakeUrl = "blob:http://localhost/abc-123";
      global.URL.createObjectURL = vi.fn().mockReturnValue(fakeUrl);

      const fileInput = getModalCard().querySelector('input[type="file"]');
      const file = new File(["img"], "logo.png", { type: "image/png" });
      await user.upload(fileInput, file);

      await waitFor(() => {
        const preview = within(getModalCard()).getByAltText("Logo preview");
        expect(preview).toHaveAttribute("src", fakeUrl);
      });
    });

    it("calls URL.createObjectURL with the uploaded file", async () => {
      const user = setup();
      await openNewModal(user);

      const createObjectURLSpy = vi.spyOn(URL, "createObjectURL");
      const fileInput = getModalCard().querySelector('input[type="file"]');
      const file = new File(["img"], "logo.svg", { type: "image/svg+xml" });
      await user.upload(fileInput, file);

      await waitFor(() =>
        expect(createObjectURLSpy).toHaveBeenCalledWith(file)
      );
    });

    it("changes upload button label to 'Change' after file selected", async () => {
      const user = setup();
      await openNewModal(user);

      const fileInput = getModalCard().querySelector('input[type="file"]');
      const file = new File(["img"], "logo.png", { type: "image/png" });
      await user.upload(fileInput, file);

      await waitFor(() =>
        expect(
          within(getModalCard()).getByRole("button", { name: /change/i })
        ).toBeInTheDocument()
      );
    });

    it("shows 'Remove' button after file is selected", async () => {
      const user = setup();
      await openNewModal(user);

      const fileInput = getModalCard().querySelector('input[type="file"]');
      await user.upload(fileInput, new File(["img"], "logo.png", { type: "image/png" }));

      await waitFor(() =>
        expect(
          within(getModalCard()).getByRole("button", { name: /remove/i })
        ).toBeInTheDocument()
      );
    });

    it("does nothing when file input fires with no file selected", async () => {
      const user = setup();
      await openNewModal(user);

      // Fire change event with empty files list
      const fileInput = getModalCard().querySelector('input[type="file"]');
      fireEvent.change(fileInput, { target: { files: [] } });

      // Preview should not appear
      expect(
        within(getModalCard()).queryByAltText("Logo preview")
      ).not.toBeInTheDocument();
    });
  });

  // ── 15. Logo remove ───────────────────────────────────────────────────────
  describe("Logo remove button", () => {
    it("clears preview and restores placeholder after Remove clicked", async () => {
      const user = setup();
      render(<AdminBrands />);

      await waitFor(() =>
        expect(screen.getByRole("button", { name: /add brand/i })).toBeInTheDocument()
      );
      await user.click(screen.getByRole("button", { name: /add brand/i }));
      await waitFor(() =>
        expect(screen.getByRole("heading", { name: /add brand/i })).toBeInTheDocument()
      );

      // Upload a file to show preview
      const fileInput = getModalCard().querySelector('input[type="file"]');
      await user.upload(
        fileInput,
        new File(["img"], "logo.png", { type: "image/png" })
      );
      await waitFor(() =>
        expect(within(getModalCard()).getByAltText("Logo preview")).toBeInTheDocument()
      );

      // Click Remove
      await user.click(
        within(getModalCard()).getByRole("button", { name: /remove/i })
      );

      await waitFor(() => {
        // Preview gone, placeholder restored
        expect(
          within(getModalCard()).queryByAltText("Logo preview")
        ).not.toBeInTheDocument();
        expect(
          within(getModalCard()).getByRole("button", { name: /upload logo/i })
        ).toBeInTheDocument();
      });
    });

    it("does not append logo to FormData after Remove clicked then submit", async () => {
      adminAPI.createBrand.mockResolvedValue({ data: {} });
      const appendSpy = vi.spyOn(FormData.prototype, "append");

      const user = setup();
      render(<AdminBrands />);
      await waitFor(() =>
        expect(screen.getByRole("button", { name: /add brand/i })).toBeInTheDocument()
      );
      await user.click(screen.getByRole("button", { name: /add brand/i }));
      await waitFor(() =>
        expect(screen.getByRole("heading", { name: /add brand/i })).toBeInTheDocument()
      );

      // Upload then remove
      const fileInput = getModalCard().querySelector('input[type="file"]');
      await user.upload(
        fileInput,
        new File(["img"], "logo.png", { type: "image/png" })
      );
      await waitFor(() =>
        expect(within(getModalCard()).getByAltText("Logo preview")).toBeInTheDocument()
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /remove/i })
      );
      await waitFor(() =>
        expect(
          within(getModalCard()).queryByAltText("Logo preview")
        ).not.toBeInTheDocument()
      );

      // Type name and submit
      await user.type(
        within(getModalCard()).getByPlaceholderText("e.g. Nike"),
        "BrandX"
      );
      await user.click(
        within(getModalCard()).getByRole("button", { name: /^add brand$/i })
      );

      await waitFor(() => expect(adminAPI.createBrand).toHaveBeenCalled());

      const logoCalls = appendSpy.mock.calls.filter(([key]) => key === "logo");
      expect(logoCalls).toHaveLength(0);
    });
  });

  // ── 16. Snapshot ─────────────────────────────────────────────────────────
  describe("Snapshot", () => {
    it("matches stable snapshot after data loads", async () => {
      const { asFragment } = render(<AdminBrands />);
      await waitFor(() => screen.getByText("Brand 1"));
      expect(asFragment()).toMatchSnapshot();
    });
  });
});
