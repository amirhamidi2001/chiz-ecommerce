/**
 * Flash-sale display on the product cards rendered by Cards (home mini
 * lists), BestSellers (home grid) and SearchResults. Category's grid/list
 * cards are covered in Category.test.jsx.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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

import { getProducts, getCategories, getBrands } from '../services/api';
import Cards from '../components/Cards';
import BestSellers from '../components/BestSellers';
import SearchResults from '../pages/SearchResults';

const product = (overrides = {}) => ({
  id: 1,
  slug: 'plain-product',
  name: 'Plain Product',
  price: '49.99',
  original_price: null,
  rating: '4.0',
  reviews_count: 3,
  stock: 5,
  is_new: false,
  is_sale: false,
  discount_percent: 0,
  thumbnail_url: '/img/x.webp',
  category: { name: 'Skincare' },
  is_on_flash_sale: false,
  flash_sale_price: null,
  ...overrides,
});

const saleProduct = (overrides = {}) =>
  product({
    id: 2,
    slug: 'vitamin-c-serum',
    name: 'Vitamin C Serum',
    price: '80.00',
    is_on_flash_sale: true,
    flash_sale_price: '60.00',
    flash_sale_original_price: '80.00',
    flash_sale_price_varies: false,
    flash_sale_discount_percent: '25.00',
    ...overrides,
  });

const page = (results) => ({
  data: { results, count: results.length, total_pages: 1, next: null, previous: null },
});

const inRouter = (ui, path = '/') =>
  render(<MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  getCategories.mockResolvedValue({ data: [] });
  getBrands.mockResolvedValue({ data: [] });
});

describe('Cards (home mini lists)', () => {
  it('shows the sale price, struck original and badge for a product on sale', async () => {
    getProducts.mockResolvedValue(page([saleProduct()]));
    inRouter(<Cards />);

    expect((await screen.findAllByText('Vitamin C Serum')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('$60.00').length).toBeGreaterThan(0);
    expect(screen.getAllByText('$80.00')[0].tagName).toBe('DEL');
    expect(screen.getAllByText('Flash Sale').length).toBeGreaterThan(0);
  });

  it('leaves a regular product’s price alone', async () => {
    getProducts.mockResolvedValue(page([product()]));
    inRouter(<Cards />);

    expect((await screen.findAllByText('Plain Product')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('$49.99').length).toBeGreaterThan(0);
    expect(screen.queryByText('Flash Sale')).not.toBeInTheDocument();
  });
});

describe('BestSellers', () => {
  it('badges and prices a product on flash sale', async () => {
    getProducts.mockResolvedValue(page([saleProduct()]));
    inRouter(<BestSellers />);

    expect(await screen.findByText('Vitamin C Serum')).toBeInTheDocument();
    expect(screen.getByText('Flash Sale')).toBeInTheDocument();
    expect(screen.getByText('$60.00')).toBeInTheDocument();
    expect(screen.getByText('$80.00').tagName).toBe('DEL');
  });

  it('flash sale takes precedence over the "New" badge', async () => {
    getProducts.mockResolvedValue(page([saleProduct({ is_new: true })]));
    inRouter(<BestSellers />);

    await screen.findByText('Vitamin C Serum');
    expect(screen.getByText('Flash Sale')).toBeInTheDocument();
    expect(screen.queryByText('New')).not.toBeInTheDocument();
  });

  it('is unchanged for a regular product', async () => {
    getProducts.mockResolvedValue(page([product({ is_new: true })]));
    inRouter(<BestSellers />);

    await screen.findByText('Plain Product');
    expect(screen.getByText('New')).toBeInTheDocument();
    expect(screen.getByText('$49.99')).toBeInTheDocument();
    expect(screen.queryByText('Flash Sale')).not.toBeInTheDocument();
  });
});

describe('SearchResults', () => {
  it('shows the flash price, struck original and badge on a result card', async () => {
    getProducts.mockResolvedValue(page([saleProduct()]));
    inRouter(<SearchResults />, '/search?q=serum');

    await waitFor(() => expect(screen.getByText('Vitamin C Serum')).toBeInTheDocument());
    expect(screen.getByText('$60.00')).toBeInTheDocument();
    expect(screen.getByText('$80.00').tagName).toBe('DEL');
    expect(screen.getByText('Flash Sale')).toBeInTheDocument();
  });

  it('is unchanged for a regular result', async () => {
    getProducts.mockResolvedValue(page([product()]));
    inRouter(<SearchResults />, '/search?q=plain');

    await waitFor(() => expect(screen.getByText('Plain Product')).toBeInTheDocument());
    expect(screen.getByText('$49.99')).toBeInTheDocument();
    expect(screen.queryByText('Flash Sale')).not.toBeInTheDocument();
  });
});
