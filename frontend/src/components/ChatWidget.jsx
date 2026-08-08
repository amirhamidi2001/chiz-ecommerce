import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { chatAPI } from '../services/api';
import { useChatWebSocket, CONNECTION_STATUS } from '../hooks/useChatWebSocket';

// ─── Tiny icon components (inline SVG — no extra dep) ──────────────────────

const IconChat = () => (
  <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
  </svg>
);

const IconX = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const IconSend = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
  </svg>
);

// ─── Status dot ─────────────────────────────────────────────────────────────

const statusColors = {
  [CONNECTION_STATUS.OPEN]: 'bg-emerald-400',
  [CONNECTION_STATUS.CONNECTING]: 'bg-amber-400 animate-pulse',
  [CONNECTION_STATUS.CLOSED]: 'bg-slate-400',
  [CONNECTION_STATUS.ERROR]: 'bg-red-400',
};

// ─── Single message bubble ───────────────────────────────────────────────────

function MessageBubble({ msg, currentUserId }) {
  const isOwn = msg.sender_id === currentUserId;
  const time = new Date(msg.created_at).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  if (msg.message_type === 'system') {
    return (
      <div className="text-center text-xs text-slate-400 my-2 px-4">{msg.content}</div>
    );
  }

  return (
    <div className={`flex ${isOwn ? 'justify-end' : 'justify-start'} mb-2`}>
      <div className={`max-w-[75%] ${isOwn ? 'items-end' : 'items-start'} flex flex-col`}>
        {!isOwn && (
          <span className="text-xs text-slate-500 mb-0.5 px-1">
            {msg.sender_name}
          </span>
        )}
        <div
          className={`px-3 py-2 rounded-2xl text-sm leading-relaxed break-words ${
            isOwn
              ? 'bg-teal-600 text-white rounded-br-sm'
              : 'bg-slate-100 text-slate-800 rounded-bl-sm'
          }`}
        >
          {msg.content}
        </div>
        <span className="text-[10px] text-slate-400 mt-0.5 px-1">{time}</span>
      </div>
    </div>
  );
}

// ─── Main widget ─────────────────────────────────────────────────────────────

export default function ChatWidget() {
  const { isAuthenticated, isAdmin, user } = useAuth();
  const [open, setOpen] = useState(false);
  const [room, setRoom] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [input, setInput] = useState('');
  const [subject, setSubject] = useState('');
  const [showNewForm, setShowNewForm] = useState(false);
  const messagesEndRef = useRef(null);
  const typingTimer = useRef(null);
  const token = localStorage.getItem('access_token');

  const { messages, typingUsers, status, sendMessage, sendTyping, loadHistory } =
    useChatWebSocket(room?.id ?? null, token, {
      onError: (msg) => setError(msg),
    });

  // ── Fetch or create room on open ──────────────────────────────────────────

  useEffect(() => {
    if (open && !room) {
      setLoading(true);
      chatAPI
        .getMyRoom()
        .then((res) => {
          setRoom(res.data);
          return chatAPI.getRoomMessages(res.data.id);
        })
        .then((res) => {
          loadHistory(
            res.data.results?.map(normaliseHistoryMsg) ??
              res.data.map(normaliseHistoryMsg),
          );
        })
        .catch((err) => {
          if (err.response?.status === 404) setShowNewForm(true);
          else setError('Could not load chat.');
        })
        .finally(() => setLoading(false));
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Scroll to bottom on new messages ─────────────────────────────────────

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Don't render for guests or admins ────────────────────────────────────

  if (!isAuthenticated || isAdmin) return null;

  // ── Helpers ───────────────────────────────────────────────────────────────

  const normaliseHistoryMsg = (m) => ({
    id: m.id,
    content: m.content,
    sender_id: m.sender?.id,
    sender_name: m.sender?.full_name,
    is_agent: m.sender?.is_agent,
    message_type: m.message_type,
    created_at: m.created_at,
  });

  const handleStartChat = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await chatAPI.createRoom(subject);
      setRoom(res.data);
      setShowNewForm(false);
    } catch {
      setError('Could not start chat. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || status !== CONNECTION_STATUS.OPEN) return;
    sendMessage(trimmed);
    setInput('');
    sendTyping(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputChange = (e) => {
    setInput(e.target.value);
    sendTyping(true);
    clearTimeout(typingTimer.current);
    typingTimer.current = setTimeout(() => sendTyping(false), 1_500);
  };

  const unreadCount = 0; // could be tracked via a ref if needed

  return (
    <>
      {/* ── Chat panel ─────────────────────────────────────────────────── */}
      {open && (
        <div className="fixed bottom-20 right-4 z-50 w-80 sm:w-96 bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-slate-200"
          style={{ height: '480px' }}
        >
          {/* Header */}
          <div className="bg-teal-600 text-white px-4 py-3 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2">
              <div className={`w-2.5 h-2.5 rounded-full ${statusColors[status]}`} />
              <div>
                <p className="font-semibold text-sm leading-none">Support Chat</p>
                <p className="text-teal-200 text-xs mt-0.5">
                  {room?.status === 'assigned'
                    ? 'Agent connected'
                    : status === CONNECTION_STATUS.OPEN
                    ? 'Waiting for agent…'
                    : 'Connecting…'}
                </p>
              </div>
            </div>
            <button onClick={() => setOpen(false)}
              className="p-1 rounded-lg hover:bg-teal-700 transition-colors"
            >
              <IconX />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-hidden flex flex-col">
            {loading ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="w-8 h-8 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : showNewForm ? (
              /* New conversation form */
              <div className="flex-1 flex flex-col items-center justify-center p-6 gap-4">
                <div className="text-center">
                  <h3 className="font-semibold text-slate-800">Start a conversation</h3>
                  <p className="text-sm text-slate-500 mt-1">
                    Our support team typically replies within a few minutes.
                  </p>
                </div>
                <input
                  type="text"
                  placeholder="What can we help you with? (optional)"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
                {error && <p className="text-red-500 text-xs">{error}</p>}
                <button
                  onClick={handleStartChat}
                  disabled={loading}
                  className="w-full bg-teal-600 hover:bg-teal-700 text-white rounded-xl py-2.5 text-sm font-medium transition-colors disabled:opacity-50"
                >
                  Start Chat
                </button>
              </div>
            ) : (
              <>
                {/* Messages */}
                <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
                  {messages.length === 0 && (
                    <div className="text-center text-sm text-slate-400 mt-8">
                      <p>👋 Hi there!</p>
                      <p className="mt-1">Send us a message to get started.</p>
                    </div>
                  )}
                  {messages.map((msg) => (
                    <MessageBubble
                      key={msg.id ?? `${msg.sender_id}-${msg.created_at}`}
                      msg={msg}
                      currentUserId={user?.id}
                    />
                  ))}
                  {typingUsers.length > 0 && (
                    <div className="flex items-center gap-1 text-xs text-slate-400 px-1">
                      <span className="flex gap-0.5">
                        {[0, 1, 2].map((i) => (
                          <span
                            key={i}
                            className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce"
                            style={{ animationDelay: `${i * 150}ms` }}
                          />
                        ))}
                      </span>
                      <span>{typingUsers.join(', ')} typing…</span>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                {room?.status !== 'closed' ? (
                  <div className="border-t border-slate-100 p-3 flex gap-2 flex-shrink-0">
                    <textarea
                      rows={1}
                      value={input}
                      onChange={handleInputChange}
                      onKeyDown={handleKeyDown}
                      placeholder="Type a message…"
                      className="flex-1 resize-none border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 max-h-24 overflow-y-auto"
                    />
                    <button
                      onClick={handleSend}
                      disabled={!input.trim() || status !== CONNECTION_STATUS.OPEN}
                      className="bg-teal-600 hover:bg-teal-700 text-white rounded-xl p-2.5 transition-colors disabled:opacity-40 flex-shrink-0"
                    >
                      <IconSend />
                    </button>
                  </div>
                ) : (
                  <div className="border-t border-slate-100 p-3 text-center text-sm text-slate-400 flex-shrink-0">
                    This conversation has been closed.
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Floating button ────────────────────────────────────────────── */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-4 right-4 z-50 w-14 h-14 bg-teal-600 hover:bg-teal-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105 active:scale-95"
        aria-label="Open support chat"
      >
        {open ? <IconX /> : <IconChat />}
      </button>
    </>
  );
}
