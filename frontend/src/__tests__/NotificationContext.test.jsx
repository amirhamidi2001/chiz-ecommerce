import { useEffect } from 'react';
import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  NotificationProvider,
  useNotifications,
} from '../context/NotificationContext';

// ─── Module mocks ────────────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  authAPI: { getUser: vi.fn() },
  getAccessToken: vi.fn(),
  notificationsAPI: {
    list: vi.fn(),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
  },
}));

const mockAuth = { user: { id: 1 } };
vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

import { authAPI, getAccessToken, notificationsAPI } from '../services/api';

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECTS = 5;

const note = (id, overrides = {}) => ({
  id,
  event: 'order_status_changed',
  message: `message ${id}`,
  link_url: '',
  is_read: false,
  created_at: `2026-11-22T10:0${id}:00Z`,
  ...overrides,
});

// ─── Consumer ────────────────────────────────────────────────────────────────
// `latest.api` always holds the most recent context value, so tests can call
// markRead()/markAllRead() and inspect the raw list.
const latest = {};
const Probe = () => {
  const ctx = useNotifications();
  useEffect(() => {
    latest.api = ctx;
  });
  return (
    <div>
      <span data-testid="unread">{ctx.unreadCount}</span>
      <span data-testid="status">{ctx.status}</span>
      <span data-testid="ids">{ctx.notifications.map((n) => n.id).join(',')}</span>
    </div>
  );
};
const text = (id) => screen.getByTestId(id).textContent;
const flush = () => act(async () => {});

describe('NotificationContext', () => {
  let sockets;
  const lastSocket = () => sockets[sockets.length - 1];

  beforeEach(() => {
    sockets = [];
    latest.api = undefined;
    mockAuth.user = { id: 1 };
    vi.useFakeTimers();
    getAccessToken.mockReturnValue('tok-1');
    notificationsAPI.list.mockResolvedValue({ data: { results: [] } });
    notificationsAPI.markRead.mockResolvedValue({});
    notificationsAPI.markAllRead.mockResolvedValue({});

    globalThis.WebSocket = class MockWebSocket {
      constructor(url) {
        this.url = url;
        this.readyState = 0; // CONNECTING
        this.send = vi.fn();
        this.close = vi.fn();
        sockets.push(this);
      }
    };
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  const mount = () =>
    render(
      <NotificationProvider>
        <Probe />
      </NotificationProvider>,
    );

  const open = async () => {
    await act(async () => {
      lastSocket().readyState = 1; // OPEN
      lastSocket().onopen();
    });
  };
  // A real socket is CLOSED by the time onclose fires.
  const closeSocket = (code) =>
    act(() => {
      lastSocket().readyState = 3;
      lastSocket().onclose({ code });
    });
  const push = (data) =>
    act(() => {
      lastSocket().onmessage({ data: JSON.stringify(data) });
    });

  describe('connection', () => {
    it('connects to /ws/notifications/ with the access token as ?token=', () => {
      mount();

      expect(sockets).toHaveLength(1);
      expect(lastSocket().url).toMatch(/\/ws\/notifications\/\?token=tok-1$/);
      expect(text('status')).toBe('connecting');
    });

    it('does not connect when signed out, and exposes an empty inbox', () => {
      mockAuth.user = null;
      mount();

      expect(sockets).toHaveLength(0);
      expect(text('unread')).toBe('0');
      expect(latest.api.notifications).toEqual([]);
    });

    it('does not connect when there is no access token', () => {
      getAccessToken.mockReturnValue(null);
      mount();

      expect(sockets).toHaveLength(0);
    });

    it('closes the socket on unmount without scheduling a reconnect', () => {
      const { unmount } = mount();
      const ws = lastSocket();

      unmount();

      expect(ws.close).toHaveBeenCalledTimes(1);
      expect(ws.onclose).toBeNull();
      vi.advanceTimersByTime(RECONNECT_DELAY_MS * 2);
      expect(sockets).toHaveLength(1);
    });

    it('opens a fresh socket when a different user signs in', () => {
      const { rerender } = mount();
      expect(sockets).toHaveLength(1);
      const first = lastSocket();

      mockAuth.user = { id: 2 };
      rerender(
        <NotificationProvider>
          <Probe />
        </NotificationProvider>,
      );

      expect(first.close).toHaveBeenCalled();
      expect(sockets).toHaveLength(2);
    });
  });

  describe('state', () => {
    it('loads the existing inbox from the API when the socket opens', async () => {
      notificationsAPI.list.mockResolvedValue({
        data: { results: [note(2), note(1, { is_read: true })] },
      });
      mount();
      await open();
      await flush();

      expect(notificationsAPI.list).toHaveBeenCalledWith({ page_size: 50 });
      expect(text('ids')).toBe('2,1');
      expect(text('unread')).toBe('1');
      expect(text('status')).toBe('open');
    });

    it('adds a pushed notification as unread, newest first', async () => {
      notificationsAPI.list.mockResolvedValue({ data: { results: [note(1)] } });
      mount();
      await open();
      await flush();

      push({ ...note(3), is_read: undefined });

      expect(text('ids')).toBe('3,1');
      expect(text('unread')).toBe('2');
    });

    it('de-duplicates a push that the REST fetch also returned', async () => {
      notificationsAPI.list.mockResolvedValue({ data: { results: [note(1)] } });
      mount();
      await open();
      push(note(1));
      await flush();

      expect(text('ids')).toBe('1');
      expect(text('unread')).toBe('1');
    });

    it('ignores malformed frames and frames without an id', async () => {
      mount();
      await open();

      act(() => {
        lastSocket().onmessage({ data: 'not json' });
        lastSocket().onmessage({ data: JSON.stringify({ hello: 'x' }) });
      });

      expect(text('ids')).toBe('');
    });
  });

  describe('reconnection', () => {
    it('reconnects after an abnormal close and re-syncs from the API', async () => {
      mount();
      await open();
      notificationsAPI.list.mockClear();

      act(() => lastSocket().onclose({ code: 1006 }));
      expect(text('status')).toBe('closed');
      await act(async () => {
        vi.advanceTimersByTime(RECONNECT_DELAY_MS);
      });
      expect(sockets).toHaveLength(2);

      await open();
      expect(notificationsAPI.list).toHaveBeenCalledTimes(1);
    });

    it('reads a fresh token for every reconnect attempt', () => {
      mount();
      getAccessToken.mockReturnValue('tok-2');

      act(() => lastSocket().onclose({ code: 1006 }));
      act(() => {
        vi.advanceTimersByTime(RECONNECT_DELAY_MS);
      });

      expect(lastSocket().url).toContain('token=tok-2');
    });

    it('gives up after MAX_RECONNECTS consecutive failures', () => {
      mount();
      for (let i = 0; i < MAX_RECONNECTS + 3; i += 1) {
        act(() => lastSocket().onclose({ code: 1006 }));
        act(() => {
          vi.advanceTimersByTime(RECONNECT_DELAY_MS);
        });
      }

      expect(sockets).toHaveLength(1 + MAX_RECONNECTS);
    });

    it('resets the retry budget after a successful open', async () => {
      mount();
      for (let i = 0; i < MAX_RECONNECTS - 1; i += 1) {
        act(() => lastSocket().onclose({ code: 1006 }));
        act(() => {
          vi.advanceTimersByTime(RECONNECT_DELAY_MS);
        });
      }
      await open();

      for (let i = 0; i < MAX_RECONNECTS; i += 1) {
        act(() => lastSocket().onclose({ code: 1006 }));
        act(() => {
          vi.advanceTimersByTime(RECONNECT_DELAY_MS);
        });
      }

      expect(sockets).toHaveLength(1 + (MAX_RECONNECTS - 1) + MAX_RECONNECTS);
    });

    it('on 4001 refreshes the session once, then reconnects with the new token', async () => {
      authAPI.getUser.mockResolvedValue({ data: {} });
      mount();

      getAccessToken.mockReturnValue('tok-refreshed');
      await act(async () => lastSocket().onclose({ code: 4001 }));

      expect(authAPI.getUser).toHaveBeenCalledTimes(1);
      expect(sockets).toHaveLength(2);
      expect(lastSocket().url).toContain('token=tok-refreshed');
    });

    it('does not loop when 4001 repeats after the refresh', async () => {
      authAPI.getUser.mockResolvedValue({ data: {} });
      mount();

      await act(async () => lastSocket().onclose({ code: 4001 }));
      await act(async () => lastSocket().onclose({ code: 4001 }));
      act(() => {
        vi.advanceTimersByTime(RECONNECT_DELAY_MS * 10);
      });

      expect(authAPI.getUser).toHaveBeenCalledTimes(1);
      expect(sockets).toHaveLength(2);
    });

    it('stays disconnected when the 4001 session refresh fails', async () => {
      authAPI.getUser.mockRejectedValue(new Error('401'));
      mount();

      await act(async () => lastSocket().onclose({ code: 4001 }));

      expect(sockets).toHaveLength(1);
    });
  });

  describe('REST fallback and revival', () => {
    it('loads the saved inbox on mount even if the socket never opens', async () => {
      notificationsAPI.list.mockResolvedValue({
        data: { results: [note(2), note(1)] },
      });
      mount();
      await flush(); // no onopen() — the socket is still connecting

      expect(notificationsAPI.list).toHaveBeenCalledTimes(1);
      expect(text('ids')).toBe('2,1');
      expect(text('unread')).toBe('2');
      expect(text('status')).toBe('connecting');
    });

    it('does not call the API without an access token', async () => {
      getAccessToken.mockReturnValue(null);
      mount();
      await flush();

      expect(notificationsAPI.list).not.toHaveBeenCalled();
    });

    it('survives a failing mount fetch', async () => {
      notificationsAPI.list.mockRejectedValue(new Error('500'));
      mount();
      await flush();

      expect(text('ids')).toBe('');
    });

    it('reconnects when the browser comes back online after retries ran out', async () => {
      mount();
      for (let i = 0; i < MAX_RECONNECTS + 1; i += 1) {
        closeSocket(1006);
        act(() => {
          vi.advanceTimersByTime(RECONNECT_DELAY_MS);
        });
      }
      const exhausted = sockets.length;
      expect(exhausted).toBe(1 + MAX_RECONNECTS);

      closeSocket(1006); // the last retry fails too: now fully given up
      act(() => {
        vi.advanceTimersByTime(RECONNECT_DELAY_MS * 10);
      });
      expect(sockets).toHaveLength(exhausted);

      act(() => {
        window.dispatchEvent(new Event('online'));
      });
      expect(sockets).toHaveLength(exhausted + 1);

      // ...with a full retry budget again.
      closeSocket(1006);
      act(() => {
        vi.advanceTimersByTime(RECONNECT_DELAY_MS);
      });
      expect(sockets).toHaveLength(exhausted + 2);
    });

    it('reconnects when the tab becomes visible again', () => {
      mount();
      closeSocket(1006);
      // (a retry is pending; becoming visible just does it now)
      Object.defineProperty(document, 'visibilityState', {
        configurable: true,
        get: () => 'visible',
      });
      act(() => {
        document.dispatchEvent(new Event('visibilitychange'));
      });

      expect(sockets).toHaveLength(2);
      delete document.visibilityState;
    });

    it('ignores online/visibility events while the socket is healthy or connecting', async () => {
      mount();
      act(() => {
        window.dispatchEvent(new Event('online')); // still CONNECTING
      });
      expect(sockets).toHaveLength(1);

      await open();
      act(() => {
        window.dispatchEvent(new Event('online')); // OPEN
        document.dispatchEvent(new Event('visibilitychange'));
      });
      expect(sockets).toHaveLength(1);
    });

    it('stops listening for online events after unmount', () => {
      const { unmount } = mount();
      unmount();
      act(() => {
        window.dispatchEvent(new Event('online'));
      });

      expect(sockets).toHaveLength(1);
    });
  });

  describe('actions', () => {
    beforeEach(() => {
      notificationsAPI.list.mockResolvedValue({
        data: { results: [note(2), note(1)] },
      });
    });

    it('markRead updates the list immediately and calls the API', async () => {
      mount();
      await open();
      await flush();

      await act(async () => {
        await latest.api.markRead(2);
      });

      expect(notificationsAPI.markRead).toHaveBeenCalledWith(2);
      expect(text('unread')).toBe('1');
    });

    it('markRead rolls back to server truth when the API call fails', async () => {
      mount();
      await open();
      await flush();
      notificationsAPI.markRead.mockRejectedValue(new Error('500'));

      await act(async () => {
        await latest.api.markRead(2);
      });

      expect(notificationsAPI.list).toHaveBeenCalledTimes(3); // mount + open + rollback
      expect(text('unread')).toBe('2');
    });

    it('markAllRead clears the unread count and calls the API', async () => {
      mount();
      await open();
      await flush();

      await act(async () => {
        await latest.api.markAllRead();
      });

      expect(notificationsAPI.markAllRead).toHaveBeenCalledTimes(1);
      expect(text('unread')).toBe('0');
    });
  });

  it('useNotifications throws outside the provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/NotificationProvider/);
    spy.mockRestore();
  });
});
