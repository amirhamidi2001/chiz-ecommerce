import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom';
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

// ─── Fixtures ─────────────────────────────────────────────────────────────────
const PRODUCT = {
  id: 1, slug: 'test-product', name: 'Test Product', price: '49.99', original_price: null,
  rating: 4.5, reviews_count: 10, stock: 5, is_new: false, is_sale: false,
  discount_percent: 0, thumbnail_url: '/img/t.webp', images: [], category: { name: 'Skincare' },
};
const BRANDS = [
  { id: 1, name: 'Acme', slug: 'acme' },
  { id: 2, name: 'Zen', slug: 'zen' },
];
const COLORS = [
  { id: 1, name: 'Red', hex_code: '#ff0000' },
  { id: 2, name: 'Deep Blue', hex_code: '#000088' },
];
const CATEGORIES = [{ id: 10, slug: 'skincare', name: 'Skincare', children: [] }];

const respond = (totalPages = 1) =>
  getProducts.mockImplementation(() =>
    Promise.resolve({ data: { results: [PRODUCT], count: 30, total_pages: totalPages } }),
  );

// ─── Harness ──────────────────────────────────────────────────────────────────
// A probe outside <Routes> exposes the current URL and the browser's
// back / forward / "someone else changed the URL" actions.
const NavProbe = () => {
  const { pathname, search } = useLocation();
  const navigate = useNavigate();
  return (
    <div>
      <div data-testid="loc">{pathname + search}</div>
      <button onClick={() => navigate(-1)}>history-back</button>
      <button onClick={() => navigate(1)}>history-forward</button>
      <button onClick={() => navigate('/category?skin_type=dry&search=lip')}>external-nav</button>
    </div>
  );
};

const tree = () => (
  <>
    <NavProbe />
    <Routes>
      <Route path="/category" element={<Category />} />
      <Route path="/product/:slug" element={<div>Product detail page</div>} />
      <Route path="/" element={<div>Home page</div>} />
    </Routes>
  </>
);

const renderCategory = ({ entries = ['/category'], index, fakeTimers = false } = {}) => {
  const user = userEvent.setup(fakeTimers ? { advanceTimers: vi.advanceTimersByTime } : {});
  const utils = render(
    <MemoryRouter initialEntries={entries} initialIndex={index ?? entries.length - 1}>
      {tree()}
    </MemoryRouter>,
  );
  return { user, ...utils };
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
const locText = () => screen.getByTestId('loc').textContent;
const path = () => locText().split('?')[0];
const url = () => new URLSearchParams(locText().split('?')[1] || '');
const lastParams = () => getProducts.mock.calls.at(-1)[0];
const settle = async () => { await screen.findByText('Test Product'); };
const sidebarReady = async () => { await screen.findByRole('checkbox', { name: 'Acme' }); };
const advance = (ms) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

const box = (name) => screen.getByRole('checkbox', { name });
const radio = (name) => screen.getByRole('radio', { name });
const colorBox = (name) => screen.getByTitle(name).querySelector('input');
const sortSelect = () => screen.getByText('Sort By').nextElementSibling;
const pageSizeSelect = () => screen.getByText('Items Per Page').nextElementSibling;
const searchInput = () => screen.getByPlaceholderText(/search products/i);
const priceInputs = () => screen.getAllByRole('spinbutton').slice(0, 2); // price min / max
const clearAllButton = () => screen.getByRole('button', { name: /clear all filters/i });
const back = (user) => user.click(screen.getByRole('button', { name: 'history-back' }));
const forward = (user) => user.click(screen.getByRole('button', { name: 'history-forward' }));
const chip = (text) => screen.getByText(text);

const FULL_URL =
  '/category?category=skincare&search=rose&brand=acme,zen&color=Red&min_price=100&max_price=500' +
  '&skin_type=oily,dry&hair_type=curly&gender=female&min_spf=30&max_spf=50' +
  '&is_cruelty_free=true&is_vegan=true&ordering=price&page=2&page_size=24&flash_sale=7';

beforeEach(() => {
  vi.clearAllMocks();
  getCategories.mockResolvedValue({ data: CATEGORIES });
  getBrands.mockResolvedValue({ data: BRANDS });
  getColors.mockResolvedValue({ data: COLORS });
  getProductFacetCounts.mockResolvedValue({ data: null });
  respond();
});
afterEach(() => {
  vi.useRealTimers();
});

// ═════════════════════════════════════════════════════════════════════════════
describe('Category URL sync — a URL restores the page', () => {
  it('a bare URL requests the defaults, once', async () => {
    renderCategory();
    await settle();
    expect(getProducts).toHaveBeenCalledTimes(1);
    expect(getProducts.mock.calls[0][0]).toEqual({ page: 1, page_size: 12, ordering: '-created_at' });
  });

  it('a filtered URL fetches with ALL of its filters, once', async () => {
    renderCategory({ entries: [FULL_URL] });
    await settle();
    expect(getProducts).toHaveBeenCalledTimes(1); // no flash of unfiltered results first
    expect(getProducts.mock.calls[0][0]).toEqual({
      page: 2,
      page_size: 24,
      ordering: 'price',
      category: 'skincare',
      search: 'rose',
      brand: 'acme,zen',
      color: 'Red',
      min_price: 100,
      max_price: 500,
      flash_sale: '7',
      skin_type: 'oily,dry',
      hair_type: 'curly',
      gender: 'female',
      min_spf: 30,
      max_spf: 50,
      is_cruelty_free: 'true',
      is_vegan: 'true',
    });
  });

  it('shows those same selections in the sidebar — not just a silently filtered list', async () => {
    renderCategory({ entries: [FULL_URL] });
    await settle();
    await sidebarReady();

    // pre-existing filters
    expect(searchInput()).toHaveValue('rose');
    expect(box('Acme')).toBeChecked();
    expect(box('Zen')).toBeChecked();
    expect(colorBox('Red')).toBeChecked();
    expect(colorBox('Deep Blue')).not.toBeChecked();
    const [minPrice, maxPrice] = priceInputs();
    expect(minPrice).toHaveValue(100);
    expect(maxPrice).toHaveValue(500);
    expect(sortSelect()).toHaveValue('price');
    expect(pageSizeSelect()).toHaveValue('24');
    expect(screen.getByRole('button', { name: 'Skincare' })).toHaveClass('text-teal-600');

    // the cosmetics facets
    expect(box('Oily')).toBeChecked();
    expect(box('Dry')).toBeChecked();
    expect(box('Normal')).not.toBeChecked();
    expect(box('Curly')).toBeChecked();
    expect(radio('Female')).toBeChecked();
    expect(screen.getByLabelText('Minimum SPF')).toHaveValue(30);
    expect(screen.getByLabelText('Maximum SPF')).toHaveValue(50);
    expect(box('Cruelty-Free')).toBeChecked();
    expect(box('Vegan')).toBeChecked();
    expect(box('Organic')).not.toBeChecked();
  });

  it('lists every active filter as a chip', async () => {
    renderCategory({ entries: [FULL_URL] });
    await settle();
    await sidebarReady();
    ['Skin Type: Oily', 'Skin Type: Dry', 'Hair Type: Curly', 'Gender: Female',
      'Certification: Vegan', 'Brand: Acme', 'Brand: Zen', 'Color: Red', 'Search: rose',
      'Category: Skincare', 'Price: $100 – $500', 'SPF: 30 – 50'].forEach((text) =>
      expect(chip(text)).toBeInTheDocument(),
    );
  });

  it('junk in the URL falls back to defaults instead of breaking', async () => {
    renderCategory({
      entries: ['/category?page=abc&ordering=bogus&page_size=7&min_price=zzz&skin_type=bogus&is_vegan=false'],
    });
    await settle();
    expect(getProducts.mock.calls[0][0]).toEqual({ page: 1, page_size: 12, ordering: '-created_at' });
    expect(box('Oily')).not.toBeChecked();
  });

  it('a page number past the last page falls back to page 1 instead of an error', async () => {
    getProducts.mockImplementation(({ page }) =>
      page > 3
        ? Promise.reject({ response: { status: 404 }, message: 'Invalid page.' })
        : Promise.resolve({ data: { results: [PRODUCT], count: 30, total_pages: 3 } }),
    );
    renderCategory({ entries: ['/category?skin_type=oily&page=99'] });

    await settle();
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
    expect(url().has('page')).toBe(false); // corrected in the address bar
    expect(url().get('skin_type')).toBe('oily'); // filters kept
    expect(lastParams()).toMatchObject({ page: 1, skin_type: 'oily' });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('Category URL sync — changes write the URL', () => {
  it('multi-select skin types become ONE comma-separated param', async () => {
    const { user } = renderCategory();
    await settle();

    await user.click(box('Oily'));
    await user.click(box('Dry'));

    await waitFor(() => expect(url().get('skin_type')).toBe('oily,dry'));
    expect(url().getAll('skin_type')).toHaveLength(1); // not ?skin_type=oily&skin_type=dry
    await waitFor(() => expect(lastParams().skin_type).toBe('oily,dry'));
  });

  it('multi-select brands become one comma-separated param too', async () => {
    const { user } = renderCategory();
    await settle();
    await sidebarReady();
    await user.click(box('Acme'));
    await user.click(box('Zen'));
    await waitFor(() => expect(url().get('brand')).toBe('acme,zen'));
    expect(url().getAll('brand')).toHaveLength(1);
  });

  it('writes each kind of filter under the API\'s own param name', async () => {
    const { user } = renderCategory();
    await settle();
    await sidebarReady();

    await user.click(screen.getByRole('button', { name: 'Skincare' }));
    await user.click(colorBox('Deep Blue'));
    fireEvent.change(priceInputs()[0], { target: { value: '100' } });
    await user.click(box('Curly'));
    await user.click(radio('Male'));
    await user.type(screen.getByLabelText('Minimum SPF'), '15');
    await user.click(screen.getByRole('button', { name: 'Apply SPF range' }));
    await user.click(box('Organic'));
    await user.selectOptions(sortSelect(), '-price');
    await user.selectOptions(pageSizeSelect(), '48');

    await waitFor(() => expect(url().get('page_size')).toBe('48'));
    expect(Object.fromEntries(url())).toEqual({
      category: 'skincare',
      color: 'Deep Blue',
      min_price: '100',
      hair_type: 'curly',
      gender: 'male',
      min_spf: '15',
      is_organic: 'true',
      ordering: '-price',
      page_size: '48',
    });
  });

  it('the request always matches the URL', async () => {
    const { user } = renderCategory();
    await settle();
    await user.click(box('Oily'));
    await user.click(box('Vegan'));
    await waitFor(() => expect(lastParams().is_vegan).toBe('true'));
    expect(lastParams()).toMatchObject({ skin_type: 'oily', is_vegan: 'true' });
    expect(url().get('skin_type')).toBe('oily');
    expect(url().get('is_vegan')).toBe('true');
  });

  it('defaults are not written: undoing a change leaves a clean URL', async () => {
    const { user } = renderCategory();
    await settle();
    await user.click(box('Oily'));
    await user.click(box('Vegan'));
    await user.selectOptions(sortSelect(), 'price');
    await user.selectOptions(pageSizeSelect(), '24');
    await waitFor(() => expect(url().get('page_size')).toBe('24'));

    await user.click(box('Oily'));
    await user.click(box('Vegan'));
    await user.selectOptions(sortSelect(), '-created_at');
    await user.selectOptions(pageSizeSelect(), '12');

    await waitFor(() => expect(locText()).toBe('/category'));
  });

  it('unchecked boxes leave no param behind (never ?is_vegan=false)', async () => {
    const { user } = renderCategory({ entries: ['/category?is_vegan=true&is_organic=true'] });
    await settle();
    await user.click(box('Vegan'));
    await waitFor(() => expect(url().has('is_vegan')).toBe(false));
    expect(url().get('is_organic')).toBe('true');
    expect(locText()).not.toContain('false');
  });

  it('changing any filter goes back to page 1 (page param dropped)', async () => {
    const { user } = renderCategory({ entries: ['/category?page=3&brand=acme'] });
    await settle();
    await user.click(box('Vegan'));
    await waitFor(() => expect(url().get('is_vegan')).toBe('true'));
    expect(url().has('page')).toBe(false);
    expect(url().get('brand')).toBe('acme');
    expect(lastParams().page).toBe(1);
  });

  it('keeps unrelated params (e.g. a campaign tag) untouched', async () => {
    const { user } = renderCategory({ entries: ['/category?utm_source=newsletter'] });
    await settle();
    await user.click(box('Vegan'));
    await waitFor(() => expect(url().get('is_vegan')).toBe('true'));
    expect(url().get('utm_source')).toBe('newsletter');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('Category URL sync — browser history', () => {
  const tickFiveFilters = async (user) => {
    await user.click(box('Oily'));
    await user.click(box('Dry'));
    await user.click(box('Vegan'));
    await user.click(radio('Female'));
    await user.click(box('Curly'));
    await waitFor(() => expect(url().get('hair_type')).toBe('curly'));
  };

  it('filter changes REPLACE the history entry — five ticks do not cost five Backs', async () => {
    const { user } = renderCategory({ entries: ['/', '/category'] });
    await settle();

    await tickFiveFilters(user);
    expect(url().get('skin_type')).toBe('oily,dry');

    await back(user); // ONE back press leaves the listing entirely
    expect(path()).toBe('/');
    expect(screen.getByText('Home page')).toBeInTheDocument();
  });

  it('sort, page size, chips and "Clear all" replace too', async () => {
    const { user } = renderCategory({ entries: ['/', '/category'] });
    await settle();

    await user.selectOptions(sortSelect(), 'price');
    await user.selectOptions(pageSizeSelect(), '24');
    await user.click(box('Oily'));
    await user.click(box('Vegan'));
    await user.click(within(chip('Certification: Vegan')).getByRole('button')); // chip removal
    await user.click(clearAllButton());
    await waitFor(() => expect(url().get('page_size')).toBe('24'));

    await back(user);
    expect(path()).toBe('/');
  });

  it('page changes PUSH an entry: Back returns to the previous page, filters intact', async () => {
    respond(3);
    const { user } = renderCategory({ entries: ['/', '/category?skin_type=oily&is_vegan=true'] });
    await settle();

    await user.click(screen.getByRole('button', { name: '2' }));
    await waitFor(() => expect(url().get('page')).toBe('2'));
    expect(url().get('skin_type')).toBe('oily');

    await back(user);
    expect(path()).toBe('/category'); // still on the listing, not thrown out to '/'
    expect(url().has('page')).toBe(false);
    expect(url().get('skin_type')).toBe('oily');
    expect(url().get('is_vegan')).toBe('true');
    await waitFor(() => expect(lastParams().page).toBe(1));
    expect(box('Oily')).toBeChecked();
    expect(box('Vegan')).toBeChecked();

    await forward(user);
    expect(url().get('page')).toBe('2');
    expect(url().get('skin_type')).toBe('oily');
    await waitFor(() => expect(lastParams().page).toBe(2));
  });

  it('Prev / Next and the page numbers all push', async () => {
    respond(3);
    const { user } = renderCategory({ entries: ['/', '/category'] });
    await settle();
    await user.click(screen.getByRole('button', { name: /next/i }));
    await waitFor(() => expect(url().get('page')).toBe('2'));
    await user.click(screen.getByRole('button', { name: /next/i }));
    await waitFor(() => expect(url().get('page')).toBe('3'));

    await back(user);
    expect(url().get('page')).toBe('2');
    await back(user);
    expect(url().has('page')).toBe(false);
    expect(path()).toBe('/category');
  });

  it('going into a product and pressing Back restores the filtered listing', async () => {
    const { user } = renderCategory({ entries: ['/', '/category'] });
    await settle();
    await sidebarReady();
    await user.click(box('Oily'));
    await user.click(box('Vegan'));
    await user.click(box('Acme'));
    await waitFor(() => expect(url().get('brand')).toBe('acme'));
    const filteredUrl = locText();

    await user.click(screen.getAllByRole('link', { name: /test product/i })[0]);
    expect(await screen.findByText('Product detail page')).toBeInTheDocument();
    expect(path()).toBe('/product/test-product');

    await back(user);

    expect(locText()).toBe(filteredUrl);
    await settle();
    await sidebarReady();
    expect(box('Oily')).toBeChecked();
    expect(box('Vegan')).toBeChecked();
    expect(box('Acme')).toBeChecked();
    expect(lastParams()).toMatchObject({ skin_type: 'oily', is_vegan: 'true', brand: 'acme' });
  });

  it('Back / Forward put every part of the sidebar back, including the search box', async () => {
    const { user } = renderCategory({ entries: ['/category?search=rose'] });
    await settle();
    expect(searchInput()).toHaveValue('rose');
    expect(box('Dry')).not.toBeChecked();

    await user.click(screen.getByRole('button', { name: 'external-nav' })); // ?skin_type=dry&search=lip
    await waitFor(() => expect(searchInput()).toHaveValue('lip'));
    expect(box('Dry')).toBeChecked();
    await waitFor(() => expect(lastParams()).toMatchObject({ search: 'lip', skin_type: 'dry' }));

    await back(user);
    await waitFor(() => expect(searchInput()).toHaveValue('rose'));
    expect(box('Dry')).not.toBeChecked();
    await waitFor(() => expect(lastParams().search).toBe('rose'));
    expect(lastParams()).not.toHaveProperty('skin_type');

    await forward(user);
    await waitFor(() => expect(searchInput()).toHaveValue('lip'));
    expect(box('Dry')).toBeChecked();
  });

  it('the price slider follows the URL on Back', async () => {
    const { user } = renderCategory({ entries: ['/category?min_price=100&max_price=500'] });
    await settle();
    expect(priceInputs()[0]).toHaveValue(100);

    await user.click(screen.getByRole('button', { name: 'external-nav' })); // no price in this URL
    await waitFor(() => expect(priceInputs()[0]).toHaveValue(0));
    expect(priceInputs()[1]).toHaveValue(1000);

    await back(user);
    await waitFor(() => expect(priceInputs()[0]).toHaveValue(100));
    expect(priceInputs()[1]).toHaveValue(500);
  });

  it('a refresh restores the same filters, sidebar and results (state lives in the URL)', async () => {
    const first = renderCategory({ entries: ['/category'] });
    await settle();
    await sidebarReady();
    await first.user.click(box('Oily'));
    await first.user.click(box('Dry'));
    await first.user.click(box('Vegan'));
    await first.user.click(box('Acme'));
    await first.user.selectOptions(sortSelect(), '-price');
    fireEvent.change(priceInputs()[1], { target: { value: '400' } });
    await waitFor(() => expect(url().get('max_price')).toBe('400'));
    await waitFor(() => expect(lastParams().max_price).toBe(400));
    const addressBar = locText();
    const requestBefore = lastParams();

    first.unmount(); // "refresh": throw the whole page away...
    getProducts.mockClear();
    renderCategory({ entries: [addressBar] }); // ...and load whatever is in the address bar
    await settle();
    await sidebarReady();

    expect(getProducts.mock.calls[0][0]).toEqual(requestBefore);
    expect(box('Oily')).toBeChecked();
    expect(box('Dry')).toBeChecked();
    expect(box('Vegan')).toBeChecked();
    expect(box('Acme')).toBeChecked();
    expect(sortSelect()).toHaveValue('-price');
    expect(priceInputs()[1]).toHaveValue(400);
  });

  it('"Show all products" (flash sale) replaces, keeping the other filters', async () => {
    const { user } = renderCategory({ entries: ['/', '/category?flash_sale=7&skin_type=oily'] });
    await settle();
    await user.click(screen.getByRole('button', { name: /show all products/i }));
    await waitFor(() => expect(url().has('flash_sale')).toBe(false));
    expect(url().get('skin_type')).toBe('oily');
    await back(user);
    expect(path()).toBe('/');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('Category URL sync — chips and "Clear all"', () => {
  it('removing a chip removes just that value from the URL', async () => {
    const { user } = renderCategory({ entries: ['/category?skin_type=oily,dry&is_vegan=true'] });
    await settle();
    await user.click(within(chip('Skin Type: Oily')).getByRole('button'));
    await waitFor(() => expect(url().get('skin_type')).toBe('dry'));
    expect(url().get('is_vegan')).toBe('true');
    expect(box('Oily')).not.toBeChecked();
    expect(box('Dry')).toBeChecked();
  });

  it('"Clear All Filters" empties the filter params but keeps flash sale and page size', async () => {
    const { user } = renderCategory({ entries: [FULL_URL] });
    await settle();
    await sidebarReady();

    await user.click(clearAllButton());

    await waitFor(() => expect(Object.fromEntries(url())).toEqual({ flash_sale: '7', page_size: '24' }));
    await waitFor(() =>
      expect(lastParams()).toEqual({ page: 1, page_size: 24, ordering: '-created_at', flash_sale: '7' }),
    );
    expect(box('Oily')).not.toBeChecked();
    expect(box('Acme')).not.toBeChecked();
    expect(searchInput()).toHaveValue('');
    expect(sortSelect()).toHaveValue('-created_at');
    expect(priceInputs()[0]).toHaveValue(0);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('Category URL sync — the search box', () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));

  it('writes the term to the URL after a pause, and fetches once for the final text', async () => {
    const { user } = renderCategory({ fakeTimers: true });
    await settle();
    getProducts.mockClear();

    await user.type(searchInput(), 'rose');
    expect(url().has('search')).toBe(false); // still typing
    expect(getProducts).not.toHaveBeenCalled();

    await advance(450);

    expect(url().get('search')).toBe('rose');
    await waitFor(() => expect(getProducts).toHaveBeenCalledTimes(1));
    expect(lastParams().search).toBe('rose');
  });

  it('is not reset mid-typing when its own URL update arrives', async () => {
    const { user } = renderCategory({ fakeTimers: true });
    await settle();

    await user.type(searchInput(), 'ro');
    await advance(450);
    expect(url().get('search')).toBe('ro');

    await user.type(searchInput(), 'se');
    expect(searchInput()).toHaveValue('rose');
    await advance(450);
    expect(url().get('search')).toBe('rose');
    expect(searchInput()).toHaveValue('rose');
  });

  it('a pending search does not overwrite a filter ticked in the meantime', async () => {
    const { user } = renderCategory({ fakeTimers: true });
    await settle();

    await user.type(searchInput(), 'ro');
    await user.click(box('Vegan')); // before the pause is over
    await advance(450);

    expect(url().get('is_vegan')).toBe('true');
    expect(url().get('search')).toBe('ro');
  });

  it('leaving the page cancels a pending search — it cannot hijack the next page', async () => {
    const { user } = renderCategory({ fakeTimers: true });
    await settle();

    await user.type(searchInput(), 'ro');
    await user.click(screen.getAllByRole('link', { name: /test product/i })[0]);
    expect(await screen.findByText('Product detail page')).toBeInTheDocument();
    await advance(1000);

    expect(locText()).toBe('/product/test-product'); // not "/product/test-product?search=ro"
  });

  it('"Clear all" cancels a pending search', async () => {
    const { user } = renderCategory({ entries: ['/category?is_vegan=true'], fakeTimers: true });
    await settle();

    await user.type(searchInput(), 'abc');
    await user.click(clearAllButton());
    await advance(1000);

    expect(url().has('search')).toBe(false);
    expect(searchInput()).toHaveValue('');
  });

  it('clearing the search chip empties the box', async () => {
    const { user } = renderCategory({ entries: ['/category?search=rose'], fakeTimers: true });
    await settle();
    await user.click(within(chip('Search: rose')).getByRole('button'));
    await waitFor(() => expect(url().has('search')).toBe(false));
    expect(searchInput()).toHaveValue('');
  });

  it('trims the term and drops a blank one from the URL', async () => {
    const { user } = renderCategory({ entries: ['/category?search=rose'], fakeTimers: true });
    await settle();
    await user.clear(searchInput());
    await user.type(searchInput(), '   ');
    await advance(450);
    expect(url().has('search')).toBe(false);

    await user.type(searchInput(), '  lip  ');
    await advance(450);
    expect(url().get('search')).toBe('lip');
  });
});
