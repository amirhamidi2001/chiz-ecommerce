import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { adminAPI } from "../../services/api";
import StatCard from "../../components/admin/StatCard";

const fmt = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

const STATUS_STYLES = {
  pending: "bg-gray-100 text-gray-700",
  processing: "bg-yellow-100 text-yellow-700",
  shipped: "bg-blue-100 text-blue-700",
  delivered: "bg-teal-100 text-teal-700",
  cancelled: "bg-red-100 text-red-700",
};

// ── Tiny SVG bar chart ────────────────────────────────────────────────────────
const MiniBarChart = ({ data = [], valueKey = "revenue", labelKey = "date" }) => {
  if (!data.length) return <div className="h-32 flex items-center justify-center text-gray-300 text-sm">No data</div>;
  const max = Math.max(...data.map((d) => d[valueKey])) || 1;
  const last12 = data.slice(-14);

  return (
    <div className="flex items-end gap-1 h-32 w-full">
      {last12.map((d, i) => {
        const h = Math.max((d[valueKey] / max) * 100, 2);
        return (
          <div key={i} className="flex-1 flex flex-col items-center gap-1 group relative">
            <div
              style={{ height: `${h}%` }}
              className="w-full bg-teal-200 hover:bg-teal-500 rounded-t transition-all cursor-pointer"
            />
            <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition whitespace-nowrap z-10 pointer-events-none">
              {fmt(d[valueKey])}
              <br />
              <span className="text-gray-300">{d[labelKey]}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ── Mini donut chart (SVG) ────────────────────────────────────────────────────
const DonutChart = ({ data = [] }) => {
  const total = data.reduce((s, d) => s + d.count, 0) || 1;
  const COLORS = ["#0d9488", "#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444"];
  let cumulative = 0;

  const getPath = (percent, startPercent) => {
    const r = 40, cx = 50, cy = 50;
    const start = (startPercent * 360 - 90) * (Math.PI / 180);
    const end = ((startPercent + percent) * 360 - 90) * (Math.PI / 180);
    const x1 = cx + r * Math.cos(start);
    const y1 = cy + r * Math.sin(start);
    const x2 = cx + r * Math.cos(end);
    const y2 = cy + r * Math.sin(end);
    const large = percent > 0.5 ? 1 : 0;
    return `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`;
  };

  return (
    <div className="flex items-center gap-6">
      <svg viewBox="0 0 100 100" className="w-28 h-28 flex-shrink-0">
        <circle cx="50" cy="50" r="28" fill="white" />
        {data.map((d, i) => {
          const pct = d.count / total;
          const path = getPath(pct, cumulative);
          cumulative += pct;
          return <path key={i} d={path} fill={COLORS[i % COLORS.length]} />;
        })}
      </svg>
      <div className="space-y-1.5">
        {data.map((d, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
            <span className="text-gray-600 capitalize">{d.status}</span>
            <span className="font-semibold text-gray-800 ml-auto pl-2">{d.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────
const AdminDashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("30d");
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    adminAPI
      .getOverview(period)
      .then(({ data: d }) => setData(d))
      .catch(() => { })
      .finally(() => setLoading(false));
  }, [period]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap justify-between items-center gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Dashboard Overview</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
          </p>
        </div>
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="px-4 py-2 border border-gray-200 rounded-xl bg-white text-sm font-medium focus:outline-none"
        >
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="90d">Last 90 days</option>
          <option value="1y">Last 12 months</option>
        </select>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Revenue" icon="bi-currency-dollar" color="teal" loading={loading}
          value={data ? fmt(data.revenue.current) : "—"}
          change={data?.revenue.change}
        />
        <StatCard
          title="Orders" icon="bi-box-seam" color="blue" loading={loading}
          value={data?.orders.current ?? "—"}
          change={data?.orders.change}
          onClick={() => navigate("/admin/orders")}
        />
        <StatCard
          title="New Users" icon="bi-people" color="violet" loading={loading}
          value={data?.users.current ?? "—"}
          change={data?.users.change}
          onClick={() => navigate("/admin/users")}
        />
        <StatCard
          title="Total Products" icon="bi-bag" color="amber" loading={loading}
          value={data?.products.total ?? "—"}
          onClick={() => navigate("/admin/products")}
        />
      </div>

      {/* Second row: alerts */}
      {!loading && data && (
        <div className="grid sm:grid-cols-3 gap-4">
          {[
            {
              label: "Low Stock", value: data.product_stats?.low_stock ?? 0,
              icon: "bi-exclamation-triangle", color: "text-amber-600 bg-amber-50", link: "/admin/products?in_stock=false"
            },
            {
              label: "Out of Stock", value: data.product_stats?.out_of_stock ?? 0,
              icon: "bi-x-circle", color: "text-red-600 bg-red-50", link: "/admin/products"
            },
            {
              label: "Pending Orders", value: data.order_status_distribution?.find(s => s.status === "pending")?.count ?? 0,
              icon: "bi-clock", color: "text-blue-600 bg-blue-50", link: "/admin/orders?status=pending"
            },
          ].map((a) => (
            <div key={a.label}
              onClick={() => navigate(a.link)}
              className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm flex items-center gap-3 cursor-pointer hover:shadow-md transition">
              <div className={`w-10 h-10 rounded-xl ${a.color} flex items-center justify-center flex-shrink-0`}>
                <i className={`bi ${a.icon} text-lg`}></i>
              </div>
              <div>
                <div className="text-xl font-bold text-gray-800">{a.value}</div>
                <div className="text-xs text-gray-500">{a.label}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Charts row */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Revenue chart */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
          <h3 className="font-bold text-gray-800 mb-4">Revenue — Last 14 Days</h3>
          {loading ? (
            <div className="h-32 bg-gray-100 rounded-xl animate-pulse" />
          ) : (
            <MiniBarChart data={data?.revenue_chart ?? []} valueKey="revenue" labelKey="date" />
          )}
        </div>

        {/* Order status distribution */}
        <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
          <h3 className="font-bold text-gray-800 mb-4">Order Status</h3>
          {loading ? (
            <div className="h-32 bg-gray-100 rounded-xl animate-pulse" />
          ) : (
            <DonutChart data={data?.order_status_distribution ?? []} />
          )}
        </div>
      </div>

      {/* Bottom row */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Recent orders */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex justify-between items-center px-6 py-4 border-b border-gray-100">
            <h3 className="font-bold text-gray-800">Recent Orders</h3>
            <button onClick={() => navigate("/admin/orders")} className="text-sm text-teal-600 hover:underline">
              View All
            </button>
          </div>
          <div className="divide-y divide-gray-50">
            {loading
              ? [...Array(5)].map((_, i) => (
                <div key={i} className="px-6 py-3 flex gap-3">
                  <div className="h-4 bg-gray-100 rounded flex-1 animate-pulse" />
                  <div className="h-4 bg-gray-100 rounded w-16 animate-pulse" />
                </div>
              ))
              : (data?.recent_orders ?? []).map((o) => (
                <div key={o.id}
                  onClick={() => navigate(`/admin/orders`)}
                  className="px-6 py-3 flex items-center justify-between gap-3 hover:bg-gray-50 cursor-pointer transition">
                  <div className="min-w-0">
                    <p className="font-semibold text-gray-800 text-sm truncate">{o.order_number}</p>
                    <p className="text-xs text-gray-500">{o.full_name || o.email}</p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full capitalize ${STATUS_STYLES[o.status]}`}>
                      {o.status}
                    </span>
                    <span className="font-bold text-sm text-gray-800">{fmt(o.total)}</span>
                  </div>
                </div>
              ))}
          </div>
        </div>

        {/* Top products */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="flex justify-between items-center px-6 py-4 border-b border-gray-100">
            <h3 className="font-bold text-gray-800">Top Products</h3>
            <button onClick={() => navigate("/admin/products")} className="text-sm text-teal-600 hover:underline">
              View All
            </button>
          </div>
          <div className="divide-y divide-gray-50">
            {loading
              ? [...Array(5)].map((_, i) => (
                <div key={i} className="px-6 py-3 flex gap-3">
                  <div className="h-4 bg-gray-100 rounded flex-1 animate-pulse" />
                  <div className="h-4 bg-gray-100 rounded w-16 animate-pulse" />
                </div>
              ))
              : (data?.top_products ?? []).slice(0, 6).map((p, i) => (
                <div key={p.product_id} className="px-6 py-3 flex items-center gap-3">
                  <span className="text-xs font-bold text-gray-400 w-5 text-center">
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{p.product_name}</p>
                    <p className="text-xs text-gray-500">{p.total_sold} units sold</p>
                  </div>
                  <span className="text-sm font-bold text-teal-700">{fmt(p.revenue)}</span>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
