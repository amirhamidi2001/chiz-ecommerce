// src/components/PaymentMethodsTab.jsx
//
// Task: repurposed into the customer's PAYMENT HISTORY (the file/tab key keep their
// old names so Account.jsx's `payments` slot and ?tab=payments links still work).
//
// WHY: this tab used to derive "payment methods on file" from historical
// order.payment_method strings. Since Epic 6 checkout goes through Iranian gateways
// (ZarinPal / Zibal / IDPay) and the platform stores no payment methods at all, so
// that summary described something that does not exist. What a customer genuinely
// lacks is a record of HOW each order was paid: this lists their real
// PaymentTransaction rows (gateway, amount, status, date) from
// GET /dashboard/customer/payment-history/, which the server scopes to request.user.
import { useEffect, useState } from "react";
import { dashboardAPI } from "../services/api";
import { formatToman } from "../utils/money";
import { formatJalaliDate, JALALI_DATETIME_FORMAT } from "../utils/jalaliDate";

const PAGE_SIZE = 10;

const STATUS_STYLES = {
  success: "bg-teal-100 text-teal-700",
  pending: "bg-yellow-100 text-yellow-700",
  failed: "bg-red-100 text-red-700",
};

const fmt = (n) => formatToman(n);

const PaymentMethodsTab = () => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // State is only set in the promise callbacks below; the "loading" and "error"
  // resets happen in the event handlers that trigger a refetch (goToPage / retry).
  useEffect(() => {
    let ignore = false;
    dashboardAPI
      .getPaymentHistory({ page, page_size: PAGE_SIZE })
      .then(({ data }) => {
        if (ignore) return;
        setTransactions(data.results ?? data);
        setTotalPages(data.count ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1);
      })
      // An empty list means "no payments"; a failed request must not look like that.
      .catch(() => { if (!ignore) setError(true); })
      .finally(() => { if (!ignore) setLoading(false); });
    return () => { ignore = true; };
  }, [page, reloadKey]);

  const goToPage = (next) => {
    setLoading(true);
    setPage(next);
  };

  const retry = () => {
    setError(false);
    setLoading(true);
    setReloadKey((k) => k + 1);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Payment History</h2>
      </div>

      <div className="bg-blue-50 border border-blue-100 text-blue-700 rounded-xl p-4 mb-6 flex items-start gap-3 text-sm">
        <i className="bi bi-info-circle text-lg flex-shrink-0"></i>
        <p>
          Every payment attempt for your orders, as processed by our payment gateways.
          We don&apos;t store card details.
        </p>
      </div>

      {loading ? (
        <div className="space-y-3" data-testid="payment-history-loading">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-14 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : error ? (
        <div role="alert" className="text-center py-12 text-red-600">
          <p className="font-medium">Could not load your payment history.</p>
          <button
            type="button"
            onClick={retry}
            className="mt-3 text-sm text-teal-600 hover:underline font-medium"
          >
            Try again
          </button>
        </div>
      ) : transactions.length === 0 ? (
        <div className="text-center py-16 text-gray-400" data-testid="payment-history-empty">
          <i className="bi bi-receipt text-5xl mb-4 block"></i>
          <p className="text-lg font-medium">No payment history</p>
          <p className="text-sm mt-1">Payments for your orders will appear here.</p>
        </div>
      ) : (
        <div className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-x-auto">
          <table className="w-full text-sm" data-testid="payment-history-table">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-start px-5 py-3 font-semibold text-gray-600">Order</th>
                <th className="text-start px-5 py-3 font-semibold text-gray-600 hidden sm:table-cell">Date</th>
                <th className="text-start px-5 py-3 font-semibold text-gray-600 hidden md:table-cell">Gateway</th>
                <th className="text-start px-5 py-3 font-semibold text-gray-600">Status</th>
                <th className="text-end px-5 py-3 font-semibold text-gray-600">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {transactions.map((t) => (
                <tr key={t.id} data-testid="payment-row" className="hover:bg-gray-50 transition">
                  <td className="px-5 py-3">
                    <span className="font-semibold text-gray-800">{t.order_number}</span>
                    {t.ref_id && (
                      <span className="block text-xs text-gray-400 break-all">Ref: {t.ref_id}</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-gray-500 hidden sm:table-cell">
                    {formatJalaliDate(t.created_at, JALALI_DATETIME_FORMAT)}
                  </td>
                  <td className="px-5 py-3 text-gray-600 hidden md:table-cell">
                    {t.gateway_display || t.gateway}
                  </td>
                  <td className="px-5 py-3">
                    <span
                      className={`text-xs font-semibold px-3 py-1 rounded-full ${STATUS_STYLES[t.status] || "bg-gray-100 text-gray-700"}`}
                    >
                      {t.status_display || t.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-end font-semibold text-gray-800">
                    {fmt(t.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-6">
          <button
            type="button"
            aria-label="Previous page"
            onClick={() => goToPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 border rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50"
          >
            ‹
          </button>
          <span className="px-3 py-1.5 text-sm text-gray-500">{page} / {totalPages}</span>
          <button
            type="button"
            aria-label="Next page"
            onClick={() => goToPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 border rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50"
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
};

export default PaymentMethodsTab;
