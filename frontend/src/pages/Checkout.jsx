// src/pages/Checkout.jsx
import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { createOrder, isAuthenticated } from '../services/api';

const TAX_RATE = 0.10;
const SHIPPING_COST = 9.99;

// ─── Helpers ─────────────────────────────────────────────────────────────────
const formatCardNumber = (raw) =>
  raw.replace(/(\d{4})/g, '$1 ').trim();

// ─── Field component ──────────────────────────────────────────────────────────
const Field = ({ label, required, error, children }) => (
  <div>
    <label className="block text-sm font-medium mb-1">
      {label} {required && <span className="text-red-500">*</span>}
    </label>
    {children}
    {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
  </div>
);

const inputCls = (err) =>
  `w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500 ${err ? 'border-red-400 bg-red-50' : 'border-gray-300'
  }`;

// ─── Step header ─────────────────────────────────────────────────────────────
const StepHeader = ({ num, title }) => (
  <div className="flex items-center gap-3 p-5 bg-gray-50 border-b">
    <div className="w-8 h-8 bg-teal-600 text-white rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">
      {num}
    </div>
    <h3 className="text-lg font-semibold">{title}</h3>
  </div>
);

// ─── Main component ───────────────────────────────────────────────────────────
const Checkout = () => {
  const navigate = useNavigate();
  const { cart, loading: cartLoading, fetchCart } = useCart();

  // ── Redirect unauthenticated users ────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated()) {
      navigate('/login?redirect=/checkout');
    }
  }, []);

  // ── Reload cart on mount ───────────────────────────────────────────────────
  useEffect(() => {
    fetchCart();
  }, []);

  // ── Form state ─────────────────────────────────────────────────────────────
  const [form, setForm] = useState({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    address: '',
    apartment: '',
    city: '',
    state: '',
    zip: '',
    country: 'US',
    billingSame: true,
    saveAddress: false,
    terms: false,
    notes: '',
  });

  const [paymentMethod, setPaymentMethod] = useState('credit_card');
  const [card, setCard] = useState({ number: '', expiry: '', cvv: '', name: '' });

  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState('');

  // ── Derived totals ─────────────────────────────────────────────────────────
  // NOTE: there is no coupon/promo system yet (tracked as Epic 9). Discount
  // is always $0 and is not client-controlled — the server hardcodes it too.
  const subtotal = Number(cart?.subtotal ?? 0);
  const tax = subtotal * TAX_RATE;
  const total = subtotal + SHIPPING_COST + tax;
  const items = cart?.items ?? [];

  // ── Input handlers ──────────────────────────────────────────────────────────
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const handleCardChange = (e) => {
    const { name, value } = e.target;
    setCard((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const handleCardNumberChange = (e) => {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 16);
    setCard((prev) => ({ ...prev, number: raw }));
    if (errors.cardNumber) setErrors((prev) => ({ ...prev, cardNumber: '' }));
  };

  const handleExpiryChange = (e) => {
    let v = e.target.value.replace(/\D/g, '');
    if (v.length >= 3) v = v.slice(0, 2) + '/' + v.slice(2, 4);
    setCard((prev) => ({ ...prev, expiry: v }));
  };

  // ── Validation ──────────────────────────────────────────────────────────────
  const validate = () => {
    const e = {};
    if (!form.firstName.trim()) e.firstName = 'Required';
    if (!form.lastName.trim()) e.lastName = 'Required';
    if (!form.email.trim()) e.email = 'Required';
    if (!form.phone.trim()) e.phone = 'Required';
    if (!form.address.trim()) e.address = 'Required';
    if (!form.city.trim()) e.city = 'Required';
    if (!form.state.trim()) e.state = 'Required';
    if (!form.zip.trim()) e.zip = 'Required';
    if (!form.country) e.country = 'Required';
    if (!form.terms) e.terms = 'You must agree to the Terms and Conditions.';

    if (paymentMethod === 'credit_card') {
      if (card.number.length < 16) e.cardNumber = 'Enter a valid 16-digit card number.';
      if (!card.expiry.match(/^\d{2}\/\d{2}$/)) e.expiry = 'Use MM/YY format.';
      if (card.cvv.length < 3) e.cvv = 'Enter a valid CVV.';
      if (!card.name.trim()) e.cardName = 'Required';
    }

    return e;
  };

  // ── Submit ──────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');

    const validationErrors = validate();
    if (Object.keys(validationErrors).length) {
      setErrors(validationErrors);
      // Scroll to first error
      const firstField = document.querySelector('[data-error="true"]');
      firstField?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    if (items.length === 0) {
      setServerError('Your cart is empty. Add items before checking out.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        first_name: form.firstName,
        last_name: form.lastName,
        email: form.email,
        phone: form.phone,
        address: form.address,
        apartment: form.apartment,
        city: form.city,
        state: form.state,
        zip: form.zip,
        country: form.country,
        billing_same: form.billingSame,
        payment_method: paymentMethod,
        card_last_four: paymentMethod === 'credit_card' ? card.number.slice(-4) : '',
        notes: form.notes,
      };

      const { data } = await createOrder(payload);
      navigate(`/order-confirmation/${data.id}`);
    } catch (err) {
      const data = err.response?.data;
      if (data && typeof data === 'object') {
        // Map server field errors back to form
        const mapped = {};
        Object.entries(data).forEach(([key, val]) => {
          mapped[key] = Array.isArray(val) ? val[0] : String(val);
        });
        if (mapped.cart) {
          setServerError(mapped.cart);
        } else {
          setErrors(mapped);
        }
      } else {
        setServerError('Something went wrong. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  // ── Empty cart redirect ─────────────────────────────────────────────────────
  if (!cartLoading && items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <i className="bi bi-cart-x text-6xl text-gray-300 mb-4"></i>
        <h2 className="text-2xl font-bold text-gray-700 mb-2">Your cart is empty</h2>
        <p className="text-gray-500 mb-6">Add items to your cart before checking out.</p>
        <Link to="/category" className="bg-teal-600 text-white px-6 py-3 rounded-xl hover:bg-teal-700 transition">
          Continue Shopping
        </Link>
      </div>
    );
  }

  return (
    <>
      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Checkout</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li><Link to="/cart" className="text-teal-700 hover:underline">Cart</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Checkout</li>
            </ol>
          </nav>
        </div>
      </div>

      <section className="py-12 bg-white">
        <div className="container mx-auto px-4">
          {/* Server error banner */}
          {serverError && (
            <div className="mb-6 flex items-center gap-3 bg-red-50 border border-red-200 text-red-700 px-5 py-4 rounded-xl">
              <i className="bi bi-exclamation-triangle"></i>
              <span>{serverError}</span>
            </div>
          )}

          <div className="flex flex-col lg:flex-row gap-8">

            {/* ── Checkout Form ─────────────────────────────────────────── */}
            <div className="lg:w-7/12">
              <form onSubmit={handleSubmit} noValidate>

                {/* 1 — Customer Information */}
                <div className="bg-white border border-gray-100 rounded-xl shadow-sm mb-6 overflow-hidden">
                  <StepHeader num="1" title="Customer Information" />
                  <div className="p-6 space-y-4">
                    <div className="grid md:grid-cols-2 gap-4">
                      <Field label="First Name" required error={errors.firstName}>
                        <input
                          type="text" name="firstName" value={form.firstName}
                          onChange={handleChange} className={inputCls(errors.firstName)}
                          data-error={!!errors.firstName} required
                        />
                      </Field>
                      <Field label="Last Name" required error={errors.lastName}>
                        <input
                          type="text" name="lastName" value={form.lastName}
                          onChange={handleChange} className={inputCls(errors.lastName)}
                          data-error={!!errors.lastName} required
                        />
                      </Field>
                    </div>
                    <Field label="Email Address" required error={errors.email}>
                      <input
                        type="email" name="email" value={form.email}
                        onChange={handleChange} className={inputCls(errors.email)}
                        data-error={!!errors.email} required
                      />
                    </Field>
                    <Field label="Phone Number" required error={errors.phone}>
                      <input
                        type="tel" name="phone" value={form.phone}
                        onChange={handleChange} className={inputCls(errors.phone)}
                        data-error={!!errors.phone} required
                      />
                    </Field>
                  </div>
                </div>

                {/* 2 — Shipping Address */}
                <div className="bg-white border border-gray-100 rounded-xl shadow-sm mb-6 overflow-hidden">
                  <StepHeader num="2" title="Shipping Address" />
                  <div className="p-6 space-y-4">
                    <Field label="Street Address" required error={errors.address}>
                      <input
                        type="text" name="address" value={form.address}
                        onChange={handleChange} className={inputCls(errors.address)}
                        data-error={!!errors.address} required
                      />
                    </Field>
                    <Field label="Apartment, Suite, etc." error={errors.apartment}>
                      <input
                        type="text" name="apartment" value={form.apartment}
                        onChange={handleChange} className={inputCls(false)}
                      />
                    </Field>
                    <div className="grid md:grid-cols-3 gap-4">
                      <Field label="City" required error={errors.city}>
                        <input
                          type="text" name="city" value={form.city}
                          onChange={handleChange} className={inputCls(errors.city)}
                          data-error={!!errors.city} required
                        />
                      </Field>
                      <Field label="State" required error={errors.state}>
                        <input
                          type="text" name="state" value={form.state}
                          onChange={handleChange} className={inputCls(errors.state)}
                          data-error={!!errors.state} required
                        />
                      </Field>
                      <Field label="ZIP Code" required error={errors.zip}>
                        <input
                          type="text" name="zip" value={form.zip}
                          onChange={handleChange} className={inputCls(errors.zip)}
                          data-error={!!errors.zip} required
                        />
                      </Field>
                    </div>
                    <Field label="Country" required error={errors.country}>
                      <select
                        name="country" value={form.country}
                        onChange={handleChange} className={inputCls(errors.country)} required
                      >
                        <option value="">Select Country</option>
                        <option value="US">United States</option>
                        <option value="CA">Canada</option>
                        <option value="GB">United Kingdom</option>
                        <option value="AU">Australia</option>
                        <option value="DE">Germany</option>
                        <option value="FR">France</option>
                      </select>
                    </Field>
                    <div className="space-y-2 pt-1">
                      <label className="flex items-center gap-2 cursor-pointer select-none">
                        <input
                          type="checkbox" name="saveAddress"
                          checked={form.saveAddress} onChange={handleChange}
                          className="rounded text-teal-600"
                        />
                        <span className="text-sm">Save this address for future orders</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer select-none">
                        <input
                          type="checkbox" name="billingSame"
                          checked={form.billingSame} onChange={handleChange}
                          className="rounded text-teal-600"
                        />
                        <span className="text-sm">Billing address same as shipping</span>
                      </label>
                    </div>
                  </div>
                </div>

                {/* 3 — Payment Method */}
                <div className="bg-white border border-gray-100 rounded-xl shadow-sm mb-6 overflow-hidden">
                  <StepHeader num="3" title="Payment Method" />
                  <div className="p-6">
                    {/* Method Selector */}
                    <div className="flex flex-wrap gap-4 mb-6">
                      {[
                        { id: 'credit_card', icon: 'bi-credit-card-2-front', label: 'Credit / Debit Card' },
                        { id: 'paypal', icon: 'bi-paypal', label: 'PayPal' },
                        { id: 'apple_pay', icon: 'bi-apple', label: 'Apple Pay' },
                      ].map((m) => (
                        <label
                          key={m.id}
                          className={`flex-1 min-w-[120px] border rounded-xl p-3 text-center cursor-pointer transition ${paymentMethod === m.id
                              ? 'border-teal-600 bg-teal-50'
                              : 'border-gray-200 hover:border-gray-300'
                            }`}
                        >
                          <input
                            type="radio" name="paymentMethod" value={m.id}
                            checked={paymentMethod === m.id}
                            onChange={() => setPaymentMethod(m.id)}
                            className="hidden"
                          />
                          <i className={`bi ${m.icon} text-2xl block mb-1`}></i>
                          <span className="text-sm">{m.label}</span>
                        </label>
                      ))}
                    </div>

                    {/* Credit card fields */}
                    {paymentMethod === 'credit_card' && (
                      <div className="space-y-4">
                        <Field label="Card Number" required error={errors.cardNumber}>
                          <div className="relative">
                            <input
                              type="text"
                              value={formatCardNumber(card.number)}
                              onChange={handleCardNumberChange}
                              className={`${inputCls(errors.cardNumber)} pr-16`}
                              placeholder="1234 5678 9012 3456"
                              data-error={!!errors.cardNumber}
                            />
                            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex gap-1 text-gray-400">
                              <i className="bi bi-credit-card-2-front"></i>
                            </div>
                          </div>
                        </Field>
                        <div className="grid md:grid-cols-2 gap-4">
                          <Field label="Expiration Date" required error={errors.expiry}>
                            <input
                              type="text" value={card.expiry}
                              onChange={handleExpiryChange}
                              className={inputCls(errors.expiry)}
                              placeholder="MM/YY"
                              data-error={!!errors.expiry}
                            />
                          </Field>
                          <Field label="Security Code (CVV)" required error={errors.cvv}>
                            <div className="relative">
                              <input
                                type="text" name="cvv" value={card.cvv}
                                onChange={handleCardChange}
                                className={`${inputCls(errors.cvv)} pr-10`}
                                placeholder="123"
                                maxLength={4}
                                data-error={!!errors.cvv}
                              />
                              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" title="3-digit code on the back of your card">
                                <i className="bi bi-question-circle"></i>
                              </span>
                            </div>
                          </Field>
                        </div>
                        <Field label="Name on Card" required error={errors.cardName}>
                          <input
                            type="text" name="name" value={card.name}
                            onChange={handleCardChange}
                            className={inputCls(errors.cardName)}
                            data-error={!!errors.cardName}
                          />
                        </Field>
                      </div>
                    )}

                    {paymentMethod === 'paypal' && (
                      <div className="bg-blue-50 border border-blue-200 text-blue-700 p-4 rounded-lg text-sm">
                        <i className="bi bi-info-circle me-2"></i>
                        You will be redirected to PayPal to complete your purchase securely.
                      </div>
                    )}
                    {paymentMethod === 'apple_pay' && (
                      <div className="bg-gray-50 border border-gray-200 text-gray-600 p-4 rounded-lg text-sm">
                        <i className="bi bi-apple me-2"></i>
                        You will be prompted to authorize payment with Apple Pay.
                      </div>
                    )}
                  </div>
                </div>

                {/* 4 — Review & Place Order */}
                <div className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-hidden">
                  <StepHeader num="4" title="Review & Place Order" />
                  <div className="p-6">
                    <Field label="" error={errors.terms}>
                      <label className="flex items-start gap-2 cursor-pointer select-none" data-error={!!errors.terms}>
                        <input
                          type="checkbox" name="terms" checked={form.terms}
                          onChange={handleChange}
                          className={`mt-1 rounded text-teal-600 ${errors.terms ? 'ring-2 ring-red-400' : ''}`}
                        />
                        <span className="text-sm">
                          I agree to the{' '}
                          <button type="button" onClick={() => document.getElementById('termsModal')?.showModal()}
                            className="text-teal-600 hover:underline">
                            Terms and Conditions
                          </button>{' '}
                          and{' '}
                          <button type="button" onClick={() => document.getElementById('privacyModal')?.showModal()}
                            className="text-teal-600 hover:underline">
                            Privacy Policy
                          </button>
                        </span>
                      </label>
                    </Field>

                    <button
                      type="submit"
                      disabled={submitting || cartLoading}
                      className="mt-6 w-full bg-teal-600 text-white py-3.5 rounded-xl font-semibold hover:bg-teal-700 transition flex justify-between items-center px-6 disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      <span className="flex items-center gap-2">
                        {submitting ? (
                          <><i className="bi bi-arrow-clockwise animate-spin"></i> Placing Order…</>
                        ) : (
                          <><i className="bi bi-bag-check"></i> Place Order</>
                        )}
                      </span>
                      <span className="bg-white/20 px-3 py-1 rounded-lg text-sm font-bold">
                        ${total.toFixed(2)}
                      </span>
                    </button>
                  </div>
                </div>

              </form>
            </div>

            {/* ── Order Summary ──────────────────────────────────────────── */}
            <div className="lg:w-5/12">
              <div className="bg-gray-50 rounded-xl p-6 sticky top-24">
                <div className="flex justify-between items-center border-b pb-4 mb-5">
                  <h3 className="text-xl font-bold">Order Summary</h3>
                  <span className="text-sm text-gray-500">
                    {cartLoading ? '…' : `${cart?.total_items ?? 0} items`}
                  </span>
                </div>

                {/* Items */}
                {cartLoading ? (
                  <div className="space-y-4 mb-6">
                    {[...Array(2)].map((_, i) => (
                      <div key={i} className="flex gap-3 animate-pulse">
                        <div className="w-16 h-16 bg-gray-200 rounded-lg flex-shrink-0" />
                        <div className="flex-1 space-y-2">
                          <div className="h-4 bg-gray-200 rounded w-3/4" />
                          <div className="h-3 bg-gray-200 rounded w-1/2" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-4 mb-6 max-h-64 overflow-y-auto pr-1">
                    {items.map((item) => (
                      <div key={item.id} className="flex gap-3">
                        <div className="w-16 h-16 rounded-lg border bg-gray-100 flex-shrink-0 overflow-hidden">
                          {item.product.image ? (
                            <img
                              src={item.product.image}
                              alt={item.product.name}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-gray-300">
                              <i className="bi bi-image text-xl"></i>
                            </div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-medium text-sm line-clamp-2">{item.product.name}</h4>
                          <div className="flex justify-between mt-1">
                            <span className="text-xs text-gray-500">
                              {item.quantity} × ${Number(item.unit_price).toFixed(2)}
                            </span>
                            <span className="text-sm font-semibold">
                              ${Number(item.subtotal).toFixed(2)}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Promo code / coupons are not implemented yet (Epic 9) —
                    intentionally removed rather than left as non-functional
                    UI. Do not re-add a promo input here without a real,
                    server-validated coupon system behind it. */}

                {/* Totals */}
                <div className="space-y-2 text-sm border-t pt-4">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Subtotal</span>
                    <span>${subtotal.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Shipping</span>
                    <span>${SHIPPING_COST.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Tax (10%)</span>
                    <span>${tax.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-base font-bold pt-3 border-t mt-2">
                    <span>Total</span>
                    <span className="text-teal-700">${total.toFixed(2)}</span>
                  </div>
                </div>

                {/* Trust badges */}
                <div className="mt-6 text-center">
                  <div className="flex items-center justify-center gap-2 text-sm text-gray-500 mb-3">
                    <i className="bi bi-shield-lock text-teal-600"></i>
                    <span>Secure Checkout — SSL Encrypted</span>
                  </div>
                  <div className="flex justify-center gap-3 text-2xl text-gray-400">
                    <i className="bi bi-credit-card-2-front"></i>
                    <i className="bi bi-credit-card"></i>
                    <i className="bi bi-paypal"></i>
                    <i className="bi bi-apple"></i>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Terms & Privacy Modals ─────────────────────────────────────────── */}
      <dialog id="termsModal" className="rounded-xl shadow-2xl p-0 backdrop:bg-black/50">
        <div className="max-w-md w-[90vw] p-6">
          <h2 className="text-xl font-bold mb-4">Terms and Conditions</h2>
          <div className="text-sm text-gray-600 space-y-2 max-h-72 overflow-y-auto">
            <p>By placing an order you agree to our standard terms of service. All sales are subject to availability. Prices and availability are subject to change without notice.</p>
            <p>We reserve the right to cancel orders that appear fraudulent. Returns are accepted within 30 days of delivery in original condition.</p>
          </div>
          <div className="mt-6 flex justify-end">
            <button
              onClick={() => document.getElementById('termsModal').close()}
              className="bg-teal-600 text-white px-4 py-2 rounded-lg hover:bg-teal-700"
            >
              I Understand
            </button>
          </div>
        </div>
      </dialog>

      <dialog id="privacyModal" className="rounded-xl shadow-2xl p-0 backdrop:bg-black/50">
        <div className="max-w-md w-[90vw] p-6">
          <h2 className="text-xl font-bold mb-4">Privacy Policy</h2>
          <div className="text-sm text-gray-600 space-y-2 max-h-72 overflow-y-auto">
            <p>We collect personal information only as needed to process and fulfill your order. Your data is never sold to third parties.</p>
            <p>Payment card details are not stored on our servers. We use industry-standard encryption to protect your information.</p>
          </div>
          <div className="mt-6 flex justify-end">
            <button
              onClick={() => document.getElementById('privacyModal').close()}
              className="bg-teal-600 text-white px-4 py-2 rounded-lg hover:bg-teal-700"
            >
              I Understand
            </button>
          </div>
        </div>
      </dialog>
    </>
  );
};

export default Checkout;
