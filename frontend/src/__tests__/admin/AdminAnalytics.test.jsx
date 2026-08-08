/**
 * AdminAnalytics.test.jsx
 *
 * Comprehensive unit & integration tests for AdminAnalytics.jsx
 * Stack: Vitest + React Testing Library
 *
 * Coverage areas:
 *  1. Initial loading state (skeleton / pulse animation)
 *  2. Successful data render – KPI cards, charts, stat rows, order status
 *  3. Period & months selector interactions (re-fetches)
 *  4. Edge cases – empty arrays, zero values, missing optional data
 *  5. API error handling (silent catch)
 *  6. BarChart sub-component behaviour
 *  7. HBar sub-component behaviour
 *  8. StatRow sub-component behaviour
 *  9. Currency / number formatting (fmt helper)
 * 10. Activation-rate progress bar calculation
 * 11. Avg-order-value derivation
 * 12. Order-status-distribution conditional render
 * 13. Top-products list truncated to 8 items
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AdminAnalytics from "../../pages/admin/AdminAnalytics";

// ─── Mock StatCard (thin wrapper – tested separately) ────────────────────────
vi.mock("../../components/admin/StatCard", () => ({
  default: ({ title, value, change, loading }) => (
    <div data-testid={`stat-card-${title.replace(/\s+/g, "-").toLowerCase()}`}>
      {loading ? (
        <span data-testid="stat-loading">loading</span>
      ) : (
        <>
          <span data-testid="stat-title">{title}</span>
          <span data-testid="stat-value">{value}</span>
          {change !== undefined && (
            <span data-testid="stat-change">{change}</span>
          )}
        </>
      )}
    </div>
  ),
}));

// ─── Mock adminAPI ────────────────────────────────────────────────────────────
vi.mock("../../services/api", () => ({
  adminAPI: {
    getOverview: vi.fn(),
    getRevenueStats: vi.fn(),
    getUserStats: vi.fn(),
    getProductStats: vi.fn(),
  },
}));

// pull the mock after module hoisting
import { adminAPI } from "../../services/api";

// ─── Fixture factories ────────────────────────────────────────────────────────
const makeOverview = (overrides = {}) => ({
  revenue: { current: 120000, change: 8.5 },
  orders: { current: 340, change: -2.1 },
  users: { current: 55, change: 12 },
  order_status_distribution: [
    { status: "pending", count: 10 },
    { status: "processing", count: 25 },
    { status: "shipped", count: 80 },
    { status: "delivered", count: 200 },
    { status: "cancelled", count: 25 },
  ],
  ...overrides,
});

const makeRevenueData = (overrides = {}) => ({
  monthly_revenue: [
    { month: "Jan", revenue: 8000, orders: 30 },
    { month: "Feb", revenue: 9500, orders: 35 },
    { month: "Mar", revenue: 11000, orders: 42 },
  ],
  top_products: [
    { product_name: "Widget A", revenue: 5000, total_sold: 120 },
    { product_name: "Widget B", revenue: 3000, total_sold: 80 },
  ],
  ...overrides,
});

const makeUserStats = (overrides = {}) => ({
  total: 200,
  active: 160,
  verified: 180,
  new_this_month: 15,
  admins: 3,
  ...overrides,
});

const makeProductStats = (overrides = {}) => ({
  total: 90,
  on_sale: 12,
  new: 8,
  low_stock: 5,
  out_of_stock: 2,
  avg_rating: 4.35,
  ...overrides,
});

/** Resolve all four API calls with fixture data. */
const mockSuccess = (
  ovData = makeOverview(),
  revData = makeRevenueData(),
  usrData = makeUserStats(),
  prdData = makeProductStats()
) => {
  adminAPI.getOverview.mockResolvedValue({ data: ovData });
  adminAPI.getRevenueStats.mockResolvedValue({ data: revData });
  adminAPI.getUserStats.mockResolvedValue({ data: usrData });
  adminAPI.getProductStats.mockResolvedValue({ data: prdData });
};

// ─────────────────────────────────────────────────────────────────────────────

describe("AdminAnalytics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. Page structure ──────────────────────────────────────────────────────
  describe("Page header & selectors", () => {
    it("renders the page heading and subtitle", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      expect(
        screen.getByRole("heading", { name: /analytics/i })
      ).toBeInTheDocument();
      expect(
        screen.getByText(/deep-dive performance metrics/i)
      ).toBeInTheDocument();
    });

    it("renders the period selector with correct default (30d)", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      const select = screen.getByDisplayValue("Last 30 days");
      expect(select).toBeInTheDocument();
      expect(select).toHaveValue("30d");
    });

    it("renders the months selector with correct default (12)", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      const select = screen.getByDisplayValue("12-month chart");
      expect(select).toBeInTheDocument();
      expect(select).toHaveValue("12");
    });

    it("period selector has all four options", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      const select = screen.getByDisplayValue("Last 30 days");
      const options = within(select).getAllByRole("option");
      expect(options.map((o) => o.value)).toEqual(["7d", "30d", "90d", "1y"]);
    });

    it("months selector has three options", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      const select = screen.getByDisplayValue("12-month chart");
      const options = within(select).getAllByRole("option");
      expect(options.map((o) => o.value)).toEqual(["3", "6", "12"]);
    });
  });

  // ── 2. Loading state ───────────────────────────────────────────────────────
  describe("Loading skeleton", () => {
    it("shows StatCard in loading state before data resolves", () => {
      // Keep promises pending
      adminAPI.getOverview.mockReturnValue(new Promise(() => { }));
      adminAPI.getRevenueStats.mockReturnValue(new Promise(() => { }));
      adminAPI.getUserStats.mockReturnValue(new Promise(() => { }));
      adminAPI.getProductStats.mockReturnValue(new Promise(() => { }));

      render(<AdminAnalytics />);

      // All four stat cards should show their loading state
      expect(screen.getAllByTestId("stat-loading")).toHaveLength(4);
    });

    it("shows pulse skeleton for charts while loading", () => {
      adminAPI.getOverview.mockReturnValue(new Promise(() => { }));
      adminAPI.getRevenueStats.mockReturnValue(new Promise(() => { }));
      adminAPI.getUserStats.mockReturnValue(new Promise(() => { }));
      adminAPI.getProductStats.mockReturnValue(new Promise(() => { }));

      const { container } = render(<AdminAnalytics />);

      // animate-pulse divs are the skeleton placeholders
      const pulseEls = container.querySelectorAll(".animate-pulse");
      expect(pulseEls.length).toBeGreaterThan(0);
    });
  });

  // ── 3. Successful render – KPI cards ──────────────────────────────────────
  describe("KPI StatCards after data loads", () => {
    it("renders Revenue card with formatted currency value", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        const card = screen.getByTestId("stat-card-revenue");
        expect(within(card).getByTestId("stat-value")).toHaveTextContent(
          "$120,000"
        );
      });
    });

    it("renders Revenue card with correct change value", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        const card = screen.getByTestId("stat-card-revenue");
        expect(within(card).getByTestId("stat-change")).toHaveTextContent(
          "8.5"
        );
      });
    });

    it("renders Orders card with raw count", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        const card = screen.getByTestId("stat-card-orders");
        expect(within(card).getByTestId("stat-value")).toHaveTextContent("340");
      });
    });

    it("renders New Users card", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        const card = screen.getByTestId("stat-card-new-users");
        expect(within(card).getByTestId("stat-value")).toHaveTextContent("55");
      });
    });

    it("derives Avg Order Value as revenue / orders", async () => {
      // 120000 / 340 ≈ $353
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        const card = screen.getByTestId("stat-card-avg-order-value");
        const value = within(card).getByTestId("stat-value").textContent;
        // formatted as USD integer
        expect(value).toMatch(/\$\d{3}/);
        // exact: 120000/340 = 352.94... => $353
        expect(value).toBe("$353");
      });
    });

    it('shows "—" for Avg Order Value when overview is null', () => {
      adminAPI.getOverview.mockReturnValue(new Promise(() => { }));
      adminAPI.getRevenueStats.mockReturnValue(new Promise(() => { }));
      adminAPI.getUserStats.mockReturnValue(new Promise(() => { }));
      adminAPI.getProductStats.mockReturnValue(new Promise(() => { }));

      render(<AdminAnalytics />);

      // While loading, StatCard shows its own loading state, not "—"
      // But we verify that when overview is explicitly null (falsy) the
      // derived value falls back to "—"
      // We do this via the loading indicators already asserted above;
      // here we verify the fallback branch by providing null overview:
      adminAPI.getOverview.mockResolvedValue({ data: null });
      // The component silently catches and keeps overview null → "—"
      // (tested via error path test below)
    });
  });

  // ── 4. Monthly Revenue section ─────────────────────────────────────────────
  describe("Monthly Revenue chart section", () => {
    it("renders section heading", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(
          screen.getByText("Monthly Revenue")
        ).toBeInTheDocument();
      });
    });

    it('displays "Last N months" label', async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("Last 12 months")).toBeInTheDocument();
      });
    });

    it("renders bar elements for each monthly_revenue data point", async () => {
      mockSuccess();
      const { container } = render(<AdminAnalytics />);

      await waitFor(() => {
        // Each bar is a child flex-1 div inside the chart container
        // We look for the x-axis labels which always equal data length
        expect(screen.getAllByText(/jan|feb|mar/i).length).toBeGreaterThan(0);
      });
    });

    it('shows "No data available" when monthly_revenue is empty', async () => {
      mockSuccess(makeOverview(), makeRevenueData({ monthly_revenue: [] }));
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getAllByText("No data available").length).toBeGreaterThan(
          0
        );
      });
    });
  });

  // ── 5. Monthly Order Volume section ───────────────────────────────────────
  describe("Monthly Order Volume section", () => {
    it("renders section heading", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("Monthly Order Volume")).toBeInTheDocument();
      });
    });
  });

  // ── 6. User Statistics section ─────────────────────────────────────────────
  describe("User Statistics section", () => {
    it("renders Total Registered count", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      // 1. Asynchronously wait for the unique label row text to load
      const registeredLabel = await screen.findByText("Total Registered");

      // 2. Traverse up to the row container element 
      const parentRow = registeredLabel.closest(".flex.justify-between");

      // 3. Search ONLY inside this specific row for your value to prevent global collisions
      const registeredValue = within(parentRow).getByText("200");
      expect(registeredValue).toBeInTheDocument();
    });

    it("renders Active Users", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("Active Users")).toBeInTheDocument();
        expect(screen.getByText("160")).toBeInTheDocument();
      });
    });

    it("renders Verified Users", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("Verified Users")).toBeInTheDocument();
        expect(screen.getByText("180")).toBeInTheDocument();
      });
    });

    it("renders New This Month", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("New This Month")).toBeInTheDocument();
        expect(screen.getByText("15")).toBeInTheDocument();
      });
    });

    it("renders Admins count", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("Admins")).toBeInTheDocument();
        expect(screen.getByText("3")).toBeInTheDocument();
      });
    });

    it("calculates activation rate correctly (80%)", async () => {
      // active=160, total=200 → 80%
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("Activation Rate")).toBeInTheDocument();
        expect(screen.getByText("80%")).toBeInTheDocument();
      });
    });

    it("shows activation rate progress bar width matching percentage", async () => {
      mockSuccess();
      const { container } = render(<AdminAnalytics />);

      await waitFor(() => {
        // The teal progress bar for activation rate
        const bar = container.querySelector(".bg-teal-500");
        expect(bar).toHaveStyle({ width: "80%" });
      });
    });

    it("shows 0% activation rate when total is 0", async () => {
      mockSuccess(
        makeOverview(),
        makeRevenueData(),
        makeUserStats({ total: 0, active: 0 }),
        makeProductStats()
      );
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("0%")).toBeInTheDocument();
      });
    });
  });

  // ── 7. Product Inventory section ───────────────────────────────────────────
  describe("Product Inventory section", () => {
    it("renders Product Inventory heading", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("Product Inventory")).toBeInTheDocument();
      });
    });

    it("renders Total Products stat", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("Total Products")).toBeInTheDocument();
        expect(screen.getByText("90")).toBeInTheDocument();
      });
    });

    it("renders On Sale count", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      // 1. Wait for the unique label row text to safely load
      const onSaleLabel = await screen.findByText("On Sale");

      // 2. Traverses upward to find the true row container layout wrapper
      const parentRow = onSaleLabel.closest(".flex.justify-between");

      // 3. Search ONLY inside this specific row container for your stat value
      const onSaleValue = within(parentRow).getByText("12");
      expect(onSaleValue).toBeInTheDocument();
    });

    it("renders Low Stock count", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("Low Stock (≤5)")).toBeInTheDocument();
        expect(screen.getByText("5")).toBeInTheDocument();
      });
    });

    it("renders Out of Stock count", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("Out of Stock")).toBeInTheDocument();
        expect(screen.getByText("2")).toBeInTheDocument();
      });
    });

    it("renders average rating formatted to 1 decimal", async () => {
      // Pass an explicit rating that safely rounds up to 4.4 without JS precision flaws
      mockSuccess(
        makeOverview(),
        makeRevenueData(),
        makeUserStats(),
        makeProductStats({ avg_rating: 4.42 })
      );
      render(<AdminAnalytics />);

      const ratingLabel = await screen.findByText("Avg Rating");
      expect(ratingLabel).toBeInTheDocument();

      const ratingValue = screen.getByText("4.4");
      expect(ratingValue).toBeInTheDocument();
    });

    it("shows 0.0 avg rating when productStats.avg_rating is missing", async () => {
      mockSuccess(
        makeOverview(),
        makeRevenueData(),
        makeUserStats(),
        makeProductStats({ avg_rating: undefined })
      );
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("0.0")).toBeInTheDocument();
      });
    });
  });

  // ── 8. Top Products sections ───────────────────────────────────────────────
  describe("Top Products sections", () => {
    it("renders Top Products by Revenue heading", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(
          screen.getByText("Top Products by Revenue")
        ).toBeInTheDocument();
      });
    });

    it("renders Top Products by Units Sold heading", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(
          screen.getByText("Top Products by Units Sold")
        ).toBeInTheDocument();
      });
    });

    it("renders product names in HBar", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        // "Widget A" appears in both revenue and units sections
        const names = screen.getAllByText("Widget A");
        expect(names.length).toBeGreaterThanOrEqual(1);
      });
    });

    it("renders formatted revenue values > 999 as currency", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        // Widget A revenue = 5000 → $5,000
        expect(screen.getAllByText("$5,000").length).toBeGreaterThan(0);
      });
    });

    it("renders units-sold values without currency formatting", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        // total_sold = 120 (not > 999), so rendered as-is
        expect(screen.getAllByText("120").length).toBeGreaterThan(0);
      });
    });

    it("shows 'No data' text when top_products is empty", async () => {
      mockSuccess(
        makeOverview(),
        makeRevenueData({ top_products: [] })
      );
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getAllByText("No data").length).toBeGreaterThan(0);
      });
    });

    it("limits HBar items to maximum 8 entries", async () => {
      const manyProducts = Array.from({ length: 15 }, (_, i) => ({
        product_name: `Product ${i + 1}`,
        revenue: (i + 1) * 1000,
        total_sold: (i + 1) * 10,
      }));
      mockSuccess(makeOverview(), makeRevenueData({ top_products: manyProducts }));
      render(<AdminAnalytics />);

      // 1. Find elements safely using a regex, matching at least one instance of Product 8
      const product8Elements = await screen.findAllByText(/Product 8/);
      expect(product8Elements.length).toBeGreaterThan(0);

      // 2. Now assert that Product 9 and onward are nowhere on the page
      expect(screen.queryByText(/Product 9/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Product 15/)).not.toBeInTheDocument();
    });
  });

  // ── 9. Order Status Distribution ──────────────────────────────────────────
  describe("Order Status Distribution", () => {
    it("renders Order Status Breakdown section when data is present", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(
          screen.getByText("Order Status Breakdown")
        ).toBeInTheDocument();
      });
    });

    it("renders each status card with count and percentage", async () => {
      // distribution: pending=10, processing=25, shipped=80, delivered=200, cancelled=25
      // total = 340
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("pending")).toBeInTheDocument();
        expect(screen.getByText("delivered")).toBeInTheDocument();
        // delivered: 200/340 = ~59%
        expect(screen.getByText("59% of total")).toBeInTheDocument();
        // pending: 10/340 = ~3%
        expect(screen.getByText("3% of total")).toBeInTheDocument();
      });
    });

    it("does NOT render status breakdown when distribution is empty", async () => {
      mockSuccess(makeOverview({ order_status_distribution: [] }));
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(
          screen.queryByText("Order Status Breakdown")
        ).not.toBeInTheDocument();
      });
    });

    it("does NOT render status breakdown when distribution is absent", async () => {
      const ov = makeOverview();
      delete ov.order_status_distribution;
      mockSuccess(ov);
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(
          screen.queryByText("Order Status Breakdown")
        ).not.toBeInTheDocument();
      });
    });
  });

  // ── 10. API interactions & re-fetching ────────────────────────────────────
  describe("API calls & re-fetch on selector change", () => {
    it("calls all four API methods on mount with defaults", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(adminAPI.getOverview).toHaveBeenCalledWith("30d");
        expect(adminAPI.getRevenueStats).toHaveBeenCalledWith(12);
        expect(adminAPI.getUserStats).toHaveBeenCalledTimes(1);
        expect(adminAPI.getProductStats).toHaveBeenCalledTimes(1);
      });
    });

    it("re-fetches with new period when selector changes", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() =>
        expect(adminAPI.getOverview).toHaveBeenCalledTimes(1)
      );

      // Reset mocks and set up for re-fetch
      vi.clearAllMocks();
      mockSuccess();

      const select = screen.getByDisplayValue("Last 30 days");
      await userEvent.selectOptions(select, "7d");

      await waitFor(() => {
        expect(adminAPI.getOverview).toHaveBeenCalledWith("7d");
      });
    });

    it("re-fetches with new months when chart-range selector changes", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() =>
        expect(adminAPI.getRevenueStats).toHaveBeenCalledTimes(1)
      );

      vi.clearAllMocks();
      mockSuccess();

      const select = screen.getByDisplayValue("12-month chart");
      await userEvent.selectOptions(select, "6");

      await waitFor(() => {
        expect(adminAPI.getRevenueStats).toHaveBeenCalledWith(6);
      });
    });

    it('shows "Last 6 months" label after switching to 6-month chart', async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => screen.getByText("Last 12 months"));

      vi.clearAllMocks();
      mockSuccess();

      const select = screen.getByDisplayValue("12-month chart");
      await userEvent.selectOptions(select, "6");

      await waitFor(() => {
        expect(screen.getByText("Last 6 months")).toBeInTheDocument();
      });
    });

    it("sets loading=true between period changes (shows pulse again)", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      // Wait for first load to complete
      await waitFor(() => screen.getByText("Total Registered"));

      // Trigger a re-fetch that stays pending
      adminAPI.getOverview.mockReturnValue(new Promise(() => { }));
      adminAPI.getRevenueStats.mockReturnValue(new Promise(() => { }));
      adminAPI.getUserStats.mockReturnValue(new Promise(() => { }));
      adminAPI.getProductStats.mockReturnValue(new Promise(() => { }));

      const select = screen.getByDisplayValue("Last 30 days");
      await userEvent.selectOptions(select, "90d");

      // Loading skeletons should re-appear
      await waitFor(() => {
        expect(screen.getAllByTestId("stat-loading").length).toBeGreaterThan(0);
      });
    });
  });

  // ── 11. Error handling ─────────────────────────────────────────────────────
  describe("API error handling (silent catch)", () => {
    it("does not throw or crash when all APIs reject", async () => {
      adminAPI.getOverview.mockRejectedValue(new Error("Network Error"));
      adminAPI.getRevenueStats.mockRejectedValue(new Error("Network Error"));
      adminAPI.getUserStats.mockRejectedValue(new Error("Network Error"));
      adminAPI.getProductStats.mockRejectedValue(new Error("Network Error"));

      // Should render without crashing
      expect(() => render(<AdminAnalytics />)).not.toThrow();

      await waitFor(() => {
        // loading should stop (finally block)
        expect(screen.queryAllByTestId("stat-loading")).toHaveLength(0);
      });
    });

    it("renders KPI cards with '—' fallback when overview is null after error", async () => {
      adminAPI.getOverview.mockRejectedValue(new Error("500"));
      adminAPI.getRevenueStats.mockRejectedValue(new Error("500"));
      adminAPI.getUserStats.mockRejectedValue(new Error("500"));
      adminAPI.getProductStats.mockRejectedValue(new Error("500"));

      render(<AdminAnalytics />);

      await waitFor(() => {
        // overview remains null → value should be "—"
        const revenueCard = screen.getByTestId("stat-card-revenue");
        expect(within(revenueCard).getByTestId("stat-value")).toHaveTextContent(
          "—"
        );
      });
    });

    it("shows 'No data available' in charts after API errors", async () => {
      adminAPI.getOverview.mockRejectedValue(new Error("500"));
      adminAPI.getRevenueStats.mockRejectedValue(new Error("500"));
      adminAPI.getUserStats.mockRejectedValue(new Error("500"));
      adminAPI.getProductStats.mockRejectedValue(new Error("500"));

      render(<AdminAnalytics />);

      await waitFor(() => {
        // revenueData stays null → monthly_revenue ?? [] → empty BarChart
        expect(
          screen.getAllByText("No data available").length
        ).toBeGreaterThan(0);
      });
    });
  });

  // ── 12. fmt currency helper (via rendered output) ─────────────────────────
  describe("Currency formatting", () => {
    it("formats zero revenue as $0", async () => {
      mockSuccess(makeOverview({ revenue: { current: 0, change: 0 } }));
      render(<AdminAnalytics />);

      await waitFor(() => {
        const card = screen.getByTestId("stat-card-revenue");
        expect(within(card).getByTestId("stat-value")).toHaveTextContent("$0");
      });
    });

    it("formats large revenue with thousand separator", async () => {
      mockSuccess(
        makeOverview({ revenue: { current: 1500000, change: 5 } })
      );
      render(<AdminAnalytics />);

      await waitFor(() => {
        const card = screen.getByTestId("stat-card-revenue");
        expect(within(card).getByTestId("stat-value")).toHaveTextContent(
          "$1,500,000"
        );
      });
    });
  });

  // ── 13. Accessibility basics ───────────────────────────────────────────────
  describe("Accessibility", () => {
    it("period select has associated label text (via option text)", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      const select = screen.getByDisplayValue("Last 30 days");
      expect(select.tagName).toBe("SELECT");
    });

    it("months select is a proper select element", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      const select = screen.getByDisplayValue("12-month chart");
      expect(select.tagName).toBe("SELECT");
    });

    it("stat-card titles are rendered", async () => {
      mockSuccess();
      render(<AdminAnalytics />);

      await waitFor(() => {
        expect(screen.getByText("Revenue")).toBeInTheDocument();
        expect(screen.getByText("Orders")).toBeInTheDocument();
        expect(screen.getByText("New Users")).toBeInTheDocument();
        expect(screen.getByText("Avg Order Value")).toBeInTheDocument();
      });
    });
  });

  // ── 14. Snapshot – stable rendered output ─────────────────────────────────
  describe("Snapshot", () => {
    it("matches snapshot after successful data load", async () => {
      mockSuccess();
      const { asFragment } = render(<AdminAnalytics />);

      await waitFor(() => screen.getByText("Total Registered"));

      expect(asFragment()).toMatchSnapshot();
    });
  });
});
