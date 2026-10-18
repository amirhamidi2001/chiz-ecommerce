import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Category from '../pages/Category';

// The other URL tests use MemoryRouter, which SIMULATES history. This file
// runs the page under BrowserRouter against jsdom's real History API, so the
// replace-vs-push behaviour is checked against window.history itself: the
// number of entries, window.location, and a real history.back().

vi.mock('../services/api', () => ({
  getProducts: vi.fn(),
  getCategories: vi.fn(),
  getBrands: vi.fn(),
  getColors: vi.fn(),
  getProductFacetCounts: vi.fn(),
}));
vi.mock('../context/CartContext', () => ({
  useCart: () => ({ addToCart: vi.fn().mockResolvedValue({ success: true, message: 'ok' }) }),
}));

import {
  getProducts, getCategories, getBrands, getColors, getProductFacetCounts,
} from '../services/api';

const PRODUCT = {
  id: 1, slug: 'test-product', name: 'Test Product', price: '49.99', original_price: null,
  rating: 4.5, reviews_count: 10, stock: 5, is_new: false, is_sale: false,
  discount_percent: 0, thumbnail_url: '/img/t.webp', images: [], category: { name: 'Skincare' },
};

const renderAt = (urlPath) => {
  window.history.replaceState({}, '', urlPath);
  const user = userEvent.setup();
  render(
    <BrowserRouter>
      <Routes>
        <Route path="/category" element={<Category />} />
      </Routes>
    </BrowserRouter>,
  );
  return { user };
};

const params = () => new URLSearchParams(window.location.search);
const entries = () => window.history.length;
const settle = async () => { await screen.findByText('Test Product'); };
const box = (name) => screen.getByRole('checkbox', { name });

beforeEach(() => {
  vi.clearAllMocks();
  getCategories.mockResolvedValue({ data: [] });
  getBrands.mockResolvedValue({ data: [] });
  getColors.mockResolvedValue({ data: [] });
  getProductFacetCounts.mockResolvedValue({ data: null });
  getProducts.mockImplementation(() =>
    Promise.resolve({ data: { results: [PRODUCT], count: 30, total_pages: 3 } }),
  );
});

describe('Category — the real History API', () => {
  it('filter changes add NO history entries (replaceState), however many are made', async () => {
    const { user } = renderAt('/category');
    await settle();
    const before = entries();

    await user.click(box('Oily'));
    await user.click(box('Dry'));
    await user.click(box('Vegan'));
    await user.click(screen.getByRole('radio', { name: 'Female' }));
    await user.click(box('Curly'));
    await user.selectOptions(screen.getByText('Sort By').nextElementSibling, 'price');
    await waitFor(() => expect(params().get('ordering')).toBe('price'));

    expect(entries()).toBe(before); // 6 changes, 0 new entries
    expect(window.location.pathname).toBe('/category');
    expect(params().get('skin_type')).toBe('oily,dry');
    expect(params().getAll('skin_type')).toHaveLength(1);
    expect(params().get('hair_type')).toBe('curly');
    expect(params().get('gender')).toBe('female');
    expect(params().get('is_vegan')).toBe('true');
  });

  it('a page change adds exactly ONE entry (pushState)', async () => {
    const { user } = renderAt('/category?skin_type=oily');
    await settle();
    const before = entries();

    await user.click(screen.getByRole('button', { name: '2' }));
    await waitFor(() => expect(params().get('page')).toBe('2'));

    expect(entries()).toBe(before + 1);
  });

  it('the browser Back button steps from page 2 to page 1 with the filters intact', async () => {
    const { user } = renderAt('/category?skin_type=oily&is_vegan=true');
    await settle();
    await user.click(screen.getByRole('button', { name: '2' }));
    await waitFor(() => expect(params().get('page')).toBe('2'));
    await waitFor(() => expect(getProducts.mock.calls.at(-1)[0].page).toBe(2));

    act(() => window.history.back()); // the real browser Back

    await waitFor(() => expect(params().has('page')).toBe(false));
    expect(params().get('skin_type')).toBe('oily');
    expect(params().get('is_vegan')).toBe('true');
    await waitFor(() => expect(getProducts.mock.calls.at(-1)[0].page).toBe(1));
    expect(getProducts.mock.calls.at(-1)[0]).toMatchObject({ skin_type: 'oily', is_vegan: 'true' });
    expect(box('Oily')).toBeChecked();
    expect(box('Vegan')).toBeChecked();

    act(() => window.history.forward()); // and the real Forward

    await waitFor(() => expect(params().get('page')).toBe('2'));
    expect(params().get('skin_type')).toBe('oily');
  });

  it('loading a copied URL restores the same filters in the sidebar and the request', async () => {
    renderAt('/category?skin_type=oily%2Cdry&hair_type=curly&gender=female&is_vegan=true&min_spf=30');
    await settle();

    expect(box('Oily')).toBeChecked();
    expect(box('Dry')).toBeChecked();
    expect(box('Curly')).toBeChecked();
    expect(screen.getByRole('radio', { name: 'Female' })).toBeChecked();
    expect(box('Vegan')).toBeChecked();
    expect(screen.getByLabelText('Minimum SPF')).toHaveValue(30);
    expect(getProducts.mock.calls[0][0]).toMatchObject({
      skin_type: 'oily,dry',
      hair_type: 'curly',
      gender: 'female',
      is_vegan: 'true',
      min_spf: 30,
    });
  });
});
