// src/pages/CheckoutFailed.jsx
import { useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useCart } from '../context/CartContext';

// ─── Reason → message map ───────────────────────────────────────────────────
// Task 6.4.1.2: these must line up exactly with the ?reason= values
// PaymentCallbackView redirects with (backend/payments/views.py):
//   - "cancelled"            — gateway_status is its own NOK-equivalent
//                              (customer cancelled/abandoned before
//                              verification)
//   - "verification_failed"  — the gateway's verify call came back
//                              unsuccessful
//   - "already_failed"       — a duplicate callback hit an already-FAILED
//                              transaction (idempotency path)
//   - "unknown_transaction"  — no PaymentTransaction row matched the
//                              authority in the callback at all
// Anything not explicitly listed (including "already_failed") falls
// through to DEFAULT_MESSAGE, per this task's spec: only "cancelled" and
// "verification_failed" get their own specific message; everything else
// is a generic fallback.
const REASON_MESSAGES = {
  cancelled: 'You cancelled the payment. Your items are still in your cart.',
  verification_failed:
    'Your payment could not be confirmed. Please try again or contact support.',
};

const DEFAULT_MESSAGE = 'Something went wrong with your payment.';

const CheckoutFailed = () => {
  const [searchParams] = useSearchParams();
  const reason = searchParams.get('reason');
  const { cartCount, fetchCart } = useCart();

  const message = REASON_MESSAGES[reason] || DEFAULT_MESSAGE;

  // The browser arrives here via a REAL external redirect from the
  // gateway (a fresh page load), so CartProvider's own mount-time fetch
  // already runs — this extra call is defense-in-depth for freshness,
  // mirroring OrderConfirmation.jsx's same explicit refresh pattern.
  useEffect(() => {
    fetchCart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4 py-12">
      <div className="w-20 h-20 rounded-full bg-red-50 flex items-center justify-center mb-6">
        <i className="bi bi-x-lg text-4xl text-red-500"></i>
      </div>

      <h1 className="text-2xl md:text-3xl font-bold text-gray-800 mb-3">
        Payment Unsuccessful
      </h1>

      <p className="text-gray-600 max-w-md mb-2" data-testid="checkout-failed-message">
        {message}
      </p>

      {cartCount > 0 && (
        <p className="text-sm text-gray-500 mb-6">
          You have {cartCount} item{cartCount === 1 ? '' : 's'} waiting in your cart —
          nothing to re-add.
        </p>
      )}

      <div className="flex flex-col sm:flex-row gap-3 mt-4">
        <Link
          to="/checkout"
          className="bg-teal-600 text-white px-6 py-3 rounded-xl font-semibold hover:bg-teal-700 transition"
        >
          <i className="bi bi-arrow-repeat me-2"></i> Try Again
        </Link>
        <Link
          to="/cart"
          className="border border-gray-300 text-gray-700 px-6 py-3 rounded-xl hover:bg-gray-50 transition"
        >
          View Cart
        </Link>
      </div>

      <Link to="/support" className="text-sm text-teal-600 hover:underline mt-8">
        Need help? Contact support
      </Link>
    </div>
  );
};

export default CheckoutFailed;
