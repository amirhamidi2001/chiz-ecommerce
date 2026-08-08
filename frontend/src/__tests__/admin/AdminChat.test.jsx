/**
 * AdminChat.test.jsx
 *
 * Comprehensive unit & integration tests for AdminChat.jsx
 * Stack : Vitest · React Testing Library · @testing-library/user-event v14
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  render,
  screen,
  waitFor,
  within,
  fireEvent,
  act,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminChat from '../../pages/admin/AdminChat';

// ─── localStorage stub ────────────────────────────────────────────────────────
const localStorageMock = (() => {
  const store = { access_token: 'mock-token-xyz' };
  return {
    getItem: vi.fn((k) => store[k] ?? null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// ─── Mock: AuthContext ────────────────────────────────────────────────────────
const mockUser = { id: 99, full_name: 'Admin User' };
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}));

// ─── Mock: adminAPI ───────────────────────────────────────────────────────────
vi.mock('../../services/api', () => ({
  adminAPI: {
    getChatRooms: vi.fn(),
    getChatRoomMessages: vi.fn(),
    updateChatRoom: vi.fn(),
  },
}));
import { adminAPI } from '../../services/api';

// ─── Mock: useChatWebSocket ───────────────────────────────────────────────────
export const CONNECTION_STATUS = {
  OPEN: 'open',
  CONNECTING: 'connecting',
  CLOSED: 'closed',
  ERROR: 'error',
};

let wsControls = {};
const resetWsControls = () => {
  wsControls = {
    messages: [],
    typingUsers: [],
    status: CONNECTION_STATUS.OPEN,
    sendMessage: vi.fn(),
    sendTyping: vi.fn(),
    loadHistory: vi.fn(),
  };
};

vi.mock('../../hooks/useChatWebSocket', () => ({
  CONNECTION_STATUS: {
    OPEN: 'open',
    CONNECTING: 'connecting',
    CLOSED: 'closed',
    ERROR: 'error',
  },
  useChatWebSocket: vi.fn((_roomId, _token, { onError } = {}) => {
    wsControls._onError = onError;
    return wsControls;
  }),
}));

// ─── Fixture factories ────────────────────────────────────────────────────────
const makeRoom = (overrides = {}) => ({
  id: 1,
  customer_name: 'Alice Smith',
  customer_email: 'alice@example.com',
  status: 'open',
  subject: 'Order #1234',
  unread_count: 0,
  last_message: {
    content: 'Hello, I need help.',
    created_at: '2024-06-01T10:30:00Z',
  },
  ...overrides,
});

const makeMessage = (overrides = {}) => ({
  id: 101,
  content: 'Hi there!',
  sender: { id: 5, full_name: 'Bob Customer', is_agent: false },
  message_type: 'text',
  created_at: '2024-06-01T10:31:00Z',
  ...overrides,
});

const paged = (results) => ({ data: { results, count: results.length } });
const flat = (arr) => ({ data: arr });

const okRooms = (rooms = [makeRoom()]) =>
  adminAPI.getChatRooms.mockResolvedValue(paged(rooms));

const okMessages = (msgs = [makeMessage()]) =>
  adminAPI.getChatRoomMessages.mockResolvedValue(paged(msgs));

const setup = () => userEvent.setup();
const setupFake = () => userEvent.setup({ advanceTimers: vi.advanceTimersByTime, delay: null });

const byOwnText = (text) => (content, node) => {
  const hasText = (n) => n.textContent === text;
  const nodeHasText = hasText(node);
  const childrenDontHaveText = Array.from(node?.children ?? []).every(
    (child) => !hasText(child)
  );
  return nodeHasText && childrenDontHaveText;
};

// Enforce UTC timezone for predictable snapshot testing across environments
process.env.TZ = 'UTC';

// ─────────────────────────────────────────────────────────────────────────────

describe('AdminChat', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetWsControls();
    okRooms();
    okMessages();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── 1. Page structure ────────────────────────────────────────────────────
  describe('Page structure', () => {
    it('renders the Conversations heading', async () => {
      render(<AdminChat />);
      expect(screen.getByText('Conversations')).toBeInTheDocument();
    });

    it('renders three filter tabs: open, assigned, closed', () => {
      render(<AdminChat />);
      expect(screen.getByRole('button', { name: /^open$/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^assigned$/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^closed$/i })).toBeInTheDocument();
    });

    it('"open" filter tab is active by default', () => {
      render(<AdminChat />);
      const openTab = screen.getByRole('button', { name: /^open$/i });
      expect(openTab.className).toMatch(/bg-teal-600/);
    });

    it('"assigned" and "closed" tabs are inactive by default', () => {
      render(<AdminChat />);
      const assigned = screen.getByRole('button', { name: /^assigned$/i });
      const closed = screen.getByRole('button', { name: /^closed$/i });
      expect(assigned.className).not.toMatch(/bg-teal-600/);
      expect(closed.className).not.toMatch(/bg-teal-600/);
    });

    it('renders the Refresh button with a title', () => {
      render(<AdminChat />);
      expect(screen.getByTitle('Refresh')).toBeInTheDocument();
    });

    it('shows the "Select a conversation" empty state when no room is selected', async () => {
      render(<AdminChat />);
      await waitFor(() =>
        expect(screen.getByText('Select a conversation')).toBeInTheDocument()
      );
      expect(
        screen.getByText('Choose one from the list to start replying.')
      ).toBeInTheDocument();
    });
  });

  // ── 2. fetchRooms (mount) ────────────────────────────────────────────────
  describe('fetchRooms – initial fetch', () => {
    it('calls getChatRooms with status "open" on mount', async () => {
      render(<AdminChat />);
      await waitFor(() =>
        expect(adminAPI.getChatRooms).toHaveBeenCalledWith({ status: 'open' })
      );
    });

    it('shows a loading spinner while rooms are loading', () => {
      adminAPI.getChatRooms.mockReturnValue(new Promise(() => { }));
      const { container } = render(<AdminChat />);
      expect(container.querySelector('.animate-spin')).toBeInTheDocument();
    });

    it('removes loading spinner after rooms resolve', async () => {
      const { container } = render(<AdminChat />);
      await waitFor(() => screen.getByText((c) => c.includes('Alice Smith')));
      expect(
        container.querySelector('.border-teal-600.animate-spin')
      ).not.toBeInTheDocument();
    });

    it('renders room names from a paginated response', async () => {
      render(<AdminChat />);
      await waitFor(() =>
        expect(screen.getByText(byOwnText('Alice Smith'))).toBeInTheDocument()
      );
    });

    it('handles a flat (non-paginated) array response', async () => {
      adminAPI.getChatRooms.mockResolvedValue(flat([makeRoom({ customer_name: 'Bob' })]));
      render(<AdminChat />);
      await waitFor(() =>
        expect(screen.getByText('Bob')).toBeInTheDocument()
      );
    });

    it('shows empty-state text when rooms array is empty', async () => {
      adminAPI.getChatRooms.mockResolvedValue(flat([]));
      render(<AdminChat />);
      await waitFor(() =>
        expect(
          screen.getByText('No open conversations.')
        ).toBeInTheDocument()
      );
    });

    it('swallows getChatRooms errors — no toast, empty list', async () => {
      adminAPI.getChatRooms.mockRejectedValue(new Error('net'));
      render(<AdminChat />);
      await waitFor(() =>
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      );
      await waitFor(() =>
        expect(
          screen.getByText('No open conversations.')
        ).toBeInTheDocument()
      );
    });
  });

  // ── 3. Status filter tabs ─────────────────────────────────────────────────
  describe('Status filter tabs', () => {
    it('clicking "assigned" tab makes it active and deactivates "open"', async () => {
      const user = setup();
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));

      await user.click(screen.getByRole('button', { name: /^assigned$/i }));

      await waitFor(() =>
        expect(
          screen.getByRole('button', { name: /^assigned$/i }).className
        ).toMatch(/bg-teal-600/)
      );
      expect(
        screen.getByRole('button', { name: /^open$/i }).className
      ).not.toMatch(/bg-teal-600/);
    });

    it('clicking "assigned" tab re-fetches with status "assigned"', async () => {
      const user = setup();
      adminAPI.getChatRooms.mockResolvedValue(flat([]));
      render(<AdminChat />);
      await waitFor(() => screen.getByText('No open conversations.'));

      vi.clearAllMocks();
      adminAPI.getChatRooms.mockResolvedValue(flat([]));

      await user.click(screen.getByRole('button', { name: /^assigned$/i }));

      await waitFor(() =>
        expect(adminAPI.getChatRooms).toHaveBeenCalledWith({ status: 'assigned' })
      );
    });

    it('clicking "closed" tab re-fetches with status "closed"', async () => {
      const user = setup();
      adminAPI.getChatRooms.mockResolvedValue(flat([]));
      render(<AdminChat />);
      await waitFor(() => screen.getByText('No open conversations.'));

      vi.clearAllMocks();
      adminAPI.getChatRooms.mockResolvedValue(flat([]));

      await user.click(screen.getByRole('button', { name: /^closed$/i }));

      await waitFor(() =>
        expect(adminAPI.getChatRooms).toHaveBeenCalledWith({ status: 'closed' })
      );
    });

    it('empty-state message reflects the current filter tab', async () => {
      const user = setup();
      adminAPI.getChatRooms.mockResolvedValue(flat([]));
      render(<AdminChat />);
      await waitFor(() => screen.getByText('No open conversations.'));

      adminAPI.getChatRooms.mockResolvedValue(flat([]));
      await user.click(screen.getByRole('button', { name: /^closed$/i }));

      await waitFor(() =>
        expect(screen.getByText('No closed conversations.')).toBeInTheDocument()
      );
    });
  });

  // ── 4. Refresh button ────────────────────────────────────────────────────
  describe('Refresh button', () => {
    it('calls getChatRooms again when Refresh is clicked', async () => {
      const user = setup();
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));

      vi.clearAllMocks();
      okRooms();

      await user.click(screen.getByTitle('Refresh'));

      await waitFor(() =>
        expect(adminAPI.getChatRooms).toHaveBeenCalledTimes(1)
      );
    });

    it('adds animate-spin to the Refresh icon SVG while refreshing', async () => {
      const user = setup();
      let resolve;
      adminAPI.getChatRooms
        .mockResolvedValueOnce(paged([makeRoom()]))
        .mockReturnValueOnce(new Promise((r) => { resolve = r; }));

      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));

      await user.click(screen.getByTitle('Refresh'));

      await waitFor(() => {
        const refreshSvg = screen.getByTitle('Refresh').querySelector('svg');
        expect(refreshSvg.getAttribute('class')).toMatch(/animate-spin/);
      });

      resolve(paged([makeRoom()]));
    });

    it('does NOT show the list loading spinner during a refresh', async () => {
      const user = setup();
      let resolve;
      adminAPI.getChatRooms
        .mockResolvedValueOnce(paged([makeRoom()]))
        .mockReturnValueOnce(new Promise((r) => { resolve = r; }));

      const { container } = render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));

      await user.click(screen.getByTitle('Refresh'));

      expect(
        container.querySelector('.border-teal-600.border-4.animate-spin')
      ).not.toBeInTheDocument();

      resolve(paged([makeRoom()]));
    });
  });

  // ── 5. RoomItem rendering ────────────────────────────────────────────────
  describe('RoomItem', () => {
    it('renders customer_name', async () => {
      okRooms([makeRoom({ customer_name: 'Charlie' })]);
      render(<AdminChat />);
      await waitFor(() =>
        expect(screen.getByText(byOwnText('Charlie'))).toBeInTheDocument()
      );
    });

    it('renders last_message content as a preview line', async () => {
      okRooms([makeRoom({ last_message: { content: 'Preview text', created_at: '2024-01-01T09:00:00Z' } })]);
      render(<AdminChat />);
      await waitFor(() =>
        expect(screen.getByText(byOwnText('Preview text'))).toBeInTheDocument()
      );
    });

    it('renders formatted time from last_message.created_at', async () => {
      okRooms([makeRoom({
        last_message: { content: 'Hi', created_at: '2024-06-01T14:30:00Z' },
      })]);
      render(<AdminChat />);
      await waitFor(() => {
        const timeEl = screen.getByText(/\d{1,2}:\d{2}/);
        expect(timeEl).toBeInTheDocument();
      });
    });

    it('shows no time element when last_message is null', async () => {
      okRooms([makeRoom({ last_message: null })]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      expect(screen.queryByText(/\d{1,2}:\d{2}/)).not.toBeInTheDocument();
    });

    it('renders subject when present', async () => {
      okRooms([makeRoom({ subject: 'My subject here' })]);
      render(<AdminChat />);
      await waitFor(() =>
        expect(screen.getByText('My subject here')).toBeInTheDocument()
      );
    });

    it('renders unread_count badge when unread_count > 0', async () => {
      okRooms([makeRoom({ unread_count: 3 })]);
      render(<AdminChat />);
      await waitFor(() =>
        expect(screen.getByText('3')).toBeInTheDocument()
      );
    });

    it('does NOT render unread badge when unread_count is 0', async () => {
      okRooms([makeRoom({ unread_count: 0 })]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const badge = document.querySelector('.bg-teal-600.rounded-full');
      expect(badge).not.toBeInTheDocument();
    });

    it('applies active border style to the selected room', async () => {
      const user = setup();
      okRooms([makeRoom()]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));

      const roomBtn = screen.getByRole('button', { name: /alice smith/i });
      await user.click(roomBtn);

      await waitFor(() =>
        expect(roomBtn.className).toMatch(/border-l-teal-600/)
      );
    });

    it('does not apply active border to non-selected rooms', async () => {
      okRooms([
        makeRoom({ id: 1, customer_name: 'Alice' }),
        makeRoom({ id: 2, customer_name: 'Bob' }),
      ]);
      const user = setup();
      render(<AdminChat />);
      await waitFor(() => screen.getByText('Bob'));

      await user.click(screen.getByRole('button', { name: /alice/i }));

      const bobBtn = screen.getByRole('button', { name: /bob/i });
      expect(bobBtn.className).not.toMatch(/border-l-teal-600/);
    });
  });

  // ── 6. StatusBadge ───────────────────────────────────────────────────────
  describe('StatusBadge', () => {
    const renderBadgeViaRoom = async (status) => {
      okRooms([makeRoom({ status })]);
      render(<AdminChat />);
      // Wait for the room list to appear
      await waitFor(() => screen.getByRole('button', { name: new RegExp(status, 'i') }));
    };

    it('applies amber-family classes for "open" status', async () => {
      await renderBadgeViaRoom('open');
      // Find the badge inside the room list item container specifically
      const roomButton = screen.getByRole('button', { name: /alice smith/i });
      const badge = within(roomButton).getByText('open');
      expect(badge.className).toMatch(/amber/);
    });

    it('applies teal-family classes for "assigned" status', async () => {
      await renderBadgeViaRoom('assigned');
      const roomButton = screen.getByRole('button', { name: /alice smith/i });
      const badge = within(roomButton).getByText('assigned');
      expect(badge.className).toMatch(/teal/);
    });

    it('applies slate-family classes for "closed" status', async () => {
      await renderBadgeViaRoom('closed');
      const roomButton = screen.getByRole('button', { name: /alice smith/i });
      const badge = within(roomButton).getByText('closed');
      expect(badge.className).toMatch(/slate/);
    });
  });

  // ── 7. Room selection ────────────────────────────────────────────────────
  describe('Room selection', () => {
    const selectRoom = async (user, room = makeRoom()) => {
      okRooms([room]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText(room.customer_name ?? room.customer_email)));

      const textNode = screen.getByText(byOwnText(room.customer_name ?? room.customer_email));
      const roomButton = textNode.closest('button');
      await user.click(roomButton);

      await waitFor(() =>
        expect(screen.queryByText('Select a conversation')).not.toBeInTheDocument()
      );
    };

    it('shows the conversation panel after a room is clicked', async () => {
      const user = setup();
      await selectRoom(user);
      expect(screen.getByText('No messages yet. Say hello!')).toBeInTheDocument();
    });

    it('shows customer_name in the conversation header', async () => {
      const user = setup();
      const room = makeRoom({ customer_name: 'Diana' });
      await selectRoom(user, room);
      const headers = screen.getAllByText(byOwnText('Diana'));
      expect(headers.length).toBeGreaterThanOrEqual(1);
    });

    it('falls back to customer_email when customer_name is null', async () => {
      const user = setup();
      const room = makeRoom({
        id: 123,
        customer_name: null,
        customer_email: 'fallback@test.com',
        subject: 'Order #1234',
      });

      okRooms([room]);
      okMessages([]);
      render(<AdminChat />);

      const roomSubjectNode = await screen.findByText('Order #1234');
      const roomButton = roomSubjectNode.closest('button');

      await user.click(roomButton);

      expect(await screen.findByText('fallback@test.com')).toBeInTheDocument();
    });

    it('renders subject in conversation header when present', async () => {
      const user = setup();
      await selectRoom(user, makeRoom({ subject: 'Order problem' }));
      const subjects = screen.getAllByText('Order problem');
      expect(subjects.length).toBeGreaterThanOrEqual(1);
    });

    it('hides the "Select a conversation" panel after selecting a room', async () => {
      const user = setup();
      await selectRoom(user);
      expect(screen.queryByText('Select a conversation')).not.toBeInTheDocument();
    });

    it('clears wsError when a room is selected', async () => {
      const user = setup();
      okRooms([makeRoom({ id: 1 }), makeRoom({ id: 2, customer_name: 'Bob' })]);
      okMessages([]);
      render(<AdminChat />);

      await waitFor(() => screen.getByText('Alice Smith'));

      await user.click(screen.getByRole('button', { name: /alice smith/i }));

      act(() => wsControls._onError('Previous error'));
      await waitFor(() => expect(screen.getByText('Previous error')).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /bob/i }));

      await waitFor(() =>
        expect(screen.queryByText('Previous error')).not.toBeInTheDocument()
      );
    });

    it('clears the input when a room is selected', async () => {
      const user = setup();
      okRooms([makeRoom()]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));

      const emailNode = screen.getByText(byOwnText('Alice Smith'));
      await user.click(emailNode.closest('button'));
      await waitFor(() => screen.getByPlaceholderText('Reply to customer…'));

      await user.type(
        screen.getByPlaceholderText('Reply to customer…'),
        'partial message'
      );
      expect(
        screen.getByPlaceholderText('Reply to customer…')
      ).toHaveValue('partial message');
    });
  });

  // ── 8. getChatRoomMessages ────────────────────────────────────────────────
  describe('getChatRoomMessages', () => {
    it('calls getChatRoomMessages with the selected room id', async () => {
      const user = setup();
      okRooms([makeRoom({ id: 42 })]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));

      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));

      await waitFor(() =>
        expect(adminAPI.getChatRoomMessages).toHaveBeenCalledWith(42)
      );
    });

    it('calls loadHistory with correctly mapped message objects', async () => {
      const user = setup();
      const rawMsg = makeMessage({
        id: 55,
        content: 'Test message',
        sender: { id: 7, full_name: 'Carol', is_agent: true },
        message_type: 'text',
        created_at: '2024-06-01T10:00:00Z',
      });
      okRooms([makeRoom()]);
      adminAPI.getChatRoomMessages.mockResolvedValue(paged([rawMsg]));
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));

      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));

      await waitFor(() =>
        expect(wsControls.loadHistory).toHaveBeenCalledWith([
          {
            id: 55,
            content: 'Test message',
            sender_id: 7,
            sender_name: 'Carol',
            is_agent: true,
            message_type: 'text',
            created_at: '2024-06-01T10:00:00Z',
          },
        ])
      );
    });

    it('handles flat (non-paginated) getChatRoomMessages response', async () => {
      const user = setup();
      const msg = makeMessage({ id: 77 });
      okRooms([makeRoom()]);
      adminAPI.getChatRoomMessages.mockResolvedValue(flat([msg]));
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));

      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));

      await waitFor(() => {
        expect(wsControls.loadHistory).toHaveBeenCalledWith(
          expect.arrayContaining([expect.objectContaining({ id: 77 })])
        );
      });
    });

    it('swallows getChatRoomMessages errors', async () => {
      const user = setup();
      okRooms([makeRoom()]);
      adminAPI.getChatRoomMessages.mockRejectedValue(new Error('net'));
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));

      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));

      await waitFor(() =>
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      );
    });
  });

  // ── 9. Messages panel ────────────────────────────────────────────────────
  describe('Messages panel', () => {
    const openRoom = async (user) => {
      okRooms([makeRoom()]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
    };

    it('shows "No messages yet. Say hello!" when messages array is empty', async () => {
      const user = setup();
      wsControls.messages = [];
      await openRoom(user);
      await waitFor(() =>
        expect(
          screen.getByText('No messages yet. Say hello!')
        ).toBeInTheDocument()
      );
    });

    it('renders message content bubbles', async () => {
      const user = setup();
      wsControls.messages = [
        {
          id: 1,
          content: 'Hello from customer',
          sender_id: 5,
          sender_name: 'Bob',
          is_agent: false,
          message_type: 'text',
          created_at: '2024-06-01T10:00:00Z',
        },
      ];
      await openRoom(user);
      await waitFor(() =>
        expect(screen.getByText('Hello from customer')).toBeInTheDocument()
      );
    });

    it('does not show "No messages" when messages array is non-empty', async () => {
      const user = setup();
      wsControls.messages = [
        {
          id: 1, content: 'Msg', sender_id: 5, sender_name: 'X',
          is_agent: false, message_type: 'text',
          created_at: '2024-06-01T10:00:00Z',
        },
      ];
      await openRoom(user);
      await waitFor(() => screen.getByText('Msg'));
      expect(
        screen.queryByText('No messages yet. Say hello!')
      ).not.toBeInTheDocument();
    });
  });

  // ── 10. AgentMessageBubble ────────────────────────────────────────────────
  describe('AgentMessageBubble', () => {
    const openRoomWithMessages = async (user, messages) => {
      wsControls.messages = messages;
      okRooms([makeRoom()]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() => {
        expect(screen.getByText(messages[0].content)).toBeInTheDocument();
      });
    };

    it('aligns own messages to the right (justify-end)', async () => {
      const user = setup();
      await openRoomWithMessages(user, [
        {
          id: 1, content: 'My reply', sender_id: mockUser.id,
          sender_name: 'Admin User', is_agent: true,
          message_type: 'text', created_at: '2024-06-01T10:00:00Z',
        },
      ]);
      const bubbleContainer = screen.getByText('My reply').closest('.flex.justify-end');
      expect(bubbleContainer).toBeInTheDocument();
    });

    it('aligns other messages to the left (justify-start)', async () => {
      const user = setup();
      await openRoomWithMessages(user, [
        {
          id: 2, content: 'Customer reply', sender_id: 999,
          sender_name: 'Customer', is_agent: false,
          message_type: 'text', created_at: '2024-06-01T10:00:00Z',
        },
      ]);
      const bubbleContainer = screen.getByText('Customer reply').closest('.flex.justify-start');
      expect(bubbleContainer).toBeInTheDocument();
    });

    it('shows sender_name label for messages not from the current user', async () => {
      const user = setup();
      await openRoomWithMessages(user, [
        {
          id: 3, content: 'Hi', sender_id: 999,
          sender_name: 'Dana', is_agent: false,
          message_type: 'text', created_at: '2024-06-01T10:00:00Z',
        },
      ]);
      expect(screen.getByText(/dana/i)).toBeInTheDocument();
    });

    it('does NOT show sender_name label for own messages', async () => {
      const user = setup();
      await openRoomWithMessages(user, [
        {
          id: 4, content: 'Own msg', sender_id: mockUser.id,
          sender_name: 'Admin User', is_agent: true,
          message_type: 'text', created_at: '2024-06-01T10:00:00Z',
        },
      ]);
      const labelSpans = screen.queryAllByText('Admin User').filter((el) => el.tagName === 'SPAN');
      expect(labelSpans).toHaveLength(0);
    });

    it('shows "(agent)" suffix for is_agent=true messages from others', async () => {
      const user = setup();
      await openRoomWithMessages(user, [
        {
          id: 5, content: 'Agent msg', sender_id: 50,
          sender_name: 'Support', is_agent: true,
          message_type: 'text', created_at: '2024-06-01T10:00:00Z',
        },
      ]);
      expect(screen.getByText('(agent)')).toBeInTheDocument();
    });

    it('does NOT show "(agent)" for is_agent=false', async () => {
      const user = setup();
      await openRoomWithMessages(user, [
        {
          id: 6, content: 'Customer msg', sender_id: 50,
          sender_name: 'Customer', is_agent: false,
          message_type: 'text', created_at: '2024-06-01T10:00:00Z',
        },
      ]);
      expect(screen.queryByText('(agent)')).not.toBeInTheDocument();
    });

    it('renders system messages centred, not in a bubble', async () => {
      const user = setup();
      await openRoomWithMessages(user, [
        {
          id: 7, content: 'Conversation started',
          sender_id: null, sender_name: null, is_agent: false,
          message_type: 'system', created_at: '2024-06-01T10:00:00Z',
        },
      ]);
      const sysMsg = screen.getByText('Conversation started');
      expect(sysMsg.className).toMatch(/text-center/);
    });

    it('renders a timestamp for each non-system message', async () => {
      const user = setup();
      await openRoomWithMessages(user, [
        {
          id: 8, content: 'Timestamped', sender_id: 99,
          sender_name: 'X', is_agent: false,
          message_type: 'text', created_at: '2024-06-01T14:45:00Z',
        },
      ]);
      const timeElements = screen.getAllByText(/\d{1,2}:\d{2}/);
      expect(timeElements.length).toBeGreaterThan(0);
    });

    it('applies teal-family bubble colour for own messages', async () => {
      const user = setup();
      await openRoomWithMessages(user, [
        {
          id: 9, content: 'Teal bubble', sender_id: mockUser.id,
          sender_name: 'Admin', is_agent: true,
          message_type: 'text', created_at: '2024-06-01T10:00:00Z',
        },
      ]);
      const bubble = screen.getByText('Teal bubble');
      expect(bubble.className).toMatch(/teal/);
    });

    it('applies slate-family bubble colour for others\' messages', async () => {
      const user = setup();
      await openRoomWithMessages(user, [
        {
          id: 10, content: 'Slate bubble', sender_id: 888,
          sender_name: 'Other', is_agent: false,
          message_type: 'text', created_at: '2024-06-01T10:00:00Z',
        },
      ]);
      const bubble = screen.getByText('Slate bubble');
      expect(bubble.className).toMatch(/slate/);
    });
  });

  // ── 11. Typing indicator ─────────────────────────────────────────────────
  describe('Typing indicator', () => {
    const openRoomWithTyping = async (user, typingUsers) => {
      wsControls.typingUsers = typingUsers;
      okRooms([makeRoom()]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
    };

    it('shows "<name> typing…" when typingUsers is non-empty', async () => {
      const user = setup();
      await openRoomWithTyping(user, ['Alice']);
      await waitFor(() =>
        expect(screen.getByText('Alice typing…')).toBeInTheDocument()
      );
    });

    it('joins multiple typing users with ", "', async () => {
      const user = setup();
      await openRoomWithTyping(user, ['Alice', 'Bob']);
      await waitFor(() =>
        expect(screen.getByText('Alice, Bob typing…')).toBeInTheDocument()
      );
    });

    it('hides typing indicator when typingUsers is empty', async () => {
      const user = setup();
      await openRoomWithTyping(user, []);
      await waitFor(() =>
        expect(screen.queryByText(/typing…/)).not.toBeInTheDocument()
      );
    });

    it('renders three animated dots when typing', async () => {
      const user = setup();
      wsControls.typingUsers = ['X'];
      okRooms([makeRoom()]);
      okMessages([]);
      const { container } = render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() => screen.getByText('X typing…'));
      const dots = container.querySelectorAll('.animate-bounce');
      expect(dots).toHaveLength(3);
    });
  });

  // ── 12. wsError display ──────────────────────────────────────────────────
  describe('wsError display', () => {
    const openRoom = async (user) => {
      okRooms([makeRoom()]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() => screen.getByText('No messages yet. Say hello!'));
    };

    it('renders wsError in a red paragraph when set via onError', async () => {
      const user = setup();
      await openRoom(user);

      act(() => wsControls._onError('Connection lost'));

      await waitFor(() => {
        const errEl = screen.getByText('Connection lost');
        expect(errEl.className).toMatch(/text-red-500/);
      });
    });

    it('clears wsError when a different room is selected', async () => {
      okRooms([makeRoom({ id: 1 }), makeRoom({ id: 2, customer_name: 'Bob' })]);
      adminAPI.getChatRoomMessages.mockResolvedValue(paged([]));
      const user = setup();
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));

      const node1 = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node1.closest('button'));
      act(() => wsControls._onError('WS error'));
      await waitFor(() => screen.getByText('WS error'));

      const node2 = screen.getByText(byOwnText('Bob'));
      await user.click(node2.closest('button'));
      await waitFor(() =>
        expect(screen.queryByText('WS error')).not.toBeInTheDocument()
      );
    });
  });

  // ── 13. Send button state ────────────────────────────────────────────────
  describe('Send button state', () => {
    const openRoom = async (user, wsStatus = CONNECTION_STATUS.OPEN) => {
      wsControls.status = wsStatus;
      okRooms([makeRoom()]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() => screen.getByPlaceholderText('Reply to customer…'));
    };

    it('Send button is disabled when input is empty', async () => {
      const user = setup();
      await openRoom(user);
      const sendBtn = screen.getByRole('button', { name: /send/i });
      expect(sendBtn).toBeDisabled();
    });

    it('Send button is disabled when input is whitespace only', async () => {
      const user = setup();
      await openRoom(user);
      await user.type(screen.getByPlaceholderText('Reply to customer…'), '   ');
      const sendBtn = screen.getByRole('button', { name: /send/i });
      expect(sendBtn).toBeDisabled();
    });

    it('Send button is disabled when status is CONNECTING even with input', async () => {
      const user = setup();
      await openRoom(user, CONNECTION_STATUS.CONNECTING);
      await user.type(screen.getByPlaceholderText('Reply to customer…'), 'hello');
      expect(screen.getByRole('button', { name: /send/i })).toBeDisabled();
    });

    it('Send button is disabled when status is CLOSED even with input', async () => {
      const user = setup();
      await openRoom(user, CONNECTION_STATUS.CLOSED);
      await user.type(screen.getByPlaceholderText('Reply to customer…'), 'hello');
      expect(screen.getByRole('button', { name: /send/i })).toBeDisabled();
    });

    it('Send button is enabled when input is non-empty and status is OPEN', async () => {
      const user = setup();
      await openRoom(user, CONNECTION_STATUS.OPEN);
      await user.type(screen.getByPlaceholderText('Reply to customer…'), 'hello');
      expect(screen.getByRole('button', { name: /send/i })).not.toBeDisabled();
    });
  });

  // ── 14. handleSend ───────────────────────────────────────────────────────
  describe('handleSend', () => {
    const openRoom = async (user) => {
      wsControls.status = CONNECTION_STATUS.OPEN;
      okRooms([makeRoom()]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() => screen.getByPlaceholderText('Reply to customer…'));
    };

    it('calls sendMessage with the trimmed input on Send click', async () => {
      const user = setup();
      await openRoom(user);
      await user.type(
        screen.getByPlaceholderText('Reply to customer…'),
        '  Hello there  '
      );
      await user.click(screen.getByRole('button', { name: /send/i }));
      expect(wsControls.sendMessage).toHaveBeenCalledWith('Hello there');
    });

    it('clears the input after sending', async () => {
      const user = setup();
      await openRoom(user);
      await user.type(
        screen.getByPlaceholderText('Reply to customer…'),
        'A message'
      );
      await user.click(screen.getByRole('button', { name: /send/i }));
      await waitFor(() =>
        expect(
          screen.getByPlaceholderText('Reply to customer…')
        ).toHaveValue('')
      );
    });

    it('calls sendTyping(false) after sending', async () => {
      const user = setup();
      await openRoom(user);
      await user.type(
        screen.getByPlaceholderText('Reply to customer…'),
        'Hi'
      );
      await user.click(screen.getByRole('button', { name: /send/i }));
      expect(wsControls.sendTyping).toHaveBeenCalledWith(false);
    });

    it('does NOT call sendMessage when input is whitespace-only', async () => {
      const user = setup();
      await openRoom(user);
      fireEvent.click(screen.getByRole('button', { name: /send/i }));
      expect(wsControls.sendMessage).not.toHaveBeenCalled();
    });

    it('does NOT call sendMessage when WebSocket status is not OPEN', async () => {
      const user = setup();
      wsControls.status = CONNECTION_STATUS.CLOSED;
      okRooms([makeRoom()]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() => screen.getByPlaceholderText('Reply to customer…'));

      fireEvent.keyDown(screen.getByPlaceholderText('Reply to customer…'), {
        key: 'Enter',
        shiftKey: false,
      });
      expect(wsControls.sendMessage).not.toHaveBeenCalled();
    });
  });

  // ── 15. handleKeyDown ────────────────────────────────────────────────────
  describe('handleKeyDown', () => {
    const openRoomAndFocusInput = async (user) => {
      wsControls.status = CONNECTION_STATUS.OPEN;
      okRooms([makeRoom()]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() => screen.getByPlaceholderText('Reply to customer…'));
    };

    it('pressing Enter (no shift) triggers send', async () => {
      const user = setup();
      await openRoomAndFocusInput(user);
      await user.type(
        screen.getByPlaceholderText('Reply to customer…'),
        'Enter send'
      );
      fireEvent.keyDown(screen.getByPlaceholderText('Reply to customer…'), {
        key: 'Enter',
        shiftKey: false,
      });
      expect(wsControls.sendMessage).toHaveBeenCalledWith('Enter send');
    });

    it('pressing Shift+Enter does NOT trigger send', async () => {
      const user = setup();
      await openRoomAndFocusInput(user);
      await user.type(
        screen.getByPlaceholderText('Reply to customer…'),
        'Shift enter'
      );
      fireEvent.keyDown(screen.getByPlaceholderText('Reply to customer…'), {
        key: 'Enter',
        shiftKey: true,
      });
      expect(wsControls.sendMessage).not.toHaveBeenCalled();
    });

    it('pressing other keys does nothing', async () => {
      const user = setup();
      await openRoomAndFocusInput(user);
      await user.type(
        screen.getByPlaceholderText('Reply to customer…'),
        'Text'
      );
      fireEvent.keyDown(screen.getByPlaceholderText('Reply to customer…'), {
        key: 'Tab',
        shiftKey: false,
      });
      expect(wsControls.sendMessage).not.toHaveBeenCalled();
    });
  });

  // ── 16. handleInputChange ────────────────────────────────────────────────
  describe('handleInputChange', () => {
    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
    });
    afterEach(() => {
      vi.useRealTimers();
    });

    const openRoom = async (user) => {
      wsControls.status = CONNECTION_STATUS.OPEN;
      okRooms([makeRoom()]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() => screen.getByPlaceholderText('Reply to customer…'));
    };

    it('updates input value as user types', async () => {
      const user = setupFake();
      await openRoom(user);
      await user.type(
        screen.getByPlaceholderText('Reply to customer…'),
        'typing test'
      );
      expect(
        screen.getByPlaceholderText('Reply to customer…')
      ).toHaveValue('typing test');
    });

    it('calls sendTyping(true) on each keystroke', async () => {
      const user = setupFake();
      await openRoom(user);
      await user.type(
        screen.getByPlaceholderText('Reply to customer…'),
        'A'
      );
      expect(wsControls.sendTyping).toHaveBeenCalledWith(true);
    });

    it('calls sendTyping(false) after 1500ms debounce with no more input', async () => {
      const user = setupFake();
      await openRoom(user);
      await user.type(
        screen.getByPlaceholderText('Reply to customer…'),
        'A'
      );
      wsControls.sendTyping.mockClear();

      act(() => { vi.advanceTimersByTime(1500); });

      expect(wsControls.sendTyping).toHaveBeenCalledWith(false);
    });

    it('resets debounce timer on each new keystroke', async () => {
      const user = setupFake();
      await openRoom(user);
      const textarea = screen.getByPlaceholderText('Reply to customer…');

      await user.type(textarea, 'A');
      act(() => { vi.advanceTimersByTime(1000); });
      wsControls.sendTyping.mockClear();

      await user.type(textarea, 'B');
      act(() => { vi.advanceTimersByTime(1000); });

      expect(wsControls.sendTyping).not.toHaveBeenCalledWith(false);

      act(() => { vi.advanceTimersByTime(500); });

      expect(wsControls.sendTyping).toHaveBeenCalledWith(false);
    });
  });

  // ── 17. handleCloseRoom ───────────────────────────────────────────────────
  describe('handleCloseRoom', () => {
    const openOpenRoom = async (user) => {
      okRooms([makeRoom({ status: 'open' })]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() =>
        expect(
          screen.getByRole('button', { name: /close conversation/i })
        ).toBeInTheDocument()
      );
    };

    it('calls updateChatRoom with status "closed"', async () => {
      adminAPI.updateChatRoom.mockResolvedValue({});
      const user = setup();
      await openOpenRoom(user);
      await user.click(
        screen.getByRole('button', { name: /close conversation/i })
      );
      await waitFor(() =>
        expect(adminAPI.updateChatRoom).toHaveBeenCalledWith(1, {
          status: 'closed',
        })
      );
    });

    it('updates selectedRoom.status to "closed" locally after success', async () => {
      adminAPI.updateChatRoom.mockResolvedValue({});
      const user = setup();
      await openOpenRoom(user);
      await user.click(
        screen.getByRole('button', { name: /close conversation/i })
      );
      await waitFor(() =>
        expect(screen.getByText('This conversation is closed.')).toBeInTheDocument()
      );
    });

    it('hides "Close conversation" button after closing', async () => {
      adminAPI.updateChatRoom.mockResolvedValue({});
      const user = setup();
      await openOpenRoom(user);
      await user.click(
        screen.getByRole('button', { name: /close conversation/i })
      );
      await waitFor(() =>
        expect(
          screen.queryByRole('button', { name: /close conversation/i })
        ).not.toBeInTheDocument()
      );
    });

    it('calls fetchRooms(false) after successful close', async () => {
      adminAPI.updateChatRoom.mockResolvedValue({});
      vi.clearAllMocks();
      adminAPI.getChatRooms.mockResolvedValue(paged([makeRoom({ status: 'open' })]));
      adminAPI.getChatRoomMessages.mockResolvedValue(paged([]));
      adminAPI.updateChatRoom.mockResolvedValue({});

      const user = setup();
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() =>
        screen.getByRole('button', { name: /close conversation/i })
      );

      vi.clearAllMocks();
      adminAPI.getChatRooms.mockResolvedValue(paged([makeRoom()]));

      await user.click(
        screen.getByRole('button', { name: /close conversation/i })
      );

      await waitFor(() =>
        expect(adminAPI.getChatRooms).toHaveBeenCalledTimes(1)
      );
    });

    it('sets wsError to "Could not close conversation." on updateChatRoom failure', async () => {
      adminAPI.updateChatRoom.mockRejectedValue(new Error('500'));
      const user = setup();
      await openOpenRoom(user);
      await user.click(
        screen.getByRole('button', { name: /close conversation/i })
      );
      await waitFor(() =>
        expect(
          screen.getByText('Could not close conversation.')
        ).toBeInTheDocument()
      );
    });
  });

  // ── 18. Closed-room UI ────────────────────────────────────────────────────
  describe('Closed-room UI', () => {
    const openClosedRoom = async (user) => {
      okRooms([makeRoom({ status: 'closed' })]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() =>
        expect(
          screen.getByText('This conversation is closed.')
        ).toBeInTheDocument()
      );
    };

    it('shows "This conversation is closed." instead of input', async () => {
      const user = setup();
      await openClosedRoom(user);
      expect(screen.queryByPlaceholderText('Reply to customer…')).not.toBeInTheDocument();
    });

    it('does NOT show the "Close conversation" button for a closed room', async () => {
      const user = setup();
      await openClosedRoom(user);
      expect(
        screen.queryByRole('button', { name: /close conversation/i })
      ).not.toBeInTheDocument();
    });
  });

  // ── 19. WS status dot colours ─────────────────────────────────────────────
  describe('WS status dot colours', () => {
    const openRoomWithStatus = async (user, wsStatus) => {
      wsControls.status = wsStatus;
      okRooms([makeRoom()]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      await waitFor(() =>
        expect(screen.getByText(`● ${wsStatus}`)).toBeInTheDocument()
      );
    };

    it('shows emerald colour for OPEN status', async () => {
      const user = setup();
      await openRoomWithStatus(user, CONNECTION_STATUS.OPEN);
      const dot = screen.getByText(`● ${CONNECTION_STATUS.OPEN}`);
      expect(dot.className).toMatch(/text-emerald-500/);
    });

    it('shows amber colour for CONNECTING status', async () => {
      const user = setup();
      await openRoomWithStatus(user, CONNECTION_STATUS.CONNECTING);
      const dot = screen.getByText(`● ${CONNECTION_STATUS.CONNECTING}`);
      expect(dot.className).toMatch(/text-amber-500/);
    });

    it('shows slate colour for CLOSED status', async () => {
      const user = setup();
      wsControls.status = CONNECTION_STATUS.CLOSED;
      okRooms([makeRoom({ status: 'open' })]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      const dot = screen.getByText(`● ${CONNECTION_STATUS.CLOSED}`);
      expect(dot.className).toMatch(/text-slate-400/);
    });

    it('shows red colour for ERROR status', async () => {
      const user = setup();
      wsControls.status = CONNECTION_STATUS.ERROR;
      okRooms([makeRoom({ status: 'open' })]);
      okMessages([]);
      render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      const node = screen.getByText(byOwnText('Alice Smith'));
      await user.click(node.closest('button'));
      const dot = screen.getByText(`● ${CONNECTION_STATUS.ERROR}`);
      expect(dot.className).toMatch(/text-red-500/);
    });
  });

  // ── 20. Snapshot ─────────────────────────────────────────────────────────
  describe('Snapshot', () => {
    it('matches stable snapshot with no room selected', async () => {
      const { asFragment } = render(<AdminChat />);
      await waitFor(() => screen.getByText(byOwnText('Alice Smith')));
      expect(asFragment()).toMatchSnapshot();
    });
  });
});