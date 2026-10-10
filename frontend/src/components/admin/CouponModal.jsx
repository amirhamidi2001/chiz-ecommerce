import { useEffect, useState } from "react";
import { adminAPI } from "../../services/api";
import {
  EMPTY_COUPON_FORM,
  buildCouponPayload,
  changedFields,
  couponToForm,
  parseCouponApiErrors,
  validateCouponForm,
} from "../../utils/coupon";

const inputCls = (error) =>
  `w-full border rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:border-teal-500 transition ${
    error ? "border-red-400 bg-red-50" : "border-gray-200"
  }`;

const Field = ({ id, label, error, hint, required, children }) => (
  <div>
    <label htmlFor={id} className="block text-xs font-semibold text-gray-600 mb-1.5">
      {label} {required && <span className="text-red-500">*</span>}
    </label>
    {children}
    {hint && !error && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    {error && (
      <p className="text-red-500 text-xs mt-1" role="alert">
        {error}
      </p>
    )}
  </div>
);

const Chip = ({ label, onRemove }) => (
  <span className="inline-flex items-center gap-1 bg-teal-50 text-teal-700 text-xs font-medium px-2.5 py-1 rounded-full">
    {label}
    <button
      type="button"
      onClick={onRemove}
      aria-label={`Remove ${label}`}
      className="text-teal-500 hover:text-teal-800"
    >
      <i className="bi bi-x"></i>
    </button>
  </span>
);

// ── Category multi-select: every category in a filterable checkbox list ───────
const loadAllCategories = async () => {
  const all = [];
  let page = 1;
  // Follow DRF pagination until there is no next page.
  for (;;) {
    const { data } = await adminAPI.getCategories({ page, page_size: 100 });
    all.push(...(data.results ?? data));
    if (!data.next) break;
    page += 1;
  }
  return all;
};

const CategoryPicker = ({ selected, onChange }) => {
  const [options, setOptions] = useState([]);
  const [filter, setFilter] = useState("");
  const [status, setStatus] = useState("loading"); // loading | ready | error

  useEffect(() => {
    let cancelled = false;
    loadAllCategories()
      .then((cats) => {
        if (cancelled) return;
        setOptions(cats);
        setStatus("ready");
      })
      .catch(() => !cancelled && setStatus("error"));
    return () => {
      cancelled = true;
    };
  }, []);

  const labelOf = (c) => (c.parent_name ? `${c.parent_name} › ${c.name}` : c.name);
  const isSelected = (id) => selected.some((c) => c.id === id);
  const toggle = (cat) =>
    onChange(
      isSelected(cat.id)
        ? selected.filter((c) => c.id !== cat.id)
        : [...selected, { id: cat.id, name: labelOf(cat) }],
    );
  const visible = options.filter((c) =>
    labelOf(c).toLowerCase().includes(filter.trim().toLowerCase()),
  );

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 mb-2" data-testid="selected-categories">
        {selected.map((c) => (
          <Chip
            key={c.id}
            label={c.name}
            onRemove={() => onChange(selected.filter((s) => s.id !== c.id))}
          />
        ))}
      </div>
      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter categories…"
        aria-label="Filter categories"
        className={`${inputCls(false)} mb-2`}
      />
      <div className="border border-gray-200 rounded-xl max-h-36 overflow-y-auto divide-y divide-gray-50">
        {status === "loading" && (
          <p className="text-xs text-gray-400 p-3">Loading categories…</p>
        )}
        {status === "error" && (
          <p className="text-xs text-red-500 p-3">Couldn't load categories.</p>
        )}
        {status === "ready" && visible.length === 0 && (
          <p className="text-xs text-gray-400 p-3">No categories match.</p>
        )}
        {visible.map((c) => (
          <label
            key={c.id}
            className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 cursor-pointer"
          >
            <input
              type="checkbox"
              checked={isSelected(c.id)}
              onChange={() => toggle(c)}
              className="accent-teal-600"
            />
            {labelOf(c)}
          </label>
        ))}
      </div>
    </div>
  );
};

// ── Product multi-select: search-as-you-type (the catalogue can be large) ─────
const ProductPicker = ({ selected, onChange }) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    const term = query.trim();
    if (!term) return undefined; // nothing to search; stale results are hidden below
    let cancelled = false;
    const timer = setTimeout(() => {
      setSearching(true);
      adminAPI
        .getProducts({ search: term, page_size: 8 })
        .then(({ data }) => !cancelled && setResults(data.results ?? data))
        .catch(() => !cancelled && setResults([]))
        .finally(() => !cancelled && setSearching(false));
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  const isSelected = (id) => selected.some((p) => p.id === id);
  const add = (product) => {
    if (!isSelected(product.id)) {
      onChange([...selected, { id: product.id, name: product.name }]);
    }
  };

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 mb-2" data-testid="selected-products">
        {selected.map((p) => (
          <Chip
            key={p.id}
            label={p.name}
            onRemove={() => onChange(selected.filter((s) => s.id !== p.id))}
          />
        ))}
      </div>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search products to add…"
        aria-label="Search products"
        className={inputCls(false)}
      />
      {query.trim() && (
        <div className="border border-gray-200 rounded-xl mt-2 max-h-36 overflow-y-auto divide-y divide-gray-50">
          {searching && <p className="text-xs text-gray-400 p-3">Searching…</p>}
          {!searching && results.length === 0 && (
            <p className="text-xs text-gray-400 p-3">No products found.</p>
          )}
          {results.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => add(p)}
              disabled={isSelected(p.id)}
              className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              {p.name}
              {isSelected(p.id) && <span className="text-xs text-gray-400"> · added</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// ── Modal ─────────────────────────────────────────────────────────────────────
/**
 * Create / edit form. `coupon` is null when creating. Client-side checks are
 * a UX nicety — the API re-validates everything and its errors are shown
 * against the matching field.
 */
const CouponModal = ({ coupon, onClose, onSaved }) => {
  const initial = coupon ? couponToForm(coupon) : EMPTY_COUPON_FORM;
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  const set = (name, value) => {
    setForm((f) => ({ ...f, [name]: value }));
    setErrors((e) => ({ ...e, [name]: undefined }));
    setFormError("");
  };
  const bind = (name) => ({
    id: `coupon-${name}`,
    value: form[name],
    onChange: (e) => set(name, e.target.value),
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    const found = validateCouponForm(form);
    if (Object.keys(found).length > 0) {
      setErrors(found);
      return;
    }

    const payload = buildCouponPayload(form);
    setSaving(true);
    try {
      if (coupon) {
        // PATCH only what changed, so untouched fields (e.g. dates the form
        // shows at minute precision) are never rewritten.
        const diff = changedFields(buildCouponPayload(couponToForm(coupon)), payload);
        if (Object.keys(diff).length > 0) {
          await adminAPI.updateCoupon(coupon.id, diff);
        }
      } else {
        await adminAPI.createCoupon(payload);
      }
      onSaved();
      onClose();
    } catch (err) {
      const { fieldErrors, formError: general } = parseCouponApiErrors(
        err?.response?.data,
      );
      setErrors(fieldErrors);
      setFormError(
        general ||
          (Object.keys(fieldErrors).length ? "" : "Failed to save coupon."),
      );
    } finally {
      setSaving(false);
    }
  };

  const isPercent = form.discount_type === "percent";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 py-6 overflow-y-auto"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-label={coupon ? "Edit Coupon" : "Add Coupon"}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl my-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center p-6 border-b">
          <h3 className="text-lg font-bold text-gray-800">
            {coupon ? "Edit Coupon" : "Add Coupon"}
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-gray-400 hover:text-gray-600"
          >
            <i className="bi bi-x-lg text-xl"></i>
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate className="p-6 space-y-5">
          {formError && (
            <p className="bg-red-50 text-red-600 text-sm rounded-xl px-4 py-2.5" role="alert">
              {formError}
            </p>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <Field
              id="coupon-code"
              label="Code"
              required
              error={errors.code}
              hint="Stored in uppercase; customers can type it in any case."
            >
              <input
                type="text"
                {...bind("code")}
                maxLength={32}
                placeholder="e.g. SUMMER20"
                className={inputCls(errors.code)}
              />
            </Field>

            <Field id="coupon-discount_type" label="Discount type" required>
              <select
                {...bind("discount_type")}
                className={inputCls(false)}
              >
                <option value="percent">Percentage</option>
                <option value="fixed">Fixed amount</option>
              </select>
            </Field>

            <Field
              id="coupon-value"
              label={isPercent ? "Value (%)" : "Value ($)"}
              required
              error={errors.value}
            >
              <input
                type="number"
                step="0.01"
                min="0"
                {...bind("value")}
                className={inputCls(errors.value)}
              />
            </Field>

            <Field
              id="coupon-min_order_amount"
              label="Minimum order ($)"
              error={errors.min_order_amount}
              hint="Applies to the eligible items if the coupon is restricted."
            >
              <input
                type="number"
                step="0.01"
                min="0"
                {...bind("min_order_amount")}
                className={inputCls(errors.min_order_amount)}
              />
            </Field>

            <Field
              id="coupon-max_uses"
              label="Total uses"
              error={errors.max_uses}
              hint="Across all customers. Leave blank for unlimited."
            >
              <input
                type="number"
                step="1"
                min="1"
                {...bind("max_uses")}
                className={inputCls(errors.max_uses)}
              />
            </Field>

            <Field
              id="coupon-uses_per_user"
              label="Uses per customer"
              required
              error={errors.uses_per_user}
            >
              <input
                type="number"
                step="1"
                min="1"
                {...bind("uses_per_user")}
                className={inputCls(errors.uses_per_user)}
              />
            </Field>

            <Field id="coupon-valid_from" label="Valid from" required error={errors.valid_from}>
              <input
                type="datetime-local"
                {...bind("valid_from")}
                className={inputCls(errors.valid_from)}
              />
            </Field>

            <Field id="coupon-valid_until" label="Valid until" required error={errors.valid_until}>
              <input
                type="datetime-local"
                {...bind("valid_until")}
                className={inputCls(errors.valid_until)}
              />
            </Field>
          </div>

          <div>
            <p className="block text-xs font-semibold text-gray-600 mb-1">
              Restrict to categories
            </p>
            <p className="text-xs text-gray-400 mb-2">
              Leave both pickers empty to apply to the whole cart. Matching is exact — a
              product in a sub-category doesn't match its parent, so tick sub-categories too.
            </p>
            <CategoryPicker
              selected={form.categories}
              onChange={(v) => set("categories", v)}
            />
          </div>

          <div>
            <p className="block text-xs font-semibold text-gray-600 mb-2">
              Restrict to products
            </p>
            <ProductPicker
              selected={form.products}
              onChange={(v) => set("products", v)}
            />
            <p className="text-xs text-gray-400 mt-1.5">
              With both set, an item qualifies if it matches either.
            </p>
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              id="coupon-is_active"
              checked={form.is_active}
              onChange={(e) => set("is_active", e.target.checked)}
              className="accent-teal-600"
            />
            Active
          </label>

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
              {saving ? "Saving…" : coupon ? "Save Changes" : "Add Coupon"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CouponModal;
