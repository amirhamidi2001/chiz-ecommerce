import { useEffect, useState } from "react";
import { dashboardAPI } from "../services/api";

const ReviewsTab = () => {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState({ rating: 5, headline: "", comment: "" });
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [toast, setToast] = useState(null);
  const [sort, setSort] = useState("-created_at");

  const showToast = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const fetchReviews = (ordering = sort) => {
    setLoading(true);
    dashboardAPI
      .getReviews({ ordering })
      .then(({ data }) => setReviews(data.results ?? data))
      .catch(() => { })
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchReviews(); }, [sort]);

  const openEdit = (review) => {
    setEditing(review.id);
    setEditForm({
      rating: review.rating,
      headline: review.headline || "",
      comment: review.comment,
    });
  };

  const handleSave = async (id) => {
    setSaving(true);
    try {
      const { data } = await dashboardAPI.updateReview(id, editForm);
      setReviews((prev) =>
        prev.map((r) => (r.id === id ? { ...r, ...data } : r))
      );
      setEditing(null);
      showToast("Review updated");
    } catch {
      showToast("Failed to update review", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this review? This cannot be undone.")) return;
    setDeleting(id);
    try {
      await dashboardAPI.deleteReview(id);
      setReviews((prev) => prev.filter((r) => r.id !== id));
      showToast("Review deleted");
    } catch {
      showToast("Failed to delete review", "error");
    } finally {
      setDeleting(null);
    }
  };

  const Stars = ({ value, onChange }) => (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => onChange && onChange(s)}
          className={`text-lg ${s <= value ? "text-yellow-400" : "text-gray-300"} ${onChange ? "hover:scale-110 transition" : ""}`}
        >
          <i className="bi bi-star-fill"></i>
        </button>
      ))}
    </div>
  );

  return (
    <div>
      {toast && (
        <div className={`fixed top-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg text-sm font-medium text-white ${toast.type === "error" ? "bg-red-500" : "bg-teal-600"}`}>
          {toast.msg}
        </div>
      )}

      <div className="flex flex-wrap justify-between items-center mb-6 gap-3">
        <h2 className="text-2xl font-bold text-gray-800">My Reviews</h2>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="px-3 py-2 border border-gray-200 rounded-lg bg-white text-sm"
        >
          <option value="-created_at">Newest First</option>
          <option value="created_at">Oldest First</option>
          <option value="-rating">Highest Rating</option>
          <option value="rating">Lowest Rating</option>
        </select>
      </div>

      {loading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-32 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : reviews.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <i className="bi bi-star text-5xl mb-4 block"></i>
          <p className="text-lg font-medium">No reviews yet</p>
          <p className="text-sm mt-1">Your product reviews will appear here.</p>
        </div>
      ) : (
        <div className="space-y-5">
          {reviews.map((review) => (
            <div
              key={review.id}
              className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm"
            >
              {editing === review.id ? (
                // ── Edit form ─────────────────────────────────────────────
                <div className="space-y-3">
                  <div>
                    <label className="text-xs font-semibold text-gray-600 block mb-1">Rating</label>
                    <Stars value={editForm.rating} onChange={(v) => setEditForm((p) => ({ ...p, rating: v }))} />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-gray-600 block mb-1">Headline</label>
                    <input
                      type="text"
                      value={editForm.headline}
                      onChange={(e) => setEditForm((p) => ({ ...p, headline: e.target.value }))}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500"
                      placeholder="Short summary…"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-gray-600 block mb-1">Comment</label>
                    <textarea
                      rows={4}
                      value={editForm.comment}
                      onChange={(e) => setEditForm((p) => ({ ...p, comment: e.target.value }))}
                      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500 resize-none"
                    />
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={() => setEditing(null)}
                      className="px-4 py-2 border border-gray-200 text-gray-700 rounded-lg text-sm hover:bg-gray-50 transition"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleSave(review.id)}
                      disabled={saving}
                      className="px-4 py-2 bg-teal-600 text-white rounded-lg text-sm hover:bg-teal-700 transition disabled:opacity-60"
                    >
                      {saving ? "Saving…" : "Save Review"}
                    </button>
                  </div>
                </div>
              ) : (
                // ── View mode ─────────────────────────────────────────────
                <div className="flex gap-4">
                  <img
                    src={review.product_thumbnail || "/assets/img/product/product-1.webp"}
                    alt={review.product_name}
                    className="w-20 h-20 object-cover rounded-xl border flex-shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold text-gray-800 truncate">
                      {review.product_name}
                    </h4>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <Stars value={review.rating} />
                      <span className="text-xs text-gray-400">
                        {new Date(review.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    {review.headline && (
                      <p className="text-sm font-medium text-gray-700 mt-2">
                        {review.headline}
                      </p>
                    )}
                    <p className="text-sm text-gray-600 mt-1 line-clamp-3">
                      {review.comment}
                    </p>
                    <div className="flex gap-3 mt-3">
                      <button
                        onClick={() => openEdit(review)}
                        className="text-xs text-teal-600 hover:bg-teal-50 px-3 py-1.5 rounded-lg transition border border-teal-100"
                      >
                        <i className="bi bi-pencil mr-1"></i>Edit
                      </button>
                      <button
                        onClick={() => handleDelete(review.id)}
                        disabled={deleting === review.id}
                        className="text-xs text-red-600 hover:bg-red-50 px-3 py-1.5 rounded-lg transition border border-red-100"
                      >
                        {deleting === review.id ? (
                          <div className="w-3 h-3 border-2 border-red-400 border-t-transparent rounded-full animate-spin inline-block" />
                        ) : (
                          <><i className="bi bi-trash mr-1"></i>Delete</>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ReviewsTab;
