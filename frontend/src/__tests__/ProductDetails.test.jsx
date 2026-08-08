import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import ProductDetails from '../pages/ProductDetails';
import * as api from '../services/api';
import { useCart } from '../context/CartContext';
import { useWishlist } from '../context/WishlistContext';

// ─── Module mocks ──────────────────────────────────────────────────────────────

vi.mock('../services/api', () => ({
  getProductDetails: vi.fn(),
  getRelatedProducts: vi.fn(),
  createReview: vi.fn(),
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
  price: '49.99',
  original_price: '69.99',
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
    price: '29.99',
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
    price: '39.99',
    rating: '3.5',
    thumbnail_url: '/assets/img/product/product-3.webp',
    category: { name: 'Widgets' },
    is_sale: true,
    is_new: false,
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
      expect(await screen.findByText('$49.99')).toBeInTheDocument();
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
      expect(await screen.findByText('$29.99')).toBeInTheDocument();
      expect(await screen.findByText('$39.99')).toBeInTheDocument();
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
});
