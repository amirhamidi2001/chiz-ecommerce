import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import CheckoutFailed from '../pages/CheckoutFailed';

// ─── Mock: CartContext ────────────────────────────────────────────────────────
const mockFetchCart = vi.fn();
let mockCartCount = 0;

vi.mock('../context/CartContext', () => ({
  useCart: () => ({ cartCount: mockCartCount, fetchCart: mockFetchCart }),
}));

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Wraps <CheckoutFailed /> in the router setup required for
 * useSearchParams() to read ?reason= from the URL.
 */
const renderWithReason = (reason) => {
  const path = reason === undefined
    ? '/checkout/failed'
    : `/checkout/failed?reason=${reason}`;

  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/checkout/failed" element={<CheckoutFailed />} />
      </Routes>
    </MemoryRouter>,
  );
};

describe('CheckoutFailed', () => {
  beforeEach(() => {
    mockCartCount = 0;
    mockFetchCart.mockClear();
  });

  it('shows the cancelled-specific message for reason=cancelled', () => {
    renderWithReason('cancelled');

    expect(
      screen.getByText(/you cancelled the payment\. your items are still in your cart\./i),
    ).toBeInTheDocument();
  });

  it('shows the verification-failed-specific message for reason=verification_failed', () => {
    renderWithReason('verification_failed');

    expect(
      screen.getByText(
        /your payment could not be confirmed\. please try again or contact support\./i,
      ),
    ).toBeInTheDocument();
  });

  it('shows the generic fallback message for reason=unknown_transaction', () => {
    renderWithReason('unknown_transaction');

    expect(
      screen.getByText(/something went wrong with your payment\./i),
    ).toBeInTheDocument();
  });

  it('shows the generic fallback message for reason=already_failed', () => {
    // Task 6.4.1.2's spec: only "cancelled" and "verification_failed" get
    // their own specific copy — every other backend-produced reason
    // (including already_failed, the idempotent-duplicate-callback case)
    // falls through to the generic message.
    renderWithReason('already_failed');

    expect(
      screen.getByText(/something went wrong with your payment\./i),
    ).toBeInTheDocument();
  });

  it('shows the generic fallback message when reason is missing entirely', () => {
    renderWithReason(undefined);

    expect(
      screen.getByText(/something went wrong with your payment\./i),
    ).toBeInTheDocument();
  });

  it('shows the generic fallback message for a completely unrecognized reason value', () => {
    renderWithReason('some_future_reason_this_page_does_not_know_about');

    expect(
      screen.getByText(/something went wrong with your payment\./i),
    ).toBeInTheDocument();
  });

  it('renders exactly one reason message at a time (no bleed-through between cases)', () => {
    renderWithReason('cancelled');

    expect(screen.getByTestId('checkout-failed-message').textContent).toBe(
      'You cancelled the payment. Your items are still in your cart.',
    );
    expect(
      screen.queryByText(/could not be confirmed/i),
    ).not.toBeInTheDocument();
  });

  it('offers a "Try again" link back to /checkout', () => {
    renderWithReason('verification_failed');

    const tryAgainLink = screen.getByRole('link', { name: /try again/i });
    expect(tryAgainLink).toHaveAttribute('href', '/checkout');
  });

  it('offers a link to view the cart', () => {
    renderWithReason('cancelled');

    const viewCartLink = screen.getByRole('link', { name: /view cart/i });
    expect(viewCartLink).toHaveAttribute('href', '/cart');
  });

  it('mentions the item count when the cart still has items', () => {
    mockCartCount = 3;
    renderWithReason('cancelled');

    expect(screen.getByText(/you have 3 items waiting in your cart/i)).toBeInTheDocument();
  });

  it('does not mention item count when the cart is empty', () => {
    mockCartCount = 0;
    renderWithReason('cancelled');

    expect(screen.queryByText(/waiting in your cart/i)).not.toBeInTheDocument();
  });

  it('refreshes the cart on mount, since the browser arrived via a real external redirect', () => {
    renderWithReason('cancelled');

    expect(mockFetchCart).toHaveBeenCalled();
  });
});
