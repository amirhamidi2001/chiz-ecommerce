import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useChatWebSocket, CONNECTION_STATUS } from '../hooks/useChatWebSocket';

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECTS = 5;

describe('useChatWebSocket', () => {
    let wsInstance;
    const mockOnError = vi.fn();

    beforeEach(() => {
        wsInstance = null;
        vi.clearAllMocks();
        vi.useFakeTimers();

        global.WebSocket = class MockWebSocket {
            constructor(url) {
                this.url = url;
                this.readyState = WebSocket.CONNECTING;
                this.send = vi.fn();
                this.close = vi.fn();
                wsInstance = this;
            }
        };

        // Polyfill WebSocket readyState constants for the mock
        global.WebSocket.CONNECTING = 0;
        global.WebSocket.OPEN = 1;
        global.WebSocket.CLOSING = 2;
        global.WebSocket.CLOSED = 3;
    });

    afterEach(() => {
        vi.clearAllTimers();
        vi.useRealTimers();
    });

    describe('connection lifecycle', () => {
        it('does not connect if roomId or token is null', () => {
            const { result } = renderHook(() => useChatWebSocket(null, null));
            expect(wsInstance).toBeNull();
            expect(result.current.status).toBe(CONNECTION_STATUS.CLOSED);
        });

        it('establishes connection when roomId and token are provided', () => {
            const { result } = renderHook(() => useChatWebSocket('room-1', 'token-123'));

            expect(wsInstance).toBeTruthy();
            expect(wsInstance.url).toContain('/ws/chat/room-1/?token=token-123');
            expect(result.current.status).toBe(CONNECTION_STATUS.CONNECTING);

            act(() => {
                wsInstance.onopen();
            });

            expect(result.current.status).toBe(CONNECTION_STATUS.OPEN);
        });

        it('closes websocket and cleans up on unmount', () => {
            const { unmount } = renderHook(() => useChatWebSocket('room-1', 'token-123'));

            const ws = wsInstance;

            act(() => {
                ws.onopen();
            });

            unmount();

            expect(ws.onclose).toBeNull();
            expect(ws.close).toHaveBeenCalledTimes(1);
        });
    });

    describe('message handling', () => {
        it('handles chat_message and deduplicates by id', () => {
            const { result } = renderHook(() => useChatWebSocket('room-1', 'token-123'));

            act(() => {
                wsInstance.onopen();
            });

            const message1 = { type: 'chat_message', id: 1, content: 'Hello' };
            const message2 = { type: 'chat_message', id: 2, content: 'World' };

            act(() => {
                wsInstance.onmessage({ data: JSON.stringify(message1) });
            });

            expect(result.current.messages).toEqual([message1]);

            act(() => {
                wsInstance.onmessage({ data: JSON.stringify(message1) }); // Duplicate
                wsInstance.onmessage({ data: JSON.stringify(message2) });
            });

            expect(result.current.messages).toEqual([message1, message2]);
        });

        it('handles typing indicator and clears it after timeout', () => {
            const { result } = renderHook(() => useChatWebSocket('room-1', 'token-123'));

            act(() => {
                wsInstance.onopen();
                wsInstance.onmessage({
                    data: JSON.stringify({ type: 'typing', sender_id: 'u1', sender_name: 'Alice', is_typing: true })
                });
            });

            expect(result.current.typingUsers).toEqual(['Alice']);

            // Advance time but not enough to trigger timeout
            act(() => {
                vi.advanceTimersByTime(3000);
            });
            expect(result.current.typingUsers).toEqual(['Alice']);

            // Advance past the 3500ms timeout
            act(() => {
                vi.advanceTimersByTime(500);
            });
            expect(result.current.typingUsers).toEqual([]);
        });

        it('clears typing indicator immediately if is_typing is false', () => {
            const { result } = renderHook(() => useChatWebSocket('room-1', 'token-123'));

            act(() => {
                wsInstance.onopen();
                wsInstance.onmessage({
                    data: JSON.stringify({ type: 'typing', sender_id: 'u1', sender_name: 'Alice', is_typing: true })
                });
            });

            expect(result.current.typingUsers).toEqual(['Alice']);

            act(() => {
                wsInstance.onmessage({
                    data: JSON.stringify({ type: 'typing', sender_id: 'u1', sender_name: 'Alice', is_typing: false })
                });
            });

            expect(result.current.typingUsers).toEqual([]);
        });

        it('handles error messages from server', () => {
            renderHook(() => useChatWebSocket('room-1', 'token-123', { onError: mockOnError }));

            act(() => {
                wsInstance.onopen();
                wsInstance.onmessage({
                    data: JSON.stringify({ type: 'error', message: 'Rate limited' })
                });
            });

            expect(mockOnError).toHaveBeenCalledWith('Rate limited');
        });
    });

    describe('reconnection', () => {
        it('reconnects after RECONNECT_DELAY_MS on abnormal close', () => {
            renderHook(() => useChatWebSocket('room-1', 'token-123'));

            act(() => {
                wsInstance.onclose({ code: 1006 });
            });

            const firstWsInstance = wsInstance;

            act(() => {
                vi.advanceTimersByTime(RECONNECT_DELAY_MS);
            });

            expect(wsInstance).not.toBe(firstWsInstance); // New instance created
            expect(wsInstance.url).toContain('/ws/chat/room-1/?token=token-123');
        });

        it('stops reconnecting after MAX_RECONNECTS', () => {
            renderHook(() => useChatWebSocket('room-1', 'token-123'));

            for (let i = 0; i < MAX_RECONNECTS; i++) {
                act(() => {
                    wsInstance.onclose({ code: 1006 });
                    vi.advanceTimersByTime(RECONNECT_DELAY_MS);
                });
            }

            const lastWsInstance = wsInstance;

            // Try one more time
            act(() => {
                wsInstance.onclose({ code: 1006 });
                vi.advanceTimersByTime(RECONNECT_DELAY_MS);
            });

            expect(wsInstance).toBe(lastWsInstance); // No new instance created
        });

        it('does not reconnect on 4001 or 4003 status codes', () => {
            renderHook(() => useChatWebSocket('room-1', 'token-123'));

            act(() => {
                wsInstance.onclose({ code: 4001 });
            });

            const currentWs = wsInstance;

            act(() => {
                vi.advanceTimersByTime(RECONNECT_DELAY_MS);
            });

            expect(wsInstance).toBe(currentWs); // Should not have reconnected
        });

        it('resets reconnect counter on successful open', () => {
            renderHook(() => useChatWebSocket('room-1', 'token-123'));

            // Fail 4 times
            for (let i = 0; i < 4; i++) {
                act(() => {
                    wsInstance.onclose({ code: 1006 });
                    vi.advanceTimersByTime(RECONNECT_DELAY_MS);
                });
            }

            // Success
            act(() => {
                wsInstance.onopen();
            });

            // Fail again, should be allowed since counter reset
            act(() => {
                wsInstance.onclose({ code: 1006 });
            });

            const beforeReconnectWs = wsInstance;

            act(() => {
                vi.advanceTimersByTime(RECONNECT_DELAY_MS);
            });

            expect(wsInstance).not.toBe(beforeReconnectWs);
        });
    });

    describe('public API', () => {
        it('sendMessage sends data and returns true when OPEN', () => {
            const { result } = renderHook(() => useChatWebSocket('room-1', 'token-123'));

            act(() => {
                wsInstance.readyState = WebSocket.OPEN;
                wsInstance.onopen();
            });

            let success;
            act(() => {
                success = result.current.sendMessage('Test message');
            });

            expect(success).toBe(true);
            expect(wsInstance.send).toHaveBeenCalledWith(JSON.stringify({ type: 'chat_message', content: 'Test message' }));
        });

        it('sendMessage returns false and does not send if NOT OPEN', () => {
            const { result } = renderHook(() => useChatWebSocket('room-1', 'token-123'));

            act(() => {
                wsInstance.readyState = WebSocket.CONNECTING;
            });

            let success;
            act(() => {
                success = result.current.sendMessage('Test message');
            });

            expect(success).toBe(false);
            expect(wsInstance.send).not.toHaveBeenCalled();
        });

        it('sendTyping sends typing indicator when OPEN', () => {
            const { result } = renderHook(() => useChatWebSocket('room-1', 'token-123'));

            act(() => {
                wsInstance.readyState = WebSocket.OPEN;
                wsInstance.onopen();
            });

            act(() => {
                result.current.sendTyping(true);
            });

            expect(wsInstance.send).toHaveBeenCalledWith(JSON.stringify({ type: 'typing', is_typing: true }));
        });

        it('loadHistory populates messages state', () => {
            const { result } = renderHook(() => useChatWebSocket('room-1', 'token-123'));
            const history = [{ id: 1, content: 'History 1' }, { id: 2, content: 'History 2' }];

            act(() => {
                result.current.loadHistory(history);
            });

            expect(result.current.messages).toEqual(history);
        });
    });

    describe('edge cases', () => {
        it('ignores malformed JSON in onmessage without crashing', () => {
            const { result } = renderHook(() => useChatWebSocket('room-1', 'token-123'));

            act(() => {
                wsInstance.onopen();
            });

            expect(() => {
                act(() => {
                    wsInstance.onmessage({ data: 'invalid json {' });
                });
            }).not.toThrow();

            expect(result.current.messages).toEqual([]);
        });

        it('updates status to ERROR and calls onError on ws.onerror', () => {
            const { result } = renderHook(() => useChatWebSocket('room-1', 'token-123', { onError: mockOnError }));

            act(() => {
                wsInstance.onerror();
            });

            expect(result.current.status).toBe(CONNECTION_STATUS.ERROR);
            expect(mockOnError).toHaveBeenCalledWith('WebSocket connection error.');
        });

        it('does not update state if unmounted before onopen', () => {
            const { result, unmount } = renderHook(() => useChatWebSocket('room-1', 'token-123'));

            unmount();

            act(() => {
                wsInstance.onopen(); // Should do nothing because isMounted is false
            });

            // The status will remain CLOSED if the unmount cleanup ran and the onopen was ignored.
            // However, unmount prevents React from updating state anyway, this checks no errors are thrown.
            expect(result.current.status).toBe(CONNECTION_STATUS.CONNECTING);
        });
    });
});