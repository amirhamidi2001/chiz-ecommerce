/**
 * Task 14.1.2.4 — the Persian-digit toggle, verified IN THE DOM at the
 * storefront sites that were deliberately switched: product review counts.
 * (Ratings and the PDP are covered in ProductDetails.test.jsx / Category.test.jsx.)
 *
 * The per-context rule under test: review counts -> Persian digits ("۱۲۸"),
 * while the price shown right next to them stays Western ("125,000 تومان").
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../services/api', () => ({
  getProducts: vi.fn(),
  getCategories: vi.fn(),
  getBrands: vi.fn(),
}));
vi.mock('../context/CartContext', () => ({
  useCart: () => ({ addToCart: vi.fn().mockResolvedValue({ success: true }) }),
}));
vi.mock('../context/WishlistContext', () => ({
  useWishlist: () => ({
    addToWishlist: vi.fn(),
    removeFromWishlist: vi.fn(),
    isInWishlist: () => false,
  }),
}));

import { getProducts } from '../services/api';
import Cards from '../components/Cards';
import BestSellers from '../components/BestSellers';
import Countdown from '../components/Countdown';
import Hero from '../components/Hero';
import { formatToman } from '../utils/money';

const PRODUCT = {
  id: 1,
  slug: 'hydrating-serum',
  name: 'Hydrating Serum',
  price: 1_250_000,
  original_price: null,
  rating: '4.5',
  reviews_count: 128,
  stock: 5,
  is_new: false,
  is_sale: false,
  discount_percent: 0,
  thumbnail_url: '/img/x.webp',
  category: { name: 'Skincare' },
  is_on_flash_sale: false,
  flash_sale_price: null,
};
const page = (results) => ({ data: { results, count: results.length } });
const inRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  getProducts.mockResolvedValue(page([PRODUCT]));
});

describe.each([
  ['Cards (home mini lists)', Cards],
  ['BestSellers (home grid)', BestSellers],
  ['Countdown (sale cards)', Countdown],
])('%s', (_name, Subject) => {
  // (a PascalCase const so JSX usage is recognised by the project's lint rules)
  const Component = Subject;

  it('shows the review count in Persian digits and the price in Western digits', async () => {
    inRouter(<Component />);

    expect((await screen.findAllByText('Hydrating Serum')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('(۱۲۸)').length).toBeGreaterThan(0); // Persian
    expect(screen.queryByText('(128)')).not.toBeInTheDocument(); // not Western
    expect(screen.getAllByText(formatToman(1_250_000)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/[۰-۹]+\s*تومان/)).not.toBeInTheDocument(); // price never Persian
  });
});

describe('Hero', () => {
  it('shows the happy-customer count in Persian digits', async () => {
    inRouter(<Hero />);

    expect(await screen.findByText('۱۲۸+')).toBeInTheDocument();
    expect(screen.queryByText('128+')).not.toBeInTheDocument();
  });
});
