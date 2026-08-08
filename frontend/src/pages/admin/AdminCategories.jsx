import { useEffect, useRef, useState } from "react";
import { adminAPI } from "../../services/api";
import DataTable from "../../components/admin/DataTable";
import ConfirmModal from "../../components/admin/ConfirmModal";
import Toast, { useToast } from "../../components/admin/Toast";

const CategoryModal = ({ category, allCategories, onClose, onSaved }) => {
  const [form, setForm] = useState({ name: category?.name || "", parent: category?.parent || "" });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [imgFile, setImgFile] = useState(null);
  const [imgPreview, setImgPreview] = useState(category?.image_url || null);
  const imgRef = useRef(null);

  const handleFile = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setImgFile(f);
    setImgPreview(URL.createObjectURL(f));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { setErrors({ name: "Required" }); return; }
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append("name", form.name);
      if (form.parent) fd.append("parent", form.parent);
      if (imgFile) fd.append("image", imgFile);
      if (category) await adminAPI.updateCategory(category.id, fd);
      else await adminAPI.createCategory(fd);
      onSaved();
      onClose();
    } catch (err) {
      setErrors(err?.response?.data || {});
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center p-6 border-b">
          <h3 className="text-lg font-bold">{category ? "Edit Category" : "Add Category"}</h3>
          <button onClick={onClose}><i className="bi bi-x-lg text-xl text-gray-400"></i></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Name</label>
            <input value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500 ${errors.name ? "border-red-400" : "border-gray-200"}`} />
            {errors.name && <p className="text-red-500 text-xs mt-0.5">{errors.name}</p>}
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Parent Category (optional)</label>
            <select value={form.parent} onChange={(e) => setForm((p) => ({ ...p, parent: e.target.value }))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500">
              <option value="">None (top-level)</option>
              {allCategories.filter(c => c.id !== category?.id).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-2">Image (optional)</label>
            <div className="flex items-center gap-3">
              {imgPreview && <img src={imgPreview} alt="" className="w-14 h-14 object-cover rounded-xl border" />}
              <button type="button" onClick={() => imgRef.current?.click()}
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50 transition">
                <i className="bi bi-upload mr-1.5"></i>Upload
              </button>
              <input ref={imgRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-sm hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={saving}
              className="flex-1 py-2.5 bg-teal-600 text-white rounded-xl text-sm font-semibold hover:bg-teal-700 disabled:opacity-60">
              {saving ? "Saving…" : category ? "Save" : "Add Category"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const AdminCategories = () => {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [modal, setModal] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const { toast, show, dismiss } = useToast();

  const fetchCategories = () => {
    setLoading(true);
    adminAPI.getCategories({ page, search, page_size: 15 })
      .then(({ data }) => { setCategories(data.results ?? data); setTotal(data.count ?? 0); })
      .catch(() => show("Failed to load categories", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchCategories(); }, [page, search]);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await adminAPI.deleteCategory(confirm.id);
      show("Category deleted");
      setConfirm(null);
      fetchCategories();
    } catch {
      show("Failed to delete. It may have linked products.", "error");
    } finally {
      setDeleting(false);
    }
  };

  const COLUMNS = [
    {
      key: "image_url", label: "Image",
      render: (v) => v
        ? <img src={v} alt="" className="w-10 h-10 object-cover rounded-lg border" />
        : <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center"><i className="bi bi-tag text-gray-400"></i></div>,
    },
    {
      key: "name", label: "Name", sortable: true,
      render: (v) => <span className="font-semibold text-gray-800">{v}</span>
    },
    {
      key: "parent_name", label: "Parent",
      render: (v) => <span className="text-sm text-gray-500">{v || "—"}</span>
    },
    {
      key: "product_count", label: "Products",
      render: (v) => <span className="bg-gray-100 text-gray-700 text-xs px-2 py-0.5 rounded-full font-medium">{v}</span>
    },
    {
      key: "created_at", label: "Created", sortable: true,
      render: (v) => <span className="text-xs text-gray-500">{new Date(v).toLocaleDateString()}</span>
    },
  ];

  return (
    <div className="space-y-5">
      <Toast toast={toast} onDismiss={dismiss} />
      {confirm && <ConfirmModal isOpen title="Delete Category" message={`Delete "${confirm.name}"?`}
        confirmLabel="Delete" onConfirm={handleDelete} onClose={() => setConfirm(null)} loading={deleting} />}
      {modal && <CategoryModal category={modal === "new" ? null : modal} allCategories={categories}
        onClose={() => setModal(null)} onSaved={() => { fetchCategories(); show("Category saved"); }} />}

      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-800">Categories</h1>
        <button onClick={() => setModal("new")}
          className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-xl hover:bg-teal-700 transition text-sm font-semibold">
          <i className="bi bi-plus-lg"></i> Add Category
        </button>
      </div>

      <DataTable columns={COLUMNS} data={categories} loading={loading} totalCount={total}
        page={page} pageSize={15} onPageChange={setPage}
        search={search} onSearch={(v) => { setSearch(v); setPage(1); }}
        searchPlaceholder="Search categories…"
        emptyIcon="bi-tag" emptyText="No categories found"
        rowActions={(row) => (
          <>
            <button onClick={() => setModal(row)} title="Edit"
              className="px-2.5 py-1.5 bg-teal-600 text-white rounded-lg text-xs border border-teal-600 hover:bg-teal-700 transition">
              <i className="bi bi-pencil"></i>
            </button>
            <button onClick={() => setConfirm(row)} title="Delete"
              className="px-2.5 py-1.5 border border-red-200 text-red-600 rounded-lg text-xs hover:bg-red-50 transition">
              <i className="bi bi-trash"></i>
            </button>
          </>
        )}
      />
    </div>
  );
};

export default AdminCategories;
