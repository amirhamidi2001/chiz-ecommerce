// src/pages/BlogDetails.jsx
import { useState, useEffect, useCallback, useRef } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { blogAPI, parseErrors } from "../services/api";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const FALLBACK_IMAGES = [
  "/assets/img/person/person-f-1.webp",
  "/assets/img/person/person-f-2.webp",
  "/assets/img/person/person-f-3.webp",
  "/assets/img/person/person-f-4.webp",
];

const getPostImage = (post, index = 0) =>
  post?.cover_image_url || FALLBACK_IMAGES[index % FALLBACK_IMAGES.length];

const formatDate = (dateStr) => {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
};

const formatTimeAgo = (dateStr) => {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes} minute${minutes !== 1 ? "s" : ""} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours !== 1 ? "s" : ""} ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days !== 1 ? "s" : ""} ago`;
  return formatDate(dateStr);
};

// ─── Sub-components ───────────────────────────────────────────────────────────

const DetailSkeleton = () => (
  <div className="animate-pulse space-y-6">
    <div className="h-6 bg-gray-200 rounded w-1/4" />
    <div className="h-10 bg-gray-200 rounded w-3/4" />
    <div className="h-4 bg-gray-200 rounded w-1/2" />
    <div className="h-80 bg-gray-200 rounded-lg" />
    <div className="space-y-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="h-4 bg-gray-200 rounded" style={{ width: `${85 + (i % 3) * 5}%` }} />
      ))}
    </div>
  </div>
);

const AvatarPlaceholder = ({ name, size = "md" }) => {
  const sizeClass = size === "sm" ? "w-8 h-8 text-xs" : size === "lg" ? "w-14 h-14 text-xl" : "w-10 h-10 text-sm";
  return (
    <div className={`${sizeClass} rounded-full bg-teal-100 flex items-center justify-center text-teal-700 font-bold flex-shrink-0`}>
      {name?.[0]?.toUpperCase() || "?"}
    </div>
  );
};

const CommentItem = ({ comment }) => (
  <div className="pb-6">
    <div className="flex gap-4">
      {comment.author_avatar ? (
        <img src={comment.author_avatar} alt={comment.name} className="w-10 h-10 rounded-full object-cover flex-shrink-0" />
      ) : (
        <AvatarPlaceholder name={comment.name} />
      )}
      <div className="flex-1">
        <div className="flex flex-wrap justify-between items-start mb-2">
          <div>
            <h4 className="font-bold text-gray-800">{comment.name}</h4>
            <span className="text-xs text-gray-400">
              <i className="bi bi-clock mr-1" />
              {formatTimeAgo(comment.created_at)}
            </span>
          </div>
        </div>
        <p className="text-gray-600 mb-3 leading-relaxed">{comment.body}</p>

        {/* Replies */}
        {comment.replies?.length > 0 && (
          <div className="mt-4 pl-6 border-l-2 border-gray-200 space-y-4">
            {comment.replies.map((reply) => (
              <div key={reply.id} className="flex gap-4">
                <AvatarPlaceholder name={reply.name} size="sm" />
                <div className="flex-1">
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="font-bold text-gray-800 text-sm">{reply.name}</h4>
                      <span className="text-xs text-gray-400">
                        {formatTimeAgo(reply.created_at)}
                      </span>
                    </div>
                  </div>
                  <p className="text-gray-600 text-sm mt-1 leading-relaxed">{reply.body}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  </div>
);

const RelatedPostCard = ({ post, index }) => (
  <article className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition group">
    <Link to={`/blog/${post.slug}`}>
      <img
        src={getPostImage(post, index)}
        alt={post.title}
        className="w-full h-40 object-cover group-hover:scale-105 transition-transform duration-500"
      />
    </Link>
    <div className="p-4">
      {post.category && (
        <span className="text-teal-600 text-xs font-semibold">{post.category.name}</span>
      )}
      <h3 className="font-bold text-gray-800 mt-1 line-clamp-2 leading-snug">
        <Link to={`/blog/${post.slug}`} className="hover:text-teal-600 transition">
          {post.title}
        </Link>
      </h3>
      <p className="text-xs text-gray-400 mt-2">
        {formatDate(post.published_at || post.created_at)}
      </p>
    </div>
  </article>
);

// ─── Initial form state ───────────────────────────────────────────────────────

const EMPTY_FORM = { name: "", email: "", website: "", body: "" };

// ─── Main component ───────────────────────────────────────────────────────────

const BlogDetails = () => {
  const { slug } = useParams();
  const navigate = useNavigate();

  // ── State ──
  const [post, setPost] = useState(null);
  const [relatedPosts, setRelatedPosts] = useState([]);
  const [comments, setComments] = useState([]);

  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [commentForm, setCommentForm] = useState(EMPTY_FORM);
  const [commentErrors, setCommentErrors] = useState({});
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [commentSuccess, setCommentSuccess] = useState(false);

  const commentFormRef = useRef(null);

  // ── Fetchers ──

  const fetchPost = useCallback(async () => {
    setLoading(true);
    setNotFound(false);
    try {
      const { data } = await blogAPI.getPost(slug);
      setPost(data);
      setComments(data.comments || []);
    } catch (err) {
      if (err.response?.status === 404) {
        setNotFound(true);
      }
    } finally {
      setLoading(false);
    }
  }, [slug]);

  const fetchRelated = useCallback(async () => {
    try {
      const { data } = await blogAPI.getRelatedPosts(slug);
      setRelatedPosts(data.results || data || []);
    } catch {
      setRelatedPosts([]);
    }
  }, [slug]);

  // ── Effects ──

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
    fetchPost();
    fetchRelated();
  }, [slug, fetchPost, fetchRelated]);

  // ── Comment handlers ──

  const handleCommentChange = (e) => {
    const { name, value } = e.target;
    setCommentForm((prev) => ({ ...prev, [name]: value }));
    if (commentErrors[name]) {
      setCommentErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  };

  const handleCommentSubmit = async (e) => {
    e.preventDefault();
    setCommentSubmitting(true);
    setCommentErrors({});
    setCommentSuccess(false);

    try {
      const payload = {
        name: commentForm.name.trim(),
        email: commentForm.email.trim(),
        body: commentForm.body.trim(),
        ...(commentForm.website.trim() ? { website: commentForm.website.trim() } : {}),
      };
      const { data } = await blogAPI.createComment(slug, payload);

      // Append the new comment optimistically
      setComments((prev) => [
        ...prev,
        { ...data, replies: [] },
      ]);
      setCommentForm(EMPTY_FORM);
      setCommentSuccess(true);

      // Auto-hide success after 4 s
      setTimeout(() => setCommentSuccess(false), 4000);
    } catch (err) {
      setCommentErrors(parseErrors(err));
    } finally {
      setCommentSubmitting(false);
    }
  };

  const scrollToCommentForm = () => {
    commentFormRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // ── Render: loading ──

  if (loading) {
    return (
      <main className="bg-white">
        <div className="bg-gray-50 py-8 border-b">
          <div className="container mx-auto px-4 animate-pulse">
            <div className="h-6 bg-gray-200 rounded w-1/3" />
          </div>
        </div>
        <section className="py-12">
          <div className="container mx-auto px-4 max-w-4xl">
            <DetailSkeleton />
          </div>
        </section>
      </main>
    );
  }

  // ── Render: 404 ──

  if (notFound || !post) {
    return (
      <main className="bg-white min-h-[60vh] flex items-center justify-center">
        <div className="text-center px-4">
          <i className="bi bi-journal-x text-6xl text-gray-300 block mb-4" />
          <h2 className="text-2xl font-bold text-gray-700 mb-2">Post not found</h2>
          <p className="text-gray-500 mb-6">
            This post may have been removed or is not yet published.
          </p>
          <Link
            to="/blog"
            className="bg-teal-600 text-white px-6 py-2 rounded-lg hover:bg-teal-700 transition"
          >
            Back to Blog
          </Link>
        </div>
      </main>
    );
  }

  // ── Render: post ──

  return (
    <main className="bg-white">
      {/* ── Breadcrumb ──────────────────────────────────────────────── */}
      <div className="bg-gray-50 py-8 border-b">
        <div className="container mx-auto px-4">
          <nav className="text-sm">
            <ol className="flex flex-wrap items-center gap-2">
              <li>
                <Link to="/" className="text-gray-500 hover:text-teal-600">
                  Home
                </Link>
              </li>
              <li className="text-gray-400">/</li>
              <li>
                <Link to="/blog" className="text-gray-500 hover:text-teal-600">
                  Blog
                </Link>
              </li>
              <li className="text-gray-400">/</li>
              <li className="text-gray-800 font-semibold truncate max-w-[240px]">
                {post.title}
              </li>
            </ol>
          </nav>
        </div>
      </div>

      {/* ── Post Header ─────────────────────────────────────────────── */}
      <section className="py-12">
        <div className="container mx-auto px-4 max-w-4xl">
          {/* Category + meta */}
          <div className="flex flex-wrap items-center gap-3 mb-4">
            {post.category && (
              <Link
                to={`/blog?category=${post.category.slug}`}
                className="bg-teal-600 text-white text-xs font-semibold px-3 py-1 rounded hover:bg-teal-700 transition"
              >
                {post.category.name}
              </Link>
            )}
            <span className="text-gray-400 text-sm flex items-center gap-1">
              <i className="bi bi-clock" />
              {post.read_time} min read
            </span>
            <span className="text-gray-400 text-sm flex items-center gap-1">
              <i className="bi bi-eye" />
              {post.views_count.toLocaleString()} views
            </span>
            <button
              onClick={scrollToCommentForm}
              className="text-gray-400 text-sm flex items-center gap-1 hover:text-teal-600 transition"
            >
              <i className="bi bi-chat" />
              {comments.length} comment{comments.length !== 1 ? "s" : ""}
            </button>
          </div>

          {/* Title */}
          <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-6 leading-tight">
            {post.title}
          </h1>

          {/* Author + date */}
          {post.author && (
            <div className="flex items-center gap-4 mb-8 pb-8 border-b border-gray-100">
              {post.author.avatar ? (
                <img
                  src={post.author.avatar}
                  alt={post.author.full_name}
                  className="w-12 h-12 rounded-full object-cover"
                />
              ) : (
                <AvatarPlaceholder name={post.author.full_name} size="lg" />
              )}
              <div>
                <p className="font-semibold text-gray-800">{post.author.full_name}</p>
                <p className="text-sm text-gray-400">
                  {formatDate(post.published_at || post.created_at)}
                </p>
              </div>
            </div>
          )}

          {/* Cover image */}
          <div className="mb-8 rounded-xl overflow-hidden shadow-lg">
            <img
              src={getPostImage(post, 0)}
              alt={post.title}
              className="w-full max-h-[480px] object-cover"
            />
          </div>
        </div>
      </section>

      {/* ── Post Content ─────────────────────────────────────────────── */}
      <section className="pb-12">
        <div className="container mx-auto px-4 max-w-4xl">
          <div
            className="prose prose-lg prose-gray max-w-none
              prose-headings:font-bold prose-headings:text-gray-900
              prose-p:text-gray-700 prose-p:leading-relaxed
              prose-a:text-teal-600 prose-a:no-underline hover:prose-a:underline
              prose-blockquote:border-l-4 prose-blockquote:border-teal-500 prose-blockquote:pl-4
              prose-blockquote:italic prose-blockquote:text-gray-600
              prose-img:rounded-lg prose-img:shadow-md
              prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded"
            dangerouslySetInnerHTML={{ __html: post.content }}
          />
        </div>
      </section>

      {/* ── Author Bio ───────────────────────────────────────────────── */}
      {post.author && (
        <section className="py-10 bg-gray-50">
          <div className="container mx-auto px-4 max-w-4xl">
            <div className="bg-white rounded-xl shadow-md p-6 flex flex-col sm:flex-row gap-5 items-start">
              {post.author.avatar ? (
                <img
                  src={post.author.avatar}
                  alt={post.author.full_name}
                  className="w-20 h-20 rounded-full object-cover flex-shrink-0"
                />
              ) : (
                <div className="w-20 h-20 rounded-full bg-teal-100 flex items-center justify-center text-teal-700 text-3xl font-bold flex-shrink-0">
                  {post.author.full_name?.[0]?.toUpperCase() || "?"}
                </div>
              )}
              <div>
                <p className="text-xs uppercase tracking-widest text-teal-600 font-semibold mb-1">
                  About the Author
                </p>
                <h3 className="text-xl font-bold text-gray-800 mb-2">
                  {post.author.full_name}
                </h3>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── Related Posts ────────────────────────────────────────────── */}
      {relatedPosts.length > 0 && (
        <section className="py-12">
          <div className="container mx-auto px-4 max-w-5xl">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">Related Posts</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {relatedPosts.map((related, i) => (
                <RelatedPostCard key={related.id} post={related} index={i} />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── Comments List ────────────────────────────────────────────── */}
      {comments.length > 0 && (
        <section className="py-12 bg-gray-50">
          <div className="container mx-auto px-4 max-w-3xl">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-2xl font-bold mb-6 flex items-center gap-2">
                <i className="bi bi-chat-square-text text-teal-600" />
                {comments.length} Comment{comments.length !== 1 ? "s" : ""}
              </h3>
              <div className="divide-y divide-gray-100">
                {comments.map((comment) => (
                  <CommentItem key={comment.id} comment={comment} />
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── Comment Form ─────────────────────────────────────────────── */}
      <section className="py-16" ref={commentFormRef}>
        <div className="container mx-auto px-4 max-w-3xl">
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="mb-6">
              <h3 className="text-2xl font-bold mb-1">Leave a Comment</h3>
              <p className="text-gray-500 text-sm">
                Your email address will not be published. Required fields are marked *
              </p>
            </div>

            {/* Success banner */}
            {commentSuccess && (
              <div className="mb-5 bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-3 flex items-center gap-2">
                <i className="bi bi-check-circle-fill" />
                Your comment has been posted successfully!
              </div>
            )}

            {/* Global error */}
            {commentErrors.non_field_errors && (
              <div className="mb-5 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
                {commentErrors.non_field_errors}
              </div>
            )}

            <form onSubmit={handleCommentSubmit} noValidate>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Full Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    name="name"
                    required
                    value={commentForm.name}
                    onChange={handleCommentChange}
                    placeholder="Enter your full name"
                    className={`w-full border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 transition ${commentErrors.name
                        ? "border-red-400 bg-red-50"
                        : "border-gray-300"
                      }`}
                  />
                  {commentErrors.name && (
                    <p className="text-red-500 text-xs mt-1">{commentErrors.name}</p>
                  )}
                </div>

                {/* Email */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email Address <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="email"
                    name="email"
                    required
                    value={commentForm.email}
                    onChange={handleCommentChange}
                    placeholder="Enter your email address"
                    className={`w-full border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 transition ${commentErrors.email
                        ? "border-red-400 bg-red-50"
                        : "border-gray-300"
                      }`}
                  />
                  {commentErrors.email && (
                    <p className="text-red-500 text-xs mt-1">{commentErrors.email}</p>
                  )}
                </div>
              </div>

              {/* Website */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Website
                </label>
                <input
                  type="url"
                  name="website"
                  value={commentForm.website}
                  onChange={handleCommentChange}
                  placeholder="https://your-website.com (optional)"
                  className={`w-full border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 transition ${commentErrors.website
                      ? "border-red-400 bg-red-50"
                      : "border-gray-300"
                    }`}
                />
                {commentErrors.website && (
                  <p className="text-red-500 text-xs mt-1">{commentErrors.website}</p>
                )}
              </div>

              {/* Comment body */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Your Comment <span className="text-red-500">*</span>
                </label>
                <textarea
                  name="body"
                  rows="5"
                  required
                  value={commentForm.body}
                  onChange={handleCommentChange}
                  placeholder="Write your thoughts here..."
                  className={`w-full border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 transition resize-none ${commentErrors.body
                      ? "border-red-400 bg-red-50"
                      : "border-gray-300"
                    }`}
                />
                {commentErrors.body && (
                  <p className="text-red-500 text-xs mt-1">{commentErrors.body}</p>
                )}
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={commentSubmitting}
                  className="bg-teal-600 text-white px-8 py-2.5 rounded-lg hover:bg-teal-700 transition font-medium text-sm disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {commentSubmitting ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Posting…
                    </>
                  ) : (
                    <>
                      <i className="bi bi-send" />
                      Post Comment
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </section>
    </main>
  );
};

export default BlogDetails;
