import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import ProductDetails from '../pages/ProductDetails';
import * as api from '../services/api';
import { useCart } from '../context/CartContext';
import { useWishlist } from '../context/WishlistContext';
import { formatToman } from '../utils/money';
import { WithSeo } from './seoTestUtils';
import {
  headTitles,
  headDescriptions,
  headMeta,
  headOgProperties,
  headCanonicals,
  headHreflangs,
  headRobots,
  stubLocationOrigin,
} from './seoTestHelpers';
import { DEFAULT_TITLE, DEFAULT_DESCRIPTION } from '../constants/seo';
import { STORE_NAME } from '../constants/store';
import {
  buildProductMetaDescription,
  buildProductStructuredData,
  serializeJsonLd,
} from '../utils/seo';

// ─── Module mocks ──────────────────────────────────────────────────────────────

vi.mock('../services/api', () => ({
  getProductDetails: vi.fn(),
  getRelatedProducts: vi.fn(),
  getFrequentlyBoughtTogether: vi.fn(),
  createReview: vi.fn(),
  subscribeStockAlert: vi.fn(),
  isAuthenticated: vi.fn(() => true),
  parseErrors: vi.fn((err) => ({ non_field_errors: err?.message || 'Unknown error' })),
}));

vi.mock('../context/CartContext', () => ({
  useCart: vi.fn(),
}));

vi.mock('../context/WishlistContext', () => ({
  useWishlist: vi.fn(),
}));

// ─── Fixtures ──────────────────────────────────────────────────────────────────

const MOCK_PRODUCT = {
  id: 42,
  slug: 'test-widget-pro',
  name: 'Test Widget Pro',
  price: 499_900,
  original_price: 699_900,
  discount_percent: 28,
  description: 'A top-quality widget for all your widget needs.',
  short_description: 'Best widget ever.',
  thumbnail_url: '/assets/img/product/product-1.webp',
  images: [],
  stock: 10,
  rating: '4.5',
  reviews_count: 23,
  category: { name: 'Widgets' },
  brand: { name: 'WidgetCo' },
  colors: [],
  reviews: [],
};

const MOCK_RELATED = [
  {
    id: 7,
    slug: 'related-widget-a',
    name: 'Related Widget A',
    price: 299_900,
    rating: '4.0',
    thumbnail_url: '/assets/img/product/product-2.webp',
    category: { name: 'Widgets' },
    is_sale: false,
    is_new: false,
  },
  {
    id: 8,
    slug: 'related-widget-b',
    name: 'Related Widget B',
    price: 399_900,
    rating: '3.5',
    thumbnail_url: '/assets/img/product/product-3.webp',
    category: { name: 'Widgets' },
    is_sale: true,
    is_new: false,
  },
];

const MOCK_FBT = [
  {
    id: 21,
    slug: 'bought-together-x',
    name: 'Bought Together X',
    price: 199_900,
    rating: '4.2',
    thumbnail_url: '/assets/img/product/product-4.webp',
    category: { name: 'Accessories' },
    is_sale: false,
    is_new: false,
  },
  {
    id: 22,
    slug: 'bought-together-y',
    name: 'Bought Together Y',
    price: 599_900,
    rating: '4.8',
    thumbnail_url: '/assets/img/product/product-5.webp',
    category: { name: 'Accessories' },
    is_sale: false,
    is_new: true,
  },
];

// ─── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Renders <ProductDetails /> inside a MemoryRouter that provides the :slug
 * param, matching the route that would exist in App.jsx.
 */
const renderProductDetails = (slug = 'test-widget-pro') =>
  render(
    <MemoryRouter initialEntries={[`/product/${slug}`]}>
      <Routes>
        <Route path="/product/:slug" element={<ProductDetails />} />
        {/* Minimal stubs so navigate() / Link targets don't blow up */}
        <Route path="/cart" element={<div>Cart Page</div>} />
        <Route path="/category" element={<div>Category Page</div>} />
        <Route path="/" element={<div>Home Page</div>} />
      </Routes>
    </MemoryRouter>,
  );

/** Returns resolved/rejected promises that mimic the Axios response shape. */
const resolveWith = (data) => Promise.resolve({ data });
const rejectWith = (status = 500, message = 'Server Error') => {
  const err = new Error(message);
  err.response = { status };
  return Promise.reject(err);
};

// Default cart/wishlist stubs – overridden per test when needed.
const mockAddToCart = vi.fn();
const mockToggleWishlist = vi.fn();
const mockIsInWishlist = vi.fn(() => false);

// ─── Global beforeEach ─────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();

  // Happy-path defaults
  api.getProductDetails.mockReturnValue(resolveWith(MOCK_PRODUCT));
  api.getRelatedProducts.mockReturnValue(resolveWith(MOCK_RELATED));
  // Default: no co-purchase data, so existing tests see only the original page.
  api.getFrequentlyBoughtTogether.mockReturnValue(resolveWith([]));

  useCart.mockReturnValue({ addToCart: mockAddToCart });
  useWishlist.mockReturnValue({
    toggleWishlist: mockToggleWishlist,
    isInWishlist: mockIsInWishlist,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ─── Tests ─────────────────────────────────────────────────────────────────────

describe('ProductDetails', () => {
  // ── Loading ────────────────────────────────────────────────────────────────

  describe('loading', () => {
    it('shows a loading spinner before data resolves', () => {
      // Never resolves during this test
      api.getProductDetails.mockReturnValue(new Promise(() => { }));
      api.getRelatedProducts.mockReturnValue(new Promise(() => { }));

      renderProductDetails();

      // The spinner is the only content rendered in the loading branch
      const spinner = document.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();

      // Product name must NOT yet appear
      expect(screen.queryByText('Test Widget Pro')).not.toBeInTheDocument();
    });
  });

  // ── Success render ─────────────────────────────────────────────────────────

  describe('success', () => {
    it('renders the product name after a successful fetch', async () => {
      renderProductDetails();
      expect(await screen.findByRole('heading', { name: /test widget pro/i })).toBeInTheDocument();
    });

    it('renders the formatted product price', async () => {
      renderProductDetails();
      // The component formats price with toFixed(2) and prefixes "$"
      expect(await screen.findByText(formatToman(499_900))).toBeInTheDocument();
    });

    it('renders the product description', async () => {
      renderProductDetails();

      // Finds both instances and returns an array
      const descriptions = await screen.findAllByText(
        /a top-quality widget for all your widget needs/i
      );

      expect(descriptions[0]).toBeInTheDocument();
    });

    it('renders the product image with the correct alt text', async () => {
      renderProductDetails();
      const img = await screen.findByRole('img', { name: /test widget pro/i });
      expect(img).toBeInTheDocument();
      expect(img).toHaveAttribute('src', MOCK_PRODUCT.thumbnail_url);
    });

    it('shows "In Stock" when the product has stock > 0', async () => {
      renderProductDetails();
      expect(await screen.findByText(/in stock/i)).toBeInTheDocument();
    });

    it('shows "Out of Stock" when product.stock is 0', async () => {
      api.getProductDetails.mockReturnValue(
        resolveWith({ ...MOCK_PRODUCT, stock: 0 }),
      );

      renderProductDetails();

      const outOfStockElement = await screen.findByText('Out of Stock', { selector: 'span' });
      expect(outOfStockElement).toBeInTheDocument();
    });

    it('passes the correct slug to getProductDetails', async () => {
      renderProductDetails('my-custom-slug');
      await screen.findByRole('heading', { name: /test widget pro/i });
      expect(api.getProductDetails).toHaveBeenCalledWith('my-custom-slug');
    });
  });

  // ── Related products ───────────────────────────────────────────────────────

  describe('related products', () => {
    it('renders the related products section heading', async () => {
      renderProductDetails();
      expect(
        await screen.findByRole('heading', { name: /related products/i }),
      ).toBeInTheDocument();
    });

    it('renders a card for each related product', async () => {
      renderProductDetails();
      // Both related product names should appear
      expect(await screen.findByText('Related Widget A')).toBeInTheDocument();
      expect(await screen.findByText('Related Widget B')).toBeInTheDocument();
    });

    it('renders related product prices', async () => {
      renderProductDetails();
      expect(await screen.findByText(formatToman(299_900))).toBeInTheDocument();
      expect(await screen.findByText(formatToman(399_900))).toBeInTheDocument();
    });

    it('links each related product card to the correct product URL', async () => {
      renderProductDetails();
      const relatedLink = await screen.findByRole('link', { name: 'Related Widget A' });
      expect(relatedLink).toHaveAttribute('href', '/product/related-widget-a');
    });

    it('still renders the main product when related-products fetch fails', async () => {
      api.getRelatedProducts.mockReturnValue(rejectWith(500));
      renderProductDetails();
      // Main product should still appear; no crash
      expect(await screen.findByRole('heading', { name: /test widget pro/i })).toBeInTheDocument();
    });

    it('renders an empty related section gracefully when no related products exist', async () => {
      api.getRelatedProducts.mockReturnValue(resolveWith([]));
      renderProductDetails();
      // Section heading still present, but no related product names
      await screen.findByRole('heading', { name: /test widget pro/i });
      expect(screen.queryByText('Related Widget A')).not.toBeInTheDocument();
    });
  });

  // ── Customers Also Bought (frequently bought together) ─────────────────────

  describe('customers also bought', () => {
    it('renders the section heading and a card per product when results exist', async () => {
      api.getFrequentlyBoughtTogether.mockReturnValue(resolveWith(MOCK_FBT));
      renderProductDetails();

      expect(
        await screen.findByRole('heading', { name: /customers also bought/i }),
      ).toBeInTheDocument();
      expect(screen.getByText('Bought Together X')).toBeInTheDocument();
      expect(screen.getByText('Bought Together Y')).toBeInTheDocument();
      expect(screen.getByText(formatToman(199_900))).toBeInTheDocument();
    });

    it('fetches using the product slug from the route', async () => {
      renderProductDetails('another-slug');
      await screen.findByRole('heading', { name: /test widget pro/i });
      expect(api.getFrequentlyBoughtTogether).toHaveBeenCalledWith('another-slug');
    });

    it('links each card to its product URL', async () => {
      api.getFrequentlyBoughtTogether.mockReturnValue(resolveWith(MOCK_FBT));
      renderProductDetails();
      const link = await screen.findByRole('link', { name: 'Bought Together X' });
      expect(link).toHaveAttribute('href', '/product/bought-together-x');
    });

    it('does not render the section when results are empty', async () => {
      api.getFrequentlyBoughtTogether.mockReturnValue(resolveWith([]));
      renderProductDetails();
      await screen.findByRole('heading', { name: /test widget pro/i });
      expect(
        screen.queryByRole('heading', { name: /customers also bought/i }),
      ).not.toBeInTheDocument();
    });

    it('has no "View All" link inside its section', async () => {
      api.getFrequentlyBoughtTogether.mockReturnValue(resolveWith(MOCK_FBT));
      renderProductDetails();
      const heading = await screen.findByRole('heading', { name: /customers also bought/i });
      const section = heading.closest('div.mt-16');
      expect(within(section).queryByText(/view all/i)).not.toBeInTheDocument();
    });

    it('a failed fetch hides only this section; the page and Related Products still render', async () => {
      api.getFrequentlyBoughtTogether.mockReturnValue(rejectWith(500));
      renderProductDetails();

      expect(await screen.findByRole('heading', { name: /test widget pro/i })).toBeInTheDocument();
      expect(
        screen.queryByRole('heading', { name: /customers also bought/i }),
      ).not.toBeInTheDocument();
      expect(screen.queryByText(/failed to load product/i)).not.toBeInTheDocument();
      // unrelated section is unaffected
      expect(screen.getByRole('heading', { name: /related products/i })).toBeInTheDocument();
      expect(screen.getByText('Related Widget A')).toBeInTheDocument();
    });

    it('renders both sections independently, each with its own data', async () => {
      api.getRelatedProducts.mockReturnValue(resolveWith(MOCK_RELATED));
      api.getFrequentlyBoughtTogether.mockReturnValue(resolveWith(MOCK_FBT));
      renderProductDetails();

      const fbtHeading = await screen.findByRole('heading', { name: /customers also bought/i });
      const relatedHeading = screen.getByRole('heading', { name: /related products/i });
      const fbtSection = fbtHeading.closest('div.mt-16');
      const relatedSection = relatedHeading.closest('div.mt-16');
      expect(fbtSection).not.toBe(relatedSection);

      // each section contains only its own source's products
      expect(within(fbtSection).getByText('Bought Together X')).toBeInTheDocument();
      expect(within(fbtSection).getByText('Bought Together Y')).toBeInTheDocument();
      expect(within(fbtSection).queryByText('Related Widget A')).not.toBeInTheDocument();

      expect(within(relatedSection).getByText('Related Widget A')).toBeInTheDocument();
      expect(within(relatedSection).getByText('Related Widget B')).toBeInTheDocument();
      expect(within(relatedSection).queryByText('Bought Together X')).not.toBeInTheDocument();
    });

    it('Related Products still renders when Customers Also Bought is empty, and vice versa', async () => {
      api.getRelatedProducts.mockReturnValue(resolveWith([]));
      api.getFrequentlyBoughtTogether.mockReturnValue(resolveWith(MOCK_FBT));
      renderProductDetails();

      expect(
        await screen.findByRole('heading', { name: /customers also bought/i }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole('heading', { name: /related products/i }),
      ).not.toBeInTheDocument();
    });
  });

  // ── Error state ────────────────────────────────────────────────────────────

  describe('error', () => {
    it('shows a "Product not found" message on a 404 response', async () => {
      api.getProductDetails.mockReturnValue(rejectWith(404));
      renderProductDetails();
      expect(await screen.findByText(/product not found/i)).toBeInTheDocument();
    });

    it('shows a generic error message when the API returns a 500', async () => {
      api.getProductDetails.mockReturnValue(rejectWith(500));
      renderProductDetails();
      expect(
        await screen.findByText(/failed to load product\. please try again/i),
      ).toBeInTheDocument();
    });

    it('shows a "Browse Products" link in the error state', async () => {
      api.getProductDetails.mockReturnValue(rejectWith(404));
      renderProductDetails();
      const browseLink = await screen.findByRole('link', { name: /browse products/i });
      expect(browseLink).toBeInTheDocument();
      expect(browseLink).toHaveAttribute('href', '/category');
    });

    it('shows a "Go Back" button in the error state', async () => {
      api.getProductDetails.mockReturnValue(rejectWith(500));
      renderProductDetails();
      expect(await screen.findByRole('button', { name: /go back/i })).toBeInTheDocument();
    });
  });

  // ── Quantity controls ──────────────────────────────────────────────────────

  describe('quantity', () => {
    it('displays an initial quantity of 1', async () => {
      renderProductDetails();
      const input = await screen.findByRole('spinbutton');
      expect(input).toHaveValue(1);
    });

    it('increases quantity when the "+" button is clicked', async () => {
      const user = userEvent.setup();
      renderProductDetails();

      // 1. Wait for the quantity input to load (clears the loading spinner state)
      const qtyInput = await screen.findByRole('spinbutton');

      // 2. Locate the wrapper row containing the controls
      const qtyWrapper = qtyInput.closest('div');

      // 3. Grab the buttons inside that row (decrease is 1st, increase is 2nd)
      const [, increaseButton] = within(qtyWrapper).getAllByRole('button');

      // 4. Interact with the button
      await user.click(increaseButton);

      expect(qtyInput).toHaveValue(2);
    });

    it('decreases quantity when the "−" button is clicked', async () => {
      const user = userEvent.setup();
      renderProductDetails();

      const qtyInput = await screen.findByRole('spinbutton');
      const qtyWrapper = qtyInput.closest('div');
      const [decreaseBtn, increaseButton] = within(qtyWrapper).getAllByRole('button');

      // First increase to 2 so we have room to decrease
      await user.click(increaseButton);
      expect(qtyInput).toHaveValue(2);

      await user.click(decreaseBtn);
      expect(qtyInput).toHaveValue(1);
    });

    it('does not allow quantity to go below 1', async () => {
      const user = userEvent.setup();
      renderProductDetails();

      const qtyInput = await screen.findByRole('spinbutton');
      const qtyWrapper = qtyInput.closest('div');
      const [decreaseBtn] = within(qtyWrapper).getAllByRole('button');

      // Try to decrease from the initial value of 1
      await user.click(decreaseBtn);
      expect(qtyInput).toHaveValue(1);
    });

    it('disables the "−" button when quantity is at 1', async () => {
      renderProductDetails();

      const qtyInput = await screen.findByRole('spinbutton');
      const qtyWrapper = qtyInput.closest('div');
      const [decreaseBtn] = within(qtyWrapper).getAllByRole('button');

      expect(decreaseBtn).toBeDisabled();
    });

    it('does not allow quantity to exceed available stock', async () => {
      const user = userEvent.setup();
      // Product has stock of 2
      api.getProductDetails.mockReturnValue(resolveWith({ ...MOCK_PRODUCT, stock: 2 }));
      renderProductDetails();

      const qtyInput = await screen.findByRole('spinbutton');
      const qtyWrapper = qtyInput.closest('div');
      const [, increaseButton] = within(qtyWrapper).getAllByRole('button');

      // Click increase twice; should max out at 2
      await user.click(increaseButton);
      await user.click(increaseButton);

      expect(qtyInput).toHaveValue(2);
      expect(increaseButton).toBeDisabled();
    });
  });

  // ── Add to Cart ────────────────────────────────────────────────────────────

  describe('add to cart', () => {
    beforeEach(() => {
      mockAddToCart.mockResolvedValue({ success: true, message: 'Added to cart!' });
    });

    it('calls addToCart with the correct product id and quantity', async () => {
      const user = userEvent.setup();
      renderProductDetails();

      const addToCartBtn = await screen.findByRole('button', { name: /add to cart/i });
      await user.click(addToCartBtn);

      expect(mockAddToCart).toHaveBeenCalledTimes(1);
      expect(mockAddToCart).toHaveBeenCalledWith(MOCK_PRODUCT.id, 1);
    });

    it('calls addToCart with the updated quantity after the user increases it', async () => {
      const user = userEvent.setup();
      renderProductDetails();

      const qtyInput = await screen.findByRole('spinbutton');
      const qtyWrapper = qtyInput.closest('div');
      const [, increaseButton] = within(qtyWrapper).getAllByRole('button');

      await user.click(increaseButton);
      await user.click(increaseButton);

      const addToCartBtn = screen.getByRole('button', { name: /add to cart/i });
      await user.click(addToCartBtn);

      expect(mockAddToCart).toHaveBeenCalledWith(MOCK_PRODUCT.id, 3);
    });

    it('disables the "Add to Cart" button when the product is out of stock', async () => {
      api.getProductDetails.mockReturnValue(
        resolveWith({ ...MOCK_PRODUCT, stock: 0 }),
      );
      renderProductDetails();

      const addToCartBtn = await screen.findByRole('button', { name: /add to cart/i });
      expect(addToCartBtn).toBeDisabled();
    });

    it('does not call addToCart when the product is out of stock', async () => {
      const user = userEvent.setup();
      api.getProductDetails.mockReturnValue(
        resolveWith({ ...MOCK_PRODUCT, stock: 0 }),
      );
      renderProductDetails();

      const addToCartBtn = await screen.findByRole('button', { name: /add to cart/i });
      await user.click(addToCartBtn);

      expect(mockAddToCart).not.toHaveBeenCalled();
    });

    it('shows a success toast after a successful add to cart', async () => {
      const user = userEvent.setup();
      mockAddToCart.mockResolvedValue({ success: true, message: 'Added to cart!' });
      renderProductDetails();

      const addToCartBtn = await screen.findByRole('button', { name: /add to cart/i });
      await user.click(addToCartBtn);

      expect(await screen.findByText('Added to cart!')).toBeInTheDocument();
    });

    it('shows an error toast when addToCart reports a failure', async () => {
      const user = userEvent.setup();
      mockAddToCart.mockResolvedValue({ success: false, message: 'Not enough stock.' });
      renderProductDetails();

      const addToCartBtn = await screen.findByRole('button', { name: /add to cart/i });
      await user.click(addToCartBtn);

      expect(await screen.findByText('Not enough stock.')).toBeInTheDocument();
    });
  });

  // ── Routing ────────────────────────────────────────────────────────────────

  describe('routing', () => {
    it('uses the slug from the URL to fetch the correct product', async () => {
      renderProductDetails('some-other-slug');

      await waitFor(() => {
        expect(api.getProductDetails).toHaveBeenCalledWith('some-other-slug');
        expect(api.getRelatedProducts).toHaveBeenCalledWith('some-other-slug');
      });
    });

    it('renders the product page heading for any valid slug', async () => {
      renderProductDetails('any-valid-slug');
      expect(
        await screen.findByRole('heading', { name: /product details/i }),
      ).toBeInTheDocument();
    });

    it('includes the product name in the breadcrumb trail', async () => {
      renderProductDetails();
      // The breadcrumb renders product.name as plain text in a <li>
      const nav = await screen.findByRole('navigation', { name: /breadcrumb/i });
      expect(within(nav).getByText('Test Widget Pro')).toBeInTheDocument();
    });
  });

  // ── Stock alert: Notify Me When Available ────────────────────────────────────
  // NotifyMeButton isn't exported separately from ProductDetails.jsx, and its
  // behavior depends on the color→variant resolution living in the main
  // component (see ProductDetails.jsx's "Variant-aware stock check" comment),
  // so these are integration-style tests through the full page rather than
  // an isolated unit test of the button component.
  describe('stock alert notify me', () => {
    const RED = { id: 1, name: 'Red', hex_code: '#ff0000' };
    const BLUE = { id: 2, name: 'Blue', hex_code: '#0000ff' };

    const OUT_OF_STOCK_VARIANT_PRODUCT = {
      ...MOCK_PRODUCT,
      stock: 5, // legacy aggregate field still shows stock from OTHER variants
      colors: [{ color: RED }, { color: BLUE }],
      variants: [
        { id: 501, color: RED, stock: 0, price: 499_900, is_active: true },
        { id: 502, color: BLUE, stock: 5, price: 499_900, is_active: true },
      ],
    };

    it('shows "Notify Me When Available" instead of "Add to Cart" when the selected variant is out of stock', async () => {
      api.getProductDetails.mockReturnValue(resolveWith(OUT_OF_STOCK_VARIANT_PRODUCT));
      renderProductDetails();

      // The first color (Red) is auto-selected on load, and its variant has stock: 0
      expect(await screen.findByRole('button', { name: /notify me when available/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^add to cart$/i })).not.toBeInTheDocument();
    });

    it('shows "Add to Cart" normally when the selected variant has stock', async () => {
      api.getProductDetails.mockReturnValue(
        resolveWith({
          ...OUT_OF_STOCK_VARIANT_PRODUCT,
          variants: [
            { id: 501, color: RED, stock: 8, price: 499_900, is_active: true },
            { id: 502, color: BLUE, stock: 5, price: 499_900, is_active: true },
          ],
        }),
      );
      renderProductDetails();

      expect(await screen.findByRole('button', { name: /^add to cart$/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /notify me/i })).not.toBeInTheDocument();
    });

    it('switching to a color whose variant is back in stock swaps the button back to Add to Cart', async () => {
      const user = userEvent.setup();
      api.getProductDetails.mockReturnValue(resolveWith(OUT_OF_STOCK_VARIANT_PRODUCT));
      renderProductDetails();

      expect(await screen.findByRole('button', { name: /notify me when available/i })).toBeInTheDocument();

      const blueSwatch = screen.getByTitle('Blue');
      await user.click(blueSwatch);

      expect(await screen.findByRole('button', { name: /^add to cart$/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /notify me/i })).not.toBeInTheDocument();
    });

    it('redirects to /login when clicked while logged out, without calling the subscribe API', async () => {
      const user = userEvent.setup();
      api.isAuthenticated.mockReturnValue(false);
      api.getProductDetails.mockReturnValue(resolveWith(OUT_OF_STOCK_VARIANT_PRODUCT));

      // jsdom doesn't implement real navigation; spy on the setter instead.
      delete window.location;
      window.location = { href: '' };

      renderProductDetails();
      const notifyBtn = await screen.findByRole('button', { name: /notify me when available/i });
      await user.click(notifyBtn);

      expect(window.location.href).toBe('/login');
      expect(api.subscribeStockAlert).not.toHaveBeenCalled();
    });

    it('shows a confirmed/disabled state after a successful subscribe', async () => {
      const user = userEvent.setup();
      api.isAuthenticated.mockReturnValue(true);
      api.subscribeStockAlert.mockReturnValue(resolveWith({ id: 1 }));
      api.getProductDetails.mockReturnValue(resolveWith(OUT_OF_STOCK_VARIANT_PRODUCT));

      renderProductDetails();
      const notifyBtn = await screen.findByRole('button', { name: /notify me when available/i });
      await user.click(notifyBtn);

      expect(api.subscribeStockAlert).toHaveBeenCalledWith(501);
      expect(await screen.findByText(/we'll notify you!/i)).toBeInTheDocument();
      // Confirmed state renders as a disabled button, not the active one anymore
      expect(screen.queryByRole('button', { name: /notify me when available/i })).not.toBeInTheDocument();
    });

    it('shows a "back in stock" message instead of a generic error on a 400 race-condition response', async () => {
      const user = userEvent.setup();
      api.isAuthenticated.mockReturnValue(true);
      api.subscribeStockAlert.mockImplementation(() => rejectWith(400, 'This item is currently in stock.'));
      api.getProductDetails.mockReturnValue(resolveWith(OUT_OF_STOCK_VARIANT_PRODUCT));

      renderProductDetails();
      const notifyBtn = await screen.findByRole('button', { name: /notify me when available/i });
      await user.click(notifyBtn);

      expect(await screen.findByText(/back in stock/i)).toBeInTheDocument();
    });
  });

  describe('image gallery (RTL)', () => {
    const IMAGES = ['/img/a.webp', '/img/b.webp', '/img/c.webp'].map((image) => ({ image }));

    const openGallery = async () => {
      // the gallery opens on thumbnail_url, which the API sets to the first image
      api.getProductDetails.mockReturnValue(
        resolveWith({ ...MOCK_PRODUCT, thumbnail_url: IMAGES[0].image, images: IMAGES }),
      );
      renderProductDetails();
      const prev = await screen.findByRole('button', { name: /previous image/i });
      const next = screen.getByRole('button', { name: /next image/i });
      return { prev, next, user: userEvent.setup() };
    };
    const shown = () => screen.getByAltText(MOCK_PRODUCT.name).getAttribute('src');

    it('marks both arrow icons as direction-sensitive so they mirror in RTL', async () => {
      const { prev, next } = await openGallery();
      expect(prev.querySelector('i')).toHaveClass('bi-chevron-left', 'icon-directional');
      expect(next.querySelector('i')).toHaveClass('bi-chevron-right', 'icon-directional');
    });

    it('puts "previous" on the start side and "next" on the end side (logical, so they swap in RTL)', async () => {
      const { prev, next } = await openGallery();
      expect(prev).toHaveClass('start-3');
      expect(next).toHaveClass('end-3');
      expect(prev).not.toHaveClass('left-3');
      expect(next).not.toHaveClass('right-3');
    });

    it('Next advances through the images in order and wraps; Previous steps back', async () => {
      // The slide logic is index-based, so it is the same in LTR and RTL: "next" always
      // means the following image, and only the arrow's POSITION and ICON change.
      const { prev, next, user } = await openGallery();
      expect(shown()).toBe('/img/a.webp');
      await user.click(next);
      expect(shown()).toBe('/img/b.webp');
      await user.click(next);
      expect(shown()).toBe('/img/c.webp');
      await user.click(next);
      expect(shown()).toBe('/img/a.webp'); // wraps to the first
      await user.click(prev);
      expect(shown()).toBe('/img/c.webp'); // wraps back to the last
    });

    it('keeps the "1 / 3" counter in reading order (a bidi run would render it "3 / 1")', async () => {
      await openGallery();
      expect(screen.getByText('1 / 3')).toHaveAttribute('dir', 'ltr');
    });
  });

  describe('store response on reviews', () => {
    const REVIEW = {
      id: 1,
      user_id: 9,
      name: 'Alice',
      rating: 4,
      headline: 'Nice',
      comment: 'Lovely shade.',
      is_verified_purchase: true,
      created_at: '2026-09-01T10:00:00Z',
      images: [],
      store_response: '',
      store_response_at: null,
    };

    const openReviews = async (reviews) => {
      const user = userEvent.setup();
      api.getProductDetails.mockReturnValue(resolveWith({ ...MOCK_PRODUCT, reviews }));
      renderProductDetails();
      await user.click(await screen.findByRole('button', { name: /reviews \(/i }));
    };

    it('renders a labelled, dated response box when the store has replied', async () => {
      await openReviews([
        { ...REVIEW, store_response: 'Thank you, Alice!', store_response_at: '2026-09-03T09:00:00Z' },
      ]);

      const box = await screen.findByTestId('store-response');
      expect(within(box).getByText(/response from chiz/i)).toBeInTheDocument();
      expect(within(box).getByText('Thank you, Alice!')).toBeInTheDocument();
      expect(within(box).getByText('September 3, 2026')).toBeInTheDocument();
      // The customer's own text is still shown separately.
      expect(screen.getByText('Lovely shade.')).toBeInTheDocument();
    });

    it('renders no response box for reviews without a reply', async () => {
      await openReviews([REVIEW]);

      expect(await screen.findByText('Lovely shade.')).toBeInTheDocument();
      expect(screen.queryByTestId('store-response')).not.toBeInTheDocument();
    });
  });

  // ── Numeral styles (Task 14.1.2.4) ─────────────────────────────────────────
  // Ratings and review counts: Persian digits. Prices: Western digits.
  describe('numeral styles', () => {
    it('shows the rating and review counts in Persian digits and the price in Western', async () => {
      renderProductDetails();

      expect(await screen.findByText(formatToman(499_900))).toBeInTheDocument();
      expect(screen.getByText('(۲۳ reviews)')).toBeInTheDocument(); // beside the stars
      expect(screen.getByRole('button', { name: 'Reviews (۲۳)' })).toBeInTheDocument();

      expect(screen.queryByText('(23 reviews)')).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Reviews (23)' })).not.toBeInTheDocument();
    });

    it('the Technical Details tab shows "rating / 5" in Persian digits', async () => {
      const user = userEvent.setup();
      renderProductDetails();
      await user.click(await screen.findByRole('button', { name: 'Technical Details' }));

      expect(await screen.findByText('۴.۵ / ۵')).toBeInTheDocument();
      expect(screen.queryByText('4.5 / 5')).not.toBeInTheDocument();
    });

    it('the Reviews tab shows the aggregate score and review total in Persian digits', async () => {
      const user = userEvent.setup();
      renderProductDetails();
      await user.click(await screen.findByRole('button', { name: 'Reviews (۲۳)' }));

      expect(await screen.findByText('۴.۵')).toBeInTheDocument(); // the big aggregate score
      expect(screen.getByText(/^[۰-۹]+ reviews?$/)).toBeInTheDocument();
      expect(screen.queryByText('4.5')).not.toBeInTheDocument();
    });

    it('related products show their ratings in Persian digits', async () => {
      renderProductDetails();
      await screen.findByText(formatToman(499_900));

      expect((await screen.findAllByText('۴.۰')).length).toBeGreaterThan(0);
      expect(screen.queryByText('4.0')).not.toBeInTheDocument();
    });
  });
});

// ─── Page <title> / <meta description> (Task 15.1.1.2) ─────────────────────────
// Rendered inside the same provider stack as App.jsx, so these assertions are about what
// actually lands in document.head, including the sitewide default NOT lingering beside it.

const FA_PRODUCT = {
  ...MOCK_PRODUCT,
  name: 'سرم ویتامین سی',
  brand: { name: 'کلینیک' },
  category: { name: 'مراقبت پوست' },
  short_description:
    'این سرم ویتامین سی با فرمولی سبک و بدون چربی پوست را روشن و یکنواخت می\u200cکند و ' +
    'برای استفاده روزانه در هر نوع پوست مناسب است و لکه\u200cهای تیره را به\u200cتدریج کم می\u200cکند',
};

const renderWithSeo = () =>
  render(
    <WithSeo>
      <MemoryRouter initialEntries={['/product/test-widget-pro']}>
        <Routes>
          <Route path="/product/:slug" element={<ProductDetails />} />
        </Routes>
      </MemoryRouter>
    </WithSeo>,
  );

describe('ProductDetails page title and description', () => {
  it("puts the product's real name and brand in the <title> once data has loaded", async () => {
    api.getProductDetails.mockReturnValue(resolveWith(FA_PRODUCT));
    renderWithSeo();

    await waitFor(() =>
      expect(document.title).toBe(`سرم ویتامین سی | کلینیک | ${STORE_NAME}`),
    );
    expect(document.title).not.toBe(DEFAULT_TITLE);
    expect(document.title).toContain('سرم ویتامین سی'); // Persian renders unmangled
  });

  it('sets a description built from the product, and leaves only ONE title and description in <head>', async () => {
    api.getProductDetails.mockReturnValue(resolveWith(FA_PRODUCT));
    renderWithSeo();

    await waitFor(() => expect(document.title).toContain('سرم ویتامین سی'));
    await waitFor(() => expect(headDescriptions()).toHaveLength(1));
    expect(headDescriptions()[0].getAttribute('content')).toBe(
      buildProductMetaDescription(FA_PRODUCT),
    );
    expect(headDescriptions()[0].getAttribute('content')).not.toBe(DEFAULT_DESCRIPTION);
    expect(headTitles()).toHaveLength(1); // the sitewide default stepped aside, not duplicated
  });

  it('uses the template description when short_description is too short to be useful', async () => {
    api.getProductDetails.mockReturnValue(resolveWith({ ...FA_PRODUCT, short_description: 'جدید' }));
    renderWithSeo();

    await waitFor(() => expect(headDescriptions()[0]?.getAttribute('content')).toContain('کلینیک'));
    const content = headDescriptions()[0].getAttribute('content');
    expect(content).toContain('سرم ویتامین سی');
    expect(content).toContain('مراقبت پوست');
  });

  it('drops the brand segment cleanly for a product without a brand', async () => {
    api.getProductDetails.mockReturnValue(resolveWith({ ...FA_PRODUCT, brand: null }));
    renderWithSeo();

    await waitFor(() => expect(document.title).toBe(`سرم ویتامین سی | ${STORE_NAME}`));
  });

  it('renders no broken title while the product is still loading: the sitewide default shows', async () => {
    api.getProductDetails.mockReturnValue(new Promise(() => { }));
    api.getRelatedProducts.mockReturnValue(new Promise(() => { }));
    renderWithSeo();

    await waitFor(() => expect(document.title).toBe(DEFAULT_TITLE));
    expect(document.head.textContent).not.toMatch(/undefined|null/);
    expect(headTitles()).toHaveLength(1);
    expect(headDescriptions()).toHaveLength(1);
    expect(headDescriptions()[0].getAttribute('content')).toBe(DEFAULT_DESCRIPTION);
  });

  it('keeps the sitewide default when the product fails to load (404)', async () => {
    api.getProductDetails.mockImplementation(() => rejectWith(404, 'Not Found'));
    renderWithSeo();

    expect(await screen.findByText(/product not found/i)).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe(DEFAULT_TITLE));
    expect(document.head.textContent).not.toMatch(/undefined|null/);
  });
});

// ─── Schema.org JSON-LD structured data (Task 15.1.2) ──────────────────────────
// Money rule under test: the platform transacts in RIAL (ADR 0001), so `price` is the raw Rial
// integer with priceCurrency 'IRR'. Never Toman (1 Toman = 10 Rial) and never rialToToman()'d.

const SD_ORIGIN = 'https://shop.example';

const variant = (overrides = {}) => ({
  id: 1,
  sku: 'SRM-VC-30',
  price: 4_990_000, // Rial. A Toman conversion would be 499_000.
  effective_price: 4_490_000, // flash-sale price: must NOT be what is advertised
  stock: 5,
  is_active: true,
  ...overrides,
});

const SD_PRODUCT = {
  ...FA_PRODUCT,
  slug: 'serum-vitamin-c',
  price: 4_990_000,
  stock: 5,
  rating: '4.5', // DRF serialises the decimal as a string
  reviews_count: 12,
  thumbnail_url: `${SD_ORIGIN}/media/thumb.jpg`,
  images: [{ id: 1, image: `${SD_ORIGIN}/media/a.jpg` }, { id: 2, image: `${SD_ORIGIN}/media/b.jpg` }],
  variants: [variant()],
};

const build = (overrides = {}) =>
  buildProductStructuredData({ ...SD_PRODUCT, ...overrides }, { origin: SD_ORIGIN });

describe('buildProductStructuredData', () => {
  describe('single-variant product', () => {
    it('is valid, parseable JSON with a plain Product + Offer', () => {
      const data = build();
      const roundTripped = JSON.parse(JSON.stringify(data));

      expect(roundTripped).toEqual(data); // nothing lost / undefined / NaN on the way through
      expect(roundTripped['@context']).toBe('https://schema.org/');
      expect(roundTripped['@type']).toBe('Product');
      expect(roundTripped.name).toBe('سرم ویتامین سی');
      expect(roundTripped.offers['@type']).toBe('Offer');
    });

    it('states the price in RAW RIAL with priceCurrency IRR, never Toman-converted', () => {
      const { offers } = build();

      expect(offers.priceCurrency).toBe('IRR');
      expect(offers.price).toBe(4_990_000);
      expect(typeof offers.price).toBe('number'); // a number, not "4,990,000" or "۴٬۹۹۰٬۰۰۰"
      expect(offers.price).not.toBe(499_000); // Toman
      expect(offers.price).not.toBe(49_900_000); // the brief's deliberately-wrong ×10 variant
    });

    it('advertises the regular price, not the flash-sale effective_price', () => {
      expect(build().offers.price).toBe(4_990_000);
    });

    it('links to the real storefront route, percent-encoding a Persian slug', () => {
      expect(build().offers.url).toBe(`${SD_ORIGIN}/product/serum-vitamin-c`);
      expect(build({ slug: 'سرم-ویتامین-سی' }).offers.url).toBe(
        `${SD_ORIGIN}/product/${encodeURIComponent('سرم-ویتامین-سی')}`,
      );
    });

    it('includes brand, absolute de-duplicated images, the variant SKU and a plain-text description', () => {
      const data = build({ thumbnail_url: `${SD_ORIGIN}/media/a.jpg`, short_description: '<p>سرم   سبک</p>' });
      expect(data.brand).toEqual({ '@type': 'Brand', name: 'کلینیک' });
      expect(data.image).toEqual([`${SD_ORIGIN}/media/a.jpg`, `${SD_ORIGIN}/media/b.jpg`]);
      expect(data.sku).toBe('SRM-VC-30');
      expect(data.description).toBe('سرم سبک');
    });

    it('strips HTML tags from text fields rather than passing markup into the JSON', () => {
      const data = build({ name: 'سرم <b>ویتامین</b> سی', brand: { name: '<i>کلینیک</i>' } });
      expect(data.name).toBe('سرم ویتامین سی');
      expect(data.brand.name).toBe('کلینیک');
      expect(build({ name: 'x<script>alert(1)</script>' }).name).toBe('x alert(1)'); // inert text
    });

    it('omits fields it has no value for instead of emitting undefined/empty ones', () => {
      const data = build({ brand: null, images: [], thumbnail_url: null, short_description: '', description: '' });
      expect(data).not.toHaveProperty('brand');
      expect(data).not.toHaveProperty('image');
      expect(data).not.toHaveProperty('description');
    });
  });

  describe('multi-variant product', () => {
    const multi = [
      variant({ id: 1, sku: 'A', price: 4_990_000, stock: 0 }),
      variant({ id: 2, sku: 'B', price: 7_500_000, stock: 3 }),
      variant({ id: 3, sku: 'C', price: 6_000_000, stock: 1 }),
    ];

    it('uses an AggregateOffer with lowPrice / highPrice / offerCount when prices differ', () => {
      const { offers } = build({ variants: multi });

      expect(offers['@type']).toBe('AggregateOffer');
      expect(offers.priceCurrency).toBe('IRR');
      expect(offers.lowPrice).toBe(4_990_000);
      expect(offers.highPrice).toBe(7_500_000);
      expect(offers.offerCount).toBe(3);
      expect(offers).not.toHaveProperty('price');
    });

    it('ignores inactive variants (the detail API returns them too)', () => {
      const withInactive = [...multi, variant({ id: 4, sku: 'D', price: 100_000, stock: 50, is_active: false })];
      const { offers } = build({ variants: withInactive });

      expect(offers.lowPrice).toBe(4_990_000); // not the inactive 100_000
      expect(offers.offerCount).toBe(3);
    });

    it('falls back to a plain Offer when the active variants all share one price', () => {
      const { offers } = build({
        variants: [variant({ id: 1, sku: 'A' }), variant({ id: 2, sku: 'B' })],
      });
      expect(offers['@type']).toBe('Offer');
      expect(offers.price).toBe(4_990_000);
    });

    it('also treats "one active + several inactive" as a plain Offer', () => {
      const { offers } = build({
        variants: [variant({ id: 1 }), variant({ id: 2, price: 9_000_000, is_active: false })],
      });
      expect(offers['@type']).toBe('Offer');
      expect(offers.price).toBe(4_990_000);
    });

    it('does not guess a product-level SKU when there are several variants', () => {
      expect(build({ variants: multi })).not.toHaveProperty('sku');
    });
  });

  describe('availability', () => {
    it('is InStock when any active variant has stock', () => {
      const data = build({
        variants: [variant({ id: 1, stock: 0 }), variant({ id: 2, price: 6_000_000, stock: 2 })],
      });
      expect(data.offers.availability).toBe('https://schema.org/InStock');
    });

    it('is OutOfStock when every active variant is at zero', () => {
      const data = build({
        variants: [variant({ id: 1, stock: 0 }), variant({ id: 2, price: 6_000_000, stock: 0 })],
      });
      expect(data.offers.availability).toBe('https://schema.org/OutOfStock');
    });

    it('does not count stock held by an inactive variant', () => {
      const data = build({
        variants: [variant({ id: 1, stock: 0 }), variant({ id: 2, stock: 40, is_active: false })],
      });
      expect(data.offers.availability).toBe('https://schema.org/OutOfStock');
    });

    it('also applies to an AggregateOffer', () => {
      const data = build({
        variants: [variant({ id: 1, stock: 0 }), variant({ id: 2, price: 6_000_000, stock: 0 })],
      });
      expect(data.offers['@type']).toBe('AggregateOffer');
      expect(data.offers.availability).toBe('https://schema.org/OutOfStock');
    });

    it('uses the legacy product price/stock for a product with no variants at all', () => {
      const inStock = build({ variants: [], price: 3_000_000, stock: 4 });
      expect(inStock.offers).toMatchObject({ '@type': 'Offer', price: 3_000_000 });
      expect(inStock.offers.availability).toBe('https://schema.org/InStock');
      expect(build({ variants: [], stock: 0 }).offers.availability).toBe('https://schema.org/OutOfStock');
    });
  });

  describe('aggregateRating', () => {
    it('is present with a numeric ratingValue when there are reviews', () => {
      expect(build().aggregateRating).toEqual({
        '@type': 'AggregateRating',
        ratingValue: 4.5, // "4.5" string from the API becomes a number
        reviewCount: 12,
      });
    });

    it('is omitted entirely (not a zero/null stub) when there are no reviews', () => {
      const data = build({ reviews_count: 0, rating: '0.0' });
      expect(data).not.toHaveProperty('aggregateRating');
      expect(JSON.stringify(data)).not.toContain('aggregateRating');
    });

    it.each([
      ['a zero rating', { reviews_count: 3, rating: '0.0' }],
      ['a missing rating', { reviews_count: 3, rating: null }],
      ['an out-of-range rating', { reviews_count: 3, rating: '7.2' }],
      ['a missing review count', { reviews_count: undefined, rating: '4.5' }],
    ])('is omitted for %s', (_label, overrides) => {
      expect(build(overrides)).not.toHaveProperty('aggregateRating');
    });
  });

  describe('when no valid rich result can be formed', () => {
    it('returns null without a name', () => {
      expect(buildProductStructuredData(undefined)).toBeNull();
      expect(buildProductStructuredData({ ...SD_PRODUCT, name: '  ' }, { origin: SD_ORIGIN })).toBeNull();
    });

    it('returns null when there is neither an offer nor a rating to state (Google rejects that)', () => {
      expect(build({ variants: [], price: null, reviews_count: 0 })).toBeNull();
    });

    it('still renders with a rating alone when no price can be stated', () => {
      const data = build({ variants: [], price: null });
      expect(data).not.toHaveProperty('offers');
      expect(data.aggregateRating.reviewCount).toBe(12);
    });
  });

  describe('serializeJsonLd', () => {
    it('round-trips through JSON.parse', () => {
      const data = build();
      expect(JSON.parse(serializeJsonLd(data))).toEqual(data);
    });

    it('escapes "<" so text can never close the <script> element, and loses nothing', () => {
      const hostile = { name: 'x</script><script>alert(1)</script>', note: 'a\u2028b\u2029c' };
      const json = serializeJsonLd(hostile);
      expect(json).not.toContain('<');
      expect(json).not.toMatch(/[\u2028\u2029]/);
      expect(JSON.parse(json)).toEqual(hostile); // lossless
    });

    it('still protects a "<" that survives tag-stripping in the builder', () => {
      const json = serializeJsonLd(build({ name: 'سرم </script' })); // no ">" so not a "tag"
      expect(json).not.toContain('<');
      expect(JSON.parse(json).name).toBe('سرم </script');
    });

    it('returns an empty string for no data', () => {
      expect(serializeJsonLd(null)).toBe('');
    });
  });
});

describe('ProductDetails structured data in the page', () => {
  // An earlier test in this file replaces window.location with `{ href: '' }` and never restores
  // it, so don't rely on the global: pin a known origin for these tests and put things back.
  const savedLocation = window.location;
  beforeEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { origin: SD_ORIGIN, href: `${SD_ORIGIN}/` },
    });
  });
  afterEach(() => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: savedLocation,
    });
  });

  const ldScripts = () => Array.from(document.querySelectorAll('script[type="application/ld+json"]'));

  const renderPage = () =>
    render(
      <WithSeo>
        <MemoryRouter initialEntries={['/product/serum-vitamin-c']}>
          <Routes>
            <Route path="/product/:slug" element={<ProductDetails />} />
          </Routes>
        </MemoryRouter>
      </WithSeo>,
    );

  it('renders one parseable application/ld+json block that round-trips to the builder output', async () => {
    api.getProductDetails.mockReturnValue(resolveWith(SD_PRODUCT));
    renderPage();

    await waitFor(() => expect(ldScripts()).toHaveLength(1));
    const parsed = JSON.parse(ldScripts()[0].textContent);

    const expected = JSON.parse(
      JSON.stringify(buildProductStructuredData(SD_PRODUCT, { origin: SD_ORIGIN })),
    );
    expect(parsed).toEqual(expected);
    expect(parsed['@type']).toBe('Product');
    expect(parsed.name).toBe('سرم ویتامین سی');
    expect(parsed.offers).toMatchObject({ '@type': 'Offer', priceCurrency: 'IRR', price: 4_990_000 });
    expect(parsed.offers.url).toBe(`${SD_ORIGIN}/product/serum-vitamin-c`);
    expect(parsed.aggregateRating.reviewCount).toBe(12);
  });

  it('renders an AggregateOffer on the page for a multi-variant product', async () => {
    api.getProductDetails.mockReturnValue(
      resolveWith({
        ...SD_PRODUCT,
        variants: [variant({ id: 1, sku: 'A' }), variant({ id: 2, sku: 'B', price: 7_500_000 })],
      }),
    );
    renderPage();

    await waitFor(() => expect(ldScripts()).toHaveLength(1));
    expect(JSON.parse(ldScripts()[0].textContent).offers).toMatchObject({
      '@type': 'AggregateOffer',
      lowPrice: 4_990_000,
      highPrice: 7_500_000,
    });
  });

  it('is absent while the product is loading and after a failed load', async () => {
    api.getProductDetails.mockReturnValue(new Promise(() => { }));
    api.getRelatedProducts.mockReturnValue(new Promise(() => { }));
    const { unmount } = renderPage();
    await waitFor(() => expect(document.title).toBe(DEFAULT_TITLE));
    expect(ldScripts()).toHaveLength(0);
    unmount();

    api.getProductDetails.mockImplementation(() => rejectWith(404, 'Not Found'));
    api.getRelatedProducts.mockReturnValue(resolveWith([]));
    renderPage();
    expect(await screen.findByText(/product not found/i)).toBeInTheDocument();
    expect(ldScripts()).toHaveLength(0);
  });

  it('is removed again when the visitor leaves the product page', async () => {
    api.getProductDetails.mockReturnValue(resolveWith(SD_PRODUCT));
    const { unmount } = renderPage();
    await waitFor(() => expect(ldScripts()).toHaveLength(1));
    unmount();
    await waitFor(() => expect(ldScripts()).toHaveLength(0));
  });

  it('cannot be broken out of by hostile text (no raw "<" in the script body)', async () => {
    // No ">" so tag-stripping leaves the "<" in place: the serializer's escaping is what protects.
    api.getProductDetails.mockReturnValue(
      resolveWith({ ...SD_PRODUCT, name: 'سرم </script', short_description: 'a </script><b' }),
    );
    renderPage();

    await waitFor(() => expect(ldScripts()).toHaveLength(1));
    const body = ldScripts()[0].textContent;
    expect(body).not.toContain('<');
    expect(JSON.parse(body).name).toBe('سرم </script'); // lossless after parsing
    expect(ldScripts()[0].outerHTML.match(/<\/script>/g)).toHaveLength(1); // only its own closer
    expect(document.querySelectorAll('script:not([type])')).toHaveLength(0); // nothing injected
  });
});

// ─── Open Graph tags (Task 15.1.3) ──────────────────────────────────────────────
// What a link-preview crawler that DOES run JavaScript sees in the real document <head>.

describe('ProductDetails Open Graph tags', () => {
  let restoreLocation;
  beforeEach(() => {
    restoreLocation = stubLocationOrigin(SD_ORIGIN);
  });
  afterEach(() => restoreLocation());

  const renderPage = () =>
    render(
      <WithSeo>
        <MemoryRouter initialEntries={['/product/serum-vitamin-c']}>
          <Routes>
            <Route path="/product/:slug" element={<ProductDetails />} />
          </Routes>
        </MemoryRouter>
      </WithSeo>,
    );
  const first = (property) => headMeta(property)[0];

  it('renders the product-specific og:* tags with the expected values', async () => {
    api.getProductDetails.mockReturnValue(resolveWith(SD_PRODUCT));
    renderPage();

    await waitFor(() => expect(first('og:type')).toBe('product'));
    expect(first('og:title')).toBe('سرم ویتامین سی'); // the bare product name
    expect(first('og:url')).toBe(`${SD_ORIGIN}/product/serum-vitamin-c`);
    expect(first('og:image')).toBe(`${SD_ORIGIN}/media/thumb.jpg`);
    expect(first('og:image:alt')).toBe('سرم ویتامین سی');
    expect(first('product:price:amount')).toBe('4990000'); // raw Rial, not Toman
    expect(first('product:price:currency')).toBe('IRR');
    // The site-wide tags must survive the default block stepping aside.
    expect(first('og:site_name')).toBe('Chiz');
    expect(first('og:locale')).toBe('fa_IR');
  });

  it('uses the SAME description for og:description and <meta name="description">', async () => {
    api.getProductDetails.mockReturnValue(resolveWith(SD_PRODUCT));
    renderPage();

    // The default block already supplies og:* while loading, so wait for the PRODUCT's own tags.
    await waitFor(() => expect(first('og:type')).toBe('product'));
    await waitFor(() => expect(headDescriptions()).toHaveLength(1));
    expect(first('og:description')).toBe(headDescriptions()[0].getAttribute('content'));
    expect(first('og:description')).toBe(buildProductMetaDescription(SD_PRODUCT));
  });

  it('emits an ABSOLUTE og:image URL, resolving a relative API path against the site origin', async () => {
    api.getProductDetails.mockReturnValue(
      resolveWith({ ...SD_PRODUCT, thumbnail_url: null, images: [{ id: 1, image: '/media/rel.jpg' }] }),
    );
    renderPage();

    await waitFor(() => expect(first('og:type')).toBe('product'));
    const image = first('og:image');
    expect(image).toBe(`${SD_ORIGIN}/media/rel.jpg`);
    expect(['http:', 'https:']).toContain(new URL(image).protocol); // new URL() with no base: throws if relative
  });

  it('falls back to the branded default image for a product with no images, not a missing/broken tag', async () => {
    api.getProductDetails.mockReturnValue(
      resolveWith({ ...SD_PRODUCT, thumbnail_url: null, images: [] }),
    );
    renderPage();

    await waitFor(() => expect(first('og:type')).toBe('product'));
    expect(headMeta('og:image')).toEqual([`${SD_ORIGIN}/og-default.jpg`]);
    expect(first('og:image:width')).toBe('1200');
    expect(first('og:image:height')).toBe('630');
    expect(first('og:image:alt')).toBe('Chiz');
  });

  it('has each og:* / product:* property exactly once (the default block steps aside)', async () => {
    api.getProductDetails.mockReturnValue(resolveWith(SD_PRODUCT));
    renderPage();

    await waitFor(() => expect(first('og:type')).toBe('product'));
    const props = headOgProperties();
    expect(props.length).toBeGreaterThan(0);
    expect(props.filter((p, i) => props.indexOf(p) !== i)).toEqual([]); // no duplicates
  });

  it('states the lowest regular price for a multi-variant product', async () => {
    api.getProductDetails.mockReturnValue(
      resolveWith({
        ...SD_PRODUCT,
        variants: [variant({ id: 1, sku: 'A' }), variant({ id: 2, sku: 'B', price: 7_500_000 })],
      }),
    );
    renderPage();

    await waitFor(() => expect(first('product:price:amount')).toBe('4990000'));
  });

  it('leaves out the price tags entirely (no "undefined") when no price can be determined', async () => {
    api.getProductDetails.mockReturnValue(resolveWith({ ...SD_PRODUCT, variants: [], price: null }));
    renderPage();

    await waitFor(() => expect(first('og:type')).toBe('product'));
    expect(headMeta('product:price:amount')).toEqual([]);
    expect(headMeta('product:price:currency')).toEqual([]);
    expect(document.head.innerHTML).not.toMatch(/content="(undefined|null)"/);
  });

  it('shows the sitewide website/default-image tags while loading, with no product:* tags', async () => {
    api.getProductDetails.mockReturnValue(new Promise(() => { }));
    api.getRelatedProducts.mockReturnValue(new Promise(() => { }));
    renderPage();

    await waitFor(() => expect(first('og:type')).toBe('website'));
    expect(first('og:title')).toBe(DEFAULT_TITLE);
    expect(first('og:image')).toBe(`${SD_ORIGIN}/og-default.jpg`);
    expect(headOgProperties().filter((p) => p.startsWith('product:'))).toEqual([]);
  });
});

// ─── Canonical link (Task 15.1.4) ────────────────────────────────────────────────

describe('ProductDetails canonical link', () => {
  let restoreLocation;
  beforeEach(() => {
    restoreLocation = stubLocationOrigin(SD_ORIGIN);
  });
  afterEach(() => restoreLocation());

  const renderAt = (url) =>
    render(
      <WithSeo>
        <MemoryRouter initialEntries={[url]}>
          <Routes>
            <Route path="/product/:slug" element={<ProductDetails />} />
          </Routes>
        </MemoryRouter>
      </WithSeo>,
    );

  it('points at the clean /product/<slug> URL', async () => {
    api.getProductDetails.mockReturnValue(resolveWith(SD_PRODUCT));
    renderAt('/product/serum-vitamin-c');

    await waitFor(() => expect(headCanonicals()).toEqual([`${SD_ORIGIN}/product/serum-vitamin-c`]));
    expect(headRobots()).toEqual([]); // product pages are meant to be indexed
  });

  it('drops tracking and variant query parameters, and agrees with og:url', async () => {
    api.getProductDetails.mockReturnValue(resolveWith(SD_PRODUCT));
    renderAt('/product/serum-vitamin-c?utm_source=telegram&variant=3&ref=abc');

    await waitFor(() => expect(headCanonicals()).toEqual([`${SD_ORIGIN}/product/serum-vitamin-c`]));
    await waitFor(() => expect(headMeta('og:url')).toEqual(headCanonicals()));
  });

  it('declares itself as fa-ir and x-default at that same URL (exactly two, no duplicates)', async () => {
    api.getProductDetails.mockReturnValue(resolveWith(SD_PRODUCT));
    renderAt('/product/serum-vitamin-c?utm_source=telegram');

    const url = `${SD_ORIGIN}/product/serum-vitamin-c`;
    await waitFor(() => expect(headCanonicals()).toEqual([url]));
    expect(headHreflangs()).toEqual([
      { hreflang: 'fa-ir', href: url },
      { hreflang: 'x-default', href: url },
    ]);
  });

  it('percent-encodes a Persian slug', async () => {
    api.getProductDetails.mockReturnValue(resolveWith({ ...SD_PRODUCT, slug: 'سرم-ویتامین-سی' }));
    renderAt('/product/' + encodeURIComponent('سرم-ویتامین-سی'));

    await waitFor(() =>
      expect(headCanonicals()).toEqual([
        `${SD_ORIGIN}/product/${encodeURIComponent('سرم-ویتامین-سی')}`,
      ]),
    );
  });
});

