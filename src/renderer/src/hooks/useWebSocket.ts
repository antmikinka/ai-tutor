import { useCallback, useEffect, useRef, useState } from 'react';
import { newClientId, resolveBackendUrl, toWebSocketUrl } from '../lib/backend';
import type { Capabilities, InboundMessage, InboundType, MessageOf, OutboundMessage } from '../types/protocol';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

type Handler<T extends InboundType> = (message: MessageOf<T>) => void;

interface PendingRequest {
  resolve: (message: InboundMessage) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

const MAX_RECONNECT_DELAY_MS = 30_000;
const HEARTBEAT_INTERVAL_MS = 25_000;
const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;

export class WebSocketRequestError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'WebSocketRequestError';
    this.code = code;
  }
}

/**
 * Single, self-healing connection to the backend WebSocket.
 *
 * - `request()` correlates a reply via `request_id` and returns a Promise.
 * - `subscribe()` registers listeners for unsolicited messages.
 * - Intentional `disconnect()` never triggers a reconnect; unexpected drops
 *   reconnect with capped exponential backoff.
 */
export const useWebSocket = () => {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const clientIdRef = useRef<string>(newClientId());
  const intentionalCloseRef = useRef(false);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingRef = useRef<Map<string, PendingRequest>>(new Map());
  const handlersRef = useRef<Map<InboundType, Set<Handler<any>>>>(new Map());
  const requestCounterRef = useRef(0);

  const clearTimers = () => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  };

  const failPending = (reason: string) => {
    pendingRef.current.forEach((pending) => {
      clearTimeout(pending.timer);
      pending.reject(new WebSocketRequestError('DISCONNECTED', reason));
    });
    pendingRef.current.clear();
  };

  const dispatch = (message: InboundMessage) => {
    if (message.request_id && pendingRef.current.has(message.request_id)) {
      const pending = pendingRef.current.get(message.request_id)!;
      pendingRef.current.delete(message.request_id);
      clearTimeout(pending.timer);
      if (message.type === 'error') {
        pending.reject(new WebSocketRequestError(message.code, message.message));
      } else {
        pending.resolve(message);
      }
      return;
    }
    handlersRef.current.get(message.type)?.forEach((handler) => {
      try {
        handler(message);
      } catch (error) {
        console.error(`WebSocket handler for ${message.type} threw`, error);
      }
    });
  };

  const scheduleReconnect = useCallback((connectFn: () => void) => {
    if (intentionalCloseRef.current) return;
    reconnectAttemptsRef.current += 1;
    const base = Math.min(MAX_RECONNECT_DELAY_MS, 1000 * 2 ** reconnectAttemptsRef.current);
    const delay = base / 2 + Math.random() * (base / 2); // jitter
    reconnectTimerRef.current = setTimeout(connectFn, delay);
  }, []);

  const connect = useCallback(async () => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }
    clearTimers();
    intentionalCloseRef.current = false;
    setConnectionStatus('connecting');

    let url: string;
    try {
      url = toWebSocketUrl(await resolveBackendUrl(), clientIdRef.current);
    } catch (error) {
      setConnectionStatus('error');
      setLastError(String(error));
      scheduleReconnect(connect);
      return;
    }

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0;
      setLastError(null);
      setConnectionStatus('connected');
      heartbeatTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
      }, HEARTBEAT_INTERVAL_MS);
    };

    ws.onmessage = (event) => {
      let parsed: InboundMessage;
      try {
        parsed = JSON.parse(event.data);
      } catch {
        console.warn('Ignoring non-JSON WebSocket frame');
        return;
      }
      if (parsed.type === 'connected') setCapabilities(parsed.capabilities);
      dispatch(parsed);
    };

    ws.onerror = () => {
      setLastError(`Cannot reach backend at ${url}`);
      setConnectionStatus('error');
    };

    ws.onclose = (event) => {
      clearTimers();
      if (wsRef.current === ws) wsRef.current = null;
      setCapabilities(null);
      failPending(`Connection closed (${event.code})`);
      if (intentionalCloseRef.current) {
        setConnectionStatus('disconnected');
        return;
      }
      setConnectionStatus('disconnected');
      scheduleReconnect(connect);
    };
  }, [scheduleReconnect]);

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    clearTimers();
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && ws.readyState !== WebSocket.CLOSED) {
      ws.close(1000, 'client closing');
    }
    failPending('Disconnected by client');
    setConnectionStatus('disconnected');
  }, []);

  const sendMessage = useCallback((message: OutboundMessage): boolean => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('Cannot send: WebSocket not connected');
      return false;
    }
    ws.send(JSON.stringify(message));
    return true;
  }, []);

  const request = useCallback(
    <T extends InboundType>(message: OutboundMessage, expect: T, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS): Promise<MessageOf<T>> => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        return Promise.reject(new WebSocketRequestError('DISCONNECTED', 'Backend is not connected'));
      }
      requestCounterRef.current += 1;
      const requestId = `${clientIdRef.current}-${requestCounterRef.current}`;
      return new Promise<MessageOf<T>>((resolve, reject) => {
        const timer = setTimeout(() => {
          pendingRef.current.delete(requestId);
          reject(new WebSocketRequestError('TIMEOUT', 'The backend did not answer in time'));
        }, timeoutMs);
        pendingRef.current.set(requestId, {
          timer,
          reject,
          resolve: (reply) => {
            if (reply.type === expect) {
              resolve(reply as MessageOf<T>);
            } else {
              reject(new WebSocketRequestError('UNEXPECTED_REPLY', `Expected ${expect}, got ${reply.type}`));
            }
          },
        });
        ws.send(JSON.stringify({ ...message, request_id: requestId }));
      });
    },
    [],
  );

  const subscribe = useCallback(<T extends InboundType>(type: T, handler: Handler<T>) => {
    if (!handlersRef.current.has(type)) handlersRef.current.set(type, new Set());
    handlersRef.current.get(type)!.add(handler);
    return () => {
      handlersRef.current.get(type)?.delete(handler);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connectionStatus,
    capabilities,
    lastError,
    clientId: clientIdRef.current,
    connect,
    disconnect,
    sendMessage,
    request,
    subscribe,
  };
};

export type WebSocketApi = ReturnType<typeof useWebSocket>;
