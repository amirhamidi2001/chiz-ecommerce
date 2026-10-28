// src/components/SearchBox.jsx
import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getProductSuggestions } from '../services/api';
import { formatToman } from '../utils/money';

export const SUGGEST_DEBOUNCE_MS = 300;
export const SUGGEST_MIN_LENGTH = 2; // mirrors the backend short-circuit
export const SUGGEST_MAX_RESULTS = 8; // mirrors the backend limit

const NO_RESULTS = [];
const PLACEHOLDER_IMG = '/assets/img/product/product-1.webp';

// ─── Debounce hook ────────────────────────────────────────────────────────────
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debouncedValue;
}

// ─── SearchBox ────────────────────────────────────────────────────────────────
// Type-ahead search box. Suggestions come from the lightweight
// GET /products/suggest/ endpoint (id, name, slug, price, thumbnail_url) — not
// the paginated product list. Self-contained so the dropdown / AbortController
// lifecycle doesn't cause Header re-renders.
const SearchBox = ({ className = '', inputClass = '', buttonClass = '', onSubmit }) => {
  const [query, setQuery] = useState('');
  // Results for the term they were fetched for. Keeping the term alongside
  // them lets "is a request in flight?" be DERIVED (settled.term !== the
  // term we want) rather than tracked in a flag that an aborted request
  // could leave stuck on.
  const [settled, setSettled] = useState({ term: null, results: [] });
  const [isOpen, setIsOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const wrapperRef = useRef(null);
  const inputRef = useRef(null);
  const debouncedQuery = useDebounce(query, SUGGEST_DEBOUNCE_MS);
  const navigate = useNavigate();

  const term = debouncedQuery.trim();
  const isSearchable = term.length >= SUGGEST_MIN_LENGTH;
  const suggestions = useMemo(
    () => (isSearchable ? settled.results : NO_RESULTS),
    [isSearchable, settled.results],
  );
  const isFetching = isSearchable && settled.term !== term;
  const showDropdown = isOpen && isSearchable;

  // ── Live suggestions ────────────────────────────────────────────────────
  useEffect(() => {
    if (!isSearchable) return undefined;

    const controller = new AbortController();

    getProductSuggestions(term, { signal: controller.signal })
      .then(({ data }) => {
        if (controller.signal.aborted) return; // superseded: ignore stale data
        const results = Array.isArray(data) ? data.slice(0, SUGGEST_MAX_RESULTS) : [];
        setSettled({ term, results });
        // Open even when empty: an empty result shows a "No results" row
        // rather than nothing at all.
        setIsOpen(true);
        setActiveIdx(-1);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        // Network error / throttled: just close — suggestions are a nicety.
        setSettled({ term, results: [] });
        setIsOpen(false);
      });

    return () => controller.abort();
  }, [term, isSearchable]);

  // ── Close on outside click ──────────────────────────────────────────────
  useEffect(() => {
    const handleOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    setQuery('');
  }, []);

  // ── Keyboard navigation ─────────────────────────────────────────────────
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
        return;
      }
      if (!showDropdown) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, -1));
      } else if (e.key === 'Enter' && activeIdx >= 0) {
        e.preventDefault();
        navigate(`/product/${suggestions[activeIdx].slug}`);
        close();
      }
    },
    [showDropdown, activeIdx, suggestions, navigate, close],
  );

  // ── Submit (Enter with nothing highlighted, search button, "See all") ───
  const handleSubmit = useCallback(
    (e) => {
      e.preventDefault();
      const trimmed = query.trim();
      if (!trimmed) return;
      setIsOpen(false);
      if (onSubmit) onSubmit(trimmed);
      else navigate(`/search?q=${encodeURIComponent(trimmed)}`);
      setQuery('');
      inputRef.current?.blur();
    },
    [query, navigate, onSubmit],
  );

  const hasResults = suggestions.length > 0;

  return (
    <div ref={wrapperRef} className={`relative ${className}`}>
      <form onSubmit={handleSubmit} className="flex border border-emerald-300 rounded-full overflow-hidden w-full shadow-sm">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            // Too short to search: close now rather than leave the previous
            // term's dropdown up until the debounce catches up.
            if (e.target.value.trim().length < SUGGEST_MIN_LENGTH) setIsOpen(false);
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => isSearchable && setIsOpen(true)}
          placeholder="Search for products…"
          className={`flex-1 px-5 py-2 outline-none text-sm bg-white ${inputClass}`}
          autoComplete="off"
          aria-label="Search products"
          aria-autocomplete="list"
          aria-expanded={showDropdown}
          aria-haspopup="listbox"
        />
        <button
          type="submit"
          className={`bg-teal-700 text-white px-5 hover:bg-teal-800 transition ${buttonClass}`}
          aria-label="Submit search"
        >
          {isFetching
            ? <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            : <i className="bi bi-search" />
          }
        </button>
      </form>

      {/* ── Suggestions dropdown ──────────────────────────────────────────── */}
      {showDropdown && (
        <ul
          role="listbox"
          aria-label="Search suggestions"
          className="absolute left-0 right-0 top-full mt-2 bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden"
        >
          {hasResults ? (
            <>
              {suggestions.map((product, idx) => (
                <li
                  key={product.id}
                  role="option"
                  aria-selected={idx === activeIdx}
                  onMouseEnter={() => setActiveIdx(idx)}
                >
                  <Link
                    to={`/product/${product.slug}`}
                    onClick={close}
                    className={`flex items-center gap-3 px-4 py-3 transition-colors ${idx === activeIdx ? 'bg-emerald-50' : 'hover:bg-gray-50'}`}
                  >
                    <img
                      src={product.thumbnail_url || PLACEHOLDER_IMG}
                      alt=""
                      className="w-10 h-10 object-cover rounded-lg flex-shrink-0"
                    />
                    <span className="flex-1 min-w-0 text-sm font-medium text-gray-800 truncate">
                      {product.name}
                    </span>
                    <span className="text-sm font-semibold text-teal-700 flex-shrink-0">
                      {formatToman(product.price)}
                    </span>
                  </Link>
                </li>
              ))}

              {/* "See all results" footer */}
              <li role="presentation" className="border-t border-gray-100">
                <button
                  type="button"
                  onClick={handleSubmit}
                  className="w-full flex items-center justify-center gap-2 py-3 text-sm text-teal-700 font-medium hover:bg-emerald-50 transition-colors"
                >
                  <i className="bi bi-search" />
                  See all results for &ldquo;{query.trim()}&rdquo;
                </button>
              </li>
            </>
          ) : (
            <li role="status" className="px-4 py-4 text-sm text-gray-500 text-center">
              No results found
            </li>
          )}
        </ul>
      )}
    </div>
  );
};

export default SearchBox;
