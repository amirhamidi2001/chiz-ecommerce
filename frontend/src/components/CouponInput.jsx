// src/components/CouponInput.jsx
import { useState } from 'react';

/**
 * Coupon entry / status box for the cart page.
 *
 * Presentational and prop-driven: the page owns the cart and the API calls
 * (via CartContext) and passes in what the cart says right now.
 *
 *   couponCode      cart.coupon_code     – code attached to the cart, or null
 *   couponDiscount  cart.coupon_discount – live discount for it ("0" if none)
 *   couponError     cart.coupon_error    – why an attached coupon no longer
 *                                          applies (expired, limit reached…)
 *   onApply(code)   → Promise<{ success, message? }>
 *   onRemove()      → Promise<{ success, message? }>
 *
 * Three states:
 *   1. no coupon attached     → code input + "Apply Coupon"
 *   2. valid coupon attached  → code, the discount, and "Remove"
 *   3. coupon attached but invalid now (couponError set) → the backend's
 *      reason, shown prominently, with "Remove" as the way out
 *
 * Rejection messages from the backend are shown verbatim — they are already
 * specific and customer-readable ("This coupon has expired.").
 */
const CouponInput = ({ couponCode, couponDiscount, couponError, onApply, onRemove }) => {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const handleApply = async (e) => {
    e.preventDefault();
    const trimmed = code.trim();
    if (!trimmed) {
      setMessage('Enter a coupon code.');
      return;
    }
    setBusy(true);
    setMessage('');
    const result = await onApply(trimmed);
    setBusy(false);
    if (result?.success) {
      setCode('');
    } else {
      // Keep what they typed so a typo can be corrected rather than retyped.
      setMessage(result?.message || 'Could not apply coupon. Please try again.');
    }
  };

  const handleRemove = async () => {
    setBusy(true);
    setMessage('');
    const result = await onRemove();
    setBusy(false);
    if (!result?.success) {
      setMessage(result?.message || 'Could not remove coupon. Please try again.');
    }
  };

  // ── 3. Attached but no longer valid ──────────────────────────────────────
  if (couponCode && couponError) {
    return (
      <div className="border border-amber-300 bg-amber-50 rounded-lg px-4 py-3 text-sm max-w-sm">
        <p className="font-semibold text-amber-800 flex items-center gap-1">
          <i className="bi bi-exclamation-triangle"></i>
          Coupon {couponCode} can&apos;t be applied
        </p>
        <p className="text-amber-700 mt-1">{couponError}</p>
        <p className="text-amber-700 mt-1">
          It isn&apos;t reducing your total. Remove it to continue.
        </p>
        <button
          type="button"
          onClick={handleRemove}
          disabled={busy}
          className="mt-2 border border-amber-400 text-amber-800 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-amber-100 transition disabled:opacity-50"
        >
          {busy ? 'Removing…' : 'Remove coupon'}
        </button>
        {message && (
          <p role="alert" className="text-red-600 text-xs mt-2">
            {message}
          </p>
        )}
      </div>
    );
  }

  // ── 2. Applied ───────────────────────────────────────────────────────────
  if (couponCode) {
    const saving = Number(couponDiscount) || 0;
    return (
      <div className="border border-teal-200 bg-teal-50 rounded-lg px-4 py-3 text-sm max-w-sm">
        <div className="flex items-center justify-between gap-3">
          <p className="text-teal-800 flex items-center gap-1">
            <i className="bi bi-check-circle-fill"></i>
            <span>
              <strong>{couponCode}</strong> applied
              {saving > 0 && <> — you save ${saving.toFixed(2)}</>}
            </span>
          </p>
          <button
            type="button"
            onClick={handleRemove}
            disabled={busy}
            // The cart page already has a "Remove" button on every item row;
            // a distinct accessible name keeps this one unambiguous.
            aria-label={busy ? 'Removing coupon' : `Remove coupon ${couponCode}`}
            className="text-xs font-medium text-red-600 hover:text-red-700 underline disabled:opacity-50"
          >
            {busy ? 'Removing…' : 'Remove'}
          </button>
        </div>
        {message && (
          <p role="alert" className="text-red-600 text-xs mt-2">
            {message}
          </p>
        )}
      </div>
    );
  }

  // ── 1. Entry form ────────────────────────────────────────────────────────
  return (
    <form onSubmit={handleApply} noValidate className="max-w-sm">
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Coupon code"
          aria-label="Coupon code"
          value={code}
          maxLength={32}
          onChange={(e) => {
            setCode(e.target.value);
            if (message) setMessage('');
          }}
          disabled={busy}
          className={`border rounded-lg px-4 py-2 text-sm w-36 focus:outline-none focus:border-teal-500 disabled:bg-gray-100 ${
            message ? 'border-red-400' : 'border-gray-300'
          }`}
        />
        <button
          type="submit"
          disabled={busy}
          className="border border-teal-600 text-teal-600 px-4 py-2 rounded-lg text-sm hover:bg-teal-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {busy ? 'Applying…' : 'Apply Coupon'}
        </button>
      </div>
      {message && (
        <p role="alert" className="text-red-600 text-xs mt-2">
          {message}
        </p>
      )}
    </form>
  );
};

export default CouponInput;
