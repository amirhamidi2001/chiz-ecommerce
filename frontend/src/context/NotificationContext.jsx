import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { authAPI, getAccessToken, notificationsAPI } from '../services/api';
import { CONNECTION_STATUS } from '../hooks/useChatWebSocket';
import { useAuth } from './AuthContext';

// Connection constants deliberately match hooks/useChatWebSocket.js: same
// VITE_WS_URL base, same ?token=<access JWT> convention (read by the backend's
// shared JWTAuthMiddleware), same 3 s / 5-attempt reconnect policy, and the
// same rule that close code 4001 (unauthenticated) is not blindly retried.
const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
const RECONNECT_DELAY_MS = 3_000;
const MAX_RECONNECTS = 5;
const INITIAL_PAGE_SIZE = 50;
// WebSocket.readyState values (the global constants aren't present on test doubles).
const WS_CONNECTING = 0;
const WS_OPEN = 1;

const NotificationContext = createContext(null);

const fetchInbox = async () => {
  const { data } = await notificationsAPI.list({ page_size: INITIAL_PAGE_SIZE });
  return data.results;
};

// Newest first, one entry per id. `incoming` wins on conflict, so a fetch
// result (server truth) overrides an optimistic local edit.
const mergeById = (existing, incoming) => {
  const byId = new Map(existing.map((n) => [n.id, n]));
  incoming.forEach((n) => byId.set(n.id, n));
  return [...byId.values()].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at) || b.id - a.id,
  );
};

/**
 * Owns the notification list for ONE signed-in user. It is rendered with
 * `key={userId}` (see NotificationProvider), so switching accounts remounts it
 * and no previous user's notifications can leak into the next session.
 */
function NotificationStore({ children }) {
  const [notifications, setNotifications] = useState([]);
  const [status, setStatus] = useState(CONNECTION_STATUS.CLOSED);

  // REST is the source of truth; the socket is only a live nudge. Pushes sent
  // while this tab was offline/reconnecting are never replayed, so every
  // (re)connect re-syncs from the API.
  const refresh = useCallback(async () => {
    try {
      const results = await fetchInbox();
      setNotifications((prev) => mergeById(prev, results));
    } catch {
      /* keep what we have; the next (re)connect retries */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    let ws = null;
    let reconnectTimer = null;
    let reconnects = 0;
    let authRefreshed = false;

    const connect = () => {
      // Read the token on EVERY attempt: access tokens live 60 minutes, so one
      // captured at mount would be expired by a later reconnect.
      const token = getAccessToken();
      if (cancelled || !token) return;

      setStatus(CONNECTION_STATUS.CONNECTING);
      ws = new WebSocket(
        `${WS_BASE}/ws/notifications/?token=${encodeURIComponent(token)}`,
      );

      ws.onopen = () => {
        reconnects = 0;
        authRefreshed = false;
        setStatus(CONNECTION_STATUS.OPEN);
        refresh();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data?.id == null) return;
          // A pushed notification is brand new, hence unread.
          setNotifications((prev) =>
            mergeById(prev, [{ ...data, is_read: false }]),
          );
        } catch {
          /* silently ignore malformed frames */
        }
      };

      ws.onerror = () => setStatus(CONNECTION_STATUS.ERROR);

      ws.onclose = (e) => {
        if (cancelled) return;
        setStatus(CONNECTION_STATUS.CLOSED);

        if (e.code === 4001) {
          // Rejected as unauthenticated — most likely an expired access token.
          // Chat gives up here; for a long-lived tab that would silently kill
          // the bell. Make ONE authenticated REST call (the axios interceptor
          // refreshes the token and stores it), then retry once. If the
          // session is truly dead the interceptor sends the user to /login.
          if (!authRefreshed) {
            authRefreshed = true;
            authAPI.getUser().then(connect).catch(() => {});
          }
          return;
        }

        if (reconnects < MAX_RECONNECTS) {
          reconnects += 1;
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };
    };

    // Bring a dead connection back to life when the browser has a reason to
    // think things changed. The 5 x 3 s retry budget only covers a blip; a
    // real outage (laptop asleep, train tunnel) outlasts it, and without this
    // the bell would stay frozen until a full page reload.
    const revive = () => {
      if (cancelled) return;
      if (ws && (ws.readyState === WS_CONNECTING || ws.readyState === WS_OPEN)) {
        return; // already healthy / already trying
      }
      clearTimeout(reconnectTimer);
      reconnects = 0;
      authRefreshed = false;
      connect();
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') revive();
    };

    // REST first, independent of the socket: if the socket can't connect at
    // all, the bell still shows the saved inbox. (Skipped without a token — an
    // unauthenticated call would trip the axios 401 handler's /login redirect.)
    if (getAccessToken()) {
      fetchInbox()
        .then((results) => {
          if (!cancelled) setNotifications((prev) => mergeById(prev, results));
        })
        .catch(() => {
          /* the socket's onopen re-sync (or the bell opening) retries */
        });
    }
    connect();

    window.addEventListener('online', revive);
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      window.removeEventListener('online', revive);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      if (ws) {
        ws.onclose = null; // intentional close must not trigger a reconnect
        ws.close();
      }
    };
  }, [refresh]);

  const markRead = useCallback(
    async (id) => {
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
      );
      try {
        await notificationsAPI.markRead(id);
      } catch {
        refresh(); // roll the optimistic edit back to server truth
      }
    },
    [refresh],
  );

  const markAllRead = useCallback(async () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    try {
      await notificationsAPI.markAllRead();
    } catch {
      refresh();
    }
  }, [refresh]);

  const value = useMemo(
    () => ({
      notifications,
      // Counted over the loaded page (newest INITIAL_PAGE_SIZE) plus live
      // pushes; the list endpoint has no server-side unread total yet.
      unreadCount: notifications.filter((n) => !n.is_read).length,
      status,
      markRead,
      markAllRead,
      refresh,
    }),
    [notifications, status, markRead, markAllRead, refresh],
  );

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
}

const SIGNED_OUT_VALUE = {
  notifications: [],
  unreadCount: 0,
  status: CONNECTION_STATUS.CLOSED,
  markRead: async () => {},
  markAllRead: async () => {},
  refresh: async () => {},
};

export const NotificationProvider = ({ children }) => {
  const { user } = useAuth();

  if (!user?.id) {
    return (
      <NotificationContext.Provider value={SIGNED_OUT_VALUE}>
        {children}
      </NotificationContext.Provider>
    );
  }
  return <NotificationStore key={user.id}>{children}</NotificationStore>;
};

export const useNotifications = () => {
  const ctx = useContext(NotificationContext);
  if (!ctx) {
    throw new Error('useNotifications must be used inside <NotificationProvider>');
  }
  return ctx;
};

export default NotificationContext;
