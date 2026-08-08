import { useEffect, useRef, useState } from "react";
import { adminAPI } from "../../services/api";
import DataTable from "../../components/admin/DataTable";
import ConfirmModal from "../../components/admin/ConfirmModal";
import Toast, { useToast } from "../../components/admin/Toast";

// ── Brand modal ───────────────────────────────────────────────────────────────
const BrandModal = ({ brand, onClose, onSaved }) => {
  const [name, setName] = useState(brand?.name || "");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(brand?.logo_url || null);
  const logoRef = useRef(null);

  const handleFile = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    setLogoFile(f);
    setLogoPreview(URL.createObjectURL(f));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) { setError("Brand name is required."); return; }
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append("name", name.trim());
      if (logoFile) fd.append("logo", logoFile);
      if (brand) await adminAPI.updateBrand(brand.id, fd);
      else await adminAPI.createBrand(fd);
      onSaved();
      onClose();
    } catch (err) {
      setError(err?.response?.data?.name?.[0] || "Failed to save brand.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center p-6 border-b">
          <h3 className="text-lg font-bold text-gray-800">
            {brand ? "Edit Brand" : "Add Brand"}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <i className="bi bi-x-lg text-xl"></i>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1.5">
              Brand Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); setError(""); }}
              placeholder="e.g. Nike"
              className={`w-full border rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-teal-500 transition ${error ? "border-red-400 bg-red-50" : "border-gray-200"
                }`}
            />
            {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
          </div>

          {/* Logo */}
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-2">
              Logo (optional)
            </label>
            <div className="flex items-center gap-4">
              {logoPreview ? (
                <img
                  src={logoPreview}
                  alt="Logo preview"
                  className="w-16 h-16 object-contain rounded-xl border bg-gray-50 p-1"
                />
              ) : (
                <div className="w-16 h-16 rounded-xl border border-dashed border-gray-200 bg-gray-50 flex items-center justify-center">
                  <i className="bi bi-image text-gray-300 text-xl"></i>
                </div>
              )}
              <div>
                <button
                  type="button"
                  onClick={() => logoRef.current?.click()}
                  className="px-3 py-2 border border-gray-200 rounded-lg text-sm hover:bg-gray-50 transition"
                >
                  <i className="bi bi-upload mr-1.5 text-gray-500"></i>
                  {logoPreview ? "Change" : "Upload Logo"}
                </button>
                {logoPreview && (
                  <button
                    type="button"
                    onClick={() => { setLogoFile(null); setLogoPreview(null); }}
                    className="ml-2 text-xs text-red-500 hover:underline"
                  >
                    Remove
                  </button>
                )}
                <input
                  ref={logoRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleFile}
                />
                <p className="text-xs text-gray-400 mt-1">PNG, SVG, WebP · max 2 MB</p>
              </div>
            </div>
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-sm hover:bg-gray-50 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 py-2.5 bg-teal-600 text-white rounded-xl text-sm font-semibold hover:bg-teal-700 transition disabled:opacity-60"
            >
              {saving ? "Saving…" : brand ? "Save Changes" : "Add Brand"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────
const AdminBrands = () => {
  const [brands, setBrands] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("name");
  const [modal, setModal] = useState(null);   // null | "new" | brand-object
  const [confirm, setConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const { toast, show, dismiss } = useToast();

  const fetchBrands = () => {
    setLoading(true);
    adminAPI
      .getBrands({ page, search, ordering: sort, page_size: 15 })
      .then(({ data }) => {
        setBrands(data.results ?? data);
        setTotal(data.count ?? (data.results?.length ?? data.length));
      })
      .catch(() => show("Failed to load brands", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchBrands(); }, [page, search, sort]);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await adminAPI.deleteBrand(confirm.id);
      show("Brand deleted");
      setConfirm(null);
      fetchBrands();
    } catch {
      show("Failed to delete. Brand may have linked products.", "error");
    } finally {
      setDeleting(false);
    }
  };

  const COLUMNS = [
    {
      key: "logo_url",
      label: "Logo",
      render: (v, row) =>
        v ? (
          <img
            src={v}
            alt={row.name}
            className="w-12 h-12 object-contain rounded-xl border bg-gray-50 p-1"
          />
        ) : (
          <div className="w-12 h-12 rounded-xl border border-dashed border-gray-200 bg-gray-50 flex items-center justify-center">
            <i className="bi bi-award text-gray-300 text-xl"></i>
          </div>
        ),
    },
    {
      key: "name",
      label: "Brand Name",
      sortable: true,
      render: (v) => <span className="font-semibold text-gray-800">{v}</span>,
    },
    {
      key: "slug",
      label: "Slug",
      render: (v) => (
        <code className="text-xs bg-gray-100 px-2 py-0.5 rounded text-gray-600">{v}</code>
      ),
    },
    {
      key: "product_count",
      label: "Products",
      render: (v) => (
        <span className="bg-teal-50 text-teal-700 text-xs font-semibold px-2.5 py-0.5 rounded-full">
          {v}
        </span>
      ),
    },
  ];

  const ActionBtn = ({ icon, label, onClick, variant = "default" }) => (
    <button
      onClick={onClick}
      title={label}
      className={`px-2.5 py-1.5 rounded-lg text-xs font-medium border transition ${variant === "danger"
          ? "border-red-200 text-red-600 hover:bg-red-50"
          : variant === "primary"
            ? "bg-teal-600 text-white border-teal-600 hover:bg-teal-700"
            : "border-gray-200 text-gray-600 hover:bg-gray-50"
        }`}
    >
      <i className={`bi ${icon}`}></i>
    </button>
  );

  return (
    <div className="space-y-5">
      <Toast toast={toast} onDismiss={dismiss} />

      {confirm && (
        <ConfirmModal
          isOpen
          title="Delete Brand"
          message={`Delete "${confirm.name}"? Products linked to this brand will lose their brand association.`}
          confirmLabel="Delete"
          onConfirm={handleDelete}
          onClose={() => setConfirm(null)}
          loading={deleting}
        />
      )}

      {modal && (
        <BrandModal
          brand={modal === "new" ? null : modal}
          onClose={() => setModal(null)}
          onSaved={() => { fetchBrands(); show("Brand saved successfully"); }}
        />
      )}

      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Brands</h1>
          <p className="text-sm text-gray-500">{total} total brands</p>
        </div>
        <button
          onClick={() => setModal("new")}
          className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-xl hover:bg-teal-700 transition text-sm font-semibold"
        >
          <i className="bi bi-plus-lg"></i> Add Brand
        </button>
      </div>

      <DataTable
        columns={COLUMNS}
        data={brands}
        loading={loading}
        totalCount={total}
        page={page}
        pageSize={15}
        onPageChange={setPage}
        sort={sort}
        onSort={setSort}
        search={search}
        onSearch={(v) => { setSearch(v); setPage(1); }}
        searchPlaceholder="Search brands…"
        emptyIcon="bi-award"
        emptyText="No brands found"
        rowActions={(row) => (
          <>
            <ActionBtn icon="bi-pencil" label="Edit" onClick={() => setModal(row)} variant="primary" />
            <ActionBtn icon="bi-trash" label="Delete" onClick={() => setConfirm(row)} variant="danger" />
          </>
        )}
      />
    </div>
  );
};

export default AdminBrands;
