// src/components/PromoCards.jsx
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getCategories, getProducts } from '../services/api';

// ─── Static palette assigned per category index ───────────────────────────────
const CARD_THEMES = [
  { bg: 'bg-blue-50', accent: 'text-blue-700', hover: 'group-hover:text-blue-800' },
  { bg: 'bg-yellow-50', accent: 'text-yellow-700', hover: 'group-hover:text-yellow-800' },
  { bg: 'bg-pink-50', accent: 'text-pink-700', hover: 'group-hover:text-pink-800' },
  { bg: 'bg-teal-50', accent: 'text-teal-700', hover: 'group-hover:text-teal-800' },
  { bg: 'bg-purple-50', accent: 'text-purple-700', hover: 'group-hover:text-purple-800' },
  { bg: 'bg-orange-50', accent: 'text-orange-700', hover: 'group-hover:text-orange-800' },
];

// ─── Fallback images per index when category has no image ────────────────────
const FALLBACK_IMAGES = [
  '/assets/img/product/product-1.webp',
  '/assets/img/product/product-2.webp',
  '/assets/img/product/product-3.webp',
  '/assets/img/product/product-4.webp',
  '/assets/img/product/product-5.webp',
  '/assets/img/product/product-1.webp',
];

// ─── Skeleton for small category card ────────────────────────────────────────
const SmallCardSkeleton = () => (
  <div className="relative bg-gray-100 rounded-2xl overflow-hidden h-56 animate-pulse">
    <div className="absolute right-0 top-0 w-1/2 h-full bg-gray-200" />
    <div className="relative p-6 w-1/2 h-full flex flex-col justify-center gap-3">
      <div className="h-5 bg-gray-200 rounded w-3/4" />
      <div className="h-3 bg-gray-200 rounded w-1/2" />
      <div className="h-3 bg-gray-200 rounded w-2/3" />
    </div>
  </div>
);

// ─── Small category card ──────────────────────────────────────────────────────
const SmallCategoryCard = ({ category, productCount, imgSrc, theme }) => (
  <div className={`relative ${theme.bg} rounded-2xl overflow-hidden group h-56`}>
    <div className="absolute right-0 top-0 w-1/2 h-full">
      <img
        src={imgSrc}
        alt={category.name}
        className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
        onError={(e) => { e.target.src = '/assets/img/product/product-1.webp'; }}
      />
      {/* gradient overlay for legibility */}
      <div className="absolute inset-0 bg-gradient-to-l from-transparent to-white/30" />
    </div>
    <div className="relative p-6 w-1/2 h-full flex flex-col justify-center z-10">
      <h4 className="text-xl font-bold text-gray-900 leading-snug line-clamp-2">
        {category.name}
      </h4>
      <p className="text-sm text-gray-500 mt-1">
        {productCount !== null
          ? `${productCount} product${productCount !== 1 ? 's' : ''}`
          : <span className="inline-block w-16 h-3 bg-gray-200 rounded animate-pulse" />}
      </p>
      <Link
        to={`/category?category=${category.slug}`}
        className={`mt-3 font-medium text-sm inline-flex items-center gap-1 transition-all duration-200 ${theme.accent} ${theme.hover} group-hover:gap-2`}
      >
        Shop Now <span>→</span>
      </Link>
    </div>
  </div>
);

// ─── PromoCards section ───────────────────────────────────────────────────────
const PromoCards = () => {
  const [categories, setCategories] = useState([]);
  const [productCounts, setProductCounts] = useState({});   // { [categorySlug]: count }
  const [heroCategory, setHeroCategory] = useState(null);
  const [heroCount, setHeroCount] = useState(null);
  const [loading, setLoading] = useState(true);

  // ── Step 1: fetch top-level categories ──────────────────────────────────
  useEffect(() => {
    getCategories()
      .then((res) => {
        const cats = Array.isArray(res.data)
          ? res.data
          : res.data.results || [];

        const smallCats = cats.slice(1, 5);
        const heroCat = cats[0] || null;

        setCategories(smallCats);
        setHeroCategory(heroCat);

        const countRequests = [...(heroCat ? [heroCat] : []), ...smallCats].map((cat) =>
          getProducts({ category: cat.slug, page_size: 1 })
            .then((r) => ({
              slug: cat.slug,
              count: r.data.count || 0
            }))
            .catch(() => ({
              slug: cat.slug,
              count: 0
            }))
        );

        Promise.all(countRequests).then((results) => {
          const map = {};

          results.forEach(({ slug, count }) => {
            map[slug] = count;
          });

          setProductCounts(map);

          if (heroCat) {
            setHeroCount(map[heroCat.slug] ?? 0);
          }
        });
      })
      .catch((err) => console.error('PromoCards category fetch error:', err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="py-16 bg-gray-50">
      <div className="container mx-auto px-4">

        {/* Section header */}
        <div className="text-center mb-10">
          <span className="inline-block bg-teal-100 text-teal-700 text-xs font-semibold px-3 py-1 rounded-full mb-3 uppercase tracking-wider">
            Shop by Category
          </span>
          <h2 className="text-3xl md:text-4xl font-bold text-gray-900">
            {loading ? (
              <span className="inline-block w-64 h-8 bg-gray-200 rounded animate-pulse" />
            ) : (
              'Explore Our Collections'
            )}
          </h2>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">

          {/* ── Left: hero category card ──────────────────────────────────── */}
          {loading ? (
            <div className="relative bg-teal-100 rounded-2xl overflow-hidden h-96 md:h-auto animate-pulse">
              <div className="absolute right-0 top-0 w-1/2 h-full bg-teal-200" />
              <div className="relative p-8 space-y-4 max-w-xs">
                <div className="h-5 bg-teal-200 rounded w-1/3" />
                <div className="h-8 bg-teal-200 rounded w-4/5" />
                <div className="h-4 bg-teal-200 rounded w-3/4" />
                <div className="h-4 bg-teal-200 rounded w-2/3" />
                <div className="h-10 bg-teal-200 rounded-full w-40" />
              </div>
            </div>
          ) : heroCategory ? (
            <div className="relative bg-teal-50 rounded-2xl overflow-hidden group">
              {/* Right-side image */}
              <div className="absolute right-0 top-0 w-1/2 h-full">
                <img
                  src={heroCategory.image || FALLBACK_IMAGES[0]}
                  alt={heroCategory.name}
                  className="w-full h-full object-cover object-top transition-transform duration-500 group-hover:scale-105"
                  onError={(e) => { e.target.src = FALLBACK_IMAGES[0]; }}
                />
                <div className="absolute inset-0 bg-gradient-to-l from-transparent to-teal-50/60" />
              </div>

              {/* Left-side text */}
              <div className="relative z-10 p-8 md:p-10 max-w-md">
                <span className="inline-block bg-teal-100 text-teal-700 text-xs font-semibold px-3 py-1 rounded-full mb-4">
                  Trending Now
                </span>
                <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-2">
                  {heroCategory.name}
                </h2>
                <p className="text-gray-600 mb-2">
                  Discover our latest arrivals designed for the modern lifestyle.
                </p>
                {heroCount !== null && (
                  <p className="text-teal-700 font-semibold text-sm mb-5">
                    {heroCount} products available
                  </p>
                )}
                <Link
                  to={`/category?category=${heroCategory.slug}`}
                  className="inline-flex items-center gap-2 bg-teal-700 text-white px-5 py-2.5 rounded-full hover:bg-teal-800 transition font-medium"
                >
                  Explore Collection <span>→</span>
                </Link>
              </div>
            </div>
          ) : (
            /* Static fallback if API returns no categories */
            <div className="relative bg-teal-50 rounded-2xl overflow-hidden group">
              <div className="absolute right-0 top-0 w-1/2 h-full">
                <img
                  src="/assets/img/product/product-3.webp"
                  alt="Collection"
                  className="w-full h-full object-cover object-top transition-transform duration-500 group-hover:scale-105"
                />
              </div>
              <div className="relative z-10 p-8 md:p-10 max-w-md">
                <span className="inline-block bg-teal-100 text-teal-700 text-xs font-semibold px-3 py-1 rounded-full mb-4">
                  Trending Now
                </span>
                <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-3">
                  New Summer Collection
                </h2>
                <p className="text-gray-600 mb-6">
                  Discover our latest arrivals designed for the modern lifestyle.
                </p>
                <Link
                  to="/category"
                  className="inline-flex items-center gap-2 bg-teal-700 text-white px-5 py-2 rounded-full hover:bg-teal-800 transition"
                >
                  Explore Collection <span>→</span>
                </Link>
              </div>
            </div>
          )}

          {/* ── Right: 2×2 small category grid ────────────────────────────── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {loading
              ? [...Array(4)].map((_, i) => <SmallCardSkeleton key={i} />)
              : categories.length > 0
                ? categories.map((cat, idx) => (
                  <SmallCategoryCard
                    key={cat.id}
                    category={cat}
                    productCount={productCounts[cat.slug] ?? null}
                    imgSrc={cat.image || FALLBACK_IMAGES[(idx + 1) % FALLBACK_IMAGES.length]}
                    theme={CARD_THEMES[(idx + 1) % CARD_THEMES.length]}
                  />
                ))
                : /* Static fallback cards */
                [
                  { name: "Men's Wear", img: '/assets/img/product/product-4.webp', slug: 'mens-wear', theme: CARD_THEMES[0] },
                  { name: "Kid's Fashion", img: '/assets/img/product/product-3.webp', slug: 'kids-fashion', theme: CARD_THEMES[1] },
                  { name: 'Beauty Products', img: '/assets/img/product/product-2.webp', slug: 'beauty-products', theme: CARD_THEMES[2] },
                  { name: 'Accessories', img: '/assets/img/product/product-1.webp', slug: 'accessories', theme: CARD_THEMES[3] },
                ].map((item) => (
                  <div key={item.slug} className={`relative ${item.theme.bg} rounded-2xl overflow-hidden group h-56`}>
                    <div className="absolute right-0 top-0 w-1/2 h-full">
                      <img
                        src={item.img}
                        alt={item.name}
                        className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                      />
                    </div>
                    <div className="relative p-6 w-1/2 h-full flex flex-col justify-center z-10">
                      <h4 className="text-xl font-bold">{item.name}</h4>
                      <Link to={`/category?category=${item.slug}`} className={`mt-2 font-medium inline-flex items-center gap-1 text-sm ${item.theme.accent} group-hover:gap-2 transition-all`}>
                        Shop Now <span>→</span>
                      </Link>
                    </div>
                  </div>
                ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default PromoCards;
