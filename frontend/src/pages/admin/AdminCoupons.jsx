import { useEffect, useState } from "react";
import { adminAPI } from "../../services/api";
import DataTable from "../../components/admin/DataTable";
import CouponModal from "../../components/admin/CouponModal";
import Toast, { useToast } from "../../components/admin/Toast";
import { couponStatus, formatCouponValue } from "../../utils/coupon";

const STATUS_STYLES = {
  Active: "bg-green-100 text-green-700",
  Inactive: "bg-gray-100 text-gray-600",
  Scheduled: "bg-blue-100 text-blue-700",
  Expired: "bg-amber-100 text-amber-700",
};

const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

const scopeLabel = (c) => {
  const cats = c.categories?.length ?? 0;
  const prods = c.products?.length ?? 0;
  if (!cats && !prods) return "Whole cart";
  const parts = [];
  if (cats) parts.push(`${cats} categor${cats === 1 ? "y" : "ies"}`);
  if (prods) parts.push(`${prods} product${prods === 1 ? "" : "s"}`);
  return parts.join(" + ");
};

const ActionBtn = ({ icon, label, onClick, variant = "default", disabled }) => (
  <button
    onClick={onClick}
    title={label}
    aria-label={label}
    disabled={disabled}
    className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border transition disabled:opacity-50 ${
      variant === "warning"
        ? "border-amber-200 text-amber-700 hover:bg-amber-50"
        : variant === "primary"
          ? "bg-teal-600 text-white border-teal-600 hover:bg-teal-700"
          : "border-gray-200 text-gray-600 hover:bg-gray-50"
    }`}
  >
    <i className={`bi ${icon}`}></i>
  </button>
);

// ── Main page ─────────────────────────────────────────────────────────────────
const AdminCoupons = () => {
  const [coupons, setCoupons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("-created_at");
  const [modal, setModal] = useState(null); // null | "new" | coupon-object
  const [togglingId, setTogglingId] = useState(null);
  const { toast, show, dismiss } = useToast();

  const fetchCoupons = () => {
    setLoading(true);
    adminAPI
      .getCoupons({ page, search, ordering: sort, page_size: 15 })
      .then(({ data }) => {
        setCoupons(data.results ?? data);
        setTotal(data.count ?? data.results?.length ?? data.length);
      })
      .catch(() => show("Failed to load coupons", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCoupons();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, search, sort]);

  // Quick on/off switch for fast campaign shutoff — a single PATCH, no form.
  const handleToggleActive = async (coupon) => {
    const next = !coupon.is_active;
    setTogglingId(coupon.id);
    try {
      await adminAPI.updateCoupon(coupon.id, { is_active: next });
      show(next ? `${coupon.code} activated` : `${coupon.code} deactivated`);
      fetchCoupons();
    } catch {
      show("Failed to update coupon", "error");
    } finally {
      setTogglingId(null);
    }
  };

  const COLUMNS = [
    {
      key: "code",
      label: "Code",
      render: (v) => (
        <code className="text-xs bg-gray-100 px-2 py-0.5 rounded font-semibold text-gray-700">
          {v}
        </code>
      ),
    },
    {
      key: "discount_type",
      label: "Discount",
      render: (_, row) => (
        <span className="font-semibold text-gray-800">{formatCouponValue(row)}</span>
      ),
    },
    {
      key: "scope",
      label: "Applies to",
      render: (_, row) => <span className="text-gray-600">{scopeLabel(row)}</span>,
    },
    {
      key: "valid_from",
      label: "Valid from",
      sortable: true,
      render: (v) => <span className="text-gray-600 whitespace-nowrap">{fmtDate(v)}</span>,
    },
    {
      key: "valid_until",
      label: "Valid until",
      sortable: true,
      render: (v) => <span className="text-gray-600 whitespace-nowrap">{fmtDate(v)}</span>,
    },
    {
      key: "is_active",
      label: "Status",
      render: (_, row) => {
        const status = couponStatus(row);
        return (
          <span
            className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${STATUS_STYLES[status]}`}
          >
            {status}
          </span>
        );
      },
    },
  ];

  return (
    <div className="space-y-5">
      <Toast toast={toast} onDismiss={dismiss} />

      {modal && (
        <CouponModal
          coupon={modal === "new" ? null : modal}
          onClose={() => setModal(null)}
          onSaved={() => {
            fetchCoupons();
            show("Coupon saved successfully");
          }}
        />
      )}

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Coupons</h1>
          <p className="text-sm text-gray-500">{total} total coupons</p>
        </div>
        <button
          onClick={() => setModal("new")}
          className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-xl hover:bg-teal-700 transition text-sm font-semibold"
        >
          <i className="bi bi-plus-lg"></i> Add Coupon
        </button>
      </div>

      <DataTable
        columns={COLUMNS}
        data={coupons}
        loading={loading}
        totalCount={total}
        page={page}
        pageSize={15}
        onPageChange={setPage}
        sort={sort}
        onSort={setSort}
        search={search}
        onSearch={(v) => {
          setSearch(v);
          setPage(1);
        }}
        searchPlaceholder="Search coupon codes…"
        emptyIcon="bi-ticket-perforated"
        emptyText="No coupons found"
        rowActions={(row) => (
          <>
            <ActionBtn
              icon="bi-pencil"
              label="Edit"
              onClick={() => setModal(row)}
              variant="primary"
            />
            <ActionBtn
              icon={row.is_active ? "bi-pause-circle" : "bi-play-circle"}
              label={row.is_active ? "Deactivate" : "Activate"}
              onClick={() => handleToggleActive(row)}
              variant={row.is_active ? "warning" : "default"}
              disabled={togglingId === row.id}
            />
          </>
        )}
      />
    </div>
  );
};

export default AdminCoupons;
