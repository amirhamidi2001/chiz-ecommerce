import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import SearchBox from '../components/SearchBox';
import { getProductSuggestions } from '../services/api';
import { formatToman } from '../utils/money';

vi.mock('../services/api', () => ({ getProductSuggestions: vi.fn() }));

// ─── Helpers ──────────────────────────────────────────────────────────────────
const makeProduct = (n, overrides = {}) => ({
  id: n,
  name: `Product ${n}`,
  slug: `product-${n}`,
  price: 125_000,
  thumbnail_url: `http://api.test/media/p${n}.jpg`,
  ...overrides,
});

const respondWith = (data) => getProductSuggestions.mockResolvedValue({ data });

/** Shows where the router currently is, so navigation can be asserted. */
const LocationProbe = () => {
  const { pathname, search } = useLocation();
  return <div data-testid="location">{pathname + search}</div>;
};

const renderBox = (props = {}) => {
  // shouldAdvanceTime lets userEvent's internal awaits proceed under fake timers.
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="*" element={<><SearchBox {...props} /><LocationProbe /></>} />
      </Routes>
    </MemoryRouter>,
  );
  return { user };
};

const box = () => screen.getByLabelText('Search products');
const listbox = () => screen.queryByRole('listbox');

/** Let the debounce elapse and the mocked request settle. */
const flushDebounce = async (ms = 300) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
};

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  getProductSuggestions.mockReset();
  respondWith([]);
});
afterEach(() => {
  vi.useRealTimers();
});

// ═════════════════════════════════════════════════════════════════════════════
// Debouncing
// ═════════════════════════════════════════════════════════════════════════════
describe('SearchBox — debounce', () => {
  it('does not fire a request until ~300ms after the last keystroke', async () => {
    const { user } = renderBox();
    await user.type(box(), 'lipstick');

    expect(getProductSuggestions).not.toHaveBeenCalled();

    // Margins are generous on purpose: shouldAdvanceTime lets a few real
    // milliseconds leak into the fake clock, so exact-boundary asserts flake.
    await flushDebounce(200);
    expect(getProductSuggestions).not.toHaveBeenCalled();

    await flushDebounce(150);
    expect(getProductSuggestions).toHaveBeenCalledTimes(1);
    expect(getProductSuggestions).toHaveBeenCalledWith('lipstick', expect.any(Object));
  });

  it('coalesces a burst of keystrokes into ONE request with the final text', async () => {
    const { user } = renderBox();
    // Each keystroke lands < 300ms after the previous one.
    for (const ch of 'lips') {
      await user.type(box(), ch);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });
    }
    expect(getProductSuggestions).not.toHaveBeenCalled();

    await flushDebounce(300);
    expect(getProductSuggestions).toHaveBeenCalledTimes(1);
    expect(getProductSuggestions.mock.calls[0][0]).toBe('lips');
  });

  it('does not request anything for fewer than 2 characters', async () => {
    const { user } = renderBox();
    await user.type(box(), 'l');
    await flushDebounce(1000);
    expect(getProductSuggestions).not.toHaveBeenCalled();
    expect(listbox()).not.toBeInTheDocument();
  });

  it('ignores surrounding whitespace when measuring and sending the term', async () => {
    const { user } = renderBox();
    await user.type(box(), '  li  ');
    await flushDebounce();
    expect(getProductSuggestions).toHaveBeenCalledWith('li', expect.any(Object));
  });

  it('aborts a superseded in-flight request and ignores its late response', async () => {
    let resolveFirst;
    getProductSuggestions
      .mockImplementationOnce(
        () => new Promise((r) => { resolveFirst = r; }),
      )
      .mockResolvedValueOnce({ data: [makeProduct(2, { name: 'Second Result' })] });

    const { user } = renderBox();
    await user.type(box(), 'ro');
    await flushDebounce();
    const firstSignal = getProductSuggestions.mock.calls[0][1].signal;
    expect(firstSignal.aborted).toBe(false);

    await user.type(box(), 'se');
    await flushDebounce();
    expect(firstSignal.aborted).toBe(true);

    // The first request "finishes" late, after being superseded.
    await act(async () => {
      resolveFirst({ data: [makeProduct(1, { name: 'Stale Result' })] });
    });

    expect(screen.getByText('Second Result')).toBeInTheDocument();
    expect(screen.queryByText('Stale Result')).not.toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Rendering suggestions
// ═════════════════════════════════════════════════════════════════════════════
describe('SearchBox — suggestions', () => {
  it('renders name, price and thumbnail for each suggestion', async () => {
    respondWith([
      makeProduct(1, { name: 'Matte Lipstick', price: 125_000 }),
      makeProduct(2, { name: 'Lip Gloss', price: 80_000 }),
    ]);
    const { user } = renderBox();
    await user.type(box(), 'lip');
    await flushDebounce();

    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(2);
    expect(screen.getByText('Matte Lipstick')).toBeInTheDocument();
    expect(screen.getByText(formatToman(125_000))).toBeInTheDocument();
    expect(screen.getByText(formatToman(80_000))).toBeInTheDocument();
    const img = options[0].querySelector('img');
    expect(img).toHaveAttribute('src', 'http://api.test/media/p1.jpg');
  });

  it('falls back to a placeholder image when thumbnail_url is null', async () => {
    respondWith([makeProduct(1, { thumbnail_url: null })]);
    const { user } = renderBox();
    await user.type(box(), 'pr');
    await flushDebounce();
    expect(screen.getByRole('option').querySelector('img').getAttribute('src')).toMatch(
      /product-1\.webp$/,
    );
  });

  it('shows at most 8 suggestions', async () => {
    respondWith(Array.from({ length: 12 }, (_, i) => makeProduct(i + 1)));
    const { user } = renderBox();
    await user.type(box(), 'pr');
    await flushDebounce();
    expect(screen.getAllByRole('option')).toHaveLength(8);
  });

  it('links each suggestion to its product detail page', async () => {
    respondWith([makeProduct(7, { name: 'Matte Lipstick', slug: 'matte-lipstick' })]);
    const { user } = renderBox();
    await user.type(box(), 'ma');
    await flushDebounce();
    expect(screen.getByRole('link', { name: /matte lipstick/i })).toHaveAttribute(
      'href',
      '/product/matte-lipstick',
    );
  });

  it('navigates to the product and closes the dropdown when one is clicked', async () => {
    respondWith([makeProduct(7, { name: 'Matte Lipstick', slug: 'matte-lipstick' })]);
    const { user } = renderBox();
    await user.type(box(), 'ma');
    await flushDebounce();

    await user.click(screen.getByRole('link', { name: /matte lipstick/i }));

    expect(screen.getByTestId('location')).toHaveTextContent('/product/matte-lipstick');
    expect(listbox()).not.toBeInTheDocument();
    expect(box()).toHaveValue('');
  });

  it('has a "See all results" link carrying the typed term to /search', async () => {
    respondWith([makeProduct(1)]);
    const { user } = renderBox();
    await user.type(box(), 'matte lip');
    await flushDebounce();

    await user.click(screen.getByRole('button', { name: /see all results for/i }));

    expect(screen.getByTestId('location')).toHaveTextContent('/search?q=matte%20lip');
  });

  it('"See all results" echoes the typed term', async () => {
    respondWith([makeProduct(1)]);
    const { user } = renderBox();
    await user.type(box(), 'matte');
    await flushDebounce();
    expect(
      screen.getByRole('button', { name: /see all results for .matte./i }),
    ).toBeInTheDocument();
  });

  it('uses the onSubmit prop (mobile) instead of navigating when provided', async () => {
    const onSubmit = vi.fn();
    respondWith([makeProduct(1)]);
    const { user } = renderBox({ onSubmit });
    await user.type(box(), 'matte');
    await flushDebounce();
    await user.click(screen.getByRole('button', { name: /see all results for/i }));
    expect(onSubmit).toHaveBeenCalledWith('matte');
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/);
  });

  it('supports arrow-key selection and Enter to open the highlighted product', async () => {
    respondWith([
      makeProduct(1, { slug: 'first' }),
      makeProduct(2, { slug: 'second' }),
    ]);
    const { user } = renderBox();
    await user.type(box(), 'pr');
    await flushDebounce();

    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}');

    expect(screen.getByTestId('location')).toHaveTextContent('/product/second');
  });

  it('submits the full search on Enter when nothing is highlighted', async () => {
    respondWith([makeProduct(1)]);
    const { user } = renderBox();
    await user.type(box(), 'serum');
    await flushDebounce();
    await user.keyboard('{Enter}');
    expect(screen.getByTestId('location')).toHaveTextContent('/search?q=serum');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Empty / error states
// ═════════════════════════════════════════════════════════════════════════════
describe('SearchBox — empty and error states', () => {
  it('shows a "No results" message instead of an empty dropdown shell', async () => {
    respondWith([]);
    const { user } = renderBox();
    await user.type(box(), 'zzzz');
    await flushDebounce();

    expect(screen.getByText(/no results found/i)).toBeInTheDocument();
    expect(screen.queryAllByRole('option')).toHaveLength(0);
    expect(
      screen.queryByRole('button', { name: /see all results/i }),
    ).not.toBeInTheDocument();
  });

  it('closes quietly (no crash, no dropdown) when the request fails', async () => {
    getProductSuggestions.mockRejectedValue(new Error('429'));
    const { user } = renderBox();
    await user.type(box(), 'lip');
    await flushDebounce();
    expect(listbox()).not.toBeInTheDocument();
    expect(box()).toBeInTheDocument();
  });

  it('shows a spinner while a request is in flight and clears it if the box is emptied', async () => {
    getProductSuggestions.mockImplementation(() => new Promise(() => {})); // never settles
    const { user } = renderBox();
    await user.type(box(), 'lip');
    await flushDebounce();
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();

    // Emptying the box aborts the in-flight request; the spinner must not
    // be left spinning for a request nobody is waiting for any more.
    await user.clear(box());
    await flushDebounce();

    expect(document.querySelector('.animate-spin')).not.toBeInTheDocument();
  });

  it('closes the dropdown again when the text is cleared below 2 characters', async () => {
    respondWith([makeProduct(1)]);
    const { user } = renderBox();
    await user.type(box(), 'lip');
    await flushDebounce();
    expect(listbox()).toBeInTheDocument();

    await user.clear(box());
    await flushDebounce();
    expect(listbox()).not.toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Closing
// ═════════════════════════════════════════════════════════════════════════════
describe('SearchBox — closing', () => {
  it('closes on a click outside the search box', async () => {
    respondWith([makeProduct(1)]);
    const { user } = renderBox();
    await user.type(box(), 'lip');
    await flushDebounce();
    expect(listbox()).toBeInTheDocument();

    fireEvent.mouseDown(document.body);

    expect(listbox()).not.toBeInTheDocument();
  });

  it('stays open on a click inside the dropdown area', async () => {
    respondWith([makeProduct(1)]);
    const { user } = renderBox();
    await user.type(box(), 'lip');
    await flushDebounce();

    fireEvent.mouseDown(listbox());

    expect(listbox()).toBeInTheDocument();
  });

  it('closes on Escape', async () => {
    respondWith([makeProduct(1)]);
    const { user } = renderBox();
    await user.type(box(), 'lip');
    await flushDebounce();
    expect(listbox()).toBeInTheDocument();

    await user.keyboard('{Escape}');

    expect(listbox()).not.toBeInTheDocument();
  });

  it('closes on Escape even when showing the empty state', async () => {
    respondWith([]);
    const { user } = renderBox();
    await user.type(box(), 'zzzz');
    await flushDebounce();
    expect(screen.getByText(/no results found/i)).toBeInTheDocument();

    await user.keyboard('{Escape}');

    expect(listbox()).not.toBeInTheDocument();
  });

  it('reopens on focus when there is a live query', async () => {
    respondWith([makeProduct(1)]);
    const { user } = renderBox();
    await user.type(box(), 'lip');
    await flushDebounce();
    fireEvent.mouseDown(document.body);
    expect(listbox()).not.toBeInTheDocument();

    act(() => box().blur());
    await user.click(box());

    expect(listbox()).toBeInTheDocument();
  });
});
