import React, { createContext, useContext, ReactNode } from 'react';
import { useWebSocket, WebSocketApi } from '../hooks/useWebSocket';

const WebSocketContext = createContext<WebSocketApi | undefined>(undefined);

/**
 * Owns the single backend WebSocket for the whole renderer. Every component
 * must consume it through `useWebSocketContext`; calling `useWebSocket`
 * directly would open an additional connection.
 */
export const WebSocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const websocket = useWebSocket();
  return <WebSocketContext.Provider value={websocket}>{children}</WebSocketContext.Provider>;
};

export const useWebSocketContext = (): WebSocketApi => {
  const context = useContext(WebSocketContext);
  if (context === undefined) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
};
