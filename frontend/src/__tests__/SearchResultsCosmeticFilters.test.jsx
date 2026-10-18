import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
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

import {
  getProducts, getCategories, getBrands, getProductFacetCounts,
} from '../services/api';

window.scrollTo = vi.fn();

// ─── Helpers ──────────────────────────────────────────────────────────────────
const item = () => ({
  id: 1, name: 'Test Product', slug: 'test-product', price: '29.99', sale_price: null,
  rating: 4.2, reviews_count: 17, thumbnail: '/img/p.webp', in_stock: true, is_new: false,
  category: { name: 'Skincare' }, brand: { name: 'Acme' },
});

const UrlProbe = () => {
  const { search } = useLocation();
  return <div data-testid="url">{search}</div>;
};

const renderSearch = (initial = '?q=serum') => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={[`/search${initial}`]}>
      <SearchResults />
      <UrlProbe />
    </MemoryRouter>,
  );
  return { user };
};

const lastParams = () => getProducts.mock.calls.at(-1)[0];
const url = () => new URLSearchParams(screen.getByTestId('url').textContent);
const settle = async () => { await screen.findByText('Test Product'); };
// The sidebar's rows are buttons; the chips' remove buttons have a longer, different name.
const row = (name) => screen.getByRole('button', { name });

const COSMETIC_KEYS = [
  'skin_type', 'hair_type', 'gender', 'min_spf', 'max_spf',
  'is_cruelty_free', 'is_vegan', 'is_organic',
];

beforeEach(() => {
  vi.clearAllMocks();
  getCategories.mockResolvedValue({ data: [] });
  getBrands.mockResolvedValue({ data: [] });
  getProductFacetCounts.mockResolvedValue({ data: null }); // no counts unless a test supplies them
  getProducts.mockImplementation(() =>
    Promise.resolve({ data: { results: [item()], count: 1 } }),
  );
});

// ═════════════════════════════════════════════════════════════════════════════
describe('SearchResults — cosmetics filters in the sidebar', () => {
  it('adds the new groups after the existing ones', async () => {
    renderSearch();
    await settle();
    ['Price Range', 'Customer Rating', 'Skin Type', 'Hair Type', 'SPF', 'Gender', 'Certifications']
      .forEach((t) => expect(screen.getByRole('button', { name: t })).toBeInTheDocument());
  });

  it('the groups are collapsible, like the existing ones', async () => {
    const { user } = renderSearch();
    await settle();
    expect(screen.getByRole('button', { name: 'Oily' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Skin Type' }));
    expect(screen.queryByRole('button', { name: 'Oily' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Skin Type' }));
    expect(screen.getByRole('button', { name: 'Oily' })).toBeInTheDocument();
  });

  it('a plain search sends none of the new filters', async () => {
    renderSearch();
    await settle();
    COSMETIC_KEYS.forEach((k) => expect(lastParams()).not.toHaveProperty(k));
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('SearchResults — URL <-> request', () => {
  it('a link with the filters in the URL fetches with them (shareable / reload-safe)', async () => {
    renderSearch('?q=serum&skin_type=oily,dry&hair_type=curly&gender=female&min_spf=30&max_spf=50&is_vegan=true');
    await settle();
    expect(getProducts.mock.calls[0][0]).toMatchObject({
      search: 'serum',
      skin_type: 'oily,dry',
      hair_type: 'curly',
      gender: 'female',
      min_spf: 30,
      max_spf: 50,
      is_vegan: 'true',
    });
    expect(getProducts.mock.calls[0][0]).not.toHaveProperty('is_organic');
  });

  it('is_vegan=false in a hand-edited URL is NOT forwarded as a false filter', async () => {
    renderSearch('?q=serum&is_vegan=false&skin_type=bogus');
    await settle();
    expect(lastParams()).not.toHaveProperty('is_vegan');
    expect(lastParams()).not.toHaveProperty('skin_type');
  });

  it('several skin types go into the URL and the request comma-joined', async () => {
    const { user } = renderSearch();
    await settle();
    await user.click(row('Oily'));
    await user.click(row('Dry'));
    await waitFor(() => expect(lastParams().skin_type).toBe('oily,dry'));
    expect(url().get('skin_type')).toBe('oily,dry');
  });

  it('skin type + vegan + min SPF narrow the same request together (AND across facets)', async () => {
    const { user } = renderSearch();
    await settle();

    await user.click(row('Oily'));
    await user.click(row('Dry'));
    await user.click(row('Vegan'));
    await user.type(screen.getByLabelText('Minimum SPF'), '30');
    await user.click(screen.getByRole('button', { name: 'Apply SPF range' }));

    await waitFor(() =>
      expect(lastParams()).toMatchObject({
        search: 'serum',
        skin_type: 'oily,dry',
        is_vegan: 'true',
        min_spf: 30,
      }),
    );
  });

  it('unchecking a certification removes it from the URL and the request — never false', async () => {
    const { user } = renderSearch('?q=serum&is_vegan=true');
    await settle();
    await user.click(row('Vegan'));
    await waitFor(() => expect(lastParams()).not.toHaveProperty('is_vegan'));
    expect(url().has('is_vegan')).toBe(false);
    getProducts.mock.calls.forEach(([p]) =>
      Object.values(p).forEach((v) => {
        expect(v).not.toBe(false);
        expect(v).not.toBe('false');
      }),
    );
  });

  it('gender is single-select and clicking it again clears it', async () => {
    const { user } = renderSearch();
    await settle();
    await user.click(row('Female'));
    await waitFor(() => expect(lastParams().gender).toBe('female'));
    await user.click(row('Male'));
    await waitFor(() => expect(lastParams().gender).toBe('male'));
    await user.click(row('Male'));
    await waitFor(() => expect(lastParams()).not.toHaveProperty('gender'));
  });

  it('changing a filter resets to page 1', async () => {
    const { user } = renderSearch('?q=serum&page=3');
    await settle();
    await user.click(row('Vegan'));
    await waitFor(() => expect(lastParams()).toMatchObject({ page: '1', is_vegan: 'true' }));
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('SearchResults — active filters', () => {
  it('"Clear all (n)" counts the new facets (one per group; each certification alone)', async () => {
    renderSearch('?q=serum&skin_type=oily,dry&is_vegan=true&min_spf=30');
    await settle();
    // skin type group + vegan + SPF range = 3
    expect(screen.getByRole('button', { name: /clear all \(3\)/i })).toBeInTheDocument();
  });

  it('shows a chip per selected value', async () => {
    renderSearch('?q=serum&skin_type=oily,dry&gender=male&is_organic=true&min_spf=15&max_spf=50');
    await settle();
    [
      'Remove Skin Type: Oily filter',
      'Remove Skin Type: Dry filter',
      'Remove Gender: Male filter',
      'Remove Certification: Organic filter',
      'Remove SPF: 15 – 50 filter',
    ].forEach((name) => expect(screen.getByRole('button', { name })).toBeInTheDocument());
  });

  it('removing one skin-type chip keeps the other', async () => {
    const { user } = renderSearch('?q=serum&skin_type=oily,dry');
    await settle();
    await user.click(screen.getByRole('button', { name: 'Remove Skin Type: Oily filter' }));
    await waitFor(() => expect(lastParams().skin_type).toBe('dry'));
    expect(url().get('skin_type')).toBe('dry');
  });

  it('removing the SPF chip clears both ends', async () => {
    const { user } = renderSearch('?q=serum&min_spf=15&max_spf=50');
    await settle();
    await user.click(screen.getByRole('button', { name: 'Remove SPF: 15 – 50 filter' }));
    await waitFor(() => {
      expect(lastParams()).not.toHaveProperty('min_spf');
      expect(lastParams()).not.toHaveProperty('max_spf');
    });
  });

  it('"Clear all" resets the new and existing filters but keeps the search term', async () => {
    const { user } = renderSearch(
      '?q=serum&min_price=5&skin_type=oily&hair_type=wavy&gender=female&is_vegan=true&is_cruelty_free=true&min_spf=30',
    );
    await settle();

    await user.click(screen.getByRole('button', { name: /clear all \(/i }));

    await waitFor(() => {
      COSMETIC_KEYS.forEach((k) => expect(lastParams()).not.toHaveProperty(k));
      expect(lastParams()).not.toHaveProperty('min_price');
    });
    expect(lastParams().search).toBe('serum');
    expect(screen.queryByRole('button', { name: /clear all \(/i })).not.toBeInTheDocument();
    expect(url().get('q')).toBe('serum');
  });

  it('the SPF inputs empty when the filters are cleared', async () => {
    const { user } = renderSearch('?q=serum&min_spf=30&max_spf=50');
    await settle();
    expect(screen.getByLabelText('Minimum SPF')).toHaveValue(30);
    await user.click(screen.getByRole('button', { name: /clear all \(/i }));
    await waitFor(() => expect(screen.getByLabelText('Minimum SPF')).toHaveValue(null));
  });

  it('with no results, the empty state offers to clear the new filters too', async () => {
    getProducts.mockImplementation(() => Promise.resolve({ data: { results: [], count: 0 } }));
    renderSearch('?q=serum&is_vegan=true');
    const empty = await screen.findByText(/no results found/i);
    expect(within(empty.parentElement).getByRole('button', { name: /clear filters/i })).toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('SearchResults — facet counts', () => {
  const countsFor = (skin, gender, vegan) => ({
    skin_type: { oily: skin, dry: 0, combination: 3, sensitive: 0, normal: 7, all: 1 },
    hair_type: { straight: 2, wavy: 0, curly: 5, coily: 1, all: 0 },
    gender: { unisex: 10, female: gender, male: 0 },
    is_cruelty_free: 8,
    is_vegan: vegan,
    is_organic: 2,
  });
  const ALL = countsFor(12, 4, 5);
  const FEMALE = countsFor(5, 4, 3);

  const respondByFilters = () =>
    getProductFacetCounts.mockImplementation((params) =>
      Promise.resolve({ data: params.gender === 'female' ? FEMALE : ALL }),
    );
  const lastFacetParams = () => getProductFacetCounts.mock.calls.at(-1)[0];

  it('shows the counts next to the filter options', async () => {
    respondByFilters();
    renderSearch();
    expect(await screen.findByRole('button', { name: 'Oily (12)' })).toBeInTheDocument();
    expect(row('Combination (3)')).toBeInTheDocument();
    expect(row('Curly (5)')).toBeInTheDocument();
    expect(row('Female (4)')).toBeInTheDocument();
    expect(row('Cruelty-Free (8)')).toBeInTheDocument();
    expect(row('Vegan (5)')).toBeInTheDocument();
  });

  it('counts the SAME filters the list shows — including the search term', async () => {
    respondByFilters();
    renderSearch('?q=serum&skin_type=oily&is_vegan=true&min_spf=30&page=2&ordering=price');
    await screen.findByRole('button', { name: 'Oily (12)' });

    // search + filters, but no page / sort
    expect(getProductFacetCounts.mock.calls[0][0]).toEqual({
      search: 'serum',
      skin_type: 'oily',
      is_vegan: 'true',
      min_spf: 30,
    });
  });

  it('updates the counts after a filter change', async () => {
    respondByFilters();
    const { user } = renderSearch();
    await screen.findByRole('button', { name: 'Oily (12)' });

    await user.click(row('Female (4)'));

    expect(await screen.findByRole('button', { name: 'Oily (5)' })).toBeInTheDocument();
    expect(row('Vegan (3)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Oily (12)' })).not.toBeInTheDocument();
    expect(lastFacetParams()).toMatchObject({ search: 'serum', gender: 'female' });
  });

  it('updates the counts when filters are cleared', async () => {
    respondByFilters();
    const { user } = renderSearch('?q=serum&gender=female');
    await screen.findByRole('button', { name: 'Oily (5)' });

    await user.click(screen.getByRole('button', { name: /clear all \(/i }));

    expect(await screen.findByRole('button', { name: 'Oily (12)' })).toBeInTheDocument();
    expect(lastFacetParams()).toEqual({ search: 'serum' });
  });

  it('greys out and disables options that would give no results', async () => {
    respondByFilters();
    renderSearch();
    await screen.findByRole('button', { name: 'Oily (12)' });

    expect(row('Dry (0)')).toBeDisabled();
    expect(row('Dry (0)')).toHaveClass('cursor-not-allowed');
    expect(row('Male (0)')).toBeDisabled();
    expect(row('Oily (12)')).toBeEnabled();
  });

  it('a disabled option cannot add a filter', async () => {
    respondByFilters();
    const { user } = renderSearch();
    await screen.findByRole('button', { name: 'Oily (12)' });

    await user.click(row('Dry (0)'));

    expect(url().has('skin_type')).toBe(false);
  });

  it('a selected option stays enabled even when its count is 0', async () => {
    getProductFacetCounts.mockResolvedValue({
      data: { ...ALL, skin_type: { ...ALL.skin_type, oily: 0 } },
    });
    renderSearch('?q=serum&skin_type=oily');
    const oily = await screen.findByRole('button', { name: 'Oily (0)' });
    expect(oily).toBeEnabled();
  });

  it('shows the plain, usable options when the counts request fails', async () => {
    getProductFacetCounts.mockRejectedValue(new Error('429'));
    const { user } = renderSearch();
    await settle();

    expect(row('Oily')).toBeEnabled();
    await user.click(row('Oily'));
    await waitFor(() => expect(lastParams().skin_type).toBe('oily'));
  });
});
