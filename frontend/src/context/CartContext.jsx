// src/context/CartContext.jsx
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getCart, addToCart, updateCartItem, removeCartItem, clearCart } from '../services/api';
import { isAuthenticated } from '../services/api';

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
        if (!isAuthenticated()) {
            setCart(null);
            return;
        }
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
    const handleAddToCart = async (productId, quantity = 1) => {
        if (!isAuthenticated()) {
            window.location.href = '/login';
            return { success: false, message: 'Please log in to add items to your cart.' };
        }
        try {
            const { data } = await addToCart(productId, quantity);
            setCart(data);
            return { success: true, message: 'Item added to cart!' };
        } catch (err) {
            const msg =
                err.response?.data?.product_id ||
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

    const value = {
        cart,
        cartCount,
        loading,
        error,
        fetchCart,
        addToCart: handleAddToCart,
        updateItem: handleUpdateItem,
        removeItem: handleRemoveItem,
        clearCart: handleClearCart,
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
