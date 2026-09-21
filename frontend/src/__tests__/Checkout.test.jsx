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
  initiatePayment: vi.fn(),
  isAuthenticated: vi.fn(),
  // Checkout fetches the shopper's saved address book on mount (Task
  // 5.2.1.5) to decide whether to show the saved-address picker.
  dashboardAPI: {
    getAddresses: vi.fn(),
  },
}));

import { useCart } from '../context/CartContext';
import { createOrder, initiatePayment, isAuthenticated, dashboardAPI } from '../services/api';

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
  // Province is a <select> of Iran's 31 provinces (Task 5.2.1.4), not a
  // free-text field, and the postal code must be exactly 10 digits.
  await user.selectOptions(byName('state'), 'tehran');
  await user.type(byName('zip'), '1234567890');

  // Task 6.4.1.3: no payment-method/card-entry step any more — real
  // payment method selection now happens on the gateway's own hosted
  // page, not this form.

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
    // Default: no saved addresses, so the picker stays hidden and these
    // pre-existing tests exercise the manual form exactly as before.
    dashboardAPI.getAddresses.mockResolvedValue({ data: [] });
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

    it('does not render any payment-method selector or card-entry fields (Task 6.4.1.3)', () => {
      renderCheckout();

      // Real payment method selection now happens on the gateway's own
      // hosted page — this platform's checkout form no longer asks the
      // customer to pick a payment method type or enter card details at
      // all.
      expect(screen.queryByText(/credit \/ debit card/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/^paypal$/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/apple pay/i)).not.toBeInTheDocument();
      expect(screen.queryByPlaceholderText('1234 5678 9012 3456')).not.toBeInTheDocument();
      expect(screen.queryByPlaceholderText('MM/YY')).not.toBeInTheDocument();
      expect(screen.queryByText(/security code/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/name on card/i)).not.toBeInTheDocument();
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

      // Country is a <select> (combobox role), also queryable by name attr.
      // This platform ships within Iran only, so "IR" is the sole option
      // (and the default) — see the backend's "IR" default on
      // Address.country.
      const countrySelect = byName('country');
      await user.selectOptions(countrySelect, 'IR');
      expect(countrySelect).toHaveValue('IR');
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
    it('calls createOrder with the correct payload (no payment fields)', async () => {
      createOrder.mockResolvedValueOnce({ data: { id: 42 } });
      initiatePayment.mockResolvedValueOnce({
        data: { redirect_url: 'https://sandbox.zarinpal.com/pg/StartPay/A123' },
      });
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
        state: 'tehran',
        zip: '1234567890',
        country: 'IR',
        // Manual-address checkouts carry save_address and NOT address_id
        // (Task 5.2.1.5) — the two payload shapes are mutually exclusive.
        save_address: false,
      });
      expect(payload).not.toHaveProperty('address_id');
      // Task 6.4.1.1: there's no card-entry step in the real flow any
      // more — the gateway's own hosted page collects payment details,
      // not this form — so these must NOT be sent. The card UI fields
      // themselves are gone too, per Task 6.4.1.3.
      expect(payload).not.toHaveProperty('payment_method');
      expect(payload).not.toHaveProperty('card_last_four');
      expect(payload).not.toHaveProperty('discount');
    });

    it('calls initiatePayment with the created order id, then redirects the full browser window to the returned gateway URL', async () => {
      createOrder.mockResolvedValueOnce({ data: { id: 99 } });
      initiatePayment.mockResolvedValueOnce({
        data: { redirect_url: 'https://sandbox.zarinpal.com/pg/StartPay/A00000000wOGYpd' },
      });

      // jsdom doesn't implement real navigation; spy on the setter
      // instead (same approach as ProductDetails.test.jsx). A real
      // window.location.href assignment can't be observed any other way
      // in jsdom, and this is a genuine external-origin redirect (the
      // gateway's hosted page), not an in-app route — so there's no
      // React Router navigation to assert on instead.
      delete window.location;
      window.location = { href: '' };

      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      await waitFor(() => expect(initiatePayment).toHaveBeenCalledWith(99));

      await waitFor(() =>
        expect(window.location.href).toBe(
          'https://sandbox.zarinpal.com/pg/StartPay/A00000000wOGYpd',
        ),
      );

      // useNavigate() must NOT be used for this — it's an external
      // origin, and React Router's navigate() only handles in-app
      // routes.
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('retries payment initiation for the SAME order (no duplicate order) when initiatePayment fails then the user retries', async () => {
      createOrder.mockResolvedValueOnce({ data: { id: 55 } });
      initiatePayment
        .mockRejectedValueOnce({
          response: { data: { detail: 'Payment gateway is currently unavailable.' } },
        })
        .mockResolvedValueOnce({
          data: { redirect_url: 'https://sandbox.zarinpal.com/pg/StartPay/RETRY' },
        });

      delete window.location;
      window.location = { href: '' };

      const user = userEvent.setup();
      renderCheckout();

      await fillValidForm(user);
      await user.click(screen.getByRole('button', { name: /place order/i }));

      // First initiate attempt fails — a clear error is shown, and the
      // button becomes a "Retry Payment" affordance rather than a plain
      // "Place Order" (which would resubmit the whole form).
      expect(
        await screen.findByText(/payment gateway is currently unavailable/i),
      ).toBeInTheDocument();
      const retryBtn = await screen.findByRole('button', { name: /retry payment/i });
      expect(retryBtn).not.toBeDisabled();

      await user.click(retryBtn);

      await waitFor(() =>
        expect(window.location.href).toBe(
          'https://sandbox.zarinpal.com/pg/StartPay/RETRY',
        ),
      );

      // THE key assertion: createOrder was called exactly ONCE across
      // both the initial submit and the retry — the retry must reuse
      // the already-created order, never create a duplicate one.
      expect(createOrder).toHaveBeenCalledOnce();
      expect(initiatePayment).toHaveBeenCalledTimes(2);
      expect(initiatePayment).toHaveBeenNthCalledWith(1, 55);
      expect(initiatePayment).toHaveBeenNthCalledWith(2, 55);
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
      await user.selectOptions(byName('state'), 'tehran');
      await user.type(byName('zip'), '1234567890');
      // Deliberately do NOT check the terms checkbox

      await user.click(screen.getByRole('button', { name: /place order/i }));

      expect(
        await screen.findByText(/you must agree to the terms and conditions/i),
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
