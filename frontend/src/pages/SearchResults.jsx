// src/pages/SearchResults.jsx
import { useState, useEffect, useCallback, useMemo, useRef, memo } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { getProducts, getCategories, getBrands } from '../services/api';
import { useCart } from '../context/CartContext';
import { useWishlist } from '../context/WishlistContext';

// ─── Constants ────────────────────────────────────────────────────────────────
const PAGE_SIZE = 12;

const SORT_OPTIONS = [
  { value: '-created_at', label: 'Newest First' },
  { value: 'price', label: 'Price: Low to High' },
  { value: '-price', label: 'Price: High to Low' },
  { value: '-rating', label: 'Customer Rating' },
  { value: '-reviews_count', label: 'Most Reviewed' },
];

const RATING_OPTIONS = [4, 3, 2, 1];

// ─── Helpers ──────────────────────────────────────────────────────────────────
const buildParams = (sp) => {
  const p = {};
  if (sp.get('q')) p.search = sp.get('q');
  if (sp.get('ordering')) p.ordering = sp.get('ordering');
  if (sp.get('category')) p.category = sp.get('category');
  if (sp.get('brand')) p.brand = sp.get('brand');
  if (sp.get('min_price')) p.min_price = sp.get('min_price');
  if (sp.get('max_price')) p.max_price = sp.get('max_price');
  if (sp.get('min_rating')) p.min_rating = sp.get('min_rating');
  p.page = sp.get('page') || 1;
  p.page_size = PAGE_SIZE;
  return p;
};

const totalPages = (count) => Math.ceil(count / PAGE_SIZE);

// ─── Skeleton Card ────────────────────────────────────────────────────────────
const SkeletonCard = () => (
  <div className="bg-white rounded-xl overflow-hidden shadow-sm animate-pulse">
    <div className="w-full h-56 bg-gray-200" />
    <div className="p-4 space-y-3">
      <div className="h-3 bg-gray-200 rounded w-1/3" />
      <div className="h-4 bg-gray-200 rounded w-3/4" />
      <div className="h-4 bg-gray-200 rounded w-1/2" />
    </div>
  </div>
);

// ─── Star Rating ──────────────────────────────────────────────────────────────
const StarRating = memo(({ rating, count, compact = false }) => {
  const full = Math.floor(rating);
  const half = rating - full >= 0.5;
  return (
    <div className="flex items-center gap-1">
      <div className="flex text-yellow-400 text-xs">
        {Array.from({ length: 5 }, (_, i) => (
          <i
            key={i}
            className={
              i < full ? 'bi bi-star-fill' : i === full && half ? 'bi bi-star-half' : 'bi bi-star'
            }
          />
        ))}
      </div>
      {!compact && <span className="text-xs text-gray-500">({count ?? 0})</span>}
    </div>
  );
});

// ─── Product Card ─────────────────────────────────────────────────────────────
const ProductCard = memo(({ product }) => {
  const [hovered, setHovered] = useState(false);
  const { addToCart } = useCart();
  const { addToWishlist, removeFromWishlist, isInWishlist } = useWishlist();

  const inWishlist = isInWishlist?.(product.id) ?? false;
  const price = Number(product.price ?? 0);
  const salePrice = product.sale_price ? Number(product.sale_price) : null;
  const displayPrice = salePrice ?? price;
  const discount = salePrice ? Math.round(((price - salePrice) / price) * 100) : null;

  const thumbnail =
    product.thumbnail ||
    product.image ||
    product.images?.[0]?.image ||
    '/assets/img/product/product-1.webp';

  const handleAddToCart = useCallback(
    (e) => {
      e.preventDefault();
      addToCart(product.id, 1);
    },
    [addToCart, product.id],
  );

  const handleWishlist = useCallback(
    (e) => {
      e.preventDefault();
      if (inWishlist) removeFromWishlist?.(product.id);
      else addToWishlist?.(product.id);
    },
    [inWishlist, addToWishlist, removeFromWishlist, product.id],
  );

  return (
    <article
      className="group bg-white rounded-xl overflow-hidden shadow-sm hover:shadow-lg transition-shadow duration-300 flex flex-col"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Image */}
      <div className="relative overflow-hidden flex-shrink-0">
        <Link to={`/product/${product.slug}`} tabIndex={-1}>
          <img
            src={hovered && product.hover_image ? product.hover_image : thumbnail}
            alt={product.name}
            className="w-full h-56 object-cover transition-transform duration-500 group-hover:scale-105"
            loading="lazy"
          />
        </Link>

        {/* Badges */}
        <div className="absolute top-3 left-3 flex flex-col gap-1">
          {product.is_new && (
            <span className="bg-teal-500 text-white text-xs font-semibold px-2 py-0.5 rounded">New</span>
          )}
          {discount && (
            <span className="bg-red-500 text-white text-xs font-semibold px-2 py-0.5 rounded">-{discount}%</span>
          )}
          {product.in_stock === false && (
            <span className="bg-gray-500 text-white text-xs font-semibold px-2 py-0.5 rounded">Out of stock</span>
          )}
        </div>

        {/* Wishlist button */}
        <button
          onClick={handleWishlist}
          className={`absolute top-3 right-3 p-1.5 rounded-full transition-all duration-200 ${inWishlist
              ? 'bg-red-500 text-white shadow-md'
              : 'bg-white/80 text-gray-600 hover:bg-red-50 hover:text-red-500 opacity-0 group-hover:opacity-100'
            }`}
          aria-label={inWishlist ? 'Remove from wishlist' : 'Add to wishlist'}
        >
          <i className={`bi ${inWishlist ? 'bi-heart-fill' : 'bi-heart'} text-sm`} />
        </button>

        {/* Quick-add overlay */}
        <div className="absolute inset-x-0 bottom-0 flex items-end justify-center pb-3 opacity-0 group-hover:opacity-100 translate-y-2 group-hover:translate-y-0 transition-all duration-300">
          <button
            onClick={handleAddToCart}
            disabled={product.in_stock === false}
            className="bg-teal-700 text-white text-sm font-medium px-5 py-2 rounded-full shadow-lg hover:bg-teal-800 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <i className="bi bi-cart-plus" />
            {product.in_stock === false ? 'Out of stock' : 'Add to cart'}
          </button>
        </div>
      </div>

      {/* Info */}
      <div className="p-4 flex flex-col gap-1 flex-1">
        {product.category?.name && (
          <p className="text-xs text-gray-400 uppercase tracking-wide">{product.category.name}</p>
        )}
        <h3 className="font-semibold text-gray-800 line-clamp-2 leading-snug text-sm">
          <Link to={`/product/${product.slug}`} className="hover:text-teal-600 transition-colors">
            {product.name}
          </Link>
        </h3>
        {product.brand?.name && (
          <p className="text-xs text-gray-500">{product.brand.name}</p>
        )}

        <div className="mt-auto pt-2 flex items-center justify-between gap-2">
          <div className="flex items-baseline gap-2">
            <span className="text-base font-bold text-teal-700">${displayPrice.toFixed(2)}</span>
            {salePrice && (
              <span className="text-xs text-gray-400 line-through">${price.toFixed(2)}</span>
            )}
          </div>
          <StarRating rating={product.rating ?? 0} count={product.reviews_count} compact />
        </div>
      </div>
    </article>
  );
});

// ─── Filter Sidebar ───────────────────────────────────────────────────────────
const FilterSidebar = memo(({ categories, brands, searchParams, onFilterChange, onClearAll, activeFilterCount }) => {
  const [priceMin, setPriceMin] = useState(searchParams.get('min_price') || '');
  const [priceMax, setPriceMax] = useState(searchParams.get('max_price') || '');

  // Sync local price inputs when URL params change externally
  useEffect(() => {
    setPriceMin(searchParams.get('min_price') || '');
    setPriceMax(searchParams.get('max_price') || '');
  }, [searchParams]);

  const applyPrice = useCallback(() => {
    const updates = {};
    if (priceMin) updates.min_price = priceMin;
    if (priceMax) updates.max_price = priceMax;
    if (!priceMin) updates.min_price = null;
    if (!priceMax) updates.max_price = null;
    onFilterChange(updates);
  }, [priceMin, priceMax, onFilterChange]);

  return (
    <aside className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-gray-800 text-base">Filters</h2>
        {activeFilterCount > 0 && (
          <button
            onClick={onClearAll}
            className="text-xs text-red-500 hover:text-red-600 font-medium flex items-center gap-1"
          >
            <i className="bi bi-x-circle" /> Clear all ({activeFilterCount})
          </button>
        )}
      </div>

      {/* ── Category ────────────────────────────────────────────────────── */}
      {categories.length > 0 && (
        <FilterGroup title="Category">
          {categories.map((cat) => (
            <FilterRadio
              key={cat.id}
              name="category"
              value={cat.slug ?? String(cat.id)}
              label={cat.name}
              checked={searchParams.get('category') === (cat.slug ?? String(cat.id))}
              onChange={(val) =>
                onFilterChange({ category: searchParams.get('category') === val ? null : val })
              }
            />
          ))}
        </FilterGroup>
      )}

      {/* ── Brand ───────────────────────────────────────────────────────── */}
      {brands.length > 0 && (
        <FilterGroup title="Brand">
          {brands.map((brand) => (
            <FilterRadio
              key={brand.id}
              name="brand"
              value={String(brand.id)}
              label={brand.name}
              checked={searchParams.get('brand') === String(brand.id)}
              onChange={(val) =>
                onFilterChange({ brand: searchParams.get('brand') === val ? null : val })
              }
            />
          ))}
        </FilterGroup>
      )}

      {/* ── Price range ─────────────────────────────────────────────────── */}
      <FilterGroup title="Price Range">
        <div className="flex items-center gap-2">
          <input
            type="number"
            min="0"
            value={priceMin}
            onChange={(e) => setPriceMin(e.target.value)}
            placeholder="Min"
            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-teal-500"
          />
          <span className="text-gray-400 flex-shrink-0">–</span>
          <input
            type="number"
            min="0"
            value={priceMax}
            onChange={(e) => setPriceMax(e.target.value)}
            placeholder="Max"
            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-teal-500"
          />
        </div>
        <button
          onClick={applyPrice}
          className="mt-2 w-full bg-teal-600 text-white text-sm rounded-lg py-1.5 hover:bg-teal-700 transition"
        >
          Apply
        </button>
      </FilterGroup>

      {/* ── Customer Rating ──────────────────────────────────────────────── */}
      <FilterGroup title="Customer Rating">
        {RATING_OPTIONS.map((r) => (
          <button
            key={r}
            onClick={() =>
              onFilterChange({ min_rating: searchParams.get('min_rating') === String(r) ? null : String(r) })
            }
            className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm transition ${searchParams.get('min_rating') === String(r)
                ? 'bg-emerald-50 text-teal-700 font-medium'
                : 'hover:bg-gray-50 text-gray-600'
              }`}
          >
            <div className="flex text-yellow-400 text-xs">
              {Array.from({ length: 5 }, (_, i) => (
                <i key={i} className={i < r ? 'bi bi-star-fill' : 'bi bi-star'} />
              ))}
            </div>
            <span>& Up</span>
            {searchParams.get('min_rating') === String(r) && (
              <i className="bi bi-check-circle-fill text-teal-600 ml-auto" />
            )}
          </button>
        ))}
      </FilterGroup>
    </aside>
  );
});

// ─── FilterGroup ──────────────────────────────────────────────────────────────
const FilterGroup = ({ title, children }) => {
  const [open, setOpen] = useState(true);
  return (
    <div className="border-t border-gray-100 pt-5">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between text-sm font-semibold text-gray-700 mb-3"
      >
        {title}
        <i className={`bi bi-chevron-${open ? 'up' : 'down'} text-gray-400 text-xs`} />
      </button>
      {open && <div className="space-y-1">{children}</div>}
    </div>
  );
};

// ─── FilterRadio ──────────────────────────────────────────────────────────────
const FilterRadio = ({ name: _name, value, label, checked, onChange }) => (
  <button
    onClick={() => onChange(value)}
    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm transition ${checked ? 'bg-emerald-50 text-teal-700 font-medium' : 'hover:bg-gray-50 text-gray-600'
      }`}
  >
    <div className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${checked ? 'border-teal-600 bg-teal-600' : 'border-gray-300'
      }`}>
      {checked && <i className="bi bi-check text-white text-xs" />}
    </div>
    {label}
  </button>
);

// ─── Pagination ───────────────────────────────────────────────────────────────
const Pagination = memo(({ currentPage, total, count, onPageChange }) => {
  if (total <= 1) return null;

  const pages = useMemo(() => {
    const delta = 2;
    const range = [];
    const left = Math.max(2, currentPage - delta);
    const right = Math.min(total - 1, currentPage + delta);

    range.push(1);
    if (left > 2) range.push('…');
    for (let i = left; i <= right; i++) range.push(i);
    if (right < total - 1) range.push('…');
    if (total > 1) range.push(total);
    return range;
  }, [currentPage, total]);

  return (
    <nav className="flex flex-col items-center gap-3 mt-12" aria-label="Pagination">
      <p className="text-sm text-gray-500">
        Page <span className="font-medium">{currentPage}</span> of{' '}
        <span className="font-medium">{total}</span> &mdash;{' '}
        <span className="font-medium">{count}</span> results
      </p>
      <div className="flex items-center gap-1 flex-wrap justify-center">
        <PageBtn
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          aria-label="Previous page"
        >
          <i className="bi bi-chevron-left" />
        </PageBtn>

        {pages.map((p, i) =>
          p === '…' ? (
            <span key={`ellipsis-${i}`} className="px-2 py-1 text-gray-400 select-none">…</span>
          ) : (
            <PageBtn
              key={p}
              onClick={() => onPageChange(p)}
              active={p === currentPage}
              aria-label={`Page ${p}`}
              aria-current={p === currentPage ? 'page' : undefined}
            >
              {p}
            </PageBtn>
          ),
        )}

        <PageBtn
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === total}
          aria-label="Next page"
        >
          <i className="bi bi-chevron-right" />
        </PageBtn>
      </div>
    </nav>
  );
});

const PageBtn = ({ children, onClick, disabled, active, ...rest }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={`min-w-[36px] h-9 flex items-center justify-center px-2 rounded-lg text-sm font-medium transition ${active
        ? 'bg-teal-600 text-white shadow-sm'
        : disabled
          ? 'text-gray-300 cursor-not-allowed'
          : 'border border-gray-200 text-gray-700 hover:bg-emerald-50 hover:border-teal-400'
      }`}
    {...rest}
  >
    {children}
  </button>
);

// ─── Active Filter Chips ──────────────────────────────────────────────────────
const ActiveChips = memo(({ searchParams, categories, brands, onRemove }) => {
  const chips = [];

  const catSlug = searchParams.get('category');
  if (catSlug) {
    const label = categories.find((c) => (c.slug ?? String(c.id)) === catSlug)?.name ?? catSlug;
    chips.push({ key: 'category', label: `Category: ${label}` });
  }

  const brandId = searchParams.get('brand');
  if (brandId) {
    const label = brands.find((b) => String(b.id) === brandId)?.name ?? brandId;
    chips.push({ key: 'brand', label: `Brand: ${label}` });
  }

  if (searchParams.get('min_price') || searchParams.get('max_price')) {
    const min = searchParams.get('min_price') ?? '0';
    const max = searchParams.get('max_price') ?? '∞';
    chips.push({ key: 'price', label: `Price: $${min} – $${max}`, removes: ['min_price', 'max_price'] });
  }

  const rating = searchParams.get('min_rating');
  if (rating) chips.push({ key: 'min_rating', label: `Rating: ${rating}★ & up` });

  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {chips.map((chip) => (
        <span
          key={chip.key}
          className="inline-flex items-center gap-1.5 bg-teal-50 text-teal-700 text-xs font-medium px-3 py-1 rounded-full border border-teal-200"
        >
          {chip.label}
          <button
            onClick={() => onRemove(chip.removes ?? [chip.key])}
            className="ml-0.5 hover:text-red-500 transition-colors"
            aria-label={`Remove ${chip.label} filter`}
          >
            <i className="bi bi-x" />
          </button>
        </span>
      ))}
    </div>
  );
});

// ─── Empty State ──────────────────────────────────────────────────────────────
const EmptyState = ({ query, hasFilters, onClearFilters }) => (
  <div className="text-center py-20">
    <i className="bi bi-search text-6xl text-gray-200" />
    <h3 className="text-xl font-semibold text-gray-700 mt-5">No results found</h3>
    <p className="text-gray-400 mt-2 max-w-sm mx-auto">
      {query
        ? <>We couldn&apos;t find anything for <strong>&ldquo;{query}&rdquo;</strong>.</>
        : 'No products match your current filters.'}
    </p>
    {hasFilters && (
      <button
        onClick={onClearFilters}
        className="mt-6 inline-flex items-center gap-2 bg-teal-600 text-white px-5 py-2 rounded-full text-sm font-medium hover:bg-teal-700 transition"
      >
        <i className="bi bi-funnel" /> Clear filters
      </button>
    )}
    <div className="mt-6">
      <Link to="/" className="text-teal-600 hover:underline text-sm">← Back to home</Link>
    </div>
  </div>
);

// ─── SearchResults (main page) ────────────────────────────────────────────────
const SearchResults = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // ── Remote data ─────────────────────────────────────────────────────────
  const [products, setProducts] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);

  // ── Local UI state ───────────────────────────────────────────────────────
  const [sidebarOpen, setSidebarOpen] = useState(false);  // mobile filter drawer
  const [inputValue, setInputValue] = useState(searchParams.get('q') || '');

  const currentPage = Number(searchParams.get('page') || 1);
  const pages = totalPages(totalCount);
  const query = searchParams.get('q') || '';

  // ── Active filter count (for badge) ─────────────────────────────────────
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (searchParams.get('category')) count++;
    if (searchParams.get('brand')) count++;
    if (searchParams.get('min_price') || searchParams.get('max_price')) count++;
    if (searchParams.get('min_rating')) count++;
    return count;
  }, [searchParams]);

  // ── Sync query input with URL on back/forward ────────────────────────────
  useEffect(() => {
    setInputValue(searchParams.get('q') || '');
  }, [searchParams]);

  // ── Fetch static filter data on mount ───────────────────────────────────
  useEffect(() => {
    let alive = true;
    Promise.all([getCategories(), getBrands()])
      .then(([catRes, brandRes]) => {
        if (!alive) return;
        // Flatten nested categories to a single list
        const flatCats = [];
        const flatten = (cats) => {
          cats.forEach((c) => {
            flatCats.push(c);
            if (c.children?.length) flatten(c.children);
          });
        };
        flatten(catRes.data ?? []);
        setCategories(flatCats);
        setBrands(brandRes.data ?? []);
      })
      .catch(() => {/* non-critical — filters remain empty */ });
    return () => { alive = false; };
  }, []);

  // ── Fetch products whenever URL params change ────────────────────────────
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const params = buildParams(searchParams);

    getProducts(params, { signal: controller.signal })
      .then(({ data }) => {
        setProducts(data?.results ?? []);
        setTotalCount(data?.count ?? 0);
      })
      .catch((err) => {
        if (err.name !== 'CanceledError' && err.name !== 'AbortError') {
          setError('Something went wrong. Please try again.');
        }
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [searchParams]);

  // ── Helpers to mutate URL params ─────────────────────────────────────────
  const setParam = useCallback(
    (key, value) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value == null || value === '') next.delete(key);
        else next.set(key, value);
        next.set('page', '1'); // reset to first page on any filter change
        return next;
      });
    },
    [setSearchParams],
  );

  const setParams = useCallback(
    (updates) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        Object.entries(updates).forEach(([k, v]) => {
          if (v == null || v === '') next.delete(k);
          else next.set(k, v);
        });
        next.set('page', '1');
        return next;
      });
    },
    [setSearchParams],
  );

  const clearAllFilters = useCallback(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams();
      if (prev.get('q')) next.set('q', prev.get('q'));
      return next;
    });
  }, [setSearchParams]);

  const removeChips = useCallback(
    (keys) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        keys.forEach((k) => next.delete(k));
        next.set('page', '1');
        return next;
      });
    },
    [setSearchParams],
  );

  // ── Search form submit ────────────────────────────────────────────────────
  const handleSearchSubmit = useCallback(
    (e) => {
      e.preventDefault();
      const q = inputValue.trim();
      if (!q) return;
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('q', q);
        next.set('page', '1');
        return next;
      });
    },
    [inputValue, setSearchParams],
  );

  // ── Page change (scroll to top) ───────────────────────────────────────────
  const handlePageChange = useCallback(
    (page) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('page', String(page));
        return next;
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },
    [setSearchParams],
  );

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <>
      {/* ── Breadcrumb + title ──────────────────────────────────────────── */}
      <div className="bg-gray-50 py-10 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-3">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Search Results</h1>
            {query && (
              <p className="text-gray-500 text-sm mt-1">
                {loading
                  ? 'Searching…'
                  : <>{totalCount} result{totalCount !== 1 ? 's' : ''} for <strong>&ldquo;{query}&rdquo;</strong></>
                }
              </p>
            )}
          </div>
          <nav aria-label="Breadcrumb">
            <ol className="flex items-center gap-2 text-sm text-gray-500">
              <li><Link to="/" className="text-teal-600 hover:underline">Home</Link></li>
              <li aria-hidden>/</li>
              <li className="text-gray-600">Search</li>
              {query && <><li aria-hidden>/</li><li className="text-gray-800 font-medium truncate max-w-xs">{query}</li></>}
            </ol>
          </nav>
        </div>
      </div>

      {/* ── Controls bar ────────────────────────────────────────────────── */}
      <section className="bg-white border-b sticky top-[64px] z-30">
        <div className="container mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
          {/* Left: inline search re-query */}
          <form onSubmit={handleSearchSubmit} className="flex gap-2 flex-1 min-w-0 max-w-sm">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Refine your search…"
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500"
            />
            <button
              type="submit"
              className="bg-teal-600 text-white px-4 py-2 rounded-lg hover:bg-teal-700 transition text-sm flex-shrink-0"
            >
              <i className="bi bi-search" />
            </button>
          </form>

          {/* Right: sort + mobile filter toggle */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <label htmlFor="sort-select" className="text-sm text-gray-600 hidden sm:block">Sort:</label>
            <select
              id="sort-select"
              value={searchParams.get('ordering') || ''}
              onChange={(e) => setParam('ordering', e.target.value || null)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500 bg-white"
            >
              <option value="">Relevance</option>
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>

            {/* Mobile: open filter drawer */}
            <button
              className="lg:hidden flex items-center gap-1.5 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-700 hover:border-teal-500 transition relative"
              onClick={() => setSidebarOpen(true)}
            >
              <i className="bi bi-funnel" /> Filters
              {activeFilterCount > 0 && (
                <span className="absolute -top-1.5 -right-1.5 bg-teal-600 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
                  {activeFilterCount}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Active filter chips */}
        {activeFilterCount > 0 && (
          <div className="container mx-auto px-4 pb-3">
            <ActiveChips
              searchParams={searchParams}
              categories={categories}
              brands={brands}
              onRemove={removeChips}
            />
          </div>
        )}
      </section>

      {/* ── Main content: sidebar + grid ────────────────────────────────── */}
      <div className="container mx-auto px-4 py-8">
        <div className="flex gap-8">

          {/* ── Desktop sidebar ──────────────────────────────────────────── */}
          <div className="hidden lg:block w-56 flex-shrink-0">
            <div className="sticky top-36">
              <FilterSidebar
                categories={categories}
                brands={brands}
                searchParams={searchParams}
                onFilterChange={setParams}
                onClearAll={clearAllFilters}
                activeFilterCount={activeFilterCount}
              />
            </div>
          </div>

          {/* ── Product grid ─────────────────────────────────────────────── */}
          <div className="flex-1 min-w-0">
            {error && (
              <div className="flex items-center gap-3 bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 mb-6">
                <i className="bi bi-exclamation-circle text-lg flex-shrink-0" />
                <p className="text-sm">{error}</p>
                <button
                  onClick={() => setSearchParams(new URLSearchParams(searchParams))}
                  className="ml-auto text-sm underline hover:no-underline flex-shrink-0"
                >
                  Retry
                </button>
              </div>
            )}

            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
                {Array.from({ length: PAGE_SIZE }, (_, i) => <SkeletonCard key={i} />)}
              </div>
            ) : products.length === 0 ? (
              <EmptyState
                query={query}
                hasFilters={activeFilterCount > 0}
                onClearFilters={clearAllFilters}
              />
            ) : (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
                  {products.map((product) => (
                    <ProductCard key={product.id} product={product} />
                  ))}
                </div>

                <Pagination
                  currentPage={currentPage}
                  total={pages}
                  count={totalCount}
                  onPageChange={handlePageChange}
                />
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── Mobile filter drawer ─────────────────────────────────────────── */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          {/* Backdrop */}
          <div
            className="flex-1 bg-black/40"
            onClick={() => setSidebarOpen(false)}
            aria-hidden
          />
          {/* Drawer */}
          <div className="w-72 bg-white h-full overflow-y-auto p-5 shadow-2xl animate-slide-in-right">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-800 text-lg">Filters</h2>
              <button onClick={() => setSidebarOpen(false)} aria-label="Close filters">
                <i className="bi bi-x-lg text-gray-500 hover:text-gray-700 text-xl" />
              </button>
            </div>
            <FilterSidebar
              categories={categories}
              brands={brands}
              searchParams={searchParams}
              onFilterChange={(updates) => { setParams(updates); setSidebarOpen(false); }}
              onClearAll={() => { clearAllFilters(); setSidebarOpen(false); }}
              activeFilterCount={activeFilterCount}
            />
          </div>
        </div>
      )}
    </>
  );
};

export default SearchResults;
