import { useEffect, useState } from "react";
import { adminAPI } from "../../services/api";
import StatCard from "../../components/admin/StatCard";

const fmt = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

// ── SVG bar chart ─────────────────────────────────────────────────────────────
const BarChart = ({ data = [], valueKey, labelKey, color = "#0d9488", height = 180 }) => {
  if (!data.length)
    return (
      <div className="flex items-center justify-center text-gray-300 text-sm" style={{ height }}>
        No data available
      </div>
    );

  const max = Math.max(...data.map((d) => Number(d[valueKey]) || 0)) || 1;

  return (
    <div className="w-full overflow-x-auto">
      <div className="flex items-end gap-1 min-w-0" style={{ height }}>
        {data.map((d, i) => {
          const pct = ((Number(d[valueKey]) || 0) / max) * 100;
          return (
            <div
              key={i}
              className="flex-1 flex flex-col items-center gap-1 group relative min-w-[20px]"
            >
              {/* Tooltip */}
              <div className="absolute bottom-full mb-1.5 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition pointer-events-none whitespace-nowrap z-20 shadow-xl">
                <div className="font-semibold">
                  {typeof d[valueKey] === "number" && d[valueKey] > 999
                    ? fmt(d[valueKey])
                    : d[valueKey]}
                </div>
                <div className="text-gray-300">{d[labelKey]}</div>
              </div>
              {/* Bar */}
              <div
                style={{ height: `${Math.max(pct, 2)}%`, backgroundColor: color }}
                className="w-full rounded-t opacity-70 hover:opacity-100 transition-all cursor-pointer"
              />
            </div>
          );
        })}
      </div>
      {/* X-axis labels */}
      <div className="flex gap-1 mt-1.5">
        {data.map((d, i) => (
          <div key={i} className="flex-1 text-center min-w-[20px]">
            <span className="text-[10px] text-gray-400 truncate block">{d[labelKey]}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ── Horizontal bar chart (for top products) ───────────────────────────────────
const HBar = ({ items = [], valueKey, nameKey, color = "#0d9488" }) => {
  if (!items.length) return <p className="text-sm text-gray-400">No data</p>;
  const max = Math.max(...items.map((i) => Number(i[valueKey]) || 0)) || 1;

  return (
    <div className="space-y-3">
      {items.slice(0, 8).map((item, idx) => {
        const pct = ((Number(item[valueKey]) || 0) / max) * 100;
        return (
          <div key={idx}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-gray-700 font-medium truncate max-w-[60%]">
                {item[nameKey]}
              </span>
              <span className="text-gray-500 font-semibold">
                {typeof item[valueKey] === "number" && item[valueKey] > 999
                  ? fmt(item[valueKey])
                  : item[valueKey]}
              </span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2">
              <div
                className="h-2 rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, backgroundColor: color }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ── Stat row ──────────────────────────────────────────────────────────────────
const StatRow = ({ label, value, icon, color = "teal" }) => {
  const colors = {
    teal: "text-teal-600 bg-teal-50",
    blue: "text-blue-600 bg-blue-50",
    amber: "text-amber-600 bg-amber-50",
    red: "text-red-600 bg-red-50",
    violet: "text-violet-600 bg-violet-50",
    green: "text-green-600 bg-green-50",
  };
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-2.5">
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs ${colors[color]}`}>
          <i className={`bi ${icon}`}></i>
        </div>
        <span className="text-sm text-gray-600">{label}</span>
      </div>
      <span className="font-bold text-gray-800">{value}</span>
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────
const AdminAnalytics = () => {
  const [overview, setOverview] = useState(null);
  const [revenueData, setRevenueData] = useState(null);
  const [userStats, setUserStats] = useState(null);
  const [productStats, setProductStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("30d");
  const [months, setMonths] = useState(12);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      adminAPI.getOverview(period),
      adminAPI.getRevenueStats(months),
      adminAPI.getUserStats(),
      adminAPI.getProductStats(),
    ])
      .then(([ov, rev, usr, prd]) => {
        setOverview(ov.data);
        setRevenueData(rev.data);
        setUserStats(usr.data);
        setProductStats(prd.data);
      })
      .catch(() => { })
      .finally(() => setLoading(false));
  }, [period, months]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap justify-between items-center gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Analytics</h1>
          <p className="text-sm text-gray-500">Deep-dive performance metrics</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="px-3 py-2 border border-gray-200 rounded-xl bg-white text-sm focus:outline-none"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="1y">Last year</option>
          </select>
          <select
            value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
            className="px-3 py-2 border border-gray-200 rounded-xl bg-white text-sm focus:outline-none"
          >
            <option value={3}>3-month chart</option>
            <option value={6}>6-month chart</option>
            <option value={12}>12-month chart</option>
          </select>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Revenue" icon="bi-currency-dollar" color="teal" loading={loading}
          value={overview ? fmt(overview.revenue.current) : "—"}
          change={overview?.revenue.change}
        />
        <StatCard
          title="Orders" icon="bi-box-seam" color="blue" loading={loading}
          value={overview?.orders.current ?? "—"}
          change={overview?.orders.change}
        />
        <StatCard
          title="New Users" icon="bi-person-plus" color="violet" loading={loading}
          value={overview?.users.current ?? "—"}
          change={overview?.users.change}
        />
        <StatCard
          title="Avg Order Value" icon="bi-receipt" color="amber" loading={loading}
          value={
            overview?.revenue.current && overview?.orders.current
              ? fmt(overview.revenue.current / (overview.orders.current || 1))
              : "—"
          }
        />
      </div>

      {/* Revenue over time */}
      <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
        <div className="flex justify-between items-center mb-5">
          <h3 className="font-bold text-gray-800">Monthly Revenue</h3>
          <span className="text-xs text-gray-400">Last {months} months</span>
        </div>
        {loading ? (
          <div className="h-48 bg-gray-100 rounded-xl animate-pulse" />
        ) : (
          <BarChart
            data={revenueData?.monthly_revenue ?? []}
            valueKey="revenue"
            labelKey="month"
            height={200}
          />
        )}
      </div>

      {/* Orders + Users side by side */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Orders chart */}
        <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
          <h3 className="font-bold text-gray-800 mb-5">Monthly Order Volume</h3>
          {loading ? (
            <div className="h-44 bg-gray-100 rounded-xl animate-pulse" />
          ) : (
            <BarChart
              data={revenueData?.monthly_revenue ?? []}
              valueKey="orders"
              labelKey="month"
              color="#3b82f6"
              height={180}
            />
          )}
        </div>

        {/* User stats */}
        <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
          <h3 className="font-bold text-gray-800 mb-4">User Statistics</h3>
          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-8 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : (
            <>
              <StatRow label="Total Registered" value={userStats?.total ?? 0} icon="bi-people" color="teal" />
              <StatRow label="Active Users" value={userStats?.active ?? 0} icon="bi-person-check" color="green" />
              <StatRow label="Verified Users" value={userStats?.verified ?? 0} icon="bi-shield-check" color="blue" />
              <StatRow label="New This Month" value={userStats?.new_this_month ?? 0} icon="bi-person-plus" color="violet" />
              <StatRow label="Admins" value={userStats?.admins ?? 0} icon="bi-person-badge" color="amber" />
              {/* Activation rate */}
              <div className="mt-4 pt-3 border-t border-gray-100">
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-gray-500">Activation Rate</span>
                  <span className="font-bold text-gray-800">
                    {userStats?.total
                      ? `${Math.round((userStats.active / userStats.total) * 100)}%`
                      : "0%"}
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div
                    className="h-2 rounded-full bg-teal-500 transition-all"
                    style={{
                      width: userStats?.total
                        ? `${Math.round((userStats.active / userStats.total) * 100)}%`
                        : "0%",
                    }}
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Product stats + top sellers */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Product breakdown */}
        <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
          <h3 className="font-bold text-gray-800 mb-4">Product Inventory</h3>
          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-8 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : (
            <>
              <StatRow label="Total Products" value={productStats?.total ?? 0} icon="bi-bag" color="teal" />
              <StatRow label="On Sale" value={productStats?.on_sale ?? 0} icon="bi-tag" color="red" />
              <StatRow label="New Arrivals" value={productStats?.new ?? 0} icon="bi-stars" color="amber" />
              <StatRow label="Low Stock (≤5)" value={productStats?.low_stock ?? 0} icon="bi-exclamation-triangle" color="amber" />
              <StatRow label="Out of Stock" value={productStats?.out_of_stock ?? 0} icon="bi-x-circle" color="red" />
              <div className="mt-4 pt-3 border-t border-gray-100 flex justify-between items-center">
                <span className="text-xs text-gray-500">Avg Rating</span>
                <div className="flex items-center gap-1.5">
                  <i className="bi bi-star-fill text-yellow-400 text-sm"></i>
                  <span className="font-bold text-gray-800">
                    {Number(productStats?.avg_rating || 0).toFixed(1)}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Top products by revenue */}
        <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
          <h3 className="font-bold text-gray-800 mb-4">Top Products by Revenue</h3>
          {loading ? (
            <div className="space-y-3">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-8 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : (
            <HBar
              items={revenueData?.top_products ?? []}
              valueKey="revenue"
              nameKey="product_name"
              color="#0d9488"
            />
          )}
        </div>
      </div>

      {/* Top products by units */}
      <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
        <h3 className="font-bold text-gray-800 mb-5">Top Products by Units Sold</h3>
        {loading ? (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-6 bg-gray-100 rounded animate-pulse" />
            ))}
          </div>
        ) : (
          <HBar
            items={revenueData?.top_products ?? []}
            valueKey="total_sold"
            nameKey="product_name"
            color="#3b82f6"
          />
        )}
      </div>

      {/* Order status distribution */}
      {!loading && overview?.order_status_distribution?.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm">
          <h3 className="font-bold text-gray-800 mb-4">Order Status Breakdown</h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {overview.order_status_distribution.map((item) => {
              const total = overview.order_status_distribution.reduce((s, i) => s + i.count, 0);
              const pct = total ? Math.round((item.count / total) * 100) : 0;
              const COLORS = {
                pending: "bg-gray-100 text-gray-700 border-gray-200",
                processing: "bg-yellow-50 text-yellow-700 border-yellow-200",
                shipped: "bg-blue-50 text-blue-700 border-blue-200",
                delivered: "bg-teal-50 text-teal-700 border-teal-200",
                cancelled: "bg-red-50 text-red-700 border-red-200",
              };
              return (
                <div
                  key={item.status}
                  className={`rounded-xl border p-4 text-center ${COLORS[item.status] || "bg-gray-50 text-gray-700 border-gray-200"}`}
                >
                  <div className="text-2xl font-bold">{item.count}</div>
                  <div className="text-xs font-semibold capitalize mt-0.5">{item.status}</div>
                  <div className="text-xs opacity-70 mt-1">{pct}% of total</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminAnalytics;
