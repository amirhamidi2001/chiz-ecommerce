import axios from 'axios';

// ─── Base instance ─────────────────────────────────────────────────────────
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
});

// ─── Token helpers ─────────────────────────────────────────────────────────
export const getAccessToken = () => localStorage.getItem('access_token');
export const getRefreshToken = () => localStorage.getItem('refresh_token');

export const setTokens = ({ access, refresh }) => {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
};

export const clearTokens = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
};

export const isAuthenticated = () => Boolean(getAccessToken());

// ─── Request interceptor — attach Bearer token ─────────────────────────────
api.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error),
);

// ─── Response interceptor — silent token refresh on 401 ───────────────────
const AUTH_PATHS = ['/auth/login/', '/auth/register/', '/auth/token/refresh/'];

const isAuthEndpoint = (config) =>
  AUTH_PATHS.some((path) => config?.url?.includes(path));

let _isRefreshing = false;
let _queue = [];

const processQueue = (error, token = null) => {
  _queue.forEach(({ resolve, reject }) =>
    error ? reject(error) : resolve(token),
  );
  _queue = [];
};

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;

    if (
      error.response?.status !== 401 ||
      original._retried ||
      isAuthEndpoint(original)
    ) {
      return Promise.reject(error);
    }

    if (_isRefreshing) {
      return new Promise((resolve, reject) => _queue.push({ resolve, reject }))
        .then((token) => {
          original.headers.Authorization = `Bearer ${token}`;
          return api(original);
        });
    }

    original._retried = true;
    _isRefreshing = true;

    try {
      const refresh = getRefreshToken();
      if (!refresh) throw new Error('No refresh token');

      const { data } = await axios.post(
        `${api.defaults.baseURL}/auth/token/refresh/`,
        { refresh },
      );

      setTokens({ access: data.access, refresh: data.refresh ?? refresh });
      processQueue(null, data.access);
      original.headers.Authorization = `Bearer ${data.access}`;
      return api(original);
    } catch (err) {
      processQueue(err, null);
      clearTokens();
      window.location.href = '/login';
      return Promise.reject(err);
    } finally {
      _isRefreshing = false;
    }
  },
);

// ─── Error parser ──────────────────────────────────────────────────────────
export const parseErrors = (error) => {
  const data = error.response?.data;
  if (!data || typeof data !== 'object') {
    return { non_field_errors: 'Network error. Please try again.' };
  }
  const flat = {};
  Object.entries(data).forEach(([key, value]) => {
    flat[key] = Array.isArray(value) ? value[0] : String(value);
  });
  return flat;
};

// ═══════════════════════════════════════════════════════════════════════════
// AUTH  →  /api/auth/
// Used by AuthContext — must be exported before any other API group.
// ═══════════════════════════════════════════════════════════════════════════
export const authAPI = {
  /**
   * POST /auth/login/
   * Body: { email, password }
   * Returns: { access, refresh }
   */
  login: (credentials) =>
    api.post('/auth/login/', credentials),

  /**
   * POST /auth/register/
   * Body: { email, password, first_name, last_name, ... }
   */
  register: (data) =>
    api.post('/auth/register/', data),

  /**
   * POST /auth/logout/
   * Body: { refresh }  — blacklists the refresh token server-side
   */
  logout: (refresh) =>
    api.post('/auth/logout/', { refresh }),

  /**
   * POST /auth/token/refresh/
   * Body: { refresh }
   * Returns: { access, refresh? }
   */
  refreshToken: (refresh) =>
    api.post('/auth/token/refresh/', { refresh }),

  /**
   * GET /auth/user/
   * Returns the authenticated user's profile (email, type, is_verified …)
   * This is what AuthContext calls on mount and after login.
   */
  getUser: () =>
    api.get('/auth/user/'),

  /**
   * POST /auth/forgot-password/
   * Body: { email }
   */
  forgotPassword: (email) =>
    api.post('/auth/forgot-password/', { email }),

  /**
   * POST /auth/reset-password/
   * Body: { uid, token, new_password, confirm_password }
   */
  resetPassword: (data) =>
    api.post('/auth/reset-password/', data),

  /**
   * POST /auth/otp/request/
   * Body: { phone_number }
   */
  requestOtp: (phone_number) =>
    api.post('/auth/otp/request/', { phone_number }),

  /**
   * POST /auth/confirm-email/
   * Body: { token }
   */
  confirmEmail: (token) =>
    api.post('/auth/confirm-email/', { token }),
};

// ═══════════════════════════════════════════════════════════════════════════
// SHOP  →  /api/products/, /api/categories/, etc.
// ═══════════════════════════════════════════════════════════════════════════

export const getProducts = (params = {}) =>
  api.get('/products/', { params });

export const getProductDetails = (slug) =>
  api.get(`/products/${slug}/`);

export const getRelatedProducts = (slug) =>
  api.get(`/products/${slug}/related/`);

/**
 * POST /products/<slug>/reviews/
 * Requires authentication — reviews are tied to the logged-in user's
 * account. Body: { rating, headline?, comment } (no `name`: the display
 * name is derived server-side from the authenticated user's profile).
 * Returns the newly created review: { id, user_id, name, rating, headline, comment, is_verified_purchase, created_at }
 *
 * The backend also recalculates and persists product.rating / product.reviews_count
 * after every successful submission.
 */
export const createReview = (slug, data) =>
  api.post(`/products/${slug}/reviews/`, data);

export const getCategories = () =>
  api.get('/categories/');

export const getBrands = (search = '') =>
  api.get('/brands/', { params: search ? { search } : {} });

export const getColors = () =>
  api.get('/colors/');

// ═══════════════════════════════════════════════════════════════════════════
// CART
// ═══════════════════════════════════════════════════════════════════════════

export const getCart = () =>
  api.get('/cart/');

export const addToCart = (productId, quantity = 1) =>
  api.post('/cart/', { product_id: productId, quantity });

export const updateCartItem = (itemId, quantity) =>
  api.patch(`/cart/item/${itemId}/`, { quantity });

export const removeCartItem = (itemId) =>
  api.delete(`/cart/item/${itemId}/`);

export const clearCart = () =>
  api.delete('/cart/clear/');

export const cartAPI = {
  getCart,
  addToCart,
  updateCartItem,
  removeCartItem,
  clearCart,
};

// ═══════════════════════════════════════════════════════════════════════════
// ORDERS
// ═══════════════════════════════════════════════════════════════════════════

export const createOrder = (payload) =>
  api.post('/orders/', payload);

export const getOrders = () =>
  api.get('/orders/');

export const getOrderDetail = (orderId) =>
  api.get(`/orders/${orderId}/`);

export const cancelOrder = (orderId) =>
  api.patch(`/orders/${orderId}/`, { status: 'cancelled' });

// ═══════════════════════════════════════════════════════════════════════════
// USER DASHBOARD  →  /api/dashboard/
// ═══════════════════════════════════════════════════════════════════════════
export const dashboardAPI = {
  // Profile
  getProfile: () => api.get('/dashboard/profile/'),
  updateProfile: (data) => api.patch('/dashboard/profile/', data),
  uploadAvatar: (formData) => api.post('/dashboard/profile/upload-avatar/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  // Security
  changePassword: (data) => api.post('/dashboard/change-password/', data),

  // Notifications
  getNotifications: () => api.get('/dashboard/notifications/'),
  updateNotifications: (data) => api.patch('/dashboard/notifications/', data),

  // Summary
  getSummary: () => api.get('/dashboard/summary/'),

  // Orders
  getOrders: (params = {}) => api.get('/dashboard/orders/', { params }),
  getOrder: (id) => api.get(`/dashboard/orders/${id}/`),

  // Wishlist
  getWishlist: () => api.get('/dashboard/wishlist/'),
  addToWishlist: (productId) => api.post('/dashboard/wishlist/', { product_id: productId }),
  removeFromWishlist: (id) => api.delete(`/dashboard/wishlist/${id}/`),

  // Addresses
  getAddresses: () => api.get('/dashboard/addresses/'),
  createAddress: (data) => api.post('/dashboard/addresses/', data),
  updateAddress: (id, data) => api.patch(`/dashboard/addresses/${id}/`, data),
  deleteAddress: (id) => api.delete(`/dashboard/addresses/${id}/`),

  // Reviews
  getReviews: (params = {}) => api.get('/dashboard/reviews/', { params }),
  updateReview: (id, data) => api.patch(`/dashboard/reviews/${id}/`, data),
  deleteReview: (id) => api.delete(`/dashboard/reviews/${id}/`),
};

// ═══════════════════════════════════════════════════════════════════════════
// CHAT  →  /api/chat/
// ═══════════════════════════════════════════════════════════════════════════
export const chatAPI = {
  /**
   * GET /api/chat/room/
   * Returns the customer's current active room, or 404.
   */
  getMyRoom: () => api.get('/chat/room/'),

  /**
   * POST /api/chat/room/
   * Body: { subject?: string }
   * Creates a new support room for the current customer.
   */
  createRoom: (subject = '') =>
    api.post('/chat/room/', { subject }),

  /**
   * GET /api/chat/room/<roomId>/messages/
   * Fetches message history and marks messages as read.
   */
  getRoomMessages: (roomId) =>
    api.get(`/chat/room/${roomId}/messages/`),
};

// ═══════════════════════════════════════════════════════════════════════════
// ADMIN DASHBOARD  →  /api/dashboard/admin/
// ═══════════════════════════════════════════════════════════════════════════
export const adminAPI = {
  // Analytics
  getOverview: (period = '30d') => api.get('/dashboard/admin/overview/', { params: { period } }),
  getRevenueStats: (months = 12) => api.get('/dashboard/admin/revenue-stats/', { params: { months } }),
  getUserStats: () => api.get('/dashboard/admin/user-stats/'),
  getProductStats: () => api.get('/dashboard/admin/product-stats/'),

  // Users
  getUsers: (params = {}) => api.get('/dashboard/admin/users/', { params }),
  getUser: (id) => api.get(`/dashboard/admin/users/${id}/`),
  updateUser: (id, data) => api.patch(`/dashboard/admin/users/${id}/`, data),

  // Products
  getProducts: (params = {}) => api.get('/dashboard/admin/products/', { params }),
  getProduct: (id) => api.get(`/dashboard/admin/products/${id}/`),
  createProduct: (formData) => api.post('/dashboard/admin/products/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  updateProduct: (id, formData) => api.patch(`/dashboard/admin/products/${id}/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  deleteProduct: (id) => api.delete(`/dashboard/admin/products/${id}/`),

  // Categories (shop)
  getCategories: (params = {}) => api.get('/dashboard/admin/categories/', { params }),
  createCategory: (formData) => api.post('/dashboard/admin/categories/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  updateCategory: (id, formData) => api.patch(`/dashboard/admin/categories/${id}/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  deleteCategory: (id) => api.delete(`/dashboard/admin/categories/${id}/`),

  // Brands
  getBrands: (params = {}) => api.get('/dashboard/admin/brands/', { params }),
  createBrand: (formData) => api.post('/dashboard/admin/brands/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  updateBrand: (id, formData) => api.patch(`/dashboard/admin/brands/${id}/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  deleteBrand: (id) => api.delete(`/dashboard/admin/brands/${id}/`),

  // Orders
  getOrders: (params = {}) => api.get('/dashboard/admin/orders/', { params }),
  getOrder: (id) => api.get(`/dashboard/admin/orders/${id}/`),
  updateOrderStatus: (id, status) => api.patch(`/dashboard/admin/orders/${id}/`, { status }),

  // Reviews
  getReviews: (params = {}) => api.get('/dashboard/admin/reviews/', { params }),
  deleteReview: (id) => api.delete(`/dashboard/admin/reviews/${id}/`),

  // Contact messages
  getMessages: (params = {}) => api.get('/dashboard/admin/messages/', { params }),
  deleteMessage: (id) => api.delete(`/dashboard/admin/messages/${id}/`),

  // ─── Chat (admin) ────────────────────────────────────────────────────────
  getChatRooms: (params = {}) => api.get('/chat/admin/rooms/', { params }),
  getChatRoomMessages: (roomId) => api.get(`/chat/room/${roomId}/messages/`),
  updateChatRoom: (roomId, data) => api.patch(`/chat/admin/rooms/${roomId}/`, data),

  // ────────────────────────────────────────────────────────────────────────
  // BLOG ADMIN (new)
  // ────────────────────────────────────────────────────────────────────────
  // Blog Categories
  getBlogCategories: (params = {}) =>
    api.get('/dashboard/admin/blog/categories/', { params }),
  createBlogCategory: (formData) =>
    api.post('/dashboard/admin/blog/categories/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  updateBlogCategory: (id, formData) =>
    api.patch(`/dashboard/admin/blog/categories/${id}/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  deleteBlogCategory: (id) =>
    api.delete(`/dashboard/admin/blog/categories/${id}/`),

  // Blog Posts
  getBlogPosts: (params = {}) =>
    api.get('/dashboard/admin/blog/posts/', { params }),
  getBlogPost: (id) => api.get(`/dashboard/admin/blog/posts/${id}/`),
  createBlogPost: (formData) =>
    api.post('/dashboard/admin/blog/posts/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  updateBlogPost: (id, formData) =>
    api.patch(`/dashboard/admin/blog/posts/${id}/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  deleteBlogPost: (id) =>
    api.delete(`/dashboard/admin/blog/posts/${id}/`),

  // Blog Comments
  getBlogComments: (params = {}) =>
    api.get('/dashboard/admin/blog/comments/', { params }),
  updateBlogComment: (id, data) =>
    api.patch(`/dashboard/admin/blog/comments/${id}/`, data), // usually { is_approved: true/false }
  deleteBlogComment: (id) =>
    api.delete(`/dashboard/admin/blog/comments/${id}/`),
};

// ═══════════════════════════════════════════════════════════════════════════
// BLOG  →  /api/blog/ (public)
// ═══════════════════════════════════════════════════════════════════════════
export const blogAPI = {
  /**
   * GET /blog/posts/
   * Supported params:
   *   page, page_size, category (slug), is_featured, search, ordering
   *   ordering values: created_at | -created_at | views_count | -views_count
   */
  getPosts: (params = {}) =>
    api.get('/blog/posts/', { params }),

  /**
   * GET /blog/posts/<slug>/
   * Returns full post data with content and approved comments.
   * Also atomically increments the post's view counter server-side.
   */
  getPost: (slug) =>
    api.get(`/blog/posts/${slug}/`),

  /**
   * GET /blog/posts/<slug>/related/
   * Returns up to 3 published posts in the same category.
   */
  getRelatedPosts: (slug) =>
    api.get(`/blog/posts/${slug}/related/`),

  /**
   * GET /blog/categories/
   * Returns all categories that have at least one published post,
   * annotated with post_count.
   */
  getCategories: () =>
    api.get('/blog/categories/'),

  /**
   * POST /blog/posts/<slug>/comments/
   * Body: { name, email, website?, body, parent? }
   * No authentication required.
   */
  createComment: (slug, data) =>
    api.post(`/blog/posts/${slug}/comments/`, data),
};

export default api;
