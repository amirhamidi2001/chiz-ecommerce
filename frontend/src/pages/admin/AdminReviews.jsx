import { useEffect, useState } from "react";
import { adminAPI } from "../../services/api";
import DataTable from "../../components/admin/DataTable";
import ConfirmModal from "../../components/admin/ConfirmModal";
import Toast, { useToast } from "../../components/admin/Toast";

// ── Review detail drawer ──────────────────────────────────────────────────────
const ReviewDrawer = ({ review, onClose, onDelete }) => {
  if (!review) return null;

  const Stars = ({ value }) => (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <i
          key={s}
          className={`bi ${s <= value ? "bi-star-fill text-yellow-400" : "bi-star text-gray-200"} text-base`}
        ></i>
      ))}
    </div>
  );

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-white w-full max-w-md h-full shadow-2xl overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex justify-between items-center px-6 py-5 border-b sticky top-0 bg-white z-10">
          <h3 className="text-lg font-bold text-gray-800">Review Detail</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100 transition">
            <i className="bi bi-x-lg text-xl"></i>
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Product */}
          <div className="bg-gray-50 rounded-xl p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Product</p>
            <p className="font-semibold text-gray-800">{review.product_name}</p>
            <p className="text-xs text-gray-400 mt-0.5">ID #{review.product_id}</p>
          </div>

          {/* Reviewer */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Reviewer</p>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-teal-100 flex items-center justify-center">
                <span className="text-teal-700 font-bold">{review.name?.[0]?.toUpperCase()}</span>
              </div>
              <div>
                <p className="font-semibold text-gray-800">{review.name}</p>
                <p className="text-xs text-gray-500">
                  {new Date(review.created_at).toLocaleDateString("en-US", {
                    year: "numeric", month: "long", day: "numeric",
                  })}
                </p>
              </div>
            </div>
          </div>

          {/* Rating */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Rating</p>
            <div className="flex items-center gap-2">
              <Stars value={review.rating} />
              <span className="text-lg font-bold text-gray-800">{review.rating}</span>
              <span className="text-sm text-gray-400">/ 5</span>
            </div>
          </div>

          {/* Headline */}
          {review.headline && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Headline</p>
              <p className="font-semibold text-gray-800">{review.headline}</p>
            </div>
          )}

          {/* Comment */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Comment</p>
            <div className="bg-gray-50 rounded-xl p-4 text-sm text-gray-700 leading-relaxed border-l-4 border-teal-200">
              {review.comment}
            </div>
          </div>

          {/* Actions */}
          <div className="pt-2 border-t border-gray-100">
            <button
              onClick={() => onDelete(review)}
              className="w-full py-2.5 bg-red-50 text-red-600 border border-red-200 rounded-xl text-sm font-semibold hover:bg-red-100 transition flex items-center justify-center gap-2"
            >
              <i className="bi bi-trash"></i>
              Delete This Review
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────
const AdminReviews = () => {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("-created_at");
  const [ratingFilter, setRatingFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const { toast, show, dismiss } = useToast();

  const fetchReviews = () => {
    setLoading(true);
    adminAPI
      .getReviews({
        page,
        search,
        ordering: sort,
        page_size: 12,
        ...(ratingFilter ? { rating: ratingFilter } : {}),
      })
      .then(({ data }) => {
        setReviews(data.results ?? data);
        setTotal(data.count ?? 0);
      })
      .catch(() => show("Failed to load reviews", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchReviews(); }, [page, search, sort, ratingFilter]);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await adminAPI.deleteReview(confirm.id);
      show("Review deleted");
      setConfirm(null);
      setSelected(null);
      fetchReviews();
    } catch {
      show("Failed to delete review", "error");
    } finally {
      setDeleting(false);
    }
  };

  const StarBadge = ({ value }) => {
    const color =
      value >= 4 ? "bg-green-100 text-green-700"
        : value === 3 ? "bg-yellow-100 text-yellow-700"
          : "bg-red-100 text-red-700";
    return (
      <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${color}`}>
        <i className="bi bi-star-fill text-[10px]"></i>
        {value}
      </span>
    );
  };

  const COLUMNS = [
    {
      key: "product_name",
      label: "Product",
      sortable: false,
      render: (v) => (
        <span className="font-medium text-gray-800 text-sm max-w-[180px] truncate block">{v}</span>
      ),
    },
    {
      key: "name",
      label: "Reviewer",
      render: (v) => (
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-teal-100 flex items-center justify-center flex-shrink-0">
            <span className="text-teal-700 text-xs font-bold">{v?.[0]?.toUpperCase()}</span>
          </div>
          <span className="text-sm text-gray-700">{v}</span>
        </div>
      ),
    },
    {
      key: "rating",
      label: "Rating",
      sortable: true,
      render: (v) => <StarBadge value={v} />,
    },
    {
      key: "headline",
      label: "Headline",
      render: (v, row) => (
        <div>
          {v && <p className="text-sm font-medium text-gray-800 truncate max-w-[200px]">{v}</p>}
          <p className="text-xs text-gray-500 truncate max-w-[200px]">{row.comment}</p>
        </div>
      ),
    },
    {
      key: "created_at",
      label: "Date",
      sortable: true,
      render: (v) => (
        <span className="text-xs text-gray-500">
          {new Date(v).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <Toast toast={toast} onDismiss={dismiss} />

      {confirm && (
        <ConfirmModal
          isOpen
          title="Delete Review"
          message={`Permanently delete this review by "${confirm.name}"? This cannot be undone.`}
          confirmLabel="Delete"
          onConfirm={handleDelete}
          onClose={() => setConfirm(null)}
          loading={deleting}
        />
      )}

      {selected && (
        <ReviewDrawer
          review={selected}
          onClose={() => setSelected(null)}
          onDelete={(r) => { setSelected(null); setConfirm(r); }}
        />
      )}

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Reviews</h1>
        <p className="text-sm text-gray-500">{total} total reviews</p>
      </div>

      <DataTable
        columns={COLUMNS}
        data={reviews}
        loading={loading}
        totalCount={total}
        page={page}
        pageSize={12}
        onPageChange={setPage}
        sort={sort}
        onSort={setSort}
        search={search}
        onSearch={(v) => { setSearch(v); setPage(1); }}
        searchPlaceholder="Search by reviewer, product…"
        emptyIcon="bi-star"
        emptyText="No reviews found"
        filters={
          <select
            value={ratingFilter}
            onChange={(e) => { setRatingFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-200 rounded-lg bg-white text-sm focus:outline-none"
          >
            <option value="">All Ratings</option>
            {[5, 4, 3, 2, 1].map((r) => (
              <option key={r} value={r}>{r} Star{r !== 1 ? "s" : ""}</option>
            ))}
          </select>
        }
        rowActions={(row) => (
          <>
            <button
              onClick={() => setSelected(row)}
              title="View"
              className="px-2.5 py-1.5 bg-teal-600 text-white rounded-lg text-xs border border-teal-600 hover:bg-teal-700 transition"
            >
              <i className="bi bi-eye"></i>
            </button>
            <button
              onClick={() => setConfirm(row)}
              title="Delete"
              className="px-2.5 py-1.5 border border-red-200 text-red-600 rounded-lg text-xs hover:bg-red-50 transition"
            >
              <i className="bi bi-trash"></i>
            </button>
          </>
        )}
      />
    </div>
  );
};

export default AdminReviews;
