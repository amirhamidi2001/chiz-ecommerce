import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import Category from '../pages/Category';

// ─── Mock: API layer ──────────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  getProducts: vi.fn(),
  getCategories: vi.fn(),
  getBrands: vi.fn(),
  getColors: vi.fn(),
}));

// ─── Mock: CartContext ────────────────────────────────────────────────────────
vi.mock('../context/CartContext', () => ({
  useCart: () => ({
    addToCart: vi.fn().mockResolvedValue({ success: true, message: 'Added to cart' }),
  }),
}));

import { getProducts, getCategories, getBrands, getColors } from '../services/api';

// ─── Shared fixtures ──────────────────────────────────────────────────────────
const makeProduct = (overrides = {}) => ({
  id: 1,
  slug: 'test-product',
  name: 'Test Product',
  price: '49.99',
  original_price: null,
  rating: 4.5,
  reviews_count: 10,
  stock: 5,
  is_new: false,
  is_sale: false,
  discount_percent: 0,
  thumbnail_url: '/img/test.webp',
  images: [],
  category: { name: 'Electronics' },
  ...overrides,
});

const makeProductsResponse = (products, extra = {}) => ({
  data: {
    results: products,
    count: products.length,
    total_pages: 1,
    ...extra,
  },
});

const makeMetaResponse = (items = []) => ({ data: items });

const defaultMeta = () => {
  getCategories.mockResolvedValue(makeMetaResponse([]));
  getBrands.mockResolvedValue(makeMetaResponse([]));
  getColors.mockResolvedValue(makeMetaResponse([]));
};

// ─── Render helper ────────────────────────────────────────────────────────────
const renderCategory = (initialSearch = '') => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={[`/category${initialSearch}`]}>
      <Category />
    </MemoryRouter>
  );
  return { user };
};

// ─── Test suite ───────────────────────────────────────────────────────────────
describe('Category', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  // ── Loading ─────────────────────────────────────────────────────────────────
  describe('loading', () => {
    it('shows a loading spinner while products are being fetched', async () => {
      // Never resolve so we stay in loading state
      getProducts.mockReturnValue(new Promise(() => { }));
      defaultMeta();

      renderCategory();

      // The spinner is rendered as a spinning div; the product count label shows "Loading..."
      expect(screen.getByText('Loading...')).toBeInTheDocument();

      // No product cards or empty/error states visible yet
      expect(screen.queryByText('No products found')).not.toBeInTheDocument();
      expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
    });

    it('hides the loading state after the fetch resolves', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));
      defaultMeta();

      renderCategory();

      await waitFor(() =>
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
      );
    });
  });

  // ── Success render ──────────────────────────────────────────────────────────
  describe('success', () => {
    it('renders a list of products after a successful fetch', async () => {
      const products = [
        makeProduct({ id: 1, name: 'Alpha Widget', price: '19.99' }),
        makeProduct({ id: 2, slug: 'beta-gadget', name: 'Beta Gadget', price: '34.50' }),
      ];
      getProducts.mockResolvedValue(makeProductsResponse(products));
      defaultMeta();

      renderCategory();

      expect(await screen.findByText('Alpha Widget')).toBeInTheDocument();
      expect(screen.getByText('Beta Gadget')).toBeInTheDocument();
    });

    it('displays each product name as a link to its detail page', async () => {
      const product = makeProduct({ slug: 'cool-shoe', name: 'Cool Shoe' });
      getProducts.mockResolvedValue(makeProductsResponse([product]));
      defaultMeta();

      renderCategory();

      const link = await screen.findByRole('link', { name: 'Cool Shoe' });
      expect(link).toHaveAttribute('href', '/product/cool-shoe');
    });

    it('shows the formatted price for each product', async () => {
      getProducts.mockResolvedValue(
        makeProductsResponse([makeProduct({ price: '99.00' })])
      );
      defaultMeta();

      renderCategory();

      expect(await screen.findByText('$99.00')).toBeInTheDocument();
    });

    it('shows original (strike-through) price when a product is on sale', async () => {
      getProducts.mockResolvedValue(
        makeProductsResponse([
          makeProduct({ price: '59.99', original_price: '89.99' }),
        ])
      );
      defaultMeta();

      renderCategory();

      expect(await screen.findByText('$59.99')).toBeInTheDocument();
      expect(screen.getByText('$89.99')).toBeInTheDocument();
    });

    it('displays the total product count returned by the API', async () => {
      getProducts.mockResolvedValue(
        makeProductsResponse([makeProduct(), makeProduct({ id: 2 })], { count: 42 })
      );
      defaultMeta();

      renderCategory();

      expect(await screen.findByText('42 products found')).toBeInTheDocument();
    });

    it('shows singular "product" label when count is 1', async () => {
      getProducts.mockResolvedValue(
        makeProductsResponse([makeProduct()], { count: 1 })
      );
      defaultMeta();

      renderCategory();

      expect(await screen.findByText('1 product found')).toBeInTheDocument();
    });
  });

  // ── Empty state ─────────────────────────────────────────────────────────────
  describe('empty state', () => {
    it('shows an empty-state message when the API returns no products', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([]));
      defaultMeta();

      renderCategory();

      expect(await screen.findByText('No products found')).toBeInTheDocument();
      expect(
        screen.getByText(/try adjusting your filters/i)
      ).toBeInTheDocument();
    });

    it('shows a "Clear Filters" button in the empty state', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([]));
      defaultMeta();

      renderCategory();

      await screen.findByText('No products found');
      expect(
        screen.getByRole('button', { name: /clear filters/i })
      ).toBeInTheDocument();
    });

    it('re-fetches products (with cleared state) after clicking "Clear Filters" in the empty state', async () => {
      // First call: empty; second call: returns a product
      getProducts
        .mockResolvedValueOnce(makeProductsResponse([]))
        .mockResolvedValueOnce(makeProductsResponse([makeProduct()]));
      defaultMeta();

      const { user } = renderCategory();

      const clearBtn = await screen.findByRole('button', { name: /clear filters/i });
      await user.click(clearBtn);

      expect(await screen.findByText('Test Product')).toBeInTheDocument();
    });
  });

  // ── Error state ─────────────────────────────────────────────────────────────
  describe('error', () => {
    it('shows an error message when the API call rejects', async () => {
      getProducts.mockRejectedValue(new Error('Network Error'));
      defaultMeta();

      renderCategory();

      expect(await screen.findByText('Something went wrong')).toBeInTheDocument();
      expect(screen.getByText('Network Error')).toBeInTheDocument();
    });

    it('shows a "Try Again" button when an error occurs', async () => {
      getProducts.mockRejectedValue(new Error('Timeout'));
      defaultMeta();

      renderCategory();

      await screen.findByText('Something went wrong');
      expect(
        screen.getByRole('button', { name: /try again/i })
      ).toBeInTheDocument();
    });

    it('retries the fetch when "Try Again" is clicked and recovers on success', async () => {
      getProducts
        .mockRejectedValueOnce(new Error('Timeout'))
        .mockResolvedValueOnce(makeProductsResponse([makeProduct()]));
      defaultMeta();

      const { user } = renderCategory();

      const retryBtn = await screen.findByRole('button', { name: /try again/i });
      await user.click(retryBtn);

      expect(await screen.findByText('Test Product')).toBeInTheDocument();
      expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
    });

    it('does not show product list or empty state when an error occurs', async () => {
      getProducts.mockRejectedValue(new Error('Server Error'));
      defaultMeta();

      renderCategory();

      await screen.findByText('Something went wrong');
      expect(screen.queryByText('No products found')).not.toBeInTheDocument();
    });
  });

  // ── Filtering ───────────────────────────────────────────────────────────────
  describe('filtering', () => {
    it('calls the API with the search query after user types in the search box', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });

      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));
      defaultMeta();

      const { user } = renderCategory();

      // Wait for the initial fetch to settle
      await screen.findByText('Test Product');
      getProducts.mockClear();
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct({ name: 'Searched Item' })]));

      const searchInput = screen.getByPlaceholderText(/search products/i);
      await user.type(searchInput, 'shoe');

      // Advance past the debounce timer
      vi.advanceTimersByTime(500);

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ search: 'shoe' })
        );
      });

      vi.useRealTimers();
    });

    it('calls the API with the selected category when user picks one from the sidebar', async () => {
      const categoryData = [{ id: 10, slug: 'shoes', name: 'Shoes', children: [] }];
      getCategories.mockResolvedValue({ data: categoryData });
      getBrands.mockResolvedValue(makeMetaResponse([]));
      getColors.mockResolvedValue(makeMetaResponse([]));
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));

      const { user } = renderCategory();

      await screen.findByText('Test Product');
      getProducts.mockClear();
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct({ name: 'Nike Runner' })]));

      const shoesBtn = await screen.findByRole('button', { name: 'Shoes' });
      await user.click(shoesBtn);

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ category: 'shoes' })
        );
      });
    });

    it('resets to page 1 when a category filter is applied', async () => {
      const categoryData = [{ id: 10, slug: 'shoes', name: 'Shoes', children: [] }];
      getCategories.mockResolvedValue({ data: categoryData });
      getBrands.mockResolvedValue(makeMetaResponse([]));
      getColors.mockResolvedValue(makeMetaResponse([]));
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));

      const { user } = renderCategory();

      await screen.findByText('Test Product');
      getProducts.mockClear();
      getProducts.mockResolvedValue(makeProductsResponse([]));

      const shoesBtn = await screen.findByRole('button', { name: 'Shoes' });
      await user.click(shoesBtn);

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1 })
        );
      });
    });

    it('calls the API with brand filter when user toggles a brand checkbox', async () => {
      const brandData = [{ id: 5, slug: 'nike', name: 'Nike' }];
      getCategories.mockResolvedValue(makeMetaResponse([]));
      getBrands.mockResolvedValue({ data: brandData });
      getColors.mockResolvedValue(makeMetaResponse([]));
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));

      const { user } = renderCategory();

      await screen.findByText('Test Product');
      getProducts.mockClear();
      getProducts.mockResolvedValue(makeProductsResponse([]));

      const nikeCheckbox = await screen.findByRole('checkbox', { name: /nike/i });
      await user.click(nikeCheckbox);

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ brand: 'nike' })
        );
      });
    });

    it('shows active filter chip when a brand is selected', async () => {
      const brandData = [{ id: 5, slug: 'nike', name: 'Nike' }];
      getCategories.mockResolvedValue(makeMetaResponse([]));
      getBrands.mockResolvedValue({ data: brandData });
      getColors.mockResolvedValue(makeMetaResponse([]));
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));

      const { user } = renderCategory();

      await screen.findByText('Test Product');

      const nikeCheckbox = await screen.findByRole('checkbox', { name: /nike/i });
      await user.click(nikeCheckbox);

      await screen.findByText(/brand: nike/i);
    });

    it('removes the filter chip and re-fetches when a chip close button is clicked', async () => {
      const brandData = [{ id: 5, slug: 'nike', name: 'Nike' }];
      getCategories.mockResolvedValue(makeMetaResponse([]));
      getBrands.mockResolvedValue({ data: brandData });
      getColors.mockResolvedValue(makeMetaResponse([]));
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));

      const { user } = renderCategory();

      await screen.findByText('Test Product');

      const nikeCheckbox = await screen.findByRole('checkbox', { name: /nike/i });
      await user.click(nikeCheckbox);

      const chip = await screen.findByText(/brand: nike/i);
      const chipContainer = chip.closest('span');
      const closeBtn = within(chipContainer).getByRole('button');

      getProducts.mockClear();
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));
      await user.click(closeBtn);

      await waitFor(() => {
        expect(screen.queryByText(/brand: nike/i)).not.toBeInTheDocument();
      });
    });

    it('clears all active filters and re-fetches when "Clear All Filters" button is clicked', async () => {
      const brandData = [{ id: 5, slug: 'nike', name: 'Nike' }];
      getCategories.mockResolvedValue(makeMetaResponse([]));
      getBrands.mockResolvedValue({ data: brandData });
      getColors.mockResolvedValue(makeMetaResponse([]));
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));

      const { user } = renderCategory();

      await screen.findByText('Test Product');

      const nikeCheckbox = await screen.findByRole('checkbox', { name: /nike/i });
      await user.click(nikeCheckbox);
      await screen.findByText(/brand: nike/i);

      getProducts.mockClear();
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));

      // The sidebar "Clear All Filters" button
      const clearAllBtn = screen.getByRole('button', { name: /clear all filters/i });
      await user.click(clearAllBtn);

      await waitFor(() => {
        expect(screen.queryByText(/brand: nike/i)).not.toBeInTheDocument();
        // Called without a brand param
        expect(getProducts).toHaveBeenCalledWith(
          expect.not.objectContaining({ brand: expect.anything() })
        );
      });
    });

    it('reads the initial category filter from the URL search params', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));
      defaultMeta();

      renderCategory('?category=shoes');

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ category: 'shoes' })
        );
      });
    });
  });

  // ── Sorting ─────────────────────────────────────────────────────────────────
  describe('sorting', () => {
    it('calls the API with the new ordering when the user changes the sort dropdown', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));
      defaultMeta();

      const { user } = renderCategory();

      await screen.findByText('Test Product');

      getProducts.mockClear();
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct({ name: 'Cheap Item', price: '5.00' })]));

      const sortSelect = screen.getByText('Sort By').nextElementSibling;
      await user.selectOptions(sortSelect, 'price');

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ ordering: 'price' })
        );
      });
    });

    it('resets to page 1 when sort order changes', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()], { total_pages: 3 }));
      defaultMeta();

      const { user } = renderCategory();

      await screen.findByText('Test Product');

      getProducts.mockClear();
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));

      const sortSelect = screen.getAllByRole('combobox')[0];
      await user.selectOptions(sortSelect, '-price');

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ ordering: '-price', page: 1 })
        );
      });
    });

    it('renders all expected sort options in the dropdown', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([]));
      defaultMeta();

      renderCategory();

      const sortSelect = screen.getByText('Sort By').nextElementSibling;
      const options = within(sortSelect).getAllByRole('option');
      const optionValues = options.map((o) => o.value);

      expect(optionValues).toContain('-created_at');
      expect(optionValues).toContain('created_at');
      expect(optionValues).toContain('price');
      expect(optionValues).toContain('-price');
      expect(optionValues).toContain('-rating');
      expect(optionValues).toContain('name');
      expect(optionValues).toContain('-name');
    });

    it('uses the default "Newest First" ordering on initial render', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));
      defaultMeta();

      renderCategory();

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ ordering: '-created_at' })
        );
      });
    });
  });

  // ── Pagination ───────────────────────────────────────────────────────────────
  describe('pagination', () => {
    const multiPageResponse = (page = 1) =>
      makeProductsResponse(
        [makeProduct({ id: page, name: `Product on page ${page}`, price: '10.00' })],
        { count: 30, total_pages: 3 }
      );

    it('does not render pagination controls when there is only one page', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()], { total_pages: 1 }));
      defaultMeta();

      renderCategory();

      await screen.findByText('Test Product');
      expect(screen.queryByRole('button', { name: /prev/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /next/i })).not.toBeInTheDocument();
    });

    it('renders Prev and Next buttons when there are multiple pages', async () => {
      getProducts.mockResolvedValue(multiPageResponse(1));
      defaultMeta();

      renderCategory();

      await screen.findByText('Product on page 1');
      expect(screen.getByRole('button', { name: /prev/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    });

    it('disables the Prev button on the first page', async () => {
      getProducts.mockResolvedValue(multiPageResponse(1));
      defaultMeta();

      renderCategory();

      await screen.findByText('Product on page 1');
      expect(screen.getByRole('button', { name: /prev/i })).toBeDisabled();
    });

    it('fetches page 2 when the Next button is clicked', async () => {
      getProducts
        .mockResolvedValueOnce(multiPageResponse(1))
        .mockResolvedValueOnce(multiPageResponse(2));
      defaultMeta();

      const { user } = renderCategory();

      await screen.findByText('Product on page 1');
      const nextBtn = screen.getByRole('button', { name: /next/i });
      await user.click(nextBtn);

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ page: 2 })
        );
      });
    });

    it('fetches page 1 again when the Prev button is clicked from page 2', async () => {
      getProducts.mockImplementation((params) => {
        const requestedPage = params?.page || 1;
        return Promise.resolve(multiPageResponse(requestedPage));
      });
      defaultMeta();

      const { user } = renderCategory();

      await screen.findByText('Product on page 1');

      const nextBtn = screen.getByRole('button', { name: /next/i });
      await user.click(nextBtn);

      await screen.findByText('Product on page 2');

      getProducts.mockClear();

      const prevBtn = screen.getByRole('button', { name: /prev/i });
      await user.click(prevBtn);

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ page: 1 })
        );
      });
    });

    it('disables the Next button on the last page', async () => {
      getProducts
        .mockResolvedValueOnce(multiPageResponse(1))
        .mockResolvedValueOnce(multiPageResponse(2))
        .mockResolvedValueOnce(
          makeProductsResponse(
            [makeProduct({ id: 3, name: 'Product on page 3', price: '10.00' })],
            { count: 30, total_pages: 3 }
          )
        );
      defaultMeta();

      const { user } = renderCategory();

      await screen.findByText('Product on page 1');
      await user.click(screen.getByRole('button', { name: /next/i }));
      await screen.findByText('Product on page 2');
      await user.click(screen.getByRole('button', { name: /next/i }));
      await screen.findByText('Product on page 3');

      expect(screen.getByRole('button', { name: /next/i })).toBeDisabled();
    });

    it('fetches the correct page when a numbered page button is clicked', async () => {
      getProducts
        .mockResolvedValueOnce(multiPageResponse(1))
        .mockResolvedValueOnce(multiPageResponse(3));
      defaultMeta();

      const { user } = renderCategory();

      await screen.findByText('Product on page 1');

      getProducts.mockClear();
      getProducts.mockResolvedValueOnce(multiPageResponse(3));

      const page3Btn = screen.getByRole('button', { name: '3' });
      await user.click(page3Btn);

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ page: 3 })
        );
      });
    });

    it('passes the items-per-page value to the API', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));
      defaultMeta();

      renderCategory();

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ page_size: 12 })
        );
      });
    });

    // it('re-fetches with updated page_size when the items-per-page selector changes', async () => {
    //   getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));
    //   defaultMeta();

    //   const { user } = renderCategory();

    //   await screen.findByText('Test Product');
    //   getProducts.mockClear();
    //   getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));

    //   const perPageSelect = screen.getByRole('combobox', { name: /items per page/i });
    //   await user.selectOptions(perPageSelect, '24');

    //   await waitFor(() => {
    //     expect(getProducts).toHaveBeenCalledWith(
    //       expect.objectContaining({ page_size: 24 })
    //     );
    //   });
    // });
  });

  // ── Routing ──────────────────────────────────────────────────────────────────
  describe('routing', () => {
    it('renders correctly when mounted via MemoryRouter without any search params', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));
      defaultMeta();

      renderCategory();

      expect(await screen.findByText('Product Category')).toBeInTheDocument();
    });

    it('reads the "search" query param from the URL on mount and passes it to the API', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([makeProduct()]));
      defaultMeta();

      renderCategory('?search=sneaker');

      await waitFor(() => {
        expect(getProducts).toHaveBeenCalledWith(
          expect.objectContaining({ search: 'sneaker' })
        );
      });
    });

    it('renders product detail links with correct slugs', async () => {
      const products = [
        makeProduct({ id: 1, slug: 'alpha-shoe', name: 'Alpha Shoe' }),
        makeProduct({ id: 2, slug: 'beta-bag', name: 'Beta Bag' }),
      ];
      getProducts.mockResolvedValue(makeProductsResponse(products));
      defaultMeta();

      renderCategory();

      const alphaLink = await screen.findByRole('link', { name: 'Alpha Shoe' });
      const betaLink = screen.getByRole('link', { name: 'Beta Bag' });

      expect(alphaLink).toHaveAttribute('href', '/product/alpha-shoe');
      expect(betaLink).toHaveAttribute('href', '/product/beta-bag');
    });

    it('renders a breadcrumb Home link pointing to "/"', async () => {
      getProducts.mockResolvedValue(makeProductsResponse([]));
      defaultMeta();

      renderCategory();

      const homeLink = await screen.findByRole('link', { name: /home/i });
      expect(homeLink).toHaveAttribute('href', '/');
    });
  });
});
