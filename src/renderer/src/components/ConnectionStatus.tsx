import React from 'react';
import { useWebSocketContext } from '../contexts/WebSocketContext';

const ConnectionStatus: React.FC = () => {
  const { connectionStatus, connect, disconnect } = useWebSocketContext();

  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'bg-green-500';
      case 'connecting':
        return 'bg-yellow-500';
      case 'disconnected':
        return 'bg-red-500';
      case 'error':
        return 'bg-red-600';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusText = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'Connected';
      case 'connecting':
        return 'Connecting...';
      case 'disconnected':
        return 'Disconnected';
      case 'error':
        return 'Connection Error';
      default:
        return 'Unknown';
    }
  };

  const getStatusIcon = () => {
    switch (connectionStatus) {
      case 'connected':
        return '✓';
      case 'connecting':
        return '⏳';
      case 'disconnected':
        return '✗';
      case 'error':
        return '⚠';
      default:
        return '?';
    }
  };

  return (
    <div className="flex items-center space-x-2 p-2 bg-gray-100 rounded-lg">
      <div className={`w-3 h-3 rounded-full ${getStatusColor()}`}></div>
      <span className="text-sm font-medium">
        {getStatusIcon()} Backend: {getStatusText()}
      </span>
      {connectionStatus === 'disconnected' && (
        <button
          onClick={connect}
          className="ml-2 px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Reconnect
        </button>
      )}
      {connectionStatus === 'error' && (
        <button
          onClick={connect}
          className="ml-2 px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600"
        >
          Retry
        </button>
      )}
    </div>
  );
};

export default ConnectionStatus;