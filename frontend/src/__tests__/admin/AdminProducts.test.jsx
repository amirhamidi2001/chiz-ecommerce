/**
 * AdminProducts.test.jsx
 *
 * Comprehensive unit & integration tests for AdminProducts.jsx
 * Stack : Vitest · React Testing Library · @testing-library/user-event v14
 *
 * ── Coverage map ──────────────────────────────────────────────────────────────
 *  1.  Page structure         – heading, "{total} total products" subtitle,
 *                               "Add Product" button
 *  2.  Mount-only fetches      – getCategories/getBrands called ONCE on mount
 *                               with page_size:100, independent of page/search/
 *                               sort/catFilter changes, errors silently swallowed
 *  3.  fetchProducts          – mount params (category:undefined when filter
 *                               empty), count ?? 0 fallback, loading state,
 *                               paginated & flat response shapes, error toast
 *  4.  Column renderers       – thumbnail_url fallback image + alt=name, name +
 *                               category/brand subtitle, price + conditional
 *                               strikethrough original_price, stock 3-way
 *                               (Out/Low/raw + colour), rating toFixed(1) +
 *                               reviews_count, is_new/is_sale badges (both/
 *                               either/neither)
 *  5.  Search                 – re-fetch w/ search param, page reset to 1
 *  6.  Sort                   – re-fetch w/ new ordering
 *  7.  Category filter        – re-fetch w/ category, empty → undefined (not
 *                               ""), page reset to 1, options from categories
 *                               state
 *  8.  Pagination             – re-fetch w/ new page
 *  9.  Empty state            – "No products found"
 * 10.  Delete – success/error/cancel/in-flight
 * 11.  ProductModal (new)     – heading, submit label, default stock=0 (not
 *                               empty string), validation (name/price/category
 *                               required; others optional), per-field error
 *                               clearing, FormData includes ALL form keys
 *                               (incl. booleans), thumbnail omitted when no
 *                               file, createProduct call, onSaved+onClose,
 *                               re-fetch, "Product saved" toast, API error
 *                               object spread into errors, saving state,
 *                               backdrop/×/Cancel close, category/brand select
 *                               options
 * 12.  ProductModal (edit)    – heading, "Save Changes" label, all fields
 *                               pre-filled, thumbnail preview pre-filled,
 *                               updateProduct(id, FormData), no createProduct
 * 13.  Thumbnail upload       – preview shown, createObjectURL called
 * 14.  Checkbox toggles       – is_new/is_sale default false, toggle updates
 *                               form state, included as "true"/"false" string
 *                               in FormData
 * 15.  Snapshot               – stable rendered output after data loads
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * ── Design notes ──────────────────────────────────────────────────────────────
 * • categories/brands load via a SEPARATE useEffect with an empty dependency
 *   array — they fire exactly once regardless of page/search/sort/catFilter
 *   changes. Tests explicitly assert call count stays at 1 after triggering
 *   multiple fetchProducts re-fetches, to lock in this independence.
 * • Labels in ProductModal/Field have no htmlFor — every field is queried via
 *   `querySelector('[name="..."]')` scoped to the modal card, mirroring the
 *   fix pattern established for AdminBlog/AdminBrands/AdminCategories.
 * • "Edit" / "Delete" / "Add Product" header button text can collide with
 *   modal heading text ("Add New Product" contains "Add Product" as a
 *   substring is NOT true here, but to be safe all modal-open assertions use
 *   getByRole('heading', ...) rather than getByText, and all submit clicks
 *   are scoped via within(getModalCard()).
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
import AdminProducts from '../../pages/admin/AdminProducts';

// ─── jsdom stubs ──────────────────────────────────────────────────────────────
global.URL.createObjectURL = vi.fn(() => 'blob:mock-thumb-url');
global.URL.revokeObjectURL = vi.fn();

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
        <button data-testid="dt-sort" onClick={() => onSort?.('price')}>
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
    getProducts: vi.fn(),
    createProduct: vi.fn(),
    updateProduct: vi.fn(),
    deleteProduct: vi.fn(),
    getCategories: vi.fn(),
    getBrands: vi.fn(),
  },
}));
import { adminAPI } from '../../services/api';

// ─── Fixture factories ────────────────────────────────────────────────────────
const makeProduct = (overrides = {}) => ({
  id: 1,
  name: 'Wireless Mouse',
  category: 10,
  category_name: 'Electronics',
  brand: 20,
  brand_name: 'Logitech',
  price: 29.99,
  original_price: null,
  stock: 50,
  rating: 4.3,
  reviews_count: 12,
  is_new: false,
  is_sale: false,
  thumbnail_url: null,
  short_description: '',
  description: '',
  ...overrides,
});

const makeProducts = (n = 3) =>
  Array.from({ length: n }, (_, i) => ({
    id: i + 1,
    name: `Product ${i + 1}`,
    category: 10,
    category_name: 'Electronics',
    brand: 20,
    brand_name: 'Logitech',
    price: (i + 1) * 10,
    original_price: null,
    stock: 50,
    rating: 4.0,
    reviews_count: 5,
    is_new: false,
    is_sale: false,
    thumbnail_url: null,
  }));

const makeCategories = (n = 2) =>
  Array.from({ length: n }, (_, i) => ({ id: i + 10, name: `Category ${i + 1}` }));

const makeBrands = (n = 2) =>
  Array.from({ length: n }, (_, i) => ({ id: i + 20, name: `Brand ${i + 1}` }));

const paged = (results, count) => ({ data: { results, count } });
const flat = (arr) => ({ data: arr });

const okProducts = (products = makeProducts()) =>
  adminAPI.getProducts.mockResolvedValue(paged(products, products.length));
const okCategories = (cats = makeCategories()) =>
  adminAPI.getCategories.mockResolvedValue(paged(cats, cats.length));
const okBrands = (brands = makeBrands()) =>
  adminAPI.getBrands.mockResolvedValue(paged(brands, brands.length));

const setup = () => userEvent.setup();

/** The inner modal card (stops propagation on click). */
const getModalCard = () => document.querySelector('.fixed.inset-0 .rounded-2xl');

/** Field getters scoped to the modal — labels have no htmlFor. */
const getField = (name) => getModalCard()?.querySelector(`[name="${name}"]`);

// ─────────────────────────────────────────────────────────────────────────────

describe('AdminProducts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedToasts = [];
    okProducts();
    okCategories();
    okBrands();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. Page structure ────────────────────────────────────────────────────
  describe('Page structure', () => {
    it('renders the "Products" heading', () => {
      render(<AdminProducts />);
      expect(screen.getByRole('heading', { name: /^products$/i })).toBeInTheDocument();
    });

    it('shows "{total} total products" subtitle after data loads', async () => {
      okProducts(makeProducts(9));
      render(<AdminProducts />);
      await waitFor(() =>
        expect(screen.getByText('9 total products')).toBeInTheDocument()
      );
    });

    it('renders the "Add Product" button', () => {
      render(<AdminProducts />);
      expect(screen.getByRole('button', { name: /add product/i })).toBeInTheDocument();
    });
  });

  // ── 2. Mount-only fetches (categories/brands) ────────────────────────────
  describe('Mount-only categories/brands fetches', () => {
    it('calls getCategories once on mount with page_size:100', async () => {
      render(<AdminProducts />);
      await waitFor(() =>
        expect(adminAPI.getCategories).toHaveBeenCalledWith({ page_size: 100 })
      );
      expect(adminAPI.getCategories).toHaveBeenCalledTimes(1);
    });

    it('calls getBrands once on mount with page_size:100', async () => {
      render(<AdminProducts />);
      await waitFor(() =>
        expect(adminAPI.getBrands).toHaveBeenCalledWith({ page_size: 100 })
      );
      expect(adminAPI.getBrands).toHaveBeenCalledTimes(1);
    });

    it('does NOT re-fetch categories/brands when page/search/sort/catFilter change', async () => {
      const user = setup();
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));
      await waitFor(() => expect(adminAPI.getCategories).toHaveBeenCalledTimes(1));

      // Trigger several fetchProducts re-fetches
      await user.click(screen.getByTestId('dt-next-page'));
      await waitFor(() => expect(adminAPI.getProducts).toHaveBeenCalledTimes(2));
      await user.click(screen.getByTestId('dt-sort'));
      await waitFor(() => expect(adminAPI.getProducts).toHaveBeenCalledTimes(3));
      await user.type(screen.getByPlaceholderText('Search products…'), 'x');
      await waitFor(() => expect(adminAPI.getProducts).toHaveBeenCalledTimes(4));

      // categories/brands should still have been called exactly once
      expect(adminAPI.getCategories).toHaveBeenCalledTimes(1);
      expect(adminAPI.getBrands).toHaveBeenCalledTimes(1);
    });

    it('does not crash when getCategories rejects (error silently swallowed)', async () => {
      adminAPI.getCategories.mockRejectedValue(new Error('net'));
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('does not crash when getBrands rejects (error silently swallowed)', async () => {
      adminAPI.getBrands.mockRejectedValue(new Error('net'));
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('handles a flat (non-paginated) categories response', async () => {
      adminAPI.getCategories.mockResolvedValue(flat(makeCategories(3)));
      const user = setup();
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));
      await waitFor(() => screen.getByTestId('dt-filters'));
      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      const opts = within(select).getAllByRole('option').map((o) => o.textContent);
      expect(opts).toContain('Category 1');
      expect(opts).toContain('Category 3');
    });
  });

  // ── 3. fetchProducts ──────────────────────────────────────────────────────
  describe('fetchProducts – initial fetch', () => {
    it('calls getProducts on mount with category:undefined when no filter set', async () => {
      render(<AdminProducts />);
      await waitFor(() =>
        expect(adminAPI.getProducts).toHaveBeenCalledWith({
          page: 1,
          search: '',
          ordering: '-created_at',
          category: undefined,
          page_size: 10,
        })
      );
    });

    it('shows loading indicator while fetch is in-flight', () => {
      adminAPI.getProducts.mockReturnValue(new Promise(() => { }));
      render(<AdminProducts />);
      expect(screen.getByTestId('dt-loading')).toBeInTheDocument();
    });

    it('clears loading state after data resolves', async () => {
      render(<AdminProducts />);
      await waitFor(() =>
        expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument()
      );
    });

    it('clears loading state even after API error', async () => {
      adminAPI.getProducts.mockRejectedValue(new Error('net'));
      render(<AdminProducts />);
      await waitFor(() =>
        expect(screen.queryByTestId('dt-loading')).not.toBeInTheDocument()
      );
    });

    it('renders product rows from a paginated response', async () => {
      render(<AdminProducts />);
      await waitFor(() => {
        expect(screen.getByText('Product 1')).toBeInTheDocument();
        expect(screen.getByText('Product 2')).toBeInTheDocument();
        expect(screen.getByText('Product 3')).toBeInTheDocument();
      });
    });

    it('handles a flat (non-paginated) array response', async () => {
      adminAPI.getProducts.mockResolvedValue(flat(makeProducts(2)));
      render(<AdminProducts />);
      await waitFor(() => {
        expect(screen.getByText('Product 1')).toBeInTheDocument();
        expect(screen.getByText('Product 2')).toBeInTheDocument();
      });
    });

    it('falls back total to 0 for flat-array response (not array length)', async () => {
      adminAPI.getProducts.mockResolvedValue(flat(makeProducts(5)));
      render(<AdminProducts />);
      await waitFor(() =>
        expect(screen.getByText('0 total products')).toBeInTheDocument()
      );
    });

    it('sets total from paginated count field', async () => {
      adminAPI.getProducts.mockResolvedValue(paged(makeProducts(3), 73));
      render(<AdminProducts />);
      await waitFor(() =>
        expect(screen.getByText('73 total products')).toBeInTheDocument()
      );
    });

    it('shows "Failed to load products" error toast on API failure', async () => {
      adminAPI.getProducts.mockRejectedValue(new Error('net'));
      render(<AdminProducts />);
      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to load products' && t.type === 'error'
          )
        ).toBe(true)
      );
    });
  });

  // ── 4. Column renderers ──────────────────────────────────────────────────
  describe('Column renderers', () => {
    describe('thumbnail_url column', () => {
      it('renders the product image when thumbnail_url is set', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ thumbnail_url: 'https://cdn.test/mouse.jpg', name: 'Mouse' })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const img = screen.getByRole('img', { name: 'Mouse' });
          expect(img).toHaveAttribute('src', 'https://cdn.test/mouse.jpg');
        });
      });

      it('falls back to the default placeholder image when thumbnail_url is null', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ thumbnail_url: null, name: 'Keyboard' })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const img = screen.getByRole('img', { name: 'Keyboard' });
          expect(img).toHaveAttribute('src', '/assets/img/product/product-1.webp');
        });
      });
    });

    describe('name column', () => {
      it('renders product name and category/brand subtitle', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ name: 'Gaming Chair', category_name: 'Furniture', brand_name: 'Herman Miller' })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-name');
          expect(within(cell).getByText('Gaming Chair')).toBeInTheDocument();
          expect(within(cell).getByText('Furniture · Herman Miller')).toBeInTheDocument();
        });
      });
    });

    describe('price column', () => {
      it('renders the formatted price', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ price: 49.5 })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-price');
          expect(within(cell).getByText('$49.50')).toBeInTheDocument();
        });
      });

      it('shows the strikethrough original_price when present', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ price: 39.99, original_price: 59.99 })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-price');
          const original = within(cell).getByText('$59.99');
          expect(original.className).toMatch(/line-through/);
        });
      });

      it('does NOT show original_price when it is null', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ price: 39.99, original_price: null })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-price');
          expect(within(cell).queryByText(/line-through/)).not.toBeInTheDocument();
          // only one price element rendered
          expect(within(cell).getAllByText(/^\$/)).toHaveLength(1);
        });
      });
    });

    describe('stock column', () => {
      it('shows "Out" with red styling when stock is 0', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ stock: 0 })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-stock');
          const badge = within(cell).getByText('Out');
          expect(badge.className).toMatch(/bg-red-100/);
        });
      });

      it('shows "Low (N)" with amber styling when 0 < stock <= 5', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ stock: 3 })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-stock');
          const badge = within(cell).getByText('Low (3)');
          expect(badge.className).toMatch(/bg-amber-100/);
        });
      });

      it('shows the raw stock number with green styling when stock > 5', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ stock: 42 })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-stock');
          const badge = within(cell).getByText('42');
          expect(badge.className).toMatch(/bg-green-100/);
        });
      });

      it('boundary: stock=5 is treated as "Low", not raw', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ stock: 5 })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-stock');
          expect(within(cell).getByText('Low (5)')).toBeInTheDocument();
        });
      });

      it('boundary: stock=6 is treated as raw green, not "Low"', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ stock: 6 })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-stock');
          expect(within(cell).getByText('6')).toBeInTheDocument();
          expect(within(cell).queryByText(/Low/)).not.toBeInTheDocument();
        });
      });
    });

    describe('rating column', () => {
      it('renders rating to one decimal place', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ rating: 4.567 })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-rating');
          expect(within(cell).getByText('4.6')).toBeInTheDocument();
        });
      });

      it('renders "0.0" when rating is null', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ rating: null })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-rating');
          expect(within(cell).getByText('0.0')).toBeInTheDocument();
        });
      });

      it('renders reviews_count in parentheses', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ reviews_count: 27 })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-rating');
          expect(within(cell).getByText('(27)')).toBeInTheDocument();
        });
      });
    });

    describe('badges column (is_sale key, renders is_new + is_sale)', () => {
      it('renders "New" badge when is_new is true', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ is_new: true, is_sale: false })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-is_sale');
          expect(within(cell).getByText('New')).toBeInTheDocument();
          expect(within(cell).queryByText('Sale')).not.toBeInTheDocument();
        });
      });

      it('renders "Sale" badge when is_sale is true', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ is_new: false, is_sale: true })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-is_sale');
          expect(within(cell).getByText('Sale')).toBeInTheDocument();
          expect(within(cell).queryByText('New')).not.toBeInTheDocument();
        });
      });

      it('renders BOTH badges when is_new and is_sale are both true', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ is_new: true, is_sale: true })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-is_sale');
          expect(within(cell).getByText('New')).toBeInTheDocument();
          expect(within(cell).getByText('Sale')).toBeInTheDocument();
        });
      });

      it('renders NEITHER badge when both are false', async () => {
        adminAPI.getProducts.mockResolvedValue(
          paged([makeProduct({ is_new: false, is_sale: false })], 1)
        );
        render(<AdminProducts />);
        await waitFor(() => {
          const cell = screen.getByTestId('cell-is_sale');
          expect(within(cell).queryByText('New')).not.toBeInTheDocument();
          expect(within(cell).queryByText('Sale')).not.toBeInTheDocument();
        });
      });
    });
  });

  // ── 5. Search ────────────────────────────────────────────────────────────
  describe('Search', () => {
    it('re-fetches with the typed search string', async () => {
      const user = setup();
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));

      vi.clearAllMocks();
      okProducts();

      await user.type(screen.getByPlaceholderText('Search products…'), 'mouse');

      await waitFor(() =>
        expect(adminAPI.getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ search: expect.stringContaining('mouse') })
        )
      );
    });

    it('resets page to 1 when search changes', async () => {
      const user = setup();
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));

      await user.click(screen.getByTestId('dt-next-page'));
      await waitFor(() =>
        expect(adminAPI.getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );

      vi.clearAllMocks();
      okProducts();

      await user.type(screen.getByPlaceholderText('Search products…'), 'x');

      await waitFor(() =>
        expect(adminAPI.getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1 })
        )
      );
    });
  });

  // ── 6. Sort ──────────────────────────────────────────────────────────────
  describe('Sort', () => {
    it('re-fetches with new ordering when sort changes', async () => {
      const user = setup();
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));

      vi.clearAllMocks();
      okProducts();

      await user.click(screen.getByTestId('dt-sort'));

      await waitFor(() =>
        expect(adminAPI.getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ ordering: 'price' })
        )
      );
    });
  });

  // ── 7. Category filter ───────────────────────────────────────────────────
  describe('Category filter', () => {
    it('renders the category filter select with "All Categories" + loaded categories', async () => {
      render(<AdminProducts />);
      await waitFor(() => screen.getByTestId('dt-filters'));
      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      const opts = within(select).getAllByRole('option').map((o) => o.textContent);
      expect(opts).toEqual(['All Categories', 'Category 1', 'Category 2']);
    });

    it('re-fetches with the selected category id', async () => {
      const user = setup();
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));
      await waitFor(() => screen.getByTestId('dt-filters'));

      vi.clearAllMocks();
      okProducts();

      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, '10');

      await waitFor(() =>
        expect(adminAPI.getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ category: '10' })
        )
      );
    });

    it('passes category:undefined (not empty string) when reset to "All Categories"', async () => {
      const user = setup();
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));
      await waitFor(() => screen.getByTestId('dt-filters'));

      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, '10');
      await waitFor(() =>
        expect(adminAPI.getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ category: '10' })
        )
      );

      vi.clearAllMocks();
      okProducts();

      await user.selectOptions(select, '');
      await waitFor(() =>
        expect(adminAPI.getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ category: undefined })
        )
      );
    });

    it('resets page to 1 when category filter changes', async () => {
      const user = setup();
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));
      await waitFor(() => screen.getByTestId('dt-filters'));

      await user.click(screen.getByTestId('dt-next-page'));
      await waitFor(() =>
        expect(adminAPI.getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );

      vi.clearAllMocks();
      okProducts();

      const select = within(screen.getByTestId('dt-filters')).getByRole('combobox');
      await user.selectOptions(select, '11');

      await waitFor(() =>
        expect(adminAPI.getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1 })
        )
      );
    });
  });

  // ── 8. Pagination ────────────────────────────────────────────────────────
  describe('Pagination', () => {
    it('re-fetches with incremented page when next-page triggered', async () => {
      const user = setup();
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));

      vi.clearAllMocks();
      okProducts();

      await user.click(screen.getByTestId('dt-next-page'));

      await waitFor(() =>
        expect(adminAPI.getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        )
      );
    });
  });

  // ── 9. Empty state ───────────────────────────────────────────────────────
  describe('Empty state', () => {
    it('shows "No products found" when results are empty', async () => {
      adminAPI.getProducts.mockResolvedValue(paged([], 0));
      render(<AdminProducts />);
      await waitFor(() =>
        expect(screen.getByTestId('dt-empty')).toHaveTextContent('No products found')
      );
    });
  });

  // ── 10. Delete flow ──────────────────────────────────────────────────────
  describe('Delete – product', () => {
    const openConfirm = async (user) => {
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Delete'));
    };

    it('opens ConfirmModal with the product name in the message', async () => {
      const user = setup();
      await openConfirm(user);
      expect(screen.getByTestId('confirm-message')).toHaveTextContent(
        'Delete "Product 1"? This action cannot be undone.'
      );
    });

    it('calls deleteProduct with the correct id on confirm', async () => {
      adminAPI.deleteProduct.mockResolvedValue({});
      const user = setup();
      await openConfirm(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() => expect(adminAPI.deleteProduct).toHaveBeenCalledWith(1));
    });

    it('shows "Product deleted" success toast', async () => {
      adminAPI.deleteProduct.mockResolvedValue({});
      const user = setup();
      await openConfirm(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(
          capturedToasts.some((t) => t.message === 'Product deleted' && t.type === 'success')
        ).toBe(true)
      );
    });

    it('closes ConfirmModal after successful delete', async () => {
      adminAPI.deleteProduct.mockResolvedValue({});
      const user = setup();
      await openConfirm(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(screen.queryByTestId('confirm-modal')).not.toBeInTheDocument()
      );
    });

    it('re-fetches product list after successful delete', async () => {
      adminAPI.deleteProduct.mockResolvedValue({});
      const user = setup();
      await openConfirm(user);

      vi.clearAllMocks();
      okProducts();

      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() => expect(adminAPI.getProducts).toHaveBeenCalledTimes(1));
    });

    it('shows "Failed to delete product" error toast on rejection', async () => {
      adminAPI.deleteProduct.mockRejectedValue(new Error('500'));
      const user = setup();
      await openConfirm(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(
          capturedToasts.some(
            (t) => t.message === 'Failed to delete product' && t.type === 'error'
          )
        ).toBe(true)
      );
    });

    it('keeps ConfirmModal open after a failed delete', async () => {
      adminAPI.deleteProduct.mockRejectedValue(new Error('500'));
      const user = setup();
      await openConfirm(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() =>
        expect(screen.getByTestId('confirm-modal')).toBeInTheDocument()
      );
    });

    it('closes ConfirmModal on Cancel without calling deleteProduct', async () => {
      const user = setup();
      await openConfirm(user);
      await user.click(screen.getByTestId('confirm-cancel'));
      expect(adminAPI.deleteProduct).not.toHaveBeenCalled();
      await waitFor(() =>
        expect(screen.queryByTestId('confirm-modal')).not.toBeInTheDocument()
      );
    });

    it('disables confirm button and shows "Deleting…" while in-flight', async () => {
      let resolve;
      adminAPI.deleteProduct.mockReturnValue(new Promise((r) => { resolve = r; }));
      const user = setup();
      await openConfirm(user);
      await user.click(screen.getByTestId('confirm-btn'));
      await waitFor(() => {
        const btn = screen.getByTestId('confirm-btn');
        expect(btn).toBeDisabled();
        expect(btn).toHaveTextContent('Deleting…');
      });
      resolve({});
    });
  });

  // ── 11. ProductModal – new product ───────────────────────────────────────
  describe('ProductModal – new product', () => {
    const openNew = async (user) => {
      render(<AdminProducts />);
      await waitFor(() =>
        expect(screen.getByRole('button', { name: /add product/i })).toBeInTheDocument()
      );
      await user.click(screen.getByRole('button', { name: /add product/i }));
      await waitFor(() =>
        expect(screen.getByRole('heading', { name: /add new product/i })).toBeInTheDocument()
      );
    };

    it('opens with "Add New Product" heading', async () => {
      const user = setup();
      await openNew(user);
      expect(screen.getByRole('heading', { name: /add new product/i })).toBeInTheDocument();
    });

    it('submit button label is "Add Product"', async () => {
      const user = setup();
      await openNew(user);
      expect(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      ).toBeInTheDocument();
    });

    it('stock field defaults to 0 (not empty string)', async () => {
      const user = setup();
      await openNew(user);
      expect(getField('stock')).toHaveValue(0);
    });

    it('name, price, category fields start empty', async () => {
      const user = setup();
      await openNew(user);
      expect(getField('name')).toHaveValue('');
      expect(getField('price')).toHaveValue(null);
      expect(getField('category')).toHaveValue('');
    });

    it('category select includes all loaded categories', async () => {
      const user = setup();
      await openNew(user);
      const select = getField('category');
      const opts = within(select).getAllByRole('option').map((o) => o.textContent);
      expect(opts).toEqual(['Select…', 'Category 1', 'Category 2']);
    });

    it('brand select includes all loaded brands', async () => {
      const user = setup();
      await openNew(user);
      const select = getField('brand');
      const opts = within(select).getAllByRole('option').map((o) => o.textContent);
      expect(opts).toEqual(['Select…', 'Brand 1', 'Brand 2']);
    });

    // ── Validation ──────────────────────────────────────────────────────────
    it('shows "Required" for name, price, and category when submitted empty', async () => {
      const user = setup();
      await openNew(user);
      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );
      await waitFor(() => {
        const errors = screen.getAllByText('Required');
        expect(errors).toHaveLength(3); // name, price, category
      });
    });

    it('does NOT require brand, original_price, or descriptions', async () => {
      adminAPI.createProduct.mockResolvedValue({ data: {} });
      const user = setup();
      await openNew(user);
      await user.type(getField('name'), 'New Widget');
      await user.type(getField('price'), '19.99');
      await user.selectOptions(getField('category'), '10');
      // leave brand, original_price, descriptions empty
      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );
      await waitFor(() => expect(adminAPI.createProduct).toHaveBeenCalled());
    });

    it('does NOT call createProduct when validation fails', async () => {
      const user = setup();
      await openNew(user);
      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );
      expect(adminAPI.createProduct).not.toHaveBeenCalled();
    });

    it('clears the name error specifically when the name field changes', async () => {
      const user = setup();
      await openNew(user);
      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );
      await waitFor(() => expect(screen.getAllByText('Required')).toHaveLength(3));

      await user.type(getField('name'), 'X');

      // name error cleared, but price/category errors remain
      await waitFor(() => expect(screen.getAllByText('Required')).toHaveLength(2));
    });

    // ── Successful create ──────────────────────────────────────────────────
    it('calls createProduct with FormData containing all form fields', async () => {
      adminAPI.createProduct.mockResolvedValue({ data: {} });
      const user = setup();
      await openNew(user);

      await user.type(getField('name'), 'Test Widget');
      await user.type(getField('price'), '15.5');
      await user.selectOptions(getField('category'), '10');

      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );

      await waitFor(() => {
        expect(adminAPI.createProduct).toHaveBeenCalledWith(expect.any(FormData));
        const fd = adminAPI.createProduct.mock.calls[0][0];
        expect(fd.get('name')).toBe('Test Widget');
        expect(fd.get('price')).toBe('15.5');
        expect(fd.get('category')).toBe('10');
        // booleans appended too
        expect(fd.get('is_new')).toBe('false');
        expect(fd.get('is_sale')).toBe('false');
      });
    });

    it('does NOT append thumbnail to FormData when no file is selected', async () => {
      adminAPI.createProduct.mockResolvedValue({ data: {} });
      const appendSpy = vi.spyOn(FormData.prototype, 'append');
      const user = setup();
      await openNew(user);

      await user.type(getField('name'), 'No Thumb');
      await user.type(getField('price'), '10');
      await user.selectOptions(getField('category'), '10');
      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );

      await waitFor(() => expect(adminAPI.createProduct).toHaveBeenCalled());
      const thumbCalls = appendSpy.mock.calls.filter(([k]) => k === 'thumbnail');
      expect(thumbCalls).toHaveLength(0);
    });

    it('closes modal and shows "Product saved" toast after successful create', async () => {
      adminAPI.createProduct.mockResolvedValue({ data: {} });
      const user = setup();
      await openNew(user);

      await user.type(getField('name'), 'Test Widget');
      await user.type(getField('price'), '15.5');
      await user.selectOptions(getField('category'), '10');

      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );

      await waitFor(() => {
        expect(screen.queryByRole('heading', { name: /add new product/i })).not.toBeInTheDocument();
        expect(capturedToasts.some((t) => t.message === 'Product saved')).toBe(true);
      });
    });

    it('re-fetches the product list after successful create', async () => {
      adminAPI.createProduct.mockResolvedValue({ data: {} });
      const user = setup();
      await openNew(user);

      await user.type(getField('name'), 'Test Widget');
      await user.type(getField('price'), '15.5');
      await user.selectOptions(getField('category'), '10');

      vi.clearAllMocks();
      okProducts();

      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );

      await waitFor(() => expect(adminAPI.getProducts).toHaveBeenCalledTimes(1));
    });

    // ── API error path ──────────────────────────────────────────────────────
    it('spreads API error response.data into errors and displays field message', async () => {
      adminAPI.createProduct.mockRejectedValue({
        response: { data: { name: 'A product with this name already exists.' } },
      });
      const user = setup();
      await openNew(user);

      await user.type(getField('name'), 'Duplicate');
      await user.type(getField('price'), '15.5');
      await user.selectOptions(getField('category'), '10');
      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );

      await waitFor(() =>
        expect(
          screen.getByText('A product with this name already exists.')
        ).toBeInTheDocument()
      );
    });

    // ── Saving state ────────────────────────────────────────────────────────
    it('disables submit button and shows "Saving…" while in-flight', async () => {
      let resolve;
      adminAPI.createProduct.mockReturnValue(new Promise((r) => { resolve = r; }));
      const user = setup();
      await openNew(user);

      await user.type(getField('name'), 'Pending Product');
      await user.type(getField('price'), '10');
      await user.selectOptions(getField('category'), '10');
      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );

      await waitFor(() =>
        expect(
          within(getModalCard()).getByRole('button', { name: /saving…/i })
        ).toBeDisabled()
      );

      resolve({ data: {} });
    });

    // ── Close behaviours ────────────────────────────────────────────────────
    it('closes modal when backdrop is clicked', async () => {
      const user = setup();
      await openNew(user);
      fireEvent.click(document.querySelector('.fixed.inset-0'));
      await waitFor(() =>
        expect(screen.queryByRole('heading', { name: /add new product/i })).not.toBeInTheDocument()
      );
    });

    it('clicking inside the modal card does NOT close it', async () => {
      const user = setup();
      await openNew(user);
      fireEvent.click(getModalCard());
      expect(screen.getByRole('heading', { name: /add new product/i })).toBeInTheDocument();
    });

    it('closes modal when Cancel is clicked', async () => {
      const user = setup();
      await openNew(user);
      await user.click(within(getModalCard()).getByRole('button', { name: /^cancel$/i }));
      await waitFor(() =>
        expect(screen.queryByRole('heading', { name: /add new product/i })).not.toBeInTheDocument()
      );
    });

    it('closes modal when × icon button is clicked', async () => {
      const user = setup();
      await openNew(user);
      const closeBtn = getModalCard().querySelector('.bi-x-lg').closest('button');
      await user.click(closeBtn);
      await waitFor(() =>
        expect(screen.queryByRole('heading', { name: /add new product/i })).not.toBeInTheDocument()
      );
    });

    it('does NOT call createProduct when Cancel is clicked', async () => {
      const user = setup();
      await openNew(user);
      await user.type(getField('name'), 'Abandoned');
      await user.click(within(getModalCard()).getByRole('button', { name: /^cancel$/i }));
      expect(adminAPI.createProduct).not.toHaveBeenCalled();
    });
  });

  // ── 12. ProductModal – edit product ──────────────────────────────────────
  describe('ProductModal – edit product', () => {
    const openEdit = async (user, overrides = {}) => {
      adminAPI.getProducts.mockResolvedValue(
        paged([makeProduct({ name: 'Wireless Mouse', ...overrides })], 1)
      );
      render(<AdminProducts />);
      await waitFor(() => screen.getByText('Wireless Mouse'));
      await user.click(within(screen.getByTestId('dt-row-0')).getByTitle('Edit'));
      await waitFor(() =>
        expect(screen.getByRole('heading', { name: /edit product/i })).toBeInTheDocument()
      );
    };

    it('opens with "Edit Product" heading', async () => {
      const user = setup();
      await openEdit(user);
      expect(screen.getByRole('heading', { name: /edit product/i })).toBeInTheDocument();
    });

    it('submit button label is "Save Changes"', async () => {
      const user = setup();
      await openEdit(user);
      expect(
        within(getModalCard()).getByRole('button', { name: /save changes/i })
      ).toBeInTheDocument();
    });

    it('pre-fills the name field', async () => {
      const user = setup();
      await openEdit(user);
      expect(getField('name')).toHaveValue('Wireless Mouse');
    });

    it('pre-fills the price field', async () => {
      const user = setup();
      await openEdit(user, { price: 29.99 });
      expect(getField('price')).toHaveValue(29.99);
    });

    it('pre-fills the category select', async () => {
      const user = setup();
      await openEdit(user, { category: 11 });
      expect(getField('category')).toHaveValue('11');
    });

    it('pre-fills the stock field', async () => {
      const user = setup();
      await openEdit(user, { stock: 33 });
      expect(getField('stock')).toHaveValue(33);
    });

    it('pre-fills the thumbnail preview when thumbnail_url is set', async () => {
      const user = setup();
      await openEdit(user, { thumbnail_url: 'https://cdn.test/mouse-thumb.jpg' });
      const img = within(getModalCard()).getByAltText('');
      expect(img).toHaveAttribute('src', 'https://cdn.test/mouse-thumb.jpg');
    });

    it('pre-fills is_new and is_sale checkboxes', async () => {
      const user = setup();
      await openEdit(user, { is_new: true, is_sale: false });
      expect(getField('is_new')).toBeChecked();
      expect(getField('is_sale')).not.toBeChecked();
    });

    it('calls updateProduct with the product id and FormData', async () => {
      adminAPI.updateProduct.mockResolvedValue({ data: {} });
      const user = setup();
      await openEdit(user);
      await user.click(
        within(getModalCard()).getByRole('button', { name: /save changes/i })
      );
      await waitFor(() =>
        expect(adminAPI.updateProduct).toHaveBeenCalledWith(1, expect.any(FormData))
      );
    });

    it('does NOT call createProduct when editing', async () => {
      adminAPI.updateProduct.mockResolvedValue({ data: {} });
      const user = setup();
      await openEdit(user);
      await user.click(
        within(getModalCard()).getByRole('button', { name: /save changes/i })
      );
      await waitFor(() => expect(adminAPI.updateProduct).toHaveBeenCalled());
      expect(adminAPI.createProduct).not.toHaveBeenCalled();
    });

    it('closes modal and shows "Product saved" toast after successful update', async () => {
      adminAPI.updateProduct.mockResolvedValue({ data: {} });
      const user = setup();
      await openEdit(user);
      await user.click(
        within(getModalCard()).getByRole('button', { name: /save changes/i })
      );
      await waitFor(() => {
        expect(screen.queryByRole('heading', { name: /edit product/i })).not.toBeInTheDocument();
        expect(capturedToasts.some((t) => t.message === 'Product saved')).toBe(true);
      });
    });
  });

  // ── 13. Thumbnail upload ─────────────────────────────────────────────────
  describe('Thumbnail upload', () => {
    const openNewModal = async (user) => {
      render(<AdminProducts />);
      await waitFor(() =>
        expect(screen.getByRole('button', { name: /add product/i })).toBeInTheDocument()
      );
      await user.click(screen.getByRole('button', { name: /add product/i }));
      await waitFor(() =>
        expect(screen.getByRole('heading', { name: /add new product/i })).toBeInTheDocument()
      );
    };

    it('shows a preview image after a thumbnail file is uploaded', async () => {
      const fakeUrl = 'blob:http://localhost/thumb-789';
      global.URL.createObjectURL = vi.fn().mockReturnValue(fakeUrl);
      const user = setup();
      await openNewModal(user);

      const fileInput = getModalCard().querySelector('input[type="file"]');
      await user.upload(fileInput, new File(['img'], 'thumb.png', { type: 'image/png' }));

      await waitFor(() => {
        const preview = within(getModalCard()).getByAltText('');
        expect(preview).toHaveAttribute('src', fakeUrl);
      });
    });

    it('calls URL.createObjectURL with the uploaded file', async () => {
      const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL');
      const user = setup();
      await openNewModal(user);
      const file = new File(['img'], 'thumb.jpg', { type: 'image/jpeg' });
      const fileInput = getModalCard().querySelector('input[type="file"]');
      await user.upload(fileInput, file);
      await waitFor(() => expect(createObjectURLSpy).toHaveBeenCalledWith(file));
    });

    it('appends the thumbnail file to FormData on submit', async () => {
      adminAPI.createProduct.mockResolvedValue({ data: {} });
      const appendSpy = vi.spyOn(FormData.prototype, 'append');
      const user = setup();
      await openNewModal(user);

      await user.type(getField('name'), 'Thumb Product');
      await user.type(getField('price'), '20');
      await user.selectOptions(getField('category'), '10');

      const file = new File(['img'], 'thumb.png', { type: 'image/png' });
      const fileInput = getModalCard().querySelector('input[type="file"]');
      await user.upload(fileInput, file);

      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );

      await waitFor(() => {
        const thumbCalls = appendSpy.mock.calls.filter(([k]) => k === 'thumbnail');
        expect(thumbCalls).toHaveLength(1);
        expect(thumbCalls[0][1]).toBeInstanceOf(File);
      });
    });

    it('does nothing when file input change fires with no file', async () => {
      const user = setup();
      await openNewModal(user);
      const fileInput = getModalCard().querySelector('input[type="file"]');
      fireEvent.change(fileInput, { target: { files: [] } });
      expect(within(getModalCard()).queryByAltText('')).not.toBeInTheDocument();
    });
  });

  // ── 14. Checkbox toggles (is_new / is_sale) ──────────────────────────────
  describe('Checkbox toggles', () => {
    const openNewModal = async (user) => {
      render(<AdminProducts />);
      await waitFor(() =>
        expect(screen.getByRole('button', { name: /add product/i })).toBeInTheDocument()
      );
      await user.click(screen.getByRole('button', { name: /add product/i }));
      await waitFor(() =>
        expect(screen.getByRole('heading', { name: /add new product/i })).toBeInTheDocument()
      );
    };

    it('is_new and is_sale default to unchecked', async () => {
      const user = setup();
      await openNewModal(user);
      expect(getField('is_new')).not.toBeChecked();
      expect(getField('is_sale')).not.toBeChecked();
    });

    it('toggling "Mark as New" checks the is_new checkbox', async () => {
      const user = setup();
      await openNewModal(user);
      await user.click(getField('is_new'));
      expect(getField('is_new')).toBeChecked();
    });

    it('toggling "On Sale" checks the is_sale checkbox independently of is_new', async () => {
      const user = setup();
      await openNewModal(user);
      await user.click(getField('is_sale'));
      expect(getField('is_sale')).toBeChecked();
      expect(getField('is_new')).not.toBeChecked();
    });

    it('includes "true" string in FormData when is_new is checked', async () => {
      adminAPI.createProduct.mockResolvedValue({ data: {} });
      const user = setup();
      await openNewModal(user);

      await user.type(getField('name'), 'Marked New');
      await user.type(getField('price'), '10');
      await user.selectOptions(getField('category'), '10');
      await user.click(getField('is_new'));

      await user.click(
        within(getModalCard()).getByRole('button', { name: /^add product$/i })
      );

      await waitFor(() => {
        const fd = adminAPI.createProduct.mock.calls[0][0];
        expect(fd.get('is_new')).toBe('true');
      });
    });
  });

  // ── 15. Snapshot ─────────────────────────────────────────────────────────
  describe('Snapshot', () => {
    it('matches stable snapshot after data loads', async () => {
      const { asFragment } = render(<AdminProducts />);
      await waitFor(() => screen.getByText('Product 1'));
      expect(asFragment()).toMatchSnapshot();
    });
  });
});
