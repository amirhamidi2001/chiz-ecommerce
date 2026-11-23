import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Header from '../components/Header';

// The bell has its own suite (NotificationBell.test.jsx); here we only check
// that Header places it for signed-in users and not for visitors.
vi.mock('../components/NotificationBell', () => ({
  default: () => <div data-testid="notification-bell" />,
}));
vi.mock('../components/SearchBox', () => ({ default: () => <div /> }));

const mockAuth = { user: null, isAuthenticated: false, logout: vi.fn(), loading: false };
vi.mock('../context/AuthContext', () => ({ useAuth: () => mockAuth }));
vi.mock('../context/CartContext', () => ({ useCart: () => ({ cartCount: 0 }) }));
vi.mock('../context/WishlistContext', () => ({
  useWishlist: () => ({ wishlistCount: 0 }),
}));

const renderHeader = () =>
  render(
    <MemoryRouter>
      <Header />
    </MemoryRouter>,
  );

describe('Header notification bell', () => {
  beforeEach(() => {
    mockAuth.user = null;
    mockAuth.isAuthenticated = false;
  });

  it('is not rendered for signed-out visitors (an inbox needs an account)', () => {
    renderHeader();
    expect(screen.queryByTestId('notification-bell')).not.toBeInTheDocument();
  });

  it('is rendered for signed-in users, alongside the wishlist and cart icons', () => {
    mockAuth.user = { id: 1, email: 'a@b.com' };
    mockAuth.isAuthenticated = true;
    renderHeader();

    const bell = screen.getByTestId('notification-bell');
    const wishlist = screen.getByLabelText('Wishlist');
    expect(bell).toBeInTheDocument();
    // Bell sits before the wishlist icon in the icon row.
    expect(
      bell.compareDocumentPosition(wishlist) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(screen.getByLabelText('Cart')).toBeInTheDocument();
  });
});
