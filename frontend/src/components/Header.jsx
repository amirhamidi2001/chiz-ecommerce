// src/components/Header.jsx
import { useState, useEffect, useRef, useCallback } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useWishlist } from '../context/WishlistContext';
import { useAuth } from '../context/AuthContext';
import { getProducts } from '../services/api';

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
// Extracted as its own component so the dropdown/AbortController lifecycle
// is fully self-contained and doesn't cause Header re-renders.
const SearchBox = ({ className = '', inputClass = '', buttonClass = '', onSubmit }) => {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [isFetching, setIsFetching] = useState(false);
  const wrapperRef = useRef(null);
  const inputRef = useRef(null);
  const debouncedQuery = useDebounce(query, 300);
  const navigate = useNavigate();

  // ── Live suggestions ────────────────────────────────────────────────────
  useEffect(() => {
    const trimmed = debouncedQuery.trim();
    if (trimmed.length < 2) {
      setSuggestions([]);
      setIsOpen(false);
      return;
    }

    const controller = new AbortController();
    setIsFetching(true);

    getProducts({ search: trimmed, page_size: 6 }, { signal: controller.signal })
      .then(({ data }) => {
        const results = data?.results ?? [];
        setSuggestions(results);
        setIsOpen(results.length > 0);
        setActiveIdx(-1);
      })
      .catch(() => {
        /* cancelled or network error — swallow silently */
      })
      .finally(() => setIsFetching(false));

    return () => controller.abort();
  }, [debouncedQuery]);

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

  // ── Keyboard navigation ─────────────────────────────────────────────────
  const handleKeyDown = useCallback(
    (e) => {
      if (!isOpen) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, -1));
      } else if (e.key === 'Enter' && activeIdx >= 0) {
        e.preventDefault();
        const product = suggestions[activeIdx];
        navigate(`/product/${product.slug}`);
        setIsOpen(false);
        setQuery('');
      } else if (e.key === 'Escape') {
        setIsOpen(false);
      }
    },
    [isOpen, activeIdx, suggestions, navigate],
  );

  // ── Submit ──────────────────────────────────────────────────────────────
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

  const handleSuggestionClick = useCallback(
    (product) => {
      navigate(`/product/${product.slug}`);
      setIsOpen(false);
      setQuery('');
    },
    [navigate],
  );

  return (
    <div ref={wrapperRef} className={`relative ${className}`}>
      <form onSubmit={handleSubmit} className="flex border border-emerald-300 rounded-full overflow-hidden w-full shadow-sm">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setIsOpen(true)}
          placeholder="Search for products…"
          className={`flex-1 px-5 py-2 outline-none text-sm bg-white ${inputClass}`}
          autoComplete="off"
          aria-label="Search products"
          aria-autocomplete="list"
          aria-expanded={isOpen}
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
      {isOpen && (
        <ul
          role="listbox"
          className="absolute left-0 right-0 top-full mt-2 bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden"
        >
          {suggestions.map((product, idx) => (
            <li
              key={product.id}
              role="option"
              aria-selected={idx === activeIdx}
              className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors ${idx === activeIdx ? 'bg-emerald-50' : 'hover:bg-gray-50'
                }`}
              onMouseDown={() => handleSuggestionClick(product)}
              onMouseEnter={() => setActiveIdx(idx)}
            >
              {/* Product thumbnail */}
              <img
                src={product.thumbnail || product.image || '/assets/img/product/product-1.webp'}
                alt={product.name}
                className="w-10 h-10 object-cover rounded-lg flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{product.name}</p>
                <p className="text-xs text-gray-500 truncate">
                  {product.brand?.name ?? ''}{product.brand?.name && product.category?.name ? ' · ' : ''}{product.category?.name ?? ''}
                </p>
              </div>
              <span className="text-sm font-semibold text-teal-700 flex-shrink-0">
                ${Number(product.sale_price ?? product.price).toFixed(2)}
              </span>
            </li>
          ))}

          {/* "See all results" footer */}
          <li className="border-t border-gray-100">
            <button
              onMouseDown={handleSubmit}
              className="w-full flex items-center justify-center gap-2 py-3 text-sm text-teal-700 font-medium hover:bg-emerald-50 transition-colors"
            >
              <i className="bi bi-search" />
              See all results for &ldquo;{query}&rdquo;
            </button>
          </li>
        </ul>
      )}
    </div>
  );
};

// ─── Header ───────────────────────────────────────────────────────────────────
const Header = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false);
  const navigate = useNavigate();

  // ── Auth state ──────────────────────────────────────────────────────────
  const { user, isAuthenticated, logout, loading } = useAuth();
  const userName = user
    ? (`${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email?.split('@')[0] || 'User')
    : '';

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  // ── Live counts from context ────────────────────────────────────────────
  const { cartCount } = useCart();
  const { wishlistCount } = useWishlist();

  // Close mobile menu/search when navigating
  const closeMobile = useCallback(() => {
    setMobileMenuOpen(false);
    setMobileSearchOpen(false);
  }, []);

  // Close mobile search after submitting
  const handleMobileSearchSubmit = useCallback(
    (q) => {
      navigate(`/search?q=${encodeURIComponent(q)}`);
      setMobileSearchOpen(false);
    },
    [navigate],
  );

  return (
    <header className="sticky top-0 z-50 bg-white shadow-md">
      {/* ========== Top Bar ========== */}
      <div className="hidden lg:block bg-emerald-100 text-sm py-2 border-b border-emerald-200">
        <div className="container mx-auto px-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <i className="bi bi-telephone-fill text-emerald-600" />
            <span className="text-emerald-600">Need help? Call us:</span>
            <a href="tel:+1234567890" className="text-teal-700 hover:underline">+1 (234) 567-890</a>
          </div>

          <div className="flex gap-6">
            <div className="overflow-hidden h-6">
              <div className="animate-marquee whitespace-nowrap text-teal-700 font-medium">
                🚚 Free shipping on orders over $50 &nbsp;&nbsp;|&nbsp;&nbsp;
                💰 30 days money back guarantee &nbsp;&nbsp;|&nbsp;&nbsp;
                🎁 20% off on your first order
              </div>
            </div>

            <div className="flex gap-3">
              <div className="dropdown relative group">
                <button className="flex items-center gap-1 text-emerald-700 hover:text-teal-700">
                  <i className="bi bi-translate" /> EN <i className="bi bi-chevron-down text-xs" />
                </button>
                <div className="absolute right-0 mt-2 w-32 bg-white shadow-lg rounded-md hidden group-hover:block z-10">
                  <a href="#" className="block px-4 py-2 text-sm hover:bg-emerald-100">English</a>
                  <a href="#" className="block px-4 py-2 text-sm hover:bg-emerald-100">Español</a>
                </div>
              </div>
              <div className="dropdown relative group">
                <button className="flex items-center gap-1 text-emerald-700 hover:text-teal-700">
                  <i className="bi bi-currency-dollar" /> USD <i className="bi bi-chevron-down text-xs" />
                </button>
                <div className="absolute right-0 mt-2 w-32 bg-white shadow-lg rounded-md hidden group-hover:block z-10">
                  <a href="#" className="block px-4 py-2 text-sm hover:bg-emerald-100">USD</a>
                  <a href="#" className="block px-4 py-2 text-sm hover:bg-emerald-100">EUR</a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ========== Main Header ========== */}
      <div className="container mx-auto px-4 py-4 flex items-center justify-between gap-4">
        <Link to="/" className="text-2xl font-bold text-emerald-800 flex-shrink-0">
          Chiz
        </Link>

        {/* Desktop search — visible md+ */}
        <SearchBox className="hidden md:block w-96 flex-shrink-0" />

        <div className="flex items-center gap-4">
          {/* Mobile search toggle */}
          <button
            className="md:hidden text-emerald-700 text-xl"
            onClick={() => setMobileSearchOpen(!mobileSearchOpen)}
            aria-label="Toggle search"
          >
            <i className="bi bi-search" />
          </button>

          {/* ── Account dropdown ─────────────────────────────────────────── */}
          <div className="dropdown relative group">
            <button className="text-emerald-700 text-xl hover:text-teal-700" aria-label="Account">
              <i className="bi bi-person" />
            </button>

            <div className="absolute right-0 mt-3 w-64 bg-white shadow-xl rounded-lg hidden group-hover:block z-10 border border-emerald-100 before:content-[''] before:absolute before:-top-3 before:left-0 before:w-full before:h-3">
              {!loading && (
                <>
                  {isAuthenticated ? (
                    <>
                      <div className="p-4 border-b">
                        <h6 className="font-semibold">Welcome back, {userName}!</h6>
                        <p className="text-xs text-emerald-500">Manage your account &amp; orders</p>
                      </div>
                      <div className="py-2">
                        <Link to="/account?tab=orders" className="block px-4 py-2 text-sm hover:bg-emerald-50">Orders</Link>
                        <Link to="/account?tab=wishlist" className="block px-4 py-2 text-sm hover:bg-emerald-50">Wishlist</Link>
                        <Link to="/account?tab=addresses" className="block px-4 py-2 text-sm hover:bg-emerald-50">Addresses</Link>
                        <Link to="/account?tab=settings" className="block px-4 py-2 text-sm hover:bg-emerald-50">Settings</Link>
                        <button
                          onClick={handleLogout}
                          className="w-full text-left block px-4 py-2 text-sm hover:bg-red-50 text-red-600"
                        >
                          <i className="bi bi-box-arrow-right me-1" /> Logout
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="p-4 border-b">
                        <h6 className="font-semibold">Welcome to Chiz</h6>
                        <p className="text-xs text-emerald-500">Access account &amp; manage orders</p>
                      </div>
                      <div className="py-2">
                        <Link to="/login" className="block px-4 py-2 text-sm hover:bg-emerald-50">Sign In</Link>
                        <Link to="/login?mode=register" className="block px-4 py-2 text-sm hover:bg-emerald-50">Register</Link>
                      </div>
                      <div className="p-4 border-t bg-emerald-50 flex gap-2">
                        <Link to="/login" className="flex-1 text-center bg-teal-700 text-white py-1 rounded text-sm">Sign In</Link>
                        <Link to="/login?mode=register" className="flex-1 text-center border border-teal-700 text-teal-700 py-1 rounded text-sm">Register</Link>
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          </div>

          {/* ── Wishlist ─────────────────────────────────────────────────── */}
          <Link to="/account?tab=wishlist" className="relative text-emerald-700 text-xl hover:text-teal-700" aria-label="Wishlist">
            <i className="bi bi-heart" />
            <span className="absolute -top-2 -right-3 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
              {wishlistCount > 99 ? '99+' : wishlistCount}
            </span>
          </Link>

          {/* ── Cart ─────────────────────────────────────────────────────── */}
          <Link to="/cart" className="relative text-emerald-700 text-xl hover:text-teal-700" aria-label="Cart">
            <i className="bi bi-cart3" />
            <span className="absolute -top-2 -right-3 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
              {cartCount}
            </span>
          </Link>

          <button
            className="md:hidden text-emerald-700 text-2xl"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            <i className="bi bi-list" />
          </button>
        </div>
      </div>

      {/* ========== Desktop Navigation ========== */}
      <nav className="hidden md:block bg-emerald-800 text-white">
        <div className="container mx-auto px-4">
          <ul className="flex space-x-6">
            <li><NavLink to="/" className={({ isActive }) => `block py-3 ${isActive ? 'text-teal-400' : 'hover:text-teal-400'}`}>Home</NavLink></li>
            <li><NavLink to="/about" className="block py-3 hover:text-teal-400">About</NavLink></li>
            <li><NavLink to="/category" className="block py-3 hover:text-teal-400">Category</NavLink></li>
            <li><NavLink to="/cart" className="block py-3 hover:text-teal-400">Cart</NavLink></li>
            <li><NavLink to="/checkout" className="block py-3 hover:text-teal-400">Checkout</NavLink></li>
            <li><NavLink to="/blog" className="block py-3 hover:text-teal-400">Blog</NavLink></li>
            <li><NavLink to="/contact" className="block py-3 hover:text-teal-400">Contact</NavLink></li>
          </ul>
        </div>
      </nav>

      {/* ========== Mobile Search ========== */}
      {mobileSearchOpen && (
        <div className="md:hidden bg-white p-4 border-t shadow-lg">
          <SearchBox onSubmit={handleMobileSearchSubmit} />
        </div>
      )}

      {/* ========== Mobile Menu ========== */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-white border-t shadow-lg p-4">
          <ul className="space-y-3">
            <li><Link to="/" onClick={closeMobile} className="block text-emerald-800">Home</Link></li>
            <li><Link to="/about" onClick={closeMobile} className="block text-emerald-800">About</Link></li>
            <li><Link to="/category" onClick={closeMobile} className="block text-emerald-800">Category</Link></li>
            <li><Link to="/cart" onClick={closeMobile} className="block text-emerald-800">Cart</Link></li>
            <li><Link to="/checkout" onClick={closeMobile} className="block text-emerald-800">Checkout</Link></li>
            <li><Link to="/blog" onClick={closeMobile} className="block text-emerald-800">Blog</Link></li>
            <li><Link to="/contact" onClick={closeMobile} className="block text-emerald-800">Contact</Link></li>
          </ul>
        </div>
      )}
    </header>
  );
};

export default Header;
