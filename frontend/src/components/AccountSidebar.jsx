import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { dashboardAPI } from "../services/api";
import { useAuth } from "../context/AuthContext";

const MENU = [
  { id: "overview", label: "Overview", icon: "bi-grid" },
  { id: "orders", label: "My Orders", icon: "bi-box-seam" },
  { id: "wishlist", label: "Wishlist", icon: "bi-heart" },
  { id: "reviews", label: "My Reviews", icon: "bi-star" },
  { id: "addresses", label: "Addresses", icon: "bi-geo-alt" },
  { id: "settings", label: "Account Settings", icon: "bi-gear" },
];

const AccountSidebar = ({ activeTab, setActiveTab }) => {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    Promise.all([dashboardAPI.getProfile(), dashboardAPI.getSummary()])
      .then(([profileRes, summaryRes]) => {
        setProfile(profileRes.data);
        setSummary(summaryRes.data);
      })
      .catch(() => { });
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const badgeMap = {
    orders: summary?.total_orders,
    wishlist: summary?.wishlist_count,
    reviews: summary?.reviews_count,
  };

  return (
    <div className="bg-white rounded-2xl shadow-md p-6 sticky top-24">
      {/* ── Avatar & name ────────────────────────────────────────────────── */}
      <div className="text-center pb-6 mb-6 border-b border-gray-100">
        <div className="relative w-24 h-24 mx-auto mb-4">
          <img
            src={
              profile?.avatar_url ||
              "/assets/img/person/person-f-1.webp"
            }
            alt="Profile"
            className="w-full h-full rounded-full object-cover border-4 border-white shadow-md"
          />
          {profile?.is_verified && (
            <span className="absolute bottom-0 right-0 bg-teal-600 text-white rounded-full w-8 h-8 flex items-center justify-center border-4 border-white">
              <i className="bi bi-shield-check text-xs"></i>
            </span>
          )}
        </div>
        {profile ? (
          <>
            <h4 className="font-semibold text-gray-800">
              {profile.first_name} {profile.last_name}
            </h4>
            <p className="text-xs text-gray-500 truncate mt-0.5">{profile.email}</p>
          </>
        ) : (
          <div className="h-5 bg-gray-100 rounded w-32 mx-auto animate-pulse" />
        )}
        <div className="inline-flex items-center gap-1 bg-teal-50 text-teal-700 text-xs px-3 py-1 rounded-full mt-2">
          <i className="bi bi-award"></i>
          <span>{profile?.user_type >= 2 ? "Admin" : "Member"}</span>
        </div>
      </div>

      {/* ── Summary chips ─────────────────────────────────────────────────── */}
      {summary && (
        <div className="grid grid-cols-3 gap-2 mb-6 text-center">
          <div className="bg-gray-50 rounded-xl p-2">
            <div className="text-lg font-bold text-gray-800">{summary.total_orders}</div>
            <div className="text-xs text-gray-500">Orders</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-2">
            <div className="text-lg font-bold text-gray-800">{summary.wishlist_count}</div>
            <div className="text-xs text-gray-500">Wishlist</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-2">
            <div className="text-lg font-bold text-gray-800">{summary.reviews_count}</div>
            <div className="text-xs text-gray-500">Reviews</div>
          </div>
        </div>
      )}

      {/* ── Navigation ───────────────────────────────────────────────────── */}
      <nav className="space-y-1">
        {MENU.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            className={`w-full flex items-center justify-between px-4 py-3 rounded-xl transition ${activeTab === item.id
              ? "bg-teal-600 text-white"
              : "text-gray-700 hover:bg-teal-50"
              }`}
          >
            <div className="flex items-center gap-3">
              <i className={`${item.icon} text-lg`}></i>
              <span className="text-sm font-medium">{item.label}</span>
            </div>
            {badgeMap[item.id] !== undefined && badgeMap[item.id] > 0 && (
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-semibold ${activeTab === item.id
                  ? "bg-white text-teal-600"
                  : "bg-gray-100 text-gray-600"
                  }`}
              >
                {badgeMap[item.id]}
              </span>
            )}
          </button>
        ))}
      </nav>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <div className="mt-8 pt-6 border-t border-gray-100 space-y-1">
        <Link
          to="/support"
          className="flex items-center gap-3 px-4 py-2 text-gray-600 hover:text-teal-600 rounded-xl transition text-sm"
        >
          <i className="bi bi-question-circle"></i>
          <span>Help Center</span>
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-2 text-red-600 hover:bg-red-50 rounded-xl transition text-sm"
        >
          <i className="bi bi-box-arrow-right"></i>
          <span>Log Out</span>
        </button>
      </div>
    </div>
  );
};

export default AccountSidebar;
