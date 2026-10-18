// src/hooks/useDebouncedCallback.js
import { useCallback, useEffect, useRef } from 'react';

/**
 * Debounce a callback: `run(...args)` calls `callback(...args)` once `delay` ms
 * have passed with no further `run` — each `run` restarts the wait.
 *
 * Guarantees that matter when the callback writes to the URL:
 *  - it always calls the LATEST `callback`, not the one from the render that
 *    scheduled it, so it never acts on stale state / a stale copy of the URL;
 *  - nothing fires after the component unmounts (a late navigate() would
 *    otherwise hijack wherever the user went next);
 *  - `cancel()` drops a pending call (e.g. when the thing it would have
 *    committed has been cleared in the meantime).
 *
 * @returns {[run: Function, cancel: Function]} both are stable identities
 */
export function useDebouncedCallback(callback, delay) {
  const timer = useRef(null);
  const latest = useRef(callback);

  useEffect(() => {
    latest.current = callback;
  }, [callback]);

  const cancel = useCallback(() => clearTimeout(timer.current), []);

  const run = useCallback(
    (...args) => {
      clearTimeout(timer.current);
      timer.current = setTimeout(() => latest.current(...args), delay);
    },
    [delay],
  );

  useEffect(() => cancel, [cancel]);

  return [run, cancel];
}
