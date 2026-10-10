// src/components/FlashSaleBanner.jsx
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getActiveFlashSales } from '../services/api';
import { formatRemaining, useRemaining } from '../utils/flashSale';

// ─── Banner ───────────────────────────────────────────────────────────────────

const percent = (v) => String(parseFloat(v));

const SaleBanner = ({ sale, onExpire }) => {
  const remaining = useRemaining(sale.ends_at, onExpire);
  return (
    <section
      aria-label="Flash sale"
      className="bg-gradient-to-r from-red-600 to-pink-600 text-white"
    >
      <div className="container mx-auto px-4 py-3 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm">
        <p className="flex items-center gap-2">
          <i className="bi bi-lightning-charge-fill text-yellow-300" aria-hidden="true"></i>
          <strong className="font-bold">{sale.name}</strong>
          <span className="opacity-90">· up to {percent(sale.discount_percent)}% off</span>
        </p>

        <p className="flex items-center gap-2">
          <span className="opacity-90">Ends in</span>
          <time
            role="timer"
            aria-label="Time remaining"
            className="font-mono font-bold tabular-nums bg-black/25 px-2 py-0.5 rounded"
          >
            {formatRemaining(remaining)}
          </time>
        </p>

        <Link
          to={`/category?flash_sale=${sale.id}`}
          className="bg-white text-red-600 font-semibold px-4 py-1.5 rounded-full hover:bg-red-50 transition"
        >
          Shop the sale
        </Link>
      </div>
    </section>
  );
};

const toList = (data) => (Array.isArray(data) ? data : data?.results ?? []);

/**
 * Running sales as of THIS browser's clock. Anything the client already
 * considers over is dropped, so a client clock that runs ahead of the
 * server's can't make the banner keep re-fetching a sale it thinks is done.
 */
const fetchActiveSales = async () => {
  const { data } = await getActiveFlashSales();
  const now = Date.now();
  return toList(data).filter((sale) => new Date(sale.ends_at).getTime() > now);
};

/**
 * Homepage flash-sale strip: the sale name, a live countdown to ends_at, and a
 * link to the products on sale. Renders nothing when no sale is running (or the
 * request fails) — never an empty shell.
 *
 * When a countdown reaches zero the banner drops that sale immediately and
 * re-fetches in case another sale is now running, so it can't sit frozen at
 * 00:00:00. Sales this browser's clock already considers over are filtered out
 * of every response, so a client clock that runs ahead of the server's can't
 * cause a re-fetch loop.
 */
const FlashSaleBanner = () => {
  const [sales, setSales] = useState([]);
  const [endedIds, setEndedIds] = useState([]);
  const mounted = useRef(true);

  // Used for re-checking after a countdown ends (not on mount — see below).
  const refresh = useCallback(() => {
    fetchActiveSales()
      .then((list) => mounted.current && setSales(list))
      .catch(() => mounted.current && setSales([]));
  }, []);

  useEffect(() => {
    mounted.current = true;
    fetchActiveSales()
      .then((list) => mounted.current && setSales(list))
      .catch(() => mounted.current && setSales([]));
    return () => {
      mounted.current = false;
    };
  }, []);

  const handleExpire = useCallback(
    (id) => {
      setEndedIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
      refresh();
    },
    [refresh],
  );

  // Soonest-ending first, matching the API's own ordering.
  const sale = [...sales]
    .filter((s) => !endedIds.includes(s.id))
    .sort((a, b) => new Date(a.ends_at) - new Date(b.ends_at))[0];

  if (!sale) return null;

  // key: a different sale gets a fresh countdown rather than inheriting state.
  return <SaleBanner key={sale.id} sale={sale} onExpire={() => handleExpire(sale.id)} />;
};

export default FlashSaleBanner;
