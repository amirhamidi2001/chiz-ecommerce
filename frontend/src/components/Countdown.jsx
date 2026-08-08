// src/components/Countdown.jsx
import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { getProducts } from '../services/api';

// ─── Countdown logic ─────────────────────────────────────────────────────────
const useCountdown = (targetDate) => {
  const calc = () => {
    const diff = new Date(targetDate).getTime() - Date.now();
    if (diff <= 0) return { days: 0, hours: 0, minutes: 0, seconds: 0 };
    return {
      days:    Math.floor(diff / 86_400_000),
      hours:   Math.floor((diff % 86_400_000) / 3_600_000),
      minutes: Math.floor((diff % 3_600_000)  /    60_000),
      seconds: Math.floor((diff % 60_000)     /     1_000),
    };
  };

  const [timeLeft, setTimeLeft] = useState(calc);

  useEffect(() => {
    const id = setInterval(() => setTimeLeft(calc()), 1000);
    return () => clearInterval(id);
  }, [targetDate]); // eslint-disable-line

  return timeLeft;
};

// ─── Flip-style time unit box ─────────────────────────────────────────────────
const TimeBox = ({ value, label }) => (
  <div className="bg-white rounded-xl shadow-md px-4 py-4 w-24 text-center">
    <div className="text-3xl font-bold text-teal-700 tabular-nums leading-none">
      {String(value).padStart(2, '0')}
    </div>
    <div className="text-xs uppercase text-gray-500 mt-1 tracking-wider">{label}</div>
  </div>
);

// ─── Sale product card (compact) ─────────────────────────────────────────────
const SaleCard = ({ product }) => {
  const img = product.thumbnail_url || '/assets/img/product/product-5.webp';
  const full = Math.floor(Number(product.rating));
  const half = Number(product.rating) % 1 >= 0.5;

  return (
    <Link
      to={`/product/${product.slug}`}
      className="bg-white rounded-xl p-4 text-center shadow hover:shadow-lg transition-shadow duration-300 group block"
    >
      <div className="relative overflow-hidden rounded-lg mb-3 h-32 bg-gray-50 flex items-center justify-center">
        <img
          src={img}
          alt={product.name}
          className="h-full w-full object-contain transition-transform duration-500 group-hover:scale-110"
          onError={(e) => { e.target.src = '/assets/img/product/product-5.webp'; }}
        />
        {product.discount_percent > 0 && (
          <span className="absolute top-2 left-2 bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded">
            -{product.discount_percent}%
          </span>
        )}
      </div>
      <h6 className="font-semibold text-sm line-clamp-2 leading-snug group-hover:text-teal-700 transition-colors">
        {product.name}
      </h6>
      <div className="flex justify-center items-baseline gap-2 mt-2">
        {product.original_price && (
          <span className="text-gray-400 line-through text-xs">
            ${Number(product.original_price).toFixed(2)}
          </span>
        )}
        <span className="text-teal-700 font-bold text-base">
          ${Number(product.price).toFixed(2)}
        </span>
      </div>
      <div className="flex justify-center items-center gap-0.5 text-yellow-400 text-xs mt-1">
        {[...Array(5)].map((_, i) => (
          <i
            key={i}
            className={`bi ${i < full ? 'bi-star-fill' : i === full && half ? 'bi-star-half' : 'bi-star'}`}
          />
        ))}
        <span className="text-gray-400 ml-1">({product.reviews_count})</span>
      </div>
    </Link>
  );
};

// ─── Skeleton sale card ───────────────────────────────────────────────────────
const SaleCardSkeleton = () => (
  <div className="bg-white rounded-xl p-4 text-center shadow animate-pulse">
    <div className="h-32 bg-gray-200 rounded-lg mb-3" />
    <div className="h-4 bg-gray-200 rounded w-3/4 mx-auto mb-2" />
    <div className="h-4 bg-gray-200 rounded w-1/2 mx-auto mb-2" />
    <div className="h-3 bg-gray-200 rounded w-2/3 mx-auto" />
  </div>
);

// ─── Countdown section ────────────────────────────────────────────────────────
// Flash sale ends at a fixed date — update this in your CMS / env as needed.
const FLASH_SALE_END = '2026-12-31T23:59:59';

const Countdown = () => {
  const timeLeft = useCountdown(FLASH_SALE_END);
  const [saleProducts, setSaleProducts] = useState([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState(null);

  useEffect(() => {
    getProducts({ is_sale: true, ordering: '-discount_percent', page_size: 4 })
      .then((res) => setSaleProducts(res.data.results || []))
      .catch(() => {
        // Fallback: grab highest-discount products regardless of flag
        return getProducts({ ordering: '-rating', page_size: 4 })
          .then((res) => setSaleProducts(res.data.results || []))
          .catch(() => setError('Could not load sale products.'));
      })
      .finally(() => setLoading(false));
  }, []);

  const isExpired = Object.values(timeLeft).every((v) => v === 0);

  return (
    <section className="py-20 bg-gradient-to-r from-teal-50 to-pink-50 relative overflow-hidden">
      {/* Decorative blobs */}
      <div className="absolute top-0 left-0 w-64 h-64 bg-teal-200 rounded-full opacity-20 -translate-x-1/2 -translate-y-1/2 pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-96 h-96 bg-pink-200 rounded-full opacity-20 translate-x-1/2 translate-y-1/2 pointer-events-none" />

      <div className="container mx-auto px-4 text-center relative z-10">
        <div className="max-w-3xl mx-auto">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 bg-teal-100 text-teal-800 px-4 py-2 rounded-full mb-6">
            <i className="bi bi-lightning-charge-fill text-teal-600" />
            <span className="text-sm font-semibold">Limited Time</span>
            <span className="text-xl font-bold">50% OFF</span>
          </div>

          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            {isExpired ? 'Sale Has Ended' : 'Exclusive Flash Sale'}
          </h2>
          <p className="text-gray-600 text-lg mb-8">
            {isExpired
              ? 'Stay tuned for our next sale event — subscribe to never miss a deal.'
              : "Don't miss out on our biggest sale of the year. Premium quality products at unbeatable prices."}
          </p>

          {/* Countdown timer */}
          {!isExpired && (
            <div className="flex justify-center gap-3 md:gap-4 mb-10">
              <TimeBox value={timeLeft.days}    label="Days"    />
              <TimeBox value={timeLeft.hours}   label="Hours"   />
              <TimeBox value={timeLeft.minutes} label="Minutes" />
              <TimeBox value={timeLeft.seconds} label="Seconds" />
            </div>
          )}

          {/* CTA buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
            <Link
              to="/category?is_sale=true"
              className="bg-teal-700 text-white px-8 py-3 rounded-full font-semibold hover:bg-teal-800 transition flex items-center justify-center gap-2"
            >
              <i className="bi bi-bag-fill" /> Shop Now
            </Link>
            <Link
              to="/category"
              className="border border-gray-300 px-8 py-3 rounded-full font-semibold hover:bg-gray-100 transition"
            >
              View All Deals
            </Link>
          </div>
        </div>

        {/* Sale product showcase grid */}
        <div className="grid md:grid-cols-4 gap-6">
          {error ? (
            <div className="md:col-span-4 text-center py-8 text-gray-400">
              <i className="bi bi-exclamation-triangle text-3xl block mb-2" />
              {error}
            </div>
          ) : loading ? (
            [...Array(4)].map((_, i) => <SaleCardSkeleton key={i} />)
          ) : saleProducts.length === 0 ? (
            <div className="md:col-span-4 text-center py-8 text-gray-400">
              No sale products available right now.
            </div>
          ) : (
            saleProducts.map((p) => <SaleCard key={p.id} product={p} />)
          )}
        </div>
      </div>
    </section>
  );
};

export default Countdown;
