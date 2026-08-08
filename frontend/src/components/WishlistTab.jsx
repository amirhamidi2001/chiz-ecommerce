// src/components/WishlistTab.jsx
import { Link } from 'react-router-dom';
import { useState } from 'react';
import { useWishlist } from '../context/WishlistContext';
import { useCart } from '../context/CartContext';

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fmt = (n) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n ?? 0);

// ─── Component ────────────────────────────────────────────────────────────────
const WishlistTab = () => {
  const {
    wishlist,
    loading,
    removeFromWishlist,
    fetchWishlist,
  } = useWishlist();

  const { addToCart } = useCart();

  // Per-item loading flags
  const [removing, setRemoving] = useState(null);       // wishlist item id
  const [addingToCart, setAddingToCart] = useState(null); // wishlist item id
  const [addingAll, setAddingAll] = useState(false);

  // Toast state
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  // ── Remove a single item ─────────────────────────────────────────────────
  const handleRemove = async (itemId) => {
    setRemoving(itemId);
    const result = await removeFromWishlist(itemId);
    showToast(result.message, result.success ? 'success' : 'error');
    setRemoving(null);
  };

  // ── Add a single item to cart, then auto-remove from wishlist ────────────
  const handleAddToCart = async (item) => {
    setAddingToCart(item.id);
    const cartResult = await addToCart(item.product.id, 1);
    if (cartResult.success) {
      // Auto-remove from wishlist after successful add-to-cart (UX task #7)
      await removeFromWishlist(item.id);
      showToast(`${item.product.name} moved to cart!`);
    } else {
      showToast(cartResult.message || 'Could not add to cart', 'error');
    }
    setAddingToCart(null);
  };

  // ── Add all available items to cart ──────────────────────────────────────
  const handleAddAll = async () => {
    const available = wishlist.filter((i) => i.product.stock > 0);
    if (available.length === 0) {
      showToast('No in-stock items to add', 'error');
      return;
    }

    setAddingAll(true);
    let successCount = 0;

    for (const item of available) {
      const cartResult = await addToCart(item.product.id, 1);
      if (cartResult.success) {
        await removeFromWishlist(item.id);
        successCount++;
      }
    }

    if (successCount > 0) {
      showToast(`${successCount} item${successCount > 1 ? 's' : ''} moved to cart!`);
    } else {
      showToast('Could not add items to cart', 'error');
    }
    setAddingAll(false);
  };

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div>
      {/* ── Toast notification ────────────────────────────────────────── */}
      {toast && (
        <div
          className={`fixed top-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg text-sm font-medium text-white transition-all ${toast.type === 'error' ? 'bg-red-500' : 'bg-teal-600'
            }`}
        >
          {toast.msg}
        </div>
      )}

      {/* ── Header ───────────────────────────────────────────────────── */}
      <div className="flex flex-wrap justify-between items-center mb-6 gap-3">
        <h2 className="text-2xl font-bold text-gray-800">
          My Wishlist
          {wishlist.length > 0 && (
            <span className="ml-2 text-sm font-normal text-gray-400">({wishlist.length} items)</span>
          )}
        </h2>

        {wishlist.length > 0 && (
          <button
            onClick={handleAddAll}
            disabled={addingAll}
            className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-60 transition text-sm font-medium"
          >
            {addingAll ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Adding all…
              </>
            ) : (
              <>
                <i className="bi bi-cart-plus" />
                Add All to Cart
              </>
            )}
          </button>
        )}
      </div>

      {/* ── Loading skeleton ─────────────────────────────────────────── */}
      {loading ? (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-72 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>

      ) : wishlist.length === 0 ? (
        /* ── Empty state ──────────────────────────────────────────────── */
        <div className="text-center py-16 text-gray-400">
          <i className="bi bi-heart text-5xl mb-4 block" />
          <p className="text-lg font-medium text-gray-500">Your wishlist is empty</p>
          <p className="text-sm mt-1">Save items you love to buy them later.</p>
          <Link
            to="/category"
            className="mt-5 inline-block px-5 py-2 bg-teal-600 text-white rounded-lg text-sm hover:bg-teal-700 transition"
          >
            Explore Products
          </Link>
        </div>

      ) : (
        /* ── Product grid ─────────────────────────────────────────────── */
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {wishlist.map((item) => {
            const p = item.product;
            const isRemoving = removing === item.id;
            const isAddingThis = addingToCart === item.id;
            const outOfStock = p.stock === 0;

            return (
              <div
                key={item.id}
                className="bg-white border border-gray-100 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition"
              >
                {/* Product image */}
                <div className="relative">
                  <Link to={`/product/${p.slug}`}>
                    <img
                      src={p.thumbnail_url || '/assets/img/product/product-1.webp'}
                      alt={p.name}
                      className="w-full h-52 object-cover hover:scale-105 transition duration-300"
                    />
                  </Link>

                  {/* Remove from wishlist */}
                  <button
                    onClick={() => handleRemove(item.id)}
                    disabled={isRemoving}
                    title="Remove from wishlist"
                    className="absolute top-2 right-2 bg-white p-1.5 rounded-full shadow hover:bg-red-50 transition disabled:opacity-60"
                  >
                    {isRemoving ? (
                      <div className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <i className="bi bi-trash text-red-500 text-sm" />
                    )}
                  </button>

                  {/* Sale badge */}
                  {p.is_sale && p.discount_percent > 0 && (
                    <span className="absolute top-2 left-2 bg-red-500 text-white text-xs px-2 py-0.5 rounded font-semibold">
                      -{p.discount_percent}%
                    </span>
                  )}

                  {/* Out of stock overlay */}
                  {outOfStock && (
                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center text-white text-sm font-medium">
                      Out of Stock
                    </div>
                  )}
                </div>

                {/* Product info */}
                <div className="p-4">
                  <Link to={`/product/${p.slug}`}>
                    <h4 className="font-semibold text-gray-800 text-sm line-clamp-2 hover:text-teal-600 transition">
                      {p.name}
                    </h4>
                  </Link>

                  {p.category_name && (
                    <p className="text-xs text-gray-400 mt-0.5">{p.category_name}</p>
                  )}

                  {/* Star rating */}
                  <div className="flex items-center gap-1 text-yellow-400 text-xs mt-1">
                    {[...Array(5)].map((_, i) => (
                      <i
                        key={i}
                        className={`bi ${i < Math.floor(p.rating ?? 0)
                            ? 'bi-star-fill'
                            : i < (p.rating ?? 0)
                              ? 'bi-star-half'
                              : 'bi-star'
                          }`}
                      />
                    ))}
                    <span className="text-gray-400 ml-1">({p.reviews_count ?? 0})</span>
                  </div>

                  {/* Price */}
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-base font-bold text-gray-800">{fmt(p.price)}</span>
                    {p.original_price && (
                      <span className="text-sm text-gray-400 line-through">{fmt(p.original_price)}</span>
                    )}
                  </div>

                  {/* Add to Cart — disabled when out of stock */}
                  <button
                    onClick={() => handleAddToCart(item)}
                    disabled={outOfStock || isAddingThis || addingAll}
                    className="w-full mt-3 py-2 bg-gray-800 text-white text-sm rounded-lg hover:bg-gray-900 transition disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                  >
                    {isAddingThis ? (
                      <span className="inline-flex items-center justify-center gap-2">
                        <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Adding…
                      </span>
                    ) : outOfStock ? (
                      'Out of Stock'
                    ) : (
                      <span className="inline-flex items-center justify-center gap-1.5">
                        <i className="bi bi-cart-plus" />
                        Add to Cart
                      </span>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Refresh hint ──────────────────────────────────────────────── */}
      {!loading && wishlist.length > 0 && (
        <div className="mt-6 text-center">
          <button
            onClick={fetchWishlist}
            className="text-xs text-gray-400 hover:text-teal-600 transition"
          >
            <i className="bi bi-arrow-clockwise mr-1" />
            Refresh wishlist
          </button>
        </div>
      )}
    </div>
  );
};

export default WishlistTab;
