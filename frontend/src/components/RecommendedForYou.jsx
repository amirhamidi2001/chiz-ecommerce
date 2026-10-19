// src/components/RecommendedForYou.jsx
import { useState, useEffect } from 'react';
import { ProductCard } from './BestSellers';
import { getHomeRecommendations, isAuthenticated } from '../services/api';
import { getRecentlyViewed } from '../utils/recentlyViewed';

/**
 * Homepage "Recommended For You" — lightweight category-affinity picks
 * (a simple heuristic, not ML; see backend shop/recommendations.py).
 *
 * The viewing history lives only in this browser's localStorage, so it is read
 * here (via the shared recentlyViewed util) and sent to the backend. Logged-in
 * users also get their purchase categories blended in server-side, so they
 * still get a request when the local history is empty.
 *
 * Renders NOTHING while loading, on failure, or when there are no results:
 * most first-time visitors have no signal, and a skeleton/empty widget (or a
 * layout jump when it vanishes) would be worse than no section at all.
 *
 * One consistent heading is used rather than "Because you viewed <X>…" copy:
 * results blend several signals (all recent views, plus purchases), so naming
 * one product would be misleading.
 */
const RecommendedForYou = () => {
  const [products, setProducts] = useState([]);

  useEffect(() => {
    let cancelled = false;

    const viewedProductIds = getRecentlyViewed()
      .map((entry) => entry?.id)
      .filter((id) => id != null);

    // Anonymous + no history = zero signal; the backend would just return [].
    if (viewedProductIds.length === 0 && !isAuthenticated()) return undefined;

    (async () => {
      try {
        const res = await getHomeRecommendations(viewedProductIds);
        const data = res?.data;
        const list = Array.isArray(data) ? data : data?.results || [];
        if (!cancelled) setProducts(list);
      } catch (err) {
        // Non-critical widget: stay hidden rather than show an error on the homepage.
        console.error('RecommendedForYou fetch error:', err);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  if (products.length === 0) return null;

  return (
    <section className="py-16 bg-gray-50" data-testid="recommended-for-you">
      <div className="container mx-auto px-4">
        <div className="text-center mb-12">
          <span className="inline-block bg-teal-100 text-teal-700 text-xs font-semibold px-3 py-1 rounded-full mb-3 uppercase tracking-wider">
            Picked For You
          </span>
          <h2 className="text-3xl md:text-4xl font-bold text-gray-900">Recommended For You</h2>
          <p className="text-gray-500 mt-2 max-w-2xl mx-auto">
            Top-rated products from the categories you&apos;ve been exploring.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      </div>
    </section>
  );
};

export default RecommendedForYou;
