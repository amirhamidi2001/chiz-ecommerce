import { useEffect, useState } from "react";
import { dashboardAPI } from "../services/api";

const COUNTRIES = [
  { code: "US", name: "United States" },
  { code: "GB", name: "United Kingdom" },
  { code: "CA", name: "Canada" },
  { code: "AU", name: "Australia" },
  { code: "DE", name: "Germany" },
  { code: "FR", name: "France" },
];

const EMPTY_FORM = {
  label: "home", first_name: "", last_name: "", phone: "",
  address_line: "", apartment: "", city: "", state: "",
  zip_code: "", country: "US", is_default: false,
};

const AddressModal = ({ address, onClose, onSave }) => {
  const [form, setForm] = useState(address || EMPTY_FORM);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((p) => ({ ...p, [name]: type === "checkbox" ? checked : value }));
    setErrors((p) => ({ ...p, [name]: undefined }));
  };

  const validate = () => {
    const errs = {};
    ["first_name", "last_name", "phone", "address_line", "city", "state", "zip_code"].forEach(
      (f) => { if (!form[f]?.trim()) errs[f] = "Required"; }
    );
    return errs;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setSaving(true);
    try {
      await onSave(form);
      onClose();
    } catch (err) {
      const data = err?.response?.data || {};
      setErrors(data);
    } finally {
      setSaving(false);
    }
  };

  const Field = ({ name, label, type = "text", half }) => (
    <div className={half ? "col-span-1" : "col-span-2"}>
      <label className="block text-xs font-semibold text-gray-600 mb-1">{label}</label>
      <input
        type={type} name={name} value={form[name]} onChange={handleChange}
        className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500 ${errors[name] ? "border-red-400 bg-red-50" : "border-gray-200"
          }`}
      />
      {errors[name] && <p className="text-red-500 text-xs mt-0.5">{errors[name]}</p>}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-center p-6 border-b">
          <h3 className="text-lg font-bold">{address ? "Edit Address" : "Add New Address"}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <i className="bi bi-x-lg text-xl"></i>
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6">
          <div className="grid grid-cols-2 gap-4">
            {/* Label */}
            <div className="col-span-2">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Label</label>
              <select name="label" value={form.label} onChange={handleChange}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500">
                <option value="home">Home</option>
                <option value="office">Office</option>
                <option value="other">Other</option>
              </select>
            </div>
            <Field name="first_name" label="First Name" half />
            <Field name="last_name" label="Last Name" half />
            <Field name="phone" label="Phone" half />
            <div className="col-span-1">
              <label className="block text-xs font-semibold text-gray-600 mb-1">Country</label>
              <select name="country" value={form.country} onChange={handleChange}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500">
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>{c.name}</option>
                ))}
              </select>
            </div>
            <Field name="address_line" label="Address Line" />
            <Field name="apartment" label="Apartment / Suite (optional)" />
            <Field name="city" label="City" half />
            <Field name="state" label="State / Province" half />
            <Field name="zip_code" label="ZIP / Postal Code" half />

            {/* Default */}
            <div className="col-span-2 flex items-center gap-2 mt-1">
              <input type="checkbox" id="is_default" name="is_default"
                checked={form.is_default} onChange={handleChange}
                className="w-4 h-4 accent-teal-600" />
              <label htmlFor="is_default" className="text-sm text-gray-700">
                Set as default address
              </label>
            </div>
          </div>

          <div className="flex gap-3 mt-6">
            <button type="button" onClick={onClose}
              className="flex-1 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-sm hover:bg-gray-50 transition">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 py-2.5 bg-teal-600 text-white rounded-xl text-sm hover:bg-teal-700 transition disabled:opacity-60 font-medium">
              {saving ? "Saving…" : address ? "Save Changes" : "Add Address"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const AddressesTab = () => {
  const [addresses, setAddresses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // null | "new" | address object
  const [deleting, setDeleting] = useState(null);
  const [toast, setToast] = useState(null);

  const showToast = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const fetchAddresses = () => {
    setLoading(true);
    dashboardAPI.getAddresses()
      .then(({ data }) => setAddresses(data.results ?? data))
      .catch(() => { })
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchAddresses(); }, []);

  const handleSave = async (formData) => {
    if (modal && modal !== "new") {
      await dashboardAPI.updateAddress(modal.id, formData);
      showToast("Address updated");
    } else {
      await dashboardAPI.createAddress(formData);
      showToast("Address added");
    }
    fetchAddresses();
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this address?")) return;
    setDeleting(id);
    try {
      await dashboardAPI.deleteAddress(id);
      setAddresses((prev) => prev.filter((a) => a.id !== id));
      showToast("Address deleted");
    } catch {
      showToast("Failed to delete", "error");
    } finally {
      setDeleting(null);
    }
  };

  const handleSetDefault = async (addr) => {
    try {
      await dashboardAPI.updateAddress(addr.id, { is_default: true });
      fetchAddresses();
      showToast("Default address updated");
    } catch {
      showToast("Failed to update", "error");
    }
  };

  return (
    <div>
      {toast && (
        <div className={`fixed top-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg text-sm font-medium text-white ${toast.type === "error" ? "bg-red-500" : "bg-teal-600"}`}>
          {toast.msg}
        </div>
      )}

      {modal && (
        <AddressModal
          address={modal === "new" ? null : modal}
          onClose={() => setModal(null)}
          onSave={handleSave}
        />
      )}

      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">My Addresses</h2>
        <button
          onClick={() => setModal("new")}
          className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition text-sm font-medium"
        >
          <i className="bi bi-plus-lg"></i>
          Add Address
        </button>
      </div>

      {loading ? (
        <div className="grid md:grid-cols-2 gap-6">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-48 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : addresses.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <i className="bi bi-geo-alt text-5xl mb-4 block"></i>
          <p className="text-lg font-medium">No addresses saved</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-6">
          {addresses.map((addr) => (
            <div key={addr.id}
              className={`bg-white border rounded-xl p-5 shadow-sm hover:shadow-md transition ${addr.is_default ? "border-teal-500" : "border-gray-100"
                }`}>
              <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-2">
                  <i className={`bi bi-${addr.label === "office" ? "building" : "house"} text-teal-600`}></i>
                  <h4 className="font-bold text-gray-800 capitalize">{addr.label}</h4>
                </div>
                {addr.is_default && (
                  <span className="bg-teal-100 text-teal-700 text-xs px-2 py-0.5 rounded-full font-medium">
                    Default
                  </span>
                )}
              </div>
              <div className="text-sm text-gray-600 leading-relaxed space-y-0.5">
                <p className="font-medium">{addr.full_name}</p>
                <p>{addr.address_line}{addr.apartment && `, ${addr.apartment}`}</p>
                <p>{addr.city}, {addr.state} {addr.zip_code}</p>
                <p>{addr.country}</p>
                <p className="mt-1 text-gray-500">
                  <i className="bi bi-telephone mr-1"></i>{addr.phone}
                </p>
              </div>
              <div className="flex gap-2 mt-4 flex-wrap">
                <button onClick={() => setModal(addr)}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 transition">
                  <i className="bi bi-pencil"></i> Edit
                </button>
                <button onClick={() => handleDelete(addr.id)} disabled={deleting === addr.id}
                  className="flex items-center gap-1 px-3 py-1.5 text-xs text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition">
                  {deleting === addr.id
                    ? <div className="w-3 h-3 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                    : <><i className="bi bi-trash"></i> Delete</>
                  }
                </button>
                {!addr.is_default && (
                  <button onClick={() => handleSetDefault(addr)}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs text-teal-600 border border-teal-200 rounded-lg hover:bg-teal-50 transition">
                    Set Default
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AddressesTab;
