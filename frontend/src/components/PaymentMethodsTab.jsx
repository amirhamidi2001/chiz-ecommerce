import { useEffect, useState } from "react";
import { dashboardAPI } from "../services/api";

const CARD_ICONS = {
  card: "bi-credit-card-2-front",
  paypal: "bi-paypal",
  bank_transfer: "bi-bank",
  cash_on_delivery: "bi-cash-coin",
};

const fmt = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

const PaymentMethodsTab = () => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [methods, setMethods] = useState([]);

  useEffect(() => {
    dashboardAPI
      .getOrders({ page_size: 100 })
      .then(({ data }) => {
        const list = data.results ?? data;
        setOrders(list);

        // Derive unique payment methods from order history
        const map = {};
        list.forEach((o) => {
          const key = o.payment_method;
          if (!map[key]) {
            map[key] = { method: key, count: 0, total: 0, last_used: o.created_at };
          }
          map[key].count += 1;
          map[key].total += parseFloat(o.total);
          if (new Date(o.created_at) > new Date(map[key].last_used)) {
            map[key].last_used = o.created_at;
          }
        });
        setMethods(Object.values(map).sort((a, b) => b.count - a.count));
      })
      .catch(() => { })
      .finally(() => setLoading(false));
  }, []);

  const friendlyName = (method) =>
  ({
    card: "Credit / Debit Card",
    paypal: "PayPal",
    bank_transfer: "Bank Transfer",
    cash_on_delivery: "Cash on Delivery",
  }[method] || method?.replace(/_/g, " ") || "Unknown");

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Payment Methods</h2>
      </div>

      {/* Info banner */}
      <div className="bg-blue-50 border border-blue-100 text-blue-700 rounded-xl p-4 mb-6 flex items-start gap-3 text-sm">
        <i className="bi bi-info-circle text-lg flex-shrink-0"></i>
        <p>
          Payment methods are managed at checkout. This page shows a summary of payment
          methods you have used across your orders.
        </p>
      </div>

      {loading ? (
        <div className="grid md:grid-cols-2 gap-4">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-32 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : methods.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <i className="bi bi-credit-card text-5xl mb-4 block"></i>
          <p className="text-lg font-medium">No payment history</p>
          <p className="text-sm mt-1">Place your first order to see payment info here.</p>
        </div>
      ) : (
        <>
          {/* Method cards */}
          <div className="grid md:grid-cols-2 gap-4 mb-8">
            {methods.map((m) => (
              <div
                key={m.method}
                className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm flex items-center gap-4"
              >
                <div className="w-12 h-12 rounded-full bg-teal-50 flex items-center justify-center flex-shrink-0">
                  <i className={`bi ${CARD_ICONS[m.method] || "bi-credit-card"} text-teal-600 text-xl`}></i>
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="font-bold text-gray-800">{friendlyName(m.method)}</h4>
                  <div className="flex gap-4 mt-1 text-sm text-gray-500">
                    <span>{m.count} order{m.count !== 1 ? "s" : ""}</span>
                    <span>{fmt(m.total)} total</span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    Last used {new Date(m.last_used).toLocaleDateString("en-US", {
                      year: "numeric", month: "short", day: "numeric",
                    })}
                  </p>
                </div>
                <span className="bg-teal-100 text-teal-700 text-xs px-2 py-1 rounded-full font-medium flex-shrink-0">
                  Used
                </span>
              </div>
            ))}
          </div>

          {/* Recent transactions table */}
          <h3 className="text-lg font-bold text-gray-800 mb-4">Recent Transactions</h3>
          <div className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  <th className="text-left px-5 py-3 font-semibold text-gray-600">Order</th>
                  <th className="text-left px-5 py-3 font-semibold text-gray-600 hidden sm:table-cell">Date</th>
                  <th className="text-left px-5 py-3 font-semibold text-gray-600 hidden md:table-cell">Method</th>
                  <th className="text-right px-5 py-3 font-semibold text-gray-600">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {orders.slice(0, 10).map((order) => (
                  <tr key={order.id} className="hover:bg-gray-50 transition">
                    <td className="px-5 py-3">
                      <span className="font-semibold text-gray-800">{order.order_number}</span>
                      {order.card_last_four && (
                        <span className="ml-2 text-xs text-gray-400">**** {order.card_last_four}</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-gray-500 hidden sm:table-cell">
                      {new Date(order.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-3 hidden md:table-cell">
                      <div className="flex items-center gap-1.5">
                        <i className={`bi ${CARD_ICONS[order.payment_method] || "bi-credit-card"} text-gray-400`}></i>
                        <span className="text-gray-600 capitalize">
                          {friendlyName(order.payment_method)}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-right font-semibold text-gray-800">
                      {fmt(order.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};

export default PaymentMethodsTab;
