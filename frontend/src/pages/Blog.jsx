// src/pages/Blog.jsx
import { useState, useEffect, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { blogAPI } from "../services/api";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const FALLBACK_IMAGES = [
  "/assets/img/person/person-f-1.webp",
  "/assets/img/person/person-f-2.webp",
  "/assets/img/person/person-f-3.webp",
  "/assets/img/person/person-f-4.webp",
  "/assets/img/person/person-f-5.webp",
  "/assets/img/person/person-f-6.webp",
];

const getPostImage = (post, index = 0) =>
  post?.cover_image_url || FALLBACK_IMAGES[index % FALLBACK_IMAGES.length];

const formatDate = (dateStr) => {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

// ─── Sub-components ───────────────────────────────────────────────────────────

const PostSkeleton = () => (
  <div className="bg-white rounded-lg shadow-md overflow-hidden animate-pulse">
    <div className="w-full h-56 bg-gray-200" />
    <div className="p-5 space-y-3">
      <div className="h-3 bg-gray-200 rounded w-1/4" />
      <div className="h-5 bg-gray-200 rounded w-3/4" />
      <div className="h-3 bg-gray-200 rounded w-1/2" />
    </div>
  </div>
);

const HeroSkeleton = () => (
  <div className="relative rounded-lg overflow-hidden shadow-lg mb-8 animate-pulse bg-gray-200 h-80" />
);

const CategoryBadge = ({ name }) => (
  <span className="bg-teal-600 text-white text-xs font-semibold px-2 py-1 rounded">
    {name}
  </span>
);

// ─── Main component ───────────────────────────────────────────────────────────

const Blog = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // ── State ──
  const [posts, setPosts] = useState([]);
  const [heroPost, setHeroPost] = useState(null);
  const [secondaryPosts, setSecondaryPosts] = useState([]);
  const [sidebarPosts, setSidebarPosts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [pagination, setPagination] = useState({
    count: 0,
    total_pages: 1,
    current_page: 1,
  });

  const [loadingHero, setLoadingHero] = useState(true);
  const [loadingGrid, setLoadingGrid] = useState(true);
  const [loadingSidebar, setLoadingSidebar] = useState(true);
  const [error, setError] = useState(null);

  const [activeTab, setActiveTab] = useState("latest");

  // Derive filter state from URL params
  const currentPage = parseInt(searchParams.get("page") || "1", 10);
  const activeCategory = searchParams.get("category") || "";
  const searchQuery = searchParams.get("search") || "";

  // ── Fetchers ──

  const fetchHeroSection = useCallback(async () => {
    setLoadingHero(true);
    try {
      // Fetch featured post + 2 secondary posts in parallel
      const [featuredRes, recentRes] = await Promise.all([
        blogAPI.getPosts({ is_featured: true, page_size: 1, ordering: "-created_at" }),
        blogAPI.getPosts({ page_size: 3, ordering: "-created_at" }),
      ]);

      const featuredResults = featuredRes.data.results || [];
      const recentResults = recentRes.data.results || [];

      if (featuredResults.length > 0) {
        setHeroPost(featuredResults[0]);
        // Secondary: take next 2 from recent, skipping the featured one
        const secondary = recentResults
          .filter((p) => p.id !== featuredResults[0].id)
          .slice(0, 2);
        setSecondaryPosts(secondary);
      } else if (recentResults.length > 0) {
        setHeroPost(recentResults[0]);
        setSecondaryPosts(recentResults.slice(1, 3));
      }
    } catch {
      // Hero section failure is non-fatal — grid still loads
    } finally {
      setLoadingHero(false);
    }
  }, []);

  const fetchSidebarPosts = useCallback(
    async (tab) => {
      setLoadingSidebar(true);
      try {
        const ordering =
          tab === "trending" ? "-views_count" : "-created_at";
        const { data } = await blogAPI.getPosts({
          page_size: 5,
          ordering,
          ...(activeCategory ? { category: activeCategory } : {}),
        });
        setSidebarPosts(data.results || []);
      } catch {
        setSidebarPosts([]);
      } finally {
        setLoadingSidebar(false);
      }
    },
    [activeCategory],
  );

  const fetchGridPosts = useCallback(async () => {
    setLoadingGrid(true);
    setError(null);
    try {
      const params = {
        page: currentPage,
        page_size: 6,
        ordering: "-created_at",
        ...(activeCategory ? { category: activeCategory } : {}),
        ...(searchQuery ? { search: searchQuery } : {}),
      };
      const { data } = await blogAPI.getPosts(params);
      setPosts(data.results || []);
      setPagination({
        count: data.count,
        total_pages: data.total_pages,
        current_page: data.current_page,
      });
    } catch {
      setError("Failed to load posts. Please try again.");
    } finally {
      setLoadingGrid(false);
    }
  }, [currentPage, activeCategory, searchQuery]);

  const fetchCategories = useCallback(async () => {
    try {
      const { data } = await blogAPI.getCategories();
      setCategories(data);
    } catch {
      setCategories([]);
    }
  }, []);

  // ── Effects ──

  useEffect(() => {
    fetchHeroSection();
    fetchCategories();
  }, [fetchHeroSection, fetchCategories]);

  useEffect(() => {
    fetchGridPosts();
  }, [fetchGridPosts]);

  useEffect(() => {
    fetchSidebarPosts(activeTab);
  }, [activeTab, fetchSidebarPosts]);

  // ── Handlers ──

  const handleTabChange = (tab) => {
    setActiveTab(tab);
  };

  const handleCategoryFilter = (slug) => {
    const next = new URLSearchParams(searchParams);
    if (slug) {
      next.set("category", slug);
    } else {
      next.delete("category");
    }
    next.delete("page");
    setSearchParams(next);
  };

  const handlePageChange = (page) => {
    const next = new URLSearchParams(searchParams);
    next.set("page", page);
    setSearchParams(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // ── Render ──

  return (
    <main className="bg-white">
      {/* ── Breadcrumb ────────────────────────────────────────────────── */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-800 mb-2 md:mb-0">Blog</h1>
          <nav className="text-sm">
            <ol className="flex space-x-2">
              <li>
                <Link to="/" className="text-gray-500 hover:text-teal-600">
                  Home
                </Link>
              </li>
              <li className="text-gray-700">/</li>
              <li className="text-gray-900 font-semibold">Blog</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* ── Hero Section ──────────────────────────────────────────────── */}
      <section className="py-16">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Main Content (2/3) */}
            <div className="lg:col-span-2">
              {/* Featured article */}
              {loadingHero ? (
                <HeroSkeleton />
              ) : heroPost ? (
                <article className="relative mb-8 rounded-lg overflow-hidden shadow-lg group">
                  <img
                    src={getPostImage(heroPost, 0)}
                    alt={heroPost.title}
                    className="w-full h-80 object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent flex items-end p-6">
                    <div className="text-white">
                      <div className="flex items-center space-x-2 text-sm mb-2">
                        {heroPost.category && (
                          <CategoryBadge name={heroPost.category.name} />
                        )}
                        <span>{formatDate(heroPost.published_at || heroPost.created_at)}</span>
                      </div>
                      <h2 className="text-2xl md:text-3xl font-bold mb-2">
                        <Link
                          to={`/blog/${heroPost.slug}`}
                          className="hover:underline"
                        >
                          {heroPost.title}
                        </Link>
                      </h2>
                      {heroPost.excerpt && (
                        <p className="text-gray-200 mb-3 line-clamp-2">
                          {heroPost.excerpt}
                        </p>
                      )}
                      {heroPost.author && (
                        <div className="text-sm">
                          by{" "}
                          <span className="font-semibold">
                            {heroPost.author.full_name}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </article>
              ) : null}

              {/* Secondary articles */}
              {!loadingHero && secondaryPosts.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {secondaryPosts.map((post, i) => (
                    <article
                      key={post.id}
                      className="bg-white rounded-lg overflow-hidden shadow-md hover:shadow-lg transition"
                    >
                      <img
                        src={getPostImage(post, i + 1)}
                        alt={post.title}
                        className="w-full h-48 object-cover"
                      />
                      <div className="p-4">
                        <div className="flex items-center space-x-2 text-sm text-gray-500 mb-2">
                          {post.category && (
                            <span className="text-teal-600 font-semibold">
                              {post.category.name}
                            </span>
                          )}
                          <span>
                            {formatDate(post.published_at || post.created_at)}
                          </span>
                        </div>
                        <h3 className="text-xl font-bold mb-2">
                          <Link
                            to={`/blog/${post.slug}`}
                            className="hover:text-teal-600"
                          >
                            {post.title}
                          </Link>
                        </h3>
                        {post.author && (
                          <div className="text-sm text-gray-600">
                            by{" "}
                            <span className="hover:text-teal-600">
                              {post.author.full_name}
                            </span>
                          </div>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </div>

            {/* ── Sidebar ─────────────────────────────────────────────── */}
            <div className="space-y-6">
              {/* Tabs widget */}
              <div className="bg-white rounded-lg shadow-md p-5">
                <div className="flex border-b border-gray-200 mb-4">
                  {[
                    { id: "latest", label: "Latest" },
                    { id: "trending", label: "Trending" },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => handleTabChange(tab.id)}
                      className={`flex-1 py-2 text-center font-semibold transition text-sm ${activeTab === tab.id
                          ? "border-b-2 border-teal-600 text-teal-600"
                          : "text-gray-500 hover:text-gray-700"
                        }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                {loadingSidebar ? (
                  <div className="space-y-4">
                    {[...Array(4)].map((_, i) => (
                      <div key={i} className="flex gap-3 animate-pulse">
                        <div className="w-1/3 h-16 bg-gray-200 rounded-md" />
                        <div className="w-2/3 space-y-2">
                          <div className="h-2 bg-gray-200 rounded w-1/2" />
                          <div className="h-3 bg-gray-200 rounded" />
                          <div className="h-3 bg-gray-200 rounded w-3/4" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : sidebarPosts.length > 0 ? (
                  <div className="space-y-4">
                    {sidebarPosts.map((post, i) => (
                      <article key={post.id} className="flex gap-3 items-start">
                        <div className="w-1/3 flex-shrink-0">
                          <img
                            src={getPostImage(post, i)}
                            alt={post.title}
                            className="w-full h-16 object-cover rounded-md"
                          />
                        </div>
                        <div className="w-2/3">
                          {post.category && (
                            <span className="text-xs text-teal-600 font-semibold">
                              {post.category.name}
                            </span>
                          )}
                          <h4 className="text-xs font-bold mt-0.5 leading-snug">
                            <Link
                              to={`/blog/${post.slug}`}
                              className="hover:text-teal-600 line-clamp-2"
                            >
                              {post.title}
                            </Link>
                          </h4>
                          <div className="text-xs text-gray-400 mt-1 flex items-center gap-1">
                            <i className="bi bi-clock" />
                            {post.read_time} min read
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 text-center py-4">
                    No posts found.
                  </p>
                )}
              </div>

              {/* Categories widget */}
              {categories.length > 0 && (
                <div className="bg-white rounded-lg shadow-md p-5">
                  <h3 className="text-lg font-bold mb-4 text-gray-800">
                    Categories
                  </h3>
                  <ul className="space-y-2">
                    <li>
                      <button
                        onClick={() => handleCategoryFilter("")}
                        className={`flex justify-between w-full text-sm py-1 hover:text-teal-600 transition ${!activeCategory
                            ? "text-teal-600 font-semibold"
                            : "text-gray-600"
                          }`}
                      >
                        <span>All Posts</span>
                        <span className="text-gray-400">
                          {pagination.count}
                        </span>
                      </button>
                    </li>
                    {categories.map((cat) => (
                      <li key={cat.id}>
                        <button
                          onClick={() => handleCategoryFilter(cat.slug)}
                          className={`flex justify-between w-full text-sm py-1 hover:text-teal-600 transition ${activeCategory === cat.slug
                              ? "text-teal-600 font-semibold"
                              : "text-gray-600"
                            }`}
                        >
                          <span>{cat.name}</span>
                          <span className="text-gray-400">{cat.post_count}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ── Blog Posts Grid ───────────────────────────────────────────── */}
      <section className="py-16 bg-gray-50">
        <div className="container mx-auto px-4">
          {/* Section header */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
            <h2 className="text-2xl font-bold text-gray-800">
              {searchQuery
                ? `Results for "${searchQuery}"`
                : activeCategory
                  ? categories.find((c) => c.slug === activeCategory)?.name || "Posts"
                  : "All Posts"}
              {pagination.count > 0 && (
                <span className="ml-2 text-base font-normal text-gray-400">
                  ({pagination.count})
                </span>
              )}
            </h2>
            {(activeCategory || searchQuery) && (
              <button
                onClick={() => {
                  const next = new URLSearchParams();
                  setSearchParams(next);
                }}
                className="text-sm text-teal-600 hover:underline flex items-center gap-1"
              >
                <i className="bi bi-x-circle" /> Clear filters
              </button>
            )}
          </div>

          {/* Error state */}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 mb-6 text-center">
              {error}
              <button
                onClick={fetchGridPosts}
                className="ml-3 underline hover:no-underline"
              >
                Retry
              </button>
            </div>
          )}

          {/* Grid */}
          {loadingGrid ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {[...Array(6)].map((_, i) => (
                <PostSkeleton key={i} />
              ))}
            </div>
          ) : posts.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {posts.map((post, i) => (
                <article
                  key={post.id}
                  className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-xl transition group"
                >
                  <Link to={`/blog/${post.slug}`}>
                    <img
                      src={getPostImage(post, i)}
                      alt={post.title}
                      className="w-full h-56 object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                  </Link>
                  <div className="p-5">
                    {post.category && (
                      <button
                        onClick={() => handleCategoryFilter(post.category.slug)}
                        className="text-teal-600 text-sm font-semibold mb-2 hover:underline"
                      >
                        {post.category.name}
                      </button>
                    )}
                    <h2 className="text-xl font-bold mb-3">
                      <Link
                        to={`/blog/${post.slug}`}
                        className="hover:text-teal-600 transition"
                      >
                        {post.title}
                      </Link>
                    </h2>
                    {post.excerpt && (
                      <p className="text-gray-500 text-sm mb-4 line-clamp-2">
                        {post.excerpt}
                      </p>
                    )}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {post.author?.avatar ? (
                          <img
                            src={post.author.avatar}
                            alt={post.author.full_name}
                            className="w-9 h-9 rounded-full object-cover"
                          />
                        ) : (
                          <div className="w-9 h-9 rounded-full bg-teal-100 flex items-center justify-center text-teal-700 text-sm font-bold">
                            {post.author?.full_name?.[0] || "A"}
                          </div>
                        )}
                        <div>
                          <p className="text-sm font-medium text-gray-800">
                            {post.author?.full_name || "Admin"}
                          </p>
                          <p className="text-xs text-gray-400">
                            {formatDate(post.published_at || post.created_at)}
                          </p>
                        </div>
                      </div>
                      <div className="text-xs text-gray-400 flex items-center gap-1">
                        <i className="bi bi-clock" />
                        {post.read_time} min
                      </div>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="text-center py-20">
              <i className="bi bi-journal-x text-5xl text-gray-300 block mb-4" />
              <p className="text-gray-500 text-lg">No posts found.</p>
              {(activeCategory || searchQuery) && (
                <button
                  onClick={() => setSearchParams(new URLSearchParams())}
                  className="mt-3 text-teal-600 hover:underline text-sm"
                >
                  View all posts
                </button>
              )}
            </div>
          )}

          {/* ── Pagination ──────────────────────────────────────────────── */}
          {!loadingGrid && pagination.total_pages > 1 && (
            <div className="flex justify-center mt-12 gap-2 flex-wrap">
              <button
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
                className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <i className="bi bi-chevron-left" />
              </button>

              {[...Array(pagination.total_pages)].map((_, i) => {
                const page = i + 1;
                const isActive = page === currentPage;
                // Show first, last, current ± 1, and ellipsis
                const showPage =
                  page === 1 ||
                  page === pagination.total_pages ||
                  Math.abs(page - currentPage) <= 1;
                const showEllipsisLeft =
                  page === 2 && currentPage > 3;
                const showEllipsisRight =
                  page === pagination.total_pages - 1 &&
                  currentPage < pagination.total_pages - 2;

                if (showEllipsisLeft) {
                  return (
                    <span key={page} className="px-3 py-2 text-gray-400 text-sm">
                      …
                    </span>
                  );
                }
                if (showEllipsisRight) {
                  return (
                    <span key={page} className="px-3 py-2 text-gray-400 text-sm">
                      …
                    </span>
                  );
                }
                if (!showPage) return null;

                return (
                  <button
                    key={page}
                    onClick={() => handlePageChange(page)}
                    className={`px-4 py-2 rounded-lg border text-sm font-medium transition ${isActive
                        ? "bg-teal-600 border-teal-600 text-white"
                        : "border-gray-300 text-gray-600 hover:bg-gray-50"
                      }`}
                  >
                    {page}
                  </button>
                );
              })}

              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === pagination.total_pages}
                className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <i className="bi bi-chevron-right" />
              </button>
            </div>
          )}
        </div>
      </section>
    </main>
  );
};

export default Blog;
