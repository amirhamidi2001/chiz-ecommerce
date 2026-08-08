import { useEffect, useState } from "react";

/**
 * Inline Toast component.
 *
 * Usage:
 *   const [toast, setToast] = useState(null);
 *   setToast({ msg: "Saved!", type: "success" });
 *   <Toast toast={toast} onDismiss={() => setToast(null)} />
 */
const Toast = ({ toast, onDismiss, duration = 3500 }) => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!toast) return;
    setVisible(true);
    const t = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss?.(), 300);
    }, duration);
    return () => clearTimeout(t);
  }, [toast, duration, onDismiss]);

  if (!toast) return null;

  const STYLES = {
    success: "bg-teal-600",
    error: "bg-red-500",
    warning: "bg-amber-500",
    info: "bg-blue-500",
  };

  const ICONS = {
    success: "bi-check-circle",
    error: "bi-x-circle",
    warning: "bi-exclamation-triangle",
    info: "bi-info-circle",
  };

  return (
    <div
      className={`fixed top-6 right-6 z-[9999] flex items-center gap-2.5 px-5 py-3 rounded-xl shadow-xl text-sm font-medium text-white transition-all duration-300 ${STYLES[toast.type] || STYLES.success
        } ${visible ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-2"}`}
    >
      <i className={`bi ${ICONS[toast.type] || ICONS.success} text-base`}></i>
      <span>{toast.msg}</span>
      <button
        onClick={() => { setVisible(false); setTimeout(() => onDismiss?.(), 300); }}
        className="ml-2 opacity-70 hover:opacity-100 transition"
      >
        <i className="bi bi-x text-lg leading-none"></i>
      </button>
    </div>
  );
};

/** Helper hook */
export const useToast = () => {
  const [toast, setToast] = useState(null);
  const show = (msg, type = "success") => setToast({ msg, type });
  const dismiss = () => setToast(null);
  return { toast, show, dismiss };
};

export default Toast;
