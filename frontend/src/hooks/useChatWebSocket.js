import { useCallback, useEffect, useRef, useState } from 'react';

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
const RECONNECT_DELAY_MS = 3_000;
const MAX_RECONNECTS = 5;

export const CONNECTION_STATUS = {
  CONNECTING: 'connecting',
  OPEN: 'open',
  CLOSED: 'closed',
  ERROR: 'error',
};

/**
 * @param {string|null} roomId     - UUID of the chat room (null = skip)
 * @param {string|null} token      - JWT access token
 * @param {object}      [options]
 * @param {function}    [options.onError]  - called with error message string
 */
export function useChatWebSocket(roomId, token, { onError } = {}) {
  const [messages, setMessages] = useState([]);
  const [typingUsers, setTypingUsers] = useState({}); // { senderId: { name, timeout } }
  const [status, setStatus] = useState(CONNECTION_STATUS.CLOSED);

  const wsRef = useRef(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef(null);
  const isMounted = useRef(true);

  // ── Helpers ──────────────────────────────────────────────────────────────

  const clearTypingTimeout = useCallback((senderId) => {
    setTypingUsers((prev) => {
      const next = { ...prev };
      if (next[senderId]?.timeout) clearTimeout(next[senderId].timeout);
      delete next[senderId];
      return next;
    });
  }, []);

  const setTypingUser = useCallback(
    (senderId, senderName, isTyping) => {
      if (!isTyping) {
        clearTypingTimeout(senderId);
        return;
      }
      setTypingUsers((prev) => {
        if (prev[senderId]?.timeout) clearTimeout(prev[senderId].timeout);
        const timeout = setTimeout(() => clearTypingTimeout(senderId), 3_500);
        return { ...prev, [senderId]: { name: senderName, timeout } };
      });
    },
    [clearTypingTimeout],
  );

  // ── Connect ───────────────────────────────────────────────────────────────

  const connect = useCallback(() => {
    if (!roomId || !token || !isMounted.current) return;

    setStatus(CONNECTION_STATUS.CONNECTING);
    const url = `${WS_BASE}/ws/chat/${roomId}/?token=${token}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMounted.current) return;
      reconnectCount.current = 0;
      setStatus(CONNECTION_STATUS.OPEN);
    };

    ws.onmessage = (event) => {
      if (!isMounted.current) return;
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch {
        /* silently ignore malformed frames */
      }
    };

    ws.onerror = () => {
      if (!isMounted.current) return;
      setStatus(CONNECTION_STATUS.ERROR);
      onError?.('WebSocket connection error.');
    };

    ws.onclose = (e) => {
      if (!isMounted.current) return;
      setStatus(CONNECTION_STATUS.CLOSED);

      // 4001 = unauthenticated, 4003 = forbidden — don't retry
      if (e.code === 4001 || e.code === 4003) return;

      if (reconnectCount.current < MAX_RECONNECTS) {
        reconnectCount.current += 1;
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };
  }, [roomId, token, onError]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Message dispatcher ────────────────────────────────────────────────────

  const handleMessage = useCallback(
    (data) => {
      switch (data.type) {
        case 'chat_message':
          setMessages((prev) => {
            // Deduplicate by id
            if (prev.some((m) => m.id === data.id)) return prev;
            return [...prev, data];
          });
          break;

        case 'typing':
          setTypingUser(data.sender_id, data.sender_name, data.is_typing);
          break;

        case 'error':
          onError?.(data.message);
          break;

        default:
          break;
      }
    },
    [setTypingUser, onError],
  );

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  useEffect(() => {
    isMounted.current = true;
    connect();

    return () => {
      isMounted.current = false;
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [connect]);

  // ── Public API ────────────────────────────────────────────────────────────

  const sendMessage = useCallback((content) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify({ type: 'chat_message', content }));
    return true;
  }, []);

  const sendTyping = useCallback((isTyping) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'typing', is_typing: isTyping }));
  }, []);

  const loadHistory = useCallback((historyMessages) => {
    setMessages(historyMessages);
  }, []);

  const typingUserList = Object.values(typingUsers).map((u) => u.name);

  return {
    messages,
    typingUsers: typingUserList,
    status,
    sendMessage,
    sendTyping,
    loadHistory,
  };
}
