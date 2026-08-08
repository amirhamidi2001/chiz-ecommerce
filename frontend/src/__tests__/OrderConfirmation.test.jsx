import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import OrderConfirmation from '../pages/OrderConfirmation';

// ─── Mock: API layer ──────────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  getOrderDetail: vi.fn(),
  isAuthenticated: vi.fn(() => true),
}));

// ─── Mock: CartContext ────────────────────────────────────────────────────────
vi.mock('../context/CartContext', () => ({
  useCart: () => ({ fetchCart: vi.fn() }),
}));

import { getOrderDetail } from '../services/api';

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Wraps <OrderConfirmation /> in the router setup required for useParams()
 * to receive the `id` param.
 */
const renderWithRoute = (orderId = '123') =>
  render(
    <MemoryRouter initialEntries={[`/order-confirmation/${orderId}`]}>
      <Routes>
        <Route
          path="/order-confirmation/:id"
          element={<OrderConfirmation />}
        />
      </Routes>
    </MemoryRouter>,
  );

/** Minimal order fixture that satisfies every field the component reads. */
const buildOrder = (overrides = {}) => ({
  id: 123,
  order_number: 'ORD-2024-0042',
  status: 'pending',
  created_at: '2024-06-01T10:00:00Z',
  first_name: 'Jane',
  email: 'jane@example.com',
  full_name: 'Jane Doe',
  phone: '+1 555-0100',
  notes: '',
  // financial
  subtotal: '89.99',
  shipping_cost: '5.00',
  tax: '7.20',
  discount: '0.00',
  total: '102.19',
  // shipping address
  shipping_address: '123 Main St',
  shipping_apartment: '',
  shipping_city: 'Springfield',
  shipping_state: 'IL',
  shipping_zip: '62701',
  shipping_country: 'US',
  // payment
  payment_method: 'credit_card',
  payment_display: 'Visa',
  card_last_four: '4242',
  billing_same_as_shipping: true,
  // items
  items: [
    {
      id: 1,
      product_name: 'Wireless Headphones',
      product_slug: 'wireless-headphones',
      product_image: null,
      quantity: 2,
      unit_price: '39.99',
      subtotal: '79.98',
    },
    {
      id: 2,
      product_name: 'Phone Case',
      product_slug: 'phone-case',
      product_image: null,
      quantity: 1,
      unit_price: '9.99',
      subtotal: '9.99',
    },
  ],
  ...overrides,
});

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('OrderConfirmation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── Loading ─────────────────────────────────────────────────────────────────
  describe('loading', () => {
    it('shows a loading spinner while the order is being fetched', () => {
      // Never resolves during this test
      getOrderDetail.mockReturnValue(new Promise(() => { }));

      renderWithRoute();

      // The spinner is a plain animated div — query by its role if available,
      // otherwise confirm the success / error content is absent while loading.
      expect(screen.queryByText(/thanks for your order/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/order not found/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/failed to load/i)).not.toBeInTheDocument();
    });
  });

  // ── Success ─────────────────────────────────────────────────────────────────
  describe('success', () => {
    beforeEach(() => {
      getOrderDetail.mockResolvedValue({ data: buildOrder() });
    });

    it('renders the success heading with the customer name', async () => {
      renderWithRoute();

      await screen.findByText(/thanks for your order, jane/i);
    });

    it('renders the order number', async () => {
      renderWithRoute();

      const orderNumberElements = await screen.findAllByText(/ORD-2024-0042/);
      expect(orderNumberElements.length).toBeGreaterThan(0);
    });

    it('renders the order total', async () => {
      renderWithRoute();

      // Total appears in the financial summary sidebar
      await screen.findByText('$102.19');
    });

    it('renders subtotal, shipping cost, and tax line items', async () => {
      renderWithRoute();

      await screen.findByText('$89.99');  // subtotal
      await screen.findByText('$5.00');   // shipping
      await screen.findByText('$7.20');   // tax
    });

    it('renders a discount row only when a discount is applied', async () => {
      getOrderDetail.mockResolvedValue({
        data: buildOrder({ discount: '15.00' }),
      });

      renderWithRoute();

      await screen.findByText(/-\$15\.00/);
    });

    it('does not render a discount row when discount is zero', async () => {
      renderWithRoute();

      await screen.findByText(/thanks for your order/i);
      expect(screen.queryByText(/-\$0\.00/)).not.toBeInTheDocument();
    });

    it('renders all order items with name, quantity, unit price, and subtotal', async () => {
      renderWithRoute();

      await screen.findByText('Wireless Headphones');
      expect(screen.getByText(/2 × \$39\.99/)).toBeInTheDocument();
      expect(screen.getByText(/\$79\.98/)).toBeInTheDocument();

      expect(screen.getByText('Phone Case')).toBeInTheDocument();
      expect(screen.getByText(/1 × \$9\.99/)).toBeInTheDocument();
    });

    it('renders shipping address details', async () => {
      renderWithRoute();

      await screen.findByText('Jane Doe');
      expect(screen.getByText(/123 Main St/)).toBeInTheDocument();
      expect(screen.getByText(/Springfield/)).toBeInTheDocument();
      expect(screen.getByText(/62701/)).toBeInTheDocument();
    });

    it('renders contact email and phone', async () => {
      renderWithRoute();

      const emailElements = await screen.findAllByText(/jane@example\.com/i);
      expect(emailElements.length).toBeGreaterThan(0);

      expect(screen.getByText('+1 555-0100')).toBeInTheDocument();
    });

    it('renders payment information', async () => {
      renderWithRoute();

      await screen.findByText('Visa');
      expect(screen.getByText(/4242/)).toBeInTheDocument();
      expect(screen.getByText(/same as shipping address/i)).toBeInTheDocument();
    });

    it('shows the order item count in the section title', async () => {
      renderWithRoute();

      await screen.findByText(/order items \(2\)/i);
    });

    it('shows the correct order status label', async () => {
      renderWithRoute();

      // "Pending" appears in both the status badge and the progress stepper.
      const statusLabels = await screen.findAllByText(/pending/i);
      expect(statusLabels.length).toBeGreaterThan(0);
    });

    it('renders an "Order Cancelled" heading for a cancelled order', async () => {
      getOrderDetail.mockResolvedValue({
        data: buildOrder({ status: 'cancelled' }),
      });

      renderWithRoute();

      await screen.findByText(/order cancelled/i);
      expect(screen.queryByText(/thanks for your order/i)).not.toBeInTheDocument();
    });

    it('renders "Order Confirmation" page title', async () => {
      renderWithRoute();

      await screen.findByText('Order Confirmation');
    });

    it('renders a breadcrumb containing the order number', async () => {
      renderWithRoute();

      await screen.findByText(/Order #ORD-2024-0042/);
    });
  });

  // ── Routing ─────────────────────────────────────────────────────────────────
  describe('routing', () => {
    it('passes the orderId from the URL to the API call', async () => {
      getOrderDetail.mockResolvedValue({ data: buildOrder() });

      renderWithRoute('456');

      await screen.findByText(/thanks for your order/i);

      expect(getOrderDetail).toHaveBeenCalledWith('456');
    });

    it('calls the API exactly once on mount', async () => {
      getOrderDetail.mockResolvedValue({ data: buildOrder() });

      renderWithRoute();

      await screen.findByText(/thanks for your order/i);

      expect(getOrderDetail).toHaveBeenCalledTimes(1);
    });
  });

  // ── Error state ─────────────────────────────────────────────────────────────
  describe('error', () => {
    it('shows "Order not found." when the API returns a 404', async () => {
      const notFoundError = { response: { status: 404 } };
      getOrderDetail.mockRejectedValue(notFoundError);

      renderWithRoute();

      await screen.findByText('Order not found.');
    });

    it('shows a generic error message for non-404 API failures', async () => {
      const serverError = { response: { status: 500 } };
      getOrderDetail.mockRejectedValue(serverError);

      renderWithRoute();

      await screen.findByText(/failed to load order details/i);
    });

    it('shows a generic error message for network failures (no response object)', async () => {
      getOrderDetail.mockRejectedValue(new Error('Network Error'));

      renderWithRoute();

      await screen.findByText(/failed to load order details/i);
    });

    it('renders a "My Orders" link on the error screen', async () => {
      getOrderDetail.mockRejectedValue({ response: { status: 404 } });

      renderWithRoute();

      await screen.findByText('Order not found.');

      const myOrdersLink = screen.getByRole('link', { name: /my orders/i });
      expect(myOrdersLink).toHaveAttribute('href', '/account');
    });

    it('renders a "Go Back" button on the error screen', async () => {
      getOrderDetail.mockRejectedValue({ response: { status: 404 } });

      renderWithRoute();

      await screen.findByText('Order not found.');

      expect(screen.getByRole('button', { name: /go back/i })).toBeInTheDocument();
    });

    it('does not render order details when an error occurs', async () => {
      getOrderDetail.mockRejectedValue({ response: { status: 404 } });

      renderWithRoute();

      await screen.findByText('Order not found.');

      expect(screen.queryByText(/thanks for your order/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/order summary/i)).not.toBeInTheDocument();
    });
  });

  // ── Navigation ───────────────────────────────────────────────────────────────
  describe('navigation', () => {
    beforeEach(() => {
      getOrderDetail.mockResolvedValue({ data: buildOrder() });
    });

    it('"Return to Shop" links point to /category', async () => {
      renderWithRoute();

      await screen.findByText(/thanks for your order/i);

      const shopLinks = screen.getAllByRole('link', { name: /return to shop/i });
      shopLinks.forEach((link) => {
        expect(link).toHaveAttribute('href', '/category');
      });
    });

    it('"Browse All Products" link points to /category', async () => {
      renderWithRoute();

      await screen.findByText(/thanks for your order/i);

      const browseLink = screen.getByRole('link', { name: /browse all products/i });
      expect(browseLink).toHaveAttribute('href', '/category');
    });

    it('"View All Orders" link points to /account?tab=orders', async () => {
      renderWithRoute();

      await screen.findByText(/thanks for your order/i);

      const viewOrdersLink = screen.getByRole('link', { name: /view all orders/i });
      expect(viewOrdersLink).toHaveAttribute('href', '/account?tab=orders');
    });

    it('"Track My Orders" link points to /account?tab=orders', async () => {
      renderWithRoute();

      await screen.findByText(/thanks for your order/i);

      const trackLink = screen.getByRole('link', { name: /track my orders/i });
      expect(trackLink).toHaveAttribute('href', '/account?tab=orders');
    });

    it('"Home" breadcrumb link points to /', async () => {
      renderWithRoute();

      await screen.findByText(/thanks for your order/i);

      const homeLink = screen.getByRole('link', { name: /^home$/i });
      expect(homeLink).toHaveAttribute('href', '/');
    });

    it('"Contact Support" link points to /contact', async () => {
      renderWithRoute();

      await screen.findByText(/thanks for your order/i);

      const contactLink = screen.getByRole('link', { name: /contact support/i });
      expect(contactLink).toHaveAttribute('href', '/contact');
    });

    it('"FAQs" link points to /faq', async () => {
      renderWithRoute();

      await screen.findByText(/thanks for your order/i);

      const faqLink = screen.getByRole('link', { name: /faqs/i });
      expect(faqLink).toHaveAttribute('href', '/faq');
    });

    it('each order item name links to the correct product page', async () => {
      renderWithRoute();

      await screen.findByText('Wireless Headphones');

      const productLink = screen.getByRole('link', { name: /wireless headphones/i });
      expect(productLink).toHaveAttribute('href', '/product/wireless-headphones');
    });

    it('CollapsibleCard sections toggle open and closed when clicked', async () => {
      const user = userEvent.setup();
      renderWithRoute();

      await screen.findByText(/thanks for your order/i);

      // "Shipping Details" section is open by default — its content is visible
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();

      // Click the section header to collapse it
      const shippingHeader = screen.getByRole('button', { name: /shipping details/i });
      await user.click(shippingHeader);

      // Content should now be hidden
      await waitFor(() => {
        expect(screen.queryByText('Jane Doe')).not.toBeInTheDocument();
      });

      // Click again to re-open
      await user.click(shippingHeader);
      await screen.findByText('Jane Doe');
    });
  });
});
