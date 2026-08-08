import { useRef } from "react";

/**
 * DataTable — generic, paginated admin table.
 *
 * Props:
 *   columns     { key, label, render?, sortable?, className? }[]
 *   data        array
 *   loading     boolean
 *   totalCount  number
 *   page        number
 *   pageSize    number
 *   onPageChange  fn(page)
 *   sort        string  (e.g. "-created_at")
 *   onSort      fn(sort)
 *   search      string
 *   onSearch    fn(string)
 *   searchPlaceholder string
 *   filters     ReactNode   (extra filter controls)
 *   rowActions  fn(row) => ReactNode
 *   emptyIcon   string   (Bootstrap icon class)
 *   emptyText   string
 */
const DataTable = ({
  columns = [],
  data = [],
  loading = false,
  totalCount = 0,
  page = 1,
  pageSize = 10,
  onPageChange,
  sort = "",
  onSort,
  search = "",
  onSearch,
  searchPlaceholder = "Search…",
  filters,
  rowActions,
  emptyIcon = "bi-inbox",
  emptyText = "No records found",
}) => {
  const searchTimeout = useRef(null);
  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  const handleSearch = (e) => {
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      onSearch?.(e.target.value);
      onPageChange?.(1);
    }, 380);
  };

  const handleSort = (key) => {
    if (!onSort) return;
    if (sort === key) onSort(`-${key}`);
    else if (sort === `-${key}`) onSort(key);
    else onSort(`-${key}`);
  };

  const SortIcon = ({ col }) => {
    if (!col.sortable) return null;
    if (sort === col.key) return <i className="bi bi-sort-up text-teal-400 ml-1 text-xs"></i>;
    if (sort === `-${col.key}`) return <i className="bi bi-sort-down text-teal-400 ml-1 text-xs"></i>;
    return <i className="bi bi-arrow-down-up text-gray-300 ml-1 text-xs"></i>;
  };

  return (
    <div>
      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3 mb-4 items-center justify-between">
        <div className="flex flex-wrap gap-2 items-center">
          {onSearch && (
            <div className="relative">
              <i className="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm"></i>
              <input
                type="text"
                defaultValue={search}
                onChange={handleSearch}
                placeholder={searchPlaceholder}
                className="pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-teal-500 w-56 bg-white"
              />
            </div>
          )}
          {filters}
        </div>
        <span className="text-sm text-gray-500">
          {totalCount} result{totalCount !== 1 ? "s" : ""}
        </span>
      </div>

      {/* ── Table ───────────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => col.sortable && handleSort(col.key)}
                    className={`text-left px-5 py-3.5 font-semibold text-gray-600 whitespace-nowrap ${col.sortable ? "cursor-pointer hover:text-gray-800 select-none" : ""
                      } ${col.className || ""}`}
                  >
                    {col.label}
                    <SortIcon col={col} />
                  </th>
                ))}
                {rowActions && (
                  <th className="text-right px-5 py-3.5 font-semibold text-gray-600">Actions</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i}>
                    {columns.map((col) => (
                      <td key={col.key} className="px-5 py-4">
                        <div className="h-4 bg-gray-100 rounded animate-pulse" />
                      </td>
                    ))}
                    {rowActions && (
                      <td className="px-5 py-4">
                        <div className="h-4 bg-gray-100 rounded animate-pulse w-16 ml-auto" />
                      </td>
                    )}
                  </tr>
                ))
              ) : data.length === 0 ? (
                <tr>
                  <td colSpan={columns.length + (rowActions ? 1 : 0)} className="px-5 py-16 text-center text-gray-400">
                    <i className={`bi ${emptyIcon} text-4xl block mb-2`}></i>
                    <span className="text-sm">{emptyText}</span>
                  </td>
                </tr>
              ) : (
                data.map((row, idx) => (
                  <tr key={row.id ?? idx} className="hover:bg-gray-50 transition">
                    {columns.map((col) => (
                      <td key={col.key} className={`px-5 py-3.5 ${col.className || ""}`}>
                        {col.render ? col.render(row[col.key], row) : (row[col.key] ?? "—")}
                      </td>
                    ))}
                    {rowActions && (
                      <td className="px-5 py-3.5 text-right">
                        <div className="flex gap-1.5 justify-end">{rowActions(row)}</div>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* ── Pagination ────────────────────────────────────────────────── */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-4 border-t border-gray-100 text-sm text-gray-600">
            <span>
              Page {page} of {totalPages} · {totalCount} total
            </span>
            <div className="flex gap-1.5">
              <button onClick={() => onPageChange?.(1)} disabled={page === 1}
                className="px-2.5 py-1.5 border rounded-lg hover:bg-gray-50 disabled:opacity-40">
                «
              </button>
              <button onClick={() => onPageChange?.(page - 1)} disabled={page === 1}
                className="px-2.5 py-1.5 border rounded-lg hover:bg-gray-50 disabled:opacity-40">
                ‹
              </button>
              {[...Array(totalPages)]
                .map((_, i) => i + 1)
                .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
                .reduce((acc, p, idx, arr) => {
                  if (idx > 0 && arr[idx - 1] !== p - 1) acc.push("…");
                  acc.push(p);
                  return acc;
                }, [])
                .map((p, i) =>
                  p === "…" ? (
                    <span key={`e-${i}`} className="px-2.5 py-1.5">…</span>
                  ) : (
                    <button key={p} onClick={() => onPageChange?.(p)}
                      className={`px-2.5 py-1.5 border rounded-lg transition ${page === p ? "bg-teal-600 text-white border-teal-600" : "hover:bg-gray-50"
                        }`}>
                      {p}
                    </button>
                  )
                )}
              <button onClick={() => onPageChange?.(page + 1)} disabled={page === totalPages}
                className="px-2.5 py-1.5 border rounded-lg hover:bg-gray-50 disabled:opacity-40">
                ›
              </button>
              <button onClick={() => onPageChange?.(totalPages)} disabled={page === totalPages}
                className="px-2.5 py-1.5 border rounded-lg hover:bg-gray-50 disabled:opacity-40">
                »
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DataTable;
