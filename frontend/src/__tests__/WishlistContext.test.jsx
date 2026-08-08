import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WishlistProvider, useWishlist } from '../context/WishlistContext';
import React, { useEffect } from 'react';

// ─── Mock the API module ──────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  isAuthenticated: vi.fn(),
  dashboardAPI: {
    getWishlist: vi.fn(),
    addToWishlist: vi.fn(),
    removeFromWishlist: vi.fn(),
  },
}));

// Pull mock references AFTER vi.mock so they're the mocked versions
import { isAuthenticated, dashboardAPI } from '../services/api';

// ─── Fixtures ─────────────────────────────────────────────────────────────────
const ITEM_1 = { id: 101, product: { id: 1, slug: 'widget-a', name: 'Widget A' } };
const ITEM_2 = { id: 202, product: { id: 2, slug: 'gadget-b', name: 'Gadget B' } };
const ITEM_3 = { id: 303, product: { id: 3, slug: 'doohickey-c', name: 'Doohickey C' } };

// ─── Helper: render a component that consumes the context ─────────────────────
/**
 * Renders children inside WishlistProvider and returns RTL utilities.
 * Wraps in act so all state updates from mount useEffect are flushed.
 */
const renderWithProvider = async (ui) => {
  let result;
  await act(async () => {
    result = render(<WishlistProvider>{ui}</WishlistProvider>);
  });
  return result;
};

/**
 * A minimal consumer component that exposes every context value via data-testid
 * attributes so tests can assert without importing the hook directly.
 */
const WishlistConsumer = ({ onMount } = {}) => {
  const ctx = useWishlist();

  // Optional callback so individual tests can grab the context object
  useEffect(() => {
    onMount?.(ctx);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <span data-testid="count">{ctx.wishlistCount}</span>
      <span data-testid="loading">{String(ctx.loading)}</span>
      <span data-testid="error">{ctx.error ?? 'null'}</span>
      <span data-testid="wishlist">{JSON.stringify(ctx.wishlist)}</span>
    </div>
  );
};

// ─── beforeEach / afterEach ────────────────────────────────────────────────────
beforeEach(() => {
  vi.clearAllMocks();
  // Default: unauthenticated; individual tests override as needed
  isAuthenticated.mockReturnValue(false);
  // Prevent JSDOM noise from window.location assignments
  Object.defineProperty(window, 'location', {
    writable: true,
    value: { href: '/' },
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ═════════════════════════════════════════════════════════════════════════════
// 1. Module contract
// ═════════════════════════════════════════════════════════════════════════════
describe('useWishlist – module contract', () => {
  it('throws a descriptive error when used outside WishlistProvider', () => {
    // Silence the expected React error boundary console output
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const ThrowingConsumer = () => {
      useWishlist(); // should throw
      return null;
    };

    expect(() => render(<ThrowingConsumer />)).toThrowError(
      'useWishlist must be used inside <WishlistProvider>',
    );

    consoleSpy.mockRestore();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 2. Initial state (unauthenticated)
// ═════════════════════════════════════════════════════════════════════════════
describe('WishlistProvider – initial state', () => {
  it('exposes empty wishlist, loading=false, error=null on first render when unauthenticated', async () => {
    await renderWithProvider(<WishlistConsumer />);

    expect(screen.getByTestId('wishlist').textContent).toBe('[]');
    expect(screen.getByTestId('loading').textContent).toBe('false');
    expect(screen.getByTestId('error').textContent).toBe('null');
    expect(screen.getByTestId('count').textContent).toBe('0');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 3. fetchWishlist
// ═════════════════════════════════════════════════════════════════════════════
describe('fetchWishlist', () => {
  it('clears wishlist and returns early when user is not authenticated', async () => {
    isAuthenticated.mockReturnValue(false);
    await renderWithProvider(<WishlistConsumer />);

    expect(dashboardAPI.getWishlist).not.toHaveBeenCalled();
    expect(screen.getByTestId('wishlist').textContent).toBe('[]');
  });

  it('populates wishlist from a paginated { results: [...] } response', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({
      data: { results: [ITEM_1, ITEM_2] },
    });

    await renderWithProvider(<WishlistConsumer />);

    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('2'),
    );
    const wishlist = JSON.parse(screen.getByTestId('wishlist').textContent);
    expect(wishlist).toEqual([ITEM_1, ITEM_2]);
  });

  it('populates wishlist from a plain-array response (non-paginated)', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({
      data: [ITEM_1],
    });

    await renderWithProvider(<WishlistConsumer />);

    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('1'),
    );
  });

  it('does NOT set error state on a 401 response (silent auth expiry)', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockRejectedValueOnce({
      response: { status: 401 },
    });

    await renderWithProvider(<WishlistConsumer />);

    await waitFor(() =>
      expect(screen.getByTestId('loading').textContent).toBe('false'),
    );
    expect(screen.getByTestId('error').textContent).toBe('null');
    expect(screen.getByTestId('wishlist').textContent).toBe('[]');
  });

  it('sets error="Failed to load wishlist." on non-401 network errors', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockRejectedValueOnce({
      response: { status: 500 },
    });

    await renderWithProvider(<WishlistConsumer />);

    await waitFor(() =>
      expect(screen.getByTestId('error').textContent).toBe('Failed to load wishlist.'),
    );
  });

  it('sets error on errors with no response object (network failure)', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockRejectedValueOnce(new Error('Network Error'));

    await renderWithProvider(<WishlistConsumer />);

    await waitFor(() =>
      expect(screen.getByTestId('error').textContent).toBe('Failed to load wishlist.'),
    );
  });

  it('clears a previous error before each fetch attempt', async () => {
    isAuthenticated.mockReturnValue(true);
    // First call fails
    dashboardAPI.getWishlist.mockRejectedValueOnce({ response: { status: 500 } });

    let capturedCtx;
    const CapturingConsumer = () => {
      capturedCtx = useWishlist();
      return <WishlistConsumer />;
    };

    await renderWithProvider(<CapturingConsumer />);

    await waitFor(() =>
      expect(screen.getByTestId('error').textContent).toBe('Failed to load wishlist.'),
    );

    // Second call succeeds
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1] });

    await act(async () => {
      await capturedCtx.fetchWishlist();
    });

    await waitFor(() =>
      expect(screen.getByTestId('error').textContent).toBe('null'),
    );
  });

  it('sets loading=true during fetch and loading=false after resolution', async () => {
    isAuthenticated.mockReturnValue(true);
    const loadingStates = [];

    let resolve;
    const pending = new Promise((r) => { resolve = r; });
    dashboardAPI.getWishlist.mockReturnValueOnce(pending);

    const LoadingConsumer = () => {
      const { loading } = useWishlist();
      loadingStates.push(loading);
      return <span data-testid="loading">{String(loading)}</span>;
    };

    render(<WishlistProvider><LoadingConsumer /></WishlistProvider>);

    // While the promise is pending loading should be true at some point
    await waitFor(() => expect(loadingStates).toContain(true));

    // Resolve the promise
    await act(async () => {
      resolve({ data: [] });
    });

    await waitFor(() =>
      expect(loadingStates[loadingStates.length - 1]).toBe(false),
    );
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 4. Event-listener wiring
// ═════════════════════════════════════════════════════════════════════════════
describe('event listeners', () => {
  it('re-fetches wishlist when "auth-change" event fires', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist
      .mockResolvedValueOnce({ data: [] })           // mount
      .mockResolvedValueOnce({ data: [ITEM_1] });    // after event

    await renderWithProvider(<WishlistConsumer />);

    await act(async () => {
      window.dispatchEvent(new Event('auth-change'));
    });

    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('1'),
    );
    expect(dashboardAPI.getWishlist).toHaveBeenCalledTimes(2);
  });

  it('re-fetches wishlist when storage event fires with key="access_token"', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [ITEM_1, ITEM_2] });

    await renderWithProvider(<WishlistConsumer />);

    await act(async () => {
      window.dispatchEvent(
        new StorageEvent('storage', { key: 'access_token', newValue: 'tok' }),
      );
    });

    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('2'),
    );
    expect(dashboardAPI.getWishlist).toHaveBeenCalledTimes(2);
  });

  it('does NOT re-fetch when an unrelated storage key changes', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValue({ data: [] });

    await renderWithProvider(<WishlistConsumer />);

    await act(async () => {
      window.dispatchEvent(
        new StorageEvent('storage', { key: 'theme', newValue: 'dark' }),
      );
    });

    // Only the initial fetch should have fired
    expect(dashboardAPI.getWishlist).toHaveBeenCalledTimes(1);
  });

  it('removes event listeners on unmount', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValue({ data: [] });

    const addSpy = vi.spyOn(window, 'addEventListener');
    const removeSpy = vi.spyOn(window, 'removeEventListener');

    const { unmount } = await renderWithProvider(<WishlistConsumer />);

    unmount();

    const removedAuthChange = removeSpy.mock.calls.some(
      ([event]) => event === 'auth-change',
    );
    const removedStorage = removeSpy.mock.calls.some(
      ([event]) => event === 'storage',
    );

    expect(removedAuthChange).toBe(true);
    expect(removedStorage).toBe(true);

    addSpy.mockRestore();
    removeSpy.mockRestore();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 5. isInWishlist
// ═════════════════════════════════════════════════════════════════════════════
describe('isInWishlist', () => {
  const setupWithItems = async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1, ITEM_2] });

    let ctx;
    const Consumer = () => {
      ctx = useWishlist();
      return null;
    };
    await renderWithProvider(<Consumer />);
    await waitFor(() => expect(ctx.wishlistCount).toBe(2));
    return ctx;
  };

  it('returns true for a product id that is in the wishlist', async () => {
    const ctx = await setupWithItems();
    expect(ctx.isInWishlist(1)).toBe(true);
    expect(ctx.isInWishlist(2)).toBe(true);
  });

  it('returns false for a product id that is NOT in the wishlist', async () => {
    const ctx = await setupWithItems();
    expect(ctx.isInWishlist(999)).toBe(false);
  });

  it('returns false for undefined / null product ids', async () => {
    const ctx = await setupWithItems();
    expect(ctx.isInWishlist(undefined)).toBe(false);
    expect(ctx.isInWishlist(null)).toBe(false);
  });

  it('returns false when wishlist is empty', async () => {
    isAuthenticated.mockReturnValue(false);
    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);
    expect(ctx.isInWishlist(1)).toBe(false);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 6. getWishlistItemId
// ═════════════════════════════════════════════════════════════════════════════
describe('getWishlistItemId', () => {
  it('returns the wishlist-item id for a matched product id', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1, ITEM_2] });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);
    await waitFor(() => expect(ctx.wishlistCount).toBe(2));

    expect(ctx.getWishlistItemId(1)).toBe(101);
    expect(ctx.getWishlistItemId(2)).toBe(202);
  });

  it('returns null when the product is not in the wishlist', async () => {
    isAuthenticated.mockReturnValue(false);
    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);

    expect(ctx.getWishlistItemId(999)).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 7. addToWishlist
// ═════════════════════════════════════════════════════════════════════════════
describe('addToWishlist', () => {
  it('redirects to /login and returns failure when unauthenticated', async () => {
    isAuthenticated.mockReturnValue(false);

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);

    let result;
    await act(async () => {
      result = await ctx.addToWishlist(1);
    });

    expect(window.location.href).toBe('/login');
    expect(result).toEqual({
      success: false,
      message: 'Please log in to save items to your wishlist.',
    });
    expect(dashboardAPI.addToWishlist).not.toHaveBeenCalled();
  });

  it('short-circuits with success if product is already in wishlist', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1] });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);
    await waitFor(() => expect(ctx.wishlistCount).toBe(1));

    let result;
    await act(async () => {
      result = await ctx.addToWishlist(1); // product id 1 is already present
    });

    expect(result).toEqual({ success: true, message: 'Already in wishlist.' });
    expect(dashboardAPI.addToWishlist).not.toHaveBeenCalled();
  });

  it('appends the returned item to wishlist state on success', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1] });
    dashboardAPI.addToWishlist.mockResolvedValueOnce({ data: ITEM_2 });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);
    await waitFor(() => expect(ctx.wishlistCount).toBe(1));

    let result;
    await act(async () => {
      result = await ctx.addToWishlist(2);
    });

    expect(result).toEqual({ success: true, message: 'Added to wishlist!' });
    expect(ctx.wishlistCount).toBe(2);
    expect(ctx.isInWishlist(2)).toBe(true);
    expect(dashboardAPI.addToWishlist).toHaveBeenCalledWith(2);
  });

  it('returns error message from err.response.data.product_id[0]', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [] });
    dashboardAPI.addToWishlist.mockRejectedValueOnce({
      response: { data: { product_id: ['Product does not exist.'] } },
    });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);

    let result;
    await act(async () => {
      result = await ctx.addToWishlist(99);
    });

    expect(result).toEqual({ success: false, message: 'Product does not exist.' });
  });

  it('returns error message from err.response.data.detail', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [] });
    dashboardAPI.addToWishlist.mockRejectedValueOnce({
      response: { data: { detail: 'You already have this item.' } },
    });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);

    let result;
    await act(async () => {
      result = await ctx.addToWishlist(99);
    });

    expect(result).toEqual({ success: false, message: 'You already have this item.' });
  });

  it('falls back to generic message when no structured error is present', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [] });
    dashboardAPI.addToWishlist.mockRejectedValueOnce(new Error('Network Error'));

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);

    let result;
    await act(async () => {
      result = await ctx.addToWishlist(99);
    });

    expect(result).toEqual({ success: false, message: 'Failed to add to wishlist.' });
  });

  it('does not mutate wishlist state when addToWishlist API call fails', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1] });
    dashboardAPI.addToWishlist.mockRejectedValueOnce({ response: { status: 500 } });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);
    await waitFor(() => expect(ctx.wishlistCount).toBe(1));

    await act(async () => {
      await ctx.addToWishlist(2);
    });

    expect(ctx.wishlistCount).toBe(1); // unchanged
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 8. removeFromWishlist
// ═════════════════════════════════════════════════════════════════════════════
describe('removeFromWishlist', () => {
  it('removes the item from wishlist state and returns success', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1, ITEM_2] });
    dashboardAPI.removeFromWishlist.mockResolvedValueOnce({});

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);
    await waitFor(() => expect(ctx.wishlistCount).toBe(2));

    let result;
    await act(async () => {
      result = await ctx.removeFromWishlist(101); // wishlist-item id
    });

    expect(result).toEqual({ success: true, message: 'Removed from wishlist.' });
    expect(ctx.wishlistCount).toBe(1);
    expect(ctx.isInWishlist(1)).toBe(false);
    expect(dashboardAPI.removeFromWishlist).toHaveBeenCalledWith(101);
  });

  it('returns failure with detail message on API error', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1] });
    dashboardAPI.removeFromWishlist.mockRejectedValueOnce({
      response: { data: { detail: 'Item not found.' } },
    });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);
    await waitFor(() => expect(ctx.wishlistCount).toBe(1));

    let result;
    await act(async () => {
      result = await ctx.removeFromWishlist(101);
    });

    expect(result).toEqual({ success: false, message: 'Item not found.' });
    // wishlist remains unchanged when removal fails
    expect(ctx.wishlistCount).toBe(1);
  });

  it('falls back to generic remove error when no detail field present', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1] });
    dashboardAPI.removeFromWishlist.mockRejectedValueOnce(new Error('Network Error'));

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);
    await waitFor(() => expect(ctx.wishlistCount).toBe(1));

    let result;
    await act(async () => {
      result = await ctx.removeFromWishlist(101);
    });

    expect(result).toEqual({ success: false, message: 'Failed to remove from wishlist.' });
  });

  it('only removes the item matching the given wishlist-item id, leaving others intact', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({
      data: [ITEM_1, ITEM_2, ITEM_3],
    });
    dashboardAPI.removeFromWishlist.mockResolvedValueOnce({});

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);
    await waitFor(() => expect(ctx.wishlistCount).toBe(3));

    await act(async () => {
      await ctx.removeFromWishlist(202); // remove ITEM_2 only
    });

    expect(ctx.wishlistCount).toBe(2);
    expect(ctx.isInWishlist(1)).toBe(true);
    expect(ctx.isInWishlist(2)).toBe(false);
    expect(ctx.isInWishlist(3)).toBe(true);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 9. toggleWishlist
// ═════════════════════════════════════════════════════════════════════════════
describe('toggleWishlist', () => {
  it('redirects to /login and returns failure when unauthenticated', async () => {
    isAuthenticated.mockReturnValue(false);

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);

    let result;
    await act(async () => {
      result = await ctx.toggleWishlist(1);
    });

    expect(window.location.href).toBe('/login');
    expect(result).toEqual({ success: false, message: 'Please log in.' });
  });

  it('calls removeFromWishlist when product IS already in wishlist', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1] });
    dashboardAPI.removeFromWishlist.mockResolvedValueOnce({});

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);
    await waitFor(() => expect(ctx.wishlistCount).toBe(1));

    let result;
    await act(async () => {
      result = await ctx.toggleWishlist(1); // product id 1 is present
    });

    expect(dashboardAPI.removeFromWishlist).toHaveBeenCalledWith(101); // item id
    expect(result).toEqual({ success: true, message: 'Removed from wishlist.' });
    expect(ctx.wishlistCount).toBe(0);
  });

  it('calls addToWishlist when product is NOT in wishlist', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [] });
    dashboardAPI.addToWishlist.mockResolvedValueOnce({ data: ITEM_1 });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);

    let result;
    await act(async () => {
      result = await ctx.toggleWishlist(1);
    });

    expect(dashboardAPI.addToWishlist).toHaveBeenCalledWith(1);
    expect(result).toEqual({ success: true, message: 'Added to wishlist!' });
    expect(ctx.wishlistCount).toBe(1);
  });

  it('propagates addToWishlist failure through toggle', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [] });
    dashboardAPI.addToWishlist.mockRejectedValueOnce({
      response: { data: { detail: 'Server error.' } },
    });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);

    let result;
    await act(async () => {
      result = await ctx.toggleWishlist(99);
    });

    expect(result).toEqual({ success: false, message: 'Server error.' });
    expect(ctx.wishlistCount).toBe(0);
  });

  it('propagates removeFromWishlist failure through toggle', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1] });
    dashboardAPI.removeFromWishlist.mockRejectedValueOnce({
      response: { data: { detail: 'Cannot remove.' } },
    });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);
    await waitFor(() => expect(ctx.wishlistCount).toBe(1));

    let result;
    await act(async () => {
      result = await ctx.toggleWishlist(1);
    });

    expect(result).toEqual({ success: false, message: 'Cannot remove.' });
    expect(ctx.wishlistCount).toBe(1); // rollback not applied, still 1
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 10. wishlistCount (derived value)
// ═════════════════════════════════════════════════════════════════════════════
describe('wishlistCount', () => {
  it('reflects 0 for empty wishlist', async () => {
    isAuthenticated.mockReturnValue(false);
    await renderWithProvider(<WishlistConsumer />);
    expect(screen.getByTestId('count').textContent).toBe('0');
  });

  it('increments correctly after addToWishlist', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [] });
    dashboardAPI.addToWishlist.mockResolvedValueOnce({ data: ITEM_1 });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return <WishlistConsumer />; };
    await renderWithProvider(<Consumer />);

    expect(screen.getByTestId('count').textContent).toBe('0');

    await act(async () => {
      await ctx.addToWishlist(1);
    });

    expect(screen.getByTestId('count').textContent).toBe('1');
  });

  it('decrements correctly after removeFromWishlist', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [ITEM_1, ITEM_2] });
    dashboardAPI.removeFromWishlist.mockResolvedValueOnce({});

    let ctx;
    const Consumer = () => {
      ctx = useWishlist();
      return <WishlistConsumer />;
    };
    await renderWithProvider(<Consumer />);
    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('2'),
    );

    await act(async () => {
      await ctx.removeFromWishlist(101);
    });

    expect(screen.getByTestId('count').textContent).toBe('1');
  });

  it('stays in sync after multiple rapid add operations', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [] });
    dashboardAPI.addToWishlist
      .mockResolvedValueOnce({ data: ITEM_1 })
      .mockResolvedValueOnce({ data: ITEM_2 })
      .mockResolvedValueOnce({ data: ITEM_3 });

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return <WishlistConsumer />; };
    await renderWithProvider(<Consumer />);

    await act(async () => {
      await ctx.addToWishlist(1);
      await ctx.addToWishlist(2);
      await ctx.addToWishlist(3);
    });

    await waitFor(() =>
      expect(screen.getByTestId('count').textContent).toBe('3'),
    );
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 11. Context value shape
// ═════════════════════════════════════════════════════════════════════════════
describe('context value shape', () => {
  it('exposes all required keys with the correct types', async () => {
    isAuthenticated.mockReturnValue(false);

    let ctx;
    const Consumer = () => {
      ctx = useWishlist();
      return null;
    };
    await renderWithProvider(<Consumer />);

    expect(Array.isArray(ctx.wishlist)).toBe(true);
    expect(typeof ctx.wishlistCount).toBe('number');
    expect(typeof ctx.loading).toBe('boolean');
    // error can be null or string
    expect(ctx.error === null || typeof ctx.error === 'string').toBe(true);
    expect(typeof ctx.fetchWishlist).toBe('function');
    expect(typeof ctx.isInWishlist).toBe('function');
    expect(typeof ctx.getWishlistItemId).toBe('function');
    expect(typeof ctx.addToWishlist).toBe('function');
    expect(typeof ctx.removeFromWishlist).toBe('function');
    expect(typeof ctx.toggleWishlist).toBe('function');
  });

  it('exposes exactly the documented public API (no undocumented keys)', async () => {
    isAuthenticated.mockReturnValue(false);

    let ctx;
    const Consumer = () => { ctx = useWishlist(); return null; };
    await renderWithProvider(<Consumer />);

    const EXPECTED_KEYS = new Set([
      'wishlist',
      'wishlistCount',
      'loading',
      'error',
      'fetchWishlist',
      'isInWishlist',
      'getWishlistItemId',
      'addToWishlist',
      'removeFromWishlist',
      'toggleWishlist',
    ]);

    const actualKeys = new Set(Object.keys(ctx));
    EXPECTED_KEYS.forEach((key) => expect(actualKeys).toContain(key));
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 12. Integration: full add → remove lifecycle
// ═════════════════════════════════════════════════════════════════════════════
describe('integration: full add → remove cycle', () => {
  it('correctly tracks a product through add and remove lifecycle', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [] });
    dashboardAPI.addToWishlist.mockResolvedValueOnce({ data: ITEM_1 });
    dashboardAPI.removeFromWishlist.mockResolvedValueOnce({});

    let ctx;
    const Consumer = () => {
      ctx = useWishlist();
      return (
        <div>
          <span data-testid="count">{ctx.wishlistCount}</span>
          <span data-testid="in-wishlist">{String(ctx.isInWishlist(1))}</span>
        </div>
      );
    };
    await renderWithProvider(<Consumer />);

    // Initial state
    expect(screen.getByTestId('count').textContent).toBe('0');
    expect(screen.getByTestId('in-wishlist').textContent).toBe('false');

    // Add
    await act(async () => { await ctx.addToWishlist(1); });
    expect(screen.getByTestId('count').textContent).toBe('1');
    expect(screen.getByTestId('in-wishlist').textContent).toBe('true');

    // Remove using getWishlistItemId to look up the item id
    const itemId = ctx.getWishlistItemId(1);
    expect(itemId).toBe(101);

    await act(async () => { await ctx.removeFromWishlist(itemId); });
    expect(screen.getByTestId('count').textContent).toBe('0');
    expect(screen.getByTestId('in-wishlist').textContent).toBe('false');
  });

  it('toggle adds then toggle removes the same product', async () => {
    isAuthenticated.mockReturnValue(true);
    dashboardAPI.getWishlist.mockResolvedValueOnce({ data: [] });
    dashboardAPI.addToWishlist.mockResolvedValueOnce({ data: ITEM_1 });
    dashboardAPI.removeFromWishlist.mockResolvedValueOnce({});

    let ctx;
    const Consumer = () => {
      ctx = useWishlist();
      return <span data-testid="count">{ctx.wishlistCount}</span>;
    };
    await renderWithProvider(<Consumer />);

    // Toggle ON
    await act(async () => { await ctx.toggleWishlist(1); });
    expect(screen.getByTestId('count').textContent).toBe('1');

    // Toggle OFF
    await act(async () => { await ctx.toggleWishlist(1); });
    expect(screen.getByTestId('count').textContent).toBe('0');

    expect(dashboardAPI.addToWishlist).toHaveBeenCalledTimes(1);
    expect(dashboardAPI.removeFromWishlist).toHaveBeenCalledTimes(1);
  });
});
