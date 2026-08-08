// src/pages/Category.jsx
import { useState, useEffect, useCallback, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getProducts, getCategories, getBrands, getColors } from '../services/api';
import { useCart } from '../context/CartContext';

// ─── Loading Spinner ────────────────────────────────────────────────────────
const Spinner = () => (
  <div className="flex justify-center items-center py-20">
    <div className="w-10 h-10 border-4 border-teal-600 border-t-transparent rounded-full animate-spin"></div>
  </div>
);

// ─── Error State ────────────────────────────────────────────────────────────
const ErrorState = ({ message, onRetry }) => (
  <div className="flex flex-col items-center justify-center py-20 text-center">
    <i className="bi bi-exclamation-triangle text-5xl text-red-400 mb-4"></i>
    <h3 className="text-xl font-semibold text-gray-700 mb-2">Something went wrong</h3>
    <p className="text-gray-500 mb-6">{message}</p>
    <button
      onClick={onRetry}
      className="bg-teal-600 text-white px-6 py-2 rounded-lg hover:bg-teal-700 transition"
    >
      Try Again
    </button>
  </div>
);

// ─── Empty State ─────────────────────────────────────────────────────────────
const EmptyState = ({ onClear }) => (
  <div className="flex flex-col items-center justify-center py-20 text-center">
    <i className="bi bi-search text-5xl text-gray-300 mb-4"></i>
    <h3 className="text-xl font-semibold text-gray-600 mb-2">No products found</h3>
    <p className="text-gray-400 mb-6">Try adjusting your filters or search term.</p>
    <button
      onClick={onClear}
      className="bg-teal-600 text-white px-6 py-2 rounded-lg hover:bg-teal-700 transition"
    >
      Clear Filters
    </button>
  </div>
);

// ─── Toast notification ──────────────────────────────────────────────────────
const Toast = ({ message, type, onClose }) => {
  useEffect(() => {
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-lg text-white transition-all ${type === 'success' ? 'bg-teal-600' : 'bg-red-500'
        }`}
    >
      <i className={`bi ${type === 'success' ? 'bi-check-circle' : 'bi-exclamation-circle'}`}></i>
      <span className="text-sm font-medium">{message}</span>
      <button onClick={onClose} className="ml-2 opacity-70 hover:opacity-100">
        <i className="bi bi-x"></i>
      </button>
    </div>
  );
};

// ─── Product Card ─────────────────────────────────────────────────────────────
const ProductCard = ({ product, onAddToCart }) => {
  const [hovered, setHovered] = useState(false);
  const [adding, setAdding] = useState(false);

  const images = product.images || [];
  const hoverImage = images.length > 1 ? images[1].image : null;
  const mainImage = product.thumbnail_url || (images[0]?.image) || '/assets/img/product/product-2.webp';

  const handleAdd = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setAdding(true);
    await onAddToCart(product.id);
    setAdding(false);
  };

  return (
    <div
      className="group bg-white rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all duration-300"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="relative overflow-hidden">
        <img
          src={hovered && hoverImage ? hoverImage : mainImage}
          alt={product.name}
          className="w-full h-64 object-cover transition-transform duration-500 group-hover:scale-105"
          onError={(e) => { e.target.src = '/assets/img/product/product-2.webp'; }}
        />
        {/* Overlay Actions */}
        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center gap-3">
          <Link
            to={`/product/${product.slug}`}
            className="bg-white p-2 rounded-full hover:bg-teal-600 hover:text-white transition"
            title="View Details"
          >
            <i className="bi bi-eye"></i>
          </Link>
          <button
            onClick={handleAdd}
            disabled={adding || product.stock === 0}
            className="bg-white p-2 rounded-full hover:bg-teal-600 hover:text-white transition disabled:opacity-50 disabled:cursor-not-allowed"
            title="Add to Cart"
          >
            {adding
              ? <i className="bi bi-arrow-clockwise animate-spin"></i>
              : <i className="bi bi-cart-plus"></i>
            }
          </button>
        </div>
        {/* Badges */}
        {product.is_new && (
          <span className="absolute top-3 left-3 bg-teal-500 text-white text-xs font-semibold px-2 py-1 rounded">
            New
          </span>
        )}
        {product.is_sale && !product.is_new && (
          <span className="absolute top-3 left-3 bg-red-500 text-white text-xs font-semibold px-2 py-1 rounded">
            Sale
          </span>
        )}
        {product.discount_percent > 0 && (
          <span className="absolute top-3 right-3 bg-orange-500 text-white text-xs font-bold px-2 py-1 rounded">
            -{product.discount_percent}%
          </span>
        )}
        {product.stock === 0 && (
          <span className="absolute top-3 left-3 bg-gray-600 text-white text-xs font-semibold px-2 py-1 rounded">
            Out of Stock
          </span>
        )}
      </div>
      <div className="p-4">
        <div className="text-xs text-gray-500 uppercase tracking-wider">
          {product.category?.name || '—'}
        </div>
        <h4 className="font-semibold text-lg mt-1 line-clamp-1">
          <Link to={`/product/${product.slug}`} className="hover:text-teal-600">
            {product.name}
          </Link>
        </h4>
        <div className="flex justify-between items-center mt-2">
          <div>
            {product.original_price ? (
              <>
                <span className="text-lg font-bold text-teal-700">${Number(product.price).toFixed(2)}</span>
                <span className="text-sm text-gray-400 line-through ml-2">${Number(product.original_price).toFixed(2)}</span>
              </>
            ) : (
              <span className="text-lg font-bold text-gray-800">${Number(product.price).toFixed(2)}</span>
            )}
          </div>
          <div className="flex items-center gap-1 text-sm">
            <i className="bi bi-star-fill text-yellow-400"></i>
            <span>{product.rating}</span>
            <span className="text-gray-400">({product.reviews_count})</span>
          </div>
        </div>
        {/* Add to Cart button below card */}
        <button
          onClick={handleAdd}
          disabled={adding || product.stock === 0}
          className={`mt-3 w-full py-2 rounded-lg text-sm font-medium transition flex items-center justify-center gap-2 ${product.stock === 0
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-teal-600 hover:bg-teal-700 text-white'
            }`}
        >
          {adding ? (
            <><i className="bi bi-arrow-clockwise animate-spin"></i> Adding…</>
          ) : product.stock === 0 ? (
            'Out of Stock'
          ) : (
            <><i className="bi bi-cart-plus"></i> Add to Cart</>
          )}
        </button>
      </div>
    </div>
  );
};

// ─── Category Tree ────────────────────────────────────────────────────────────
const CategoryTree = ({ categories, selectedCategory, onSelectCategory, loading }) => {
  const [open, setOpen] = useState({});
  const toggle = (id) => setOpen((prev) => ({ ...prev, [id]: !prev[id] }));

  if (loading) return (
    <div className="widget-item mb-6">
      <h3 className="text-lg font-semibold border-l-4 border-teal-600 pl-3 mb-4">Categories</h3>
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-5 bg-gray-100 rounded animate-pulse" />
        ))}
      </div>
    </div>
  );

  return (
    <div className="widget-item mb-6">
      <h3 className="text-lg font-semibold border-l-4 border-teal-600 pl-3 mb-4">Categories</h3>
      <ul className="space-y-2">
        <li>
          <button
            onClick={() => onSelectCategory('')}
            className={`text-gray-700 hover:text-teal-600 ${!selectedCategory ? 'text-teal-600 font-medium' : ''}`}
          >
            All Categories
          </button>
        </li>
        {categories.map((cat) => (
          <li key={cat.id}>
            <div className="flex justify-between items-center">
              <button
                onClick={() => onSelectCategory(cat.slug)}
                className={`text-gray-700 hover:text-teal-600 ${selectedCategory === cat.slug ? 'text-teal-600 font-medium' : ''}`}
              >
                {cat.name}
              </button>
              {cat.children?.length > 0 && (
                <button onClick={() => toggle(cat.id)} className="text-gray-400 hover:text-teal-600">
                  <i className={`bi bi-chevron-${open[cat.id] ? 'up' : 'down'}`}></i>
                </button>
              )}
            </div>
            {open[cat.id] && cat.children?.length > 0 && (
              <ul className="pl-4 mt-2 space-y-1">
                {cat.children.map((sub) => (
                  <li key={sub.id}>
                    <button
                      onClick={() => onSelectCategory(sub.slug)}
                      className={`text-sm text-gray-500 hover:text-teal-600 ${selectedCategory === sub.slug ? 'text-teal-600 font-medium' : ''}`}
                    >
                      {sub.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};

// ─── Price Range Slider ───────────────────────────────────────────────────────
const PriceRangeSlider = ({ minPrice, maxPrice, onPriceChange }) => {
  const [minVal, setMinVal] = useState(minPrice);
  const [maxVal, setMaxVal] = useState(maxPrice);
  const GLOBAL_MIN = 0;
  const GLOBAL_MAX = 1000;

  useEffect(() => { setMinVal(minPrice); }, [minPrice]);
  useEffect(() => { setMaxVal(maxPrice); }, [maxPrice]);

  const handleMin = (e) => {
    const val = Math.min(Number(e.target.value), maxVal - 10);
    setMinVal(val);
    onPriceChange({ min: val, max: maxVal });
  };
  const handleMax = (e) => {
    const val = Math.max(Number(e.target.value), minVal + 10);
    setMaxVal(val);
    onPriceChange({ min: minVal, max: val });
  };

  return (
    <div className="widget-item mb-6">
      <h3 className="text-lg font-semibold border-l-4 border-teal-600 pl-3 mb-4">Price Range</h3>
      <div className="mb-3 flex justify-between text-sm font-medium">
        <span>${minVal}</span>
        <span>${maxVal}</span>
      </div>
      <div className="relative h-1 bg-gray-200 rounded">
        <div
          className="absolute h-1 bg-teal-600 rounded"
          style={{ left: `${(minVal / GLOBAL_MAX) * 100}%`, right: `${100 - (maxVal / GLOBAL_MAX) * 100}%` }}
        />
        <input
          type="range" min={GLOBAL_MIN} max={GLOBAL_MAX} step={10} value={minVal}
          onChange={handleMin}
          className="absolute w-full top-0 left-0 appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-teal-600 [&::-webkit-slider-thumb]:cursor-pointer"
        />
        <input
          type="range" min={GLOBAL_MIN} max={GLOBAL_MAX} step={10} value={maxVal}
          onChange={handleMax}
          className="absolute w-full top-0 left-0 appearance-none bg-transparent pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-teal-600 [&::-webkit-slider-thumb]:cursor-pointer"
        />
      </div>
      <div className="flex gap-2 mt-4">
        <input type="number" value={minVal} onChange={handleMin} className="w-1/2 border rounded px-2 py-1 text-sm" />
        <input type="number" value={maxVal} onChange={handleMax} className="w-1/2 border rounded px-2 py-1 text-sm" />
      </div>
    </div>
  );
};

// ─── Color Filter ─────────────────────────────────────────────────────────────
const ColorFilter = ({ colors, selectedColors, onToggle, loading }) => {
  if (loading) return (
    <div className="widget-item mb-6">
      <h3 className="text-lg font-semibold border-l-4 border-teal-600 pl-3 mb-4">Filter by Color</h3>
      <div className="flex flex-wrap gap-2">
        {[...Array(8)].map((_, i) => <div key={i} className="w-8 h-8 rounded-full bg-gray-200 animate-pulse" />)}
      </div>
    </div>
  );

  return (
    <div className="widget-item mb-6">
      <h3 className="text-lg font-semibold border-l-4 border-teal-600 pl-3 mb-4">Filter by Color</h3>
      <div className="flex flex-wrap gap-2">
        {colors.map((color) => (
          <label key={color.id} className="relative cursor-pointer" title={color.name}>
            <input
              type="checkbox"
              value={color.name}
              checked={selectedColors.includes(color.name)}
              onChange={() => onToggle(color.name)}
              className="sr-only peer"
            />
            <span
              className="block w-8 h-8 rounded-full border-2 border-gray-300 peer-checked:border-teal-600 peer-checked:ring-2 peer-checked:ring-teal-300 transition"
              style={{
                backgroundColor: color.hex_code,
                boxShadow: color.hex_code?.toLowerCase() === '#ffffff' ? 'inset 0 0 0 1px #ccc' : 'none',
              }}
            />
          </label>
        ))}
      </div>
    </div>
  );
};

// ─── Brand Filter ─────────────────────────────────────────────────────────────
const BrandFilter = ({ brands, selectedBrands, onToggle, onClear, loading }) => {
  const [search, setSearch] = useState('');
  const filtered = brands.filter((b) => b.name.toLowerCase().includes(search.toLowerCase()));

  if (loading) return (
    <div className="widget-item mb-6">
      <h3 className="text-lg font-semibold border-l-4 border-teal-600 pl-3 mb-4">Filter by Brand</h3>
      <div className="space-y-2">
        {[...Array(6)].map((_, i) => <div key={i} className="h-5 bg-gray-100 rounded animate-pulse" />)}
      </div>
    </div>
  );

  return (
    <div className="widget-item mb-6">
      <h3 className="text-lg font-semibold border-l-4 border-teal-600 pl-3 mb-4">Filter by Brand</h3>
      <div className="relative mb-3">
        <input
          type="text"
          placeholder="Search brands..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full border rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-teal-500"
        />
        <i className="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
      </div>
      <div className="max-h-56 overflow-y-auto space-y-2">
        {filtered.map((brand) => (
          <label key={brand.id} className="flex justify-between items-center cursor-pointer">
            <span className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={selectedBrands.includes(brand.slug)}
                onChange={() => onToggle(brand.slug)}
                className="rounded text-teal-600 focus:ring-teal-500"
              />
              <span className="text-sm">{brand.name}</span>
            </span>
          </label>
        ))}
        {filtered.length === 0 && <p className="text-sm text-gray-400">No brands found.</p>}
      </div>
      <div className="mt-3">
        <button onClick={onClear} className="text-sm text-teal-600 hover:underline">Clear All</button>
      </div>
    </div>
  );
};

// ─── Main Category Page ───────────────────────────────────────────────────────
const Category = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { addToCart } = useCart();

  // ── Filter state ────────────────────────────────────────────────────────────
  const [selectedCategory, setSelectedCategory] = useState(searchParams.get('category') || '');
  const [priceRange, setPriceRange] = useState({ min: 0, max: 1000 });
  const [selectedColors, setSelectedColors] = useState([]);
  const [selectedBrands, setSelectedBrands] = useState([]);
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '');
  const [sortBy, setSortBy] = useState('-created_at');
  const [viewMode, setViewMode] = useState('grid');
  const [itemsPerPage, setItemsPerPage] = useState(12);
  const [currentPage, setCurrentPage] = useState(1);

  // ── Data state ──────────────────────────────────────────────────────────────
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);
  const [colors, setColors] = useState([]);
  const [pagination, setPagination] = useState({ count: 0, total_pages: 1 });

  // ── Loading / error ─────────────────────────────────────────────────────────
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [error, setError] = useState(null);

  // ── Toast ───────────────────────────────────────────────────────────────────
  const [toast, setToast] = useState(null);
  const showToast = (message, type = 'success') => setToast({ message, type });
  const hideToast = () => setToast(null);

  const searchTimer = useRef(null);

  // ── Fetch sidebar meta once ─────────────────────────────────────────────────
  useEffect(() => {
    const fetchMeta = async () => {
      try {
        const [catRes, brandRes, colorRes] = await Promise.all([
          getCategories(),
          getBrands(),
          getColors(),
        ]);
        setCategories(Array.isArray(catRes.data) ? catRes.data : catRes.data.results || []);
        setBrands(Array.isArray(brandRes.data) ? brandRes.data : brandRes.data.results || []);
        setColors(Array.isArray(colorRes.data) ? colorRes.data : colorRes.data.results || []);
      } catch (err) {
        console.error('Failed to load sidebar data:', err);
      } finally {
        setLoadingMeta(false);
      }
    };
    fetchMeta();
  }, []);

  // ── Fetch products whenever filters change ──────────────────────────────────
  const fetchProducts = useCallback(async () => {
    setLoadingProducts(true);
    setError(null);
    try {
      const params = {
        page: currentPage,
        page_size: itemsPerPage,
        ordering: sortBy,
      };
      if (selectedCategory) params.category = selectedCategory;
      if (searchQuery.trim()) params.search = searchQuery.trim();
      if (selectedBrands.length) params.brand = selectedBrands.join(',');
      if (selectedColors.length) params.color = selectedColors.join(',');
      if (priceRange.min > 0) params.min_price = priceRange.min;
      if (priceRange.max < 1000) params.max_price = priceRange.max;

      const res = await getProducts(params);
      const data = res.data;
      setProducts(data.results || []);
      setPagination({ count: data.count, total_pages: data.total_pages });
    } catch (err) {
      setError(err.message || 'Failed to load products');
    } finally {
      setLoadingProducts(false);
    }
  }, [currentPage, itemsPerPage, sortBy, selectedCategory, searchQuery, selectedBrands, selectedColors, priceRange]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  // ── Handlers ────────────────────────────────────────────────────────────────
  const toggleColor = (name) => {
    setSelectedColors((prev) => prev.includes(name) ? prev.filter((c) => c !== name) : [...prev, name]);
    setCurrentPage(1);
  };

  const toggleBrand = (slug) => {
    setSelectedBrands((prev) => prev.includes(slug) ? prev.filter((b) => b !== slug) : [...prev, slug]);
    setCurrentPage(1);
  };

  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchQuery(val);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => setCurrentPage(1), 400);
  };

  const clearAllFilters = () => {
    setSelectedCategory('');
    setPriceRange({ min: 0, max: 1000 });
    setSelectedColors([]);
    setSelectedBrands([]);
    setSearchQuery('');
    setSortBy('-created_at');
    setCurrentPage(1);
  };

  // ── Add to cart handler ─────────────────────────────────────────────────────
  const handleAddToCart = async (productId) => {
    const result = await addToCart(productId, 1);
    showToast(result.message, result.success ? 'success' : 'error');
  };

  // ── Active filters chips ────────────────────────────────────────────────────
  const activeFilters = [];
  if (selectedCategory) {
    activeFilters.push({
      type: 'Category',
      value: categories.find((c) => c.slug === selectedCategory)?.name || selectedCategory,
      clear: () => { setSelectedCategory(''); setCurrentPage(1); },
    });
  }
  selectedBrands.forEach((slug) => {
    activeFilters.push({
      type: 'Brand',
      value: brands.find((b) => b.slug === slug)?.name || slug,
      clear: () => toggleBrand(slug),
    });
  });
  selectedColors.forEach((name) => {
    activeFilters.push({
      type: 'Color',
      value: name,
      clear: () => toggleColor(name),
    });
  });
  if (priceRange.min > 0 || priceRange.max < 1000) {
    activeFilters.push({
      type: 'Price',
      value: `$${priceRange.min} – $${priceRange.max}`,
      clear: () => { setPriceRange({ min: 0, max: 1000 }); setCurrentPage(1); },
    });
  }
  if (searchQuery.trim()) {
    activeFilters.push({
      type: 'Search',
      value: searchQuery,
      clear: () => { setSearchQuery(''); setCurrentPage(1); },
    });
  }

  const totalPages = pagination.total_pages || 1;

  const getPageNumbers = () => {
    const pages = [];
    const range = 2;
    for (
      let i = Math.max(1, currentPage - range);
      i <= Math.min(totalPages, currentPage + range);
      i++
    ) {
      pages.push(i);
    }
    return pages;
  };

  return (
    <>
      {/* Toast */}
      {toast && <Toast message={toast.message} type={toast.type} onClose={hideToast} />}

      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Product Category</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Category</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Main Section */}
      <section className="py-12 bg-white">
        <div className="container mx-auto px-4">
          <div className="flex flex-col lg:flex-row gap-8">
            {/* ── Sidebar ────────────────────────────────────────────────────── */}
            <aside className="lg:w-1/4 xl:w-1/5">
              {/* Search */}
              <div className="widget-item mb-6">
                <h3 className="text-lg font-semibold border-l-4 border-teal-600 pl-3 mb-4">Search</h3>
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Search products..."
                    value={searchQuery}
                    onChange={handleSearchChange}
                    className="w-full border border-gray-300 rounded-lg pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-teal-500"
                  />
                  <i className="bi bi-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
                </div>
              </div>

              <CategoryTree
                categories={categories}
                selectedCategory={selectedCategory}
                onSelectCategory={(slug) => { setSelectedCategory(slug); setCurrentPage(1); }}
                loading={loadingMeta}
              />

              <PriceRangeSlider
                minPrice={priceRange.min}
                maxPrice={priceRange.max}
                onPriceChange={(range) => { setPriceRange(range); setCurrentPage(1); }}
              />

              <ColorFilter
                colors={colors}
                selectedColors={selectedColors}
                onToggle={toggleColor}
                loading={loadingMeta}
              />

              <BrandFilter
                brands={brands}
                selectedBrands={selectedBrands}
                onToggle={toggleBrand}
                onClear={() => { setSelectedBrands([]); setCurrentPage(1); }}
                loading={loadingMeta}
              />

              {activeFilters.length > 0 && (
                <button
                  onClick={clearAllFilters}
                  className="w-full mt-2 py-2 border border-red-300 text-red-600 rounded-lg text-sm hover:bg-red-50 transition"
                >
                  <i className="bi bi-x-circle me-2"></i>Clear All Filters
                </button>
              )}
            </aside>

            {/* ── Main Content ─────────────────────────────────────────────── */}
            <main className="flex-1 min-w-0">
              {/* Sort & View Controls */}
              <div className="bg-gray-50 rounded-xl p-4 mb-6">
                <div className="flex flex-col sm:flex-row gap-3">
                  {/* Sort */}
                  <div className="flex-1">
                    <label className="block text-sm font-medium mb-1">Sort By</label>
                    <select
                      value={sortBy}
                      onChange={(e) => { setSortBy(e.target.value); setCurrentPage(1); }}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-teal-500"
                    >
                      <option value="-created_at">Newest First</option>
                      <option value="created_at">Oldest First</option>
                      <option value="price">Price: Low to High</option>
                      <option value="-price">Price: High to Low</option>
                      <option value="-rating">Top Rated</option>
                      <option value="name">Name: A–Z</option>
                      <option value="-name">Name: Z–A</option>
                    </select>
                  </div>
                  {/* Per page */}
                  <div>
                    <label className="block text-sm font-medium mb-1">Items Per Page</label>
                    <select
                      value={itemsPerPage}
                      onChange={(e) => { setItemsPerPage(Number(e.target.value)); setCurrentPage(1); }}
                      className="w-full border rounded-lg px-3 py-2 text-sm"
                    >
                      <option value={12}>12 per page</option>
                      <option value={24}>24 per page</option>
                      <option value={48}>48 per page</option>
                    </select>
                  </div>
                </div>

                {/* View toggle + count */}
                <div className="flex justify-between items-center mt-4">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-500">View:</span>
                    <button
                      onClick={() => setViewMode('grid')}
                      className={`p-2 rounded ${viewMode === 'grid' ? 'bg-teal-600 text-white' : 'bg-gray-200 text-gray-700'}`}
                    >
                      <i className="bi bi-grid-3x3-gap-fill"></i>
                    </button>
                    <button
                      onClick={() => setViewMode('list')}
                      className={`p-2 rounded ${viewMode === 'list' ? 'bg-teal-600 text-white' : 'bg-gray-200 text-gray-700'}`}
                    >
                      <i className="bi bi-list-ul"></i>
                    </button>
                  </div>
                  <div className="text-sm text-gray-500">
                    {loadingProducts
                      ? 'Loading...'
                      : `${pagination.count} product${pagination.count !== 1 ? 's' : ''} found`}
                  </div>
                </div>
              </div>

              {/* Active Filter Chips */}
              {activeFilters.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 mb-6 p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm font-medium">Active Filters:</span>
                  {activeFilters.map((f, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1 bg-teal-100 text-teal-700 text-xs px-2 py-1 rounded-full"
                    >
                      {f.type}: {f.value}
                      <button onClick={f.clear} className="ml-1 hover:text-teal-900">
                        <i className="bi bi-x"></i>
                      </button>
                    </span>
                  ))}
                  <button onClick={clearAllFilters} className="text-xs text-red-500 hover:underline ml-auto">
                    Clear All
                  </button>
                </div>
              )}

              {/* Product Grid / List / Loading / Empty / Error */}
              {loadingProducts ? (
                <Spinner />
              ) : error ? (
                <ErrorState message={error} onRetry={fetchProducts} />
              ) : products.length === 0 ? (
                <EmptyState onClear={clearAllFilters} />
              ) : viewMode === 'grid' ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                  {products.map((product) => (
                    <ProductCard key={product.id} product={product} onAddToCart={handleAddToCart} />
                  ))}
                </div>
              ) : (
                <div className="space-y-4">
                  {products.map((product) => {
                    const img = product.thumbnail_url || '/assets/img/product/product-2.webp';
                    return (
                      <div key={product.id} className="flex gap-4 bg-white rounded-xl shadow-sm p-4">
                        <img
                          src={img}
                          alt={product.name}
                          className="w-32 h-32 object-cover rounded-lg flex-shrink-0"
                          onError={(e) => { e.target.src = '/assets/img/product/product-2.webp'; }}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs text-gray-500">{product.category?.name}</div>
                          <h4 className="font-semibold text-lg truncate">{product.name}</h4>
                          <div className="flex items-center gap-2 mt-1">
                            <i className="bi bi-star-fill text-yellow-400 text-sm"></i>
                            <span className="text-sm text-gray-700">{product.rating}</span>
                            <span className="text-sm text-gray-400">({product.reviews_count} reviews)</span>
                          </div>
                          <div className="mt-2">
                            {product.original_price ? (
                              <>
                                <span className="text-xl font-bold text-teal-700">${Number(product.price).toFixed(2)}</span>
                                <span className="text-gray-400 line-through ml-2">${Number(product.original_price).toFixed(2)}</span>
                              </>
                            ) : (
                              <span className="text-xl font-bold">${Number(product.price).toFixed(2)}</span>
                            )}
                          </div>
                          <div className="mt-3 flex gap-2">
                            <button
                              onClick={() => handleAddToCart(product.id)}
                              disabled={product.stock === 0}
                              className="bg-teal-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-1"
                            >
                              <i className="bi bi-cart-plus"></i>
                              {product.stock === 0 ? 'Out of Stock' : 'Add to Cart'}
                            </button>
                            <Link
                              to={`/product/${product.slug}`}
                              className="border border-gray-300 px-4 py-1.5 rounded-lg text-sm hover:bg-gray-50 flex items-center gap-1"
                            >
                              <i className="bi bi-eye"></i> View
                            </Link>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Pagination */}
              {!loadingProducts && totalPages > 1 && (
                <div className="flex justify-center mt-8">
                  <nav className="flex items-center gap-1">
                    <button
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                      className="px-3 py-1 border rounded-md disabled:opacity-50 hover:bg-gray-100"
                    >
                      <i className="bi bi-chevron-left"></i> Prev
                    </button>

                    {currentPage > 3 && (
                      <>
                        <button onClick={() => setCurrentPage(1)} className="px-3 py-1 border rounded-md hover:bg-gray-100">1</button>
                        {currentPage > 4 && <span className="px-2">…</span>}
                      </>
                    )}

                    {getPageNumbers().map((num) => (
                      <button
                        key={num}
                        onClick={() => setCurrentPage(num)}
                        className={`px-3 py-1 border rounded-md ${currentPage === num ? 'bg-teal-600 text-white border-teal-600' : 'hover:bg-gray-100'}`}
                      >
                        {num}
                      </button>
                    ))}

                    {currentPage < totalPages - 2 && (
                      <>
                        {currentPage < totalPages - 3 && <span className="px-2">…</span>}
                        <button onClick={() => setCurrentPage(totalPages)} className="px-3 py-1 border rounded-md hover:bg-gray-100">
                          {totalPages}
                        </button>
                      </>
                    )}

                    <button
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      disabled={currentPage === totalPages}
                      className="px-3 py-1 border rounded-md disabled:opacity-50 hover:bg-gray-100"
                    >
                      Next <i className="bi bi-chevron-right"></i>
                    </button>
                  </nav>
                </div>
              )}
            </main>
          </div>
        </div>
      </section>
    </>
  );
};

export default Category;
