// src/App.jsx
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';

// ─── Context providers ────────────────────────────────────────────────────
import { AuthProvider } from './context/AuthContext';
import { CartProvider } from './context/CartContext';
import { WishlistProvider } from './context/WishlistContext';

// ─── Shared layout pieces ─────────────────────────────────────────────────
import Header from './components/Header';
import Footer from './components/Footer';
import ChatWidget from './components/ChatWidget';

// ─── Admin layout ─────────────────────────────────────────────────────────
import AdminLayout from './components/admin/AdminLayout';

// ─── Admin pages ──────────────────────────────────────────────────────────
import AdminDashboard from './pages/admin/AdminDashboard';
import AdminAnalytics from './pages/admin/AdminAnalytics';
import AdminOrders from './pages/admin/AdminOrders';
import AdminProducts from './pages/admin/AdminProducts';
import AdminCategories from './pages/admin/AdminCategories';
import AdminBrands from './pages/admin/AdminBrands';
import AdminUsers from './pages/admin/AdminUsers';
import AdminReviews from './pages/admin/AdminReviews';
import AdminMessages from './pages/admin/AdminMessages';
import AdminChat from './pages/admin/AdminChat';
import AdminBlog from './pages/admin/AdminBlog';

// ─── Storefront pages ─────────────────────────────────────────────────────
import Home from './pages/Home';
import About from './pages/About';
import Account from './pages/Account';
import Cart from './pages/Cart';
import Category from './pages/Category';
import ChangePassword from './pages/ChangePassword';
import Checkout from './pages/Checkout';
import ConfirmEmail from './pages/ConfirmEmail';
import Contact from './pages/Contact';
import Faq from './pages/Faq';
import ForgotPassword from './pages/ForgotPassword';
import Login from './pages/Login';
import NotFound from './pages/NotFound';
import OrderConfirmation from './pages/OrderConfirmation';
import PaymentMethods from './pages/PaymentMethods';
import Privacy from './pages/Privacy';
import ProductDetails from './pages/ProductDetails';
import ProductLists from './pages/ProductLists';
import ResetPassword from './pages/ResetPassword';
import ReturnPolicy from './pages/ReturnPolicy';
import SearchResults from './pages/SearchResults';
import ShippingInfo from './pages/ShippingInfo';
import Support from './pages/Support';
import Tos from './pages/Tos';
import Blog from './pages/Blog';
import BlogDetails from './pages/BlogDetails';

// ─── Auth hook ────────────────────────────────────────────────────────────
import { useAuth } from './context/AuthContext';

// ═════════════════════════════════════════════════════════════════════════
// Layout wrappers
// ═════════════════════════════════════════════════════════════════════════

/**
 * MainLayout — renders the shared Header + Footer around every non-admin page.
 * ChatWidget is mounted here, appearing on all storefront pages.
 * Admin pages use AdminLayout and must NOT render the storefront Header/Footer.
 */
const MainLayout = () => (
  <>
    <Header />
    <main className="min-h-screen">
      <Outlet />
    </main>
    <Footer />
    <ChatWidget />
  </>
);

// ═════════════════════════════════════════════════════════════════════════
// Route guards
// ═════════════════════════════════════════════════════════════════════════

/**
 * ProtectedRoute — authentication required.
 * Redirects unauthenticated users to /login.
 */
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-10 h-10 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return isAuthenticated ? children : <Navigate to="/login" replace />;
};

/**
 * AdminRoute — authentication + admin/superuser type required (type 2 or 3).
 * Regular customers are redirected to /account.
 */
const AdminRoute = ({ children }) => {
  const { isAuthenticated, isAdmin, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-10 h-10 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!isAdmin) return <Navigate to="/account" replace />;
  return children;
};

/**
 * GuestRoute — prevents already-authenticated users from seeing auth pages.
 * Redirects them to /account instead.
 */
const GuestRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return null;
  return isAuthenticated ? <Navigate to="/account" replace /> : children;
};

// ═════════════════════════════════════════════════════════════════════════
// App
// ═════════════════════════════════════════════════════════════════════════
function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        {/*
          WishlistProvider is nested inside AuthProvider so it can react to
          auth-change events dispatched by AuthContext on login/logout.
          CartProvider follows the same pattern.
        */}
        <CartProvider>
          <WishlistProvider>
            <Routes>

              {/* ── Storefront routes (Header + Footer via MainLayout) ──────── */}
              <Route element={<MainLayout />}>

                {/* Public */}
                <Route path="/" element={<Home />} />
                <Route path="/about" element={<About />} />
                <Route path="/cart" element={<Cart />} />
                <Route path="/category" element={<Category />} />
                <Route path="/contact" element={<Contact />} />
                <Route path="/faq" element={<Faq />} />
                <Route path="/payment-methods" element={<PaymentMethods />} />
                <Route path="/privacy" element={<Privacy />} />
                <Route path="/product-details" element={<ProductDetails />} />
                <Route path="/product/:slug" element={<ProductDetails />} />
                <Route path="/product-lists" element={<ProductLists />} />
                <Route path="/return-policy" element={<ReturnPolicy />} />
                <Route path="/search" element={<SearchResults />} />
                <Route path="/shipping-info" element={<ShippingInfo />} />
                <Route path="/support" element={<Support />} />
                <Route path="/tos" element={<Tos />} />
                <Route path="/blog" element={<Blog />} />
                <Route path="/blog/:slug" element={<BlogDetails />} />

                {/* Guest-only (redirect to /account when logged in) */}
                <Route path="/login" element={<GuestRoute><Login /></GuestRoute>} />
                <Route path="/forgot-password" element={<GuestRoute><ForgotPassword /></GuestRoute>} />
                <Route path="/reset-password/:uid/:token" element={<GuestRoute><ResetPassword /></GuestRoute>} />
                <Route path="/confirm-email" element={<GuestRoute><ConfirmEmail /></GuestRoute>} />

                {/* Auth-required */}
                <Route path="/account" element={<ProtectedRoute><Account /></ProtectedRoute>} />
                <Route path="/change-password" element={<ProtectedRoute><ChangePassword /></ProtectedRoute>} />
                <Route path="/checkout" element={<ProtectedRoute><Checkout /></ProtectedRoute>} />
                <Route path="/order-confirmation/:id" element={<ProtectedRoute><OrderConfirmation /></ProtectedRoute>} />

                {/* 404 */}
                <Route path="*" element={<NotFound />} />
              </Route>

              {/* ── Admin routes (AdminLayout — no storefront Header/Footer) ─ */}
              <Route
                path="/admin"
                element={<AdminRoute><AdminLayout /></AdminRoute>}
              >
                <Route index element={<AdminDashboard />} />
                <Route path="analytics" element={<AdminAnalytics />} />
                <Route path="orders" element={<AdminOrders />} />
                <Route path="products" element={<AdminProducts />} />
                <Route path="categories" element={<AdminCategories />} />
                <Route path="brands" element={<AdminBrands />} />
                <Route path="users" element={<AdminUsers />} />
                <Route path="reviews" element={<AdminReviews />} />
                <Route path="messages" element={<AdminMessages />} />
                <Route path="chat" element={<AdminChat />} />
                <Route path="blog" element={<AdminBlog />} />
                {/* Unknown /admin/* → back to overview */}
                <Route path="*" element={<Navigate to="/admin" replace />} />
              </Route>

            </Routes>
          </WishlistProvider>
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
