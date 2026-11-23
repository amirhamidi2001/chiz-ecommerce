import { render, screen, act, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import NotificationBell from '../components/NotificationBell';
import { NotificationProvider } from '../context/NotificationContext';

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

import { getAccessToken, notificationsAPI } from '../services/api';

// ─── Fixtures ────────────────────────────────────────────────────────────────
const hoursAgo = (h) => new Date(Date.now() - h * 3_600_000).toISOString();

// ids ascend with recency, so the list API returns them newest (highest id) first.
const note = (id, overrides = {}) => ({
  id,
  event: 'order_status_changed',
  message: `message ${id}`,
  link_url: '',
  is_read: false,
  created_at: hoursAgo(10 - id),
  ...overrides,
});

const LocationProbe = () => <div data-testid="location">{useLocation().pathname}</div>;

describe('NotificationBell', () => {
  let sockets;
  const lastSocket = () => sockets[sockets.length - 1];
  let user;

  const seedInbox = (results) =>
    notificationsAPI.list.mockResolvedValue({ data: { results } });

  const renderBell = async () => {
    const view = render(
      <MemoryRouter>
        <NotificationProvider>
          <NotificationBell />
          <LocationProbe />
        </NotificationProvider>
      </MemoryRouter>,
    );
    await act(async () => {}); // let the mount fetch resolve
    return view;
  };

  const openSocket = () =>
    act(async () => {
      lastSocket().readyState = 1;
      lastSocket().onopen();
    });
  const pushOverSocket = (data) =>
    act(() => {
      lastSocket().onmessage({ data: JSON.stringify(data) });
    });
  const bellButton = () => screen.getByRole('button', { name: /^Notifications/ });
  const badge = () => screen.queryByTestId('notification-badge');
  const openDropdown = async () => {
    await user.click(bellButton());
    return screen.getByRole('region', { name: 'Notifications' });
  };

  beforeEach(() => {
    sockets = [];
    user = userEvent.setup();
    mockAuth.user = { id: 1 };
    document.documentElement.lang = 'en'; // deterministic relative-time wording
    getAccessToken.mockReturnValue('tok-1');
    seedInbox([]);
    notificationsAPI.markRead.mockResolvedValue({});
    notificationsAPI.markAllRead.mockResolvedValue({});

    globalThis.WebSocket = class MockWebSocket {
      constructor(url) {
        this.url = url;
        this.readyState = 0;
        this.send = vi.fn();
        this.close = vi.fn();
        sockets.push(this);
      }
    };
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  // ─── Unread count badge ────────────────────────────────────────────────────
  describe('unread badge', () => {
    it('shows the correct unread count on load (read ones are not counted)', async () => {
      seedInbox([note(4), note(3), note(2, { is_read: true }), note(1)]);
      await renderBell();

      expect(badge()).toHaveTextContent('3');
      expect(bellButton()).toHaveAccessibleName('Notifications, 3 unread');
    });

    it('is hidden when there is nothing unread', async () => {
      seedInbox([note(1, { is_read: true })]);
      await renderBell();

      expect(badge()).not.toBeInTheDocument();
      expect(bellButton()).toHaveAccessibleName('Notifications');
    });

    it('is hidden for an empty inbox', async () => {
      await renderBell();
      expect(badge()).not.toBeInTheDocument();
    });

    it('caps large counts at "9+" so it cannot overflow the badge', async () => {
      seedInbox(Array.from({ length: 12 }, (_, i) => note(i + 1)));
      await renderBell();

      expect(badge()).toHaveTextContent('9+');
      // The exact number is still available to assistive tech.
      expect(bellButton()).toHaveAccessibleName('Notifications, 12 unread');
    });

    it('shows exactly 9 (not "9+") at the cap boundary', async () => {
      seedInbox(Array.from({ length: 9 }, (_, i) => note(i + 1)));
      await renderBell();

      expect(badge()).toHaveTextContent(/^9$/);
    });
  });

  // ─── Dropdown list ─────────────────────────────────────────────────────────
  describe('dropdown', () => {
    it('is closed until the bell is clicked', async () => {
      seedInbox([note(1)]);
      await renderBell();

      expect(screen.queryByRole('region', { name: 'Notifications' })).not.toBeInTheDocument();
      expect(bellButton()).toHaveAttribute('aria-expanded', 'false');
    });

    it('lists notifications newest first with message text and relative time', async () => {
      seedInbox([note(3), note(2), note(1)]); // created 7h, 8h, 9h ago
      await renderBell();

      const menu = await openDropdown();
      const items = within(menu).getAllByRole('listitem');

      expect(items).toHaveLength(3);
      expect(items[0]).toHaveTextContent('message 3');
      expect(items[0]).toHaveTextContent('7 hours ago');
      expect(items[2]).toHaveTextContent('message 1');
      expect(items[2]).toHaveTextContent('9 hours ago');
      expect(bellButton()).toHaveAttribute('aria-expanded', 'true');
    });

    it('flags unread items for screen readers and leaves read ones plain', async () => {
      seedInbox([note(2), note(1, { is_read: true })]);
      await renderBell();

      const items = within(await openDropdown()).getAllByRole('listitem');

      expect(within(items[0]).getByText('Unread')).toBeInTheDocument();
      expect(within(items[1]).queryByText('Unread')).not.toBeInTheDocument();
    });

    it('shows an empty state when there are no notifications', async () => {
      await renderBell();
      const menu = await openDropdown();

      expect(within(menu).getByText('No notifications yet')).toBeInTheDocument();
      expect(within(menu).queryByText('Mark all as read')).not.toBeInTheDocument();
    });

    it('closes on Escape (returning focus to the bell) and on outside click', async () => {
      seedInbox([note(1)]);
      await renderBell();

      await openDropdown();
      await user.keyboard('{Escape}');
      expect(screen.queryByRole('region', { name: 'Notifications' })).not.toBeInTheDocument();
      expect(bellButton()).toHaveFocus();

      await openDropdown();
      await user.click(document.body);
      expect(screen.queryByRole('region', { name: 'Notifications' })).not.toBeInTheDocument();
    });

    it('toggles closed when the bell is clicked again', async () => {
      await renderBell();
      await openDropdown();
      await user.click(bellButton());

      expect(screen.queryByRole('region', { name: 'Notifications' })).not.toBeInTheDocument();
    });
  });

  // ─── Clicking a notification ───────────────────────────────────────────────
  describe('selecting a notification', () => {
    it('navigates to its link, marks it read via the API, drops the badge, and closes', async () => {
      seedInbox([note(2, { link_url: '/order-confirmation/42' }), note(1)]);
      await renderBell();
      expect(badge()).toHaveTextContent('2');

      const menu = await openDropdown();
      await user.click(within(menu).getByText('message 2'));

      expect(notificationsAPI.markRead).toHaveBeenCalledWith(2);
      expect(screen.getByTestId('location')).toHaveTextContent('/order-confirmation/42');
      expect(badge()).toHaveTextContent('1');
      expect(screen.queryByRole('region', { name: 'Notifications' })).not.toBeInTheDocument();
    });

    it('marks read but stays put when the notification has no link', async () => {
      seedInbox([note(1, { link_url: '' })]);
      await renderBell();

      await user.click(within(await openDropdown()).getByText('message 1'));

      expect(notificationsAPI.markRead).toHaveBeenCalledWith(1);
      expect(screen.getByTestId('location')).toHaveTextContent('/');
      expect(badge()).not.toBeInTheDocument();
    });

    it('does not re-mark an already-read notification, but still navigates', async () => {
      seedInbox([note(1, { is_read: true, link_url: '/product/lipstick' })]);
      await renderBell();

      await user.click(within(await openDropdown()).getByText('message 1'));

      expect(notificationsAPI.markRead).not.toHaveBeenCalled();
      expect(screen.getByTestId('location')).toHaveTextContent('/product/lipstick');
    });
  });

  // ─── Mark all as read ──────────────────────────────────────────────────────
  describe('mark all as read', () => {
    it('calls the bulk endpoint once and clears the badge', async () => {
      seedInbox([note(3), note(2), note(1)]);
      await renderBell();
      expect(badge()).toHaveTextContent('3');

      const menu = await openDropdown();
      await user.click(within(menu).getByRole('button', { name: 'Mark all as read' }));

      expect(notificationsAPI.markAllRead).toHaveBeenCalledTimes(1);
      expect(notificationsAPI.markRead).not.toHaveBeenCalled();
      expect(badge()).not.toBeInTheDocument();
      expect(bellButton()).toHaveAccessibleName('Notifications');
      // The list stays open and every row is now read; the action disappears.
      expect(within(menu).queryByText('Unread')).not.toBeInTheDocument();
      expect(within(menu).queryByRole('button', { name: 'Mark all as read' })).not.toBeInTheDocument();
    });

    it('restores the real unread state if the API call fails', async () => {
      seedInbox([note(2), note(1)]);
      notificationsAPI.markAllRead.mockRejectedValue(new Error('500'));
      await renderBell();

      const menu = await openDropdown();
      await user.click(within(menu).getByRole('button', { name: 'Mark all as read' }));

      expect(badge()).toHaveTextContent('2'); // rolled back from the server's list
    });
  });

  // ─── Real-time updates ─────────────────────────────────────────────────────
  describe('real-time WebSocket updates', () => {
    it('increments the badge and puts a pushed notification at the top, with no re-fetch', async () => {
      seedInbox([note(2), note(1)]);
      await renderBell();
      await openSocket();
      const menu = await openDropdown();
      notificationsAPI.list.mockClear();

      await pushOverSocket({
        id: 3,
        event: 'order_status_changed',
        message: 'Your order has shipped',
        link_url: '/order-confirmation/7',
        created_at: new Date().toISOString(),
      });

      expect(badge()).toHaveTextContent('3');
      const items = within(menu).getAllByRole('listitem');
      expect(items).toHaveLength(3);
      expect(items[0]).toHaveTextContent('Your order has shipped');
      expect(items[0]).toHaveTextContent('now');
      expect(notificationsAPI.list).not.toHaveBeenCalled();
    });

    it('shows the badge appearing from zero while the dropdown is closed', async () => {
      await renderBell();
      await openSocket();
      expect(badge()).not.toBeInTheDocument();

      await pushOverSocket(note(1));

      expect(badge()).toHaveTextContent('1');
    });

    it('does not double count a push that the REST fetch already returned', async () => {
      seedInbox([note(1)]);
      await renderBell();
      await openSocket();

      await pushOverSocket(note(1));

      expect(badge()).toHaveTextContent('1');
    });

    it('opens one socket to /ws/notifications/ with the access token', async () => {
      await renderBell();

      expect(sockets).toHaveLength(1);
      expect(lastSocket().url).toMatch(/\/ws\/notifications\/\?token=tok-1$/);
    });
  });

  // ─── WebSocket disconnected ────────────────────────────────────────────────
  describe('when the WebSocket is down', () => {
    it('still works from the REST data when the socket never connects', async () => {
      seedInbox([note(2), note(1)]);
      await renderBell(); // no openSocket(): the connection never succeeds

      expect(badge()).toHaveTextContent('2');
      const menu = await openDropdown();
      expect(within(menu).getAllByRole('listitem')).toHaveLength(2);

      await user.click(within(menu).getByRole('button', { name: 'Mark all as read' }));
      expect(notificationsAPI.markAllRead).toHaveBeenCalledTimes(1);
      expect(badge()).not.toBeInTheDocument();
    });

    it('keeps the data after a drop, tells the user, and re-fetches when opened', async () => {
      seedInbox([note(2), note(1)]);
      await renderBell();
      await openSocket();
      act(() => {
        lastSocket().readyState = 3;
        lastSocket().onclose({ code: 1006 });
      });
      notificationsAPI.list.mockClear();

      expect(badge()).toHaveTextContent('2'); // nothing lost
      const menu = await openDropdown();

      expect(within(menu).getByRole('status')).toHaveTextContent(/Live updates are paused/);
      expect(notificationsAPI.list).toHaveBeenCalledTimes(1); // opening refreshes
      expect(within(menu).getAllByRole('listitem')).toHaveLength(2);
    });

    it('does not show the paused notice while connected, and does not refetch on open', async () => {
      seedInbox([note(1)]);
      await renderBell();
      await openSocket();
      notificationsAPI.list.mockClear();

      const menu = await openDropdown();

      expect(within(menu).queryByRole('status')).not.toBeInTheDocument();
      expect(notificationsAPI.list).not.toHaveBeenCalled();
    });

    it('drops the notice once the connection is restored', async () => {
      await renderBell();
      await openSocket();
      act(() => {
        lastSocket().readyState = 3;
        lastSocket().onclose({ code: 1006 });
      });
      const menu = await openDropdown();
      expect(within(menu).getByRole('status')).toBeInTheDocument();

      act(() => {
        window.dispatchEvent(new Event('online')); // browser regained network
      });
      await openSocket(); // the revived socket connects

      expect(within(menu).queryByRole('status')).not.toBeInTheDocument();
    });
  });
});
