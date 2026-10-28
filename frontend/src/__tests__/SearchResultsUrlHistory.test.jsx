import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import SearchResults from '../pages/SearchResults';

vi.mock('../services/api', () => ({
  getProducts: vi.fn(),
  getCategories: vi.fn(),
  getBrands: vi.fn(),
  getProductFacetCounts: vi.fn(),
}));
vi.mock('../context/CartContext', () => ({ useCart: () => ({ addToCart: vi.fn() }) }));
vi.mock('../context/WishlistContext', () => ({
  useWishlist: () => ({
    addToWishlist: vi.fn(),
    removeFromWishlist: vi.fn(),
    isInWishlist: () => false,
  }),
}));

import { getProducts, getCategories, getBrands, getProductFacetCounts } from '../services/api';

window.scrollTo = vi.fn();

// ─── Harness ──────────────────────────────────────────────────────────────────
const ITEM = {
  id: 1, name: 'Test Product', slug: 'test-product', price: 299_900, sale_price: null,
  rating: 4.2, reviews_count: 17, thumbnail: '/img/p.webp', in_stock: true, is_new: false,
  category: { name: 'Skincare' }, brand: { name: 'Acme' },
};

const NavProbe = () => {
  const { pathname, search } = useLocation();
  const navigate = useNavigate();
  return (
    <div>
      <div data-testid="loc">{pathname + search}</div>
      <button onClick={() => navigate(-1)}>history-back</button>
      <button onClick={() => navigate(1)}>history-forward</button>
      <button onClick={() => navigate('/search?q=lipstick&skin_type=dry&min_price=200000')}>external-nav</button>
    </div>
  );
};

const renderSearch = (entries = ['/search?q=serum'], index = entries.length - 1) => {
  const user = userEvent.setup();
  const utils = render(
    <MemoryRouter initialEntries={entries} initialIndex={index}>
      <NavProbe />
      <Routes>
        <Route path="/search" element={<SearchResults />} />
        <Route path="/" element={<div>Home page</div>} />
      </Routes>
    </MemoryRouter>,
  );
  return { user, ...utils };
};

const locText = () => screen.getByTestId('loc').textContent;
const path = () => locText().split('?')[0];
const url = () => new URLSearchParams(locText().split('?')[1] || '');
const lastParams = () => getProducts.mock.calls.at(-1)[0];
const settle = async () => { await screen.findByText('Test Product'); };
// (the SPF inputs are placeholdered plain "Min"; the price field says "Min (Toman)")
const priceMin = () => screen.getByPlaceholderText('Min (Toman)');
const row = (name) => screen.getByRole('button', { name });
const back = (user) => user.click(screen.getByRole('button', { name: 'history-back' }));
const forward = (user) => user.click(screen.getByRole('button', { name: 'history-forward' }));
const removeChip = (user, label) =>
  user.click(screen.getByRole('button', { name: `Remove ${label} filter` }));
const hasChip = (label) => !!screen.queryByRole('button', { name: `Remove ${label} filter` });

beforeEach(() => {
  vi.clearAllMocks();
  getCategories.mockResolvedValue({ data: [] });
  getBrands.mockResolvedValue({ data: [] });
  getProductFacetCounts.mockResolvedValue({ data: null });
  getProducts.mockImplementation(() =>
    Promise.resolve({ data: { results: [ITEM], count: 40 } }), // 40 results -> 4 pages of 12
  );
});

// ═════════════════════════════════════════════════════════════════════════════
describe('SearchResults history — filter changes replace, pages and searches push', () => {
  it('filter changes REPLACE the entry — several ticks, one Back', async () => {
    const { user } = renderSearch(['/', '/search?q=serum']);
    await settle();

    await user.click(row('Oily'));
    await user.click(row('Dry'));
    await user.click(row('Vegan'));
    await user.click(row('Female'));
    await user.click(row('Curly'));
    await waitFor(() => expect(url().get('hair_type')).toBe('curly'));
    expect(url().get('skin_type')).toBe('oily,dry');

    await back(user);

    expect(path()).toBe('/');
    expect(screen.getByText('Home page')).toBeInTheDocument();
  });

  it('sort changes, chip removal and "Clear all" replace too', async () => {
    const { user } = renderSearch(['/', '/search?q=serum']);
    await settle();

    await user.selectOptions(screen.getByLabelText('Sort:'), 'price');
    await user.click(row('Oily'));
    await user.click(row('Vegan'));
    await waitFor(() => expect(url().get('is_vegan')).toBe('true'));
    await removeChip(user, 'Certification: Vegan');
    await user.click(screen.getByRole('button', { name: /clear all \(/i }));
    await waitFor(() => expect(locText()).toBe('/search?q=serum'));

    await back(user);
    expect(path()).toBe('/');
  });

  it('page changes PUSH: Back returns to the previous page with the filters intact', async () => {
    const { user } = renderSearch(['/', '/search?q=serum&skin_type=oily&is_vegan=true']);
    await settle();

    await user.click(screen.getByRole('button', { name: 'Page 2' }));
    await waitFor(() => expect(url().get('page')).toBe('2'));
    expect(url().get('skin_type')).toBe('oily');

    await back(user);

    expect(path()).toBe('/search'); // still on the results, not thrown out to '/'
    expect(url().get('page')).not.toBe('2');
    expect(url().get('skin_type')).toBe('oily');
    expect(url().get('is_vegan')).toBe('true');
    await waitFor(() => expect(lastParams()).toMatchObject({ skin_type: 'oily', is_vegan: 'true' }));
    expect(lastParams().page).toBe(1);
    expect(hasChip('Skin Type: Oily')).toBe(true);

    await forward(user);
    expect(url().get('page')).toBe('2');
    await waitFor(() => expect(lastParams().page).toBe('2'));
  });

  it('submitting a NEW search term pushes: Back returns to the previous search', async () => {
    const { user } = renderSearch(['/search?q=serum&skin_type=oily']);
    await settle();

    const box = screen.getByPlaceholderText('Refine your search…');
    await user.clear(box);
    await user.type(box, 'lipstick{Enter}');
    await waitFor(() => expect(url().get('q')).toBe('lipstick'));

    await back(user);

    await waitFor(() => expect(url().get('q')).toBe('serum'));
    expect(url().get('skin_type')).toBe('oily');
    expect(screen.getByPlaceholderText('Refine your search…')).toHaveValue('serum');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('SearchResults history — the page follows the URL', () => {
  it('Back / Forward restore the sidebar, search box and price fields', async () => {
    const { user } = renderSearch(['/search?q=serum&skin_type=oily&min_price=50000']);
    await settle();
    expect(priceMin()).toHaveValue('5000'); // Toman text field (Persian digits allowed); Rial in the URL
    expect(hasChip('Skin Type: Oily')).toBe(true);

    await user.click(screen.getByRole('button', { name: 'external-nav' }));
    await waitFor(() => expect(screen.getByPlaceholderText('Refine your search…')).toHaveValue('lipstick'));
    expect(priceMin()).toHaveValue('20000');
    expect(hasChip('Skin Type: Dry')).toBe(true);
    expect(hasChip('Skin Type: Oily')).toBe(false);

    await back(user);
    await waitFor(() => expect(screen.getByPlaceholderText('Refine your search…')).toHaveValue('serum'));
    expect(priceMin()).toHaveValue('5000'); // Toman text field (Persian digits allowed); Rial in the URL
    expect(hasChip('Skin Type: Oily')).toBe(true);
    expect(hasChip('Skin Type: Dry')).toBe(false);
    await waitFor(() => expect(lastParams()).toMatchObject({ search: 'serum', skin_type: 'oily', min_price: '50000' }));
  });

  it('a URL shared into a new tab restores the same filters and results', async () => {
    const first = renderSearch(['/search?q=serum']);
    await settle();
    await first.user.click(row('Oily'));
    await first.user.click(row('Dry'));
    await first.user.click(row('Vegan'));
    await first.user.click(row('Female'));
    await waitFor(() => expect(url().get('gender')).toBe('female'));
    await waitFor(() => expect(lastParams().gender).toBe('female'));
    const sharedUrl = locText();
    const requestBefore = lastParams();

    first.unmount();
    getProducts.mockClear();
    renderSearch([sharedUrl]); // "new tab"
    await settle();

    expect(getProducts.mock.calls[0][0]).toEqual(requestBefore);
    expect(locText()).toBe(sharedUrl);
    ['Skin Type: Oily', 'Skin Type: Dry', 'Certification: Vegan', 'Gender: Female'].forEach((label) =>
      expect(hasChip(label)).toBe(true),
    );
  });

  it('multi-select values are written as one comma-separated param', async () => {
    const { user } = renderSearch();
    await settle();
    await user.click(row('Oily'));
    await user.click(row('Dry'));
    await waitFor(() => expect(url().get('skin_type')).toBe('oily,dry'));
    expect(url().getAll('skin_type')).toHaveLength(1);
  });
});
