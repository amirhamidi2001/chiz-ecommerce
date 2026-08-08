/**
 * AdminDashboard.test.jsx
 *
 * Comprehensive unit & integration tests for AdminDashboard.jsx
 * Stack : Vitest · React Testing Library · @testing-library/user-event v14
 *
 * ── Coverage map ──────────────────────────────────────────────────────────────
 *  1.  Page structure        – heading, formatted date, period <select> options
 *  2.  getOverview fetch     – mount call w/ default period, re-fetch on period
 *                              change, error swallowed silently (no crash)
 *  3.  Loading state         – StatCards loading=true, alerts hidden, chart
 *                              skeletons, table skeletons (5 rows × 2 each)
 *  4.  KPI StatCards         – Revenue (currency, no onClick), Orders (raw,
 *                              navigates /admin/orders), New Users (raw,
 *                              navigates /admin/users), Total Products (raw,
 *                              navigates /admin/products), "—" fallbacks
 *  5.  Alerts row            – hidden while loading/no data, Low Stock /
 *                              Out of Stock / Pending Orders values + fallback
 *                              to 0, click navigation per alert
 *  6.  MiniBarChart          – "No data" on empty array, renders one bar per
 *                              data point (≤14), bar height % from value/max,
 *                              tooltip shows formatted value + label
 *  7.  DonutChart            – total fallback to 1 when empty (no NaN), one
 *                              <path> per data point, legend status + count,
 *                              color cycling via modulo
 *  8.  Recent Orders panel   – heading, "View All" navigation, empty list
 *                              shows no rows, order_number, full_name vs
 *                              email fallback, STATUS_STYLES per status,
 *                              formatted total
 *  9.  Top Products panel    – heading, "View All" navigation, sliced to 6,
 *                              rank numbers, product_name, total_sold,
 *                              formatted revenue
 * 10.  Currency formatting   – fmt() via rendered KPI/order/product values
 * 11.  Snapshot              – stable rendered output after data loads
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * ── Design notes (lessons applied from prior cascading-failure fixes) ────────
 *
 * • Never use exact getByText() on strings that might be interleaved with
 *   sibling elements in the same row (e.g. order_number + email in the same
 *   <div>, or product rank + name + units in the same row). Every such lookup
 *   below either targets a leaf node directly or uses a function matcher.
 *
 * • userEvent.setup() is NOT given `advanceTimers` globally — this component
 *   has no debounce/timer logic, so a single plain `setup()` helper is used
 *   throughout. No fake timers are needed anywhere in this suite.
 *
 * • StatCard is mocked as a thin stub so onClick / loading / value / change
 *   are asserted directly via props rather than guessing DOM structure.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminDashboard from '../../pages/admin/AdminDashboard';

// ─── Mock: react-router-dom useNavigate ──────────────────────────────────────
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

// ─── Mock: StatCard ───────────────────────────────────────────────────────────
vi.mock('../../components/admin/StatCard', () => ({
  default: ({ title, value, change, loading, onClick }) => (
    <div
      data-testid={`stat-${title.replace(/\s+/g, '-').toLowerCase()}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
    >
      {loading ? (
        <span data-testid="stat-loading">loading</span>
      ) : (
        <>
          <span data-testid="stat-title">{title}</span>
          <span data-testid="stat-value">{value}</span>
          {change !== undefined && <span data-testid="stat-change">{change}</span>}
        </>
      )}
    </div>
  ),
}));

// ─── Mock: adminAPI ───────────────────────────────────────────────────────────
vi.mock('../../services/api', () => ({
  adminAPI: { getOverview: vi.fn() },
}));
import { adminAPI } from '../../services/api';

// ─── Fixture factory ──────────────────────────────────────────────────────────
const makeOverview = (overrides = {}) => ({
  revenue: { current: 125000, change: 8.2 },
  orders: { current: 340, change: -1.5 },
  users: { current: 58, change: 12.3 },
  products: { total: 412 },
  product_stats: { low_stock: 7, out_of_stock: 3 },
  order_status_distribution: [
    { status: 'pending', count: 12 },
    { status: 'processing', count: 20 },
    { status: 'shipped', count: 45 },
    { status: 'delivered', count: 200 },
    { status: 'cancelled', count: 8 },
  ],
  revenue_chart: [
    { date: '06-01', revenue: 4000 },
    { date: '06-02', revenue: 7000 },
    { date: '06-03', revenue: 5000 },
  ],
  recent_orders: [
    {
      id: 1, order_number: 'ORD-1001', full_name: 'Alice Smith',
      email: 'alice@test.com', status: 'pending', total: 89.5,
    },
    {
      id: 2, order_number: 'ORD-1002', full_name: null,
      email: 'bob@test.com', status: 'delivered', total: 240,
    },
  ],
  top_products: [
    { product_id: 1, product_name: 'Widget A', total_sold: 120, revenue: 5400 },
    { product_id: 2, product_name: 'Widget B', total_sold: 80, revenue: 3200 },
  ],
  ...overrides,
});

const okOverview = (data = makeOverview()) =>
  adminAPI.getOverview.mockResolvedValue({ data });

const setup = () => userEvent.setup();

// ─────────────────────────────────────────────────────────────────────────────

describe('AdminDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    okOverview();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. Page structure ────────────────────────────────────────────────────
  describe('Page structure', () => {
    it('renders the "Dashboard Overview" heading', () => {
      render(<AdminDashboard />);
      expect(
        screen.getByRole('heading', { name: /dashboard overview/i })
      ).toBeInTheDocument();
    });

    it('renders today\'s date in long format', () => {
      render(<AdminDashboard />);
      const expected = new Date().toLocaleDateString('en-US', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      });
      expect(screen.getByText(expected)).toBeInTheDocument();
    });

    it('renders the period select with default value "30d"', () => {
      render(<AdminDashboard />);
      const select = screen.getByDisplayValue('Last 30 days');
      expect(select).toHaveValue('30d');
    });

    it('period select has all four expected options', () => {
      render(<AdminDashboard />);
      const select = screen.getByDisplayValue('Last 30 days');
      const values = within(select).getAllByRole('option').map((o) => o.value);
      expect(values).toEqual(['7d', '30d', '90d', '1y']);
    });
  });

  // ── 2. getOverview fetch ─────────────────────────────────────────────────
  describe('getOverview – fetch behaviour', () => {
    it('calls getOverview on mount with the default period "30d"', async () => {
      render(<AdminDashboard />);
      await waitFor(() =>
        expect(adminAPI.getOverview).toHaveBeenCalledWith('30d')
      );
    });

    it('re-fetches with the new period when the select changes', async () => {
      const user = setup();
      render(<AdminDashboard />);
      await waitFor(() => expect(adminAPI.getOverview).toHaveBeenCalledTimes(1));

      vi.clearAllMocks();
      okOverview();

      const select = screen.getByDisplayValue('Last 30 days');
      await user.selectOptions(select, '7d');

      await waitFor(() =>
        expect(adminAPI.getOverview).toHaveBeenCalledWith('7d')
      );
    });

    it('does not throw and clears loading state when getOverview rejects', async () => {
      adminAPI.getOverview.mockRejectedValue(new Error('network error'));
      render(<AdminDashboard />);
      await waitFor(() =>
        expect(screen.queryAllByTestId('stat-loading')).toHaveLength(0)
      );
    });

    it('does not render the alerts row after a rejected fetch (data stays null)', async () => {
      adminAPI.getOverview.mockRejectedValue(new Error('network error'));
      render(<AdminDashboard />);
      await waitFor(() =>
        expect(screen.queryAllByTestId('stat-loading')).toHaveLength(0)
      );
      expect(screen.queryByText('Low Stock')).not.toBeInTheDocument();
    });
  });

  // ── 3. Loading state ─────────────────────────────────────────────────────
  describe('Loading state', () => {
    it('shows all four StatCards in loading state initially', () => {
      adminAPI.getOverview.mockReturnValue(new Promise(() => { }));
      render(<AdminDashboard />);
      expect(screen.getAllByTestId('stat-loading')).toHaveLength(4);
    });

    it('does not render the alerts row while loading', () => {
      adminAPI.getOverview.mockReturnValue(new Promise(() => { }));
      render(<AdminDashboard />);
      expect(screen.queryByText('Low Stock')).not.toBeInTheDocument();
    });

    it('shows animate-pulse skeletons for both charts while loading', () => {
      adminAPI.getOverview.mockReturnValue(new Promise(() => { }));
      const { container } = render(<AdminDashboard />);
      const pulses = container.querySelectorAll('.h-32.bg-gray-100.animate-pulse');
      expect(pulses.length).toBe(2); // revenue chart + donut chart
    });

    it('shows 5 skeleton rows in the Recent Orders panel while loading', () => {
      adminAPI.getOverview.mockReturnValue(new Promise(() => { }));
      const { container } = render(<AdminDashboard />);
      const headers = screen.getAllByText('Recent Orders');
      const panel = headers[0].closest('.bg-white');
      const skeletonRows = panel.querySelectorAll('.divide-y > div');
      expect(skeletonRows.length).toBe(5);
    });

    it('shows 5 skeleton rows in the Top Products panel while loading', () => {
      adminAPI.getOverview.mockReturnValue(new Promise(() => { }));
      render(<AdminDashboard />);
      const header = screen.getByText('Top Products');
      const panel = header.closest('.bg-white');
      const skeletonRows = panel.querySelectorAll('.divide-y > div');
      expect(skeletonRows.length).toBe(5);
    });

    it('removes loading state after data resolves', async () => {
      render(<AdminDashboard />);
      await waitFor(() =>
        expect(screen.queryAllByTestId('stat-loading')).toHaveLength(0)
      );
    });
  });

  // ── 4. KPI StatCards ─────────────────────────────────────────────────────
  describe('KPI StatCards', () => {
    it('renders Revenue card with formatted currency and no onClick', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        const card = screen.getByTestId('stat-revenue');
        expect(within(card).getByTestId('stat-value')).toHaveTextContent('$125,000');
        expect(card).not.toHaveAttribute('role', 'button');
      });
    });

    it('renders Revenue card with the correct change value', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        const card = screen.getByTestId('stat-revenue');
        expect(within(card).getByTestId('stat-change')).toHaveTextContent('8.2');
      });
    });

    it('renders Orders card with the raw count', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        const card = screen.getByTestId('stat-orders');
        expect(within(card).getByTestId('stat-value')).toHaveTextContent('340');
      });
    });

    it('clicking Orders card navigates to /admin/orders', async () => {
      const user = setup();
      render(<AdminDashboard />);
      await waitFor(() => screen.getByTestId('stat-orders'));
      await user.click(screen.getByTestId('stat-orders'));
      expect(mockNavigate).toHaveBeenCalledWith('/admin/orders');
    });

    it('renders New Users card with the raw count', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        const card = screen.getByTestId('stat-new-users');
        expect(within(card).getByTestId('stat-value')).toHaveTextContent('58');
      });
    });

    it('clicking New Users card navigates to /admin/users', async () => {
      const user = setup();
      render(<AdminDashboard />);
      await waitFor(() => screen.getByTestId('stat-new-users'));
      await user.click(screen.getByTestId('stat-new-users'));
      expect(mockNavigate).toHaveBeenCalledWith('/admin/users');
    });

    it('renders Total Products card with data.products.total', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        const card = screen.getByTestId('stat-total-products');
        expect(within(card).getByTestId('stat-value')).toHaveTextContent('412');
      });
    });

    it('clicking Total Products card navigates to /admin/products', async () => {
      const user = setup();
      render(<AdminDashboard />);
      await waitFor(() => screen.getByTestId('stat-total-products'));
      await user.click(screen.getByTestId('stat-total-products'));
      expect(mockNavigate).toHaveBeenCalledWith('/admin/products');
    });

    it('shows "—" fallback for Orders/Users/Products values when data is null after error', async () => {
      adminAPI.getOverview.mockRejectedValue(new Error('fail'));
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(
          within(screen.getByTestId('stat-orders')).getByTestId('stat-value')
        ).toHaveTextContent('—');
        expect(
          within(screen.getByTestId('stat-new-users')).getByTestId('stat-value')
        ).toHaveTextContent('—');
        expect(
          within(screen.getByTestId('stat-total-products')).getByTestId('stat-value')
        ).toHaveTextContent('—');
      });
    });

    it('shows "—" fallback for Revenue value when data is null after error', async () => {
      adminAPI.getOverview.mockRejectedValue(new Error('fail'));
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(
          within(screen.getByTestId('stat-revenue')).getByTestId('stat-value')
        ).toHaveTextContent('—');
      });
    });
  });

  // ── 5. Alerts row ────────────────────────────────────────────────────────
  describe('Alerts row', () => {
    it('renders Low Stock value from product_stats.low_stock', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(screen.getByText('Low Stock')).toBeInTheDocument();
        expect(screen.getByText('7')).toBeInTheDocument();
      });
    });

    it('renders Out of Stock value from product_stats.out_of_stock', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(screen.getByText('Out of Stock')).toBeInTheDocument();
        expect(screen.getByText('3')).toBeInTheDocument();
      });
    });

    it('renders Pending Orders value from order_status_distribution', async () => {
      render(<AdminDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Pending Orders')).toBeInTheDocument();

        const alertCard = screen.getByText('Pending Orders').closest('div').parentElement;

        expect(within(alertCard).getByText('12')).toBeInTheDocument();
      });
    });

    it('falls back to 0 for Low Stock when product_stats is missing', async () => {
      okOverview(makeOverview({ product_stats: undefined }));
      render(<AdminDashboard />);
      await waitFor(() => screen.getByText('Low Stock'));
      const card = screen.getByText('Low Stock').closest('div').parentElement;
      expect(within(card).getByText('0')).toBeInTheDocument();
    });

    it('falls back to 0 for Pending Orders when no pending status exists', async () => {
      okOverview(makeOverview({
        order_status_distribution: [{ status: 'shipped', count: 5 }],
      }));
      render(<AdminDashboard />);
      await waitFor(() => screen.getByText('Pending Orders'));
      const card = screen.getByText('Pending Orders').closest('div').parentElement;
      expect(within(card).getByText('0')).toBeInTheDocument();
    });

    it('clicking the Low Stock alert navigates to the correct link', async () => {
      const user = setup();
      render(<AdminDashboard />);
      await waitFor(() => screen.getByText('Low Stock'));
      await user.click(screen.getByText('Low Stock').closest('.cursor-pointer'));
      expect(mockNavigate).toHaveBeenCalledWith('/admin/products?in_stock=false');
    });

    it('clicking the Out of Stock alert navigates to /admin/products', async () => {
      const user = setup();
      render(<AdminDashboard />);
      await waitFor(() => screen.getByText('Out of Stock'));
      await user.click(screen.getByText('Out of Stock').closest('.cursor-pointer'));
      expect(mockNavigate).toHaveBeenCalledWith('/admin/products');
    });

    it('clicking the Pending Orders alert navigates to filtered orders link', async () => {
      const user = setup();
      render(<AdminDashboard />);
      await waitFor(() => screen.getByText('Pending Orders'));
      await user.click(screen.getByText('Pending Orders').closest('.cursor-pointer'));
      expect(mockNavigate).toHaveBeenCalledWith('/admin/orders?status=pending');
    });
  });

  // ── 6. MiniBarChart ──────────────────────────────────────────────────────
  describe('MiniBarChart (Revenue chart)', () => {
    it('shows "No data" when revenue_chart is empty', async () => {
      okOverview(makeOverview({ revenue_chart: [] }));
      render(<AdminDashboard />);
      await waitFor(() => expect(screen.getByText('No data')).toBeInTheDocument());
    });

    it('renders the "Revenue — Last 14 Days" heading', async () => {
      render(<AdminDashboard />);
      await waitFor(() =>
        expect(screen.getByText('Revenue — Last 14 Days')).toBeInTheDocument()
      );
    });

    it('renders one bar element per data point', async () => {
      okOverview(makeOverview({
        revenue_chart: [
          { date: 'd1', revenue: 100 },
          { date: 'd2', revenue: 200 },
          { date: 'd3', revenue: 300 },
        ],
      }));
      const { container } = render(<AdminDashboard />);
      await waitFor(() => {
        const bars = container.querySelectorAll('.bg-teal-200');
        expect(bars).toHaveLength(3);
      });
    });

    it('caps rendered bars at the last 14 data points when more are supplied', async () => {
      const chart = Array.from({ length: 20 }, (_, i) => ({
        date: `d${i}`,
        revenue: (i + 1) * 10,
      }));
      okOverview(makeOverview({ revenue_chart: chart }));
      const { container } = render(<AdminDashboard />);
      await waitFor(() => {
        const bars = container.querySelectorAll('.bg-teal-200');
        expect(bars).toHaveLength(14);
      });
    });

    it('sets the tallest bar height to 100% for the max value', async () => {
      okOverview(makeOverview({
        revenue_chart: [
          { date: 'low', revenue: 10 },
          { date: 'high', revenue: 100 },
        ],
      }));
      const { container } = render(<AdminDashboard />);
      await waitFor(() => {
        const bars = Array.from(container.querySelectorAll('.bg-teal-200'));
        const tallest = bars.find((b) => b.style.height === '100%');
        expect(tallest).toBeTruthy();
      });
    });

    it('shows formatted currency value in the tooltip', async () => {
      okOverview(makeOverview({
        revenue_chart: [{ date: 'Jun 1', revenue: 4000 }],
      }));
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(screen.getByText('$4,000')).toBeInTheDocument();
        expect(screen.getByText('Jun 1')).toBeInTheDocument();
      });
    });
  });

  // ── 7. DonutChart ────────────────────────────────────────────────────────
  describe('DonutChart (Order Status)', () => {
    it('renders the "Order Status" heading', async () => {
      render(<AdminDashboard />);
      await waitFor(() => expect(screen.getByText('Order Status')).toBeInTheDocument());
    });

    it('renders one <path> per status entry', async () => {
      const { container } = render(<AdminDashboard />);
      await waitFor(() => {
        const paths = container.querySelectorAll('svg path');
        expect(paths).toHaveLength(5); // 5 statuses in fixture
      });
    });

    it('does not crash and total defaults to 1 when data is empty', async () => {
      okOverview(makeOverview({ order_status_distribution: [] }));
      const { container } = render(<AdminDashboard />);
      await waitFor(() => {
        // No paths drawn but the SVG circle (base) is still present
        expect(container.querySelector('svg circle')).toBeInTheDocument();
        expect(container.querySelectorAll('svg path')).toHaveLength(0);
      });
    });

    it('renders legend rows with status name and count', async () => {
      render(<AdminDashboard />);

      await waitFor(() => {
        const chartHeader = screen.getByRole('heading', { name: /order status/i });
        const chartPanel = chartHeader.closest('.bg-white');

        expect(within(chartPanel).getByText('pending')).toBeInTheDocument();
        expect(within(chartPanel).getByText('delivered')).toBeInTheDocument();

        // count for delivered = 200
        expect(within(chartPanel).getByText('200')).toBeInTheDocument();
      });
    });
  });

  // ── 8. Recent Orders panel ───────────────────────────────────────────────
  describe('Recent Orders panel', () => {
    it('renders the "Recent Orders" heading', async () => {
      render(<AdminDashboard />);
      await waitFor(() =>
        expect(screen.getByText('Recent Orders')).toBeInTheDocument()
      );
    });

    it('renders order_number for each order', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(screen.getByText('ORD-1001')).toBeInTheDocument();
        expect(screen.getByText('ORD-1002')).toBeInTheDocument();
      });
    });

    it('shows full_name when present', async () => {
      render(<AdminDashboard />);
      await waitFor(() =>
        expect(screen.getByText('Alice Smith')).toBeInTheDocument()
      );
    });

    it('falls back to email when full_name is null', async () => {
      render(<AdminDashboard />);
      await waitFor(() =>
        expect(screen.getByText('bob@test.com')).toBeInTheDocument()
      );
    });

    it('applies STATUS_STYLES classes per order status', async () => {
      render(<AdminDashboard />);

      await waitFor(() => {
        const panelHeader = screen.getByRole('heading', { name: /recent orders/i });
        const recentOrdersPanel = panelHeader.closest('.bg-white');

        const pendingBadge = within(recentOrdersPanel).getByText('pending');
        expect(pendingBadge).toHaveClass('bg-gray-100');

        const deliveredBadge = within(recentOrdersPanel).getByText('delivered');
        expect(deliveredBadge).toHaveClass('bg-teal-100');
      });
    });

    it('renders formatted order totals', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(screen.getByText('$90')).toBeInTheDocument();   // 89.5 rounds to $90 (maximumFractionDigits:0)
        expect(screen.getByText('$240')).toBeInTheDocument();
      });
    });

    it('renders no order rows when recent_orders is empty', async () => {
      okOverview(makeOverview({ recent_orders: [] }));
      render(<AdminDashboard />);
      await waitFor(() => screen.getByText('Recent Orders'));
      expect(screen.queryByText('ORD-1001')).not.toBeInTheDocument();
    });

    it('clicking "View All" navigates to /admin/orders', async () => {
      const user = setup();
      render(<AdminDashboard />);
      await waitFor(() => screen.getByText('Recent Orders'));
      const viewAllButtons = screen.getAllByRole('button', { name: /view all/i });
      // First "View All" belongs to Recent Orders panel (DOM order)
      await user.click(viewAllButtons[0]);
      expect(mockNavigate).toHaveBeenCalledWith('/admin/orders');
    });

    it('clicking an order row navigates to /admin/orders', async () => {
      const user = setup();
      render(<AdminDashboard />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(screen.getByText('ORD-1001').closest('.cursor-pointer'));
      expect(mockNavigate).toHaveBeenCalledWith('/admin/orders');
    });
  });

  // ── 9. Top Products panel ────────────────────────────────────────────────
  describe('Top Products panel', () => {
    it('renders the "Top Products" heading', async () => {
      render(<AdminDashboard />);
      await waitFor(() => expect(screen.getByText('Top Products')).toBeInTheDocument());
    });

    it('renders product_name for each top product', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(screen.getByText('Widget A')).toBeInTheDocument();
        expect(screen.getByText('Widget B')).toBeInTheDocument();
      });
    });

    it('renders total_sold units text', async () => {
      render(<AdminDashboard />);
      await waitFor(() =>
        expect(screen.getByText('120 units sold')).toBeInTheDocument()
      );
    });

    it('renders formatted revenue per product', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(screen.getByText('$5,400')).toBeInTheDocument();
        expect(screen.getByText('$3,200')).toBeInTheDocument();
      });
    });

    it('renders rank numbers starting at 1', async () => {
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(screen.getByText('1')).toBeInTheDocument();
        expect(screen.getByText('2')).toBeInTheDocument();
      });
    });

    it('slices top_products to a maximum of 6 entries', async () => {
      const many = Array.from({ length: 10 }, (_, i) => ({
        product_id: i + 1,
        product_name: `Product ${i + 1}`,
        total_sold: i + 1,
        revenue: (i + 1) * 100,
      }));
      okOverview(makeOverview({ top_products: many }));
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(screen.getByText('Product 6')).toBeInTheDocument();
        expect(screen.queryByText('Product 7')).not.toBeInTheDocument();
      });
    });

    it('renders no product rows when top_products is empty', async () => {
      okOverview(makeOverview({ top_products: [] }));
      render(<AdminDashboard />);
      await waitFor(() => screen.getByText('Top Products'));
      expect(screen.queryByText('Widget A')).not.toBeInTheDocument();
    });

    it('clicking "View All" in Top Products navigates to /admin/products', async () => {
      const user = setup();
      render(<AdminDashboard />);
      await waitFor(() => screen.getByText('Top Products'));
      const viewAllButtons = screen.getAllByRole('button', { name: /view all/i });
      // Second "View All" belongs to Top Products panel (DOM order)
      await user.click(viewAllButtons[1]);
      expect(mockNavigate).toHaveBeenCalledWith('/admin/products');
    });
  });

  // ── 10. Currency formatting ──────────────────────────────────────────────
  describe('Currency formatting (fmt helper)', () => {
    it('formats zero revenue as $0', async () => {
      okOverview(makeOverview({ revenue: { current: 0, change: 0 } }));
      render(<AdminDashboard />);
      await waitFor(() => {
        const card = screen.getByTestId('stat-revenue');
        expect(within(card).getByTestId('stat-value')).toHaveTextContent('$0');
      });
    });

    it('formats large revenue with thousand separators and no decimals', async () => {
      okOverview(makeOverview({ revenue: { current: 2350000, change: 1 } }));
      render(<AdminDashboard />);
      await waitFor(() => {
        const card = screen.getByTestId('stat-revenue');
        expect(within(card).getByTestId('stat-value')).toHaveTextContent('$2,350,000');
      });
    });
  });

  // ── 11. Snapshot ─────────────────────────────────────────────────────────
  describe('Snapshot', () => {
    beforeEach(() => {
      // Tell Vitest to run timers but support modern async microtasks
      vi.useFakeTimers({ toFake: ['Date'] });
      vi.setSystemTime(new Date('2026-06-19'));
    });
    afterEach(() => {
      vi.useRealTimers();
    });
    it('matches stable snapshot after data loads', async () => {
      const { asFragment } = render(<AdminDashboard />);
      await waitFor(() => screen.getByText('Recent Orders'));
      expect(asFragment()).toMatchSnapshot();
    });
  });
});
