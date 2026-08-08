import { useCallback, useEffect, useRef, useState } from "react";
import { dashboardAPI } from "../services/api";

const STATUS_STYLES = {
  pending: "bg-gray-100 text-gray-700",
  processing: "bg-yellow-100 text-yellow-700",
  shipped: "bg-blue-100 text-blue-700",
  delivered: "bg-teal-100 text-teal-700",
  cancelled: "bg-red-100 text-red-700",
};

const fmt = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

// ─── Order detail modal ───────────────────────────────────────────────────────
const OrderDetailModal = ({ orderId, onClose }) => {
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardAPI
      .getOrder(orderId)
      .then(({ data }) => setOrder(data))
      .catch(() => { })
      .finally(() => setLoading(false));
  }, [orderId]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center p-6 border-b">
          <h3 className="text-lg font-bold text-gray-800">
            {order ? `Order ${order.order_number}` : "Order Details"}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <i className="bi bi-x-lg text-xl"></i>
          </button>
        </div>

        {loading ? (
          <div className="flex justify-center p-12">
            <div className="w-8 h-8 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : order ? (
          <div className="p-6 space-y-6">
            {/* Status + Meta */}
            <div className="flex flex-wrap gap-3 items-center">
              <span
                className={`text-xs font-semibold px-3 py-1 rounded-full capitalize ${STATUS_STYLES[order.status]}`}
              >
                {order.status}
              </span>
              <span className="text-sm text-gray-500">
                Placed {new Date(order.created_at).toLocaleDateString()}
              </span>
            </div>

            {/* Items */}
            <div>
              <h5 className="font-semibold text-gray-700 mb-3">Items</h5>
              <div className="space-y-3">
                {order.items.map((item) => (
                  <div key={item.id} className="flex gap-3 items-center">
                    {item.product_image ? (
                      <img
                        src={item.product_image}
                        alt={item.product_name}
                        className="w-14 h-14 object-cover rounded-lg border"
                      />
                    ) : (
                      <div className="w-14 h-14 bg-gray-100 rounded-lg flex items-center justify-center">
                        <i className="bi bi-image text-gray-400 text-xl"></i>
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm text-gray-800 truncate">
                        {item.product_name}
                      </p>
                      <p className="text-xs text-gray-500">Qty: {item.quantity}</p>
                    </div>
                    <div className="text-sm font-semibold text-gray-800">
                      {fmt(item.subtotal)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Price breakdown */}
            <div className="bg-gray-50 rounded-xl p-4 space-y-2 text-sm">
              <div className="flex justify-between text-gray-600">
                <span>Subtotal</span><span>{fmt(order.subtotal)}</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>Shipping</span><span>{fmt(order.shipping_cost)}</span>
              </div>
              <div className="flex justify-between text-gray-600">
                <span>Tax</span><span>{fmt(order.tax)}</span>
              </div>
              {parseFloat(order.discount) > 0 && (
                <div className="flex justify-between text-green-600">
                  <span>Discount</span><span>-{fmt(order.discount)}</span>
                </div>
              )}
              <div className="flex justify-between font-bold text-gray-800 pt-2 border-t border-gray-200">
                <span>Total</span><span>{fmt(order.total)}</span>
              </div>
            </div>

            {/* Shipping address */}
            <div>
              <h5 className="font-semibold text-gray-700 mb-2">Shipping Address</h5>
              <p className="text-sm text-gray-600 leading-relaxed">
                {order.first_name} {order.last_name}<br />
                {order.shipping_address}
                {order.shipping_apartment && `, ${order.shipping_apartment}`}<br />
                {order.shipping_city}, {order.shipping_state} {order.shipping_zip}<br />
                {order.shipping_country}
              </p>
            </div>

            {/* Payment */}
            <div>
              <h5 className="font-semibold text-gray-700 mb-2">Payment</h5>
              <p className="text-sm text-gray-600 capitalize">
                {order.payment_method?.replace("_", " ")}
                {order.card_last_four && ` (**** ${order.card_last_four})`}
              </p>
            </div>
          </div>
        ) : (
          <div className="p-8 text-center text-gray-500">Order not found.</div>
        )}
      </div>
    </div>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────
const OrdersTab = () => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedOrderId, setSelectedOrderId] = useState(null);
  const searchTimeout = useRef(null);

  const fetchOrders = useCallback(() => {
    setLoading(true);
    dashboardAPI
      .getOrders({ page, search, status: statusFilter || undefined, page_size: 8 })
      .then(({ data }) => {
        setOrders(data.results ?? data);
        if (data.count) {
          setTotalPages(Math.ceil(data.count / 8));
        }
      })
      .catch(() => { })
      .finally(() => setLoading(false));
  }, [page, search, statusFilter]);

  useEffect(() => { fetchOrders(); }, [fetchOrders]);

  const handleSearch = (e) => {
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setSearch(e.target.value);
      setPage(1);
    }, 400);
  };

  return (
    <div>
      {selectedOrderId && (
        <OrderDetailModal
          orderId={selectedOrderId}
          onClose={() => setSelectedOrderId(null)}
        />
      )}

      {/* Header */}
      <div className="flex flex-wrap justify-between items-center gap-3 mb-6">
        <h2 className="text-2xl font-bold text-gray-800">My Orders</h2>
        <div className="flex gap-2 flex-wrap">
          <div className="relative">
            <i className="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm"></i>
            <input
              type="text"
              placeholder="Search orders…"
              onChange={handleSearch}
              className="pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-teal-500 w-48"
            />
          </div>
          <select
            className="px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white"
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="shipped">Shipped</option>
            <option value="delivered">Delivered</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      {/* Order list */}
      {loading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : orders.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <i className="bi bi-box-seam text-5xl mb-4 block"></i>
          <p className="text-lg font-medium">No orders found</p>
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <div
              key={order.id}
              className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm hover:shadow-md transition"
            >
              <div className="flex flex-wrap justify-between gap-3">
                <div>
                  <span className="font-bold text-gray-800 text-sm">
                    {order.order_number}
                  </span>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {new Date(order.created_at).toLocaleDateString("en-US", {
                      year: "numeric", month: "short", day: "numeric",
                    })}
                    {" · "}{order.items_count} item{order.items_count !== 1 ? "s" : ""}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`text-xs font-semibold px-3 py-1 rounded-full capitalize ${STATUS_STYLES[order.status]}`}
                  >
                    {order.status}
                  </span>
                  <span className="font-bold text-gray-800">{fmt(order.total)}</span>
                </div>
              </div>

              {/* Product thumbnails */}
              {order.preview_images?.length > 0 && (
                <div className="flex gap-2 mt-3">
                  {order.preview_images.map((img, idx) => (
                    <img
                      key={idx}
                      src={img}
                      alt=""
                      className="w-12 h-12 object-cover rounded-lg border"
                    />
                  ))}
                </div>
              )}

              <button
                onClick={() => setSelectedOrderId(order.id)}
                className="mt-3 text-sm text-teal-600 hover:underline font-medium"
              >
                View Details →
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-8">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 border rounded-lg text-sm disabled:opacity-40 hover:bg-gray-50"
          >
            ‹
          </button>
          {[...Array(totalPages)].map((_, i) => (
            <button
              key={i}
              onClick={() => setPage(i + 1)}
              className={`px-3 py-1.5 border rounded-lg text-sm ${page === i + 1
                  ? "bg-teal-600 text-white border-teal-600"
                  : "hover:bg-gray-50"
                }`}
            >
              {i + 1}
            </button>
          ))}
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
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

export default OrdersTab;
