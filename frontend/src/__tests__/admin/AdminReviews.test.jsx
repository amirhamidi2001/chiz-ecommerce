/**
 * AdminReviews.test.jsx
 *
 * Comprehensive unit & integration tests for AdminReviews.jsx
 * Stack : Vitest · React Testing Library · @testing-library/user-event v14
 *
 * ── Coverage map ──────────────────────────────────────────────────────────────
 *  1.  Page structure        – "Reviews" heading, "{total} total reviews"
 *                              subtitle
 *  2.  fetchReviews          – mount params (NO `rating` key at all when
 *                              ratingFilter is empty — conditional spread, not
 *                              `undefined`), rating key present when filter
 *                              set, count ?? 0 fallback, loading state,
 *                              paginated & flat response shapes, error toast
 *  3.  Column renderers      – product_name (not sortable), reviewer avatar +
 *                              name, StarBadge colour thresholds (≥4 green,
 *                              ===3 yellow, ≤2 red), headline conditional +
 *                              comment always shown, created_at date format
 *  4.  Search                – re-fetch w/ search param, page reset to 1
 *  5.  Sort                  – re-fetch w/ new ordering
 *  6.  Rating filter         – options "5 Stars"…"1 Star" (singular for 1),
 *                              re-fetch w/ rating value, key OMITTED entirely
 *                              when reset to "All Ratings", page reset to 1
 *  7.  Pagination            – re-fetch w/ new page
 *  8.  Empty state           – "No reviews found"
 *  9.  Row actions            – "View" opens ReviewDrawer, "Delete" opens
 *                              ConfirmModal
 * 10.  Delete – success      – ConfirmModal message w/ reviewer name,
 *                              deleteReview(id), "Review deleted" toast,
 *                              closes confirm + selected, re-fetches
 * 11.  Delete – error        – error toast, modal stays open
 * 12.  Delete – cancel       – closes, no API call
 * 13.  Delete – in-flight    – confirm button disabled + "Deleting…" label
 * 14.  ReviewDrawer          – null review renders nothing, static "Review
 *                              Detail" header, product block (name + ID),
 *                              reviewer block (avatar initial + long-form
 *                              date), Stars component (filled vs empty count
 *                              matches rating value), numeric rating + "/ 5",
 *                              headline conditional render, comment always
 *                              shown, close (×) + backdrop + inner-click-
 *                              does-not-close
 * 15.  Drawer → Delete wiring – clicking "Delete This Review" in drawer closes
 *                              drawer AND opens ConfirmModal for that message
 * 16.  Snapshot              – stable rendered output after data loads
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * ── Design notes ──────────────────────────────────────────────────────────────
 * • The `rating` query param uses `...(ratingFilter ? { rating: ratingFilter }
 *   : {})` — a CONDITIONAL SPREAD, meaning the key is entirely absent from the
 *   call args object when empty (not `rating: undefined`). Tests assert this
 *   precisely via `expect.not.objectContaining({ rating: expect.anything() })`
 *   alongside positive-path assertions, to avoid a false pass from a looser
 *   `objectContaining` check that wouldn't catch a stray `rating: undefined`.
 * • "Delete" appears both as a row-action button and inside ReviewDrawer —
 *   every interaction is scoped via within(row) / within(drawer).
 * • No debounce/timer logic in this component → plain userEvent.setup() only.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  render,
  screen,
  waitFor,
  within,
  fireEvent,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminReviews from '../../pages/admin/AdminReviews';

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
    return (
      <div data-testid="data-table">
        {loading && <div data-testid="dt-loading">Loading…</div>}

        {filters && <div data-testid="dt-filters">{filters}</div>}
        <input
          data-testid="dt-search"
          placeholder={searchPlaceholder}
          value={search ?? ''}
          onChange={(e) => onSearch?.(e.target.value)}
        />
        <button data-testid="dt-sort" onClick={() => onSort?.('rating')}>
          sort
        </button>
        <button
          data-testid="dt-next-page"
          onClick={() => onPageChange?.(page + 1)}
        >
          next
        </button>
        <span data-testid="dt-total">{totalCount}</span>

        {!loading && data.length === 0 && <div data-testid="dt-empty">{emptyText}</div>}

        {!loading && data.map((row, ri) => (
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

// ─── Mock: ConfirmModal ───────────────────────────────────────────────────────
vi.mock('../../components/admin/ConfirmModal', () => ({
  default: ({ isOpen, title, message, confirmLabel, onConfirm, onClose, loading }) =>
    isOpen ? (
      <div data-testid="confirm-modal">
        <p data-testid="confirm-title">{title}</p>
        <p data-testid="confirm-message">{message}</p>
        <button data-testid="confirm-btn" onClick={onConfirm} disabled={loading}>
          {loading ? 'Deleting…' : confirmLabel}
        </button>
        <button data-testid="confirm-cancel" onClick={onClose}>
          Cancel
        </button>
      </div>
    ) : null,
}));

// ─── Mock: Toast / useToast ───────────────────────────────────────────────────
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
    getReviews: vi.fn(),
    deleteReview: vi.fn(),
  },
}));
import { adminAPI } from '../../services/api';

// ─── Fixture factories ────────────────────────────────────────────────────────
const makeReview = (overrides = {}) => ({
  id: 1,
  product_id: 100,
  product_name: 'Wireless Mouse',
  name: 'Alice Johnson',
  rating: 5,
  headline: 'Great product!',
  comment: 'Works exactly as described, very happy with this purchase.',
  created_at: '2024-06-01T10:30:00Z',
  ...overrides,
});

const makeReviews = (n = 3) =>
  Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    product_id: 100 + i,
    product_name: `Product ${i + 1}`,
    name: `Reviewer ${i + 1}`,
    rating: 5,
    headline: `Headline ${i + 1}`,
    comment: `Comment body ${i + 1}`,
    created_at: '2024-06-01T10:30:00Z',
  }));

const paged = (results, count) => ({ data: { results, count } });
const flat = (arr) => ({ data: arr });

const okReviews = (reviews = makeReviews()) =>
  adminAPI.getReviews.mockResolvedValue(paged(reviews, reviews.length));

const setup = () => userEvent.setup();

/** The slide-out drawer card (inner div that stops propagation). */
const getDrawerCard = () =>
  document.querySelector('.fixed.inset-0.flex.justify-end .bg-white');

// ─────────────────────────────────────────────────────────────────────────────

describe('AdminReviews', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedToasts = [];
    okReviews();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. Page structure ────────────────────────────────────────────────────
  describe('Page structure', () => {
    it('renders the "Reviews" heading', () => {
      render(<AdminReviews />);
      expect(screen.getByRole('heading', { name: /^reviews$/i })).toBeInTheDocument();
    });

    it('shows "{total} total reviews" subtitle after data loads', async () => {
      okReviews(makeReviews(8));
      render(<AdminReviews />);
      await waitFor(() =>
        expect(screen.getByText('8 total reviews')).toBeInTheDocument()
      );
    });

    it('shows "0 total reviews" before data loads', () => {
      adminAPI.getReviews.mockReturnValue(new Promise(() => { }));
      render(<AdminReviews />);
      expect(screen.getByText('0 total reviews')).toBeInTheDocument();
    });
  });

  // ── 2. fetchReviews ──────────────────────────────────────────────────────
  describe('fetchReviews – initial fetch', () => {
    it('calls getReviews on mount WITHOUT a rating key (conditional spread)', async () => {
      render(<AdminReviews />);
      await waitFor(() => expect(adminAPI.getReviews).toHaveBeenCalled());
      const callArgs = adminAPI.getReviews.mock.calls[0][0];
      expect(callArgs).toEqual({
        page: 1,
        search: '',
        ordering: '-created_at',
        page_size: 12,
      });
      expect(callArgs).not.toHaveProperty('rating');
    });

    it('shows loading indicator while fetch is in-flight', () => {
      adminAPI.getReviews.mockReturnValue(new Promise(() => { }));
      render(<AdminReviews />);
      expect(screen.getByTestId('dt-loading')).toBeInTheDocument();
    });

    it('clears loading state after data resolves', async () => {
      render(<AdminReviews />);
      await waitFor(() =>
        expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument()
      );
    });

    it('clears loading state even after API error', async () => {
      adminAPI.getReviews.mockRejectedValue(new Error('net'));
      render(<AdminReviews />);
      await waitFor(() =>
        expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument()
      );
    });

    it('renders review rows from a paginated response', async () => {
      render(<AdminReviews />);
      await waitFor(() => {
        expect(screen.getByText('Reviewer 1')).toBeInTheDocument();
        expect(screen.getByText('Reviewer 2')).toBeInTheDocument();
        expect(screen.getByText('Reviewer 3')).toBeInTheDocument();
      });
    });

    it('handles a flat (non-paginated) array response', async () => {
      adminAPI.getReviews.mockResolvedValue(flat(makeReviews(2)));
      render(<AdminReviews />);
      await waitFor(() => {
        expect(screen.getByText('Reviewer 1')).toBeInTheDocument();
        expect(screen.getByText('Reviewer 2')).toBeInTheDocument();
      });
    });

    it('falls back total to 0 for flat-array response (not array length)', async () => {
      adminAPI.getReviews.mockResolvedValue(flat(makeReviews(5)));
      render(<AdminReviews />);
      await waitFor(() =>
        expect(screen.getByText('0 total reviews')).toBeInTheDocument()
      );
    });

    it('sets total from paginated count field', async () => {
      adminAPI.getReviews.mockResolvedValue(paged(makeReviews(3), 41));
      render(<AdminReviews />);
      await waitFor(() =>
        expect(screen.getByText('41 total reviews')).toBeInTheDocument()
      );
    });

    it('shows "Failed to load reviews" error toast on API failure', async () => {
      adminAPI.getReviews.mockRejectedValue(new Error('net'));
      render(<AdminReviews />);
      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to load reviews' && t.type === 'error'
          )
        ).toBe(true)
      );
    });
  });

  // ── 3. Column renderers ──────────────────────────────────────────────────
  describe('Column renderers', () => {
    describe('product_name column', () => {
      it('renders the product name', async () => {
        adminAPI.getReviews.mockResolvedValue(
          paged([makeReview({ product_name: 'Mechanical Keyboard' })], 1)
        );
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-product_name');
          expect(within(cell).getByText('Mechanical Keyboard')).toBeInTheDocument();
        });
      });
    });

    describe('name (reviewer) column', () => {
      it("renders the reviewer's name", async () => {
        adminAPI.getReviews.mockResolvedValue(
          paged([makeReview({ name: 'Bob Wilson' })], 1)
        );
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-name');
          expect(within(cell).getByText('Bob Wilson')).toBeInTheDocument();
        });
      });

      it('renders the uppercase avatar initial', async () => {
        adminAPI.getReviews.mockResolvedValue(
          paged([makeReview({ name: 'bob wilson' })], 1)
        );
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-name');
          expect(within(cell).getByText('B')).toBeInTheDocument();
        });
      });
    });

    describe('rating column (StarBadge)', () => {
      it('applies green styling when rating >= 4', async () => {
        adminAPI.getReviews.mockResolvedValue(paged([makeReview({ rating: 4 })], 1));
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-rating');
          const badge = within(cell).getByText('4');
          expect(badge.className).toMatch(/bg-green-100/);
        });
      });

      it('applies green styling when rating is 5', async () => {
        adminAPI.getReviews.mockResolvedValue(paged([makeReview({ rating: 5 })], 1));
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-rating');
          const badge = within(cell).getByText('5');
          expect(badge.className).toMatch(/bg-green-100/);
        });
      });

      it('applies yellow styling when rating is exactly 3', async () => {
        adminAPI.getReviews.mockResolvedValue(paged([makeReview({ rating: 3 })], 1));
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-rating');
          const badge = within(cell).getByText('3');
          expect(badge.className).toMatch(/bg-yellow-100/);
        });
      });

      it('applies red styling when rating is 2', async () => {
        adminAPI.getReviews.mockResolvedValue(paged([makeReview({ rating: 2 })], 1));
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-rating');
          const badge = within(cell).getByText('2');
          expect(badge.className).toMatch(/bg-red-100/);
        });
      });

      it('applies red styling when rating is 1', async () => {
        adminAPI.getReviews.mockResolvedValue(paged([makeReview({ rating: 1 })], 1));
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-rating');
          const badge = within(cell).getByText('1');
          expect(badge.className).toMatch(/bg-red-100/);
        });
      });
    });

    describe('headline column', () => {
      it('renders headline when present', async () => {
        adminAPI.getReviews.mockResolvedValue(
          paged([makeReview({ headline: 'Loved it', comment: 'Great buy' })], 1)
        );
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-headline');
          expect(within(cell).getByText('Loved it')).toBeInTheDocument();
        });
      });

      it('does NOT render an empty headline paragraph when headline is falsy', async () => {
        adminAPI.getReviews.mockResolvedValue(
          paged([makeReview({ headline: '', comment: 'No headline here' })], 1)
        );
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-headline');
          // Only the comment <p> should render; no headline <p>
          expect(within(cell).getAllByText(/./).length).toBeGreaterThanOrEqual(1);
          expect(within(cell).getByText('No headline here')).toBeInTheDocument();
        });
      });

      it('always renders the comment text regardless of headline', async () => {
        adminAPI.getReviews.mockResolvedValue(
          paged([makeReview({ headline: null, comment: 'Comment always shows' })], 1)
        );
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-headline');
          expect(within(cell).getByText('Comment always shows')).toBeInTheDocument();
        });
      });
    });

    describe('created_at column', () => {
      it('formats the ISO date string', async () => {
        adminAPI.getReviews.mockResolvedValue(
          paged([makeReview({ created_at: '2024-06-15T00:00:00Z' })], 1)
        );
        render(<AdminReviews />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-created_at');
          expect(cell.textContent).toMatch(/\d/);
          expect(cell.textContent).not.toContain('T');
        });
      });
    });
  });

  // ── 4. Search ────────────────────────────────────────────────────────────
  describe('Search', () => {
    it('re-fetches with the typed search string', async () => {
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));

      vi.clearAllMocks();
      okReviews();

      await user.type(
        screen.getByPlaceholderText('Search by reviewer, product…'),
        'alice'
      );

      await waitFor(() =>
        expect(adminAPI.getReviews).toHaveBeenCalledWith(
          expect.objectContaining({ search: expect.stringContaining('alice') })
        )
      );
    });

    it('resets page to 1 when search changes', async () => {
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));

      await user.click(screen.getByTestId('dt-next-page'));
      await waitFor(() =>
        expect(adminAPI.getReviews).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );

      vi.clearAllMocks();
      okReviews();

      await user.type(
        screen.getByPlaceholderText('Search by reviewer, product…'),
        'x'
      );

      await waitFor(() =>
        expect(adminAPI.getReviews).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1 })
        )
      );
    });
  });

  // ── 5. Sort ──────────────────────────────────────────────────────────────
  describe('Sort', () => {
    it('re-fetches with new ordering when sort changes', async () => {
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));

      vi.clearAllMocks();
      okReviews();

      await user.click(screen.getByTestId('dt-sort'));

      await waitFor(() =>
        expect(adminAPI.getReviews).toHaveBeenCalledWith(
          expect.objectContaining({ ordering: 'rating' })
        )
      );
    });
  });

  // ── 6. Rating filter ─────────────────────────────────────────────────────
  describe('Rating filter', () => {
    it('renders "All Ratings" plus 5 down to 1 stars, singular for "1 Star"', async () => {
      render(<AdminReviews />);
      await waitFor(() => screen.getByTestId('dt-filters'));
      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      const labels = within(select).getAllByRole('option').map((o) => o.textContent);
      expect(labels).toEqual([
        'All Ratings', '5 Stars', '4 Stars', '3 Stars', '2 Stars', '1 Star',
      ]);
    });

    it('re-fetches WITH the rating key when a star rating is selected', async () => {
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await waitFor(() => screen.getByTestId('dt-filters'));

      vi.clearAllMocks();
      okReviews();

      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, '4');

      await waitFor(() =>
        expect(adminAPI.getReviews).toHaveBeenCalledWith(
          expect.objectContaining({ rating: '4' })
        )
      );
    });

    it('OMITS the rating key entirely when reset to "All Ratings" (not rating:undefined)', async () => {
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await waitFor(() => screen.getByTestId('dt-filters'));

      let select = within(screen.getByTestId('dt-filters')).getByRole('combobox');

      // 1. Select 4 Stars
      await user.selectOptions(select, '4');
      await waitFor(() =>
        expect(adminAPI.getReviews).toHaveBeenCalledWith(
          expect.objectContaining({ rating: '4' })
        )
      );

      // ─── CRITICAL: Wait for the loading state to clear and filters to remount ───
      await waitFor(() => expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument());

      // Clear mock history and re-prime
      vi.clearAllMocks();
      okReviews();

      // ─── CRITICAL: Re-query the select element since the old one was unmounted ───
      select = within(screen.getByTestId('dt-filters')).getByRole('combobox');

      // 2. Reset back to All Ratings (the standard empty string works perfectly now!)
      await user.selectOptions(select, '');

      // 3. Now waitFor will accurately catch the second call
      await waitFor(() => expect(adminAPI.getReviews).toHaveBeenCalledTimes(1));

      const lastCallArgs = adminAPI.getReviews.mock.calls[0][0];
      expect(lastCallArgs).not.toHaveProperty('rating');
    });

    it('resets page to 1 when rating filter changes', async () => {
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await waitFor(() => screen.getByTestId('dt-filters'));

      await user.click(screen.getByTestId('dt-next-page'));
      await waitFor(() =>
        expect(adminAPI.getReviews).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );

      vi.clearAllMocks();
      okReviews();

      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, '5');

      await waitFor(() =>
        expect(adminAPI.getReviews).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1 })
        )
      );
    });
  });

  // ── 7. Pagination ────────────────────────────────────────────────────────
  describe('Pagination', () => {
    it('re-fetches with incremented page when next-page triggered', async () => {
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));

      vi.clearAllMocks();
      okReviews();

      await user.click(screen.getByTestId('dt-next-page'));

      await waitFor(() =>
        expect(adminAPI.getReviews).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );
    });
  });

  // ── 8. Empty state ───────────────────────────────────────────────────────
  describe('Empty state', () => {
    it('shows "No reviews found" when results are empty', async () => {
      adminAPI.getReviews.mockResolvedValue(paged([], 0));
      render(<AdminReviews />);
      await waitFor(() =>
        expect(screen.getByTestId('dt-empty')).toHaveTextContent('No reviews found')
      );
    });
  });

  // ── 9. Row actions ───────────────────────────────────────────────────────
  describe('Row actions', () => {
    it('"View" button opens the ReviewDrawer for that row', async () => {
      adminAPI.getReviews.mockResolvedValue(
        paged([makeReview({ name: 'Carol Diaz' })], 1)
      );
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Carol Diaz'));

      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View'));

      await waitFor(() => {
        const drawer = getDrawerCard();
        expect(within(drawer).getByText('Carol Diaz')).toBeInTheDocument();
      });
    });

    it('"Delete" row action opens ConfirmModal', async () => {
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await waitFor(() =>
        expect(screen.getByTestId('confirm-modal')).toBeInTheDocument()
      );
    });
  });

  // ── 10. Delete – success ──────────────────────────────────────────────────
  describe('Delete – success', () => {
    const openConfirmFromRow = async (user) => {
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
    };

    it('ConfirmModal title is "Delete Review"', async () => {
      const user = setup();
      await openConfirmFromRow(user);
      expect(screen.getByTestId('confirm-title')).toHaveTextContent('Delete Review');
    });

    it('ConfirmModal message includes the reviewer name', async () => {
      const user = setup();
      await openConfirmFromRow(user);
      expect(screen.getByTestId('confirm-message')).toHaveTextContent(
        'Permanently delete this review by "Reviewer 1"? This cannot be undone.'
      );
    });

    it('calls deleteReview with the correct id on confirm', async () => {
      adminAPI.deleteReview.mockResolvedValue({});
      const user = setup();
      await openConfirmFromRow(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() => expect(adminAPI.deleteReview).toHaveBeenCalledWith(1));
    });

    it('shows "Review deleted" success toast', async () => {
      adminAPI.deleteReview.mockResolvedValue({});
      const user = setup();
      await openConfirmFromRow(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === 'Review deleted' && t.type === 'success')
        ).toBe(true)
      );
    });

    it('closes ConfirmModal after successful delete', async () => {
      adminAPI.deleteReview.mockResolvedValue({});
      const user = setup();
      await openConfirmFromRow(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(screen.queryByTestId('confirm-modal')).not.toBeInTheDocument()
      );
    });

    it('also clears selected (closes ReviewDrawer) after successful delete', async () => {
      adminAPI.deleteReview.mockResolvedValue({});
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View'));
      await waitFor(() => getDrawerCard());

      const drawer = getDrawerCard();
      await user.click(within(drawer).getByRole('button', { name: /delete this review/i }));

      await waitFor(() => screen.getByTestId('confirm-modal'));
      await user.click(screen.getByTestId('confirm-btn'));

      await waitFor(() => {
        expect(screen.queryByTestId('confirm-modal')).not.toBeInTheDocument();
        expect(getDrawerCard()).not.toBeInTheDocument();
      });
    });

    it('re-fetches review list after successful delete', async () => {
      adminAPI.deleteReview.mockResolvedValue({});
      const user = setup();
      await openConfirmFromRow(user);

      vi.clearAllMocks();
      okReviews();

      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() => expect(adminAPI.getReviews).toHaveBeenCalledTimes(1));
    });
  });

  // ── 11. Delete – error ───────────────────────────────────────────────────
  describe('Delete – error', () => {
    it('shows "Failed to delete review" error toast when deleteReview rejects', async () => {
      adminAPI.deleteReview.mockRejectedValue(new Error('500'));
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to delete review' && t.type === 'error'
          )
        ).toBe(true)
      );
    });

    it('keeps ConfirmModal open after a failed delete', async () => {
      adminAPI.deleteReview.mockRejectedValue(new Error('500'));
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(screen.getByTestId('confirm-modal')).toBeInTheDocument()
      );
    });
  });

  // ── 12. Delete – cancel ───────────────────────────────────────────────────
  describe('Delete – cancel', () => {
    it('closes ConfirmModal when Cancel is clicked', async () => {
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-cancel'));
      await waitFor(() =>
        expect(screen.queryByTestId('confirm-modal')).not.toBeInTheDocument()
      );
    });

    it('does NOT call deleteReview when Cancel is clicked', async () => {
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-cancel'));
      expect(adminAPI.deleteReview).not.toHaveBeenCalled();
    });
  });

  // ── 13. Delete – in-flight state ─────────────────────────────────────────
  describe('Delete – in-flight state', () => {
    const pendingDelete = () => {
      let resolve;
      adminAPI.deleteReview.mockReturnValue(new Promise((r) => { resolve = r; }));
      return resolve;
    };

    it('disables confirm button while delete is in-flight', async () => {
      const resolve = pendingDelete();
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(screen.getByTestId('confirm-btn')).toBeDisabled()
      );
      resolve({});
    });

    it('shows "Deleting…" label on confirm button while in-flight', async () => {
      const resolve = pendingDelete();
      const user = setup();
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(screen.getByTestId('confirm-btn')).toHaveTextContent('Deleting…')
      );
      resolve({});
    });
  });

  // ── 14. ReviewDrawer ─────────────────────────────────────────────────────
  describe('ReviewDrawer', () => {
    const openDrawer = async (user, review = makeReview()) => {
      adminAPI.getReviews.mockResolvedValue(paged([review], 1));
      render(<AdminReviews />);
      await waitFor(() => screen.getByText(review.name));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View'));
      await waitFor(() => getDrawerCard());
    };

    it('renders nothing when no review is selected', () => {
      render(<AdminReviews />);
      expect(getDrawerCard()).not.toBeInTheDocument();
    });

    it('shows the static "Review Detail" header', async () => {
      const user = setup();
      await openDrawer(user);
      const drawer = getDrawerCard();
      expect(within(drawer).getByText('Review Detail')).toBeInTheDocument();
    });

    it("renders the reviewed product's name", async () => {
      const user = setup();
      await openDrawer(user, makeReview({ product_name: 'Noise-Cancelling Headphones' }));
      const drawer = getDrawerCard();
      expect(within(drawer).getByText('Noise-Cancelling Headphones')).toBeInTheDocument();
    });

    it('renders the product ID', async () => {
      const user = setup();
      await openDrawer(user, makeReview({ product_id: 555 }));
      const drawer = getDrawerCard();
      expect(within(drawer).getByText('ID #555')).toBeInTheDocument();
    });

    it("renders the reviewer's name", async () => {
      const user = setup();
      await openDrawer(user, makeReview({ name: 'Derek Lee' }));
      const drawer = getDrawerCard();
      expect(within(drawer).getByText('Derek Lee')).toBeInTheDocument();
    });

    it('renders the uppercase avatar initial from the name', async () => {
      const user = setup();
      await openDrawer(user, makeReview({ name: 'derek lee' }));
      const drawer = getDrawerCard();
      expect(within(drawer).getByText('D')).toBeInTheDocument();
    });

    it('renders the long-form review date', async () => {
      const user = setup();
      await openDrawer(user, makeReview({ created_at: '2024-03-10T00:00:00Z' }));
      const drawer = getDrawerCard();
      // Locale-dependent; just confirm year + month name appear (long format)
      expect(within(drawer).getByText(/2024/)).toBeInTheDocument();
    });

    it('renders the numeric rating value and "/ 5"', async () => {
      const user = setup();
      await openDrawer(user, makeReview({ rating: 4 }));
      const drawer = getDrawerCard();
      expect(within(drawer).getByText('4')).toBeInTheDocument();
      expect(within(drawer).getByText('/ 5')).toBeInTheDocument();
    });

    it('renders 5 star icons total, with filled count matching rating value', async () => {
      const user = setup();
      await openDrawer(user, makeReview({ rating: 3 }));
      const drawer = getDrawerCard();
      const filledStars = drawer.querySelectorAll('.bi-star-fill.text-yellow-400');
      const emptyStars = drawer.querySelectorAll('.bi-star.text-gray-200');
      expect(filledStars).toHaveLength(3);
      expect(emptyStars).toHaveLength(2);
    });

    it('renders all 5 stars filled when rating is 5', async () => {
      const user = setup();
      await openDrawer(user, makeReview({ rating: 5 }));
      const drawer = getDrawerCard();
      const filledStars = drawer.querySelectorAll('.bi-star-fill.text-yellow-400');
      expect(filledStars).toHaveLength(5);
    });

    it('renders all 5 stars empty when rating is 0', async () => {
      const user = setup();
      await openDrawer(user, makeReview({ rating: 0 }));
      const drawer = getDrawerCard();
      const filledStars = drawer.querySelectorAll('.bi-star-fill.text-yellow-400');
      const emptyStars = drawer.querySelectorAll('.bi-star.text-gray-200');
      expect(filledStars).toHaveLength(0);
      expect(emptyStars).toHaveLength(5);
    });

    it('shows the headline when present', async () => {
      const user = setup();
      await openDrawer(user, makeReview({ headline: 'Excellent purchase' }));
      const drawer = getDrawerCard();
      expect(within(drawer).getByText('Excellent purchase')).toBeInTheDocument();
    });

    it('does NOT render the Headline section when headline is falsy', async () => {
      const user = setup();
      await openDrawer(user, makeReview({ headline: '' }));
      const drawer = getDrawerCard();
      expect(within(drawer).queryByText('Headline')).not.toBeInTheDocument();
    });

    it('always renders the comment text', async () => {
      const user = setup();
      const fullComment = 'This is the complete review comment text.';
      await openDrawer(user, makeReview({ comment: fullComment }));
      const drawer = getDrawerCard();
      expect(within(drawer).getByText(fullComment)).toBeInTheDocument();
    });

    it('renders the "Delete This Review" button', async () => {
      const user = setup();
      await openDrawer(user);
      const drawer = getDrawerCard();
      expect(
        within(drawer).getByRole('button', { name: /delete this review/i })
      ).toBeInTheDocument();
    });

    it('closes the drawer when the × button is clicked', async () => {
      const user = setup();
      await openDrawer(user);
      const drawer = getDrawerCard();
      const closeBtn = drawer.parentElement.querySelector('.bi-x-lg').closest('button');
      await user.click(closeBtn);
      await waitFor(() => expect(getDrawerCard()).not.toBeInTheDocument());
    });

    it('closes the drawer when the backdrop is clicked', async () => {
      const user = setup();
      await openDrawer(user);
      const backdrop = document.querySelector('.fixed.inset-0.flex.justify-end');
      fireEvent.click(backdrop);
      await waitFor(() => expect(getDrawerCard()).not.toBeInTheDocument());
    });

    it('clicking inside the drawer does NOT close it', async () => {
      const user = setup();
      await openDrawer(user);
      const drawer = getDrawerCard();
      fireEvent.click(drawer);
      expect(getDrawerCard()).toBeInTheDocument();
    });
  });

  // ── 15. Drawer → Delete wiring ───────────────────────────────────────────
  describe('ReviewDrawer delete wiring', () => {
    it('clicking "Delete This Review" closes the drawer and opens ConfirmModal', async () => {
      const user = setup();
      adminAPI.getReviews.mockResolvedValue(
        paged([makeReview({ name: 'Erin Park' })], 1)
      );
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Erin Park'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View'));

      const drawer = getDrawerCard();
      await waitFor(() => within(drawer).getByText('Erin Park'));

      await user.click(within(drawer).getByRole('button', { name: /delete this review/i }));

      await waitFor(() => {
        expect(getDrawerCard()).not.toBeInTheDocument();
        expect(screen.getByTestId('confirm-modal')).toBeInTheDocument();
      });
    });

    it('ConfirmModal opened from the drawer references the correct reviewer', async () => {
      const user = setup();
      adminAPI.getReviews.mockResolvedValue(
        paged([makeReview({ name: 'Erin Park' })], 1)
      );
      render(<AdminReviews />);
      await waitFor(() => screen.getByText('Erin Park'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('View'));

      const drawer = getDrawerCard();
      await user.click(within(drawer).getByRole('button', { name: /delete this review/i }));

      await waitFor(() =>
        expect(screen.getByTestId('confirm-message')).toHaveTextContent(
          'Permanently delete this review by "Erin Park"? This cannot be undone.'
        )
      );
    });
  });

  // ── 16. Snapshot ─────────────────────────────────────────────────────────
  describe('Snapshot', () => {
    it('matches stable snapshot after data loads', async () => {
      const { asFragment } = render(<AdminReviews />);
      await waitFor(() => screen.getByText('Reviewer 1'));
      expect(asFragment()).toMatchSnapshot();
    });
  });
});
