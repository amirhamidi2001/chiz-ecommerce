// src/components/Cards.jsx
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getProducts } from '../services/api';

// ─── Shared Stars ────────────────────────────────────────────────────────────
const Stars = ({ rating }) => {
  const full = Math.floor(Number(rating));
  const half = Number(rating) % 1 >= 0.5;
  return (
    <div className="flex items-center gap-0.5">
      {[...Array(5)].map((_, i) => (
        <i
          key={i}
          className={`bi text-xs ${
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

// ─── Skeleton row ────────────────────────────────────────────────────────────
const SkeletonRow = () => (
  <div className="flex gap-3 items-center animate-pulse">
    <div className="w-20 h-20 flex-shrink-0 bg-gray-200 rounded-lg" />
    <div className="flex-1 space-y-2">
      <div className="h-3 bg-gray-200 rounded w-4/5" />
      <div className="h-3 bg-gray-200 rounded w-3/5" />
      <div className="h-4 bg-gray-200 rounded w-1/3" />
    </div>
  </div>
);

// ─── Single mini product row ─────────────────────────────────────────────────
const ProductRow = ({ product }) => {
  const img = product.thumbnail_url || '/assets/img/product/product-1.webp';
  return (
    <div className="flex gap-3 items-center group">
      <Link
        to={`/product/${product.slug}`}
        className="w-20 h-20 flex-shrink-0 bg-white rounded-lg overflow-hidden border border-gray-100"
      >
        <img
          src={img}
          alt={product.name}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110"
          onError={(e) => { e.target.src = '/assets/img/product/product-1.webp'; }}
        />
      </Link>
      <div className="flex-1 min-w-0">
        <Link
          to={`/product/${product.slug}`}
          className="font-medium text-gray-800 group-hover:text-teal-700 transition-colors line-clamp-2 text-sm leading-snug block"
        >
          {product.name}
        </Link>
        <div className="flex items-center gap-1 mt-1">
          <Stars rating={product.rating} />
          <span className="text-gray-400 text-xs">({product.reviews_count})</span>
        </div>
        <div className="flex items-center gap-2 mt-1">
          <span className="font-bold text-gray-900 text-sm">
            ${Number(product.price).toFixed(2)}
          </span>
          {product.original_price && (
            <span className="text-xs text-gray-400 line-through">
              ${Number(product.original_price).toFixed(2)}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

// ─── Card column ─────────────────────────────────────────────────────────────
const CardColumn = ({ title, icon, products, loading, error, linkParams }) => (
  <div className="bg-gray-50 p-5 rounded-xl border border-gray-100">
    <div className="flex items-center justify-between mb-5">
      <h3 className="text-xl font-bold flex items-center gap-2">
        <i className={`bi ${icon} text-teal-700`} /> {title}
      </h3>
      <Link
        to={`/category?${new URLSearchParams(linkParams).toString()}`}
        className="text-xs text-teal-600 hover:underline font-medium"
      >
        View all →
      </Link>
    </div>

    <div className="space-y-4">
      {error ? (
        <p className="text-sm text-gray-400 italic py-4 text-center">{error}</p>
      ) : loading ? (
        [...Array(3)].map((_, i) => <SkeletonRow key={i} />)
      ) : products.length === 0 ? (
        <p className="text-sm text-gray-400 italic py-4 text-center">No products found.</p>
      ) : (
        products.map((p) => <ProductRow key={p.id} product={p} />)
      )}
    </div>
  </div>
);

// ─── Cards section ────────────────────────────────────────────────────────────
const Cards = () => {
  const [trending, setTrending]       = useState({ data: [], loading: true, error: null });
  const [bestSellers, setBestSellers] = useState({ data: [], loading: true, error: null });
  const [featured, setFeatured]       = useState({ data: [], loading: true, error: null });

  useEffect(() => {
    // Trending = newest arrivals
    getProducts({ ordering: '-created_at', page_size: 3 })
      .then((res) => setTrending({ data: res.data.results || [], loading: false, error: null }))
      .catch(() => setTrending({ data: [], loading: false, error: 'Could not load.' }));

    // Best sellers = most reviewed
    getProducts({ ordering: '-reviews_count', page_size: 3 })
      .then((res) => setBestSellers({ data: res.data.results || [], loading: false, error: null }))
      .catch(() => setBestSellers({ data: [], loading: false, error: 'Could not load.' }));

    // Featured = new arrivals flag
    getProducts({ is_new: true, ordering: '-rating', page_size: 3 })
      .then((res) => setFeatured({ data: res.data.results || [], loading: false, error: null }))
      .catch(() => setFeatured({ data: [], loading: false, error: 'Could not load.' }));
  }, []);

  return (
    <section className="py-16 bg-white">
      <div className="container mx-auto px-4">
        <div className="text-center mb-10">
          <span className="inline-block bg-teal-100 text-teal-700 text-xs font-semibold px-3 py-1 rounded-full mb-3 uppercase tracking-wider">
            Curated For You
          </span>
          <h2 className="text-3xl md:text-4xl font-bold text-gray-900">Shop by Popularity</h2>
          <p className="text-gray-500 mt-2 max-w-xl mx-auto">
            Discover what's hot, what's selling fast, and what's freshly arrived.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          <CardColumn
            title="Trending Now"
            icon="bi-fire"
            products={trending.data}
            loading={trending.loading}
            error={trending.error}
            linkParams={{ ordering: '-created_at' }}
          />
          <CardColumn
            title="Best Sellers"
            icon="bi-award"
            products={bestSellers.data}
            loading={bestSellers.loading}
            error={bestSellers.error}
            linkParams={{ ordering: '-reviews_count' }}
          />
          <CardColumn
            title="New Arrivals"
            icon="bi-stars"
            products={featured.data}
            loading={featured.loading}
            error={featured.error}
            linkParams={{ is_new: true }}
          />
        </div>
      </div>
    </section>
  );
};

export default Cards;
