import { useEffect, useState } from "react";
import { adminAPI } from "../../services/api";
import DataTable from "../../components/admin/DataTable";
import Toast, { useToast } from "../../components/admin/Toast";

const USER_TYPES = { 1: "Customer", 2: "Admin", 3: "Superuser" };

const AdminUsers = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("-created_date");
  const [activeFilter, setActiveFilter] = useState("");
  const [updating, setUpdating] = useState(null);
  const { toast, show, dismiss } = useToast();

  const fetchUsers = () => {
    setLoading(true);
    adminAPI.getUsers({
      page, search, ordering: sort, page_size: 10,
      is_active: activeFilter !== "" ? activeFilter : undefined,
    })
      .then(({ data }) => { setUsers(data.results ?? data); setTotal(data.count ?? 0); })
      .catch(() => show("Failed to load users", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchUsers(); }, [page, search, sort, activeFilter]);

  const toggleActive = async (user) => {
    setUpdating(user.id);
    try {
      await adminAPI.updateUser(user.id, { is_active: !user.is_active });
      setUsers((prev) =>
        prev.map((u) => (u.id === user.id ? { ...u, is_active: !u.is_active } : u))
      );
      show(`User ${user.is_active ? "deactivated" : "activated"}`);
    } catch {
      show("Failed to update user", "error");
    } finally {
      setUpdating(null);
    }
  };

  const changeRole = async (user, type) => {
    setUpdating(user.id);
    try {
      await adminAPI.updateUser(user.id, { type: parseInt(type) });
      setUsers((prev) =>
        prev.map((u) => (u.id === user.id ? { ...u, type: parseInt(type) } : u))
      );
      show("Role updated");
    } catch {
      show("Failed to update role", "error");
    } finally {
      setUpdating(null);
    }
  };

  const fmt = (n) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);

  const COLUMNS = [
    {
      key: "avatar_url", label: "",
      render: (v, row) => (
        <div className="w-9 h-9 rounded-full bg-teal-100 flex items-center justify-center overflow-hidden flex-shrink-0">
          {v
            ? <img src={v} alt="" className="w-full h-full object-cover" />
            : <span className="text-teal-700 font-bold text-sm">{row.email?.[0]?.toUpperCase()}</span>
          }
        </div>
      ),
    },
    {
      key: "email", label: "User", sortable: true,
      render: (v, row) => (
        <div>
          <p className="font-semibold text-gray-800 text-sm">{row.full_name || v}</p>
          <p className="text-xs text-gray-500">{v}</p>
        </div>
      ),
    },
    {
      key: "type", label: "Role",
      render: (v, row) => (
        <select
          value={v}
          onChange={(e) => changeRole(row, e.target.value)}
          disabled={updating === row.id}
          className="px-2 py-1 border border-gray-200 rounded-lg text-xs bg-white focus:outline-none disabled:opacity-50"
          onClick={(e) => e.stopPropagation()}
        >
          {Object.entries(USER_TYPES).map(([k, label]) => (
            <option key={k} value={k}>{label}</option>
          ))}
        </select>
      ),
    },
    {
      key: "is_active", label: "Status",
      render: (v) => (
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${v ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
          {v ? "Active" : "Inactive"}
        </span>
      ),
    },
    {
      key: "is_verified", label: "Verified",
      render: (v) => (
        <i className={`bi ${v ? "bi-shield-check text-teal-600" : "bi-shield-x text-gray-300"} text-lg`}></i>
      ),
    },
    {
      key: "total_orders", label: "Orders", sortable: false,
      render: (v) => <span className="text-sm text-gray-700">{v}</span>,
    },
    {
      key: "total_spent", label: "Spent",
      render: (v) => <span className="text-sm font-medium text-gray-800">{fmt(v)}</span>,
    },
    {
      key: "created_date", label: "Joined", sortable: true,
      render: (v) => <span className="text-xs text-gray-500">{new Date(v).toLocaleDateString()}</span>,
    },
  ];

  return (
    <div className="space-y-5">
      <Toast toast={toast} onDismiss={dismiss} />
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Users</h1>
        <p className="text-sm text-gray-500">{total} registered users</p>
      </div>

      <DataTable
        columns={COLUMNS}
        data={users}
        loading={loading}
        totalCount={total}
        page={page}
        pageSize={10}
        onPageChange={setPage}
        sort={sort}
        onSort={setSort}
        search={search}
        onSearch={(v) => { setSearch(v); setPage(1); }}
        searchPlaceholder="Search by name or email…"
        emptyIcon="bi-people"
        emptyText="No users found"
        filters={
          <select value={activeFilter} onChange={(e) => { setActiveFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-200 rounded-lg bg-white text-sm focus:outline-none">
            <option value="">All Users</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        }
        rowActions={(row) => (
          <button
            onClick={() => toggleActive(row)}
            disabled={updating === row.id}
            title={row.is_active ? "Deactivate" : "Activate"}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition disabled:opacity-50 ${row.is_active
                ? "border-red-200 text-red-600 hover:bg-red-50"
                : "border-green-200 text-green-600 hover:bg-green-50"
              }`}
          >
            {updating === row.id
              ? <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
              : row.is_active ? "Deactivate" : "Activate"
            }
          </button>
        )}
      />
    </div>
  );
};

export default AdminUsers;
