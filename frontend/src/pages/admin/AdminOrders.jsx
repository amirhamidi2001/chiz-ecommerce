import { useEffect, useState } from "react";
import { adminAPI } from "../../services/api";
import DataTable from "../../components/admin/DataTable";
import ConfirmModal from "../../components/admin/ConfirmModal";
import Toast, { useToast } from "../../components/admin/Toast";

const fmt = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

const STATUS_STYLES = {
  pending: "bg-gray-100 text-gray-700",
  processing: "bg-yellow-100 text-yellow-700",
  shipped: "bg-blue-100 text-blue-700",
  delivered: "bg-teal-100 text-teal-700",
  cancelled: "bg-red-100 text-red-700",
};

const ORDER_STATUSES = ["pending", "processing", "shipped", "delivered", "cancelled"];

// ── Order detail modal ────────────────────────────────────────────────────────
const OrderDetailModal = ({ order, onClose, onStatusUpdate }) => {
  const [newStatus, setNewStatus] = useState(order?.status || "");
  const [saving, setSaving] = useState(false);
  const { toast, show, dismiss } = useToast();

  if (!order) return null;

  const handleUpdate = async () => {
    if (newStatus === order.status) { onClose(); return; }
    setSaving(true);
    try {
      await adminAPI.updateOrderStatus(order.id, newStatus);
      show("Status updated");
      onStatusUpdate(order.id, newStatus);
      setTimeout(onClose, 800);
    } catch {
      show("Failed to update status", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4" onClick={onClose}>
      <Toast toast={toast} onDismiss={dismiss} />
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center p-6 border-b sticky top-0 bg-white z-10">
          <h3 className="text-lg font-bold text-gray-800">Order #{order.order_number}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <i className="bi bi-x-lg text-xl"></i>
          </button>
        </div>
        <div className="p-6 space-y-6">
          {/* Customer */}
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="bg-gray-50 rounded-xl p-4">
              <h5 className="text-xs font-semibold text-gray-500 uppercase mb-2">Customer</h5>
              <p className="font-semibold text-gray-800">{order.full_name}</p>
              <p className="text-sm text-gray-600">{order.email}</p>
              <p className="text-sm text-gray-600">{order.phone}</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-4">
              <h5 className="text-xs font-semibold text-gray-500 uppercase mb-2">Shipping Address</h5>
              <p className="text-sm text-gray-700 leading-relaxed">
                {order.shipping_address}{order.shipping_apartment ? `, ${order.shipping_apartment}` : ""}<br />
                {order.shipping_city}, {order.shipping_state} {order.shipping_zip}<br />
                {order.shipping_country}
              </p>
            </div>
          </div>

          {/* Status update */}
          <div className="flex items-center gap-3 bg-gray-50 rounded-xl p-4">
            <label className="text-sm font-semibold text-gray-700 flex-shrink-0">Update Status:</label>
            <select value={newStatus} onChange={(e) => setNewStatus(e.target.value)}
              className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:border-teal-500">
              {ORDER_STATUSES.map((s) => (
                <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
              ))}
            </select>
            <button onClick={handleUpdate} disabled={saving}
              className="px-4 py-1.5 bg-teal-600 text-white text-sm rounded-lg hover:bg-teal-700 transition disabled:opacity-60 font-medium">
              {saving ? "Saving…" : "Update"}
            </button>
          </div>

          {/* Items */}
          {order.items && (
            <div>
              <h5 className="font-semibold text-gray-700 mb-3">Items ({order.items.length})</h5>
              <div className="space-y-3">
                {order.items.map((item) => (
                  <div key={item.id} className="flex gap-3 items-center">
                    {item.product_image
                      ? <img src={item.product_image} alt={item.product_name} className="w-12 h-12 object-cover rounded-lg border" />
                      : <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center"><i className="bi bi-image text-gray-400"></i></div>
                    }
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{item.product_name}</p>
                      <p className="text-xs text-gray-500">Qty: {item.quantity} × {fmt(item.unit_price)}</p>
                    </div>
                    <span className="font-semibold text-sm">{fmt(item.subtotal)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Totals */}
          <div className="bg-gray-50 rounded-xl p-4 space-y-2 text-sm">
            {[
              ["Subtotal", fmt(order.subtotal)],
              ["Shipping", fmt(order.shipping_cost)],
              ["Tax", fmt(order.tax)],
            ].map(([l, v]) => (
              <div key={l} className="flex justify-between text-gray-600"><span>{l}</span><span>{v}</span></div>
            ))}
            {parseFloat(order.discount) > 0 && (
              <div className="flex justify-between text-green-600"><span>Discount</span><span>-{fmt(order.discount)}</span></div>
            )}
            <div className="flex justify-between font-bold text-gray-800 pt-2 border-t border-gray-200">
              <span>Total</span><span>{fmt(order.total)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────
const AdminOrders = () => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("-created_at");
  const [statusFilter, setStatusFilter] = useState("");
  const [detailOrder, setDetailOrder] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const { toast, show, dismiss } = useToast();

  const fetchOrders = () => {
    setLoading(true);
    adminAPI.getOrders({
      page, search, ordering: sort,
      status: statusFilter || undefined, page_size: 10,
    })
      .then(({ data }) => {
        setOrders(data.results ?? data);
        setTotal(data.count ?? (data.results?.length ?? data.length));
      })
      .catch(() => show("Failed to load orders", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchOrders(); }, [page, search, sort, statusFilter]);

  const openDetail = async (id) => {
    setDetailLoading(true);
    try {
      const { data } = await adminAPI.getOrder(id);
      setDetailOrder(data);
    } catch {
      show("Failed to load order details", "error");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleStatusUpdate = (id, newStatus) => {
    setOrders((prev) =>
      prev.map((o) => (o.id === id ? { ...o, status: newStatus } : o))
    );
    show("Order status updated");
  };

  const COLUMNS = [
    {
      key: "order_number", label: "Order", sortable: true,
      render: (v) => <span className="font-semibold text-gray-800 text-sm">{v}</span>,
    },
    {
      key: "full_name", label: "Customer",
      render: (v, row) => (
        <div>
          <p className="font-medium text-gray-800 text-sm">{v}</p>
          <p className="text-xs text-gray-500">{row.email}</p>
        </div>
      ),
    },
    {
      key: "status", label: "Status", sortable: true,
      render: (v) => (
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full capitalize ${STATUS_STYLES[v]}`}>{v}</span>
      ),
    },
    {
      key: "payment_method", label: "Payment",
      render: (v) => <span className="text-sm capitalize text-gray-600">{v?.replace(/_/g, " ")}</span>,
    },
    {
      key: "items_count", label: "Items",
      render: (v) => <span className="text-sm text-gray-600">{v}</span>,
    },
    {
      key: "total", label: "Total", sortable: true,
      render: (v) => <span className="font-semibold text-gray-800">{fmt(v)}</span>,
    },
    {
      key: "created_at", label: "Date", sortable: true,
      render: (v) => <span className="text-sm text-gray-500">{new Date(v).toLocaleDateString()}</span>,
    },
  ];

  const ActionBtn = ({ icon, label, onClick, variant = "default" }) => (
    <button onClick={onClick} title={label}
      className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition border ${variant === "primary" ? "bg-teal-600 text-white border-teal-600 hover:bg-teal-700"
          : "border-gray-200 text-gray-600 hover:bg-gray-50"
        }`}>
      <i className={`bi ${icon}`}></i>
    </button>
  );

  return (
    <div className="space-y-5">
      <Toast toast={toast} onDismiss={dismiss} />
      {detailOrder && (
        <OrderDetailModal
          order={detailOrder}
          onClose={() => setDetailOrder(null)}
          onStatusUpdate={handleStatusUpdate}
        />
      )}

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Orders</h1>
          <p className="text-sm text-gray-500">{total} total orders</p>
        </div>
      </div>

      <DataTable
        columns={COLUMNS}
        data={orders}
        loading={loading}
        totalCount={total}
        page={page}
        pageSize={10}
        onPageChange={setPage}
        sort={sort}
        onSort={setSort}
        search={search}
        onSearch={(v) => { setSearch(v); setPage(1); }}
        searchPlaceholder="Search by order #, customer…"
        emptyIcon="bi-box-seam"
        emptyText="No orders found"
        filters={
          <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-200 rounded-lg bg-white text-sm focus:outline-none">
            <option value="">All Statuses</option>
            {ORDER_STATUSES.map((s) => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        }
        rowActions={(row) => (
          <ActionBtn icon="bi-eye" label="View Details" onClick={() => openDetail(row.id)} variant="primary" />
        )}
      />
    </div>
  );
};

export default AdminOrders;
