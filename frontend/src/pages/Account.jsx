import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import AccountSidebar from "../components/AccountSidebar";
import OrdersTab from "../components/OrdersTab";
import WishlistTab from "../components/WishlistTab";
import AddressesTab from "../components/AddressesTab";
import ReviewsTab from "../components/ReviewsTab";
import SettingsTab from "../components/SettingsTab";
import PaymentMethodsTab from "../components/PaymentMethodsTab";
import { dashboardAPI } from "../services/api";

const fmt = (n) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

// ─── Valid tab ids ─────────────────────────────────────────────────────────
const VALID_TABS = ["overview", "orders", "wishlist", "reviews", "addresses", "settings", "payments"];

// ─── Overview / landing tab ──────────────────────────────────────────────
const OverviewTab = ({ onNavigate }) => {
  const { user } = useAuth();
  const [summary, setSummary]           = useState(null);
  const [recentOrders, setRecentOrders] = useState([]);
  const [loading, setLoading]           = useState(true);

  useEffect(() => {
    Promise.all([
      dashboardAPI.getSummary(),
      dashboardAPI.getOrders({ page_size: 3, ordering: "-created_at" }),
    ])
      .then(([sumRes, ordersRes]) => {
        setSummary(sumRes.data);
        setRecentOrders(ordersRes.data.results ?? ordersRes.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const STATUS_STYLES = {
    pending:    "bg-gray-100 text-gray-700",
    processing: "bg-yellow-100 text-yellow-700",
    shipped:    "bg-blue-100 text-blue-700",
    delivered:  "bg-teal-100 text-teal-700",
    cancelled:  "bg-red-100 text-red-700",
  };

  const STAT_CARDS = [
    { label: "Total Orders",  value: summary?.total_orders  ?? "—", icon: "bi-box-seam",  color: "teal",   tab: "orders"   },
    { label: "Total Spent",   value: summary ? fmt(summary.total_spent) : "—", icon: "bi-wallet2", color: "violet", tab: null },
    { label: "Wishlist Items",value: summary?.wishlist_count ?? "—", icon: "bi-heart",    color: "pink",   tab: "wishlist" },
    { label: "My Reviews",    value: summary?.reviews_count ?? "—", icon: "bi-star",      color: "amber",  tab: "reviews"  },
  ];

  const COLOR_MAP = {
    teal:   "bg-teal-50 text-teal-600",
    violet: "bg-violet-50 text-violet-600",
    pink:   "bg-pink-50 text-pink-600",
    amber:  "bg-amber-50 text-amber-600",
  };

  return (
    <div className="space-y-8">
      {/* Welcome banner */}
      <div className="bg-gradient-to-r from-teal-600 to-teal-700 rounded-2xl p-6 text-white">
        <h2 className="text-2xl font-bold mb-1">
          Welcome back{user?.first_name ? `, ${user.first_name}` : ""}! 👋
        </h2>
        <p className="text-teal-100 text-sm">Here's a summary of your account activity.</p>
        {summary?.pending_orders > 0 && (
          <div className="mt-3 bg-white/20 rounded-xl px-4 py-2 text-sm inline-flex items-center gap-2">
            <i className="bi bi-clock"></i>
            <span>{summary.pending_orders} order{summary.pending_orders > 1 ? "s" : ""} in progress</span>
            <button onClick={() => onNavigate("orders")} className="underline ml-1 font-medium">View →</button>
          </div>
        )}
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STAT_CARDS.map((s) => (
          <div
            key={s.label}
            onClick={() => s.tab && onNavigate(s.tab)}
            className={`bg-white border border-gray-100 rounded-xl p-5 shadow-sm ${s.tab ? "cursor-pointer hover:shadow-md transition" : ""}`}
          >
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-3 ${COLOR_MAP[s.color]}`}>
              <i className={`bi ${s.icon} text-lg`}></i>
            </div>
            {loading
              ? <div className="h-7 bg-gray-100 rounded animate-pulse w-16" />
              : <div className="text-2xl font-bold text-gray-800">{s.value}</div>
            }
            <div className="text-xs text-gray-500 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Recent orders */}
      <div>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-bold text-gray-800">Recent Orders</h3>
          <button onClick={() => onNavigate("orders")} className="text-sm text-teal-600 hover:underline font-medium">
            View All →
          </button>
        </div>
        {loading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : recentOrders.length === 0 ? (
          <div className="bg-white border border-gray-100 rounded-xl p-8 text-center text-gray-400">
            <i className="bi bi-box-seam text-4xl mb-3 block"></i>
            <p>No orders yet.</p>
            <Link to="/product-lists" className="mt-3 inline-block text-sm text-teal-600 hover:underline">
              Start Shopping →
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {recentOrders.map((order) => (
              <div key={order.id} className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm flex flex-wrap justify-between items-center gap-3">
                <div>
                  <p className="font-semibold text-gray-800 text-sm">{order.order_number}</p>
                  <p className="text-xs text-gray-500">
                    {new Date(order.created_at).toLocaleDateString()}
                    {" · "}{order.items_count} item{order.items_count !== 1 ? "s" : ""}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs font-semibold px-3 py-1 rounded-full capitalize ${STATUS_STYLES[order.status]}`}>
                    {order.status}
                  </span>
                  <span className="font-bold text-gray-800 text-sm">{fmt(order.total)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick links */}
      <div className="grid sm:grid-cols-3 gap-4">
        {[
          { icon: "bi-geo-alt",  label: "Manage Addresses", tab: "addresses", href: null },
          { icon: "bi-gear",     label: "Account Settings", tab: "settings",  href: null },
          { icon: "bi-headset",  label: "Help Center",      tab: null,        href: "/contact" },
        ].map((l) =>
          l.href ? (
            <Link key={l.label} to={l.href}
              className="bg-white border border-gray-100 rounded-xl p-4 flex items-center gap-3 hover:shadow-md transition">
              <i className={`bi ${l.icon} text-teal-600 text-xl`}></i>
              <span className="text-sm font-semibold text-gray-700">{l.label}</span>
            </Link>
          ) : (
            <button key={l.label} onClick={() => onNavigate(l.tab)}
              className="bg-white border border-gray-100 rounded-xl p-4 flex items-center gap-3 hover:shadow-md transition text-left">
              <i className={`bi ${l.icon} text-teal-600 text-xl`}></i>
              <span className="text-sm font-semibold text-gray-700">{l.label}</span>
            </button>
          )
        )}
      </div>
    </div>
  );
};

// ─── Tab component map ─────────────────────────────────────────────────────
const TABS = {
  overview:  (p) => <OverviewTab onNavigate={p.onNavigate} />,
  orders:    ()  => <OrdersTab />,
  wishlist:  ()  => <WishlistTab />,
  reviews:   ()  => <ReviewsTab />,
  addresses: ()  => <AddressesTab />,
  settings:  ()  => <SettingsTab />,
  payments:  ()  => <PaymentMethodsTab />,
};

// ─── Page ──────────────────────────────────────────────────────────────────
const Account = () => {
  const { loading } = useAuth();

  // FIX: read initial tab from the ?tab= URL param so Header deep links like
  // /account?tab=orders land on the correct tab instead of always showing overview.
  const [searchParams, setSearchParams] = useSearchParams();

  const tabFromUrl = searchParams.get("tab");
  const initialTab = VALID_TABS.includes(tabFromUrl) ? tabFromUrl : "overview";
  const [activeTab, setActiveTab] = useState(initialTab);

  // Keep URL in sync when the user clicks a sidebar item
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (tab === "overview") {
      setSearchParams({});            // clean URL for the default tab
    } else {
      setSearchParams({ tab });       // /account?tab=orders etc.
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-10 h-10 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const TabContent = TABS[activeTab] ?? TABS.overview;

  return (
    <section className="py-10 bg-gray-50 min-h-screen">
      <div className="container mx-auto px-4 max-w-6xl">
        {/* Breadcrumb */}
        <nav className="text-sm text-gray-500 mb-6 flex items-center gap-2">
          <Link to="/" className="hover:text-teal-600">Home</Link>
          <i className="bi bi-chevron-right text-xs"></i>
          <span className="text-gray-800 capitalize">
            {activeTab === "overview" ? "My Account" : activeTab}
          </span>
        </nav>

        <div className="grid lg:grid-cols-[280px,1fr] gap-8 items-start">
          {/* Sidebar receives handleTabChange so it also updates the URL */}
          <AccountSidebar activeTab={activeTab} setActiveTab={handleTabChange} />

          <div className="bg-white rounded-2xl shadow-md p-8 min-h-[600px]">
            <TabContent onNavigate={handleTabChange} />
          </div>
        </div>
      </div>
    </section>
  );
};

export default Account;
