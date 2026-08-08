// src/pages/Cart.jsx
import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { isAuthenticated } from '../services/api';

// ─── Shipping options ──────────────────────────────────────────────────────
const SHIPPING_OPTIONS = [
  { id: 'standard', label: 'Standard Delivery', price: 4.99, eta: '5-7 days' },
  { id: 'express', label: 'Express Delivery', price: 12.99, eta: '2-3 days' },
  { id: 'free', label: 'Free Shipping', price: 0, eta: '7-14 days', minOrder: 300 },
];

const TAX_RATE = 0.10; // 10%

// ─── Toast notification ────────────────────────────────────────────────────
const Toast = ({ message, type, onClose }) => {
  useEffect(() => {
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [onClose]);

  const colors = type === 'success'
    ? 'bg-teal-600 text-white'
    : 'bg-red-500 text-white';

  return (
    <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-lg ${colors} transition-all`}>
      <i className={`bi ${type === 'success' ? 'bi-check-circle' : 'bi-exclamation-circle'}`}></i>
      <span className="text-sm font-medium">{message}</span>
      <button onClick={onClose} className="ml-2 opacity-70 hover:opacity-100">
        <i className="bi bi-x"></i>
      </button>
    </div>
  );
};

// ─── Skeleton loader ───────────────────────────────────────────────────────
const CartSkeleton = () => (
  <div className="space-y-4">
    {[...Array(3)].map((_, i) => (
      <div key={i} className="flex gap-4 py-5 border-b border-gray-100 animate-pulse">
        <div className="w-20 h-20 bg-gray-200 rounded-lg flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-3 bg-gray-200 rounded w-1/2" />
          <div className="h-3 bg-gray-100 rounded w-1/4" />
        </div>
        <div className="w-20 h-8 bg-gray-200 rounded" />
      </div>
    ))}
  </div>
);

// ─── Cart Item Row ─────────────────────────────────────────────────────────
const CartItemRow = ({ item, onUpdateQty, onRemove, updatingId }) => {
  const price = Number(item.unit_price);
  const subtotal = Number(item.subtotal);
  const original = item.product.original_price ? Number(item.product.original_price) : null;
  const isBusy = updatingId === item.id;

  return (
    <div className="flex flex-col md:grid md:grid-cols-12 gap-4 py-5 border-b border-gray-100">
      {/* Product Info */}
      <div className="flex gap-4 md:col-span-6">
        <div className="w-20 h-20 flex-shrink-0 bg-gray-100 rounded-lg overflow-hidden">
          {item.product.image ? (
            <img
              src={item.product.image}
              alt={item.product.name}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-300">
              <i className="bi bi-image text-2xl"></i>
            </div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <h6 className="font-semibold text-gray-800 line-clamp-2">
            <Link to={`/product/${item.product.slug}`} className="hover:text-teal-600 transition">
              {item.product.name}
            </Link>
          </h6>
          <div className="text-xs text-gray-400 mt-1">
            {item.product.stock > 0 ? (
              <span className="text-teal-600">
                <i className="bi bi-check-circle me-1"></i>In Stock
              </span>
            ) : (
              <span className="text-red-500">Out of Stock</span>
            )}
          </div>
          <button
            onClick={() => onRemove(item.id)}
            disabled={isBusy}
            className="text-red-400 text-sm mt-2 flex items-center gap-1 hover:text-red-600 transition disabled:opacity-40"
          >
            {isBusy ? (
              <i className="bi bi-arrow-clockwise animate-spin"></i>
            ) : (
              <i className="bi bi-trash"></i>
            )}
            Remove
          </button>
        </div>
      </div>

      {/* Price */}
      <div className="flex items-center justify-between md:justify-center md:col-span-2">
        <span className="md:hidden text-sm text-gray-500 font-medium">Price:</span>
        <div className="text-right md:text-center">
          {original && original > price ? (
            <>
              <span className="text-gray-400 line-through text-xs block">${original.toFixed(2)}</span>
              <span className="font-semibold text-teal-700">${price.toFixed(2)}</span>
            </>
          ) : (
            <span className="font-semibold text-gray-800">${price.toFixed(2)}</span>
          )}
        </div>
      </div>

      {/* Quantity */}
      <div className="flex items-center justify-between md:justify-center md:col-span-2">
        <span className="md:hidden text-sm text-gray-500 font-medium">Qty:</span>
        <div className="flex items-center border border-gray-300 rounded-lg overflow-hidden">
          <button
            onClick={() => item.quantity > 1 && onUpdateQty(item.id, item.quantity - 1)}
            disabled={isBusy || item.quantity <= 1}
            className="px-2.5 py-1.5 hover:bg-gray-100 transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <i className="bi bi-dash"></i>
          </button>
          <span className="w-10 text-center text-sm font-medium border-x border-gray-300 py-1.5">
            {isBusy ? <i className="bi bi-three-dots"></i> : item.quantity}
          </span>
          <button
            onClick={() => onUpdateQty(item.id, item.quantity + 1)}
            disabled={isBusy}
            className="px-2.5 py-1.5 hover:bg-gray-100 transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <i className="bi bi-plus"></i>
          </button>
        </div>
      </div>

      {/* Line Total */}
      <div className="flex items-center justify-between md:justify-center md:col-span-2">
        <span className="md:hidden text-sm text-gray-500 font-medium">Total:</span>
        <span className="font-bold text-gray-800">${subtotal.toFixed(2)}</span>
      </div>
    </div>
  );
};

// ─── Main Cart Page ────────────────────────────────────────────────────────
const Cart = () => {
  const navigate = useNavigate();
  const { cart, loading, error, fetchCart, updateItem, removeItem, clearCart } = useCart();

  const [shippingMethod, setShippingMethod] = useState('standard');
  const [updatingId, setUpdatingId] = useState(null);  // item being updated
  const [clearing, setClearing] = useState(false);
  const [toast, setToast] = useState(null);  // { message, type }
  const [couponCode, setCouponCode] = useState('');
  const [discount, setDiscount] = useState(0);
  const [couponApplied, setCouponApplied] = useState(false);

  const showToast = (message, type = 'success') => setToast({ message, type });
  const hideToast = () => setToast(null);

  // Reload cart when page mounts (in case navigated here from another page)
  useEffect(() => {
    if (!isAuthenticated()) {
      navigate('/login');
      return;
    }
    fetchCart();
  }, []);

  // ── Derived totals ───────────────────────────────────────────────────────
  const subtotal = Number(cart?.subtotal ?? 0);

  const getShippingCost = () => {
    const option = SHIPPING_OPTIONS.find((o) => o.id === shippingMethod);
    if (!option) return 0;
    if (option.id === 'free' && subtotal < (option.minOrder ?? 0)) return 12.99;
    return option.price;
  };

  const shippingCost = getShippingCost();
  const tax = subtotal * TAX_RATE;
  const total = subtotal + shippingCost + tax - discount;

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleUpdateQty = async (itemId, newQty) => {
    setUpdatingId(itemId);
    const result = await updateItem(itemId, newQty);
    setUpdatingId(null);
    if (!result.success) showToast(result.message, 'error');
  };

  const handleRemove = async (itemId) => {
    setUpdatingId(itemId);
    const result = await removeItem(itemId);
    setUpdatingId(null);
    if (result.success) {
      showToast('Item removed from cart.');
    } else {
      showToast(result.message, 'error');
    }
  };

  const handleClear = async () => {
    if (!window.confirm('Are you sure you want to clear your entire cart?')) return;
    setClearing(true);
    const result = await clearCart();
    setClearing(false);
    if (result.success) {
      showToast('Cart cleared.');
      setDiscount(0);
      setCouponApplied(false);
      setCouponCode('');
    } else {
      showToast(result.message, 'error');
    }
  };

  const applyCoupon = () => {
    if (couponApplied) {
      showToast('A coupon is already applied.', 'error');
      return;
    }
    if (couponCode.toUpperCase() === 'DISCOUNT20') {
      setDiscount(20);
      setCouponApplied(true);
      showToast('Coupon applied! $20 discount added.');
    } else {
      showToast('Invalid coupon code.', 'error');
    }
  };

  const items = cart?.items ?? [];

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      {/* Toast */}
      {toast && <Toast message={toast.message} type={toast.type} onClose={hideToast} />}

      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">
            Shopping Cart
            {!loading && items.length > 0 && (
              <span className="ml-3 text-lg text-gray-500 font-normal">
                ({cart.total_items} {cart.total_items === 1 ? 'item' : 'items'})
              </span>
            )}
          </h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Cart</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Cart Section */}
      <section className="py-12 bg-white">
        <div className="container mx-auto px-4">

          {/* API Error banner */}
          {error && !loading && (
            <div className="mb-6 flex items-center gap-3 bg-red-50 border border-red-200 text-red-700 px-5 py-4 rounded-xl">
              <i className="bi bi-exclamation-triangle text-lg"></i>
              <span>{error}</span>
              <button onClick={fetchCart} className="ml-auto text-sm underline hover:no-underline">
                Retry
              </button>
            </div>
          )}

          <div className="flex flex-col lg:flex-row gap-8">
            {/* ── Left Column: Cart Items ──────────────────────────────── */}
            <div className="lg:w-2/3">
              <div className="bg-white border border-gray-100 rounded-xl shadow-sm p-4 md:p-6">

                {/* Table Header (Desktop) */}
                {!loading && items.length > 0 && (
                  <div className="hidden md:grid grid-cols-12 gap-4 pb-3 mb-2 border-b border-gray-100 text-gray-500 text-xs font-semibold uppercase tracking-wider">
                    <div className="col-span-6">Product</div>
                    <div className="col-span-2 text-center">Price</div>
                    <div className="col-span-2 text-center">Quantity</div>
                    <div className="col-span-2 text-center">Total</div>
                  </div>
                )}

                {/* Loading skeleton */}
                {loading && <CartSkeleton />}

                {/* Empty state */}
                {!loading && items.length === 0 && (
                  <div className="text-center py-16">
                    <i className="bi bi-cart3 text-7xl text-gray-200 block mb-4"></i>
                    <h3 className="text-xl font-semibold text-gray-600 mb-2">Your cart is empty</h3>
                    <p className="text-gray-400 mb-6 text-sm">Looks like you haven't added anything yet.</p>
                    <Link
                      to="/category"
                      className="inline-flex items-center gap-2 bg-teal-600 text-white px-6 py-3 rounded-xl hover:bg-teal-700 transition font-medium"
                    >
                      <i className="bi bi-bag-plus"></i>
                      Continue Shopping
                    </Link>
                  </div>
                )}

                {/* Cart item rows */}
                {!loading && items.map((item) => (
                  <CartItemRow
                    key={item.id}
                    item={item}
                    onUpdateQty={handleUpdateQty}
                    onRemove={handleRemove}
                    updatingId={updatingId}
                  />
                ))}

                {/* Cart Actions */}
                {!loading && items.length > 0 && (
                  <div className="flex flex-col md:flex-row justify-between gap-4 mt-6 pt-4 border-t border-gray-100">
                    {/* Coupon */}
                    <div className="flex gap-2">
                      <input
                        type="text"
                        placeholder="Coupon code"
                        value={couponCode}
                        onChange={(e) => setCouponCode(e.target.value)}
                        disabled={couponApplied}
                        className="border border-gray-300 rounded-lg px-4 py-2 text-sm w-36 focus:outline-none focus:border-teal-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                      />
                      <button
                        onClick={applyCoupon}
                        disabled={couponApplied}
                        className="border border-teal-600 text-teal-600 px-4 py-2 rounded-lg text-sm hover:bg-teal-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {couponApplied ? (
                          <><i className="bi bi-check-circle me-1"></i>Applied</>
                        ) : 'Apply Coupon'}
                      </button>
                    </div>

                    {/* Clear / Continue */}
                    <div className="flex gap-2 flex-wrap">
                      <Link
                        to="/category"
                        className="border border-gray-300 text-gray-700 px-4 py-2 rounded-lg text-sm hover:bg-gray-50 transition flex items-center gap-1"
                      >
                        <i className="bi bi-arrow-left"></i> Continue Shopping
                      </Link>
                      <button
                        onClick={handleClear}
                        disabled={clearing}
                        className="border border-red-300 text-red-600 px-4 py-2 rounded-lg text-sm hover:bg-red-50 transition disabled:opacity-50 flex items-center gap-1"
                      >
                        {clearing ? (
                          <><i className="bi bi-arrow-clockwise animate-spin"></i> Clearing…</>
                        ) : (
                          <><i className="bi bi-trash"></i> Clear Cart</>
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ── Right Column: Order Summary ──────────────────────────── */}
            {!loading && items.length > 0 && (
              <div className="lg:w-1/3">
                <div className="bg-gray-50 rounded-xl p-6 shadow-sm sticky top-24">
                  <h4 className="text-xl font-bold text-gray-800 pb-4 border-b border-gray-200">
                    Order Summary
                  </h4>

                  <div className="space-y-3 mt-4">
                    {/* Subtotal */}
                    <div className="flex justify-between">
                      <span className="text-gray-600">
                        Subtotal ({cart.total_items} {cart.total_items === 1 ? 'item' : 'items'})
                      </span>
                      <span className="font-semibold">${subtotal.toFixed(2)}</span>
                    </div>

                    {/* Shipping Options */}
                    <div className="border-t border-gray-200 pt-3">
                      <p className="text-gray-600 mb-3 text-sm font-medium">Shipping Method</p>
                      <div className="space-y-2">
                        {SHIPPING_OPTIONS.map((opt) => {
                          const disabled = opt.id === 'free' && subtotal < (opt.minOrder ?? 0);
                          return (
                            <label
                              key={opt.id}
                              className={`flex items-center justify-between cursor-pointer p-2 rounded-lg transition ${shippingMethod === opt.id ? 'bg-teal-50 border border-teal-200' : 'hover:bg-gray-100'
                                } ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
                            >
                              <div className="flex items-center gap-2">
                                <input
                                  type="radio"
                                  name="shipping"
                                  value={opt.id}
                                  checked={shippingMethod === opt.id}
                                  onChange={() => !disabled && setShippingMethod(opt.id)}
                                  disabled={disabled}
                                  className="text-teal-600"
                                />
                                <div>
                                  <span className="text-sm font-medium">{opt.label}</span>
                                  <span className="text-xs text-gray-400 block">{opt.eta}</span>
                                  {opt.id === 'free' && disabled && (
                                    <span className="text-xs text-amber-600">
                                      (Requires ${(opt.minOrder ?? 0).toFixed(0)}+ order)
                                    </span>
                                  )}
                                </div>
                              </div>
                              <span className="text-sm font-semibold text-teal-700">
                                {opt.price === 0 && !disabled ? 'FREE' : `$${opt.price.toFixed(2)}`}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </div>

                    {/* Tax */}
                    <div className="flex justify-between border-t border-gray-200 pt-3">
                      <span className="text-gray-600">Tax (10%)</span>
                      <span className="font-medium">${tax.toFixed(2)}</span>
                    </div>

                    {/* Discount */}
                    {discount > 0 && (
                      <div className="flex justify-between text-teal-600">
                        <span className="flex items-center gap-1">
                          <i className="bi bi-tag-fill"></i> Coupon Discount
                        </span>
                        <span className="font-semibold">-${discount.toFixed(2)}</span>
                      </div>
                    )}

                    {/* Total */}
                    <div className="flex justify-between border-t-2 border-gray-200 pt-4 mt-2">
                      <span className="text-lg font-bold text-gray-800">Total</span>
                      <span className="text-xl font-bold text-teal-700">${total.toFixed(2)}</span>
                    </div>
                  </div>

                  {/* Checkout CTA */}
                  <Link
                    to="/checkout"
                    className="mt-6 w-full flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-700 text-white py-3 rounded-xl font-semibold transition"
                  >
                    Proceed to Checkout
                    <i className="bi bi-arrow-right"></i>
                  </Link>

                  {/* Trust badges */}
                  <div className="mt-4 grid grid-cols-3 gap-2 text-center text-gray-500">
                    <div className="text-xs">
                      <i className="bi bi-shield-check text-teal-500 block text-lg mb-1"></i>
                      Secure
                    </div>
                    <div className="text-xs">
                      <i className="bi bi-arrow-return-left text-teal-500 block text-lg mb-1"></i>
                      30-day returns
                    </div>
                    <div className="text-xs">
                      <i className="bi bi-truck text-teal-500 block text-lg mb-1"></i>
                      Fast delivery
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </>
  );
};

export default Cart;
