import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CartProvider, useCart } from '../context/CartContext';

// ─── Mock the entire api service module ───────────────────────────────────────
// isAuthenticated is kept in the mock (even though CartContext no longer
// imports it — Task 5.1.1.4 removed all auth gating) specifically so the
// "ignored regardless of auth state" tests below can prove the OLD signal
// has no effect anymore, per this task's acceptance criteria.
vi.mock('../services/api', () => ({
  isAuthenticated: vi.fn(),
  getCart: vi.fn(),
  addToCart: vi.fn(),
  updateCartItem: vi.fn(),
  removeCartItem: vi.fn(),
  clearCart: vi.fn(),
}));

import {
  isAuthenticated,
  getCart,
  addToCart,
  updateCartItem,
  removeCartItem,
  clearCart,
} from '../services/api';

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Minimal cart object returned by the API */
const makeCart = (overrides = {}) => ({
  id: 1,
  total_items: 2,
  total_price: '49.98',
  items: [
    { id: 10, variant_id: 501, quantity: 1, price: '24.99' },
    { id: 11, variant_id: 502, quantity: 1, price: '24.99' },
  ],
  ...overrides,
});

/** An empty (but valid) cart, matching what an anonymous session gets. */
const makeEmptyCart = () => makeCart({ total_items: 0, items: [] });

const renderWithCart = (ui) => render(<CartProvider>{ui}</CartProvider>);

const TestConsumer = ({ variantId = 501, itemId = 10, quantity = 3 }) => {
  const {
    cart,
    cartCount,
    loading,
    error,
    fetchCart,
    addToCart,
    updateItem,
    removeItem,
    clearCart,
  } = useCart();

  return (
    <div>
      <span data-testid="cart-count">{cartCount}</span>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="error">{error ?? 'null'}</span>
      <span data-testid="cart">{cart ? JSON.stringify(cart) : 'null'}</span>

      <button onClick={fetchCart}>fetchCart</button>
      <button onClick={() => addToCart(variantId, quantity)}>addToCart</button>
      <button onClick={() => updateItem(itemId, quantity)}>updateItem</button>
      <button onClick={() => removeItem(itemId)}>removeItem</button>
      <button onClick={() => clearCart()}>clearCart</button>
    </div>
  );
};

beforeEach(() => {
  vi.clearAllMocks();
  // Default: resolve to an empty cart, matching a fresh anonymous session's
  // response — most tests don't care about this and just need SOMETHING
  // valid so the unconditional mount fetch doesn't crash on undefined.
  getCart.mockResolvedValue({ data: makeEmptyCart() });
});

// ═════════════════════════════════════════════════════════════════════════════
// 1. PROVIDER — initial state / unconditional fetch on mount
// ═════════════════════════════════════════════════════════════════════════════
describe('CartProvider — fetches unconditionally on mount', () => {
  it('calls getCart on mount regardless of auth state (anonymous)', async () => {
    isAuthenticated.mockReturnValue(false);
    renderWithCart(<TestConsumer />);

    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(1));
  });

  it('calls getCart on mount regardless of auth state (authenticated)', async () => {
    isAuthenticated.mockReturnValue(true);
    renderWithCart(<TestConsumer />);

    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(1));
  });

  it('populates cart state from an anonymous session cart', async () => {
    isAuthenticated.mockReturnValue(false);
    const cart = makeCart({ total_items: 2 });
    getCart.mockResolvedValueOnce({ data: cart });

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('cart-count').textContent).toBe('2');
    });
    expect(screen.getByTestId('cart').textContent).toContain('"id":1');
  });

  it('sets loading=true while fetching and loading=false after', async () => {
    let resolveCart;
    getCart.mockReturnValueOnce(
      new Promise((res) => { resolveCart = () => res({ data: makeEmptyCart() }); })
    );

    renderWithCart(<TestConsumer />);

    expect(screen.getByTestId('loading').textContent).toBe('true');

    await act(async () => { resolveCart(); });

    expect(screen.getByTestId('loading').textContent).toBe('false');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 2. fetchCart
// ═════════════════════════════════════════════════════════════════════════════
describe('fetchCart', () => {
  it('sets cart from API response on success', async () => {
    const cart = makeCart({ total_items: 5 });
    getCart.mockResolvedValue({ data: cart });

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('cart-count').textContent).toBe('5');
    });
  });

  it('suppresses error and does not set error state on 401', async () => {
    const err = { response: { status: 401 } };
    getCart.mockRejectedValueOnce(err);

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });
    expect(screen.getByTestId('error').textContent).toBe('null');
  });

  it('sets error state on non-401 API failure', async () => {
    const err = { response: { status: 500 } };
    getCart.mockRejectedValueOnce(err);

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('error').textContent).toBe('Failed to load cart.');
    });
  });

  it('clears previous error on a successful re-fetch', async () => {
    getCart
      .mockRejectedValueOnce({ response: { status: 500 } })
      .mockResolvedValueOnce({ data: makeCart() });

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('error').textContent).toBe('Failed to load cart.');
    });

    await act(async () => {
      userEvent.click(screen.getByText('fetchCart'));
    });

    await waitFor(() => {
      expect(screen.getByTestId('error').textContent).toBe('null');
    });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 3. Event listeners — auth-change & storage
// ═════════════════════════════════════════════════════════════════════════════
describe('event listeners', () => {
  it('re-fetches cart when auth-change event fires (e.g. after post-login merge)', async () => {
    const cart = makeCart({ total_items: 3 });
    getCart.mockResolvedValue({ data: cart });

    renderWithCart(<TestConsumer />);

    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(1));

    await act(async () => {
      window.dispatchEvent(new Event('auth-change'));
    });

    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(2));
  });

  it('does NOT re-fetch cart when storage event fires for an unrelated key', async () => {
    getCart.mockResolvedValue({ data: makeEmptyCart() });

    renderWithCart(<TestConsumer />);

    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(1));

    await act(async () => {
      window.dispatchEvent(
        new StorageEvent('storage', { key: 'theme', newValue: 'dark' })
      );
    });

    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(1));
  });

  it('removes auth-change listener on unmount', async () => {
    getCart.mockResolvedValue({ data: makeEmptyCart() });

    const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

    const { unmount } = renderWithCart(<TestConsumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(1));

    unmount();

    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      'auth-change',
      expect.any(Function)
    );

    removeEventListenerSpy.mockRestore();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 4. addToCart — no auth gate (Task 5.1.1.4)
// ═════════════════════════════════════════════════════════════════════════════
describe('addToCart', () => {
  it('calls the API and succeeds even when isAuthenticated() reports false', async () => {
    // The old code short-circuited here and redirected to /login without
    // ever calling the API. Proving isAuthenticated() is now IGNORED is
    // the core regression test for this task.
    isAuthenticated.mockReturnValue(false);
    const updatedCart = makeCart({ total_items: 1 });
    addToCart.mockResolvedValueOnce({ data: updatedCart });

    let result;
    let capturedHref = 'unchanged';
    Object.defineProperty(window, 'location', {
      value: {
        ...window.location,
        set href(val) { capturedHref = val; },
        get href() { return capturedHref; },
      },
      writable: true,
    });

    const Consumer = () => {
      const { addToCart } = useCart();
      return (
        <button onClick={async () => { result = await addToCart(501, 1); }}>
          add
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await act(async () => { userEvent.click(screen.getByText('add')); });

    await waitFor(() => {
      expect(result).toEqual({ success: true, message: 'Item added to cart!' });
    });
    expect(addToCart).toHaveBeenCalledWith(501, 1);
    // No redirect happened.
    expect(capturedHref).toBe('unchanged');
  });

  it('updates cart and returns success on a successful API call', async () => {
    const updatedCart = makeCart({ total_items: 3 });
    addToCart.mockResolvedValueOnce({ data: updatedCart });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.addToCart(501, 1); }}>
          add
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('add')); });

    await waitFor(() => {
      expect(result).toEqual({ success: true, message: 'Item added to cart!' });
    });
    expect(addToCart).toHaveBeenCalledWith(501, 1);
  });

  it('returns failure with variant_id error message from API', async () => {
    addToCart.mockRejectedValueOnce({
      response: { data: { variant_id: 'Invalid variant.' } },
    });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.addToCart(9999); }}>
          add
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('add')); });

    await waitFor(() => {
      expect(result).toEqual({ success: false, message: 'Invalid variant.' });
    });
  });

  it('returns failure with quantity error message from API', async () => {
    addToCart.mockRejectedValueOnce({
      response: { data: { quantity: 'Quantity must be at least 1.' } },
    });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.addToCart(501, 0); }}>
          add
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('add')); });

    await waitFor(() => {
      expect(result).toEqual({
        success: false,
        message: 'Quantity must be at least 1.',
      });
    });
  });

  it('returns failure with detail message from API', async () => {
    addToCart.mockRejectedValueOnce({
      response: { data: { detail: 'Out of stock.' } },
    });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.addToCart(501); }}>
          add
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('add')); });

    await waitFor(() => {
      expect(result).toEqual({ success: false, message: 'Out of stock.' });
    });
  });

  it('falls back to generic message when API error has no known field', async () => {
    addToCart.mockRejectedValueOnce({ response: { data: {} } });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.addToCart(501); }}>
          add
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('add')); });

    await waitFor(() => {
      expect(result).toEqual({
        success: false,
        message: 'Failed to add item to cart.',
      });
    });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 5. updateItem
// ═════════════════════════════════════════════════════════════════════════════
describe('updateItem', () => {
  it('updates cart state and returns success', async () => {
    const updatedCart = makeCart({ total_items: 4 });
    updateCartItem.mockResolvedValueOnce({ data: updatedCart });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.updateItem(10, 4); }}>
          update
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('update')); });

    await waitFor(() => {
      expect(result).toEqual({ success: true });
    });
    expect(updateCartItem).toHaveBeenCalledWith(10, 4);
  });

  it('returns failure with quantity error from API', async () => {
    updateCartItem.mockRejectedValueOnce({
      response: { data: { quantity: 'Invalid quantity.' } },
    });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.updateItem(10, -1); }}>
          update
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('update')); });

    await waitFor(() => {
      expect(result).toEqual({ success: false, message: 'Invalid quantity.' });
    });
  });

  it('returns generic failure message when API error has no quantity field', async () => {
    updateCartItem.mockRejectedValueOnce({ response: { data: {} } });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.updateItem(10, 0); }}>
          update
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('update')); });

    await waitFor(() => {
      expect(result).toEqual({ success: false, message: 'Failed to update quantity.' });
    });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 6. removeItem
// ═════════════════════════════════════════════════════════════════════════════
describe('removeItem', () => {
  it('updates cart state and returns success', async () => {
    const updatedCart = makeCart({ total_items: 1, items: [makeCart().items[1]] });
    removeCartItem.mockResolvedValueOnce({ data: updatedCart });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.removeItem(10); }}>
          remove
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('remove')); });

    await waitFor(() => {
      expect(result).toEqual({ success: true });
    });
    expect(removeCartItem).toHaveBeenCalledWith(10);
  });

  it('returns failure message on API error', async () => {
    removeCartItem.mockRejectedValueOnce(new Error('Network Error'));

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.removeItem(10); }}>
          remove
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('remove')); });

    await waitFor(() => {
      expect(result).toEqual({ success: false, message: 'Failed to remove item.' });
    });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 7. clearCart
// ═════════════════════════════════════════════════════════════════════════════
describe('clearCart', () => {
  it('clears cart state and returns success', async () => {
    const emptyCart = makeCart({ total_items: 0, items: [] });
    clearCart.mockResolvedValueOnce({ data: emptyCart });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.clearCart(); }}>
          clear
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('clear')); });

    await waitFor(() => {
      expect(result).toEqual({ success: true });
    });
    expect(clearCart).toHaveBeenCalledTimes(1);
  });

  it('returns failure message on API error', async () => {
    clearCart.mockRejectedValueOnce(new Error('Network Error'));

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.clearCart(); }}>
          clear
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('clear')); });

    await waitFor(() => {
      expect(result).toEqual({ success: false, message: 'Failed to clear cart.' });
    });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 8. cartCount derived value
// ═════════════════════════════════════════════════════════════════════════════
describe('cartCount', () => {
  it('returns 0 when the cart fetch fails (cart stays null)', async () => {
    getCart.mockRejectedValueOnce({ response: { status: 500 } });
    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });
    expect(screen.getByTestId('cart-count').textContent).toBe('0');
  });

  it('reflects total_items from the cart object', async () => {
    getCart.mockResolvedValueOnce({ data: makeCart({ total_items: 7 }) });

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('cart-count').textContent).toBe('7');
    });
  });

  it('updates after addToCart changes the cart', async () => {
    getCart.mockResolvedValueOnce({ data: makeCart({ total_items: 2 }) });
    addToCart.mockResolvedValueOnce({ data: makeCart({ total_items: 3 }) });

    const Consumer = () => {
      const ctx = useCart();
      return (
        <div>
          <span data-testid="count">{ctx.cartCount}</span>
          <button onClick={() => ctx.addToCart(501, 1)}>add</button>
        </div>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('2'));

    await act(async () => { userEvent.click(screen.getByText('add')); });

    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('3'));
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 9. useCart hook — usage outside provider
// ═════════════════════════════════════════════════════════════════════════════
describe('useCart hook', () => {
  it('throws a descriptive error when used outside of CartProvider', () => {
    const BrokenConsumer = () => {
      useCart();
      return null;
    };

    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => { });

    expect(() => render(<BrokenConsumer />)).toThrowError(
      'useCart must be used inside <CartProvider>'
    );

    consoleError.mockRestore();
  });
});
