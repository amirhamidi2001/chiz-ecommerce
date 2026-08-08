import { useEffect, useRef, useState } from "react";
import { adminAPI } from "../../services/api";
import DataTable from "../../components/admin/DataTable";
import ConfirmModal from "../../components/admin/ConfirmModal";
import Toast, { useToast } from "../../components/admin/Toast";

const fmt = (n) => `$${parseFloat(n || 0).toFixed(2)}`;

// ── Standalone Field Component (Moved Outside to Prevent Focus Loss) ──────────
const Field = ({ name, label, form, handleChange, errors, type = "text", textarea }) => (
  <div className={textarea ? "col-span-2" : ""}>
    <label className="block text-xs font-semibold text-gray-600 mb-1">{label}</label>
    {textarea ? (
      <textarea name={name} value={form[name]} onChange={handleChange} rows={3}
        className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500 resize-none ${errors[name] ? "border-red-400" : "border-gray-200"}`} />
    ) : (
      <input type={type} name={name} value={form[name]} onChange={handleChange}
        className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500 ${errors[name] ? "border-red-400" : "border-gray-200"}`} />
    )}
    {errors[name] && <p className="text-red-500 text-xs mt-0.5">{errors[name]}</p>}
  </div>
);

// ── Product form modal ────────────────────────────────────────────────────────
const ProductModal = ({ product, categories, brands, onClose, onSaved }) => {
  const [form, setForm] = useState({
    name: product?.name || "",
    category: product?.category || "",
    brand: product?.brand || "",
    price: product?.price || "",
    original_price: product?.original_price || "",
    stock: product?.stock || 0,
    short_description: product?.short_description || "",
    description: product?.description || "",
    is_new: product?.is_new ?? false,
    is_sale: product?.is_sale ?? false,
  });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [thumbPreview, setThumbPreview] = useState(product?.thumbnail_url || null);
  const thumbRef = useRef(null);
  const [thumbFile, setThumbFile] = useState(null);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((p) => ({ ...p, [name]: type === "checkbox" ? checked : value }));
    setErrors((p) => ({ ...p, [name]: undefined }));
  };

  const handleThumb = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setThumbFile(f);
    setThumbPreview(URL.createObjectURL(f));
  };

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = "Required";
    if (!form.price) e.price = "Required";
    if (!form.category) e.category = "Required";
    return e;
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    const e = validate();
    if (Object.keys(e).length) { setErrors(e); return; }
    setSaving(true);
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => fd.append(k, v));
      if (thumbFile) fd.append("thumbnail", thumbFile);
      if (product) {
        await adminAPI.updateProduct(product.id, fd);
      } else {
        await adminAPI.createProduct(fd);
      }
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
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center p-6 border-b sticky top-0 bg-white z-10">
          <h3 className="text-lg font-bold">{product ? "Edit Product" : "Add New Product"}</h3>
          <button onClick={onClose}><i className="bi bi-x-lg text-xl text-gray-400 hover:text-gray-600"></i></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Field name="name" label="Product Name" form={form} handleChange={handleChange} errors={errors} />
            </div>
            {/* Category */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Category</label>
              <select name="category" value={form.category} onChange={handleChange}
                className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500 ${errors.category ? "border-red-400" : "border-gray-200"}`}>
                <option value="">Select…</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              {errors.category && <p className="text-red-500 text-xs mt-0.5">{errors.category}</p>}
            </div>
            {/* Brand */}
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Brand</label>
              <select name="brand" value={form.brand} onChange={handleChange}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500">
                <option value="">Select…</option>
                {brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </div>
            <Field name="price" label="Price ($)" type="number" form={form} handleChange={handleChange} errors={errors} />
            <Field name="original_price" label="Original Price ($)" type="number" form={form} handleChange={handleChange} errors={errors} />
            <Field name="stock" label="Stock Quantity" type="number" form={form} handleChange={handleChange} errors={errors} />
            <Field name="short_description" label="Short Description" textarea form={form} handleChange={handleChange} errors={errors} />
            <Field name="description" label="Full Description" textarea form={form} handleChange={handleChange} errors={errors} />

            {/* Thumbnail */}
            <div className="col-span-2">
              <label className="block text-xs font-semibold text-gray-600 mb-2">Thumbnail</label>
              <div className="flex items-center gap-4">
                {thumbPreview && (
                  <img src={thumbPreview} alt="" className="w-20 h-20 object-cover rounded-xl border" />
                )}
                <button type="button" onClick={() => thumbRef.current?.click()}
                  className="px-4 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50 transition">
                  <i className="bi bi-upload mr-1.5"></i> Upload Image
                </button>
                <input ref={thumbRef} type="file" accept="image/*" className="hidden" onChange={handleThumb} />
              </div>
            </div>

            {/* Toggles */}
            <div className="col-span-2 flex gap-6">
              {[["is_new", "Mark as New"], ["is_sale", "On Sale"]].map(([key, label]) => (
                <label key={key} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" name={key} checked={form[key]} onChange={handleChange}
                    className="w-4 h-4 accent-teal-600" />
                  <span className="text-sm text-gray-700">{label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="flex gap-3 mt-6">
            <button type="button" onClick={onClose}
              className="flex-1 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-sm hover:bg-gray-50 transition">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 py-2.5 bg-teal-600 text-white rounded-xl text-sm font-semibold hover:bg-teal-700 transition disabled:opacity-60">
              {saving ? "Saving…" : product ? "Save Changes" : "Add Product"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────
const AdminProducts = () => {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("-created_at");
  const [catFilter, setCatFilter] = useState("");
  const [modal, setModal] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const { toast, show, dismiss } = useToast();

  const fetchProducts = () => {
    setLoading(true);
    adminAPI.getProducts({ page, search, ordering: sort, category: catFilter || undefined, page_size: 10 })
      .then(({ data }) => { setProducts(data.results ?? data); setTotal(data.count ?? 0); })
      .catch(() => show("Failed to load products", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    adminAPI.getCategories({ page_size: 100 }).then(({ data }) => setCategories(data.results ?? data)).catch(() => { });
    adminAPI.getBrands({ page_size: 100 }).then(({ data }) => setBrands(data.results ?? data)).catch(() => { });
  }, []);

  useEffect(() => { fetchProducts(); }, [page, search, sort, catFilter]);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await adminAPI.deleteProduct(confirm.id);
      show("Product deleted");
      setConfirm(null);
      fetchProducts();
    } catch {
      show("Failed to delete product", "error");
    } finally {
      setDeleting(false);
    }
  };

  const COLUMNS = [
    {
      key: "thumbnail_url", label: "Image",
      render: (v, row) => (
        <img src={v || "/assets/img/product/product-1.webp"} alt={row.name}
          className="w-12 h-12 object-cover rounded-xl border" />
      ),
    },
    {
      key: "name", label: "Product", sortable: true,
      render: (v, row) => (
        <div>
          <p className="font-semibold text-gray-800 text-sm max-w-xs truncate">{v}</p>
          <p className="text-xs text-gray-500">{row.category_name} · {row.brand_name}</p>
        </div>
      ),
    },
    {
      key: "price", label: "Price", sortable: true,
      render: (v, row) => (
        <div>
          <p className="font-semibold text-gray-800">{fmt(v)}</p>
          {row.original_price && <p className="text-xs text-gray-400 line-through">{fmt(row.original_price)}</p>}
        </div>
      ),
    },
    {
      key: "stock", label: "Stock", sortable: true,
      render: (v) => (
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${v === 0 ? "bg-red-100 text-red-700" : v <= 5 ? "bg-amber-100 text-amber-700" : "bg-green-100 text-green-700"
          }`}>
          {v === 0 ? "Out" : v <= 5 ? `Low (${v})` : v}
        </span>
      ),
    },
    {
      key: "rating", label: "Rating", sortable: true,
      render: (v, row) => (
        <div className="flex items-center gap-1 text-yellow-500 text-xs">
          <i className="bi bi-star-fill"></i>
          <span className="text-gray-700 font-medium">{parseFloat(v || 0).toFixed(1)}</span>
          <span className="text-gray-400">({row.reviews_count})</span>
        </div>
      ),
    },
    {
      key: "is_sale", label: "Badges",
      render: (_, row) => (
        <div className="flex gap-1 flex-wrap">
          {row.is_new && <span className="bg-teal-100 text-teal-700 text-xs px-2 py-0.5 rounded-full">New</span>}
          {row.is_sale && <span className="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full">Sale</span>}
        </div>
      ),
    },
  ];

  const Btn = ({ icon, label, onClick, variant }) => (
    <button onClick={onClick} title={label}
      className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border transition ${variant === "danger" ? "border-red-200 text-red-600 hover:bg-red-50"
        : variant === "primary" ? "bg-teal-600 text-white border-teal-600 hover:bg-teal-700"
          : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
      <i className={`bi ${icon}`}></i>
    </button>
  );

  return (
    <div className="space-y-5">
      <Toast toast={toast} onDismiss={dismiss} />
      {confirm && (
        <ConfirmModal isOpen title="Delete Product" message={`Delete "${confirm.name}"? This action cannot be undone.`}
          confirmLabel="Delete" onConfirm={handleDelete} onClose={() => setConfirm(null)} loading={deleting} />
      )}
      {modal && (
        <ProductModal product={modal === "new" ? null : modal} categories={categories} brands={brands}
          onClose={() => setModal(null)} onSaved={() => { fetchProducts(); show("Product saved"); }} />
      )}

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Products</h1>
          <p className="text-sm text-gray-500">{total} total products</p>
        </div>
        <button onClick={() => setModal("new")}
          className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-xl hover:bg-teal-700 transition text-sm font-semibold">
          <i className="bi bi-plus-lg"></i> Add Product
        </button>
      </div>

      <DataTable columns={COLUMNS} data={products} loading={loading} totalCount={total}
        page={page} pageSize={10} onPageChange={setPage}
        sort={sort} onSort={setSort} search={search}
        onSearch={(v) => { setSearch(v); setPage(1); }}
        searchPlaceholder="Search products…"
        emptyIcon="bi-bag" emptyText="No products found"
        filters={
          <select value={catFilter} onChange={(e) => { setCatFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-200 rounded-lg bg-white text-sm focus:outline-none">
            <option value="">All Categories</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        }
        rowActions={(row) => (
          <>
            <Btn icon="bi-pencil" label="Edit" onClick={() => setModal(row)} variant="primary" />
            <Btn icon="bi-trash" label="Delete" onClick={() => setConfirm(row)} variant="danger" />
          </>
        )}
      />
    </div>
  );
};

export default AdminProducts;
