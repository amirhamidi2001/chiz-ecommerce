// src/components/Hero.jsx
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getProducts } from '../services/api';

// ─── Skeleton for the hero product card ──────────────────────────────────────
const HeroCardSkeleton = () => (
  <div className="bg-white rounded-2xl shadow-xl p-4 animate-pulse">
    <div className="w-full max-w-sm mx-auto h-64 bg-gray-200 rounded-xl" />
    <div className="mt-4 space-y-2">
      <div className="h-5 bg-gray-200 rounded w-3/4 mx-auto" />
      <div className="h-6 bg-gray-200 rounded w-1/3 mx-auto" />
    </div>
  </div>
);

// ─── Star display ─────────────────────────────────────────────────────────────
const Stars = ({ rating }) => {
  const full = Math.floor(Number(rating));
  const half = Number(rating) % 1 >= 0.5;
  return (
    <div className="flex items-center gap-0.5 justify-center">
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

// ─── Hero section ─────────────────────────────────────────────────────────────
const Hero = () => {
  const [featuredProduct, setFeaturedProduct] = useState(null);
  const [loading, setLoading]                 = useState(true);

  useEffect(() => {
    getProducts({ ordering: '-rating', page_size: 1 })
      .then((res) => {
        const results = res.data.results || [];
        if (results.length > 0) setFeaturedProduct(results[0]);
      })
      .catch((err) => console.error('Hero product fetch error:', err))
      .finally(() => setLoading(false));
  }, []);

  const img = featuredProduct?.thumbnail_url || '/assets/img/product/product-2.webp';
  const savings = featuredProduct?.original_price
    ? (Number(featuredProduct.original_price) - Number(featuredProduct.price)).toFixed(2)
    : null;

  return (
    <section className="bg-gradient-to-r from-emerald-50 to-white py-20 overflow-hidden">
      <div className="container mx-auto flex flex-col md:flex-row items-center gap-10 px-4">

        {/* ── Left: copy ─────────────────────────────────────────────────── */}
        <div className="flex-1 text-center md:text-left">
          <span className="inline-block bg-teal-100 text-teal-700 text-xs font-semibold px-3 py-1 rounded-full mb-4 uppercase tracking-wider">
            Now Live
          </span>
          <h1 className="text-4xl md:text-6xl font-bold leading-tight text-gray-900">
            Chiz <br className="hidden md:block" />
            <span className="text-teal-600">E-Commerce</span>
          </h1>
          <p className="text-gray-600 mt-4 text-lg max-w-lg">
            Smart electrical panel e-commerce platform — built with Django REST Framework &amp; React.
          </p>

          <div className="mt-8 flex gap-4 justify-center md:justify-start flex-wrap">
            <Link
              to="/category"
              className="bg-black text-white px-7 py-3 rounded-full hover:bg-gray-800 transition font-medium"
            >
              Shop Now
            </Link>
            <Link
              to="/category"
              className="border border-gray-300 px-7 py-3 rounded-full hover:bg-gray-100 transition font-medium"
            >
              Browse Categories
            </Link>
          </div>

          {/* Trust badges */}
          <div className="flex flex-wrap gap-6 mt-8 justify-center md:justify-start text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <i className="bi bi-truck text-teal-600" />
              <span>Free Shipping</span>
            </div>
            <div className="flex items-center gap-2">
              <i className="bi bi-award text-teal-600" />
              <span>Quality Guarantee</span>
            </div>
            <div className="flex items-center gap-2">
              <i className="bi bi-headset text-teal-600" />
              <span>24/7 Support</span>
            </div>
          </div>

          {/* Live stats strip */}
          {!loading && featuredProduct && (
            <div className="mt-8 inline-flex items-center gap-3 bg-white border border-gray-200 rounded-full px-5 py-2 shadow-sm">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span className="text-xs text-gray-500">
                <strong className="text-gray-800">{featuredProduct.reviews_count}+</strong> happy customers already
              </span>
            </div>
          )}
        </div>

        {/* ── Right: featured product card ────────────────────────────────── */}
        <div className="flex-1 relative max-w-sm md:max-w-none w-full">
          {loading ? (
            <HeroCardSkeleton />
          ) : featuredProduct ? (
            <div className="bg-white rounded-2xl shadow-xl p-5 relative z-10 group">
              {/* Badge */}
              <div className="absolute top-4 right-4 bg-teal-600 text-white text-xs font-bold px-2 py-1 rounded-full z-20">
                ★ Top Rated
              </div>

              {/* Product image */}
              <div className="overflow-hidden rounded-xl bg-gray-50 flex items-center justify-center h-56">
                <img
                  src={img}
                  alt={featuredProduct.name}
                  className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                  onError={(e) => { e.target.src = '/assets/img/product/product-2.webp'; }}
                />
              </div>

              {/* Product info */}
              <div className="mt-4 text-center">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
                  {featuredProduct.category?.name}
                </div>
                <h4 className="font-bold text-base line-clamp-2 leading-snug">
                  {featuredProduct.name}
                </h4>
                <Stars rating={featuredProduct.rating} />
                <div className="flex justify-center items-baseline gap-2 mt-2">
                  <span className="text-2xl font-bold text-teal-700">
                    ${Number(featuredProduct.price).toFixed(2)}
                  </span>
                  {featuredProduct.original_price && (
                    <span className="text-gray-400 line-through text-sm">
                      ${Number(featuredProduct.original_price).toFixed(2)}
                    </span>
                  )}
                </div>
                {savings && (
                  <p className="text-xs text-teal-600 mt-0.5 font-medium">
                    You save ${savings}!
                  </p>
                )}

                <Link
                  to={`/product/${featuredProduct.slug}`}
                  className="mt-4 inline-block w-full bg-teal-600 text-white py-2.5 rounded-xl font-semibold text-sm hover:bg-teal-700 transition"
                >
                  View Product
                </Link>
              </div>
            </div>
          ) : (
            /* Fallback static card when API returns nothing */
            <div className="bg-white rounded-2xl shadow-xl p-4 relative z-10">
              <img
                src="/assets/img/product/product-2.webp"
                alt="Featured Product"
                className="w-full max-w-md mx-auto rounded-xl"
              />
              <div className="absolute top-4 right-4 bg-teal-600 text-white text-xs font-bold px-2 py-1 rounded">
                Best Seller
              </div>
              <div className="mt-4 text-center">
                <h4 className="font-bold text-lg">Premium Wireless Headphones</h4>
                <div className="flex justify-center items-baseline gap-2 mt-1">
                  <span className="text-2xl font-bold text-teal-700">$299</span>
                  <span className="text-gray-400 line-through">$399</span>
                </div>
              </div>
            </div>
          )}

          {/* Floating decorative elements */}
          <div className="absolute -bottom-4 -left-4 w-24 h-24 bg-teal-100 rounded-full opacity-60 blur-xl pointer-events-none" />
          <div className="absolute -top-6 -right-6 w-32 h-32 bg-pink-100 rounded-full opacity-60 blur-xl pointer-events-none" />
        </div>
      </div>
    </section>
  );
};

export default Hero;
