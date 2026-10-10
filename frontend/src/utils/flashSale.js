// src/utils/flashSale.js
import { useEffect, useRef, useState } from 'react';

/** True when the product is currently on a flash sale AND has a price to show. */
export const isOnFlashSale = (product) =>
  Boolean(product?.is_on_flash_sale && product.flash_sale_price != null);

/** Whole seconds left, rounded UP so "00:00:00" coincides with the moment of expiry. */
const secondsLeft = (ms) => Math.ceil(ms / 1000);

/** "03:04:05", or "2d 03:04:05" once more than a day remains. */
export const formatRemaining = (ms) => {
  const total = Math.max(0, secondsLeft(ms));
  const days = Math.floor(total / 86400);
  const hh = String(Math.floor((total % 86400) / 3600)).padStart(2, '0');
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, '0');
  const ss = String(total % 60).padStart(2, '0');
  return `${days > 0 ? `${days}d ` : ''}${hh}:${mm}:${ss}`;
};

/**
 * Milliseconds until `endsAt`, ticking every second.
 *
 * Remaining time is recomputed from the clock on every tick rather than
 * decremented, so a throttled background tab (browsers slow timers there)
 * snaps to the right value instead of drifting. The interval is cleared when
 * the component unmounts or `endsAt` changes, and `onExpire` fires exactly
 * once, when time runs out.
 */
export const useRemaining = (endsAt, onExpire) => {
  const endMs = new Date(endsAt).getTime();
  const [remaining, setRemaining] = useState(() => Math.max(0, endMs - Date.now()));

  // Always call the latest onExpire without restarting the interval.
  const onExpireRef = useRef(onExpire);
  useEffect(() => {
    onExpireRef.current = onExpire;
  });

  useEffect(() => {
    const id = setInterval(() => {
      const left = Math.max(0, endMs - Date.now());
      setRemaining(left);
      if (left === 0) {
        clearInterval(id);
        onExpireRef.current?.();
      }
    }, 1000);
    return () => clearInterval(id);
  }, [endMs]);

  return remaining;
};
