import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDebouncedCallback } from '../hooks/useDebouncedCallback';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

const advance = (ms) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

describe('useDebouncedCallback', () => {
  it('calls the callback once after the delay, with the arguments', async () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(cb, 400));
    result.current[0]('rose', 2);

    await advance(399);
    expect(cb).not.toHaveBeenCalled();
    await advance(1);
    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith('rose', 2);
  });

  it('each call restarts the wait; only the last call fires', async () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(cb, 400));
    const run = result.current[0];

    run('r'); await advance(300);
    run('ro'); await advance(300);
    run('ros'); await advance(300);
    expect(cb).not.toHaveBeenCalled();

    await advance(100);
    expect(cb).toHaveBeenCalledTimes(1);
    expect(cb).toHaveBeenCalledWith('ros');
  });

  it('cancel() drops the pending call', async () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(cb, 400));
    result.current[0]('x');
    result.current[1]();
    await advance(1000);
    expect(cb).not.toHaveBeenCalled();
  });

  it('cancel() with nothing pending is harmless', () => {
    const { result } = renderHook(() => useDebouncedCallback(vi.fn(), 400));
    expect(() => result.current[1]()).not.toThrow();
  });

  it('can be used again after firing or cancelling', async () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useDebouncedCallback(cb, 100));
    result.current[0]('a'); await advance(100);
    result.current[0]('b'); result.current[1]();
    result.current[0]('c'); await advance(100);
    expect(cb.mock.calls).toEqual([['a'], ['c']]);
  });

  it('calls the LATEST callback, not the one from when it was scheduled', async () => {
    const first = vi.fn();
    const second = vi.fn();
    const { result, rerender } = renderHook(({ cb }) => useDebouncedCallback(cb, 400), {
      initialProps: { cb: first },
    });
    result.current[0]('go');
    rerender({ cb: second }); // e.g. the page re-rendered with a newer URL meanwhile
    await advance(400);
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledWith('go');
  });

  it('never fires after unmount', async () => {
    const cb = vi.fn();
    const { result, unmount } = renderHook(() => useDebouncedCallback(cb, 400));
    result.current[0]('late');
    unmount();
    await advance(1000);
    expect(cb).not.toHaveBeenCalled();
  });

  it('run and cancel keep a stable identity across renders', () => {
    const { result, rerender } = renderHook(({ cb }) => useDebouncedCallback(cb, 400), {
      initialProps: { cb: () => {} },
    });
    const [run, cancel] = result.current;
    rerender({ cb: () => {} });
    expect(result.current[0]).toBe(run);
    expect(result.current[1]).toBe(cancel);
  });
});
