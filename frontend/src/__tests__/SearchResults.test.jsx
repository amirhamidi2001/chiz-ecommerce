import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import SearchResults from '../pages/SearchResults';

// ─── Module mocks ──────────────────────────────────────────────────────────────

vi.mock('../services/api', () => ({
  getProducts: vi.fn(),
  getCategories: vi.fn(),
  getBrands: vi.fn(),
}));

// We import the mocked functions AFTER vi.mock so the references are the spies.
import { getProducts, getCategories, getBrands } from '../services/api';

// Mock context hooks so we can control their return values per test.
const mockAddToCart = vi.fn();
const mockAddToWishlist = vi.fn();
const mockRemoveFromWishlist = vi.fn();
const mockIsInWishlist = vi.fn(() => false);

vi.mock('../context/CartContext', () => ({
  useCart: () => ({ addToCart: mockAddToCart }),
}));

vi.mock('../context/WishlistContext', () => ({
  useWishlist: () => ({
    addToWishlist: mockAddToWishlist,
    removeFromWishlist: mockRemoveFromWishlist,
    isInWishlist: mockIsInWishlist,
  }),
}));

// Silence "not wrapped in act" noise for smooth scrollTo
window.scrollTo = vi.fn();

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const CATEGORIES = [
  { id: 1, name: 'Electronics', slug: 'electronics', children: [] },
  { id: 2, name: 'Books', slug: 'books', children: [] },
];

const BRANDS = [
  { id: 10, name: 'BrandAlpha' },
  { id: 11, name: 'BrandBeta' },
];

/** Build a minimal product object. Override fields as needed. */
const makeProduct = (overrides = {}) => ({
  id: 1,
  name: 'Test Product',
  slug: 'test-product',
  price: '29.99',
  sale_price: null,
  rating: 4.2,
  reviews_count: 17,
  thumbnail: '/assets/img/product/product-1.webp',
  in_stock: true,
  is_new: false,
  category: { name: 'Electronics' },
  brand: { name: 'BrandAlpha' },
  ...overrides,
});

/** Paginated API envelope */
const productPage = (items, count = items.length) => ({
  data: { results: items, count },
});

/** Resolved promise helpers */
const resolvedCategories = () => Promise.resolve({ data: CATEGORIES });
const resolvedBrands = () => Promise.resolve({ data: BRANDS });
const resolvedProducts = (items, count) =>
  Promise.resolve(productPage(items, count));

// ─── Render helper ────────────────────────────────────────────────────────────

/**
 * Renders <SearchResults> inside a MemoryRouter so useSearchParams and
 * useNavigate work correctly.  Pass `initialSearch` as a query-string, e.g.
 * '?q=shoes&page=2'.
 */
const renderSearchResults = (initialSearch = '') => {
  return render(
    <MemoryRouter initialEntries={[`/search${initialSearch}`]}>
      <SearchResults />
    </MemoryRouter>,
  );
};

// ─── Setup / teardown ─────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  mockIsInWishlist.mockReturnValue(false);

  // Default: static filter data resolves immediately.
  getCategories.mockReturnValue(resolvedCategories());
  getBrands.mockReturnValue(resolvedBrands());
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ═════════════════════════════════════════════════════════════════════════════
// 1. INITIAL LOAD & DATA FETCHING
// ═════════════════════════════════════════════════════════════════════════════

describe('Initial load & data fetching', () => {
  it('shows skeleton cards while products are loading', async () => {
    // Products never resolves during this test so we stay in loading state.
    getProducts.mockReturnValue(new Promise(() => { }));

    renderSearchResults();

    // The component renders PAGE_SIZE (12) skeleton cards while loading.
    // SkeletonCard has no accessible role; query by the animate-pulse class.
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);

    // "Search Results" heading should already be in the DOM.
    expect(screen.getByRole('heading', { name: /search results/i })).toBeInTheDocument();
  });

  it('calls getCategories, getBrands, and getProducts on mount', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    renderSearchResults('?q=laptop');

    await waitFor(() => expect(getProducts).toHaveBeenCalledTimes(1));
    expect(getCategories).toHaveBeenCalledTimes(1);
    expect(getBrands).toHaveBeenCalledTimes(1);
  });

  it('passes the search query from the URL to getProducts', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    renderSearchResults('?q=headphones');

    await waitFor(() =>
      expect(getProducts).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'headphones' }),
        expect.anything(),
      ),
    );
  });

  it('renders product cards after a successful fetch', async () => {
    const products = [
      makeProduct({ id: 1, name: 'Wireless Headphones' }),
      makeProduct({ id: 2, name: 'Bluetooth Speaker' }),
    ];
    getProducts.mockReturnValue(resolvedProducts(products, 2));

    renderSearchResults('?q=audio');

    await waitFor(() =>
      expect(screen.getByText('Wireless Headphones')).toBeInTheDocument(),
    );
    expect(screen.getByText('Bluetooth Speaker')).toBeInTheDocument();
  });

  it('renders categories in the filter sidebar after fetch', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    renderSearchResults();

    // Accounts for both desktop and mobile sidebars
    await waitFor(() =>
      expect(screen.getAllByText('Electronics').length).toBeGreaterThan(0),
    );
    expect(screen.getAllByText('Books').length).toBeGreaterThan(0);
  });

  it('renders brands in the filter sidebar after fetch', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    renderSearchResults();

    // Accounts for both desktop and mobile sidebars
    await waitFor(() =>
      expect(screen.getAllByText('BrandAlpha').length).toBeGreaterThan(0),
    );
    expect(screen.getAllByText('BrandBeta').length).toBeGreaterThan(0);
  });

  it('shows the result count and query in the subtitle once loaded', async () => {
    const products = [makeProduct(), makeProduct({ id: 2 })];
    getProducts.mockReturnValue(resolvedProducts(products, 2));

    renderSearchResults('?q=shoes');

    await waitFor(() =>
      expect(screen.getByText(/2 results/i)).toBeInTheDocument(),
    );

    // Asserts that at least one (and possibly multiple) instances of "shoes" appear in the DOM
    expect(screen.getAllByText(/shoes/i).length).toBeGreaterThan(0);
  });

  it('displays "Searching…" while loading a query', async () => {
    getProducts.mockReturnValue(new Promise(() => { })); // never resolves

    renderSearchResults('?q=watches');

    expect(screen.getByText(/searching…/i)).toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 2. EMPTY STATE
// ═════════════════════════════════════════════════════════════════════════════

describe('Empty state', () => {
  it('renders the empty state when the results array is empty', async () => {
    getProducts.mockReturnValue(resolvedProducts([], 0));

    renderSearchResults('?q=xyznotfound');

    await waitFor(() =>
      expect(screen.getByText(/no results found/i)).toBeInTheDocument(),
    );
  });

  it('shows the searched query inside the empty-state message', async () => {
    getProducts.mockReturnValue(resolvedProducts([], 0));

    renderSearchResults('?q=unicornproduct');

    await waitFor(() =>
      expect(screen.getByText(/unicornproduct/i)).toBeInTheDocument(),
    );
  });

  it('shows "no products match your current filters" when there is no query', async () => {
    getProducts.mockReturnValue(resolvedProducts([], 0));

    renderSearchResults('?category=electronics');

    await waitFor(() =>
      expect(
        screen.getByText(/no products match your current filters/i),
      ).toBeInTheDocument(),
    );
  });

  it('shows the "Clear filters" button when active filters exist and results are empty', async () => {
    getProducts.mockReturnValue(resolvedProducts([], 0));

    renderSearchResults('?category=electronics');

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /clear filters/i }),
      ).toBeInTheDocument(),
    );
  });

  it('does NOT show "Clear filters" when there are no active filters', async () => {
    getProducts.mockReturnValue(resolvedProducts([], 0));

    renderSearchResults('?q=xyz');

    await waitFor(() =>
      expect(screen.getByText(/no results found/i)).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole('button', { name: /clear filters/i }),
    ).not.toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 3. ERROR STATE
// ═════════════════════════════════════════════════════════════════════════════

describe('Error state', () => {
  it('shows the error message when getProducts rejects', async () => {
    getProducts.mockRejectedValue(new Error('Network Error'));

    renderSearchResults();

    await waitFor(() =>
      expect(
        screen.getByText(/something went wrong/i),
      ).toBeInTheDocument(),
    );
  });

  it('renders a Retry button alongside the error message', async () => {
    getProducts.mockRejectedValue(new Error('Network Error'));

    renderSearchResults();

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /retry/i }),
      ).toBeInTheDocument(),
    );
  });

  it('does NOT show the error state when the error is a CanceledError (abort)', async () => {
    const abortError = Object.assign(new Error('canceled'), {
      name: 'CanceledError',
    });
    getProducts.mockRejectedValue(abortError);

    renderSearchResults();

    // Give the component time to settle.
    await waitFor(() => expect(getProducts).toHaveBeenCalled());

    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 4. FILTER & SEARCH INTERACTIONS
// ═════════════════════════════════════════════════════════════════════════════

describe('Search form', () => {
  it('updates the "q" search param when the refine-search form is submitted', async () => {
    getProducts.mockReturnValue(resolvedProducts([]));

    const user = userEvent.setup();
    renderSearchResults('?q=shoes');

    // Wait for the component to finish loading so the input is populated.
    await waitFor(() => expect(getProducts).toHaveBeenCalled());

    const input = screen.getByPlaceholderText(/refine your search/i);

    // Clear, type a new query, submit.
    await user.clear(input);
    await user.type(input, 'boots');

    const submitBtn = screen.getByRole('button', { name: '' }); // the icon-only search button
    // Find the submit button inside the form by its type.
    const form = input.closest('form');
    const formSubmitBtn = within(form).getByRole('button');
    await user.click(formSubmitBtn);

    // getProducts should be called again with the updated query.
    await waitFor(() =>
      expect(getProducts).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: 'boots' }),
        expect.anything(),
      ),
    );
  });

  it('does not submit the form when the input is empty', async () => {
    getProducts.mockReturnValue(resolvedProducts([]));

    const user = userEvent.setup();
    renderSearchResults();

    await waitFor(() => expect(getProducts).toHaveBeenCalledTimes(1));

    const input = screen.getByPlaceholderText(/refine your search/i);
    await user.clear(input);

    const form = input.closest('form');
    const formSubmitBtn = within(form).getByRole('button');
    await user.click(formSubmitBtn);

    // getProducts should NOT be called a second time.
    expect(getProducts).toHaveBeenCalledTimes(1);
  });
});

describe('Category filter', () => {
  it('clicking a category radio updates the URL with the category param', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    const user = userEvent.setup();
    renderSearchResults();

    // Wait for the desktop view version to be confirmed in the DOM
    await waitFor(() =>
      expect(screen.getAllByText('Electronics').length).toBeGreaterThan(0),
    );

    // Reset mock count AFTER initial load
    getProducts.mockClear();
    getProducts.mockReturnValue(resolvedProducts([], 0));

    // 1. Isolate the desktop layout wrapper
    const desktopContainer = document.querySelector('.hidden.lg\\:block');

    // 2. Query the category button inside the desktop container
    const categoryButton = within(desktopContainer).getByRole('button', { name: /electronics/i });
    await user.click(categoryButton);

    await waitFor(() =>
      expect(getProducts).toHaveBeenCalledWith(
        expect.objectContaining({ category: 'electronics' }),
        expect.anything(),
      ),
    );
  });

  it('clicking the same category again toggles it off (deselects)', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    const user = userEvent.setup();
    renderSearchResults('?category=electronics');

    await waitFor(() =>
      expect(screen.getAllByText('Electronics').length).toBeGreaterThan(0),
    );

    getProducts.mockClear();
    getProducts.mockReturnValue(resolvedProducts([], 0));

    // 1. Isolate the desktop layout wrapper
    const desktopContainer = document.querySelector('.hidden.lg\\:block');

    // 2. Query the category button inside the desktop container
    const categoryButton = within(desktopContainer).getByRole('button', { name: /electronics/i });
    await user.click(categoryButton);

    await waitFor(() =>
      expect(getProducts).toHaveBeenCalledWith(
        expect.not.objectContaining({ category: 'electronics' }),
        expect.anything(),
      ),
    );
  });
});

describe('Price range filter', () => {
  it('applying a price range updates min_price and max_price params', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    const user = userEvent.setup();
    renderSearchResults();

    await waitFor(() =>
      expect(screen.getAllByPlaceholderText(/min/i).length).toBeGreaterThan(0),
    );

    getProducts.mockClear();
    getProducts.mockReturnValue(resolvedProducts([], 0));

    // There may be two price inputs (desktop sidebar + mobile drawer).
    // Target the first visible set.
    const minInputs = screen.getAllByPlaceholderText(/min/i);
    const maxInputs = screen.getAllByPlaceholderText(/max/i);

    await user.type(minInputs[0], '10');
    await user.type(maxInputs[0], '100');

    const applyBtns = screen.getAllByRole('button', { name: /apply/i });
    await user.click(applyBtns[0]);

    await waitFor(() =>
      expect(getProducts).toHaveBeenCalledWith(
        expect.objectContaining({ min_price: '10', max_price: '100' }),
        expect.anything(),
      ),
    );
  });
});

describe('Active filter chips', () => {
  it('renders an active chip for the selected category', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    renderSearchResults('?category=electronics');

    await waitFor(() =>
      expect(screen.getByText(/category: electronics/i)).toBeInTheDocument(),
    );
  });

  it('renders an active chip for the selected brand', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    renderSearchResults('?brand=10');

    await waitFor(() =>
      expect(screen.getByText(/brand: brandalpha/i)).toBeInTheDocument(),
    );
  });

  it('renders an active chip for an applied price range', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    renderSearchResults('?min_price=10&max_price=100');

    await waitFor(() =>
      expect(screen.getByText(/price: \$10 – \$100/i)).toBeInTheDocument(),
    );
  });

  it('clicking the remove button on a category chip removes the category param', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    const user = userEvent.setup();
    renderSearchResults('?category=electronics');

    await waitFor(() =>
      expect(screen.getByText(/category: electronics/i)).toBeInTheDocument(),
    );

    getProducts.mockClear();
    getProducts.mockReturnValue(resolvedProducts([], 0));

    const removeBtn = screen.getByRole('button', {
      name: /remove category: electronics filter/i,
    });
    await user.click(removeBtn);

    await waitFor(() =>
      expect(getProducts).toHaveBeenCalledWith(
        expect.not.objectContaining({ category: 'electronics' }),
        expect.anything(),
      ),
    );
    expect(
      screen.queryByText(/category: electronics/i),
    ).not.toBeInTheDocument();
  });

  it('clicking "Clear all" in the sidebar removes all filters but keeps the query', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    const user = userEvent.setup();
    renderSearchResults('?q=sneakers&category=electronics&brand=10');

    await waitFor(() =>
      expect(screen.getByText(/category: electronics/i)).toBeInTheDocument(),
    );

    getProducts.mockClear();
    getProducts.mockReturnValue(resolvedProducts([], 0));

    // "Clear all" button lives in the sidebar header.
    const clearAllBtn = screen.getByRole('button', { name: /clear all/i });
    await user.click(clearAllBtn);

    await waitFor(() =>
      expect(getProducts).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'sneakers' }),
        expect.anything(),
      ),
    );
    await waitFor(() =>
      expect(getProducts).toHaveBeenCalledWith(
        expect.not.objectContaining({ category: 'electronics' }),
        expect.anything(),
      ),
    );
  });
});

describe('Sort selector', () => {
  it('changing the sort select updates the ordering param', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    const user = userEvent.setup();
    renderSearchResults();

    await waitFor(() => expect(getProducts).toHaveBeenCalledTimes(1));

    getProducts.mockClear();
    getProducts.mockReturnValue(resolvedProducts([], 0));

    const sortSelect = screen.getByRole('combobox');
    await user.selectOptions(sortSelect, 'price');

    await waitFor(() =>
      expect(getProducts).toHaveBeenCalledWith(
        expect.objectContaining({ ordering: 'price' }),
        expect.anything(),
      ),
    );
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 5. CART & WISHLIST INTERACTIONS
// ═════════════════════════════════════════════════════════════════════════════

describe('Cart interactions', () => {
  it('clicking "Add to cart" calls addToCart with the product id and quantity 1', async () => {
    const product = makeProduct({ id: 42, name: 'Cart Test Product' });
    getProducts.mockReturnValue(resolvedProducts([product], 1));

    const user = userEvent.setup();
    renderSearchResults();

    // Wait for the product card to appear.
    await waitFor(() =>
      expect(screen.getByText('Cart Test Product')).toBeInTheDocument(),
    );

    // "Add to cart" button is hidden behind a hover overlay; it's still in the
    // DOM — trigger it directly.
    const addToCartBtn = screen.getByRole('button', { name: /add to cart/i });
    await user.click(addToCartBtn);

    expect(mockAddToCart).toHaveBeenCalledTimes(1);
    expect(mockAddToCart).toHaveBeenCalledWith(42, 1);
  });

  it('the "Add to cart" button is disabled when the product is out of stock', async () => {
    const product = makeProduct({ id: 5, name: 'OOS Product', in_stock: false });
    getProducts.mockReturnValue(resolvedProducts([product], 1));

    renderSearchResults();

    await waitFor(() =>
      expect(screen.getByText('OOS Product')).toBeInTheDocument(),
    );

    const outOfStockBtn = screen.getByRole('button', { name: /out of stock/i });
    expect(outOfStockBtn).toBeDisabled();
  });
});

describe('Wishlist interactions', () => {
  it('clicking the wishlist button calls addToWishlist when not in wishlist', async () => {
    mockIsInWishlist.mockReturnValue(false);
    const product = makeProduct({ id: 7, name: 'Wishlist Add Product' });
    getProducts.mockReturnValue(resolvedProducts([product], 1));

    const user = userEvent.setup();
    renderSearchResults();

    await waitFor(() =>
      expect(screen.getByText('Wishlist Add Product')).toBeInTheDocument(),
    );

    const wishlistBtn = screen.getByRole('button', { name: /add to wishlist/i });
    await user.click(wishlistBtn);

    expect(mockAddToWishlist).toHaveBeenCalledTimes(1);
    expect(mockAddToWishlist).toHaveBeenCalledWith(7);
    expect(mockRemoveFromWishlist).not.toHaveBeenCalled();
  });

  it('clicking the wishlist button calls removeFromWishlist when already in wishlist', async () => {
    mockIsInWishlist.mockReturnValue(true);
    const product = makeProduct({ id: 8, name: 'Wishlist Remove Product' });
    getProducts.mockReturnValue(resolvedProducts([product], 1));

    const user = userEvent.setup();
    renderSearchResults();

    await waitFor(() =>
      expect(screen.getByText('Wishlist Remove Product')).toBeInTheDocument(),
    );

    const wishlistBtn = screen.getByRole('button', {
      name: /remove from wishlist/i,
    });
    await user.click(wishlistBtn);

    expect(mockRemoveFromWishlist).toHaveBeenCalledTimes(1);
    expect(mockRemoveFromWishlist).toHaveBeenCalledWith(8);
    expect(mockAddToWishlist).not.toHaveBeenCalled();
  });

  it('the wishlist button shows bi-heart-fill icon when product is in the wishlist', async () => {
    mockIsInWishlist.mockReturnValue(true);
    const product = makeProduct({ id: 9, name: 'Hearted Product' });
    getProducts.mockReturnValue(resolvedProducts([product], 1));

    renderSearchResults();

    await waitFor(() =>
      expect(screen.getByText('Hearted Product')).toBeInTheDocument(),
    );

    // The button renders a filled heart icon when in wishlist.
    const heartIcon = document.querySelector('.bi-heart-fill');
    expect(heartIcon).toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 6. PAGINATION
// ═════════════════════════════════════════════════════════════════════════════

describe('Pagination', () => {
  /**
   * Creates 13 products (> PAGE_SIZE of 12) so the component renders the
   * Pagination widget (total pages = 2).
   */
  const buildMultiPageFixture = () => {
    const products = Array.from({ length: 12 }, (_, i) =>
      makeProduct({ id: i + 1, name: `Product ${i + 1}` }),
    );
    return { products, count: 13 }; // 13 items → ceil(13/12) = 2 pages
  };

  it('renders the pagination component when there is more than one page', async () => {
    const { products, count } = buildMultiPageFixture();
    getProducts.mockReturnValue(resolvedProducts(products, count));

    renderSearchResults('?page=1');

    await waitFor(() =>
      expect(screen.getByRole('navigation', { name: /pagination/i })).toBeInTheDocument(),
    );
  });

  it('displays the correct current-page and total-page info', async () => {
    const { products, count } = buildMultiPageFixture();
    getProducts.mockReturnValue(resolvedProducts(products, count));

    renderSearchResults('?page=1');

    await waitFor(() =>
      expect(screen.getByRole('navigation', { name: /pagination/i })).toBeInTheDocument(),
    );

    // Use a custom matcher function to read compiled text across tags
    const paginationText = screen.getByText((content, element) => {
      const hasText = (node) =>
        node.textContent.includes('Page 1 of 2') &&
        node.textContent.includes('13 results');

      const nodeHasText = hasText(element);
      const childrenDoNotHaveText = Array.from(element.children).every(child => !hasText(child));

      return nodeHasText && childrenDoNotHaveText;
    });

    expect(paginationText).toBeInTheDocument();
  });

  it('clicking a page button fetches that page', async () => {
    const { products, count } = buildMultiPageFixture();
    getProducts.mockReturnValue(resolvedProducts(products, count));

    const user = userEvent.setup();
    renderSearchResults('?page=1');

    await waitFor(() =>
      expect(
        screen.getByRole('navigation', { name: /pagination/i }),
      ).toBeInTheDocument(),
    );

    getProducts.mockClear();
    getProducts.mockReturnValue(resolvedProducts(products, count));

    // Page 2 button
    const page2Btn = screen.getByRole('button', { name: /page 2/i });
    await user.click(page2Btn);

    await waitFor(() =>
      expect(getProducts).toHaveBeenCalledWith(
        expect.objectContaining({ page: '2' }),
        expect.anything(),
      ),
    );
  });

  it('"Previous page" button is disabled on the first page', async () => {
    const { products, count } = buildMultiPageFixture();
    getProducts.mockReturnValue(resolvedProducts(products, count));

    renderSearchResults('?page=1');

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /previous page/i }),
      ).toBeDisabled(),
    );
  });

  it('"Next page" button is disabled on the last page', async () => {
    const { products, count } = buildMultiPageFixture();
    getProducts.mockReturnValue(resolvedProducts(products, count));

    renderSearchResults('?page=2');

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /next page/i }),
      ).toBeDisabled(),
    );
  });

  it('calls window.scrollTo when a page button is clicked', async () => {
    const { products, count } = buildMultiPageFixture();
    getProducts.mockReturnValue(resolvedProducts(products, count));

    const user = userEvent.setup();
    renderSearchResults('?page=1');

    await waitFor(() =>
      expect(
        screen.getByRole('navigation', { name: /pagination/i }),
      ).toBeInTheDocument(),
    );

    getProducts.mockClear();
    getProducts.mockReturnValue(resolvedProducts(products, count));

    const page2Btn = screen.getByRole('button', { name: /page 2/i });
    await user.click(page2Btn);

    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
  });

  it('does NOT render pagination when results fit on a single page', async () => {
    const products = [makeProduct()]; // 1 product → 1 page
    getProducts.mockReturnValue(resolvedProducts(products, 1));

    renderSearchResults();

    await waitFor(() =>
      expect(screen.getByText('Test Product')).toBeInTheDocument(),
    );

    expect(
      screen.queryByRole('navigation', { name: /pagination/i }),
    ).not.toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 7. MOBILE FILTER DRAWER
// ═════════════════════════════════════════════════════════════════════════════

describe('Mobile filter drawer', () => {
  it('opens the filter drawer when the "Filters" button is clicked', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    const user = userEvent.setup();
    renderSearchResults();

    await waitFor(() => expect(getProducts).toHaveBeenCalled());

    const filtersBtn = screen.getByRole('button', { name: /^filters$/i });
    await user.click(filtersBtn);

    // The DOM now contains multiple "Filters" headings (desktop sidebar + mobile drawer wrapper + mobile sidebar)
    const headings = screen.getAllByRole('heading', { name: /^filters$/i });
    expect(headings.length).toBeGreaterThan(1);
  });

  it('closes the drawer when the backdrop is clicked', async () => {
    getProducts.mockReturnValue(resolvedProducts([makeProduct()]));

    const user = userEvent.setup();
    renderSearchResults();

    await waitFor(() => expect(getProducts).toHaveBeenCalled());

    const filtersBtn = screen.getByRole('button', { name: /^filters$/i });
    await user.click(filtersBtn);

    // Drawer is open — find the close button.
    const closeBtn = screen.getByRole('button', { name: /close filters/i });
    await user.click(closeBtn);

    await waitFor(() =>
      expect(
        screen.queryByRole('button', { name: /close filters/i }),
      ).not.toBeInTheDocument(),
    );
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 8. PRODUCT CARD DISPLAY
// ═════════════════════════════════════════════════════════════════════════════

describe('ProductCard display', () => {
  it('renders the sale price and the original price when sale_price is set', async () => {
    const product = makeProduct({
      id: 99,
      name: 'Sale Item',
      price: '50.00',
      sale_price: '35.00',
    });
    getProducts.mockReturnValue(resolvedProducts([product], 1));

    renderSearchResults();

    await waitFor(() =>
      expect(screen.getByText('Sale Item')).toBeInTheDocument(),
    );

    expect(screen.getByText('$35.00')).toBeInTheDocument();
    expect(screen.getByText('$50.00')).toBeInTheDocument();
  });

  it('renders the "New" badge when product.is_new is true', async () => {
    const product = makeProduct({ id: 20, name: 'New Arrival', is_new: true });
    getProducts.mockReturnValue(resolvedProducts([product], 1));

    renderSearchResults();

    await waitFor(() =>
      expect(screen.getByText('New')).toBeInTheDocument(),
    );
  });

  it('renders the "Out of stock" badge when product.in_stock is false', async () => {
    const product = makeProduct({
      id: 21,
      name: 'OOS Item',
      in_stock: false,
    });
    getProducts.mockReturnValue(resolvedProducts([product], 1));

    renderSearchResults();

    await waitFor(() =>
      // The badge text "Out of stock" appears on both the overlay button AND
      // potentially a badge; use getAllByText and assert at least one.
      expect(screen.getAllByText(/out of stock/i).length).toBeGreaterThan(0),
    );
  });

  it('renders the discount percentage badge when sale_price is set', async () => {
    const product = makeProduct({
      id: 22,
      name: 'Discounted Item',
      price: '100.00',
      sale_price: '75.00',
    });
    getProducts.mockReturnValue(resolvedProducts([product], 1));

    renderSearchResults();

    await waitFor(() =>
      expect(screen.getByText(/-25%/i)).toBeInTheDocument(),
    );
  });

  it('links the product image and name to the correct product URL', async () => {
    const product = makeProduct({ id: 1, name: 'Linked Product', slug: 'linked-product' });
    getProducts.mockReturnValue(resolvedProducts([product], 1));

    renderSearchResults();

    await waitFor(() =>
      expect(screen.getByText('Linked Product')).toBeInTheDocument(),
    );

    // FIX: The product image AND the title are both wrapped in independent <Link> tags.
    // Use getAllByRole to account for both links pointing to the target product details view.
    const productLinks = screen.getAllByRole('link', { name: /linked product/i });
    expect(productLinks.length).toBe(2);
    productLinks.forEach(link => {
      expect(link).toHaveAttribute('href', '/product/linked-product');
    });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 9. STATIC FILTER FETCH FAILURE (non-critical)
// ═════════════════════════════════════════════════════════════════════════════

describe('Static filter fetch failure', () => {
  it('still renders products even when getCategories/getBrands fail', async () => {
    getCategories.mockRejectedValue(new Error('Categories API error'));
    getBrands.mockRejectedValue(new Error('Brands API error'));
    getProducts.mockReturnValue(resolvedProducts([makeProduct()], 1));

    renderSearchResults();

    // Products should still load despite filter fetch failure.
    await waitFor(() =>
      expect(screen.getByText('Test Product')).toBeInTheDocument(),
    );

    // No unhandled error UI should appear.
    expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();
  });
});
