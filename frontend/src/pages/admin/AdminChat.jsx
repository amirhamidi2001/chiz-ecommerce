import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { adminAPI } from '../../services/api';
import { useChatWebSocket, CONNECTION_STATUS } from '../../hooks/useChatWebSocket';

// ─── Icons ────────────────────────────────────────────────────────────────────

const IconSend = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
  </svg>
);

const IconRefresh = ({ spinning }) => (
  <svg
    className={`w-4 h-4 ${spinning ? 'animate-spin' : ''}`}
    fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
  >
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
);

// ─── Status badge ─────────────────────────────────────────────────────────────

const STATUS_STYLES = {
  open: 'bg-amber-100 text-amber-700',
  assigned: 'bg-teal-100 text-teal-700',
  closed: 'bg-slate-100 text-slate-500',
};

function StatusBadge({ status }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[status] ?? ''}`}>
      {status}
    </span>
  );
}

// ─── Room list item ───────────────────────────────────────────────────────────

function RoomItem({ room, active, onSelect }) {
  const last = room.last_message;
  const time = last
    ? new Date(last.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <button
      onClick={() => onSelect(room)}
      className={`w-full text-left px-4 py-3 border-b border-slate-100 transition-colors hover:bg-slate-50 ${
        active ? 'bg-teal-50 border-l-2 border-l-teal-600' : ''
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-sm text-slate-800 truncate">
          {room.customer_name}
        </span>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {room.unread_count > 0 && (
            <span className="bg-teal-600 text-white text-xs rounded-full px-1.5 py-0.5 min-w-[18px] text-center leading-none">
              {room.unread_count}
            </span>
          )}
          <span className="text-xs text-slate-400">{time}</span>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-0.5">
        <StatusBadge status={room.status} />
        {room.subject && (
          <span className="text-xs text-slate-500 truncate">{room.subject}</span>
        )}
      </div>
      {last && (
        <p className="text-xs text-slate-400 mt-1 truncate">{last.content}</p>
      )}
    </button>
  );
}

// ─── Message bubble ───────────────────────────────────────────────────────────

function AgentMessageBubble({ msg, currentUserId }) {
  const isOwn = msg.sender_id === currentUserId;
  const time = new Date(msg.created_at).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit',
  });

  if (msg.message_type === 'system') {
    return (
      <div className="text-center text-xs text-slate-400 my-2">{msg.content}</div>
    );
  }

  return (
    <div className={`flex ${isOwn ? 'justify-end' : 'justify-start'} mb-2`}>
      <div className={`max-w-[70%] flex flex-col ${isOwn ? 'items-end' : 'items-start'}`}>
        {!isOwn && (
          <span className="text-xs text-slate-400 mb-0.5 px-1">
            {msg.sender_name}
            {msg.is_agent && (
              <span className="ml-1 text-teal-600 font-medium">(agent)</span>
            )}
          </span>
        )}
        <div
          className={`px-3.5 py-2 rounded-2xl text-sm leading-relaxed break-words ${
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

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AdminChat() {
  const { user } = useAuth();
  const token = localStorage.getItem('access_token');

  const [rooms, setRooms] = useState([]);
  const [statusFilter, setStatusFilter] = useState('open');
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [loadingRooms, setLoadingRooms] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [input, setInput] = useState('');
  const [wsError, setWsError] = useState('');
  const messagesEndRef = useRef(null);
  const typingTimer = useRef(null);

  const { messages, typingUsers, status, sendMessage, sendTyping, loadHistory } =
    useChatWebSocket(selectedRoom?.id ?? null, token, {
      onError: (msg) => setWsError(msg),
    });

  // ── Fetch rooms ───────────────────────────────────────────────────────────

  const fetchRooms = useCallback(
    async (showSpinner = true) => {
      if (showSpinner) setLoadingRooms(true);
      else setRefreshing(true);
      try {
        const res = await adminAPI.getChatRooms({ status: statusFilter });
        setRooms(res.data?.results ?? res.data ?? []);
      } catch {
        /* swallow — display will be empty */
      } finally {
        setLoadingRooms(false);
        setRefreshing(false);
      }
    },
    [statusFilter],
  );

  useEffect(() => {
    fetchRooms();
  }, [fetchRooms]);

  // ── Load history on room select ───────────────────────────────────────────

  useEffect(() => {
    if (!selectedRoom) return;
    adminAPI
      .getChatRoomMessages(selectedRoom.id)
      .then((res) => {
        const msgs = res.data?.results ?? res.data ?? [];
        loadHistory(
          msgs.map((m) => ({
            id: m.id,
            content: m.content,
            sender_id: m.sender?.id,
            sender_name: m.sender?.full_name,
            is_agent: m.sender?.is_agent,
            message_type: m.message_type,
            created_at: m.created_at,
          })),
        );
      })
      .catch(() => {});
  }, [selectedRoom?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Auto-scroll ───────────────────────────────────────────────────────────

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Actions ───────────────────────────────────────────────────────────────

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

  const handleCloseRoom = async () => {
    if (!selectedRoom) return;
    try {
      await adminAPI.updateChatRoom(selectedRoom.id, { status: 'closed' });
      setSelectedRoom((r) => ({ ...r, status: 'closed' }));
      fetchRooms(false);
    } catch {
      setWsError('Could not close conversation.');
    }
  };

  const wsStatusColor = {
    [CONNECTION_STATUS.OPEN]: 'text-emerald-500',
    [CONNECTION_STATUS.CONNECTING]: 'text-amber-500',
    [CONNECTION_STATUS.CLOSED]: 'text-slate-400',
    [CONNECTION_STATUS.ERROR]: 'text-red-500',
  }[status];

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-white rounded-xl border border-slate-200 shadow-sm">

      {/* ── LEFT: Room list ─────────────────────────────────────────────── */}
      <aside className="w-72 flex-shrink-0 border-r border-slate-200 flex flex-col">
        {/* Filter tabs */}
        <div className="px-4 pt-4 pb-2 border-b border-slate-100">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-slate-800">Conversations</h2>
            <button
              onClick={() => fetchRooms(false)}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500"
              title="Refresh"
            >
              <IconRefresh spinning={refreshing} />
            </button>
          </div>
          <div className="flex gap-1">
            {['open', 'assigned', 'closed'].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`flex-1 text-xs py-1 rounded-lg capitalize font-medium transition-colors ${
                  statusFilter === s
                    ? 'bg-teal-600 text-white'
                    : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loadingRooms ? (
            <div className="flex items-center justify-center h-32">
              <div className="w-6 h-6 border-4 border-teal-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : rooms.length === 0 ? (
            <div className="text-center text-sm text-slate-400 mt-10 px-4">
              No {statusFilter} conversations.
            </div>
          ) : (
            rooms.map((room) => (
              <RoomItem
                key={room.id}
                room={room}
                active={selectedRoom?.id === room.id}
                onSelect={(r) => {
                  setSelectedRoom(r);
                  setWsError('');
                  setInput('');
                }}
              />
            ))
          )}
        </div>
      </aside>

      {/* ── RIGHT: Conversation ─────────────────────────────────────────── */}
      {selectedRoom ? (
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Conversation header */}
          <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between flex-shrink-0">
            <div>
              <p className="font-semibold text-slate-800">
                {selectedRoom.customer_name ?? selectedRoom.customer_email}
              </p>
              <div className="flex items-center gap-2 mt-0.5">
                <StatusBadge status={selectedRoom.status} />
                {selectedRoom.subject && (
                  <span className="text-xs text-slate-500">{selectedRoom.subject}</span>
                )}
                <span className={`text-xs font-medium ${wsStatusColor}`}>
                  ● {status}
                </span>
              </div>
            </div>
            {selectedRoom.status !== 'closed' && (
              <button
                onClick={handleCloseRoom}
                className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-3 py-1.5 rounded-lg transition-colors"
              >
                Close conversation
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {messages.length === 0 && (
              <div className="text-center text-sm text-slate-400 mt-16">
                No messages yet. Say hello!
              </div>
            )}
            {messages.map((msg) => (
              <AgentMessageBubble
                key={msg.id ?? `${msg.sender_id}-${msg.created_at}`}
                msg={msg}
                currentUserId={user?.id}
              />
            ))}
            {typingUsers.length > 0 && (
              <div className="flex items-center gap-1 text-xs text-slate-400 mt-1">
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
            {wsError && (
              <p className="text-center text-xs text-red-500 mt-2">{wsError}</p>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          {selectedRoom.status !== 'closed' ? (
            <div className="border-t border-slate-200 p-4 flex gap-3 flex-shrink-0">
              <textarea
                rows={1}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder="Reply to customer…"
                className="flex-1 resize-none border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 max-h-28 overflow-y-auto"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || status !== CONNECTION_STATUS.OPEN}
                className="bg-teal-600 hover:bg-teal-700 text-white rounded-xl px-4 flex items-center gap-2 transition-colors disabled:opacity-40 text-sm font-medium"
              >
                <IconSend />
                Send
              </button>
            </div>
          ) : (
            <div className="border-t border-slate-200 p-4 text-center text-sm text-slate-400">
              This conversation is closed.
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
          <svg className="w-16 h-16 mb-4 opacity-30" fill="none" stroke="currentColor" strokeWidth={1} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
          <p className="font-medium">Select a conversation</p>
          <p className="text-sm mt-1">Choose one from the list to start replying.</p>
        </div>
      )}
    </div>
  );
}
