import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useFacetCounts, FACET_COUNTS_DEBOUNCE_MS } from '../hooks/useFacetCounts';
import { getProductFacetCounts } from '../services/api';

vi.mock('../services/api', () => ({ getProductFacetCounts: vi.fn() }));

const COUNTS = { skin_type: { oily: 12, dry: 3 }, gender: { female: 4 }, is_vegan: 5 };

beforeEach(() => {
  vi.clearAllMocks();
  getProductFacetCounts.mockResolvedValue({ data: COUNTS });
});
afterEach(() => {
  vi.useRealTimers();
});

describe('useFacetCounts — fetching', () => {
  it('is null until the first response, then returns the counts', async () => {
    const { result } = renderHook(() => useFacetCounts({ search: 'rose' }));
    expect(result.current).toBeNull();
    await waitFor(() => expect(result.current).toEqual(COUNTS));
  });

  it('sends the filter params and an abort signal', async () => {
    renderHook(() => useFacetCounts({ search: 'rose', skin_type: 'oily,dry', min_spf: 30 }));
    await waitFor(() => expect(getProductFacetCounts).toHaveBeenCalledTimes(1));
    const [params, config] = getProductFacetCounts.mock.calls[0];
    expect(params).toEqual({ search: 'rose', skin_type: 'oily,dry', min_spf: 30 });
    expect(config.signal).toBeInstanceOf(AbortSignal);
  });

  it('fetches immediately the first time (no debounce delay on page load)', async () => {
    vi.useFakeTimers();
    renderHook(() => useFacetCounts({ search: 'rose' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(getProductFacetCounts).toHaveBeenCalledTimes(1);
  });

  it('works with no filters at all (an empty params object)', async () => {
    const { result } = renderHook(() => useFacetCounts({}));
    await waitFor(() => expect(result.current).toEqual(COUNTS));
    expect(getProductFacetCounts.mock.calls[0][0]).toEqual({});
  });

  it('does not fetch when params is null (disabled)', async () => {
    renderHook(() => useFacetCounts(null));
    await act(async () => { await new Promise((r) => setTimeout(r, 30)); });
    expect(getProductFacetCounts).not.toHaveBeenCalled();
  });
});

describe('useFacetCounts — when filters change', () => {
  it('refetches after the debounce delay', async () => {
    vi.useFakeTimers();
    const { rerender } = renderHook(({ p }) => useFacetCounts(p), {
      initialProps: { p: { gender: 'female' } },
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(getProductFacetCounts).toHaveBeenCalledTimes(1);

    rerender({ p: { gender: 'male' } });
    await act(async () => { await vi.advanceTimersByTimeAsync(FACET_COUNTS_DEBOUNCE_MS - 50); });
    expect(getProductFacetCounts).toHaveBeenCalledTimes(1); // still waiting

    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    expect(getProductFacetCounts).toHaveBeenCalledTimes(2);
    expect(getProductFacetCounts.mock.calls[1][0]).toEqual({ gender: 'male' });
  });

  it('a burst of changes makes ONE request, for the final filters', async () => {
    vi.useFakeTimers();
    const { rerender } = renderHook(({ p }) => useFacetCounts(p), {
      initialProps: { p: { search: 'r' } },
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(getProductFacetCounts).toHaveBeenCalledTimes(1);

    for (const term of ['ro', 'ros', 'rose']) {
      rerender({ p: { search: term } });
      await act(async () => { await vi.advanceTimersByTimeAsync(100); }); // typing speed
    }
    await act(async () => { await vi.advanceTimersByTimeAsync(FACET_COUNTS_DEBOUNCE_MS); });

    expect(getProductFacetCounts).toHaveBeenCalledTimes(2);
    expect(getProductFacetCounts.mock.calls[1][0]).toEqual({ search: 'rose' });
  });

  it('a new but equal params object does not refetch', async () => {
    vi.useFakeTimers();
    const { rerender } = renderHook(({ p }) => useFacetCounts(p), {
      initialProps: { p: { gender: 'female', skin_type: 'oily' } },
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    rerender({ p: { gender: 'female', skin_type: 'oily' } });
    rerender({ p: { skin_type: 'oily', gender: 'female' } }); // key order differs too
    await act(async () => { await vi.advanceTimersByTimeAsync(FACET_COUNTS_DEBOUNCE_MS * 2); });

    expect(getProductFacetCounts).toHaveBeenCalledTimes(1);
  });

  it('keeps showing the previous counts while the next ones load', async () => {
    let resolveSecond;
    getProductFacetCounts
      .mockResolvedValueOnce({ data: COUNTS })
      .mockImplementationOnce(() => new Promise((r) => { resolveSecond = r; }));

    const { result, rerender } = renderHook(({ p }) => useFacetCounts(p, { delay: 10 }), {
      initialProps: { p: { gender: 'female' } },
    });
    await waitFor(() => expect(result.current).toEqual(COUNTS));

    rerender({ p: { gender: 'male' } });
    await waitFor(() => expect(getProductFacetCounts).toHaveBeenCalledTimes(2));
    expect(result.current).toEqual(COUNTS); // not blanked while loading

    const next = { ...COUNTS, is_vegan: 99 };
    await act(async () => { resolveSecond({ data: next }); });
    expect(result.current).toEqual(next);
  });

  it('aborts a superseded request and ignores its late response', async () => {
    let resolveFirst;
    getProductFacetCounts
      .mockImplementationOnce(() => new Promise((r) => { resolveFirst = r; }))
      .mockResolvedValueOnce({ data: { ...COUNTS, is_vegan: 2 } });

    const { result, rerender } = renderHook(({ p }) => useFacetCounts(p, { delay: 10 }), {
      initialProps: { p: { gender: 'female' } },
    });
    await waitFor(() => expect(getProductFacetCounts).toHaveBeenCalledTimes(1));
    const firstSignal = getProductFacetCounts.mock.calls[0][1].signal;

    rerender({ p: { gender: 'male' } });
    await waitFor(() => expect(result.current?.is_vegan).toBe(2));
    expect(firstSignal.aborted).toBe(true);

    await act(async () => { resolveFirst({ data: { ...COUNTS, is_vegan: 777 } }); });
    expect(result.current.is_vegan).toBe(2); // the stale answer did not overwrite it
  });

  it('does not request again on unmount, and aborts anything in flight', async () => {
    let signal;
    getProductFacetCounts.mockImplementationOnce((_p, cfg) => {
      signal = cfg.signal;
      return new Promise(() => {});
    });
    const { unmount } = renderHook(() => useFacetCounts({ gender: 'female' }));
    await waitFor(() => expect(getProductFacetCounts).toHaveBeenCalledTimes(1));
    unmount();
    expect(signal.aborted).toBe(true);
  });
});

describe('useFacetCounts — failure is harmless', () => {
  it('returns null when the request fails', async () => {
    getProductFacetCounts.mockRejectedValue(new Error('500'));
    const { result } = renderHook(() => useFacetCounts({ gender: 'female' }));
    await waitFor(() => expect(getProductFacetCounts).toHaveBeenCalled());
    await act(async () => {});
    expect(result.current).toBeNull();
  });

  it('drops stale counts rather than show wrong numbers if a later request fails', async () => {
    getProductFacetCounts
      .mockResolvedValueOnce({ data: COUNTS })
      .mockRejectedValueOnce(new Error('429'));
    const { result, rerender } = renderHook(({ p }) => useFacetCounts(p, { delay: 10 }), {
      initialProps: { p: { gender: 'female' } },
    });
    await waitFor(() => expect(result.current).toEqual(COUNTS));

    rerender({ p: { gender: 'male' } });
    await waitFor(() => expect(result.current).toBeNull());
  });

  it('returns null for an empty body', async () => {
    getProductFacetCounts.mockResolvedValue({ data: undefined });
    const { result } = renderHook(() => useFacetCounts({}));
    await waitFor(() => expect(getProductFacetCounts).toHaveBeenCalled());
    expect(result.current).toBeNull();
  });

  it('does not throw if the API function is missing or throws synchronously', async () => {
    getProductFacetCounts.mockImplementation(() => { throw new Error('boom'); });
    const { result } = renderHook(() => useFacetCounts({}));
    await waitFor(() => expect(getProductFacetCounts).toHaveBeenCalled());
    await act(async () => {});
    expect(result.current).toBeNull();
  });
});
