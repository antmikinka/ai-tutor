import { useState, useEffect, useRef, useCallback } from 'react';

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
}

export const useWebSocket = (url?: string) => {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [messages, setMessages] = useState<WebSocketMessage[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;

  const connect = useCallback(async () => {
    try {
      setConnectionStatus('connecting');

      // Get WebSocket URL from settings or use default
      let wsUrl = url || 'ws://localhost:8000/ws/test-client';

      // Check if we're getting settings from Electron API
      if (window.electronAPI?.getSettings) {
        try {
          const settings = await window.electronAPI.getSettings();
          console.log('Settings retrieved:', settings);
          if (settings?.websocketUrl) {
            wsUrl = settings.websocketUrl;
            console.log('Using WebSocket URL from settings:', wsUrl);
          }
        } catch (error) {
          console.warn('Failed to get settings from Electron API:', error);
        }
      } else {
        console.log('Electron API not available, using default WebSocket URL:', wsUrl);
      }

      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          setMessages(prev => [...prev, message]);

          // Handle specific message types
          if (message.type === 'connection_established') {
            console.log('Connection established with backend');
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      wsRef.current.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        setConnectionStatus('disconnected');

        // Attempt to reconnect
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++;
          const timeout = Math.pow(2, reconnectAttemptsRef.current) * 1000; // Exponential backoff

          console.log(`Attempting to reconnect in ${timeout}ms...`);
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, timeout);
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        console.error('WebSocket URL:', wsUrl);
        console.error('WebSocket readyState:', wsRef.current?.readyState);
        setConnectionStatus('error');
      };
    } catch (error) {
      console.error('Failed to connect to WebSocket:', error);
      setConnectionStatus('error');
    }
  }, [url]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionStatus('disconnected');
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current && connectionStatus === 'connected') {
      const websocketMessage: WebSocketMessage = {
        type: message.type || 'message',
        data: message,
        timestamp: new Date().toISOString(),
      };

      wsRef.current.send(JSON.stringify(websocketMessage));
    } else {
      console.warn('Cannot send message: WebSocket not connected');
    }
  }, [connectionStatus]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setLastMessage(null);
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, []);

  return {
    connectionStatus,
    lastMessage,
    messages,
    sendMessage,
    connect,
    disconnect,
    clearMessages,
  };
};