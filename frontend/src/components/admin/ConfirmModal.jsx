/**
 * ConfirmModal — reusable danger-confirmation dialog.
 *
 * Usage:
 *   <ConfirmModal
 *     isOpen={showConfirm}
 *     title="Delete Product"
 *     message="Are you sure? This action cannot be undone."
 *     confirmLabel="Delete"
 *     onConfirm={handleDelete}
 *     onClose={() => setShowConfirm(false)}
 *     loading={deleting}
 *   />
 */
const ConfirmModal = ({
  isOpen,
  title = "Confirm Action",
  message = "Are you sure you want to proceed?",
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "danger",     // "danger" | "warning" | "primary"
  onConfirm,
  onClose,
  loading = false,
}) => {
  if (!isOpen) return null;

  const VARIANT_STYLES = {
    danger: "bg-red-600 hover:bg-red-700",
    warning: "bg-amber-500 hover:bg-amber-600",
    primary: "bg-teal-600 hover:bg-teal-700",
  };

  const ICON_STYLES = {
    danger: { wrap: "bg-red-100", icon: "bi-exclamation-triangle text-red-600" },
    warning: { wrap: "bg-amber-100", icon: "bi-exclamation-circle text-amber-600" },
    primary: { wrap: "bg-teal-100", icon: "bi-question-circle text-teal-600" },
  };

  const { wrap, icon } = ICON_STYLES[variant] || ICON_STYLES.danger;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`w-12 h-12 rounded-full ${wrap} flex items-center justify-center mx-auto mb-4`}>
          <i className={`bi ${icon} text-xl`}></i>
        </div>
        <h3 className="text-lg font-bold text-gray-800 text-center mb-2">{title}</h3>
        <p className="text-sm text-gray-600 text-center leading-relaxed">{message}</p>
        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            disabled={loading}
            className="flex-1 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50 transition disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`flex-1 py-2.5 text-white rounded-xl text-sm font-semibold transition disabled:opacity-60 ${VARIANT_STYLES[variant]}`}
          >
            {loading ? (
              <span className="inline-flex items-center justify-center gap-2">
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Processing…
              </span>
            ) : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmModal;
