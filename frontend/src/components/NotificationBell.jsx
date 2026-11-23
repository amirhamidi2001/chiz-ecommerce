// src/components/NotificationBell.jsx
//
// Header bell + unread badge + dropdown of recent in-app notifications.
//
// All data comes from NotificationContext (Task 16.4.1.2), which owns the REST
// fetch AND the live WebSocket merge — this component deliberately makes no API
// calls of its own, so there is exactly one source of truth for the list and
// no fetch/push race to reconcile here.
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNotifications } from '../context/NotificationContext';
import { CONNECTION_STATUS } from '../hooks/useChatWebSocket';
import { formatRelativeTime } from '../utils/relativeTime';

// "9+" rather than an unbounded number: the badge is a fixed w-5 h-5 circle
// (same as the cart/wishlist badges), which fits two characters but not three.
const BADGE_CAP = 9;
const formatBadgeCount = (count) => (count > BADGE_CAP ? `${BADGE_CAP}+` : String(count));

// Relative timestamps go stale while the dropdown stays open.
const TICK_MS = 60_000;

const EVENT_ICONS = {
  order_confirmed: 'bi-bag-check',
  order_status_changed: 'bi-box-seam',
  shipping_update: 'bi-truck',
  back_in_stock: 'bi-box-arrow-in-down',
  price_drop: 'bi-tag',
  welcome: 'bi-stars',
};
const iconFor = (event) => EVENT_ICONS[event] || 'bi-bell';

const NotificationBell = () => {
  const { notifications, unreadCount, status, markRead, markAllRead, refresh } =
    useNotifications();
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const rootRef = useRef(null);
  const buttonRef = useRef(null);

  // While open: close on outside click / Escape, and keep timestamps fresh.
  useEffect(() => {
    if (!open) return undefined;

    const onPointerDown = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    const tick = setInterval(() => setNow(Date.now()), TICK_MS);

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      clearInterval(tick);
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const handleToggle = () => {
    if (!open) {
      setNow(Date.now());
      // Live updates are down: opening the dropdown is a good moment to pull
      // the saved inbox again so the REST fallback is as fresh as possible.
      if (status !== CONNECTION_STATUS.OPEN) refresh();
    }
    setOpen(!open);
  };

  const handleSelect = (notification) => {
    if (!notification.is_read) markRead(notification.id);
    setOpen(false);
    if (notification.link_url) navigate(notification.link_url);
  };

  const liveUpdatesDown =
    status === CONNECTION_STATUS.CLOSED || status === CONNECTION_STATUS.ERROR;

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={handleToggle}
        className="relative text-emerald-700 text-xl hover:text-teal-700"
        aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls="notification-menu"
      >
        <i className="bi bi-bell" aria-hidden="true" />
        {unreadCount > 0 && (
          <span
            data-testid="notification-badge"
            aria-hidden="true"
            className="absolute -top-2 -end-3 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center"
          >
            {formatBadgeCount(unreadCount)}
          </span>
        )}
      </button>

      {open && (
        // Phones: pinned under the header with a 1rem gutter (an end-aligned
        // 24rem panel would run off the left edge of a 360px screen).
        // sm and up: anchored to the bell like the account dropdown.
        <div
          id="notification-menu"
          role="region"
          aria-label="Notifications"
          className="fixed inset-x-4 top-[4.5rem] sm:absolute sm:inset-x-auto sm:end-0 sm:top-auto sm:mt-3 sm:w-96 bg-white shadow-xl rounded-lg border border-emerald-100 z-10"
        >
          <div className="flex items-center justify-between gap-2 px-4 py-3 border-b">
            <h6 className="font-semibold text-emerald-800">Notifications</h6>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                className="text-xs text-teal-700 hover:underline"
              >
                Mark all as read
              </button>
            )}
          </div>

          {notifications.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-emerald-500">
              No notifications yet
            </p>
          ) : (
            <ul className="max-h-96 overflow-y-auto divide-y divide-emerald-50">
              {notifications.map((notification) => (
                <li key={notification.id}>
                  <button
                    type="button"
                    onClick={() => handleSelect(notification)}
                    className={`w-full text-start flex items-start gap-3 px-4 py-3 hover:bg-emerald-50 ${
                      notification.is_read ? '' : 'bg-emerald-50/60'
                    }`}
                  >
                    <i
                      className={`bi ${iconFor(notification.event)} mt-0.5 text-lg ${
                        notification.is_read ? 'text-emerald-400' : 'text-teal-700'
                      }`}
                      aria-hidden="true"
                    />
                    <span className="flex-1 min-w-0">
                      <span
                        className={`block text-sm break-words ${
                          notification.is_read ? 'text-gray-600' : 'text-gray-900 font-medium'
                        }`}
                      >
                        {notification.message}
                      </span>
                      <time
                        dateTime={notification.created_at}
                        className="block mt-1 text-xs text-emerald-500"
                      >
                        {formatRelativeTime(notification.created_at, { now })}
                      </time>
                    </span>
                    {!notification.is_read && (
                      <>
                        <span
                          className="mt-1.5 w-2 h-2 rounded-full bg-red-500 flex-shrink-0"
                          aria-hidden="true"
                        />
                        <span className="sr-only">Unread</span>
                      </>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}

          {liveUpdatesDown && (
            <p
              role="status"
              className="px-4 py-2 text-xs text-emerald-600 bg-emerald-50 border-t rounded-b-lg"
            >
              Live updates are paused. Showing your saved notifications.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default NotificationBell;
