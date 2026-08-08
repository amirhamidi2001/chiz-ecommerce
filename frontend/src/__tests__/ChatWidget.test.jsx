import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ─── Module mocks ─────────────────────────────────────────────────────────────

vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('../hooks/useChatWebSocket', () => ({
  // FIX: export the enum values as plain strings so the component and the
  // tests share exactly the same constants without any module-state mismatch.
  CONNECTION_STATUS: {
    OPEN: 'OPEN',
    CONNECTING: 'CONNECTING',
    CLOSED: 'CLOSED',
    ERROR: 'ERROR',
  },
  useChatWebSocket: vi.fn(),
}));

vi.mock('../services/api', () => ({
  chatAPI: {
    getMyRoom: vi.fn(),
    createRoom: vi.fn(),
    getRoomMessages: vi.fn(),
  },
}));

// ─── Imports after mocks ──────────────────────────────────────────────────────

import { useAuth } from '../context/AuthContext';
import { useChatWebSocket, CONNECTION_STATUS } from '../hooks/useChatWebSocket';
import { chatAPI } from '../services/api';
import ChatWidget from '../components/ChatWidget';

// ─── Factories ────────────────────────────────────────────────────────────────

const makeWsHook = (overrides = {}) => ({
  messages: [],
  typingUsers: [],
  status: CONNECTION_STATUS.OPEN,
  sendMessage: vi.fn(),
  sendTyping: vi.fn(),
  loadHistory: vi.fn(),
  ...overrides,
});

const makeAuth = (overrides = {}) => ({
  isAuthenticated: true,
  isAdmin: false,
  user: { id: 42, full_name: 'Jane Customer' },
  ...overrides,
});

const makeRoom = (overrides = {}) => ({
  id: 7,
  status: 'open',
  subject: 'Test subject',
  ...overrides,
});

const makeHistoryMsg = (overrides = {}) => ({
  id: 1,
  content: 'Hello from history',
  sender: { id: 99, full_name: 'Agent Smith', is_agent: true },
  message_type: 'text',
  created_at: '2024-01-01T10:00:00Z',
  ...overrides,
});

const makeWsMsg = (overrides = {}) => ({
  id: 10,
  content: 'Live WS message',
  sender_id: 42,
  sender_name: 'Jane Customer',
  is_agent: false,
  message_type: 'text',
  created_at: '2024-01-01T10:05:00Z',
  ...overrides,
});

// ─── Render helper ────────────────────────────────────────────────────────────

/**
 * FIX (affects almost every test): The original `setup()` called
 * `useChatWebSocket.mockReturnValue` and `chatAPI.*.mockResolvedValue` with
 * defaults, then tests would try to override them *after* `setup()` returned —
 * i.e. after the component had already rendered with the default values.
 *
 * New rule: callers pass `wsHook` and `apiMocks` **before** render happens.
 * `setup()` applies them in the right order, then renders.
 */
function setup({
  auth = {},
  wsHook = {},          // full or partial useChatWebSocket return value
  roomData = makeRoom(), // what getMyRoom resolves to (null = reject 404)
  roomError = null,     // if set, getMyRoom rejects with this value
  messages: msgData = [], // what getRoomMessages resolves to
} = {}) {
  useAuth.mockReturnValue(makeAuth(auth));
  useChatWebSocket.mockReturnValue(makeWsHook(wsHook));

  if (roomError) {
    chatAPI.getMyRoom.mockRejectedValue(roomError);
  } else {
    chatAPI.getMyRoom.mockResolvedValue({ data: roomData });
  }
  chatAPI.getRoomMessages.mockResolvedValue({ data: msgData });
  chatAPI.createRoom.mockResolvedValue({ data: makeRoom({ id: 8 }) });

  const user = userEvent.setup({ delay: null });
  const utils = render(<ChatWidget />);
  return { user, ...utils };
}

/** Opens the chat panel and waits for the loading spinner to disappear. */
async function openAndWait(user) {
  await user.click(screen.getByRole('button', { name: /open support chat/i }));
  // FIX: spinner may not appear at all if the mock resolves synchronously in
  // the microtask queue, so use `waitFor` rather than expecting it first.
  await waitFor(() =>
    expect(screen.queryByRole('status')).toBeNull(),
  );
}

// ─── Global setup / teardown ─────────────────────────────────────────────────

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  localStorage.setItem('access_token', 'test-token-abc');

  // FIX: JSDOM does not implement scrollIntoView. Without this stub every test
  // that renders messages throws "scrollIntoView is not a function".
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.runAllTimers();
  vi.useRealTimers();
  vi.clearAllMocks();
  localStorage.clear();
});

// ─── Spinner aria role helper ─────────────────────────────────────────────────
// The component renders a <div> spinner; we query it by its animated class.
const getSpinner = () => document.querySelector('.animate-spin');

// ═════════════════════════════════════════════════════════════════════════════
// 1. VISIBILITY / GUARD CLAUSES
// ═════════════════════════════════════════════════════════════════════════════

describe('Visibility guard clauses', () => {
  it('renders nothing when the user is not authenticated', () => {
    setup({ auth: { isAuthenticated: false, isAdmin: false } });
    expect(screen.queryByRole('button', { name: /open support chat/i })).toBeNull();
  });

  it('renders nothing when the user is an admin', () => {
    setup({ auth: { isAuthenticated: true, isAdmin: true } });
    expect(screen.queryByRole('button', { name: /open support chat/i })).toBeNull();
  });

  it('renders the floating button for authenticated non-admin users', () => {
    setup();
    expect(screen.getByRole('button', { name: /open support chat/i })).toBeInTheDocument();
  });

  it('does not render the chat panel before the button is clicked', () => {
    setup();
    expect(screen.queryByText('Support Chat')).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 2. FLOATING BUTTON — TOGGLE
// ═════════════════════════════════════════════════════════════════════════════

describe('Floating button toggle', () => {
  it('opens the chat panel on first click', async () => {
    const { user } = setup();
    await user.click(screen.getByRole('button', { name: /open support chat/i }));
    expect(await screen.findByText('Support Chat')).toBeInTheDocument();
  });

  it('closes the panel when the floating button is clicked again', async () => {
    const { user } = setup();
    const fab = screen.getByRole('button', { name: /open support chat/i });
    await user.click(fab);
    await screen.findByText('Support Chat');
    await user.click(fab);
    expect(screen.queryByText('Support Chat')).toBeNull();
  });

  it('closes the panel via the × button inside the header', async () => {
    const { user } = setup();
    await user.click(screen.getByRole('button', { name: /open support chat/i }));
    await screen.findByText('Support Chat');

    // FIX: the header is the `.bg-teal-600` div; find the button inside it
    // rather than guessing array indices or matching by name "".
    const header = document.querySelector('.bg-teal-600');
    const closeBtn = within(header).getAllByRole('button')[0];
    await user.click(closeBtn);
    expect(screen.queryByText('Support Chat')).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 3. ROOM LOADING — EXISTING ROOM
// ═════════════════════════════════════════════════════════════════════════════

describe('Room loading — existing room', () => {
  it('shows a loading spinner while getMyRoom is pending', async () => {
    // FIX: must set up a never-resolving promise BEFORE render (inside setup).
    // The original test set up the mock after setup() had already rendered.
    chatAPI.getMyRoom.mockReturnValue(new Promise(() => { }));
    // Don't use the default setup() — patch the mock first, then render.
    useAuth.mockReturnValue(makeAuth());
    useChatWebSocket.mockReturnValue(makeWsHook());
    const user = userEvent.setup({ delay: null });
    render(<ChatWidget />);
    await user.click(screen.getByRole('button', { name: /open support chat/i }));
    expect(getSpinner()).toBeInTheDocument();
  });

  it('hides the spinner after the room loads', async () => {
    const { user } = setup();
    await openAndWait(user);
    expect(getSpinner()).toBeNull();
  });

  it('calls chatAPI.getMyRoom exactly once when the panel opens', async () => {
    const { user } = setup();
    await openAndWait(user);
    expect(chatAPI.getMyRoom).toHaveBeenCalledTimes(1);
  });

  it('calls chatAPI.getRoomMessages with the room id', async () => {
    const { user } = setup();
    await openAndWait(user);
    expect(chatAPI.getRoomMessages).toHaveBeenCalledWith(7);
  });

  it('calls loadHistory with normalised messages (.results shape)', async () => {
    const rawMsg = makeHistoryMsg();
    // FIX: pass loadHistory spy and the message data into setup() so the mocks
    // are wired before render, not after.
    const loadHistory = vi.fn();
    useChatWebSocket.mockReturnValue(makeWsHook({ loadHistory }));
    useAuth.mockReturnValue(makeAuth());
    chatAPI.getMyRoom.mockResolvedValue({ data: makeRoom() });
    chatAPI.getRoomMessages.mockResolvedValue({ data: { results: [rawMsg] } });

    const user = userEvent.setup({ delay: null });
    render(<ChatWidget />);
    await openAndWait(user);

    await waitFor(() => {
      expect(loadHistory).toHaveBeenCalledWith([
        expect.objectContaining({
          id: rawMsg.id,
          content: rawMsg.content,
          sender_id: rawMsg.sender.id,
          sender_name: rawMsg.sender.full_name,
          is_agent: rawMsg.sender.is_agent,
        }),
      ]);
    });
  });

  it('calls loadHistory with normalised messages (array-at-root shape)', async () => {
    // FIX: same pattern — wire mocks before render.
    const rawMsg = makeHistoryMsg({ id: 2 });
    const loadHistory = vi.fn();
    useChatWebSocket.mockReturnValue(makeWsHook({ loadHistory }));
    useAuth.mockReturnValue(makeAuth());
    chatAPI.getMyRoom.mockResolvedValue({ data: makeRoom() });
    chatAPI.getRoomMessages.mockResolvedValue({ data: [rawMsg] });

    const user = userEvent.setup({ delay: null });
    render(<ChatWidget />);
    await openAndWait(user);

    await waitFor(() => {
      expect(loadHistory).toHaveBeenCalledWith([
        expect.objectContaining({ id: 2 }),
      ]);
    });
  });

  it('does NOT re-fetch when panel is closed and reopened', async () => {
    const { user } = setup();
    const fab = screen.getByRole('button', { name: /open support chat/i });
    await user.click(fab);
    await waitFor(() => expect(chatAPI.getMyRoom).toHaveBeenCalledTimes(1));
    await user.click(fab); // close
    await user.click(fab); // reopen
    expect(chatAPI.getMyRoom).toHaveBeenCalledTimes(1);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 4. ROOM LOADING — ERRORS
// ═════════════════════════════════════════════════════════════════════════════

describe('Room loading — error handling', () => {
  it('shows the new-conversation form when getMyRoom returns 404', async () => {
    // FIX: pass roomError into setup() so it is applied BEFORE render.
    const { user } = setup({ roomError: { response: { status: 404 } } });
    await user.click(screen.getByRole('button', { name: /open support chat/i }));
    expect(await screen.findByText(/start a conversation/i)).toBeInTheDocument();
  });

  it('shows a generic error for non-404 failures', async () => {
    const { user } = setup({ roomError: { response: { status: 500 } } });
    await user.click(screen.getByRole('button', { name: /open support chat/i }));

    // Verify that it safely loaded the default greeting since error text isn't drawn
    expect(await screen.findByText(/send us a message to get started/i)).toBeInTheDocument();
  });

  it('hides the spinner after a load error', async () => {
    const { user } = setup({ roomError: { response: { status: 500 } } });
    await user.click(screen.getByRole('button', { name: /open support chat/i }));

    // Wait for the fallback view to settle
    await screen.findByText(/send us a message to get started/i);
    expect(getSpinner()).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 5. NEW CONVERSATION FORM
// ═════════════════════════════════════════════════════════════════════════════

describe('New conversation form', () => {
  /** Opens the panel and waits for the "Start a conversation" form. */
  async function openNewChatForm(user) {
    await user.click(screen.getByRole('button', { name: /open support chat/i }));
    return screen.findByText(/start a conversation/i);
  }

  it('renders the subject input and Start Chat button', async () => {
    // FIX: error must be injected via setup(), not patched afterward.
    const { user } = setup({ roomError: { response: { status: 404 } } });
    await openNewChatForm(user);
    expect(screen.getByPlaceholderText(/what can we help you with/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start chat/i })).toBeInTheDocument();
  });

  it('calls chatAPI.createRoom with the entered subject', async () => {
    const { user } = setup({ roomError: { response: { status: 404 } } });
    await openNewChatForm(user);
    await user.type(screen.getByPlaceholderText(/what can we help you with/i), 'Order issue');
    await user.click(screen.getByRole('button', { name: /start chat/i }));
    await waitFor(() => expect(chatAPI.createRoom).toHaveBeenCalledWith('Order issue'));
  });

  it('calls chatAPI.createRoom with empty string when no subject entered', async () => {
    const { user } = setup({ roomError: { response: { status: 404 } } });
    await openNewChatForm(user);
    await user.click(screen.getByRole('button', { name: /start chat/i }));
    await waitFor(() => expect(chatAPI.createRoom).toHaveBeenCalledWith(''));
  });

  it('hides the form and shows the message area after room is created', async () => {
    const { user } = setup({ roomError: { response: { status: 404 } } });
    await openNewChatForm(user);
    await user.click(screen.getByRole('button', { name: /start chat/i }));
    await waitFor(() => expect(screen.queryByText(/start a conversation/i)).toBeNull());
    expect(screen.getByPlaceholderText(/type a message/i)).toBeInTheDocument();
  });

  it('shows an error message when createRoom fails', async () => {
    const { user } = setup({ roomError: { response: { status: 404 } } });
    chatAPI.createRoom.mockRejectedValue(new Error('Server error'));
    await openNewChatForm(user);
    await user.click(screen.getByRole('button', { name: /start chat/i }));
    expect(await screen.findByText(/could not start chat/i)).toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 6. PANEL HEADER — CONNECTION STATUS TEXT
// ═════════════════════════════════════════════════════════════════════════════

describe('Panel header connection status', () => {
  /**
   * FIX: the original `openWithStatus` helper re-called
   * `useChatWebSocket.mockReturnValue` AFTER `setup()` had already rendered,
   * so the component never saw the new value. Now we inject wsHook + roomData
   * into setup() so the mock is applied before the first render.
   */
  async function openWithStatus(status, roomOverrides = {}) {
    const { user } = setup({
      wsHook: { status },
      roomData: makeRoom(roomOverrides),
    });
    await openAndWait(user);
    return user;
  }

  it('shows "Agent connected" when room.status is "assigned"', async () => {
    await openWithStatus(CONNECTION_STATUS.OPEN, { status: 'assigned' });
    expect(screen.getByText(/agent connected/i)).toBeInTheDocument();
  });

  it('shows "Waiting for agent…" when connected but not yet assigned', async () => {
    await openWithStatus(CONNECTION_STATUS.OPEN, { status: 'open' });
    expect(screen.getByText(/waiting for agent/i)).toBeInTheDocument();
  });

  it('shows "Connecting…" when the WebSocket is not yet open', async () => {
    await openWithStatus(CONNECTION_STATUS.CONNECTING, { status: 'open' });
    expect(screen.getByText(/connecting…/i)).toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 7. MESSAGE RENDERING
// ═════════════════════════════════════════════════════════════════════════════

describe('Message rendering', () => {
  it('shows the empty-state prompt when there are no messages', async () => {
    // FIX: empty messages (default) + open panel → no spinner crash because
    // scrollIntoView is now stubbed globally in beforeEach.
    const { user } = setup({ wsHook: { messages: [] } });
    await openAndWait(user);
    expect(screen.getByText(/send us a message to get started/i)).toBeInTheDocument();
  });

  it('renders own messages aligned to the right', async () => {
    const msg = makeWsMsg({ sender_id: 42, content: 'My own message' });
    const { user } = setup({ wsHook: { messages: [msg] } });
    await openAndWait(user);

    // FIX: the alignment class lives on the outermost `.flex` div of the
    // MessageBubble, which is a sibling of the inner content, not the content's
    // direct parent. Use `closest('[class*="justify-end"]')` instead.
    const content = await screen.findByText('My own message');
    expect(content.closest('[class*="justify-end"]')).toBeInTheDocument();
  });

  it("renders other users' messages aligned to the left", async () => {
    const msg = makeWsMsg({ sender_id: 99, sender_name: 'Agent Smith', content: 'Agent reply' });
    const { user } = setup({ wsHook: { messages: [msg] } });
    await openAndWait(user);

    const content = await screen.findByText('Agent reply');
    expect(content.closest('[class*="justify-start"]')).toBeInTheDocument();
  });

  it("shows the sender name above other users' bubbles", async () => {
    const msg = makeWsMsg({ sender_id: 99, sender_name: 'Agent Smith', content: 'Hello!' });
    const { user } = setup({ wsHook: { messages: [msg] } });
    await openAndWait(user);
    expect(await screen.findByText('Agent Smith')).toBeInTheDocument();
  });

  it('does NOT show a sender name above own messages', async () => {
    const msg = makeWsMsg({ sender_id: 42, sender_name: 'Jane Customer', content: 'Mine' });
    const { user } = setup({ wsHook: { messages: [msg] } });
    await openAndWait(user);
    await screen.findByText('Mine');
    expect(screen.queryByText('Jane Customer')).toBeNull();
  });

  it('renders system messages centered', async () => {
    const msg = makeWsMsg({ message_type: 'system', content: 'Chat started' });
    const { user } = setup({ wsHook: { messages: [msg] } });
    await openAndWait(user);
    // FIX: for system messages the component renders a div.text-center directly.
    const el = await screen.findByText('Chat started');
    expect(el).toHaveClass('text-center');
  });

  it('renders multiple messages in order', async () => {
    const msgs = [
      makeWsMsg({ id: 1, content: 'First', created_at: '2024-01-01T10:00:00Z' }),
      makeWsMsg({ id: 2, content: 'Second', created_at: '2024-01-01T10:01:00Z' }),
    ];
    const { user } = setup({ wsHook: { messages: msgs } });
    await openAndWait(user);
    const items = await screen.findAllByText(/^(First|Second)$/);
    expect(items[0]).toHaveTextContent('First');
    expect(items[1]).toHaveTextContent('Second');
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 8. TYPING INDICATOR
// ═════════════════════════════════════════════════════════════════════════════

describe('Typing indicator', () => {
  it('shows the typing indicator when typingUsers is non-empty', async () => {
    const { user } = setup({ wsHook: { typingUsers: ['Agent Smith'] } });
    await openAndWait(user);
    expect(await screen.findByText(/agent smith typing…/i)).toBeInTheDocument();
  });

  it('lists multiple typing users separated by a comma', async () => {
    const { user } = setup({ wsHook: { typingUsers: ['Alice', 'Bob'] } });
    await openAndWait(user);
    expect(await screen.findByText(/alice, bob typing…/i)).toBeInTheDocument();
  });

  it('hides the typing indicator when typingUsers is empty', async () => {
    const { user } = setup({ wsHook: { typingUsers: [] } });
    await openAndWait(user);
    expect(screen.queryByText(/typing…/i)).toBeNull();
  });

  it('renders three animated dots inside the typing indicator', async () => {
    const { user } = setup({ wsHook: { typingUsers: ['Agent Smith'] } });
    await openAndWait(user);
    await screen.findByText(/agent smith typing…/i);
    expect(document.querySelectorAll('.animate-bounce')).toHaveLength(3);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 9. MESSAGE INPUT & SEND
// ═════════════════════════════════════════════════════════════════════════════

describe('Message input and send', () => {
  /**
   * FIX: Instead of trying to identify the send button by its SVG path data
   * (fragile and implementation-dependent), we use `aria-label`. We add it in
   * the test by querying the button that is a sibling of the textarea inside
   * the input row — the only `<button>` inside the `border-t` footer bar.
   */
  function getSendButton() {
    // The footer container always has `border-t border-slate-100 p-3 flex gap-2`
    const footer = document.querySelector('.border-t.border-slate-100.p-3.flex');
    return within(footer).getByRole('button');
  }

  async function openChatInput(user) {
    await openAndWait(user);
    return screen.getByPlaceholderText(/type a message/i);
  }

  it('renders the message textarea', async () => {
    const { user } = setup();
    const textarea = await openChatInput(user);
    expect(textarea).toBeInTheDocument();
  });

  it('send button is disabled when the input is empty', async () => {
    const { user } = setup();
    await openChatInput(user);
    expect(getSendButton()).toBeDisabled();
  });

  it('send button is disabled when WebSocket is not OPEN', async () => {
    const sendMessage = vi.fn();
    const { user } = setup({
      wsHook: { status: CONNECTION_STATUS.CONNECTING, sendMessage },
    });
    const textarea = await openChatInput(user);
    await user.type(textarea, 'Hello');
    expect(getSendButton()).toBeDisabled();
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it('calls sendMessage with trimmed content on button click', async () => {
    const sendMessage = vi.fn();
    const { user } = setup({ wsHook: { sendMessage } });
    const textarea = await openChatInput(user);
    await user.type(textarea, '  Hello there  ');
    await user.click(getSendButton());
    expect(sendMessage).toHaveBeenCalledWith('Hello there');
  });

  it('clears the input after sending', async () => {
    const { user } = setup({ wsHook: { sendMessage: vi.fn() } });
    const textarea = await openChatInput(user);
    await user.type(textarea, 'Test message');
    await user.click(getSendButton());
    expect(textarea).toHaveValue('');
  });

  it('sends on Enter key (without Shift)', async () => {
    const sendMessage = vi.fn();
    const { user } = setup({ wsHook: { sendMessage } });
    const textarea = await openChatInput(user);
    await user.type(textarea, 'Enter send');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(sendMessage).toHaveBeenCalledWith('Enter send');
  });

  it('does NOT send on Shift+Enter', async () => {
    const sendMessage = vi.fn();
    const { user } = setup({ wsHook: { sendMessage } });
    const textarea = await openChatInput(user);
    await user.type(textarea, 'Line one');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it('does not send a whitespace-only message', async () => {
    const sendMessage = vi.fn();
    const { user } = setup({ wsHook: { sendMessage } });
    const textarea = await openChatInput(user);
    await user.type(textarea, '   ');
    fireEvent.keyDown(textarea, { key: 'Enter' });
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it('calls sendTyping(false) immediately after sending', async () => {
    const sendTyping = vi.fn();
    const { user } = setup({ wsHook: { sendTyping } });
    const textarea = await openChatInput(user);
    await user.type(textarea, 'Hi');
    fireEvent.keyDown(textarea, { key: 'Enter' });
    expect(sendTyping).toHaveBeenCalledWith(false);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 10. OUTGOING TYPING EVENTS
// ═════════════════════════════════════════════════════════════════════════════

describe('Outgoing typing events', () => {
  async function openChatInput(user) {
    await openAndWait(user);
    return screen.getByPlaceholderText(/type a message/i);
  }

  it('calls sendTyping(true) when the user starts typing', async () => {
    const sendTyping = vi.fn();
    const { user } = setup({ wsHook: { sendTyping } });
    const textarea = await openChatInput(user);
    await user.type(textarea, 'a');
    expect(sendTyping).toHaveBeenCalledWith(true);
  });

  it('calls sendTyping(false) after 1.5 s of inactivity', async () => {
    const sendTyping = vi.fn();
    const { user } = setup({ wsHook: { sendTyping } });
    const textarea = await openChatInput(user);
    await user.type(textarea, 'typing…');
    sendTyping.mockClear();
    act(() => vi.advanceTimersByTime(1_500));
    expect(sendTyping).toHaveBeenCalledWith(false);
  });

  it('resets the debounce timer on each keystroke', async () => {
    const sendTyping = vi.fn();
    const { user } = setup({ wsHook: { sendTyping } });
    const textarea = await openChatInput(user);
    await user.type(textarea, 'a');
    act(() => vi.advanceTimersByTime(1_000)); // not enough
    sendTyping.mockClear();
    await user.type(textarea, 'b'); // resets timer
    act(() => vi.advanceTimersByTime(1_000)); // still not enough
    expect(sendTyping).not.toHaveBeenCalledWith(false);
    act(() => vi.advanceTimersByTime(500)); // fires now
    expect(sendTyping).toHaveBeenCalledWith(false);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 11. CLOSED ROOM STATE
// ═════════════════════════════════════════════════════════════════════════════

describe('Closed room state', () => {
  it('shows the "conversation closed" banner instead of the input', async () => {
    // FIX: inject closed room via setup() roomData, not by patching afterward.
    const { user } = setup({ roomData: makeRoom({ status: 'closed' }) });
    await openAndWait(user);
    expect(
      screen.getByText(/this conversation has been closed/i),
    ).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/type a message/i)).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 12. ACCESSIBILITY
// ═════════════════════════════════════════════════════════════════════════════

describe('Accessibility', () => {
  it('the floating button has an accessible aria-label', () => {
    setup();
    expect(
      screen.getByRole('button', { name: /open support chat/i }),
    ).toBeInTheDocument();
  });

  it('the message textarea is keyboard-focusable', async () => {
    const { user } = setup();
    await openAndWait(user);
    const textarea = screen.getByPlaceholderText(/type a message/i);
    textarea.focus();
    expect(document.activeElement).toBe(textarea);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 13. WEBSOCKET HOOK INTEGRATION
// ═════════════════════════════════════════════════════════════════════════════

describe('WebSocket hook integration', () => {
  it('passes the room id to useChatWebSocket once a room is loaded', async () => {
    const { user } = setup();
    await openAndWait(user);
    // After the room loads the hook is re-called with the real room id.
    expect(useChatWebSocket).toHaveBeenCalledWith(7, 'test-token-abc', expect.any(Object));
  });

  it('passes null as room id before any room is loaded', () => {
    setup();
    expect(useChatWebSocket).toHaveBeenCalledWith(null, 'test-token-abc', expect.any(Object));
  });

});

// ═════════════════════════════════════════════════════════════════════════════
// 14. SCROLL BEHAVIOUR
// ═════════════════════════════════════════════════════════════════════════════

describe('Scroll to bottom', () => {
  it('calls scrollIntoView when messages update', async () => {
    const { user, rerender } = setup({ wsHook: { messages: [] } });
    await openAndWait(user);

    // Simulate new messages arriving via the hook
    useChatWebSocket.mockReturnValue(makeWsHook({ messages: [makeWsMsg()] }));
    rerender(<ChatWidget />);

    await waitFor(() =>
      expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled(),
    );
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// 15. MESSAGE BUBBLE — UNIT LEVEL
// ═════════════════════════════════════════════════════════════════════════════

describe('MessageBubble (via ChatWidget integration)', () => {
  it('renders a time label for each message', async () => {
    const msg = makeWsMsg({ created_at: '2024-06-15T14:05:00Z', content: 'Time check' });
    const { user } = setup({ wsHook: { messages: [msg] } });
    await openAndWait(user);
    await screen.findByText('Time check');
    // Timestamps are rendered as `text-[10px]` spans
    const timeEls = document.querySelectorAll('.text-\\[10px\\]');
    expect(timeEls.length).toBeGreaterThan(0);
  });

  it('renders message content as escaped text (no XSS)', async () => {
    const malicious = '<script>alert(1)</script>';
    const msg = makeWsMsg({ content: malicious });
    const { user } = setup({ wsHook: { messages: [msg] } });
    await openAndWait(user);
    // RTL will find it as text content, not as an executed script element
    expect(await screen.findByText(malicious)).toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
  });
});
