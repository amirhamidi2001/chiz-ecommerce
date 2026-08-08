import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

const NAV = [
  { label: "Overview", to: "/admin", icon: "bi-grid", exact: true },
  { label: "Analytics", to: "/admin/analytics", icon: "bi-bar-chart-line" },
  { label: "Orders", to: "/admin/orders", icon: "bi-box-seam" },
  { label: "Products", to: "/admin/products", icon: "bi-bag" },
  { label: "Categories", to: "/admin/categories", icon: "bi-tag" },
  { label: "Brands", to: "/admin/brands", icon: "bi-award" },
  { label: "Users", to: "/admin/users", icon: "bi-people" },
  { label: "Reviews", to: "/admin/reviews", icon: "bi-star" },
  { label: "Chats", to: "/admin/chat", icon: "bi-chat" },
  { label: "Blog", to: "/admin/blog", icon: "bi-journal-text" },
  { label: "Messages", to: "/admin/messages", icon: "bi-envelope" },
];

const AdminLayout = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className={`flex items-center gap-3 px-5 py-6 border-b border-slate-700 ${collapsed ? "justify-center" : ""}`}>
        <div className="w-8 h-8 bg-teal-500 rounded-lg flex items-center justify-center flex-shrink-0">
          <i className="bi bi-shop-window text-white text-base"></i>
        </div>
        {!collapsed && (
          <span className="font-bold text-white text-lg tracking-tight">Admin Panel</span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV.map(({ label, to, icon, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl transition text-sm font-medium ${isActive
                ? "bg-teal-600 text-white"
                : "text-slate-300 hover:bg-slate-700 hover:text-white"
              } ${collapsed ? "justify-center" : ""}`
            }
            title={collapsed ? label : undefined}
            onClick={() => setMobileOpen(false)}
          >
            <i className={`bi ${icon} text-base flex-shrink-0`}></i>
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* User footer */}
      <div className={`border-t border-slate-700 p-4 ${collapsed ? "flex justify-center" : ""}`}>
        {collapsed ? (
          <button onClick={handleLogout} className="text-slate-400 hover:text-red-400 transition p-2 rounded-lg hover:bg-slate-700">
            <i className="bi bi-box-arrow-right text-lg"></i>
          </button>
        ) : (
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-teal-600 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
              {user?.email?.[0]?.toUpperCase() || "A"}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white truncate">
                {user?.email || "Admin"}
              </p>
              <p className="text-xs text-slate-400">Administrator</p>
            </div>
            <button onClick={handleLogout} title="Log out"
              className="text-slate-400 hover:text-red-400 transition p-1.5 rounded-lg hover:bg-slate-700">
              <i className="bi bi-box-arrow-right"></i>
            </button>
          </div>
        )}
      </div>
    </>
  );

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      {/* ── Desktop sidebar ─────────────────────────────────────────────── */}
      <aside
        className={`hidden lg:flex flex-col bg-slate-800 transition-all duration-300 flex-shrink-0 ${collapsed ? "w-16" : "w-60"
          }`}
      >
        <SidebarContent />
      </aside>

      {/* ── Mobile sidebar overlay ──────────────────────────────────────── */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <aside className="relative z-50 flex flex-col bg-slate-800 w-64 h-full shadow-2xl">
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* ── Main content ────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Topbar */}
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between gap-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              className="p-1.5 rounded-lg hover:bg-gray-100 transition"
              onClick={() => {
                if (window.innerWidth >= 1024) setCollapsed((c) => !c);
                else setMobileOpen((v) => !v);
              }}
            >
              <i className="bi bi-list text-xl text-gray-600"></i>
            </button>
            <Link to="/" className="text-sm text-teal-600 hover:underline hidden sm:inline">
              ← Back to Store
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500 hidden sm:block">{user?.email}</span>
            <div className="w-8 h-8 rounded-full bg-teal-600 flex items-center justify-center text-white text-sm font-bold">
              {user?.email?.[0]?.toUpperCase() || "A"}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;
