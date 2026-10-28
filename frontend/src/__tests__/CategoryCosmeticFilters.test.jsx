import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Category from '../pages/Category';

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

// ─── Fixtures / helpers ───────────────────────────────────────────────────────
const product = (over = {}) => ({
  id: 1, slug: 'p', name: 'Test Product', price: 499_900, original_price: null,
  rating: 4.5, reviews_count: 10, stock: 5, is_new: false, is_sale: false,
  discount_percent: 0, thumbnail_url: '/img/t.webp', images: [], category: { name: 'Skincare' },
  ...over,
});
const page = (items = [product()], extra = {}) => ({
  data: { results: items, count: items.length, total_pages: 1, ...extra },
});

const renderCategory = () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={['/category']}>
      <Category />
    </MemoryRouter>,
  );
  return { user };
};

/** Params of the most recent product request. */
const lastParams = () => getProducts.mock.calls.at(-1)[0];
const settle = async () => { await screen.findByText('Test Product'); };

const box = (name) => screen.getByRole('checkbox', { name });
const radio = (name) => screen.getByRole('radio', { name });

const COSMETIC_KEYS = [
  'skin_type', 'hair_type', 'gender', 'min_spf', 'max_spf',
  'is_cruelty_free', 'is_vegan', 'is_organic',
];

beforeEach(() => {
  vi.clearAllMocks();
  getCategories.mockResolvedValue({ data: [] });
  getBrands.mockResolvedValue({ data: [] });
  getColors.mockResolvedValue({ data: [] });
  getProducts.mockResolvedValue(page());
  getProductFacetCounts.mockResolvedValue({ data: null }); // no counts unless a test supplies them
});

// ═════════════════════════════════════════════════════════════════════════════
describe('Category — cosmetics filters in the sidebar', () => {
  it('adds the new sections without removing the existing ones', async () => {
    renderCategory();
    await settle();

    ['Skin Type', 'Hair Type', 'SPF', 'Gender', 'Certifications'].forEach((t) =>
      expect(screen.getByRole('heading', { name: t })).toBeInTheDocument(),
    );
    // existing sidebar widgets still there
    expect(screen.getByRole('heading', { name: 'Price Range' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Filter by Brand' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Filter by Color' })).toBeInTheDocument();
  });

  it('the initial request carries none of the new filters', async () => {
    renderCategory();
    await settle();
    COSMETIC_KEYS.forEach((k) => expect(lastParams()).not.toHaveProperty(k));
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('Category — requests', () => {
  it('several skin types are sent comma-joined (match ANY of them)', async () => {
    const { user } = renderCategory();
    await settle();

    await user.click(box('Oily'));
    await user.click(box('Dry'));

    await waitFor(() => expect(lastParams().skin_type).toBe('oily,dry'));
  });

  it('hair type, gender and each certification map to their params', async () => {
    const { user } = renderCategory();
    await settle();

    await user.click(box('Curly'));
    await user.click(radio('Female'));
    await user.click(box('Cruelty-Free'));
    await user.click(box('Organic'));

    await waitFor(() =>
      expect(lastParams()).toMatchObject({
        hair_type: 'curly',
        gender: 'female',
        is_cruelty_free: 'true',
        is_organic: 'true',
      }),
    );
    expect(lastParams()).not.toHaveProperty('is_vegan');
  });

  it('skin type + vegan + min SPF are sent TOGETHER in one request (AND across facets)', async () => {
    const { user } = renderCategory();
    await settle();

    await user.click(box('Oily'));
    await user.click(box('Dry'));
    await user.click(box('Vegan'));
    await user.type(screen.getByLabelText('Minimum SPF'), '30');
    await user.click(screen.getByRole('button', { name: 'Apply SPF range' }));

    await waitFor(() =>
      expect(lastParams()).toMatchObject({
        skin_type: 'oily,dry',
        is_vegan: 'true',
        min_spf: 30,
      }),
    );
    expect(lastParams()).not.toHaveProperty('is_organic');
    expect(lastParams()).not.toHaveProperty('max_spf');
  });

  it('keeps the existing params (paging, sort) alongside the new ones', async () => {
    const { user } = renderCategory();
    await settle();
    await user.click(box('Vegan'));
    await waitFor(() => expect(lastParams().is_vegan).toBe('true'));
    expect(lastParams()).toMatchObject({ page: 1, page_size: 12, ordering: '-created_at' });
  });

  it('unchecking a certification drops the param — it is never sent as false', async () => {
    const { user } = renderCategory();
    await settle();

    await user.click(box('Vegan'));
    await waitFor(() => expect(lastParams().is_vegan).toBe('true'));

    await user.click(box('Vegan'));
    await waitFor(() => expect(lastParams()).not.toHaveProperty('is_vegan'));

    // and at no point in any request was a false value sent
    getProducts.mock.calls.forEach(([p]) => {
      Object.values(p).forEach((v) => {
        expect(v).not.toBe(false);
        expect(v).not.toBe('false');
      });
    });
  });

  it('changing a filter goes back to page 1', async () => {
    getProducts.mockImplementation(({ page: pg }) =>
      Promise.resolve(page([product({ name: 'Test Product' })], { count: 30, total_pages: 3, page: pg })),
    );
    const { user } = renderCategory();
    await settle();

    await user.click(screen.getByRole('button', { name: /next/i }));
    await waitFor(() => expect(lastParams().page).toBe(2));

    await user.click(box('Vegan'));
    await waitFor(() => expect(lastParams()).toMatchObject({ page: 1, is_vegan: 'true' }));
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('Category — active filter chips', () => {
  it('shows a chip per selected value', async () => {
    const { user } = renderCategory();
    await settle();

    await user.click(box('Oily'));
    await user.click(box('Dry'));
    await user.click(box('Vegan'));
    await user.click(radio('Male'));

    expect(await screen.findByText(/Skin Type: Oily/)).toBeInTheDocument();
    expect(screen.getByText(/Skin Type: Dry/)).toBeInTheDocument();
    expect(screen.getByText(/Certification: Vegan/)).toBeInTheDocument();
    expect(screen.getByText(/Gender: Male/)).toBeInTheDocument();
  });

  it('shows an SPF chip for the applied range', async () => {
    const { user } = renderCategory();
    await settle();
    await user.type(screen.getByLabelText('Minimum SPF'), '15');
    await user.type(screen.getByLabelText('Maximum SPF'), '50');
    await user.click(screen.getByRole('button', { name: 'Apply SPF range' }));
    expect(await screen.findByText(/SPF: 15 – 50/)).toBeInTheDocument();
  });

  it("removing one chip removes only that filter, and unticks its checkbox", async () => {
    const { user } = renderCategory();
    await settle();
    await user.click(box('Oily'));
    await user.click(box('Dry'));

    const chip = await screen.findByText(/Skin Type: Oily/);
    await user.click(within(chip).getByRole('button'));

    await waitFor(() => expect(lastParams().skin_type).toBe('dry'));
    expect(box('Oily')).not.toBeChecked();
    expect(box('Dry')).toBeChecked();
    expect(screen.queryByText(/Skin Type: Oily/)).not.toBeInTheDocument();
  });

  it('removing the last value of a facet removes its param', async () => {
    const { user } = renderCategory();
    await settle();
    await user.click(box('Vegan'));

    const chip = await screen.findByText(/Certification: Vegan/);
    await user.click(within(chip).getByRole('button'));

    await waitFor(() => expect(lastParams()).not.toHaveProperty('is_vegan'));
    expect(box('Vegan')).not.toBeChecked();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('Category — clear all', () => {
  const pickEverything = async (user) => {
    await user.click(box('Oily'));
    await user.click(box('Curly'));
    await user.click(radio('Female'));
    await user.click(box('Vegan'));
    await user.type(screen.getByLabelText('Minimum SPF'), '30');
    await user.click(screen.getByRole('button', { name: 'Apply SPF range' }));
    await waitFor(() => expect(lastParams().min_spf).toBe(30));
  };

  it('"Clear All Filters" resets every new filter and re-fetches unfiltered', async () => {
    const { user } = renderCategory();
    await settle();
    await pickEverything(user);

    await user.click(screen.getByRole('button', { name: /clear all filters/i }));

    await waitFor(() =>
      COSMETIC_KEYS.forEach((k) => expect(lastParams()).not.toHaveProperty(k)),
    );
    screen.getAllByRole('checkbox').forEach((c) => expect(c).not.toBeChecked());
    screen.getAllByRole('radio').forEach((r) => expect(r).not.toBeChecked());
    expect(screen.getByLabelText('Minimum SPF')).toHaveValue(null);
    expect(screen.queryByText(/Active Filters/)).not.toBeInTheDocument();
  });

  it('clears the new filters together with the existing ones', async () => {
    getBrands.mockResolvedValue({ data: [{ id: 1, name: 'Acme', slug: 'acme' }] });
    const { user } = renderCategory();
    await settle();

    await user.click(await screen.findByRole('checkbox', { name: 'Acme' }));
    await user.click(box('Vegan'));
    await waitFor(() => expect(lastParams()).toMatchObject({ brand: 'acme', is_vegan: 'true' }));

    await user.click(screen.getByRole('button', { name: /clear all filters/i }));

    await waitFor(() => {
      expect(lastParams()).not.toHaveProperty('brand');
      expect(lastParams()).not.toHaveProperty('is_vegan');
    });
  });

  it('the chip bar "Clear All" does the same', async () => {
    const { user } = renderCategory();
    await settle();
    await user.click(box('Oily'));
    await user.click(box('Organic'));
    await screen.findByText(/Active Filters/);

    const chipBar = screen.getByText(/Active Filters/).parentElement;
    await user.click(within(chipBar).getByRole('button', { name: 'Clear All' }));

    await waitFor(() => {
      expect(lastParams()).not.toHaveProperty('skin_type');
      expect(lastParams()).not.toHaveProperty('is_organic');
    });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('Category — facet counts', () => {
  const countsFor = (skin, gender, vegan) => ({
    skin_type: { oily: skin, dry: 0, combination: 3, sensitive: 0, normal: 7, all: 1 },
    hair_type: { straight: 2, wavy: 0, curly: 5, coily: 1, all: 0 },
    gender: { unisex: 10, female: gender, male: 0 },
    is_cruelty_free: 8,
    is_vegan: vegan,
    is_organic: 2,
  });
  const ALL = countsFor(12, 4, 5);
  const FEMALE = countsFor(5, 4, 3); // what the counts look like once gender=female is applied

  // The API answers according to the filters it was asked about, like the real one.
  const respondByFilters = () =>
    getProductFacetCounts.mockImplementation((params) =>
      Promise.resolve({ data: params.gender === 'female' ? FEMALE : ALL }),
    );

  const lastFacetParams = () => getProductFacetCounts.mock.calls.at(-1)[0];

  it('shows the counts next to the filter options', async () => {
    respondByFilters();
    renderCategory();

    expect(await screen.findByRole('checkbox', { name: 'Oily (12)' })).toBeInTheDocument();
    expect(box('Combination (3)')).toBeInTheDocument();
    expect(box('Curly (5)')).toBeInTheDocument();
    expect(radio('Female (4)')).toBeInTheDocument();
    expect(box('Cruelty-Free (8)')).toBeInTheDocument();
    expect(box('Vegan (5)')).toBeInTheDocument();
  });

  it('asks for counts alongside the first product fetch, with only filter params', async () => {
    respondByFilters();
    renderCategory();
    await settle();
    await waitFor(() => expect(getProductFacetCounts).toHaveBeenCalledTimes(1));

    expect(getProducts).toHaveBeenCalledTimes(1);
    // no paging or sort — they can't change the counts
    expect(lastFacetParams()).toEqual({});
    expect(getProducts.mock.calls[0][0]).toMatchObject({ page: 1, page_size: 12 });
  });

  it('updates the counts after a filter change, and sends the active filters', async () => {
    respondByFilters();
    const { user } = renderCategory();
    await screen.findByRole('checkbox', { name: 'Oily (12)' });

    await user.click(radio('Female (4)'));

    expect(await screen.findByRole('checkbox', { name: 'Oily (5)' })).toBeInTheDocument();
    expect(box('Vegan (3)')).toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: 'Oily (12)' })).not.toBeInTheDocument();
    expect(lastFacetParams()).toEqual({ gender: 'female' });
  });

  it('carries every active filter into the counts request', async () => {
    respondByFilters();
    const { user } = renderCategory();
    await screen.findByRole('checkbox', { name: 'Oily (12)' });

    await user.click(box('Oily (12)'));
    await user.click(box('Vegan (5)'));
    await user.type(screen.getByLabelText('Minimum SPF'), '30');
    await user.click(screen.getByRole('button', { name: 'Apply SPF range' }));

    await waitFor(() =>
      expect(lastFacetParams()).toEqual({ skin_type: 'oily', is_vegan: 'true', min_spf: 30 }),
    );
  });

  it('refreshes the counts when filters are cleared', async () => {
    respondByFilters();
    const { user } = renderCategory();
    await screen.findByRole('checkbox', { name: 'Oily (12)' });
    await user.click(radio('Female (4)'));
    await screen.findByRole('checkbox', { name: 'Oily (5)' });

    await user.click(screen.getByRole('button', { name: /clear all filters/i }));

    expect(await screen.findByRole('checkbox', { name: 'Oily (12)' })).toBeInTheDocument();
    expect(lastFacetParams()).toEqual({});
  });

  it('does not refetch the counts when only the page changes', async () => {
    respondByFilters();
    getProducts.mockImplementation(({ page: pg }) =>
      Promise.resolve(page([product()], { count: 30, total_pages: 3, page: pg })),
    );
    const { user } = renderCategory();
    await screen.findByRole('checkbox', { name: 'Oily (12)' });
    const facetCalls = getProductFacetCounts.mock.calls.length;

    await user.click(screen.getByRole('button', { name: /next/i }));
    await waitFor(() => expect(lastParams().page).toBe(2));
    await new Promise((r) => setTimeout(r, 450)); // longer than the debounce

    expect(getProductFacetCounts.mock.calls.length).toBe(facetCalls);
  });

  it('greys out and disables options that would give no results', async () => {
    respondByFilters();
    renderCategory();
    await screen.findByRole('checkbox', { name: 'Oily (12)' });

    expect(box('Dry (0)')).toBeDisabled();
    expect(box('Dry (0)').closest('label')).toHaveClass('text-gray-400');
    expect(radio('Male (0)')).toBeDisabled();
    expect(box('Oily (12)')).toBeEnabled();
  });

  it('a disabled option cannot add a filter', async () => {
    respondByFilters();
    const { user } = renderCategory();
    await screen.findByRole('checkbox', { name: 'Oily (12)' });
    const before = getProducts.mock.calls.length;

    await user.click(box('Dry (0)'));

    expect(box('Dry (0)')).not.toBeChecked();
    expect(getProducts.mock.calls.length).toBe(before);
  });

  it('a selected option stays enabled even when its count drops to 0', async () => {
    getProductFacetCounts.mockImplementation((params) =>
      Promise.resolve({
        data: params.skin_type === 'oily'
          ? { ...ALL, skin_type: { ...ALL.skin_type, oily: 0 } }
          : ALL,
      }),
    );
    const { user } = renderCategory();
    await screen.findByRole('checkbox', { name: 'Oily (12)' });

    await user.click(box('Oily (12)'));

    const oily = await screen.findByRole('checkbox', { name: 'Oily (0)' });
    expect(oily).toBeChecked();
    expect(oily).toBeEnabled(); // so it can still be unticked

    await user.click(oily);
    expect(await screen.findByRole('checkbox', { name: 'Oily (12)' })).not.toBeChecked();
  });

  it('shows the plain options, still fully usable, when the counts request fails', async () => {
    getProductFacetCounts.mockRejectedValue(new Error('500'));
    const { user } = renderCategory();
    await settle();

    expect(box('Oily')).toBeEnabled();
    expect(box('Dry')).toBeEnabled();
    // (not a page-wide text search: product cards show "(10) reviews" too)
    [...screen.getAllByRole('checkbox'), ...screen.getAllByRole('radio')].forEach((el) =>
      expect(el).not.toHaveAccessibleName(/\(\d+\)/),
    );

    await user.click(box('Dry'));
    await waitFor(() => expect(lastParams().skin_type).toBe('dry'));
  });
});
