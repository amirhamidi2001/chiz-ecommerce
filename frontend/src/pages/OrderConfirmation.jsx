// src/pages/OrderConfirmation.jsx
import { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { getOrderDetail, isAuthenticated } from '../services/api';
import { useCart } from '../context/CartContext';

// ─── Status helpers ───────────────────────────────────────────────────────────
const STATUS_STEPS = ['pending', 'processing', 'shipped', 'delivered'];

const STATUS_META = {
  pending: { label: 'Pending', icon: 'bi-clock', color: 'text-amber-500' },
  processing: { label: 'Processing', icon: 'bi-gear', color: 'text-blue-500' },
  shipped: { label: 'Shipped', icon: 'bi-truck', color: 'text-indigo-500' },
  delivered: { label: 'Delivered', icon: 'bi-check-circle', color: 'text-teal-500' },
  cancelled: { label: 'Cancelled', icon: 'bi-x-circle', color: 'text-red-500' },
};

const getStepIndex = (status) => STATUS_STEPS.indexOf(status);

// ─── Sub-components ───────────────────────────────────────────────────────────
const Spinner = () => (
  <div className="flex justify-center items-center min-h-[60vh]">
    <div className="w-12 h-12 border-4 border-teal-600 border-t-transparent rounded-full animate-spin"></div>
  </div>
);

const CollapsibleCard = ({ icon, title, children }) => {
  const [open, setOpen] = useState(true);
  return (
    <div className="border border-gray-200 rounded-xl mb-5 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex justify-between items-center p-5 bg-gray-50 hover:bg-gray-100 transition"
      >
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <i className={`bi ${icon} text-teal-600`}></i>
          {title}
        </h3>
        <i className={`bi bi-chevron-${open ? 'up' : 'down'} text-gray-500`}></i>
      </button>
      {open && (
        <div className="p-5 border-t border-gray-100">
          {children}
        </div>
      )}
    </div>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────
const OrderConfirmation = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { fetchCart } = useCart();

  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Redirect unauthenticated users
  useEffect(() => {
    if (!isAuthenticated()) {
      navigate('/login');
    }
  }, []);

  // Fetch order + refresh cart count (cart was cleared after checkout)
  useEffect(() => {
    if (!id) {
      navigate('/');
      return;
    }

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const { data } = await getOrderDetail(id);
        setOrder(data);
        // Refresh cart badge (cart was cleared when order was placed)
        fetchCart();
      } catch (err) {
        if (err.response?.status === 404) {
          setError('Order not found.');
        } else {
          setError('Failed to load order details. Please try again.');
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  if (loading) return <Spinner />;

  if (error) return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <i className="bi bi-exclamation-triangle text-6xl text-red-400 mb-4"></i>
      <h2 className="text-2xl font-bold text-gray-700 mb-3">{error}</h2>
      <div className="flex gap-3">
        <button onClick={() => navigate(-1)} className="border border-gray-300 px-5 py-2 rounded-lg hover:bg-gray-50">
          Go Back
        </button>
        <Link to="/account" className="bg-teal-600 text-white px-5 py-2 rounded-lg hover:bg-teal-700">
          My Orders
        </Link>
      </div>
    </div>
  );

  if (!order) return null;

  // Derived values
  const currentStep = getStepIndex(order.status);
  const isCancelled = order.status === 'cancelled';
  const statusMeta = STATUS_META[order.status] || STATUS_META.processing;

  const orderDate = new Date(order.created_at).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });

  // Estimated delivery: 5-7 business days from order date
  const deliveryBase = new Date(order.created_at);
  deliveryBase.setDate(deliveryBase.getDate() + 5);
  const deliveryEnd = new Date(order.created_at);
  deliveryEnd.setDate(deliveryEnd.getDate() + 7);
  const estimatedDelivery = `${deliveryBase.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })} – ${deliveryEnd.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`;

  return (
    <>
      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Order Confirmation</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Order #{order.order_number}</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Main Section */}
      <section className="py-12 bg-white">
        <div className="container mx-auto px-4">
          <div className="flex flex-col lg:flex-row rounded-xl overflow-hidden shadow-lg border border-gray-100">

            {/* ── Sidebar ────────────────────────────────────────────────── */}
            <div className="lg:w-1/3 bg-gradient-to-br from-teal-800 to-teal-900 text-white p-6 md:p-8">

              {/* Success / cancelled icon */}
              <div className="flex justify-center mb-6">
                <div className={`w-20 h-20 rounded-full flex items-center justify-center relative ${isCancelled ? 'bg-red-500/20' : 'bg-white/20'}`}>
                  {!isCancelled && (
                    <div className="absolute w-24 h-24 rounded-full bg-white/10 animate-ping"></div>
                  )}
                  <i className={`bi ${isCancelled ? 'bi-x-lg' : 'bi-check-lg'} text-4xl text-white`}></i>
                </div>
              </div>

              {/* Order ID & Date */}
              <div className="text-center mb-8 pb-6 border-b border-white/20">
                <h4 className="text-xl font-bold">#{order.order_number}</h4>
                <div className="text-white/70 text-sm mt-1">{orderDate}</div>
                <div className={`mt-2 inline-flex items-center gap-2 text-sm font-semibold ${statusMeta.color} bg-white/10 px-3 py-1 rounded-full`}>
                  <i className={`bi ${statusMeta.icon}`}></i>
                  {statusMeta.label}
                </div>
              </div>

              {/* Order Progress Stepper (hidden if cancelled) */}
              {!isCancelled && (
                <div className="mb-8">
                  <h5 className="text-base font-semibold mb-4">Order Progress</h5>
                  <div className="space-y-4">
                    {STATUS_STEPS.map((step, idx) => {
                      const done = idx <= currentStep;
                      const current = idx === currentStep;
                      return (
                        <div key={step} className="flex items-center gap-3">
                          <div
                            className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold flex-shrink-0 ${done
                                ? current
                                  ? 'bg-white text-teal-800 ring-4 ring-white/30'
                                  : 'bg-teal-500 text-white'
                                : 'bg-white/20 text-white/50'
                              }`}
                          >
                            {done && !current
                              ? <i className="bi bi-check-lg text-xs"></i>
                              : idx + 1
                            }
                          </div>
                          <div className={`flex-1 text-sm ${current ? 'font-semibold' : done ? 'text-white/80' : 'text-white/40'}`}>
                            {STATUS_META[step]?.label || step}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Financial Summary */}
              <div className="mb-8">
                <h5 className="text-base font-semibold mb-3">Order Summary</h5>
                <ul className="space-y-2 text-sm">
                  <li className="flex justify-between">
                    <span className="text-white/70">Subtotal</span>
                    <span>${Number(order.subtotal).toFixed(2)}</span>
                  </li>
                  <li className="flex justify-between">
                    <span className="text-white/70">Shipping</span>
                    <span>${Number(order.shipping_cost).toFixed(2)}</span>
                  </li>
                  <li className="flex justify-between">
                    <span className="text-white/70">Tax</span>
                    <span>${Number(order.tax).toFixed(2)}</span>
                  </li>
                  {Number(order.discount) > 0 && (
                    <li className="flex justify-between text-teal-300">
                      <span>Discount</span>
                      <span>-${Number(order.discount).toFixed(2)}</span>
                    </li>
                  )}
                  <li className="flex justify-between text-lg font-bold pt-2 border-t border-white/20 mt-2">
                    <span>Total</span>
                    <span>${Number(order.total).toFixed(2)}</span>
                  </li>
                </ul>
              </div>

              {/* Delivery Info */}
              {!isCancelled && (
                <div className="mb-8">
                  <h5 className="text-base font-semibold mb-3">Delivery Information</h5>
                  <div className="space-y-2 text-sm text-white/80">
                    <p className="flex items-center gap-2">
                      <i className="bi bi-calendar-check flex-shrink-0"></i>
                      Estimated: {estimatedDelivery}
                    </p>
                    <p className="flex items-center gap-2">
                      <i className="bi bi-truck flex-shrink-0"></i>
                      Standard Shipping
                    </p>
                  </div>
                </div>
              )}

              {/* Help Links */}
              <div>
                <h5 className="text-base font-semibold mb-3">Need Help?</h5>
                <div className="space-y-2 text-sm">
                  <Link to="/contact" className="flex items-center gap-2 text-white/70 hover:text-white transition">
                    <i className="bi bi-chat-dots"></i> Contact Support
                  </Link>
                  <Link to="/faq" className="flex items-center gap-2 text-white/70 hover:text-white transition">
                    <i className="bi bi-question-circle"></i> FAQs
                  </Link>
                </div>
              </div>
            </div>

            {/* ── Main Content ────────────────────────────────────────────── */}
            <div className="lg:w-2/3 p-6 md:p-8 bg-white">

              {/* Thank You / Cancelled header */}
              <div className="mb-8">
                {isCancelled ? (
                  <>
                    <h1 className="text-2xl md:text-3xl font-bold text-red-600">Order Cancelled</h1>
                    <p className="text-gray-600 mt-2">
                      Your order has been cancelled. If you were charged, a refund will be processed within 5–7 business days.
                    </p>
                  </>
                ) : (
                  <>
                    <h1 className="text-2xl md:text-3xl font-bold text-gray-800">
                      Thanks for your order, {order.first_name}!
                    </h1>
                    <p className="text-gray-600 mt-2">
                      We've received your order and will begin processing it right away.
                      Confirmation details will be sent to <strong>{order.email}</strong>.
                    </p>
                  </>
                )}
              </div>

              {/* Shipping Details */}
              <CollapsibleCard icon="bi-geo-alt" title="Shipping Details">
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Ship To</p>
                    <address className="not-italic text-gray-700 text-sm leading-relaxed">
                      <strong>{order.full_name}</strong><br />
                      {order.shipping_address}
                      {order.shipping_apartment && <>, {order.shipping_apartment}</>}<br />
                      {order.shipping_city}, {order.shipping_state} {order.shipping_zip}<br />
                      {order.shipping_country}
                    </address>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Contact</p>
                    <div className="space-y-1 text-sm text-gray-700">
                      <p><i className="bi bi-envelope me-2 text-gray-400"></i>{order.email}</p>
                      <p><i className="bi bi-telephone me-2 text-gray-400"></i>{order.phone}</p>
                    </div>
                    {order.notes && (
                      <div className="mt-4">
                        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Notes</p>
                        <p className="text-sm text-gray-600 italic">{order.notes}</p>
                      </div>
                    )}
                  </div>
                </div>
              </CollapsibleCard>

              {/* Payment Details */}
              <CollapsibleCard icon="bi-credit-card" title="Payment Details">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-teal-100 rounded-lg flex items-center justify-center flex-shrink-0">
                    <i className={`bi ${order.payment_method === 'paypal' ? 'bi-paypal' :
                        order.payment_method === 'apple_pay' ? 'bi-apple' :
                          'bi-credit-card-2-front'
                      } text-teal-600 text-2xl`}></i>
                  </div>
                  <div>
                    <div className="font-semibold">{order.payment_display}</div>
                    {order.card_last_four && (
                      <div className="text-gray-500 text-sm">
                        •••• •••• •••• {order.card_last_four}
                      </div>
                    )}
                  </div>
                </div>
                <div className="mt-4 pt-3 border-t border-gray-100">
                  <p className="text-sm text-gray-500">
                    Billing address:{' '}
                    {order.billing_same_as_shipping
                      ? 'Same as shipping address'
                      : 'Separate billing address on file'}
                  </p>
                </div>
              </CollapsibleCard>

              {/* Order Items */}
              <CollapsibleCard icon="bi-bag-check" title={`Order Items (${order.items.length})`}>
                <div className="space-y-5">
                  {order.items.map((item) => (
                    <div key={item.id} className="flex gap-4 pb-4 border-b border-gray-100 last:border-0 last:pb-0">
                      <div className="w-20 h-20 rounded-lg border bg-gray-100 flex-shrink-0 overflow-hidden">
                        {item.product_image ? (
                          <img
                            src={item.product_image}
                            alt={item.product_name}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-300">
                            <i className="bi bi-image text-2xl"></i>
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="font-semibold line-clamp-2">
                          {item.product_slug ? (
                            <Link
                              to={`/product/${item.product_slug}`}
                              className="hover:text-teal-600 transition"
                            >
                              {item.product_name}
                            </Link>
                          ) : item.product_name}
                        </h4>
                        <div className="flex justify-between items-center mt-2">
                          <span className="text-sm text-gray-500">
                            {item.quantity} × ${Number(item.unit_price).toFixed(2)}
                          </span>
                          <span className="font-semibold text-gray-800">
                            ${Number(item.subtotal).toFixed(2)}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CollapsibleCard>

              {/* Action Buttons */}
              <div className="grid md:grid-cols-2 gap-4 mb-10">
                <Link
                  to="/category"
                  className="flex items-center justify-center gap-2 border border-gray-300 text-gray-700 py-3 rounded-xl hover:bg-gray-50 transition"
                >
                  <i className="bi bi-arrow-left"></i> Return to Shop
                </Link>
                <Link
                  to="/account?tab=orders"
                  className="flex items-center justify-center gap-2 bg-teal-600 text-white py-3 rounded-xl hover:bg-teal-700 transition"
                >
                  View All Orders <i className="bi bi-arrow-right"></i>
                </Link>
              </div>

              {/* Recommended — static suggestions since we don't have a "related to order" API */}
              <div>
                <h3 className="text-xl font-bold text-gray-800 mb-5 pb-2 border-b border-gray-100">
                  Continue Shopping
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <Link
                    to="/category"
                    className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-center hover:shadow-md hover:border-teal-300 transition group"
                  >
                    <i className="bi bi-grid text-3xl text-teal-600 block mb-2 group-hover:scale-110 transition"></i>
                    <span className="font-medium text-gray-700">Browse All Products</span>
                  </Link>
                  <Link
                    to="/account?tab=orders"
                    className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-center hover:shadow-md hover:border-teal-300 transition group"
                  >
                    <i className="bi bi-bag-heart text-3xl text-teal-600 block mb-2 group-hover:scale-110 transition"></i>
                    <span className="font-medium text-gray-700">Track My Orders</span>
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default OrderConfirmation;
