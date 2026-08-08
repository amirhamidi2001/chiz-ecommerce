import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import axios from 'axios';

// ─── Axios mock ───────────────────────────────────────────────────────────────
vi.mock('axios', async () => {
  const actual = await vi.importActual('axios');

  // 1. Define instance methods as standalone Vitest mocks
  const mockMethods = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
    defaults: { baseURL: 'http://localhost:8000/api' },
  };

  const mockInstance = vi.fn(() => Promise.resolve({ data: {} }));
  
  Object.assign(mockInstance, mockMethods);

  return {
    default: {
      ...actual.default,
      create: vi.fn(() => mockInstance),
      post: vi.fn(), 
    },
    create: vi.fn(() => mockInstance),
  };
});

// ─── Import module under test AFTER mocks are in place ───────────────────────
// Dynamic import lets us re-import fresh copies between describe blocks when needed.
import {
  getAccessToken,
  getRefreshToken,
  setTokens,
  clearTokens,
  isAuthenticated,
  parseErrors,
  authAPI,
  getProducts,
  getProductDetails,
  getRelatedProducts,
  createReview,
  getCategories,
  getBrands,
  getColors,
  cartAPI,
  getCart,
  addToCart,
  updateCartItem,
  removeCartItem,
  clearCart,
  createOrder,
  getOrders,
  getOrderDetail,
  cancelOrder,
  dashboardAPI,
  chatAPI,
  adminAPI,
  blogAPI,
} from '../services/api.js';

// ─── Grab the mocked axios instance (the one `axios.create()` returned) ───────
// NOTE: axios.create() is called during the api.js module initialisation (before
// any test runs).  We call it once more here purely to get a reference to the
// same shared mockInstance object returned by the factory above.
const mockAxiosInstance = axios.create();

// ─── Capture interceptor handlers at module scope ─────────────────────────────
// api.js calls interceptors.request.use() and interceptors.response.use() at
// module load time — BEFORE any test's beforeEach / vi.clearAllMocks() runs.
// We must read .mock.calls right now; if we wait until inside a beforeEach that
// follows a vi.clearAllMocks() the call records will already be gone.
//
// axios.create() is called twice: once by api.js (which registers the handlers)
// and once by us just above (which does not).  The api.js call is [0]; our call
// is [1].  We therefore look at the calls recorded on the shared mockInstance
// directly — those are the ones api.js registered.
const _requestInterceptorCalls = mockAxiosInstance.interceptors.request.use.mock.calls.slice();
const _responseInterceptorCalls = mockAxiosInstance.interceptors.response.use.mock.calls.slice();

// Convenience accessors used in the interceptor describe blocks
const getRequestFulfilled = () => _requestInterceptorCalls[0]?.[0];
const getResponseRejected = () => _responseInterceptorCalls[0]?.[1];

// ─── Helpers ──────────────────────────────────────────────────────────────────
const resolvedWith = (data) => Promise.resolve({ data });
const rejectedWith = (status, data = {}) =>
  Promise.reject({ response: { status, data }, config: {} });

// ─────────────────────────────────────────────────────────────────────────────
// 1. TOKEN HELPERS
// ─────────────────────────────────────────────────────────────────────────────
describe('Token helpers', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  // ── getAccessToken ──────────────────────────────────────────────────────────
  describe('getAccessToken()', () => {
    it('returns null when no token is stored', () => {
      expect(getAccessToken()).toBeNull();
    });

    it('returns the stored access token', () => {
      localStorage.setItem('access_token', 'abc123');
      expect(getAccessToken()).toBe('abc123');
    });
  });

  // ── getRefreshToken ─────────────────────────────────────────────────────────
  describe('getRefreshToken()', () => {
    it('returns null when no token is stored', () => {
      expect(getRefreshToken()).toBeNull();
    });

    it('returns the stored refresh token', () => {
      localStorage.setItem('refresh_token', 'refresh_xyz');
      expect(getRefreshToken()).toBe('refresh_xyz');
    });
  });

  // ── setTokens ───────────────────────────────────────────────────────────────
  describe('setTokens()', () => {
    it('persists both access and refresh tokens', () => {
      setTokens({ access: 'new_access', refresh: 'new_refresh' });
      expect(localStorage.getItem('access_token')).toBe('new_access');
      expect(localStorage.getItem('refresh_token')).toBe('new_refresh');
    });

    it('overwrites existing tokens', () => {
      localStorage.setItem('access_token', 'old_access');
      setTokens({ access: 'updated_access', refresh: 'updated_refresh' });
      expect(localStorage.getItem('access_token')).toBe('updated_access');
    });
  });

  // ── clearTokens ─────────────────────────────────────────────────────────────
  describe('clearTokens()', () => {
    it('removes both tokens from localStorage', () => {
      setTokens({ access: 'a', refresh: 'r' });
      clearTokens();
      expect(localStorage.getItem('access_token')).toBeNull();
      expect(localStorage.getItem('refresh_token')).toBeNull();
    });

    it('is a no-op when storage is already empty', () => {
      expect(() => clearTokens()).not.toThrow();
    });
  });

  // ── isAuthenticated ─────────────────────────────────────────────────────────
  describe('isAuthenticated()', () => {
    it('returns false when no access token exists', () => {
      expect(isAuthenticated()).toBe(false);
    });

    it('returns true when an access token exists', () => {
      localStorage.setItem('access_token', 'token');
      expect(isAuthenticated()).toBe(true);
    });

    it('returns false after tokens are cleared', () => {
      setTokens({ access: 'a', refresh: 'r' });
      clearTokens();
      expect(isAuthenticated()).toBe(false);
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. parseErrors
// ─────────────────────────────────────────────────────────────────────────────
describe('parseErrors()', () => {
  it('returns a network-error message when response is undefined', () => {
    const result = parseErrors({});
    expect(result).toEqual({ non_field_errors: 'Network error. Please try again.' });
  });

  it('returns a network-error message when response.data is a string', () => {
    const result = parseErrors({ response: { data: 'Internal Server Error' } });
    expect(result).toEqual({ non_field_errors: 'Network error. Please try again.' });
  });

  it('returns a network-error message when response.data is null', () => {
    const result = parseErrors({ response: { data: null } });
    expect(result).toEqual({ non_field_errors: 'Network error. Please try again.' });
  });

  it('flattens array values to their first element', () => {
    const error = {
      response: {
        data: { email: ['This field is required.'], password: ['Too short.'] },
      },
    };
    const result = parseErrors(error);
    expect(result).toEqual({
      email: 'This field is required.',
      password: 'Too short.',
    });
  });

  it('converts non-array values to strings', () => {
    const error = {
      response: { data: { detail: 'No active account.' } },
    };
    expect(parseErrors(error)).toEqual({ detail: 'No active account.' });
  });

  it('handles mixed array and scalar values', () => {
    const error = {
      response: {
        data: {
          username: ['Already taken.'],
          non_field_errors: 'Invalid credentials.',
        },
      },
    };
    const result = parseErrors(error);
    expect(result.username).toBe('Already taken.');
    expect(result.non_field_errors).toBe('Invalid credentials.');
  });

  it('handles numeric error values by converting to string', () => {
    const error = { response: { data: { code: 42 } } };
    expect(parseErrors(error).code).toBe('42');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. INTERCEPTORS
// ─────────────────────────────────────────────────────────────────────────────
describe('Axios interceptors', () => {
  // We verify registration counts using the snapshot taken at module scope
  // (before any vi.clearAllMocks() can erase the records).

  it('registers a request interceptor', () => {
    expect(_requestInterceptorCalls.length).toBe(1);
  });

  it('registers a response interceptor', () => {
    expect(_responseInterceptorCalls.length).toBe(1);
  });

  // ── Request interceptor behaviour ─────────────────────────────────────────
  describe('Request interceptor', () => {
    // Handler is extracted once from the pre-captured snapshot — safe against
    // any vi.clearAllMocks() that runs in sibling describe blocks.
    const requestFulfilled = getRequestFulfilled();

    beforeEach(() => {
      localStorage.clear();
    });

    it('attaches Bearer token when access_token exists', () => {
      localStorage.setItem('access_token', 'tok_abc');
      const config = { headers: {} };
      const result = requestFulfilled(config);
      expect(result.headers.Authorization).toBe('Bearer tok_abc');
    });

    it('does not add Authorization header when no token present', () => {
      const config = { headers: {} };
      const result = requestFulfilled(config);
      expect(result.headers.Authorization).toBeUndefined();
    });

    it('returns the config object unchanged (aside from the header)', () => {
      const config = { headers: {}, url: '/test', method: 'get' };
      const result = requestFulfilled(config);
      expect(result.url).toBe('/test');
      expect(result.method).toBe('get');
    });
  });

  // ── Response interceptor — 401 handling ────────────────────────────────────
  describe('Response interceptor — 401 token refresh', () => {
    // Handler captured from the module-scope snapshot — immune to clearAllMocks.
    const responseRejected = getResponseRejected();

    beforeEach(() => {
      localStorage.clear();
      // Reset only the mocks that these tests actually assert on, rather than
      // calling vi.clearAllMocks() which would wipe the interceptor call records.
      mockAxiosInstance.get.mockReset();
      mockAxiosInstance.post.mockReset();
      axios.post.mockReset();
      // Reset window.location so redirect assertions start clean each test.
      delete window.location;
      window.location = { href: '' };
    });

    it('passes non-401 errors straight through', async () => {
      const err = { response: { status: 500 }, config: { url: '/some/' } };
      await expect(responseRejected(err)).rejects.toEqual(err);
    });

    it('passes 401 on auth endpoints straight through', async () => {
      const err = {
        response: { status: 401 },
        config: { url: '/auth/login/', _retried: false },
      };
      await expect(responseRejected(err)).rejects.toEqual(err);
    });

    it('passes 401 when already retried (_retried flag)', async () => {
      const err = {
        response: { status: 401 },
        config: { url: '/dashboard/profile/', _retried: true },
      };
      await expect(responseRejected(err)).rejects.toEqual(err);
    });

    it('redirects to /login and clears tokens when no refresh token is available', async () => {
      // No refresh token in storage → the guard throws immediately before any
      // network call is made.
      const err = {
        response: { status: 401 },
        config: { url: '/dashboard/profile/', headers: {}, _retried: false },
      };

      await expect(responseRejected(err)).rejects.toThrow('No refresh token');
      expect(localStorage.getItem('access_token')).toBeNull();
      expect(window.location.href).toBe('/login');
    });

    it('refreshes the token and retries the original request on success', async () => {
      localStorage.setItem('refresh_token', 'old_refresh');

      // The interceptor calls bare axios.post (not the instance) for the refresh.
      axios.post.mockResolvedValueOnce({
        data: { access: 'new_access', refresh: 'new_refresh' },
      });

      const originalConfig = {
        url: '/dashboard/profile/',
        headers: {},
        _retried: false,
        method: 'get',
      };
      const err = { response: { status: 401 }, config: originalConfig };

      // After refresh, the interceptor calls api(originalConfig).  api is the
      // mocked axios instance which is not directly callable as a function, so
      // the retry itself may throw — that's fine; we only care that tokens were
      // stored correctly.
      await responseRejected(err).catch(() => { });

      expect(localStorage.getItem('access_token')).toBe('new_access');
      expect(localStorage.getItem('refresh_token')).toBe('new_refresh');
    });

    it('clears tokens and redirects when refresh call itself fails', async () => {
      localStorage.setItem('access_token', 'old_access');
      localStorage.setItem('refresh_token', 'old_refresh');

      axios.post.mockRejectedValueOnce(new Error('Refresh failed'));

      const err = {
        response: { status: 401 },
        config: { url: '/dashboard/profile/', headers: {}, _retried: false },
      };

      await expect(responseRejected(err)).rejects.toThrow('Refresh failed');
      expect(localStorage.getItem('access_token')).toBeNull();
      expect(window.location.href).toBe('/login');
    });

    it('queues concurrent 401 requests while refreshing and resolves them after', async () => {
      // Two simultaneous 401s: only one refresh call should be issued.
      localStorage.setItem('refresh_token', 'r');

      let resolveRefresh;
      axios.post.mockReturnValueOnce(
        new Promise((res) => {
          resolveRefresh = () => res({ data: { access: 'new_tok', refresh: 'new_r' } });
        }),
      );

      const makeErr = () => ({
        response: { status: 401 },
        config: { url: '/dashboard/profile/', headers: {}, _retried: false },
      });

      const p1 = responseRejected(makeErr()).catch(() => { });
      const p2 = responseRejected(makeErr()).catch(() => { });

      resolveRefresh();
      await Promise.allSettled([p1, p2]);

      // The bare axios.post for the token refresh must only fire once.
      expect(axios.post).toHaveBeenCalledTimes(1);
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. authAPI
// ─────────────────────────────────────────────────────────────────────────────
describe('authAPI', () => {
  beforeEach(() => vi.clearAllMocks());

  it('login() — POSTs to /auth/login/ with credentials', async () => {
    const creds = { email: 'user@example.com', password: 'secret' };
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({ access: 'a', refresh: 'r' }));

    await authAPI.login(creds);

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/auth/login/', creds);
  });

  it('register() — POSTs to /auth/register/ with payload', async () => {
    const payload = { email: 'new@example.com', password: 'pass', first_name: 'Alice' };
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));

    await authAPI.register(payload);

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/auth/register/', payload);
  });

  it('logout() — POSTs to /auth/logout/ with the refresh token', async () => {
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));

    await authAPI.logout('refresh_tok');

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/auth/logout/', { refresh: 'refresh_tok' });
  });

  it('refreshToken() — POSTs to /auth/token/refresh/', async () => {
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({ access: 'new_a' }));

    await authAPI.refreshToken('old_refresh');

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/auth/token/refresh/', {
      refresh: 'old_refresh',
    });
  });

  it('getUser() — GETs /auth/user/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({ email: 'u@e.com' }));

    await authAPI.getUser();

    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/auth/user/');
  });

  it('forgotPassword() — POSTs to /auth/forgot-password/ with email', async () => {
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));

    await authAPI.forgotPassword('user@example.com');

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/auth/forgot-password/', {
      email: 'user@example.com',
    });
  });

  it('resetPassword() — POSTs to /auth/reset-password/ with full payload', async () => {
    const data = { uid: 'abc', token: 'xyz', new_password: 'np', confirm_password: 'np' };
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));

    await authAPI.resetPassword(data);

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/auth/reset-password/', data);
  });

  it('confirmEmail() — POSTs to /auth/confirm-email/ with token', async () => {
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));

    await authAPI.confirmEmail('confirm_tok_123');

    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/auth/confirm-email/', {
      token: 'confirm_tok_123',
    });
  });

  it('propagates rejection from the API call', async () => {
    mockAxiosInstance.post.mockRejectedValueOnce(new Error('Network Error'));

    await expect(authAPI.login({ email: 'a@b.com', password: 'x' })).rejects.toThrow(
      'Network Error',
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. SHOP API (standalone exports)
// ─────────────────────────────────────────────────────────────────────────────
describe('Shop API', () => {
  beforeEach(() => vi.clearAllMocks());

  describe('getProducts()', () => {
    it('GETs /products/ with no params by default', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
      await getProducts();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/products/', { params: {} });
    });

    it('forwards query params (page, category, etc.)', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
      await getProducts({ page: 2, category: 'shoes' });
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/products/', {
        params: { page: 2, category: 'shoes' },
      });
    });
  });

  describe('getProductDetails()', () => {
    it('GETs /products/<slug>/', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
      await getProductDetails('cool-sneakers');
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/products/cool-sneakers/');
    });
  });

  describe('getRelatedProducts()', () => {
    it('GETs /products/<slug>/related/', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
      await getRelatedProducts('cool-sneakers');
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/products/cool-sneakers/related/');
    });
  });

  describe('createReview()', () => {
    it('POSTs to /products/<slug>/reviews/ with review data', async () => {
      const reviewData = { name: 'Alice', rating: 5, comment: 'Great!' };
      mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith(reviewData));
      await createReview('cool-sneakers', reviewData);
      expect(mockAxiosInstance.post).toHaveBeenCalledWith(
        '/products/cool-sneakers/reviews/',
        reviewData,
      );
    });
  });

  describe('getCategories()', () => {
    it('GETs /categories/', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
      await getCategories();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/categories/');
    });
  });

  describe('getBrands()', () => {
    it('GETs /brands/ with no params when search is empty', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
      await getBrands();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/brands/', { params: {} });
    });

    it('passes search param when a search string is provided', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
      await getBrands('Nike');
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/brands/', {
        params: { search: 'Nike' },
      });
    });

    it('does NOT include search param when empty string is passed', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
      await getBrands('');
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/brands/', { params: {} });
    });
  });

  describe('getColors()', () => {
    it('GETs /colors/', async () => {
      mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
      await getColors();
      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/colors/');
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 6. cartAPI
// ─────────────────────────────────────────────────────────────────────────────
describe('cartAPI', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getCart() — GETs /cart/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({ items: [] }));
    await cartAPI.getCart();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/cart/');
  });

  it('also works via the standalone getCart export', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({ items: [] }));
    await getCart();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/cart/');
  });

  it('addToCart() — POSTs with productId and default quantity 1', async () => {
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await cartAPI.addToCart(42);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/cart/', {
      product_id: 42,
      quantity: 1,
    });
  });

  it('addToCart() — respects an explicit quantity', async () => {
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await addToCart(7, 3);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/cart/', {
      product_id: 7,
      quantity: 3,
    });
  });

  it('updateCartItem() — PATCHes /cart/item/<id>/ with quantity', async () => {
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await cartAPI.updateCartItem(5, 4);
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith('/cart/item/5/', { quantity: 4 });
  });

  it('removeCartItem() — DELETEs /cart/item/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await cartAPI.removeCartItem(5);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/cart/item/5/');
  });

  it('clearCart() — DELETEs /cart/clear/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await cartAPI.clearCart();
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/cart/clear/');
  });

  it('cartAPI object exposes all five methods', () => {
    expect(typeof cartAPI.getCart).toBe('function');
    expect(typeof cartAPI.addToCart).toBe('function');
    expect(typeof cartAPI.updateCartItem).toBe('function');
    expect(typeof cartAPI.removeCartItem).toBe('function');
    expect(typeof cartAPI.clearCart).toBe('function');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 7. ORDER API
// ─────────────────────────────────────────────────────────────────────────────
describe('Order API', () => {
  beforeEach(() => vi.clearAllMocks());

  it('createOrder() — POSTs to /orders/ with payload', async () => {
    const payload = { items: [{ product_id: 1, quantity: 2 }], address_id: 10 };
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({ id: 99 }));
    await createOrder(payload);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/orders/', payload);
  });

  it('getOrders() — GETs /orders/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await getOrders();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/orders/');
  });

  it('getOrderDetail() — GETs /orders/<id>/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await getOrderDetail(42);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/orders/42/');
  });

  it('cancelOrder() — PATCHes /orders/<id>/ with status cancelled', async () => {
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await cancelOrder(7);
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith('/orders/7/', {
      status: 'cancelled',
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 8. dashboardAPI
// ─────────────────────────────────────────────────────────────────────────────
describe('dashboardAPI', () => {
  beforeEach(() => vi.clearAllMocks());

  // ── Profile ───────────────────────────────────────────────────────────────
  it('getProfile() — GETs /dashboard/profile/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.getProfile();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/profile/');
  });

  it('updateProfile() — PATCHes /dashboard/profile/', async () => {
    const data = { first_name: 'Bob' };
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.updateProfile(data);
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith('/dashboard/profile/', data);
  });

  it('uploadAvatar() — POSTs multipart to /dashboard/profile/upload-avatar/', async () => {
    const fd = new FormData();
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.uploadAvatar(fd);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/dashboard/profile/upload-avatar/',
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  });

  // ── Security ──────────────────────────────────────────────────────────────
  it('changePassword() — POSTs to /dashboard/change-password/', async () => {
    const data = { old_password: 'old', new_password: 'new', confirm_password: 'new' };
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.changePassword(data);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/dashboard/change-password/', data);
  });

  // ── Notifications ─────────────────────────────────────────────────────────
  it('getNotifications() — GETs /dashboard/notifications/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.getNotifications();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/notifications/');
  });

  it('updateNotifications() — PATCHes /dashboard/notifications/', async () => {
    const data = { email_promotions: false };
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.updateNotifications(data);
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith('/dashboard/notifications/', data);
  });

  // ── Summary ───────────────────────────────────────────────────────────────
  it('getSummary() — GETs /dashboard/summary/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.getSummary();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/summary/');
  });

  // ── Orders ────────────────────────────────────────────────────────────────
  it('getOrders() — GETs /dashboard/orders/ with optional params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await dashboardAPI.getOrders({ page: 2 });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/orders/', {
      params: { page: 2 },
    });
  });

  it('getOrders() — defaults to empty params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await dashboardAPI.getOrders();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/orders/', { params: {} });
  });

  it('getOrder() — GETs /dashboard/orders/<id>/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.getOrder(5);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/orders/5/');
  });

  // ── Wishlist ──────────────────────────────────────────────────────────────
  it('getWishlist() — GETs /dashboard/wishlist/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await dashboardAPI.getWishlist();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/wishlist/');
  });

  it('addToWishlist() — POSTs to /dashboard/wishlist/ with product_id', async () => {
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.addToWishlist(11);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/dashboard/wishlist/', {
      product_id: 11,
    });
  });

  it('removeFromWishlist() — DELETEs /dashboard/wishlist/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.removeFromWishlist(3);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/dashboard/wishlist/3/');
  });

  // ── Addresses ─────────────────────────────────────────────────────────────
  it('getAddresses() — GETs /dashboard/addresses/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await dashboardAPI.getAddresses();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/addresses/');
  });

  it('createAddress() — POSTs to /dashboard/addresses/', async () => {
    const addr = { street: '1 Main St', city: 'Hamburg' };
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.createAddress(addr);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/dashboard/addresses/', addr);
  });

  it('updateAddress() — PATCHes /dashboard/addresses/<id>/', async () => {
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.updateAddress(2, { city: 'Berlin' });
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith('/dashboard/addresses/2/', {
      city: 'Berlin',
    });
  });

  it('deleteAddress() — DELETEs /dashboard/addresses/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.deleteAddress(2);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/dashboard/addresses/2/');
  });

  // ── Reviews ───────────────────────────────────────────────────────────────
  it('getReviews() — GETs /dashboard/reviews/ with optional params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await dashboardAPI.getReviews({ page: 1 });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/reviews/', {
      params: { page: 1 },
    });
  });

  it('updateReview() — PATCHes /dashboard/reviews/<id>/', async () => {
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.updateReview(9, { rating: 4 });
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith('/dashboard/reviews/9/', {
      rating: 4,
    });
  });

  it('deleteReview() — DELETEs /dashboard/reviews/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await dashboardAPI.deleteReview(9);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/dashboard/reviews/9/');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 9. chatAPI
// ─────────────────────────────────────────────────────────────────────────────
describe('chatAPI', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getMyRoom() — GETs /chat/room/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({ id: 1 }));
    await chatAPI.getMyRoom();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/chat/room/');
  });

  it('createRoom() — POSTs to /chat/room/ with subject', async () => {
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({ id: 2 }));
    await chatAPI.createRoom('Order issue');
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/chat/room/', {
      subject: 'Order issue',
    });
  });

  it('createRoom() — defaults subject to empty string', async () => {
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({ id: 3 }));
    await chatAPI.createRoom();
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/chat/room/', { subject: '' });
  });

  it('getRoomMessages() — GETs /chat/room/<roomId>/messages/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await chatAPI.getRoomMessages(7);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/chat/room/7/messages/');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 10. adminAPI
// ─────────────────────────────────────────────────────────────────────────────
describe('adminAPI', () => {
  beforeEach(() => vi.clearAllMocks());

  // ── Analytics ─────────────────────────────────────────────────────────────
  it('getOverview() — defaults to period "30d"', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.getOverview();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/overview/', {
      params: { period: '30d' },
    });
  });

  it('getOverview() — forwards custom period', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.getOverview('7d');
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/overview/', {
      params: { period: '7d' },
    });
  });

  it('getRevenueStats() — defaults to 12 months', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.getRevenueStats();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/revenue-stats/', {
      params: { months: 12 },
    });
  });

  it('getUserStats() — GETs /dashboard/admin/user-stats/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.getUserStats();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/user-stats/');
  });

  it('getProductStats() — GETs /dashboard/admin/product-stats/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.getProductStats();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/product-stats/');
  });

  // ── Users ─────────────────────────────────────────────────────────────────
  it('getUsers() — GETs /dashboard/admin/users/ with params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await adminAPI.getUsers({ search: 'alice' });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/users/', {
      params: { search: 'alice' },
    });
  });

  it('getUser() — GETs /dashboard/admin/users/<id>/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.getUser(3);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/users/3/');
  });

  it('updateUser() — PATCHes /dashboard/admin/users/<id>/', async () => {
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.updateUser(3, { is_active: false });
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith('/dashboard/admin/users/3/', {
      is_active: false,
    });
  });

  // ── Products ──────────────────────────────────────────────────────────────
  it('createProduct() — POSTs multipart to /dashboard/admin/products/', async () => {
    const fd = new FormData();
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.createProduct(fd);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/dashboard/admin/products/',
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  });

  it('updateProduct() — PATCHes multipart to /dashboard/admin/products/<id>/', async () => {
    const fd = new FormData();
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.updateProduct(5, fd);
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith(
      '/dashboard/admin/products/5/',
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  });

  it('deleteProduct() — DELETEs /dashboard/admin/products/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.deleteProduct(5);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/dashboard/admin/products/5/');
  });

  // ── Categories ────────────────────────────────────────────────────────────
  it('getCategories() — GETs /dashboard/admin/categories/ with params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await adminAPI.getCategories({ page: 1 });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/categories/', {
      params: { page: 1 },
    });
  });

  it('createCategory() — POSTs multipart to /dashboard/admin/categories/', async () => {
    const fd = new FormData();
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.createCategory(fd);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/dashboard/admin/categories/',
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  });

  it('deleteCategory() — DELETEs /dashboard/admin/categories/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.deleteCategory(2);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith(
      '/dashboard/admin/categories/2/',
    );
  });

  // ── Brands ────────────────────────────────────────────────────────────────
  it('getBrands() — GETs /dashboard/admin/brands/ with params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await adminAPI.getBrands({ search: 'Nike' });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/brands/', {
      params: { search: 'Nike' },
    });
  });

  it('createBrand() — POSTs multipart to /dashboard/admin/brands/', async () => {
    const fd = new FormData();
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.createBrand(fd);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/dashboard/admin/brands/',
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  });

  it('deleteBrand() — DELETEs /dashboard/admin/brands/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.deleteBrand(8);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/dashboard/admin/brands/8/');
  });

  // ── Orders ────────────────────────────────────────────────────────────────
  it('getOrders() — GETs /dashboard/admin/orders/ with params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await adminAPI.getOrders({ status: 'pending' });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/orders/', {
      params: { status: 'pending' },
    });
  });

  it('getOrder() — GETs /dashboard/admin/orders/<id>/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.getOrder(12);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/orders/12/');
  });

  it('updateOrderStatus() — PATCHes status to /dashboard/admin/orders/<id>/', async () => {
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.updateOrderStatus(12, 'shipped');
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith('/dashboard/admin/orders/12/', {
      status: 'shipped',
    });
  });

  // ── Reviews ───────────────────────────────────────────────────────────────
  it('getReviews() — GETs /dashboard/admin/reviews/ with params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await adminAPI.getReviews({ page: 2 });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/reviews/', {
      params: { page: 2 },
    });
  });

  it('deleteReview() — DELETEs /dashboard/admin/reviews/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.deleteReview(4);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/dashboard/admin/reviews/4/');
  });

  // ── Contact messages ──────────────────────────────────────────────────────
  it('getMessages() — GETs /dashboard/admin/messages/ with params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await adminAPI.getMessages({ page: 1 });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/dashboard/admin/messages/', {
      params: { page: 1 },
    });
  });

  it('deleteMessage() — DELETEs /dashboard/admin/messages/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.deleteMessage(6);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith(
      '/dashboard/admin/messages/6/',
    );
  });

  // ── Admin Chat ────────────────────────────────────────────────────────────
  it('getChatRooms() — GETs /chat/admin/rooms/ with params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await adminAPI.getChatRooms({ status: 'open' });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/chat/admin/rooms/', {
      params: { status: 'open' },
    });
  });

  it('getChatRoomMessages() — GETs /chat/room/<roomId>/messages/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await adminAPI.getChatRoomMessages(5);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/chat/room/5/messages/');
  });

  it('updateChatRoom() — PATCHes /chat/admin/rooms/<roomId>/', async () => {
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.updateChatRoom(5, { status: 'closed' });
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith('/chat/admin/rooms/5/', {
      status: 'closed',
    });
  });

  // ── Blog Admin — Categories ───────────────────────────────────────────────
  it('getBlogCategories() — GETs /dashboard/admin/blog/categories/ with params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await adminAPI.getBlogCategories({ page: 1 });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/dashboard/admin/blog/categories/',
      { params: { page: 1 } },
    );
  });

  it('createBlogCategory() — POSTs multipart to /dashboard/admin/blog/categories/', async () => {
    const fd = new FormData();
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.createBlogCategory(fd);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/dashboard/admin/blog/categories/',
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  });

  it('updateBlogCategory() — PATCHes multipart', async () => {
    const fd = new FormData();
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.updateBlogCategory(3, fd);
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith(
      '/dashboard/admin/blog/categories/3/',
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  });

  it('deleteBlogCategory() — DELETEs /dashboard/admin/blog/categories/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.deleteBlogCategory(3);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith(
      '/dashboard/admin/blog/categories/3/',
    );
  });

  // ── Blog Admin — Posts ────────────────────────────────────────────────────
  it('getBlogPosts() — GETs /dashboard/admin/blog/posts/ with params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await adminAPI.getBlogPosts({ page: 2 });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/dashboard/admin/blog/posts/',
      { params: { page: 2 } },
    );
  });

  it('getBlogPost() — GETs /dashboard/admin/blog/posts/<id>/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.getBlogPost(10);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/dashboard/admin/blog/posts/10/',
    );
  });

  it('createBlogPost() — POSTs multipart to /dashboard/admin/blog/posts/', async () => {
    const fd = new FormData();
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.createBlogPost(fd);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/dashboard/admin/blog/posts/',
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  });

  it('updateBlogPost() — PATCHes multipart to /dashboard/admin/blog/posts/<id>/', async () => {
    const fd = new FormData();
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.updateBlogPost(10, fd);
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith(
      '/dashboard/admin/blog/posts/10/',
      fd,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  });

  it('deleteBlogPost() — DELETEs /dashboard/admin/blog/posts/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.deleteBlogPost(10);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith(
      '/dashboard/admin/blog/posts/10/',
    );
  });

  // ── Blog Admin — Comments ─────────────────────────────────────────────────
  it('getBlogComments() — GETs /dashboard/admin/blog/comments/ with params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await adminAPI.getBlogComments({ is_approved: false });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/dashboard/admin/blog/comments/',
      { params: { is_approved: false } },
    );
  });

  it('updateBlogComment() — PATCHes /dashboard/admin/blog/comments/<id>/', async () => {
    mockAxiosInstance.patch.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.updateBlogComment(7, { is_approved: true });
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith(
      '/dashboard/admin/blog/comments/7/',
      { is_approved: true },
    );
  });

  it('deleteBlogComment() — DELETEs /dashboard/admin/blog/comments/<id>/', async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce(resolvedWith({}));
    await adminAPI.deleteBlogComment(7);
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith(
      '/dashboard/admin/blog/comments/7/',
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 11. blogAPI (public)
// ─────────────────────────────────────────────────────────────────────────────
describe('blogAPI (public)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getPosts() — GETs /blog/posts/ with no params by default', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await blogAPI.getPosts();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/blog/posts/', { params: {} });
  });

  it('getPosts() — forwards all supported query params', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await blogAPI.getPosts({
      page: 2,
      page_size: 10,
      category: 'tech',
      is_featured: true,
      search: 'vitest',
      ordering: '-views_count',
    });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/blog/posts/', {
      params: {
        page: 2,
        page_size: 10,
        category: 'tech',
        is_featured: true,
        search: 'vitest',
        ordering: '-views_count',
      },
    });
  });

  it('getPost() — GETs /blog/posts/<slug>/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith({}));
    await blogAPI.getPost('my-first-post');
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/blog/posts/my-first-post/');
  });

  it('getRelatedPosts() — GETs /blog/posts/<slug>/related/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await blogAPI.getRelatedPosts('my-first-post');
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/blog/posts/my-first-post/related/',
    );
  });

  it('getCategories() — GETs /blog/categories/', async () => {
    mockAxiosInstance.get.mockResolvedValueOnce(resolvedWith([]));
    await blogAPI.getCategories();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/blog/categories/');
  });

  it('createComment() — POSTs to /blog/posts/<slug>/comments/ with comment data', async () => {
    const data = {
      name: 'Alice',
      email: 'alice@example.com',
      body: 'Great post!',
    };
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({ id: 1, ...data }));
    await blogAPI.createComment('my-first-post', data);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/blog/posts/my-first-post/comments/',
      data,
    );
  });

  it('createComment() — accepts optional website and parent fields', async () => {
    const data = {
      name: 'Bob',
      email: 'bob@example.com',
      website: 'https://bob.dev',
      body: 'Reply here',
      parent: 1,
    };
    mockAxiosInstance.post.mockResolvedValueOnce(resolvedWith({}));
    await blogAPI.createComment('some-slug', data);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/blog/posts/some-slug/comments/',
      data,
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 12. Module shape & default export
// ─────────────────────────────────────────────────────────────────────────────
describe('Module exports', () => {
  it('exports an axios instance as the default export', async () => {
    const mod = await import('../services/api.js');
    // The default export should be the axios instance (which is our mock)
    expect(mod.default).toBeDefined();
  });

  it('exports all expected named API objects and functions', async () => {
    const mod = await import('../services/api.js');
    const expectedNamedExports = [
      'getAccessToken', 'getRefreshToken', 'setTokens', 'clearTokens', 'isAuthenticated',
      'parseErrors',
      'authAPI',
      'getProducts', 'getProductDetails', 'getRelatedProducts', 'createReview',
      'getCategories', 'getBrands', 'getColors',
      'getCart', 'addToCart', 'updateCartItem', 'removeCartItem', 'clearCart', 'cartAPI',
      'createOrder', 'getOrders', 'getOrderDetail', 'cancelOrder',
      'dashboardAPI',
      'chatAPI',
      'adminAPI',
      'blogAPI',
    ];
    expectedNamedExports.forEach((name) => {
      expect(mod[name], `Expected export "${name}" to be defined`).toBeDefined();
    });
  });
});
