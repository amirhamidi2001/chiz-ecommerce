import { useEffect, useState } from "react";
import { adminAPI } from "../../services/api";
import DataTable from "../../components/admin/DataTable";
import ConfirmModal from "../../components/admin/ConfirmModal";
import Toast, { useToast } from "../../components/admin/Toast";

// ── Message reader panel ──────────────────────────────────────────────────────
const MessagePanel = ({ message, onClose, onDelete }) => {
  if (!message) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-white w-full max-w-lg h-full shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex justify-between items-center px-6 py-5 border-b flex-shrink-0">
          <h3 className="text-lg font-bold text-gray-800 truncate pr-4">{message.subject || "(No subject)"}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1 rounded-lg hover:bg-gray-100 transition flex-shrink-0"
          >
            <i className="bi bi-x-lg text-xl"></i>
          </button>
        </div>

        {/* Sender meta */}
        <div className="px-6 py-4 border-b bg-gray-50 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-teal-100 flex items-center justify-center flex-shrink-0">
              <span className="text-teal-700 font-bold text-sm">
                {message.name?.[0]?.toUpperCase() || "?"}
              </span>
            </div>
            <div className="min-w-0">
              <p className="font-semibold text-gray-800">{message.name}</p>
              <a
                href={`mailto:${message.email}`}
                className="text-sm text-teal-600 hover:underline truncate block"
              >
                {message.email}
              </a>
            </div>
            <p className="ml-auto text-xs text-gray-400 flex-shrink-0">
              {new Date(message.created_at).toLocaleDateString("en-US", {
                year: "numeric", month: "short", day: "numeric",
              })}
            </p>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="bg-white border border-gray-100 rounded-2xl p-5 shadow-sm">
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {message.message}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="px-6 py-4 border-t flex-shrink-0 flex gap-3">
          <a
            href={`mailto:${message.email}?subject=Re: ${encodeURIComponent(message.subject || "")}`}
            className="flex-1 py-2.5 bg-teal-600 text-white rounded-xl text-sm font-semibold hover:bg-teal-700 transition text-center"
          >
            <i className="bi bi-reply mr-2"></i>Reply via Email
          </a>
          <button
            onClick={() => onDelete(message)}
            className="px-4 py-2.5 border border-red-200 text-red-600 rounded-xl text-sm font-medium hover:bg-red-50 transition"
          >
            <i className="bi bi-trash"></i>
          </button>
        </div>
      </div>
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────
const AdminMessages = () => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("-created_at");
  const [selected, setSelected] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const { toast, show, dismiss } = useToast();

  const fetchMessages = () => {
    setLoading(true);
    adminAPI
      .getMessages({ page, search, ordering: sort, page_size: 12 })
      .then(({ data }) => {
        setMessages(data.results ?? data);
        setTotal(data.count ?? 0);
      })
      .catch(() => show("Failed to load messages", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchMessages(); }, [page, search, sort]);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await adminAPI.deleteMessage(confirm.id);
      show("Message deleted");
      setConfirm(null);
      setSelected(null);
      fetchMessages();
    } catch {
      show("Failed to delete message", "error");
    } finally {
      setDeleting(false);
    }
  };

  const COLUMNS = [
    {
      key: "name",
      label: "Sender",
      render: (v, row) => (
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center flex-shrink-0">
            <span className="text-teal-700 text-xs font-bold">{v?.[0]?.toUpperCase()}</span>
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-gray-800 text-sm">{v}</p>
            <p className="text-xs text-gray-500 truncate max-w-[160px]">{row.email}</p>
          </div>
        </div>
      ),
    },
    {
      key: "subject",
      label: "Subject",
      render: (v, row) => (
        <div className="min-w-0">
          <p className="font-medium text-gray-800 text-sm truncate max-w-[220px]">
            {v || "(No subject)"}
          </p>
          <p className="text-xs text-gray-400 truncate max-w-[220px] mt-0.5">
            {row.message?.slice(0, 80)}…
          </p>
        </div>
      ),
    },
    {
      key: "created_at",
      label: "Received",
      sortable: true,
      render: (v) => (
        <span className="text-xs text-gray-500 whitespace-nowrap">
          {new Date(v).toLocaleDateString("en-US", {
            month: "short", day: "numeric", year: "numeric",
          })}
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
          title="Delete Message"
          message={`Permanently delete the message from "${confirm.name}"?`}
          confirmLabel="Delete"
          onConfirm={handleDelete}
          onClose={() => setConfirm(null)}
          loading={deleting}
        />
      )}

      {selected && (
        <MessagePanel
          message={selected}
          onClose={() => setSelected(null)}
          onDelete={(m) => { setSelected(null); setConfirm(m); }}
        />
      )}

      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Contact Messages</h1>
          <p className="text-sm text-gray-500">{total} message{total !== 1 ? "s" : ""} in inbox</p>
        </div>
        {total > 0 && (
          <div className="bg-teal-50 border border-teal-100 text-teal-700 text-sm px-3 py-1.5 rounded-xl flex items-center gap-1.5">
            <i className="bi bi-envelope text-sm"></i>
            {total} unread
          </div>
        )}
      </div>

      <DataTable
        columns={COLUMNS}
        data={messages}
        loading={loading}
        totalCount={total}
        page={page}
        pageSize={12}
        onPageChange={setPage}
        sort={sort}
        onSort={setSort}
        search={search}
        onSearch={(v) => { setSearch(v); setPage(1); }}
        searchPlaceholder="Search by name, email, subject…"
        emptyIcon="bi-envelope-open"
        emptyText="No messages yet"
        rowActions={(row) => (
          <>
            <button
              onClick={() => setSelected(row)}
              title="Read"
              className="px-2.5 py-1.5 bg-teal-600 text-white rounded-lg text-xs border border-teal-600 hover:bg-teal-700 transition"
            >
              <i className="bi bi-envelope-open"></i>
            </button>
            <a
              href={`mailto:${row.email}?subject=Re: ${encodeURIComponent(row.subject || "")}`}
              title="Reply"
              className="px-2.5 py-1.5 border border-gray-200 text-gray-600 rounded-lg text-xs hover:bg-gray-50 transition"
            >
              <i className="bi bi-reply"></i>
            </a>
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

export default AdminMessages;
