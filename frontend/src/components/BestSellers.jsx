// src/components/BestSellers.jsx
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getProducts } from '../services/api';

// ─── Shared star renderer ───────────────────────────────────────────────────
const Stars = ({ rating }) => {
  const full = Math.floor(Number(rating));
  const half = Number(rating) % 1 >= 0.5;
  return (
    <div className="flex items-center gap-0.5">
      {[...Array(5)].map((_, i) => (
        <i
          key={i}
          className={`bi text-sm ${
            i < full
              ? 'bi-star-fill text-yellow-400'
              : i === full && half
              ? 'bi-star-half text-yellow-400'
              : 'bi-star text-gray-300'
          }`}
        />
      ))}
    </div>
  );
};

// ─── Skeleton card ──────────────────────────────────────────────────────────
const SkeletonCard = () => (
  <div className="bg-white rounded-lg overflow-hidden shadow-md animate-pulse">
    <div className="w-full h-72 bg-gray-200" />
    <div className="p-4 space-y-3">
      <div className="h-3 bg-gray-200 rounded w-1/3" />
      <div className="h-4 bg-gray-200 rounded w-3/4" />
      <div className="h-4 bg-gray-200 rounded w-1/2" />
      <div className="h-5 bg-gray-200 rounded w-1/4" />
      <div className="flex gap-2 mt-1">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="w-5 h-5 rounded-full bg-gray-200" />
        ))}
      </div>
    </div>
  </div>
);

// ─── Product card ────────────────────────────────────────────────────────────
const ProductCard = ({ product }) => {
  const img = product.thumbnail_url || '/assets/img/product/product-2.webp';
  const colors = product.colors?.map((pc) => pc.color) || [];

  // Badge logic
  let badge = null;
  let badgeClass = '';
  if (product.is_new) { badge = 'New'; badgeClass = 'bg-teal-600 text-white'; }
  else if (product.is_sale && product.discount_percent > 0) {
    badge = `-${product.discount_percent}%`;
    badgeClass = 'bg-red-500 text-white';
  } else if (Number(product.rating) >= 4.8) {
    badge = 'Trending';
    badgeClass = 'bg-teal-600 text-white';
  }

  return (
    <div className="group bg-white rounded-lg overflow-hidden shadow-md hover:shadow-xl transition-all duration-300">
      <div className="relative overflow-hidden">
        <img
          src={img}
          alt={product.name}
          className="w-full h-72 object-cover transition-transform duration-500 group-hover:scale-105"
          onError={(e) => { e.target.src = '/assets/img/product/product-2.webp'; }}
        />
        {badge && (
          <span className={`absolute top-4 left-4 text-xs font-semibold px-2 py-1 rounded ${badgeClass}`}>
            {badge}
          </span>
        )}

        {/* Hover actions */}
        <div className="absolute top-4 right-4 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-all duration-300 translate-x-4 group-hover:translate-x-0">
          <button className="bg-white p-2 rounded-full shadow hover:bg-teal-50 hover:text-teal-700 transition" title="Wishlist">
            <i className="bi bi-heart" />
          </button>
          <button className="bg-white p-2 rounded-full shadow hover:bg-teal-50 hover:text-teal-700 transition" title="Compare">
            <i className="bi bi-arrow-left-right" />
          </button>
        </div>

        {/* Quick-select CTA */}
        <Link
          to={`/product/${product.slug}`}
          className="absolute bottom-4 left-4 right-4 bg-white text-gray-800 py-2 rounded-lg text-center text-sm font-medium opacity-0 group-hover:opacity-100 transition-all duration-300 translate-y-2 group-hover:translate-y-0 hover:bg-teal-700 hover:text-white"
        >
          Select Options
        </Link>
      </div>

      <div className="p-4">
        <div className="text-xs text-gray-500 uppercase tracking-wider truncate">
          {product.category?.name || 'Uncategorised'}
        </div>
        <h4 className="font-semibold text-lg mt-1 line-clamp-2 leading-snug">
          <Link to={`/product/${product.slug}`} className="hover:text-teal-700 transition-colors">
            {product.name}
          </Link>
        </h4>

        <div className="flex items-center gap-2 mt-2">
          <Stars rating={product.rating} />
          <span className="text-xs text-gray-400">({product.reviews_count})</span>
        </div>

        <div className="mt-2">
          <span className="text-lg font-bold text-gray-900">
            ${Number(product.price).toFixed(2)}
          </span>
          {product.original_price && (
            <span className="text-sm text-gray-400 line-through ml-2">
              ${Number(product.original_price).toFixed(2)}
            </span>
          )}
        </div>

        {colors.length > 0 && (
          <div className="flex gap-2 mt-3 flex-wrap">
            {colors.slice(0, 5).map((color) => (
              <span
                key={color.id}
                className="w-5 h-5 rounded-full border border-gray-300 cursor-pointer hover:scale-110 transition-transform"
                style={{ backgroundColor: color.hex_code }}
                title={color.name}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// ─── BestSellers section ─────────────────────────────────────────────────────
const BestSellers = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await getProducts({ ordering: '-rating', page_size: 4 });
        setProducts(res.data.results || []);
      } catch (err) {
        console.error('BestSellers fetch error:', err);
        setError('Could not load best sellers.');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, []);

  return (
    <section className="py-16 bg-white">
      <div className="container mx-auto px-4">
        <div className="text-center mb-12">
          <span className="inline-block bg-teal-100 text-teal-700 text-xs font-semibold px-3 py-1 rounded-full mb-3 uppercase tracking-wider">
            Top Rated
          </span>
          <h2 className="text-3xl md:text-4xl font-bold text-gray-900">Best Sellers</h2>
          <p className="text-gray-500 mt-2 max-w-2xl mx-auto">
            Our highest-rated products, loved by thousands of customers worldwide.
          </p>
        </div>

        {error ? (
          <div className="text-center py-10">
            <i className="bi bi-exclamation-triangle text-4xl text-red-300 block mb-2" />
            <p className="text-gray-500">{error}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {loading
              ? [...Array(4)].map((_, i) => <SkeletonCard key={i} />)
              : products.map((p) => <ProductCard key={p.id} product={p} />)}
          </div>
        )}

        {!loading && !error && (
          <div className="text-center mt-10">
            <Link
              to="/category"
              className="inline-flex items-center gap-2 border border-gray-300 px-7 py-3 rounded-full font-medium hover:bg-gray-50 hover:border-teal-600 hover:text-teal-700 transition-all duration-200"
            >
              View All Products <i className="bi bi-arrow-right" />
            </Link>
          </div>
        )}
      </div>
    </section>
  );
};

export default BestSellers;
