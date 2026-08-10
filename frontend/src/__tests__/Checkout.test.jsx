import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Checkout from '../pages/Checkout';

// ─── Mocks ────────────────────────────────────────────────────────────────────

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('../context/CartContext', () => ({
  useCart: vi.fn(),
}));

vi.mock('../services/api', () => ({
  createOrder: vi.fn(),
  isAuthenticated: vi.fn(),
}));

import { useCart } from '../context/CartContext';
import { createOrder, isAuthenticated } from '../services/api';

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const MOCK_ITEMS = [
  {
    id: 1,
    quantity: 2,
    unit_price: '19.99',
    subtotal: '39.98',
    product: { id: 10, name: 'Test Widget', image: null },
  },
  {
    id: 2,
    quantity: 1,
    unit_price: '49.99',
    subtotal: '49.99',
    product: { id: 11, name: 'Premium Gadget', image: 'https://example.com/img.jpg' },
  },
];

const MOCK_CART = {
  subtotal: '89.97',
  total_items: 3,
  items: MOCK_ITEMS,
};

const CART_LOADING_STATE = {
  cart: null,
  loading: true,
  error: null,
  fetchCart: vi.fn(),
  clearCart: vi.fn(),
};

const CART_READY_STATE = {
  cart: MOCK_CART,
  loading: false,
  error: null,
  fetchCart: vi.fn(),
  clearCart: vi.fn(),
};

const CART_EMPTY_STATE = {
  cart: { subtotal: '0.00', total_items: 0, items: [] },
  loading: false,
  error: null,
  fetchCart: vi.fn(),
  clearCart: vi.fn(),
};

// ─── Query helpers ────────────────────────────────────────────────────────────
//
// The Field component renders a plain <label> (no htmlFor) and a sibling
// <input> (no id), so there is no programmatic label association.
// RTL's getByRole({ name }) and getByLabelText both rely on that association
// and therefore cannot find these inputs.
//
// Instead we query by the `name` attribute, which is unique per field and
// directly maps to the controlled form state used in handleSubmit.

const byName = (name) => document.querySelector(`[name="${name}"]`);

// ─── Form filler ──────────────────────────────────────────────────────────────

/**
 * Fills every required field and accepts the terms checkbox.
 * Requires credit_card as the active payment method (the default).
 */
const fillValidForm = async (user) => {
  // ── Customer Information ──────────────────────────────────────────────────
  await user.type(byName('firstName'), 'Jane');
  await user.type(byName('lastName'), 'Doe');
  await user.type(byName('email'), 'jane@example.com');
  await user.type(byName('phone'), '555-0100');

  // ── Shipping Address ──────────────────────────────────────────────────────
  await user.type(byName('address'), '123 Main St');
  await user.type(byName('city'), 'Springfield');
  await user.type(byName('state'), 'IL');
  await user.type(byName('zip'), '62701');

  // ── Credit card ───────────────────────────────────────────────────────────
  // Card number uses a custom handler (no name attr); query by placeholder.
  await user.type(screen.getByPlaceholderText('1234 5678 9012 3456'), '1234567890123456');
  // Expiry also uses a custom handler; query by placeholder.
  await user.type(screen.getByPlaceholderText('MM/YY'), '1227');
  await user.type(byName('cvv'), '321');
  // "Name on Card" input uses name="name"
  await user.type(byName('name'), 'Jane Doe');

  // ── Terms ─────────────────────────────────────────────────────────────────
  await user.click(byName('terms'));
};

// ─── Render helper ────────────────────────────────────────────────────────────

const renderCheckout = () =>
  render(
    <MemoryRouter>
      <Checkout />
    </MemoryRouter>,
  );

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('Checkout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    isAuthenticated.mockReturnValue(true);
    useCart.mockReturnValue(CART_READY_STATE);
  });

  // ── Auth ──────────────────────────────────────────────────────────────────

  describe('auth', () => {
    it('redirects to /login when the user is not authenticated', () => {
      isAuthenticated.mockReturnValue(false);
      renderCheckout();

      expect(mockNavigate).toHaveBeenCalledWith('/login?redirect=/checkout');
    });

    it('does NOT redirect when the user is authenticated', () => {
      isAuthenticated.mockReturnValue(true);
      renderCheckout();

      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('calls fetchCart on mount when authenticated', () => {
      const fetchCart = vi.fn();
      useCart.mockReturnValue({ ...CART_READY_STATE, fetchCart });
      renderCheckout();

      expect(fetchCart).toHaveBeenCalledOnce();
    });
  });

  // ── Loading ───────────────────────────────────────────────────────────────

  describe('loading', () => {
    it('shows skeleton placeholders while the cart is loading', () => {
      useCart.mockReturnValue(CART_LOADING_STATE);
      const { container } = renderCheckout();

      const skeletons = container.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('disables the Place Order button while the cart is loading', () => {
      useCart.mockReturnValue(CART_LOADING_STATE);
      renderCheckout();

      const btn = screen.queryByRole('button', { name: /place order/i });
      if (btn) {
        expect(btn).toBeDisabled();
      }
    });
  });

  // ── Empty cart ────────────────────────────────────────────────────────────

  describe('empty cart', () => {
    it('shows an empty cart message when cart has no items', () => {
      useCart.mockReturnValue(CART_EMPTY_STATE);
      renderCheckout();

      expect(screen.getByText(/your cart is empty/i)).toBeInTheDocument();
    });

    it('shows a link to continue shopping when cart is empty', () => {
      useCart.mockReturnValue(CART_EMPTY_STATE);
      renderCheckout();

      expect(screen.getByRole('link', { name: /continue shopping/i })).toBeInTheDocument();
    });

    it('does NOT show the checkout form when cart is empty', () => {
      useCart.mockReturnValue(CART_EMPTY_STATE);
      renderCheckout();

      // The submit button only renders inside the checkout form
      expect(screen.queryByText(/place order/i)).not.toBeInTheDocument();
    });
  });

  // ── Render ────────────────────────────────────────────────────────────────

  describe('render', () => {
    it('renders the page heading', () => {
      renderCheckout();
      expect(screen.getByRole('heading', { name: /^checkout$/i })).toBeInTheDocument();
    });

    it('renders all required form fields', () => {
      renderCheckout();

      // Queried by name attribute because Field renders label + input as
      // unassociated siblings (no htmlFor / id pairing).
      expect(byName('firstName')).toBeInTheDocument();
      expect(byName('lastName')).toBeInTheDocument();
      expect(byName('email')).toBeInTheDocument();
      expect(byName('phone')).toBeInTheDocument();
      expect(byName('address')).toBeInTheDocument();
      expect(byName('city')).toBeInTheDocument();
      expect(byName('state')).toBeInTheDocument();
      expect(byName('zip')).toBeInTheDocument();
    });

    it('renders payment method labels for each option', () => {
      renderCheckout();

      expect(screen.getByText(/credit \/ debit card/i)).toBeInTheDocument();
      expect(screen.getByText(/paypal/i)).toBeInTheDocument();
      expect(screen.getByText(/apple pay/i)).toBeInTheDocument();
    });

    it('renders credit card fields when credit_card is the selected payment method (default)', () => {
      renderCheckout();

      // Card number: no name attr, identified by its unique placeholder
      expect(screen.getByPlaceholderText('1234 5678 9012 3456')).toBeInTheDocument();
      // Expiry: no name attr, identified by its placeholder
      expect(screen.getByPlaceholderText('MM/YY')).toBeInTheDocument();
      // CVV and card name have name attrs
      expect(byName('cvv')).toBeInTheDocument();
      expect(byName('name')).toBeInTheDocument();
    });

    it('renders the Order Summary heading', () => {
      renderCheckout();
      expect(screen.getByText(/order summary/i)).toBeInTheDocument();
    });

    it('displays each cart item name in the order summary', () => {
      renderCheckout();

      expect(screen.getByText('Test Widget')).toBeInTheDocument();
      expect(screen.getByText('Premium Gadget')).toBeInTheDocument();
    });

    it('displays subtotal, shipping, and tax rows in the order summary', () => {
      renderCheckout();

      expect(screen.getByText('$89.97')).toBeInTheDocument();
      expect(screen.getByText('$9.99')).toBeInTheDocument();
      expect(screen.getByText(/tax \(10%\)/i)).toBeInTheDocument();
    });

    it('renders the Place Order submit button', () => {
      renderCheckout();
      expect(screen.getByRole('button', { name: /place order/i })).toBeInTheDocument();
    });

    it('renders the terms & conditions checkbox', () => {
      renderCheckout();
      expect(byName('terms')).toBeInTheDocument();
    });
  });

  // ── Form interaction ──────────────────────────────────────────────────────

  describe('form interaction', () => {
    it('allows the user to type into customer information fields', async () => {
      const user = userEvent.setup();
      renderCheckout();

      await user.type(byName('firstName'), 'Alice');
      expect(byName('firstName')).toHaveValue('Alice');

      await user.type(byName('email'), 'alice@example.com');
      expect(byName('email')).toHaveValue('alice@example.com');

      await user.type(byName('city'), 'Chicago');
      expect(byName('city')).toHaveValue('Chicago');
    });

    it('allows the user to type a phone number (tel input)', async () => {
      const user = userEvent.setup();
      renderCheckout();

      await user.type(byName('phone'), '312-555-0199');
      expect(byName('phone')).toHaveValue('312-555-0199');
    });

    it('allows the user to type into the street address field', async () => {
      const user = userEvent.setup();
      renderCheckout();

      await user.type(byName('address'), '456 Elm Street');
      expect(byName('address')).toHaveValue('456 Elm Street');
    });

    it('allows the user to select a country from the dropdown', async () => {
      const user = userEvent.setup();
      renderCheckout();

      // Country is a <select> (combobox role), also queryable by name attr
      const countrySelect = byName('country');
      await user.selectOptions(countrySelect, 'CA');
      expect(countrySelect).toHaveValue('CA');
    });

    it('switches payment method when a different option is clicked', async () => {
      const user = userEvent.setup();
      renderCheckout();

      // Click the PayPal label — the radio is hidden (className="hidden") so we
      // click the visible label text instead.
      await user.click(screen.getByText(/paypal/i));

      // Credit card fields should disappear
      expect(screen.queryByPlaceholderText('1234 5678 9012 3456')).not.toBeInTheDocument();
    });

    it('shows a PayPal redirect notice when PayPal is selected', async () => {
      const user = userEvent.setup();
      renderCheckout();

      await user.click(screen.getByText(/paypal/i));

      expect(screen.getByText(/redirected to paypal/i)).toBeInTheDocument();
    });

    it('shows an Apple Pay notice when Apple Pay is selected', async () => {
      const user = userEvent.setup();
      renderCheckout();

      await user.click(screen.getByText(/apple pay/i));

      expect(screen.getByText(/prompted to authorize payment with apple pay/i)).toBeInTheDocument();
    });

    it('allows the user to toggle the terms checkbox', async () => {
      const user = userEvent.setup();
      renderCheckout();

      const checkbox = byName('terms');
      expect(checkbox).not.toBeChecked();

      await user.click(checkbox);
      expect(checkbox).toBeChecked();

      await user.click(checkbox);
      expect(checkbox).not.toBeChecked();
    });

    // Promo/coupon UI was removed as part of the discount security fix
    // (Epic 9 will introduce a real, server-validated coupon system and
    // its own tests at that point) — see backend/order/serializers.py
    // and this component's Epic 9 TODO comment.
  });

  // ── Submission success ─────────────────────────────────────────────────────

  describe('submission success', () => {
    it('calls createOrder with the correct payload', async () => {
      createOrder.mockResolvedValueOnce({ data: { id: 42 } });
      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      await waitFor(() => expect(createOrder).toHaveBeenCalledOnce());

      const [payload] = createOrder.mock.calls[0];
      expect(payload).toMatchObject({
        first_name: 'Jane',
        last_name: 'Doe',
        email: 'jane@example.com',
        phone: '555-0100',
        address: '123 Main St',
        city: 'Springfield',
        state: 'IL',
        zip: '62701',
        payment_method: 'credit_card',
        card_last_four: '3456',
      });
    });

    it('navigates to /order-confirmation/:id on success', async () => {
      createOrder.mockResolvedValueOnce({ data: { id: 99 } });
      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      await waitFor(() =>
        expect(mockNavigate).toHaveBeenCalledWith('/order-confirmation/99'),
      );
    });

    it('shows "Placing Order…" text on the button while submitting', async () => {
      let resolveOrder;
      createOrder.mockImplementationOnce(
        () => new Promise((res) => { resolveOrder = res; }),
      );

      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      expect(await screen.findByText(/placing order/i)).toBeInTheDocument();

      resolveOrder({ data: { id: 1 } });
    });

    it('disables the submit button while the order is being placed', async () => {
      let resolveOrder;
      createOrder.mockImplementationOnce(
        () => new Promise((res) => { resolveOrder = res; }),
      );

      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      const btn = await screen.findByRole('button', { name: /placing order/i });
      expect(btn).toBeDisabled();

      resolveOrder({ data: { id: 1 } });
    });
  });

  // ── Validation errors ──────────────────────────────────────────────────────

  describe('validation errors', () => {
    it('shows required-field errors when the form is submitted empty', async () => {
      const user = userEvent.setup();
      renderCheckout();

      await user.click(screen.getByRole('button', { name: /place order/i }));

      // The Field component renders error text as a sibling <p> when truthy.
      // Multiple fields are required so multiple "Required" messages appear.
      const requiredMessages = await screen.findAllByText(/^required$/i);
      expect(requiredMessages.length).toBeGreaterThanOrEqual(5);
    });

    it('shows a terms error when terms are not accepted', async () => {
      const user = userEvent.setup();
      renderCheckout();

      await user.type(byName('firstName'), 'Jane');
      await user.type(byName('lastName'), 'Doe');
      await user.type(byName('email'), 'jane@example.com');
      await user.type(byName('phone'), '555-0100');
      await user.type(byName('address'), '123 Main St');
      await user.type(byName('city'), 'Springfield');
      await user.type(byName('state'), 'IL');
      await user.type(byName('zip'), '62701');
      await user.type(screen.getByPlaceholderText('1234 5678 9012 3456'), '1234567890123456');
      await user.type(screen.getByPlaceholderText('MM/YY'), '1227');
      await user.type(byName('cvv'), '321');
      await user.type(byName('name'), 'Jane Doe');
      // Deliberately do NOT check the terms checkbox

      await user.click(screen.getByRole('button', { name: /place order/i }));

      expect(
        await screen.findByText(/you must agree to the terms and conditions/i),
      ).toBeInTheDocument();
    });

    it('shows a card number error when fewer than 16 digits are entered', async () => {
      const user = userEvent.setup();
      renderCheckout();

      await user.type(screen.getByPlaceholderText('1234 5678 9012 3456'), '1234');
      await user.click(screen.getByRole('button', { name: /place order/i }));

      expect(
        await screen.findByText(/valid 16-digit card number/i),
      ).toBeInTheDocument();
    });

    it('shows an expiry format error when the value does not match MM/YY', async () => {
      const user = userEvent.setup();
      renderCheckout();

      // Type only digits — the auto-formatter inserts the slash, but an
      // incomplete entry won't match /^\d{2}\/\d{2}$/ in validate().
      await user.type(screen.getByPlaceholderText('MM/YY'), '12');
      await user.click(screen.getByRole('button', { name: /place order/i }));

      // The error text is "Use MM/YY format." — the slash in the source text
      // can cause RTL to fail with a plain regex. Use a function matcher.
      expect(
        await screen.findByText((content) => content.includes('MM/YY')),
      ).toBeInTheDocument();
    });

    it('clears a field error once the user corrects the input', async () => {
      const user = userEvent.setup();
      renderCheckout();

      // Trigger full validation
      await user.click(screen.getByRole('button', { name: /place order/i }));
      const initialErrors = await screen.findAllByText(/^required$/i);
      const initialCount = initialErrors.length;

      // Fix firstName — its specific "Required" message should clear
      await user.type(byName('firstName'), 'Alice');

      await waitFor(() => {
        const remaining = screen.queryAllByText(/^required$/i);
        expect(remaining.length).toBeLessThan(initialCount);
      });
    });

    it('does NOT call createOrder when client-side validation fails', async () => {
      const user = userEvent.setup();
      renderCheckout();

      await user.click(screen.getByRole('button', { name: /place order/i }));
      await screen.findAllByText(/^required$/i);

      expect(createOrder).not.toHaveBeenCalled();
    });
  });

  // ── Server errors ──────────────────────────────────────────────────────────

  describe('server errors', () => {
    it('shows a global error banner when the server returns a cart-level error', async () => {
      createOrder.mockRejectedValueOnce({
        response: { data: { cart: 'Your cart has expired. Please add items again.' } },
      });

      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      expect(
        await screen.findByText(/your cart has expired/i),
      ).toBeInTheDocument();
    });

    it('maps server field errors back to the corresponding form fields', async () => {
      createOrder.mockRejectedValueOnce({
        response: {
          data: {
            email: ['This email is already registered.'],
            zip: ['Invalid postal code.'],
          },
        },
      });

      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      expect(await screen.findByText('This email is already registered.')).toBeInTheDocument();
      expect(await screen.findByText('Invalid postal code.')).toBeInTheDocument();
    });

    it('shows a generic fallback error when the response has no structured data', async () => {
      createOrder.mockRejectedValueOnce(new Error('Network Error'));

      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      expect(
        await screen.findByText(/something went wrong/i),
      ).toBeInTheDocument();
    });

    it('re-enables the submit button after a failed submission', async () => {
      createOrder.mockRejectedValueOnce(new Error('Network Error'));

      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      await screen.findByText(/something went wrong/i);

      expect(screen.getByRole('button', { name: /place order/i })).not.toBeDisabled();
    });

    it('clears the previous server error banner when the user resubmits', async () => {
      createOrder
        .mockRejectedValueOnce(new Error('Network Error'))
        .mockResolvedValueOnce({ data: { id: 7 } });

      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));
      await screen.findByText(/something went wrong/i);

      // Second attempt — form is still filled, submit again
      await user.click(screen.getByRole('button', { name: /place order/i }));

      await waitFor(() => {
        expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();
      });
    });
  });

  // ── Button state ──────────────────────────────────────────────────────────

  describe('button state', () => {
    it('submit button is enabled by default when the cart is loaded', () => {
      renderCheckout();
      expect(screen.getByRole('button', { name: /place order/i })).not.toBeDisabled();
    });

    it('submit button is disabled while the submission is in progress', async () => {
      let resolveOrder;
      createOrder.mockImplementationOnce(
        () => new Promise((res) => { resolveOrder = res; }),
      );

      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      const btn = await screen.findByRole('button', { name: /placing order/i });
      expect(btn).toBeDisabled();

      resolveOrder({ data: { id: 1 } });
    });

    it('submit button is re-enabled after a failed submission', async () => {
      createOrder.mockRejectedValueOnce(new Error('fail'));

      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      expect(
        await screen.findByRole('button', { name: /place order/i }),
      ).not.toBeDisabled();
    });
  });
});
