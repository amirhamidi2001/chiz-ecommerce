// src/pages/ProductDetails.jsx
import { useState, useEffect, useCallback } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { getProductDetails, getRelatedProducts, createReview, parseErrors, isAuthenticated } from '../services/api';
import { useCart } from '../context/CartContext';
import { useWishlist } from '../context/WishlistContext';

// ─── Spinner ──────────────────────────────────────────────────────────────────
const Spinner = () => (
  <div className="flex justify-center items-center py-32">
    <div className="w-12 h-12 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" />
  </div>
);

// ─── Star renderer ─────────────────────────────────────────────────────────────
const Stars = ({ rating, size = 'text-base' }) => {
  const full = Math.floor(rating);
  const half = rating % 1 !== 0;
  return (
    <div className={`flex text-yellow-400 ${size}`}>
      {[...Array(5)].map((_, i) => (
        <i
          key={i}
          className={`bi ${i < full ? 'bi-star-fill' : i === full && half ? 'bi-star-half' : 'bi-star'
            }`}
        />
      ))}
    </div>
  );
};

// ─── Toast ────────────────────────────────────────────────────────────────────
const Toast = ({ message, type, onClose }) => {
  useEffect(() => {
    const t = setTimeout(onClose, 3500);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-lg text-white transition-all ${type === 'success' ? 'bg-teal-600' : 'bg-red-500'
        }`}
    >
      <i
        className={`bi ${type === 'success' ? 'bi-check-circle' : 'bi-exclamation-circle'
          } text-lg`}
      />
      <span className="text-sm font-medium">{message}</span>
      <button onClick={onClose} className="ml-2 opacity-70 hover:opacity-100">
        <i className="bi bi-x" />
      </button>
    </div>
  );
};

// ─── Related Product Card ──────────────────────────────────────────────────────
const RelatedCard = ({ product }) => {
  const img = product.thumbnail_url || '/assets/img/product/product-2.webp';
  return (
    <div className="group bg-white rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-all duration-300">
      <div className="relative overflow-hidden">
        <img
          src={img}
          alt={product.name}
          className="w-full h-48 object-cover transition-transform duration-500 group-hover:scale-105"
          onError={(e) => { e.target.src = '/assets/img/product/product-2.webp'; }}
        />
        {product.is_sale && (
          <span className="absolute top-2 left-2 bg-red-500 text-white text-xs font-semibold px-2 py-0.5 rounded">
            Sale
          </span>
        )}
        {product.is_new && (
          <span className="absolute top-2 left-2 bg-teal-500 text-white text-xs font-semibold px-2 py-0.5 rounded">
            New
          </span>
        )}
      </div>
      <div className="p-3">
        <div className="text-xs text-gray-500 truncate">{product.category?.name}</div>
        <h5 className="font-semibold text-sm line-clamp-2 mt-1">
          <Link to={`/product/${product.slug}`} className="hover:text-teal-600">
            {product.name}
          </Link>
        </h5>
        <div className="flex items-center justify-between mt-2">
          <span className="font-bold text-teal-700">${Number(product.price).toFixed(2)}</span>
          <div className="flex items-center gap-1 text-xs text-gray-500">
            <i className="bi bi-star-fill text-yellow-400" />
            {product.rating}
          </div>
        </div>
      </div>
    </div>
  );
};

// ─── Star picker (interactive, used inside AddReviewForm) ─────────────────────
const StarPicker = ({ value, onChange, error }) => (
  <div>
    <label className="block text-sm font-medium text-gray-700 mb-1">
      Rating <span className="text-red-500">*</span>
    </label>
    <div className="flex gap-1" role="group" aria-label="Star rating">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          aria-label={`${star} star${star > 1 ? 's' : ''}`}
          onClick={() => onChange(star)}
          className={`text-3xl transition-transform hover:scale-110 focus:outline-none ${star <= value ? 'text-yellow-400' : 'text-gray-300 hover:text-yellow-300'
            }`}
        >
          <i className="bi bi-star-fill" />
        </button>
      ))}
    </div>
    {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
  </div>
);

// ─── Add Review Form ───────────────────────────────────────────────────────────
/**
 * Self-contained review submission form.
 *
 * Props:
 *   productSlug  {string}    – slug of the product being reviewed
 *   onSuccess    {function}  – called with the new review object on success
 */
const FORM_INITIAL = { rating: 0, headline: '', comment: '' };

const AddReviewForm = ({ productSlug, onSuccess }) => {
  const [form, setForm] = useState(FORM_INITIAL);
  const [fieldErrors, setFieldErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  // ── field change ───────────────────────────────────────────────────────────
  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    // Clear the error for this field as soon as the user starts typing
    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: '' }));
    }
  };

  const handleRatingChange = (value) => {
    setForm((prev) => ({ ...prev, rating: value }));
    if (fieldErrors.rating) {
      setFieldErrors((prev) => ({ ...prev, rating: '' }));
    }
  };

  // ── client-side validation ─────────────────────────────────────────────────
  const validate = () => {
    const errs = {};
    if (!form.rating) errs.rating = 'Please select a star rating.';
    if (!form.comment.trim()) errs.comment = 'A review comment is required.';
    return errs;
  };

  // ── submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();

    const clientErrs = validate();
    if (Object.keys(clientErrs).length) {
      setFieldErrors(clientErrs);
      return;
    }

    setSubmitting(true);
    setFieldErrors({});

    try {
      const { data: newReview } = await createReview(productSlug, {
        rating: form.rating,
        headline: form.headline.trim(),
        comment: form.comment.trim(),
      });

      setSubmitted(true);
      setForm(FORM_INITIAL);
      onSuccess(newReview);
    } catch (err) {
      // Map DRF field errors (and non_field_errors) back to the form
      setFieldErrors(parseErrors(err));
    } finally {
      setSubmitting(false);
    }
  };

  // ── logged-out state ───────────────────────────────────────────────────────
  // Reviews now require an authenticated account (they're tied to a real
  // user, not a free-text name) — show an inline prompt instead of a form
  // that would 401 on submit. Full auth-gating UX (e.g. redirecting back to
  // this exact product page after login) is tracked as its own follow-up
  // task; this is the minimal fix so logged-out visitors get a clear,
  // immediate explanation instead of a confusing failed submission.
  if (!isAuthenticated()) {
    return (
      <div className="bg-gray-50 border border-gray-100 rounded-2xl p-6 md:p-8 mb-10 text-center">
        <i className="bi bi-pencil-square text-teal-600 text-2xl mb-2 block" />
        <h4 className="font-bold text-gray-800 mb-1">Want to leave a review?</h4>
        <p className="text-sm text-gray-500 mb-4">
          Please log in to your account to write a review.
        </p>
        <Link
          to="/login"
          className="inline-block bg-teal-600 text-white px-6 py-2.5 rounded-lg font-semibold hover:bg-teal-700 active:bg-teal-800 transition text-sm"
        >
          Log In
        </Link>
      </div>
    );
  }

  // ── success state ──────────────────────────────────────────────────────────
  if (submitted) {
    return (
      <div className="bg-teal-50 border border-teal-200 rounded-2xl p-8 text-center mb-10">
        <i className="bi bi-check-circle-fill text-teal-500 text-4xl mb-3 block" />
        <h4 className="font-bold text-lg text-teal-800 mb-1">
          Thank you for your review!
        </h4>
        <p className="text-sm text-teal-700 mb-4">
          Your feedback helps other customers make better decisions.
        </p>
        <button
          onClick={() => setSubmitted(false)}
          className="text-sm text-teal-600 hover:underline font-medium"
        >
          Write another review
        </button>
      </div>
    );
  }

  // ── form ───────────────────────────────────────────────────────────────────
  return (
    <div className="bg-gray-50 border border-gray-100 rounded-2xl p-6 md:p-8 mb-10">
      <h3 className="text-xl font-bold text-gray-800 mb-6 flex items-center gap-2">
        <i className="bi bi-pencil-square text-teal-600" />
        Write a Review
      </h3>

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        {/* Star Rating */}
        <StarPicker
          value={form.rating}
          onChange={handleRatingChange}
          error={fieldErrors.rating}
        />

        {/* Headline (optional) */}
        <div>
          <label htmlFor="review-headline" className="block text-sm font-medium text-gray-700 mb-1">
            Review Title{' '}
            <span className="text-gray-400 font-normal text-xs">(optional)</span>
          </label>
          <input
            id="review-headline"
            type="text"
            name="headline"
            value={form.headline}
            onChange={handleChange}
            placeholder="Summarise your experience in one line"
            className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm outline-none transition focus:ring-2 focus:ring-teal-400 focus:border-teal-400 bg-white hover:border-gray-400"
          />
        </div>

        {/* Comment */}
        <div>
          <label htmlFor="review-comment" className="block text-sm font-medium text-gray-700 mb-1">
            Review <span className="text-red-500">*</span>
          </label>
          <textarea
            id="review-comment"
            name="comment"
            value={form.comment}
            onChange={handleChange}
            rows={5}
            placeholder="What did you think about this product? Would you recommend it?"
            className={`w-full border rounded-lg px-4 py-2.5 text-sm outline-none transition focus:ring-2 focus:ring-teal-400 focus:border-teal-400 resize-none ${fieldErrors.comment
              ? 'border-red-400 bg-red-50'
              : 'border-gray-300 bg-white hover:border-gray-400'
              }`}
          />
          {fieldErrors.comment && (
            <p className="text-red-500 text-xs mt-1">{fieldErrors.comment}</p>
          )}
        </div>

        {/* Non-field / network error */}
        {fieldErrors.non_field_errors && (
          <div className="flex items-center gap-2 text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm">
            <i className="bi bi-exclamation-circle-fill flex-shrink-0" />
            {fieldErrors.non_field_errors}
          </div>
        )}

        {/* Submit */}
        <div className="flex items-center gap-4 pt-1">
          <button
            type="submit"
            disabled={submitting}
            className="bg-teal-600 text-white px-7 py-2.5 rounded-lg font-semibold hover:bg-teal-700 active:bg-teal-800 transition flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {submitting ? (
              <>
                <i className="bi bi-arrow-clockwise animate-spin" />
                Submitting…
              </>
            ) : (
              <>
                <i className="bi bi-send" />
                Submit Review
              </>
            )}
          </button>
          <p className="text-xs text-gray-400">
            Fields marked <span className="text-red-500">*</span> are required.
          </p>
        </div>
      </form>
    </div>
  );
};

// ─── Main Component ────────────────────────────────────────────────────────────
const ProductDetails = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { addToCart } = useCart();
  const { toggleWishlist, isInWishlist } = useWishlist();

  const [product, setProduct] = useState(null);
  const [relatedProducts, setRelatedProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Gallery state
  const [selectedImage, setSelectedImage] = useState(null);
  const [currentIndex, setCurrentIndex] = useState(0);

  // UI state
  const [quantity, setQuantity] = useState(1);
  const [selectedColor, setSelectedColor] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  // Action states
  const [addingToCart, setAddingToCart] = useState(false);
  const [buyingNow, setBuyingNow] = useState(false);
  const [wishlistToggling, setWishlistToggling] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (message, type = 'success') => setToast({ message, type });
  const hideToast = useCallback(() => setToast(null), []);

  const productInWishlist = product ? isInWishlist(product.id) : false;

  const handleToggleWishlist = async () => {
    if (!product) return;
    setWishlistToggling(true);
    const result = await toggleWishlist(product.id);
    setWishlistToggling(false);
    showToast(result.message, result.success ? 'success' : 'error');
  };

  // ── Fetch product ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!slug) return;
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      setQuantity(1);
      setActiveTab('overview');
      try {
        const [productRes, relatedRes] = await Promise.all([
          getProductDetails(slug),
          getRelatedProducts(slug).catch(() => ({ data: [] })),
        ]);
        const data = productRes.data;
        setProduct(data);
        setRelatedProducts(
          Array.isArray(relatedRes.data) ? relatedRes.data : relatedRes.data.results || [],
        );

        const firstImage =
          data.thumbnail_url ||
          (data.images?.length ? data.images[0].image : '/assets/img/product/product-3.webp');
        setSelectedImage(firstImage);
        setCurrentIndex(0);

        if (data.colors?.length) setSelectedColor(data.colors[0].color);
      } catch (err) {
        setError(
          err.response?.status === 404
            ? 'Product not found.'
            : 'Failed to load product. Please try again.',
        );
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [slug]);

  // ── Review submission callback ─────────────────────────────────────────────
  /**
   * Called by AddReviewForm on success with the newly created review object.
   * Prepends the review and increments the counter; no re-fetch needed.
   */
  const handleReviewAdded = useCallback((newReview) => {
    setProduct((prev) => ({
      ...prev,
      reviews: [newReview, ...(prev.reviews || [])],
      reviews_count: (prev.reviews_count || 0) + 1,
    }));
    showToast('Your review has been posted!', 'success');
    setActiveTab('reviews');
  }, []);

  // ── Early returns ──────────────────────────────────────────────────────────
  if (loading) return <Spinner />;

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <i className="bi bi-exclamation-triangle text-6xl text-red-400 mb-4" />
        <h2 className="text-2xl font-bold text-gray-700 mb-3">{error}</h2>
        <div className="flex gap-3">
          <button
            onClick={() => navigate(-1)}
            className="border border-gray-300 px-5 py-2 rounded-lg hover:bg-gray-50"
          >
            Go Back
          </button>
          <Link to="/category" className="bg-teal-600 text-white px-5 py-2 rounded-lg hover:bg-teal-700">
            Browse Products
          </Link>
        </div>
      </div>
    );
  }

  if (!product) return null;

  // ── Derived values ─────────────────────────────────────────────────────────
  const allImages = product.images?.length
    ? product.images.map((img) => img.image)
    : [product.thumbnail_url || '/assets/img/product/product-3.webp'];

  const savings = product.original_price
    ? (Number(product.original_price) - Number(product.price)).toFixed(2)
    : null;
  const discountPercent = product.discount_percent || 0;

  // Gallery handlers
  const handleThumbnail = (img, idx) => { setSelectedImage(img); setCurrentIndex(idx); };
  const handlePrev = () => {
    const idx = currentIndex === 0 ? allImages.length - 1 : currentIndex - 1;
    setCurrentIndex(idx); setSelectedImage(allImages[idx]);
  };
  const handleNext = () => {
    const idx = currentIndex === allImages.length - 1 ? 0 : currentIndex + 1;
    setCurrentIndex(idx); setSelectedImage(allImages[idx]);
  };

  // Quantity handlers
  const maxQty = product.stock || 1;
  const increaseQty = () => { if (quantity < maxQty) setQuantity((q) => q + 1); };
  const decreaseQty = () => { if (quantity > 1) setQuantity((q) => q - 1); };

  // Cart handlers
  const handleAddToCart = async () => {
    setAddingToCart(true);
    const result = await addToCart(product.id, quantity);
    setAddingToCart(false);
    showToast(result.message, result.success ? 'success' : 'error');
  };

  const handleBuyNow = async () => {
    setBuyingNow(true);
    const result = await addToCart(product.id, quantity);
    setBuyingNow(false);
    if (result.success) {
      navigate('/cart');
    } else {
      showToast(result.message, 'error');
    }
  };

  // Reviews distribution
  const reviews = product.reviews || [];
  const ratingDist = [5, 4, 3, 2, 1].map((stars) => {
    const count = reviews.filter((r) => r.rating === stars).length;
    const pct = reviews.length ? Math.round((count / reviews.length) * 100) : 0;
    return { stars, count, pct };
  });

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      {toast && <Toast message={toast.message} type={toast.type} onClose={hideToast} />}

      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Product Details</h1>
          <nav className="text-sm" aria-label="Breadcrumb">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li>
                <Link to="/category" className="text-teal-700 hover:underline">
                  {product.category?.name || 'Category'}
                </Link>
              </li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600 line-clamp-1 max-w-xs">{product.name}</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Product Section */}
      <section className="py-12 bg-white">
        <div className="container mx-auto px-4">
          <div className="flex flex-col lg:flex-row gap-8">

            {/* Gallery */}
            <div className="lg:w-7/12">
              <div className="relative bg-gray-100 rounded-2xl overflow-hidden mb-4">
                <img
                  src={selectedImage}
                  alt={product.name}
                  className="w-full h-auto object-contain max-h-[520px]"
                  onError={(e) => { e.target.src = '/assets/img/product/product-3.webp'; }}
                />
                {allImages.length > 1 && (
                  <>
                    <button
                      onClick={handlePrev}
                      className="absolute left-3 top-1/2 -translate-y-1/2 w-10 h-10 bg-white/80 rounded-full flex items-center justify-center hover:bg-white shadow-md transition"
                    >
                      <i className="bi bi-chevron-left text-xl" />
                    </button>
                    <button
                      onClick={handleNext}
                      className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 bg-white/80 rounded-full flex items-center justify-center hover:bg-white shadow-md transition"
                    >
                      <i className="bi bi-chevron-right text-xl" />
                    </button>
                  </>
                )}
                {allImages.length > 1 && (
                  <div className="absolute bottom-3 right-3 bg-black/50 text-white text-xs px-2 py-1 rounded-full">
                    {currentIndex + 1} / {allImages.length}
                  </div>
                )}
              </div>

              {/* Thumbnails */}
              {allImages.length > 1 && (
                <div className="grid grid-cols-6 gap-2">
                  {allImages.map((img, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleThumbnail(img, idx)}
                      className={`border-2 rounded-lg overflow-hidden transition ${selectedImage === img
                        ? 'border-teal-600'
                        : 'border-transparent hover:border-gray-300'
                        }`}
                    >
                      <img
                        src={img}
                        alt={`Thumb ${idx + 1}`}
                        className="w-full h-20 object-cover"
                        onError={(e) => { e.target.src = '/assets/img/product/product-2.webp'; }}
                      />
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Product Info */}
            <div className="lg:w-5/12">
              {/* Category & Rating */}
              <div className="flex justify-between items-start mb-3">
                <span className="bg-teal-100 text-teal-700 text-xs font-semibold px-3 py-1 rounded-full">
                  {product.category?.name || 'Uncategorised'}
                </span>
                <div className="flex items-center gap-2">
                  <Stars rating={Number(product.rating)} />
                  <span className="text-gray-500 text-sm">({product.reviews_count} reviews)</span>
                </div>
              </div>

              {/* Brand */}
              {product.brand && (
                <div className="text-sm text-gray-500 mb-1">
                  Brand:{' '}
                  <span className="font-medium text-gray-700">{product.brand.name}</span>
                </div>
              )}

              {/* Title */}
              <h1 className="text-2xl md:text-3xl font-bold text-gray-800 mb-4">
                {product.name}
              </h1>

              {/* Price */}
              <div className="mb-4">
                <div className="flex items-baseline gap-3">
                  <span className="text-3xl font-bold text-teal-700">
                    ${Number(product.price).toFixed(2)}
                  </span>
                  {product.original_price && (
                    <span className="text-gray-400 line-through">
                      ${Number(product.original_price).toFixed(2)}
                    </span>
                  )}
                </div>
                {savings && (
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-teal-600 text-sm">Save ${savings}</span>
                    {discountPercent > 0 && (
                      <span className="bg-red-100 text-red-600 text-xs px-2 py-0.5 rounded-full">
                        ({discountPercent}% off)
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Short description */}
              {product.short_description && (
                <p className="text-gray-600 mb-4 text-sm">{product.short_description}</p>
              )}

              {/* Full description */}
              {product.description && (
                <p className="text-gray-600 mb-5">{product.description}</p>
              )}

              {/* Availability */}
              <div className="flex justify-between items-center bg-teal-50 p-3 rounded-lg mb-5">
                <div className="flex items-center gap-2">
                  {product.stock > 0 ? (
                    <>
                      <i className="bi bi-check-circle-fill text-teal-600" />
                      <span className="font-medium text-teal-800">In Stock</span>
                    </>
                  ) : (
                    <>
                      <i className="bi bi-x-circle-fill text-red-500" />
                      <span className="font-medium text-red-700">Out of Stock</span>
                    </>
                  )}
                </div>
                {product.stock > 0 && product.stock <= 20 && (
                  <div className="text-sm text-orange-600 font-medium">
                    Only {product.stock} remaining!
                  </div>
                )}
                {product.stock > 20 && (
                  <div className="text-sm text-gray-600">{product.stock} in stock</div>
                )}
              </div>

              {/* Color Selection */}
              {product.colors?.length > 0 && (
                <div className="mb-5">
                  <label className="block font-medium text-gray-700 mb-2">
                    Available Colors:
                  </label>
                  <div className="flex gap-3 flex-wrap">
                    {product.colors.map(({ color }) => (
                      <button
                        key={color.id}
                        onClick={() => setSelectedColor(color)}
                        className={`w-10 h-10 rounded-full border-2 transition ${selectedColor?.id === color.id
                          ? 'border-teal-600 ring-2 ring-teal-300'
                          : 'border-gray-300 hover:border-gray-400'
                          }`}
                        style={{ backgroundColor: color.hex_code }}
                        title={color.name}
                      >
                        {selectedColor?.id === color.id && (
                          <i className="bi bi-check text-white text-sm flex justify-center items-center h-full drop-shadow" />
                        )}
                      </button>
                    ))}
                  </div>
                  {selectedColor && (
                    <div className="text-sm text-gray-500 mt-2">
                      Selected: <span className="font-medium">{selectedColor.name}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Quantity & Actions */}
              <div className="mb-6">
                <label className="block font-medium text-gray-700 mb-2">Quantity:</label>
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex border border-gray-300 rounded-lg overflow-hidden">
                    <button
                      onClick={decreaseQty}
                      disabled={quantity <= 1}
                      className="px-3 py-2 hover:bg-gray-100 transition disabled:opacity-40"
                    >
                      <i className="bi bi-dash" />
                    </button>
                    <input
                      type="number"
                      value={quantity}
                      onChange={(e) =>
                        setQuantity(Math.min(maxQty, Math.max(1, parseInt(e.target.value) || 1)))
                      }
                      className="w-16 text-center border-x border-gray-300 py-2 outline-none"
                      min="1"
                      max={maxQty}
                    />
                    <button
                      onClick={increaseQty}
                      disabled={quantity >= maxQty}
                      className="px-3 py-2 hover:bg-gray-100 transition disabled:opacity-40"
                    >
                      <i className="bi bi-plus" />
                    </button>
                  </div>
                  <span className="text-sm text-gray-500">
                    {product.stock > 0 ? `${product.stock} available` : 'Out of stock'}
                  </span>
                </div>

                {/* Action Buttons */}
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={handleAddToCart}
                    disabled={product.stock === 0 || addingToCart}
                    className="flex-1 bg-teal-600 text-white py-3 rounded-lg font-semibold hover:bg-teal-700 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {addingToCart ? (
                      <><i className="bi bi-arrow-clockwise animate-spin" /> Adding…</>
                    ) : (
                      <><i className="bi bi-bag-plus" /> Add to Cart</>
                    )}
                  </button>
                  <button
                    onClick={handleBuyNow}
                    disabled={product.stock === 0 || buyingNow}
                    className="flex-1 border border-teal-600 text-teal-600 py-3 rounded-lg font-semibold hover:bg-teal-50 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {buyingNow ? (
                      <><i className="bi bi-arrow-clockwise animate-spin" /> Processing…</>
                    ) : (
                      <><i className="bi bi-lightning" /> Buy Now</>
                    )}
                  </button>
                  <button
                    onClick={handleToggleWishlist}
                    disabled={wishlistToggling}
                    className={`p-3 border rounded-lg transition flex items-center justify-center ${productInWishlist
                      ? 'bg-red-50 border-red-200 text-red-600 hover:bg-red-100'
                      : 'border-gray-300 text-gray-600 hover:bg-gray-50'
                      } disabled:opacity-50 disabled:cursor-not-allowed`}
                    title={productInWishlist ? 'Remove from Wishlist' : 'Add to Wishlist'}
                  >
                    {wishlistToggling ? (
                      <i className="bi bi-arrow-repeat animate-spin" />
                    ) : (
                      <i className={`bi ${productInWishlist ? 'bi-heart-fill' : 'bi-heart'} text-xl`} />
                    )}
                  </button>
                </div>
              </div>

              {/* Social Meta */}
              <div className="border-t border-gray-100 pt-4 flex gap-4 text-sm text-gray-500">
                <span className="flex items-center gap-1">
                  <i className="bi bi-share" />
                  <a href="#" className="hover:text-teal-600">Share</a>
                </span>
                <span className="flex items-center gap-1">
                  <i className="bi bi-heart" />
                  <a
                    href="#"
                    className="hover:text-teal-600"
                    onClick={(e) => { e.preventDefault(); handleToggleWishlist(); }}
                  >
                    Wishlist
                  </a>
                </span>
                {product.brand && (
                  <span className="flex items-center gap-1">
                    <i className="bi bi-shop" />
                    <a href="#" className="hover:text-teal-600">{product.brand.name}</a>
                  </span>
                )}
              </div>

              {/* Delivery Info */}
              <div className="mt-4 grid grid-cols-3 gap-3 text-center text-xs text-gray-500">
                <div className="bg-gray-50 p-2 rounded-lg">
                  <i className="bi bi-truck text-teal-600 block text-lg mb-1" />
                  Free Shipping
                </div>
                <div className="bg-gray-50 p-2 rounded-lg">
                  <i className="bi bi-arrow-return-left text-teal-600 block text-lg mb-1" />
                  30-Day Returns
                </div>
                <div className="bg-gray-50 p-2 rounded-lg">
                  <i className="bi bi-shield-check text-teal-600 block text-lg mb-1" />
                  Secure Pay
                </div>
              </div>
            </div>
          </div>

          {/* ── Tabs ─────────────────────────────────────────────────────────── */}
          <div className="mt-16">
            <div className="border-b border-gray-200 mb-8">
              <nav className="flex gap-0 overflow-x-auto">
                {[
                  { id: 'overview', label: 'Overview' },
                  { id: 'specifications', label: 'Specifications' },
                  { id: 'technical', label: 'Technical Details' },
                  { id: 'reviews', label: `Reviews (${product.reviews_count || 0})` },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`px-6 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition ${activeTab === tab.id
                      ? 'border-teal-600 text-teal-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                      }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </nav>
            </div>

            {/* Overview Tab */}
            {activeTab === 'overview' && (
              <div className="prose max-w-none text-gray-600">
                {product.description ? (
                  <p>{product.description}</p>
                ) : (
                  <p className="text-gray-400 italic">No product description available.</p>
                )}
              </div>
            )}

            {/* Specifications Tab */}
            {activeTab === 'specifications' && (
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-semibold text-lg mb-4">Key Features</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-50 p-4 rounded-xl text-center">
                      <i className="bi bi-star text-2xl text-teal-600 mb-2 block" />
                      <h5 className="font-semibold">Premium Quality</h5>
                      <p className="text-sm text-gray-500">Built to the highest standards</p>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-xl text-center">
                      <i className="bi bi-patch-check text-2xl text-teal-600 mb-2 block" />
                      <h5 className="font-semibold">Certified</h5>
                      <p className="text-sm text-gray-500">Tested and certified safe</p>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-xl text-center">
                      <i className="bi bi-box-seam text-2xl text-teal-600 mb-2 block" />
                      <h5 className="font-semibold">Ready to Ship</h5>
                      <p className="text-sm text-gray-500">Fast and reliable shipping</p>
                    </div>
                    <div className="bg-gray-50 p-4 rounded-xl text-center">
                      <i className="bi bi-person-check text-2xl text-teal-600 mb-2 block" />
                      <h5 className="font-semibold">Comfort First</h5>
                      <p className="text-sm text-gray-500">Designed for your comfort</p>
                    </div>
                  </div>
                </div>
                <div className="bg-gray-50 p-6 rounded-xl">
                  <h4 className="text-lg font-semibold mb-4">Package Contents</h4>
                  <ul className="space-y-2">
                    <li className="flex items-center gap-2">
                      <i className="bi bi-check-circle text-teal-600" /> {product.name}
                    </li>
                    <li className="flex items-center gap-2">
                      <i className="bi bi-check-circle text-teal-600" /> Premium Carrying Case
                    </li>
                    <li className="flex items-center gap-2">
                      <i className="bi bi-check-circle text-teal-600" /> USB-C Fast Charging Cable
                    </li>
                    <li className="flex items-center gap-2">
                      <i className="bi bi-check-circle text-teal-600" /> Quick Start Guide
                    </li>
                    <li className="flex items-center gap-2">
                      <i className="bi bi-check-circle text-teal-600" /> Warranty Documentation
                    </li>
                  </ul>
                  {product.brand && (
                    <div className="mt-4 pt-4 border-t">
                      <p className="text-sm text-gray-600">
                        Brand:{' '}
                        <span className="font-semibold">{product.brand.name}</span>
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Technical Details Tab */}
            {activeTab === 'technical' && (
              <div className="grid md:grid-cols-2 gap-8">
                <div>
                  <h4 className="text-lg font-semibold mb-3">Product Information</h4>
                  <div className="bg-gray-50 rounded-xl divide-y">
                    <div className="flex justify-between p-3">
                      <span className="text-gray-600">Category</span>
                      <span className="font-medium">{product.category?.name || '—'}</span>
                    </div>
                    <div className="flex justify-between p-3">
                      <span className="text-gray-600">Brand</span>
                      <span className="font-medium">{product.brand?.name || '—'}</span>
                    </div>
                    <div className="flex justify-between p-3">
                      <span className="text-gray-600">SKU / Slug</span>
                      <span className="font-medium text-sm">{product.slug}</span>
                    </div>
                    <div className="flex justify-between p-3">
                      <span className="text-gray-600">Stock</span>
                      <span className={`font-medium ${product.stock > 0 ? 'text-teal-700' : 'text-red-600'}`}>
                        {product.stock > 0 ? `${product.stock} units` : 'Out of Stock'}
                      </span>
                    </div>
                    <div className="flex justify-between p-3">
                      <span className="text-gray-600">Rating</span>
                      <span className="font-medium">{product.rating} / 5</span>
                    </div>
                  </div>
                </div>
                <div>
                  <h4 className="text-lg font-semibold mb-3">Available Colors</h4>
                  {product.colors?.length > 0 ? (
                    <div className="bg-gray-50 rounded-xl p-4">
                      <div className="flex flex-wrap gap-3">
                        {product.colors.map(({ color }) => (
                          <div key={color.id} className="flex items-center gap-2">
                            <span
                              className="w-5 h-5 rounded-full border border-gray-300 inline-block"
                              style={{ backgroundColor: color.hex_code }}
                            />
                            <span className="text-sm">{color.name}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-gray-500 text-sm">No color variants available.</p>
                  )}
                  <h4 className="text-lg font-semibold mb-3 mt-6">Pricing</h4>
                  <div className="bg-gray-50 rounded-xl divide-y">
                    <div className="flex justify-between p-3">
                      <span className="text-gray-600">Current Price</span>
                      <span className="font-bold text-teal-700">
                        ${Number(product.price).toFixed(2)}
                      </span>
                    </div>
                    {product.original_price && (
                      <div className="flex justify-between p-3">
                        <span className="text-gray-600">Original Price</span>
                        <span className="font-medium line-through text-gray-400">
                          ${Number(product.original_price).toFixed(2)}
                        </span>
                      </div>
                    )}
                    {discountPercent > 0 && (
                      <div className="flex justify-between p-3">
                        <span className="text-gray-600">Discount</span>
                        <span className="font-medium text-red-500">{discountPercent}% off</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* ── Reviews Tab ─────────────────────────────────────────────────── */}
            {activeTab === 'reviews' && (
              <div>
                {/* Rating summary */}
                <div className="flex flex-col md:flex-row gap-8 mb-10">
                  {/* Aggregate score */}
                  <div className="md:w-1/4 flex flex-col items-center justify-center bg-gray-50 rounded-2xl p-6 text-center">
                    <span className="text-6xl font-bold text-gray-800 leading-none">
                      {Number(product.rating).toFixed(1)}
                    </span>
                    <Stars rating={Number(product.rating)} size="text-xl" />
                    <p className="text-sm text-gray-500 mt-2">
                      {reviews.length} {reviews.length === 1 ? 'review' : 'reviews'}
                    </p>
                  </div>

                  {/* Distribution bars */}
                  <div className="flex-1 flex flex-col justify-center gap-2">
                    {ratingDist.map((item) => (
                      <div key={item.stars} className="flex items-center gap-3">
                        <span className="text-sm w-8 text-gray-600">{item.stars}★</span>
                        <div className="flex-1 h-2.5 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-yellow-400 rounded-full transition-all duration-500"
                            style={{ width: `${item.pct}%` }}
                          />
                        </div>
                        <span className="text-sm text-gray-500 w-6 text-right">
                          {item.count}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Add Review Form */}
                <AddReviewForm productSlug={product.slug} onSuccess={handleReviewAdded} />

                {/* Reviews list */}
                {reviews.length > 0 ? (
                  <div className="space-y-6">
                    {reviews.map((review) => (
                      <div key={review.id} className="border-b border-gray-100 pb-6 last:border-0">
                        <div className="flex gap-4 mb-3">
                          {/* Avatar initial */}
                          <div className="w-12 h-12 rounded-full bg-teal-100 flex items-center justify-center text-teal-700 font-bold text-lg flex-shrink-0">
                            {review.name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-semibold text-gray-800">{review.name}</div>
                            <div className="flex items-center gap-2 text-sm text-gray-500">
                              <Stars rating={review.rating} size="text-xs" />
                              <span>
                                {new Date(review.created_at).toLocaleDateString('en-US', {
                                  year: 'numeric',
                                  month: 'long',
                                  day: 'numeric',
                                })}
                              </span>
                            </div>
                          </div>
                        </div>
                        {review.headline && (
                          <h5 className="font-semibold text-lg mb-2 text-gray-800">
                            {review.headline}
                          </h5>
                        )}
                        <p className="text-gray-600 mb-3">{review.comment}</p>
                        <div className="flex gap-4">
                          <button className="text-sm text-gray-500 hover:text-teal-600 flex items-center gap-1">
                            <i className="bi bi-hand-thumbs-up" /> Helpful
                          </button>
                          <button className="text-sm text-gray-500 hover:text-teal-600 flex items-center gap-1">
                            <i className="bi bi-chat-dots" /> Reply
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-400">
                    <i className="bi bi-chat-square-text text-4xl mb-3 block" />
                    <p className="text-lg font-medium mb-1">No reviews yet</p>
                    <p className="text-sm">Be the first to share your thoughts above!</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Related Products */}
          {relatedProducts.length > 0 && (
            <div className="mt-16">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-800">Related Products</h2>
                <Link to="/category" className="text-teal-600 hover:underline text-sm">
                  View All <i className="bi bi-arrow-right" />
                </Link>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-5">
                {relatedProducts.map((rp) => (
                  <RelatedCard key={rp.id} product={rp} />
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    </>
  );
};

export default ProductDetails;
