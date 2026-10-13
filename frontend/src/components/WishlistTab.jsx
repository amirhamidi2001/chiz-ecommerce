// src/components/WishlistTab.jsx
import { Link } from 'react-router-dom';
import { useState } from 'react';
import { useWishlist } from '../context/WishlistContext';
import { useCart } from '../context/CartContext';
import { dashboardAPI } from '../services/api';
import VariantPicker from './VariantPicker';

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fmt = (n) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n ?? 0);

// ─── A product with several options: pick one, then confirm ──────────────────
// Shown when the server answers "move to cart" with 300 (single item) or lists
// the product under `needs_selection` (move all). Selection state is local;
// the parent only hears about the final choice.
const VariantChoice = ({ variants, busy, onConfirm }) => {
  const [selectedId, setSelectedId] = useState(null);

  return (
    <div className="mt-3 space-y-2">
      <VariantPicker
        variants={variants}
        selectedId={selectedId}
        onSelect={setSelectedId}
        disabled={busy}
      />
      <button
        type="button"
        onClick={() => onConfirm(selectedId)}
        disabled={selectedId === null || busy}
        className="px-3 py-1.5 bg-teal-600 text-white text-xs rounded-lg hover:bg-teal-700 transition disabled:opacity-50 disabled:cursor-not-allowed font-medium"
      >
        {busy ? 'Moving…' : 'Move selected option to cart'}
      </button>
    </div>
  );
};

const BAD_VARIANT_MESSAGE =
  'That option is no longer available — please choose again.';

// ─── Component ────────────────────────────────────────────────────────────────
const WishlistTab = () => {
  const {
    wishlist,
    loading,
    removeFromWishlist,
    fetchWishlist,
    refreshWishlist,
  } = useWishlist();

  const { refreshCart } = useCart();

  // Per-item loading flags
  const [removing, setRemoving] = useState(null);       // wishlist item id
  const [moving, setMoving] = useState(null);           // wishlist item id
  const [movingAll, setMovingAll] = useState(false);

  // Items whose product has several purchasable variants and now needs the
  // customer to choose: { [wishlistItemId]: variants[] } (single "Move to Cart").
  const [choices, setChoices] = useState({});
  // Result of "Move All to Cart": { moved, needsSelection, unavailable }.
  // Kept on screen (dismissible) so nothing is dropped without explanation.
  const [summary, setSummary] = useState(null);

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

  // ── Both lists changed (the item left one and entered the other) ──────────
  // Silent refetches, so neither list flashes a loading state.
  const refreshBoth = () => Promise.all([refreshWishlist(), refreshCart()]);

  const forgetPending = (itemId) => {
    setChoices((prev) => {
      const { [itemId]: _gone, ...rest } = prev;
      return rest;
    });
    setSummary((prev) =>
      prev
        ? {
            ...prev,
            needsSelection: prev.needsSelection.filter(
              (entry) => entry.wishlist_item_id !== itemId,
            ),
          }
        : prev,
    );
  };

  // ── Move one item to the cart ────────────────────────────────────────────
  // The cart holds a specific variant, the wishlist a product. The server
  // resolves it when only one variant is purchasable; with several it answers
  // 300 + the choices (axios rejects that, hence the catch), and we resubmit
  // with the customer's pick as `variantId`.
  const moveItem = async (itemId, productName, variantId) => {
    setMoving(itemId);
    try {
      await dashboardAPI.moveWishlistItemToCart(itemId, variantId);
      forgetPending(itemId);
      showToast(`${productName} moved to cart!`);
      await refreshBoth();
    } catch (err) {
      const status = err.response?.status;
      const data = err.response?.data;
      if (status === 300) {
        setChoices((prev) => ({ ...prev, [itemId]: data.variants }));
      } else if (status === 400 && data?.variant_id) {
        // Stale pick (it sold out while the picker was open). Don't guess a
        // replacement: drop the picker so the next click fetches fresh choices.
        forgetPending(itemId);
        showToast(BAD_VARIANT_MESSAGE, 'error');
        await refreshBoth();
      } else if (status === 404) {
        // Already moved elsewhere (another tab) — the lists are just stale.
        forgetPending(itemId);
        showToast('That item is no longer on your wishlist.', 'error');
        await refreshBoth();
      } else {
        showToast(data?.detail || 'Could not move item to cart', 'error');
      }
    } finally {
      setMoving(null);
    }
  };

  // ── Move everything that can be moved without asking ─────────────────────
  const handleMoveAll = async () => {
    setMovingAll(true);
    try {
      const { data } = await dashboardAPI.moveAllWishlistToCart();
      setSummary({
        moved: data.moved,
        needsSelection: data.needs_selection,
        unavailable: data.unavailable,
      });
      // The summary hosts the pickers for these; don't show two per item.
      setChoices((prev) => {
        const next = { ...prev };
        data.needs_selection.forEach((entry) => delete next[entry.wishlist_item_id]);
        return next;
      });
      await refreshBoth();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Could not move items to cart', 'error');
    } finally {
      setMovingAll(false);
    }
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
            onClick={handleMoveAll}
            disabled={movingAll || moving !== null}
            className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-60 transition text-sm font-medium"
          >
            {movingAll ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Moving all…
              </>
            ) : (
              <>
                <i className="bi bi-cart-plus" />
                Move All to Cart
              </>
            )}
          </button>
        )}
      </div>

      {/* ── Move-all summary ─────────────────────────────────────────── */}
      {summary && (
        <section
          aria-label="Move to cart summary"
          className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-xl text-sm space-y-4"
        >
          <div className="flex justify-between items-start gap-3">
            <p className="font-semibold text-gray-800">
              {summary.moved.length > 0
                ? `${summary.moved.length} item${summary.moved.length > 1 ? 's' : ''} moved to your cart`
                : 'Nothing could be moved automatically'}
            </p>
            <button
              type="button"
              onClick={() => setSummary(null)}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              Dismiss
            </button>
          </div>

          {summary.moved.length > 0 && (
            <ul className="list-disc list-inside text-gray-600">
              {summary.moved.map((name) => (
                <li key={name}>{name}</li>
              ))}
            </ul>
          )}

          {summary.needsSelection.length > 0 && (
            <div>
              <p className="font-medium text-gray-800">
                Choose an option to finish moving
                {summary.needsSelection.length > 1 ? ' these items' : ' this item'}:
              </p>
              <div className="mt-2 space-y-4">
                {summary.needsSelection.map((entry) => (
                  <div key={entry.wishlist_item_id}>
                    <p className="text-gray-700">{entry.product}</p>
                    <VariantChoice
                      variants={entry.variants}
                      busy={moving === entry.wishlist_item_id}
                      onConfirm={(variantId) =>
                        moveItem(entry.wishlist_item_id, entry.product, variantId)
                      }
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {summary.unavailable.length > 0 && (
            <div>
              <p className="font-medium text-gray-800">
                Currently unavailable (still on your wishlist):
              </p>
              <ul className="list-disc list-inside text-gray-600">
                {summary.unavailable.map((entry) => (
                  <li key={entry.wishlist_item_id}>{entry.product}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

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
            const isMovingThis = moving === item.id;

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

                  {/* Move to Cart — availability and variant choice are the
                      server's call (Product.stock is no longer authoritative) */}
                  <button
                    onClick={() => moveItem(item.id, p.name)}
                    disabled={isMovingThis || movingAll}
                    className="w-full mt-3 py-2 bg-gray-800 text-white text-sm rounded-lg hover:bg-gray-900 transition disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                  >
                    {isMovingThis && !choices[item.id] ? (
                      <span className="inline-flex items-center justify-center gap-2">
                        <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Moving…
                      </span>
                    ) : (
                      <span className="inline-flex items-center justify-center gap-1.5">
                        <i className="bi bi-cart-plus" />
                        Move to Cart
                      </span>
                    )}
                  </button>

                  {/* This product has several options: ask which one */}
                  {choices[item.id] && (
                    <VariantChoice
                      variants={choices[item.id]}
                      busy={isMovingThis}
                      onConfirm={(variantId) => moveItem(item.id, p.name, variantId)}
                    />
                  )}
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
