import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import FlashSaleBanner from '../components/FlashSaleBanner';

vi.mock('../services/api', () => ({
  getActiveFlashSales: vi.fn(),
}));
import { getActiveFlashSales } from '../services/api';

// ─── Fixtures ─────────────────────────────────────────────────────────────────
const NOW = new Date('2030-01-01T12:00:00Z');
const HOUR = 3600 * 1000;

const makeSale = (overrides = {}) => ({
  id: 7,
  name: 'Weekend Flash Sale',
  discount_percent: '25.00',
  starts_at: new Date(NOW.getTime() - HOUR).toISOString(),
  ends_at: new Date(NOW.getTime() + HOUR).toISOString(), // 1h from NOW
  product_count: 3,
  products: [],
  ...overrides,
});

const respond = (sales) => getActiveFlashSales.mockResolvedValue({ data: sales });

/** Mount and let the initial fetch (a resolved promise) settle. */
const mountBanner = async () => {
  const utils = render(
    <MemoryRouter>
      <FlashSaleBanner />
    </MemoryRouter>,
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
  return utils;
};

/** Advance fake time (and the clock with it), flushing React/promise work. */
const tick = (ms) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });

const timer = () => screen.getByRole('timer');

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ═════════════════════════════════════════════════════════════════════════════
// Rendering
// ═════════════════════════════════════════════════════════════════════════════
describe('FlashSaleBanner — rendering', () => {
  it('renders the sale name, discount, countdown and a link to its products', async () => {
    respond([makeSale()]);
    await mountBanner();

    expect(screen.getByRole('region', { name: /flash sale/i })).toBeInTheDocument();
    expect(screen.getByText('Weekend Flash Sale')).toBeInTheDocument();
    expect(screen.getByText(/up to 25% off/i)).toBeInTheDocument();
    expect(timer()).toHaveTextContent('01:00:00');
    expect(screen.getByRole('link', { name: /shop the sale/i })).toHaveAttribute(
      'href',
      '/category?flash_sale=7',
    );
  });

  it('formats fractional discounts without trailing zeros', async () => {
    respond([makeSale({ discount_percent: '12.50' })]);
    await mountBanner();
    expect(screen.getByText(/up to 12\.5% off/i)).toBeInTheDocument();
  });

  it('shows days when more than a day remains', async () => {
    const ends = NOW.getTime() + (2 * 86400 + 3 * 3600 + 4 * 60 + 5) * 1000;
    respond([makeSale({ ends_at: new Date(ends).toISOString() })]);
    await mountBanner();
    expect(timer()).toHaveTextContent('2d 03:04:05');
  });

  it('accepts a paginated-style response as well as a bare array', async () => {
    getActiveFlashSales.mockResolvedValue({ data: { results: [makeSale()] } });
    await mountBanner();
    expect(screen.getByText('Weekend Flash Sale')).toBeInTheDocument();
  });

  it('shows the soonest-ending sale when several are running', async () => {
    respond([
      makeSale({ id: 1, name: 'Later', ends_at: new Date(NOW.getTime() + 5 * HOUR).toISOString() }),
      makeSale({ id: 2, name: 'Sooner', ends_at: new Date(NOW.getTime() + HOUR).toISOString() }),
    ]);
    await mountBanner();
    expect(screen.getByText('Sooner')).toBeInTheDocument();
    expect(screen.queryByText('Later')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /shop the sale/i })).toHaveAttribute(
      'href',
      '/category?flash_sale=2',
    );
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// No active sale
// ═════════════════════════════════════════════════════════════════════════════
describe('FlashSaleBanner — no active sale', () => {
  it('renders nothing at all (no empty shell) when there are no sales', async () => {
    respond([]);
    const { container } = await mountBanner();
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole('region')).not.toBeInTheDocument();
    expect(screen.queryByRole('timer')).not.toBeInTheDocument();
  });

  it('renders nothing when the request fails', async () => {
    getActiveFlashSales.mockRejectedValue(new Error('network'));
    const { container } = await mountBanner();
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing while the first request is still pending', () => {
    getActiveFlashSales.mockReturnValue(new Promise(() => {}));
    const { container } = render(
      <MemoryRouter>
        <FlashSaleBanner />
      </MemoryRouter>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('ignores a sale this browser’s clock already considers over', async () => {
    respond([makeSale({ ends_at: new Date(NOW.getTime() - 1000).toISOString() })]);
    const { container } = await mountBanner();
    expect(container).toBeEmptyDOMElement();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Countdown
// ═════════════════════════════════════════════════════════════════════════════
describe('FlashSaleBanner — countdown', () => {
  it('decrements once per second', async () => {
    respond([makeSale()]);
    await mountBanner();
    expect(timer()).toHaveTextContent('01:00:00');

    await tick(1000);
    expect(timer()).toHaveTextContent('00:59:59');

    await tick(1000);
    expect(timer()).toHaveTextContent('00:59:58');

    await tick(58 * 1000);
    expect(timer()).toHaveTextContent('00:59:00');
  });

  it('carries across minute and hour boundaries correctly', async () => {
    respond([makeSale({ ends_at: new Date(NOW.getTime() + 61 * 1000).toISOString() })]);
    await mountBanner();
    expect(timer()).toHaveTextContent('00:01:01');

    await tick(2000);
    expect(timer()).toHaveTextContent('00:00:59');
  });

  it('resyncs to the real clock after a stalled tab instead of drifting', async () => {
    respond([makeSale()]);
    await mountBanner();

    // A background tab can go minutes without firing timers; the clock still moves.
    vi.setSystemTime(new Date(NOW.getTime() + 10 * 60 * 1000));
    await tick(1000);

    expect(timer()).toHaveTextContent('00:49:59'); // 1h - 10min - 1s
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Unmount: no lingering timers, no work after unmount
// ═════════════════════════════════════════════════════════════════════════════
describe('FlashSaleBanner — cleanup on unmount', () => {
  it('clears the countdown interval so no timer lingers', async () => {
    respond([makeSale()]);
    const { unmount } = await mountBanner();
    expect(vi.getTimerCount()).toBe(1); // the 1s interval

    unmount();

    expect(vi.getTimerCount()).toBe(0);
  });

  it('does nothing — no errors, no re-fetch — if time passes after unmount', async () => {
    respond([makeSale({ ends_at: new Date(NOW.getTime() + 2000).toISOString() })]);
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { unmount } = await mountBanner();
    expect(getActiveFlashSales).toHaveBeenCalledTimes(1);

    unmount();
    await tick(10_000); // well past the sale's end

    expect(consoleError).not.toHaveBeenCalled();
    expect(getActiveFlashSales).toHaveBeenCalledTimes(1); // expiry never fired
  });

  it('ignores a response that arrives after unmount', async () => {
    let resolveFetch;
    getActiveFlashSales.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { unmount, container } = render(
      <MemoryRouter>
        <FlashSaleBanner />
      </MemoryRouter>,
    );

    unmount();
    await act(async () => {
      resolveFetch({ data: [makeSale()] });
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(container).toBeEmptyDOMElement();
    expect(vi.getTimerCount()).toBe(0); // never started a countdown
    expect(consoleError).not.toHaveBeenCalled();
  });

  it('does not leave the old interval running when a different sale takes over', async () => {
    getActiveFlashSales
      .mockResolvedValueOnce({
        data: [makeSale({ id: 1, name: 'First', ends_at: new Date(NOW.getTime() + 2000).toISOString() })],
      })
      .mockResolvedValueOnce({
        data: [makeSale({ id: 2, name: 'Second', ends_at: new Date(NOW.getTime() + HOUR).toISOString() })],
      });
    await mountBanner();

    await tick(2000); // First ends, Second is fetched

    expect(screen.getByText('Second')).toBeInTheDocument();
    expect(vi.getTimerCount()).toBe(1); // exactly one live interval
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// A sale ending while the page is open
// ═════════════════════════════════════════════════════════════════════════════
describe('FlashSaleBanner — sale ends while viewing', () => {
  const endsInTwoSeconds = () =>
    makeSale({ ends_at: new Date(NOW.getTime() + 2000).toISOString() });

  it('disappears when the countdown reaches zero instead of freezing at 00:00:00', async () => {
    getActiveFlashSales
      .mockResolvedValueOnce({ data: [endsInTwoSeconds()] })
      .mockResolvedValueOnce({ data: [] });
    const { container } = await mountBanner();
    expect(timer()).toHaveTextContent('00:00:02');

    await tick(1000);
    expect(timer()).toHaveTextContent('00:00:01');
    await tick(1000);

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText('00:00:00')).not.toBeInTheDocument();
  });

  it('hides immediately at zero even while the re-fetch is still in flight', async () => {
    let resolveRefetch;
    getActiveFlashSales
      .mockResolvedValueOnce({ data: [endsInTwoSeconds()] })
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveRefetch = resolve;
        }),
      );
    const { container } = await mountBanner();

    await tick(2000); // countdown hits zero; the re-fetch has NOT resolved

    // Not frozen at 00:00:00 while we wait on the network.
    expect(container).toBeEmptyDOMElement();

    // ...and a newly running sale still appears once the answer arrives.
    await act(async () => {
      resolveRefetch({
        data: [makeSale({ id: 9, name: 'Next Sale', ends_at: new Date(NOW.getTime() + HOUR).toISOString() })],
      });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText('Next Sale')).toBeInTheDocument();
  });

  it('re-fetches once to look for a newly running sale and shows it', async () => {
    getActiveFlashSales
      .mockResolvedValueOnce({ data: [endsInTwoSeconds()] })
      .mockResolvedValueOnce({
        data: [makeSale({ id: 9, name: 'Next Sale', ends_at: new Date(NOW.getTime() + HOUR).toISOString() })],
      });
    await mountBanner();

    await tick(2000);

    expect(getActiveFlashSales).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('Weekend Flash Sale')).not.toBeInTheDocument();
    expect(screen.getByText('Next Sale')).toBeInTheDocument();
    // The new sale ends at NOW+1h; two seconds of fake time have passed.
    expect(timer()).toHaveTextContent('00:59:58');
  });

  it('does not loop on re-fetches if the server still lists the finished sale (clock skew)', async () => {
    // The server still reports the sale as running, but this browser's clock says it's over.
    getActiveFlashSales.mockResolvedValue({ data: [endsInTwoSeconds()] });
    const { container } = await mountBanner();

    await tick(2000);
    expect(getActiveFlashSales).toHaveBeenCalledTimes(2);
    expect(container).toBeEmptyDOMElement();

    await tick(30_000);
    expect(getActiveFlashSales).toHaveBeenCalledTimes(2); // no further polling
    expect(vi.getTimerCount()).toBe(0);
  });

  it('stays hidden if the re-fetch fails', async () => {
    getActiveFlashSales
      .mockResolvedValueOnce({ data: [endsInTwoSeconds()] })
      .mockRejectedValueOnce(new Error('offline'));
    const { container } = await mountBanner();

    await tick(2000);

    expect(container).toBeEmptyDOMElement();
  });
});
