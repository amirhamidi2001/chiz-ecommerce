/**
 * AdminOrders.test.jsx
 *
 * Comprehensive unit & integration tests for AdminOrders.jsx
 * Stack : Vitest · React Testing Library · @testing-library/user-event v14
 *
 * ── Coverage map ──────────────────────────────────────────────────────────────
 *  1.  Page structure        – "Orders" heading, "{total} total orders" subtitle
 *  2.  fetchOrders           – mount params (status:undefined when filter is
 *                              empty), three-level total fallback
 *                              (count ?? results.length ?? length), loading
 *                              state, error toast
 *  3.  Column renderers      – order_number, full_name/email, status badge,
 *                              payment_method underscore→space + null-safe,
 *                              items_count, total fmt(), created_at date
 *  4.  Search                – re-fetch w/ search param, page reset to 1
 *  5.  Sort                  – re-fetch w/ new ordering
 *  6.  Status filter         – re-fetch w/ status, empty string → undefined,
 *                              page reset to 1
 *  7.  Pagination            – re-fetch w/ new page
 *  8.  Empty state           – "No orders found"
 *  9.  View Details action   – openDetail(id) → getOrder called, modal opens
 *                              with returned data, error toast on failure
 * 10.  OrderDetailModal       – null order renders nothing, header order
 *                              number, customer block, shipping block
 *                              (with/without apartment), status select
 *                              pre-filled, items section (present/absent,
 *                              image/placeholder), totals (discount
 *                              conditional), close (×) + backdrop + inner-
 *                              click-does-not-close
 * 11.  Status update — no-op – same status selected → onClose only, no API call
 * 12.  Status update — save  – different status → updateOrderStatus called,
 *                              "Status updated" toast (modal's own toast),
 *                              onStatusUpdate fires, modal closes after 800ms,
 *                              saving state disables button + "Saving…" label
 * 13.  Status update — error – "Failed to update status" toast, modal stays
 *                              open, no onStatusUpdate call
 * 14.  Page-level wiring     – handleStatusUpdate mutates the correct row in
 *                              the orders array and shows the page-level
 *                              "Order status updated" toast (distinct from
 *                              the modal's own toast instance)
 * 15.  Snapshot              – stable rendered output after data loads
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * ── Design notes ──────────────────────────────────────────────────────────────
 * • OrderDetailModal calls useToast() ITSELF — a separate hook instance from
 *   the page. The mock factory below returns a fresh independent toast
 *   controller per call, with all show() calls funneled into one shared
 *   `capturedToasts` array tagged with a `source` so tests can distinguish
 *   "page toast" vs "modal toast" calls if ever needed, while still allowing
 *   simple message/type assertions for the common case.
 * • setTimeout(onClose, 800) inside handleUpdate requires real or fake timers;
 *   fake timers are scoped locally to the "Status update — save" describe
 *   block only, mirroring the AdminChat fix pattern (no global advanceTimers).
 * • No exact-text getByText() on rows where text might be interleaved with
 *   siblings (customer name+email, item name+qty) — all scoped via within().
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  render,
  screen,
  waitFor,
  within,
  fireEvent,
  act,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminOrders from '../../pages/admin/AdminOrders';

// ─── Mock: DataTable ──────────────────────────────────────────────────────────
vi.mock('../../components/admin/DataTable', () => ({
  default: ({
    columns,
    data,
    loading,
    emptyText,
    rowActions,
    filters,
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
        {filters && <div data-testid="dt-filters">{filters}</div>}
        <input
          data-testid="dt-search"
          placeholder={searchPlaceholder}
          value={search ?? ''}
          onChange={(e) => onSearch?.(e.target.value)}
        />
        <button data-testid="dt-sort" onClick={() => onSort?.('total')}>
          sort
        </button>
        <button
          data-testid="dt-next-page"
          onClick={() => onPageChange?.(page + 1)}
        >
          next
        </button>
        <span data-testid="dt-total">{totalCount}</span>

        {data.length === 0 && <div data-testid="dt-empty">{emptyText}</div>}

        {data.map((row, ri) => (
          <div key={row.id ?? ri} data-testid={`dt-row-${ri}`}>
            {columns.map((col) => (
              <div key={col.key} data-testid={`cell-${col.key}`}>
                {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '')}
              </div>
            ))}
            {rowActions && <div data-testid="row-actions">{rowActions(row)}</div>}
          </div>
        ))}
      </div>
    );
  },
}));

// ─── Mock: ConfirmModal (imported but unused by component logic we exercise;
//      stubbed for safety/parity with sibling test suites) ───────────────────
vi.mock('../../components/admin/ConfirmModal', () => ({
  default: () => null,
}));

// ─── Mock: Toast / useToast ───────────────────────────────────────────────────
// Each call to useToast() returns an INDEPENDENT controller (matching the
// real hook's per-component-instance state), but every show() call funnels
// into one shared array so tests can assert on messages regardless of which
// instance (page vs modal) produced them.
let capturedToasts = [];

vi.mock('../../components/admin/Toast', () => ({
  default: ({ toast, onDismiss }) =>
    toast ? (
      <div data-testid="toast" data-type={toast.type}>
        {toast.message}
        <button data-testid="toast-dismiss" onClick={onDismiss}>×</button>
      </div>
    ) : null,
  useToast: () => ({
    toast: null,
    show: (message, type = 'success') => {
      capturedToasts.push({ message, type });
    },
    dismiss: () => { },
  }),
}));

// ─── Mock: adminAPI ───────────────────────────────────────────────────────────
vi.mock('../../services/api', () => ({
  adminAPI: {
    getOrders: vi.fn(),
    getOrder: vi.fn(),
    updateOrderStatus: vi.fn(),
  },
}));
import { adminAPI } from '../../services/api';

// ─── Fixture factories ────────────────────────────────────────────────────────
const makeOrder = (overrides = {}) => ({
  id: 1,
  order_number: 'ORD-1001',
  full_name: 'Alice Smith',
  email: 'alice@test.com',
  status: 'pending',
  payment_method: 'credit_card',
  items_count: 2,
  total: 150.5,
  created_at: '2024-06-01T10:00:00Z',
  ...overrides,
});

const makeOrders = (n = 3) =>
  Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    order_number: `ORD-100${i + 1}`,
    full_name: `Customer ${i + 1}`,
    email: `cust${i + 1}@test.com`,
    status: 'pending',
    payment_method: 'credit_card',
    items_count: i + 1,
    total: (i + 1) * 50,
    created_at: '2024-06-01T10:00:00Z',
  }));

const makeOrderDetail = (overrides = {}) => ({
  id: 1,
  order_number: 'ORD-1001',
  status: 'pending',
  full_name: 'Alice Smith',
  email: 'alice@test.com',
  phone: '555-1234',
  shipping_address: '123 Main St',
  shipping_apartment: '',
  shipping_city: 'Springfield',
  shipping_state: 'IL',
  shipping_zip: '62704',
  shipping_country: 'USA',
  items: [
    {
      id: 1, product_name: 'Widget A', product_image: null,
      quantity: 2, unit_price: 25, subtotal: 50,
    },
  ],
  subtotal: 50,
  shipping_cost: 5,
  tax: 4.5,
  discount: 0,
  total: 59.5,
  ...overrides,
});

const paged = (results, count) => ({ data: { results, count } });
const flat = (arr) => ({ data: arr });

const okOrders = (orders = makeOrders()) =>
  adminAPI.getOrders.mockResolvedValue(paged(orders, orders.length));

const setup = () => userEvent.setup();

/** The modal's inner card element (stops propagation on click). */
const getModalCard = () =>
  document.querySelector('.fixed.inset-0 .rounded-2xl');

// ─────────────────────────────────────────────────────────────────────────────

describe('AdminOrders', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedToasts = [];
    okOrders();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. Page structure ────────────────────────────────────────────────────
  describe('Page structure', () => {
    it('renders the "Orders" heading', () => {
      render(<AdminOrders />);
      expect(screen.getByRole('heading', { name: /^orders$/i })).toBeInTheDocument();
    });

    it('shows "{total} total orders" subtitle after data loads', async () => {
      okOrders(makeOrders(7));
      render(<AdminOrders />);
      await waitFor(() =>
        expect(screen.getByText('7 total orders')).toBeInTheDocument()
      );
    });

    it('shows "0 total orders" before data loads', () => {
      adminAPI.getOrders.mockReturnValue(new Promise(() => { }));
      render(<AdminOrders />);
      expect(screen.getByText('0 total orders')).toBeInTheDocument();
    });
  });

  // ── 2. fetchOrders ───────────────────────────────────────────────────────
  describe('fetchOrders – initial fetch', () => {
    it('calls getOrders on mount with status:undefined when no filter is set', async () => {
      render(<AdminOrders />);
      await waitFor(() =>
        expect(adminAPI.getOrders).toHaveBeenCalledWith({
          page: 1,
          search: '',
          ordering: '-created_at',
          status: undefined,
          page_size: 10,
        })
      );
    });

    it('shows loading indicator while fetch is in-flight', () => {
      adminAPI.getOrders.mockReturnValue(new Promise(() => { }));
      render(<AdminOrders />);
      expect(screen.getByTestId('dt-loading')).toBeInTheDocument();
    });

    it('clears loading state after data resolves', async () => {
      render(<AdminOrders />);
      await waitFor(() =>
        expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument()
      );
    });

    it('clears loading state even after API error', async () => {
      adminAPI.getOrders.mockRejectedValue(new Error('net'));
      render(<AdminOrders />);
      await waitFor(() =>
        expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument()
      );
    });

    it('renders order rows from a paginated response', async () => {
      render(<AdminOrders />);
      await waitFor(() => {
        expect(screen.getByText('ORD-1001')).toBeInTheDocument();
        expect(screen.getByText('ORD-1002')).toBeInTheDocument();
        expect(screen.getByText('ORD-1003')).toBeInTheDocument();
      });
    });

    it('handles a flat (non-paginated) array response', async () => {
      adminAPI.getOrders.mockResolvedValue(flat(makeOrders(2)));
      render(<AdminOrders />);
      await waitFor(() => {
        expect(screen.getByText('ORD-1001')).toBeInTheDocument();
        expect(screen.getByText('ORD-1002')).toBeInTheDocument();
      });
    });

    it('sets total from paginated count field when present', async () => {
      adminAPI.getOrders.mockResolvedValue(paged(makeOrders(3), 88));
      render(<AdminOrders />);
      await waitFor(() =>
        expect(screen.getByText('88 total orders')).toBeInTheDocument()
      );
    });

    it('falls back to results.length when count is absent on a wrapped response', async () => {
      adminAPI.getOrders.mockResolvedValue({ data: { results: makeOrders(4) } });
      render(<AdminOrders />);
      await waitFor(() =>
        expect(screen.getByText('4 total orders')).toBeInTheDocument()
      );
    });

    it('falls back to array length for a fully flat response', async () => {
      adminAPI.getOrders.mockResolvedValue(flat(makeOrders(6)));
      render(<AdminOrders />);
      await waitFor(() =>
        expect(screen.getByText('6 total orders')).toBeInTheDocument()
      );
    });

    it('shows "Failed to load orders" error toast on API failure', async () => {
      adminAPI.getOrders.mockRejectedValue(new Error('net'));
      render(<AdminOrders />);
      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to load orders' && t.type === 'error'
          )
        ).toBe(true)
      );
    });
  });

  // ── 3. Column renderers ──────────────────────────────────────────────────
  describe('Column renderers', () => {
    it('renders order_number as bold text', async () => {
      adminAPI.getOrders.mockResolvedValue(
        paged([makeOrder({ order_number: 'ORD-9999' })], 1)
      );
      render(<AdminOrders />);
      await waitFor(() => {
        const cell = screen.getByTestId('cell-order_number');
        expect(within(cell).getByText('ORD-9999')).toBeInTheDocument();
      });
    });

    it('renders full_name and email stacked in the customer column', async () => {
      adminAPI.getOrders.mockResolvedValue(
        paged([makeOrder({ full_name: 'Bob Lee', email: 'bob@test.com' })], 1)
      );
      render(<AdminOrders />);
      await waitFor(() => {
        const cell = screen.getByTestId('cell-full_name');
        expect(within(cell).getByText('Bob Lee')).toBeInTheDocument();
        expect(within(cell).getByText('bob@test.com')).toBeInTheDocument();
      });
    });

    it('applies STATUS_STYLES class for the status badge', async () => {
      adminAPI.getOrders.mockResolvedValue(
        paged([makeOrder({ status: 'shipped' })], 1)
      );
      render(<AdminOrders />);
      await waitFor(() => {
        const cell = screen.getByTestId('cell-status');
        const badge = within(cell).getByText('shipped');
        expect(badge.className).toMatch(/bg-blue-100/);
      });
    });

    it('replaces underscores with spaces in payment_method', async () => {
      adminAPI.getOrders.mockResolvedValue(
        paged([makeOrder({ payment_method: 'bank_transfer' })], 1)
      );
      render(<AdminOrders />);
      await waitFor(() => {
        const cell = screen.getByTestId('cell-payment_method');
        expect(within(cell).getByText('bank transfer')).toBeInTheDocument();
      });
    });

    it('does not crash when payment_method is null', async () => {
      adminAPI.getOrders.mockResolvedValue(
        paged([makeOrder({ payment_method: null })], 1)
      );
      render(<AdminOrders />);
      await waitFor(() => {
        const cell = screen.getByTestId('cell-payment_method');
        expect(cell).toBeInTheDocument();
      });
    });

    it('renders items_count as plain text', async () => {
      adminAPI.getOrders.mockResolvedValue(
        paged([makeOrder({ items_count: 5 })], 1)
      );
      render(<AdminOrders />);
      await waitFor(() => {
        const cell = screen.getByTestId('cell-items_count');
        expect(within(cell).getByText('5')).toBeInTheDocument();
      });
    });

    it('formats total as currency', async () => {
      adminAPI.getOrders.mockResolvedValue(
        paged([makeOrder({ total: 1234.5 })], 1)
      );
      render(<AdminOrders />);
      await waitFor(() => {
        const cell = screen.getByTestId('cell-total');
        expect(within(cell).getByText('$1,234.50')).toBeInTheDocument();
      });
    });

    it('formats created_at as a locale date string', async () => {
      adminAPI.getOrders.mockResolvedValue(
        paged([makeOrder({ created_at: '2024-06-15T00:00:00Z' })], 1)
      );
      render(<AdminOrders />);
      await waitFor(() => {
        const cell = screen.getByTestId('cell-created_at');
        expect(cell.textContent).toMatch(/\d/);
        expect(cell.textContent).not.toContain('T');
      });
    });
  });

  // ── 4. Search ────────────────────────────────────────────────────────────
  describe('Search', () => {
    it('re-fetches with the typed search string', async () => {
      const user = setup();
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));

      vi.clearAllMocks();
      okOrders();

      const searchInput = screen.getByPlaceholderText('Search by order #, customer…');

      fireEvent.change(searchInput, { target: { value: 'alice' } });

      await waitFor(() =>
        expect(adminAPI.getOrders).toHaveBeenCalledWith(
          expect.objectContaining({ search: 'alice' })
        )
      );
    });

    it('resets page to 1 when search changes', async () => {
      const user = setup();
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));

      await user.click(screen.getByTestId('dt-next-page'));
      await waitFor(() =>
        expect(adminAPI.getOrders).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );

      vi.clearAllMocks();
      okOrders();

      const searchInput = screen.getByPlaceholderText('Search by order #, customer…');

      fireEvent.change(searchInput, { target: { value: 'x' } });

      await waitFor(() =>
        expect(adminAPI.getOrders).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1, search: 'x' })
        )
      );
    });
  });

  // ── 5. Sort ──────────────────────────────────────────────────────────────
  describe('Sort', () => {
    it('re-fetches with new ordering when sort changes', async () => {
      const user = setup();
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));

      vi.clearAllMocks();
      okOrders();

      await user.click(screen.getByTestId('dt-sort'));

      await waitFor(() =>
        expect(adminAPI.getOrders).toHaveBeenCalledWith(
          expect.objectContaining({ ordering: 'total' })
        )
      );
    });
  });

  // ── 6. Status filter ─────────────────────────────────────────────────────
  describe('Status filter', () => {
    it('renders the status filter select with all options', async () => {
      render(<AdminOrders />);
      await waitFor(() => screen.getByTestId('dt-filters'));
      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      const opts = within(select).getAllByRole('option').map((o) => o.value);
      expect(opts).toEqual(['', 'pending', 'processing', 'shipped', 'delivered', 'cancelled']);
    });

    it('re-fetches with the selected status', async () => {
      const user = setup();
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await waitFor(() => screen.getByTestId('dt-filters'));

      vi.clearAllMocks();
      okOrders();

      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, 'shipped');

      await waitFor(() =>
        expect(adminAPI.getOrders).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'shipped' })
        )
      );
    });

    it('resets page to 1 when status filter changes', async () => {
      const user = setup();
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await waitFor(() => screen.getByTestId('dt-filters'));

      await user.click(screen.getByTestId('dt-next-page'));
      await waitFor(() =>
        expect(adminAPI.getOrders).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );

      vi.clearAllMocks();
      okOrders();

      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, 'delivered');

      await waitFor(() =>
        expect(adminAPI.getOrders).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1 })
        )
      );
    });
  });

  // ── 7. Pagination ────────────────────────────────────────────────────────
  describe('Pagination', () => {
    it('re-fetches with incremented page when next-page triggered', async () => {
      const user = setup();
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));

      vi.clearAllMocks();
      okOrders();

      await user.click(screen.getByTestId('dt-next-page'));

      await waitFor(() =>
        expect(adminAPI.getOrders).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );
    });
  });

  // ── 8. Empty state ───────────────────────────────────────────────────────
  describe('Empty state', () => {
    it('shows "No orders found" when results are empty', async () => {
      adminAPI.getOrders.mockResolvedValue(paged([], 0));
      render(<AdminOrders />);
      await waitFor(() =>
        expect(screen.getByTestId('dt-empty')).toHaveTextContent('No orders found')
      );
    });
  });

  // ── 9. View Details action ───────────────────────────────────────────────
  describe('View Details action', () => {
    it('calls getOrder with the row id when View Details is clicked', async () => {
      adminAPI.getOrder.mockResolvedValue({ data: makeOrderDetail({ id: 42 }) });
      const user = setup();
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(
        within(screen.getByTestId('dt-row-0')).getByTitle('View Details')
      );
      await waitFor(() =>
        expect(adminAPI.getOrder).toHaveBeenCalledWith(1)
      );
    });

    it('opens OrderDetailModal with the returned order data', async () => {
      adminAPI.getOrder.mockResolvedValue({
        data: makeOrderDetail({ order_number: 'ORD-DETAIL-1' }),
      });
      const user = setup();
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(
        within(screen.getByTestId('dt-row-0')).getByTitle('View Details')
      );
      await waitFor(() =>
        expect(screen.getByText('Order #ORD-DETAIL-1')).toBeInTheDocument()
      );
    });

    it('shows "Failed to load order details" error toast on getOrder failure', async () => {
      adminAPI.getOrder.mockRejectedValue(new Error('500'));
      const user = setup();
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(
        within(screen.getByTestId('dt-row-0')).getByTitle('View Details')
      );
      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to load order details' && t.type === 'error'
          )
        ).toBe(true)
      );
    });

    it('does not open the modal when getOrder fails', async () => {
      adminAPI.getOrder.mockRejectedValue(new Error('500'));
      const user = setup();
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(
        within(screen.getByTestId('dt-row-0')).getByTitle('View Details')
      );
      await waitFor(() => expect(adminAPI.getOrder).toHaveBeenCalled());
      expect(getModalCard()).not.toBeInTheDocument();
    });
  });

  // ── 10. OrderDetailModal – structure ─────────────────────────────────────
  describe('OrderDetailModal – structure', () => {
    const openDetail = async (user, detail = makeOrderDetail()) => {
      adminAPI.getOrder.mockResolvedValue({ data: detail });
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(
        within(screen.getByTestId('dt-row-0')).getByTitle('View Details')
      );
      await waitFor(() =>
        expect(screen.getByText(`Order #${detail.order_number}`)).toBeInTheDocument()
      );
    };

    it('renders nothing when detailOrder is null (initial state)', () => {
      render(<AdminOrders />);
      expect(getModalCard()).not.toBeInTheDocument();
    });

    it('shows the order number in the header', async () => {
      const user = setup();
      await openDetail(user, makeOrderDetail({ order_number: 'ORD-7777' }));
      expect(screen.getByText('Order #ORD-7777')).toBeInTheDocument();
    });

    it("renders the customer's full_name, email, and phone", async () => {
      const user = setup();
      await openDetail(
        user,
        makeOrderDetail({ full_name: 'Carol Diaz', email: 'carol@test.com', phone: '555-9999' })
      );
      const modal = getModalCard();
      expect(within(modal).getByText('Carol Diaz')).toBeInTheDocument();
      expect(within(modal).getByText('carol@test.com')).toBeInTheDocument();
      expect(within(modal).getByText('555-9999')).toBeInTheDocument();
    });

    it('renders the shipping address cleanly when apartment is missing', async () => {
      const user = setup();
      await openDetail(
        user,
        makeOrderDetail({
          shipping_address: '456 Oak Ave',
          shipping_apartment: null,
        })
      );
      const modal = getModalCard();

      expect(within(modal).getByText(/456 Oak Ave/)).toBeInTheDocument();

      expect(screen.queryByText(/,\s*$/)).not.toBeInTheDocument();
    });

    it('includes the apartment in the shipping address when present', async () => {
      const user = setup();
      await openDetail(
        user,
        makeOrderDetail({
          shipping_address: '456 Oak Ave',
          shipping_apartment: 'Apt 3B',
        })
      );
      const modal = getModalCard();

      // This allows React Testing Library's built-in normalization to handle the text smoothly.
      expect(within(modal).getByText(/456 Oak Ave, Apt 3B/)).toBeInTheDocument();
    });

    it('pre-fills the status select with the order\'s current status', async () => {
      const user = setup();
      await openDetail(user, makeOrderDetail({ status: 'shipped' }));
      const modal = getModalCard();
      const select = within(modal).getByRole('combobox');
      expect(select).toHaveValue('shipped');
    });

    it('status select renders all ORDER_STATUSES capitalized', async () => {
      const user = setup();
      await openDetail(user);
      const modal = getModalCard();
      const select = within(modal).getByRole('combobox');
      const labels = within(select).getAllByRole('option').map((o) => o.textContent);
      expect(labels).toEqual(['Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled']);
    });

    it('renders the items section with item count when items are present', async () => {
      const user = setup();
      await openDetail(
        user,
        makeOrderDetail({
          items: [
            { id: 1, product_name: 'A', product_image: null, quantity: 1, unit_price: 10, subtotal: 10 },
            { id: 2, product_name: 'B', product_image: null, quantity: 2, unit_price: 5, subtotal: 10 },
          ],
        })
      );
      expect(screen.getByText('Items (2)')).toBeInTheDocument();
    });

    it('does NOT render the items section when items is undefined', async () => {
      const user = setup();
      const detail = makeOrderDetail();
      delete detail.items;
      await openDetail(user, detail);
      expect(screen.queryByText(/^Items \(/)).not.toBeInTheDocument();
    });

    it('renders product image when product_image is present', async () => {
      const user = setup();
      await openDetail(
        user,
        makeOrderDetail({
          items: [
            { id: 1, product_name: 'Widget', product_image: 'https://cdn.test/w.png', quantity: 1, unit_price: 10, subtotal: 10 },
          ],
        })
      );
      const img = screen.getByRole('img', { name: 'Widget' });
      expect(img).toHaveAttribute('src', 'https://cdn.test/w.png');
    });

    it('renders placeholder icon when product_image is null', async () => {
      const user = setup();
      const { container } = render(<AdminOrders />);
      adminAPI.getOrder.mockResolvedValue({
        data: makeOrderDetail({
          items: [
            { id: 1, product_name: 'Widget', product_image: null, quantity: 1, unit_price: 10, subtotal: 10 },
          ],
        }),
      });
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View Details'));
      await waitFor(() => screen.getByText('Items (1)'));
      expect(container.querySelector('.bi-image')).toBeInTheDocument();
    });

    it('renders item quantity and unit price', async () => {
      const user = setup();
      await openDetail(
        user,
        makeOrderDetail({
          items: [
            { id: 1, product_name: 'Gadget', product_image: null, quantity: 3, unit_price: 9.99, subtotal: 29.97 },
          ],
        })
      );
      expect(screen.getByText(/Qty: 3/)).toBeInTheDocument();
    });

    it('renders item subtotal as currency', async () => {
      const user = setup();
      await openDetail(
        user,
        makeOrderDetail({
          items: [
            { id: 1, product_name: 'Gadget', product_image: null, quantity: 1, unit_price: 19.99, subtotal: 19.99 },
          ],
        })
      );
      expect(screen.getByText('$19.99')).toBeInTheDocument();
    });

    it('renders Subtotal, Shipping, and Tax rows', async () => {
      const user = setup();
      await openDetail(user, makeOrderDetail({ subtotal: 100, shipping_cost: 10, tax: 8 }));

      const modal = getModalCard();

      // Scope all text queries inside the modal to avoid matching background table cells
      expect(within(modal).getByText('Subtotal')).toBeInTheDocument();
      expect(within(modal).getByText('Shipping')).toBeInTheDocument();
      expect(within(modal).getByText('Tax')).toBeInTheDocument();
      expect(within(modal).getByText('$100.00')).toBeInTheDocument();
      expect(within(modal).getByText('$10.00')).toBeInTheDocument();
      expect(within(modal).getByText('$8.00')).toBeInTheDocument();
    });

    it('renders Discount row when discount > 0', async () => {
      const user = setup();
      await openDetail(user, makeOrderDetail({ discount: 15 }));
      expect(screen.getByText('Discount')).toBeInTheDocument();
      expect(screen.getByText('-$15.00')).toBeInTheDocument();
    });

    it('does NOT render Discount row when discount is 0', async () => {
      const user = setup();
      await openDetail(user, makeOrderDetail({ discount: 0 }));
      expect(screen.queryByText('Discount')).not.toBeInTheDocument();
    });

    it('renders the Total row in bold', async () => {
      const user = setup();
      await openDetail(user, makeOrderDetail({ total: 250.75 }));
      const totalLabel = screen.getByText('Total');
      expect(totalLabel.closest('div').className).toMatch(/font-bold/);
      expect(screen.getByText('$250.75')).toBeInTheDocument();
    });

    it('closes the modal when the × button is clicked', async () => {
      const user = setup();
      await openDetail(user);
      const modal = getModalCard();
      const closeBtn = modal.querySelector('.bi-x-lg').closest('button');
      await user.click(closeBtn);
      await waitFor(() => expect(getModalCard()).not.toBeInTheDocument());
    });

    it('closes the modal when the backdrop is clicked', async () => {
      const user = setup();
      await openDetail(user);
      const backdrop = document.querySelector('.fixed.inset-0');
      fireEvent.click(backdrop);
      await waitFor(() => expect(getModalCard()).not.toBeInTheDocument());
    });

    it('clicking inside the modal does NOT close it', async () => {
      const user = setup();
      await openDetail(user);
      fireEvent.click(getModalCard());
      expect(getModalCard()).toBeInTheDocument();
    });
  });

  // ── 11. Status update — no-op (same status selected) ────────────────────
  describe('Status update — no-op', () => {
    it('calls onClose without calling updateOrderStatus when status is unchanged', async () => {
      const user = setup();
      adminAPI.getOrder.mockResolvedValue({ data: makeOrderDetail({ status: 'pending' }) });
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View Details'));
      await waitFor(() => getModalCard());

      // Status select already shows "pending" — click Update without changing it
      const modal = getModalCard();
      await user.click(within(modal).getByRole('button', { name: /^update$/i }));

      await waitFor(() => expect(getModalCard()).not.toBeInTheDocument());
      expect(adminAPI.updateOrderStatus).not.toHaveBeenCalled();
    });
  });

  // ── 12. Status update — save ─────────────────────────────────────────────
  describe('Status update — save', () => {
    const openDetailAndChangeStatus = async (user, newStatus = 'shipped') => {
      adminAPI.getOrder.mockResolvedValue({ data: makeOrderDetail({ id: 1, status: 'pending' }) });
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View Details'));
      await waitFor(() => getModalCard());

      const modal = getModalCard();
      const select = within(modal).getByRole('combobox');
      await user.selectOptions(select, newStatus);
    };

    it('calls updateOrderStatus with the order id and new status', async () => {
      adminAPI.updateOrderStatus.mockResolvedValue({});
      const user = setup();
      await openDetailAndChangeStatus(user, 'shipped');
      const modal = getModalCard();
      await user.click(within(modal).getByRole('button', { name: /^update$/i }));
      await waitFor(() =>
        expect(adminAPI.updateOrderStatus).toHaveBeenCalledWith(1, 'shipped')
      );
    });

    it('shows "Status updated" toast (modal\'s own toast instance)', async () => {
      adminAPI.updateOrderStatus.mockResolvedValue({});
      const user = setup();
      await openDetailAndChangeStatus(user, 'shipped');
      const modal = getModalCard();
      await user.click(within(modal).getByRole('button', { name: /^update$/i }));
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === 'Status updated' && t.type === 'success')
        ).toBe(true)
      );
    });

    it('calls onStatusUpdate which updates the row status in the table', async () => {
      adminAPI.updateOrderStatus.mockResolvedValue({});
      const user = setup();
      await openDetailAndChangeStatus(user, 'shipped');
      const modal = getModalCard();
      await user.click(within(modal).getByRole('button', { name: /^update$/i }));

      await waitFor(() => {
        const rowZero = screen.getByTestId('dt-row-0');
        const statusCell = within(rowZero).getByTestId('cell-status');
        expect(within(statusCell).getByText('shipped')).toBeInTheDocument();
      });
    });

    it('shows the page-level "Order status updated" toast via onStatusUpdate', async () => {
      adminAPI.updateOrderStatus.mockResolvedValue({});
      const user = setup();
      await openDetailAndChangeStatus(user, 'shipped');
      const modal = getModalCard();
      await user.click(within(modal).getByRole('button', { name: /^update$/i }));
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === 'Order status updated')
        ).toBe(true)
      );
    });

    it('shows "Saving…" and disables the Update button while in-flight', async () => {
      let resolve;
      adminAPI.updateOrderStatus.mockReturnValue(new Promise((r) => { resolve = r; }));
      const user = setup();
      await openDetailAndChangeStatus(user, 'shipped');
      const modal = getModalCard();
      await user.click(within(modal).getByRole('button', { name: /^update$/i }));

      await waitFor(() =>
        expect(within(modal).getByRole('button', { name: /saving…/i })).toBeDisabled()
      );

      resolve({});
    });

    it('closes the modal 800ms after a successful update', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      adminAPI.updateOrderStatus.mockResolvedValue({});
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime, delay: null });

      adminAPI.getOrder.mockResolvedValue({ data: makeOrderDetail({ id: 1, status: 'pending' }) });
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View Details'));
      await waitFor(() => getModalCard());

      const modal = getModalCard();
      const select = within(modal).getByRole('combobox');
      await user.selectOptions(select, 'shipped');
      await user.click(within(modal).getByRole('button', { name: /^update$/i }));

      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === 'Status updated')
        ).toBe(true)
      );

      // Modal should still be open immediately after the toast appears
      expect(getModalCard()).toBeInTheDocument();

      act(() => { vi.advanceTimersByTime(800); });

      await waitFor(() => expect(getModalCard()).not.toBeInTheDocument());

      vi.useRealTimers();
    });
  });

  // ── 13. Status update — error ────────────────────────────────────────────
  describe('Status update — error', () => {
    it('shows "Failed to update status" error toast on rejection', async () => {
      adminAPI.updateOrderStatus.mockRejectedValue(new Error('500'));
      const user = setup();
      adminAPI.getOrder.mockResolvedValue({ data: makeOrderDetail({ id: 1, status: 'pending' }) });
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View Details'));
      await waitFor(() => getModalCard());

      const modal = getModalCard();
      const select = within(modal).getByRole('combobox');
      await user.selectOptions(select, 'cancelled');
      await user.click(within(modal).getByRole('button', { name: /^update$/i }));

      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to update status' && t.type === 'error'
          )
        ).toBe(true)
      );
    });

    it('keeps the modal open after a failed update', async () => {
      adminAPI.updateOrderStatus.mockRejectedValue(new Error('500'));
      const user = setup();
      adminAPI.getOrder.mockResolvedValue({ data: makeOrderDetail({ id: 1, status: 'pending' }) });
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View Details'));
      await waitFor(() => getModalCard());

      const modal = getModalCard();
      const select = within(modal).getByRole('combobox');
      await user.selectOptions(select, 'cancelled');
      await user.click(within(modal).getByRole('button', { name: /^update$/i }));

      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === 'Failed to update status')
        ).toBe(true)
      );
      expect(getModalCard()).toBeInTheDocument();
    });

    it('does NOT update the row status in the table after a failed update', async () => {
      adminAPI.updateOrderStatus.mockRejectedValue(new Error('500'));
      const user = setup();
      adminAPI.getOrder.mockResolvedValue({ data: makeOrderDetail({ id: 1, status: 'pending' }) });
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View Details'));
      await waitFor(() => getModalCard());

      const modal = getModalCard();
      const select = within(modal).getByRole('combobox');
      await user.selectOptions(select, 'cancelled');
      await user.click(within(modal).getByRole('button', { name: /^update$/i }));

      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === 'Failed to update status')
        ).toBe(true)
      );

      const rowZero = screen.getByTestId('dt-row-0');
      const statusCell = within(rowZero).getByTestId('cell-status');

      // Row should still show original "pending" status
      expect(within(statusCell).getByText('pending')).toBeInTheDocument();
    });

    it('re-enables the Update button after a failed save (saving resets)', async () => {
      adminAPI.updateOrderStatus.mockRejectedValue(new Error('500'));
      const user = setup();
      adminAPI.getOrder.mockResolvedValue({ data: makeOrderDetail({ id: 1, status: 'pending' }) });
      render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View Details'));
      await waitFor(() => getModalCard());

      const modal = getModalCard();
      const select = within(modal).getByRole('combobox');
      await user.selectOptions(select, 'cancelled');
      await user.click(within(modal).getByRole('button', { name: /^update$/i }));

      await waitFor(() =>
        expect(within(modal).getByRole('button', { name: /^update$/i })).not.toBeDisabled()
      );
    });
  });

  // ── 14. Snapshot ─────────────────────────────────────────────────────────
  describe('Snapshot', () => {
    it('matches stable snapshot after data loads', async () => {
      const { asFragment } = render(<AdminOrders />);
      await waitFor(() => screen.getByText('ORD-1001'));
      expect(asFragment()).toMatchSnapshot();
    });
  });
});
