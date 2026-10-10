// src/context/CartContext.jsx
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
    getCart,
    addToCart,
    updateCartItem,
    removeCartItem,
    clearCart,
    applyCoupon as applyCouponRequest,
    removeCoupon as removeCouponRequest,
} from '../services/api';

// Surface the backend's own message (e.g. "This coupon has expired.") rather
// than a generic one. Coupon rejections arrive as { coupon: ["..."] }; a
// malformed request as { code: ["..."] }; throttling/other as { detail }.
const firstString = (v) => (Array.isArray(v) ? v[0] : v);
const couponErrorMessage = (err, fallback) => {
    const data = err.response?.data;
    const msg = firstString(data?.coupon) || firstString(data?.code) || firstString(data?.detail);
    return typeof msg === 'string' && msg ? msg : fallback;
};

// ─── Context ──────────────────────────────────────────────────────────────────
const CartContext = createContext(null);

// ─── Provider ─────────────────────────────────────────────────────────────────
export const CartProvider = ({ children }) => {
    const [cart, setCart] = useState(null);    // full cart object from API
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Total unit count used for the header badge
    const cartCount = cart?.total_items ?? 0;

    // ── Fetch full cart from API ───────────────────────────────────────────────
    const fetchCart = useCallback(async () => {
        // No auth gate: the backend returns a valid (possibly empty) cart
        // for anonymous sessions too (Task 5.1.1.2), so this runs
        // unconditionally for every visitor.
        setLoading(true);
        setError(null);
        try {
            const { data } = await getCart();
            setCart(data);
        } catch (err) {
            // 401 is handled by the axios interceptor (redirect to /login)
            if (err.response?.status !== 401) {
                setError('Failed to load cart.');
            }
        } finally {
            setLoading(false);
        }
    }, []);

    // ── Silent refetch ────────────────────────────────────────────────────────
    // Same request as fetchCart but leaves `loading`/`error` alone, so pages
    // that swap their content for a skeleton while loading don't flash after
    // an action that merely changed the cart's totals (applying a coupon).
    // Returns whether the cart was refreshed; never throws.
    const refreshCart = useCallback(async () => {
        try {
            const { data } = await getCart();
            setCart(data);
            return true;
        } catch {
            return false;
        }
    }, []);

    // Fetch cart on mount and whenever the user logs in/out
    useEffect(() => {
        fetchCart();

        const onAuthChange = () => fetchCart();
        window.addEventListener('auth-change', onAuthChange);
        window.addEventListener('storage', (e) => {
            if (e.key === 'access_token') fetchCart();
        });

        return () => window.removeEventListener('auth-change', onAuthChange);
    }, [fetchCart]);

    // ── Add item ──────────────────────────────────────────────────────────────
    // Anonymous add-to-cart works now (Task 5.1.1.2) — no auth gate, no
    // redirect to /login. Hits the same API call as an authenticated user;
    // the backend resolves the correct cart (user- or session-based) itself.
    const handleAddToCart = async (variantId, quantity = 1) => {
        try {
            const { data } = await addToCart(variantId, quantity);
            setCart(data);
            return { success: true, message: 'Item added to cart!' };
        } catch (err) {
            const msg =
                err.response?.data?.variant_id ||
                err.response?.data?.quantity ||
                err.response?.data?.detail ||
                'Failed to add item to cart.';
            return { success: false, message: msg };
        }
    };

    // ── Update quantity ───────────────────────────────────────────────────────
    const handleUpdateItem = async (itemId, quantity) => {
        try {
            const { data } = await updateCartItem(itemId, quantity);
            setCart(data);
            return { success: true };
        } catch (err) {
            const msg = err.response?.data?.quantity || 'Failed to update quantity.';
            return { success: false, message: msg };
        }
    };

    // ── Remove item ───────────────────────────────────────────────────────────
    const handleRemoveItem = async (itemId) => {
        try {
            const { data } = await removeCartItem(itemId);
            setCart(data);
            return { success: true };
        } catch (err) {
            return { success: false, message: 'Failed to remove item.' };
        }
    };

    // ── Clear cart ────────────────────────────────────────────────────────────
    const handleClearCart = async () => {
        try {
            const { data } = await clearCart();
            setCart(data);
            return { success: true };
        } catch (err) {
            return { success: false, message: 'Failed to clear cart.' };
        }
    };

    // ── Coupon ────────────────────────────────────────────────────────────────
    // The apply/remove endpoints don't return a cart, so refetch it: the
    // backend recomputes coupon_code / coupon_discount / coupon_error (and
    // the page's displayed total follows) — nothing is derived client-side.
    // If that refetch fails the coupon change itself still succeeded, so
    // report success rather than a misleading failure.
    const handleApplyCoupon = async (code) => {
        try {
            await applyCouponRequest(code);
        } catch (err) {
            return {
                success: false,
                message: couponErrorMessage(err, 'Could not apply coupon. Please try again.'),
            };
        }
        await refreshCart();
        return { success: true };
    };

    const handleRemoveCoupon = async () => {
        try {
            await removeCouponRequest();
        } catch (err) {
            return {
                success: false,
                message: couponErrorMessage(err, 'Could not remove coupon. Please try again.'),
            };
        }
        await refreshCart();
        return { success: true };
    };

    const value = {
        cart,
        cartCount,
        loading,
        error,
        fetchCart,
        refreshCart,
        addToCart: handleAddToCart,
        updateItem: handleUpdateItem,
        removeItem: handleRemoveItem,
        clearCart: handleClearCart,
        applyCoupon: handleApplyCoupon,
        removeCoupon: handleRemoveCoupon,
    };

    return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
};

// ─── Hook ─────────────────────────────────────────────────────────────────────
export const useCart = () => {
    const ctx = useContext(CartContext);
    if (!ctx) throw new Error('useCart must be used inside <CartProvider>');
    return ctx;
};

export default CartContext;
