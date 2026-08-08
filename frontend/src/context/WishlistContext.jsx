// src/context/WishlistContext.jsx
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { dashboardAPI, isAuthenticated } from '../services/api';

// ─── Context ──────────────────────────────────────────────────────────────────
const WishlistContext = createContext(null);

// ─── Provider ─────────────────────────────────────────────────────────────────
export const WishlistProvider = ({ children }) => {
    // Array of wishlist item objects: [{ id, product: { id, slug, name, ... } }]
    const [wishlist, setWishlist] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Derived count used for the header badge
    const wishlistCount = wishlist.length;

    // ── Fetch full wishlist from API ───────────────────────────────────────────
    const fetchWishlist = useCallback(async () => {
        if (!isAuthenticated()) {
            setWishlist([]);
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const { data } = await dashboardAPI.getWishlist();
            // API may return { results: [...] } (paginated) or a plain array
            setWishlist(data.results ?? data);
        } catch (err) {
            if (err.response?.status !== 401) {
                setError('Failed to load wishlist.');
            }
        } finally {
            setLoading(false);
        }
    }, []);

    // Fetch on mount and re-fetch whenever the user logs in / out
    useEffect(() => {
        fetchWishlist();

        const onAuthChange = () => fetchWishlist();
        window.addEventListener('auth-change', onAuthChange);

        const onStorage = (e) => {
            if (e.key === 'access_token') fetchWishlist();
        };
        window.addEventListener('storage', onStorage);

        return () => {
            window.removeEventListener('auth-change', onAuthChange);
            window.removeEventListener('storage', onStorage);
        };
    }, [fetchWishlist]);

    // ── Check whether a product (by product.id) is already wishlisted ─────────
    const isInWishlist = useCallback(
        (productId) => wishlist.some((item) => item.product?.id === productId),
        [wishlist],
    );

    // ── Get the wishlist-item id for a given product id (needed for DELETE) ────
    const getWishlistItemId = useCallback(
        (productId) => wishlist.find((item) => item.product?.id === productId)?.id ?? null,
        [wishlist],
    );

    // ── Add a product to the wishlist ─────────────────────────────────────────
    const addToWishlist = async (productId) => {
        if (!isAuthenticated()) {
            window.location.href = '/login';
            return { success: false, message: 'Please log in to save items to your wishlist.' };
        }
        // Optimistic: skip if already present
        if (isInWishlist(productId)) {
            return { success: true, message: 'Already in wishlist.' };
        }
        try {
            const { data } = await dashboardAPI.addToWishlist(productId);
            // data is the new wishlist item: { id, product: { ... } }
            setWishlist((prev) => [...prev, data]);
            return { success: true, message: 'Added to wishlist!' };
        } catch (err) {
            const msg =
                err.response?.data?.product_id?.[0] ||
                err.response?.data?.detail ||
                'Failed to add to wishlist.';
            return { success: false, message: msg };
        }
    };

    // ── Remove a product from the wishlist ────────────────────────────────────
    // Accepts either the wishlist-item id directly, or a productId with a flag
    const removeFromWishlist = async (wishlistItemId) => {
        try {
            await dashboardAPI.removeFromWishlist(wishlistItemId);
            setWishlist((prev) => prev.filter((item) => item.id !== wishlistItemId));
            return { success: true, message: 'Removed from wishlist.' };
        } catch (err) {
            const msg = err.response?.data?.detail || 'Failed to remove from wishlist.';
            return { success: false, message: msg };
        }
    };

    // ── Toggle: add if absent, remove if present ──────────────────────────────
    const toggleWishlist = async (productId) => {
        if (!isAuthenticated()) {
            window.location.href = '/login';
            return { success: false, message: 'Please log in.' };
        }
        if (isInWishlist(productId)) {
            const itemId = getWishlistItemId(productId);
            return removeFromWishlist(itemId);
        }
        return addToWishlist(productId);
    };

    const value = {
        wishlist,
        wishlistCount,
        loading,
        error,
        fetchWishlist,
        isInWishlist,
        getWishlistItemId,
        addToWishlist,
        removeFromWishlist,
        toggleWishlist,
    };

    return (
        <WishlistContext.Provider value={value}>
            {children}
        </WishlistContext.Provider>
    );
};

// ─── Hook ─────────────────────────────────────────────────────────────────────
export const useWishlist = () => {
    const ctx = useContext(WishlistContext);
    if (!ctx) throw new Error('useWishlist must be used inside <WishlistProvider>');
    return ctx;
};

export default WishlistContext;
