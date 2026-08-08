import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CartProvider, useCart } from '../context/CartContext';

// ─── Mock the entire api service module ───────────────────────────────────────
vi.mock('../services/api', () => ({
  isAuthenticated: vi.fn(),
  getCart: vi.fn(),
  addToCart: vi.fn(),
  updateCartItem: vi.fn(),
  removeCartItem: vi.fn(),
  clearCart: vi.fn(),
}));

// Import the mocked functions so we can control them per-test
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
    { id: 10, product_id: 101, quantity: 1, price: '24.99' },
    { id: 11, product_id: 102, quantity: 1, price: '24.99' },
  ],
  ...overrides,
});

/**
 * Renders a small consumer component inside CartProvider and returns
 * handles to the rendered output plus a way to grab the latest context value.
 */
const renderWithCart = (ui) => {
  return render(<CartProvider>{ui}</CartProvider>);
};

/**
 * A test consumer that exposes every context value via data-testid attributes
 * and provides buttons to invoke each action.
 */
const TestConsumer = ({ productId = 101, itemId = 10, quantity = 3 }) => {
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
      <button onClick={() => addToCart(productId, quantity)}>addToCart</button>
      <button onClick={() => updateItem(itemId, quantity)}>updateItem</button>
      <button onClick={() => removeItem(itemId)}>removeItem</button>
      <button onClick={() => clearCart()}>clearCart</button>
    </div>
  );
};

// ─── Shared setup / teardown ──────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  // Default: unauthenticated (safest baseline)
  isAuthenticated.mockReturnValue(false);
});

afterEach(() => {
  // Clean up any lingering fake timers / window listeners
});

// ═════════════════════════════════════════════════════════════════════════════
// 1. PROVIDER — initial state
// ═════════════════════════════════════════════════════════════════════════════
describe('CartProvider — initial state', () => {
  it('exposes cart=null, cartCount=0, loading=false, error=null when unauthenticated', async () => {
    renderWithCart(<TestConsumer />);

    // After the async fetchCart resolves (no-op for unauthenticated)
    await waitFor(() => {
      expect(screen.getByTestId('cart').textContent).toBe('null');
    });

    expect(screen.getByTestId('cart-count').textContent).toBe('0');
    expect(screen.getByTestId('loading').textContent).toBe('false');
    expect(screen.getByTestId('error').textContent).toBe('null');
  });

  it('does NOT call getCart when user is unauthenticated on mount', async () => {
    isAuthenticated.mockReturnValue(false);
    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(getCart).not.toHaveBeenCalled();
    });
  });

  it('calls getCart and populates cart state when authenticated on mount', async () => {
    const cart = makeCart();
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValueOnce({ data: cart });

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('cart-count').textContent).toBe('2');
    });

    expect(getCart).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('cart').textContent).toContain('"id":1');
  });

  it('sets loading=true while fetching and loading=false after', async () => {
    isAuthenticated.mockReturnValue(true);

    let resolveCart;
    getCart.mockReturnValueOnce(
      new Promise((res) => { resolveCart = () => res({ data: makeCart() }); })
    );

    renderWithCart(<TestConsumer />);

    // Mid-flight: loading should be true
    expect(screen.getByTestId('loading').textContent).toBe('true');

    // Settle the promise
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
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValue({ data: cart });

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('cart-count').textContent).toBe('5');
    });
  });

  it('suppresses error and does not set error state on 401', async () => {
    isAuthenticated.mockReturnValue(true);
    const err = { response: { status: 401 } };
    getCart.mockRejectedValueOnce(err);

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });

    expect(screen.getByTestId('error').textContent).toBe('null');
  });

  it('sets error state on non-401 API failure', async () => {
    isAuthenticated.mockReturnValue(true);
    const err = { response: { status: 500 } };
    getCart.mockRejectedValueOnce(err);

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('error').textContent).toBe('Failed to load cart.');
    });
  });

  it('clears previous error on a successful re-fetch', async () => {
    isAuthenticated.mockReturnValue(true);
    // First call fails
    getCart
      .mockRejectedValueOnce({ response: { status: 500 } })
      // Second call succeeds
      .mockResolvedValueOnce({ data: makeCart() });

    renderWithCart(<TestConsumer />);

    // Wait for error to appear
    await waitFor(() => {
      expect(screen.getByTestId('error').textContent).toBe('Failed to load cart.');
    });

    // Manually trigger re-fetch
    await act(async () => {
      userEvent.click(screen.getByText('fetchCart'));
    });

    await waitFor(() => {
      expect(screen.getByTestId('error').textContent).toBe('null');
    });
  });

  it('resets cart to null when called while unauthenticated', async () => {
    // Start authenticated so cart gets set
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValueOnce({ data: makeCart() });

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('cart').textContent).not.toBe('null');
    });

    // Now become unauthenticated and re-fetch
    isAuthenticated.mockReturnValue(false);

    await act(async () => {
      userEvent.click(screen.getByText('fetchCart'));
    });

    await waitFor(() => {
      expect(screen.getByTestId('cart').textContent).toBe('null');
    });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 3. Event listeners — auth-change & storage
// ═════════════════════════════════════════════════════════════════════════════
describe('event listeners', () => {
  it('re-fetches cart when auth-change event fires', async () => {
    isAuthenticated.mockReturnValue(true);
    const cart = makeCart({ total_items: 3 });
    getCart.mockResolvedValue({ data: cart });

    renderWithCart(<TestConsumer />);

    // Initial fetch
    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(1));

    // Simulate auth change
    await act(async () => {
      window.dispatchEvent(new Event('auth-change'));
    });

    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(2));
  });

  it('does NOT re-fetch cart when storage event fires for an unrelated key', async () => {
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValue({ data: makeCart() });

    renderWithCart(<TestConsumer />);

    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(1));

    await act(async () => {
      window.dispatchEvent(
        new StorageEvent('storage', { key: 'theme', newValue: 'dark' })
      );
    });

    // Still only the mount call
    await waitFor(() => expect(getCart).toHaveBeenCalledTimes(1));
  });

  it('removes auth-change listener on unmount', async () => {
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValue({ data: makeCart() });

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
// 4. addToCart
// ═════════════════════════════════════════════════════════════════════════════
describe('addToCart', () => {
  it('redirects to /login and returns failure when unauthenticated', async () => {
    isAuthenticated.mockReturnValue(false);

    // Capture any attempted navigation
    const locationSpy = vi.spyOn(window, 'location', 'get').mockReturnValue({
      ...window.location,
      href: '',
    });
    let capturedHref = '';
    Object.defineProperty(window, 'location', {
      value: {
        ...window.location,
        set href(val) { capturedHref = val; },
        get href() { return capturedHref; },
      },
      writable: true,
    });

    let result;
    const Consumer = () => {
      const { addToCart } = useCart();
      return (
        <button onClick={async () => { result = await addToCart(101); }}>
          add
        </button>
      );
    };

    renderWithCart(<Consumer />);

    await act(async () => { userEvent.click(screen.getByText('add')); });

    await waitFor(() => {
      expect(result).toEqual({
        success: false,
        message: 'Please log in to add items to your cart.',
      });
    });
    expect(addToCart).not.toHaveBeenCalled(); // the api function, not the hook handler
    expect(capturedHref).toBe('/login');

    locationSpy.mockRestore?.();
  });

  it('updates cart and returns success on a successful API call', async () => {
    isAuthenticated.mockReturnValue(true);
    const updatedCart = makeCart({ total_items: 3 });
    getCart.mockResolvedValueOnce({ data: makeCart() });
    addToCart.mockResolvedValueOnce({ data: updatedCart });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button
          onClick={async () => { result = await ctx.addToCart(101, 1); }}
        >
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
    expect(addToCart).toHaveBeenCalledWith(101, 1);
  });

  it('returns failure with product_id error message from API', async () => {
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValueOnce({ data: makeCart() });
    addToCart.mockRejectedValueOnce({
      response: { data: { product_id: 'Invalid product.' } },
    });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.addToCart(999); }}>
          add
        </button>
      );
    };

    renderWithCart(<Consumer />);
    await waitFor(() => expect(getCart).toHaveBeenCalled());

    await act(async () => { userEvent.click(screen.getByText('add')); });

    await waitFor(() => {
      expect(result).toEqual({ success: false, message: 'Invalid product.' });
    });
  });

  it('returns failure with quantity error message from API', async () => {
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValueOnce({ data: makeCart() });
    addToCart.mockRejectedValueOnce({
      response: { data: { quantity: 'Quantity must be at least 1.' } },
    });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.addToCart(101, 0); }}>
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
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValueOnce({ data: makeCart() });
    addToCart.mockRejectedValueOnce({
      response: { data: { detail: 'Out of stock.' } },
    });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.addToCart(101); }}>
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
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValueOnce({ data: makeCart() });
    addToCart.mockRejectedValueOnce({ response: { data: {} } });

    let result;
    const Consumer = () => {
      const ctx = useCart();
      return (
        <button onClick={async () => { result = await ctx.addToCart(101); }}>
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
  const setupAuthenticated = () => {
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValueOnce({ data: makeCart() });
  };

  it('updates cart state and returns success', async () => {
    setupAuthenticated();
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
    setupAuthenticated();
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
    setupAuthenticated();
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
  const setupAuthenticated = () => {
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValueOnce({ data: makeCart() });
  };

  it('updates cart state and returns success', async () => {
    setupAuthenticated();
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
    setupAuthenticated();
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
  const setupAuthenticated = () => {
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValueOnce({ data: makeCart() });
  };

  it('clears cart state and returns success', async () => {
    setupAuthenticated();
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
    setupAuthenticated();
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
  it('returns 0 when cart is null', async () => {
    isAuthenticated.mockReturnValue(false);
    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('cart-count').textContent).toBe('0');
    });
  });

  it('reflects total_items from the cart object', async () => {
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValueOnce({ data: makeCart({ total_items: 7 }) });

    renderWithCart(<TestConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('cart-count').textContent).toBe('7');
    });
  });

  it('updates after addToCart changes the cart', async () => {
    isAuthenticated.mockReturnValue(true);
    getCart.mockResolvedValueOnce({ data: makeCart({ total_items: 2 }) });
    addToCart.mockResolvedValueOnce({ data: makeCart({ total_items: 3 }) });

    const Consumer = () => {
      const ctx = useCart();
      return (
        <div>
          <span data-testid="count">{ctx.cartCount}</span>
          <button onClick={() => ctx.addToCart(101, 1)}>add</button>
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
      useCart(); // no provider above
      return null;
    };

    // Suppress the expected React error boundary noise in the console
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => { });

    expect(() => render(<BrokenConsumer />)).toThrowError(
      'useCart must be used inside <CartProvider>'
    );

    consoleError.mockRestore();
  });
});
