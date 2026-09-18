import React, { useEffect, useState } from 'react';
import { Box, Button, Chip, Tooltip } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import SyncIcon from '@mui/icons-material/Sync';
import CloudOffIcon from '@mui/icons-material/CloudOff';
import { useWebSocketContext } from '../contexts/WebSocketContext';

const STATUS_META = {
  connected: { label: 'Backend connected', color: 'success' as const, icon: <CheckCircleIcon fontSize="small" /> },
  connecting: { label: 'Connecting…', color: 'warning' as const, icon: <SyncIcon fontSize="small" /> },
  disconnected: { label: 'Backend offline', color: 'default' as const, icon: <CloudOffIcon fontSize="small" /> },
  error: { label: 'Connection error', color: 'error' as const, icon: <ErrorIcon fontSize="small" /> },
};

interface ConnectionStatusProps {
  compact?: boolean;
}

interface BackendStatusEvent {
  state: 'starting' | 'ready' | 'stopped' | 'error';
  message?: string;
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ compact = false }) => {
  const { connectionStatus, connect, lastError, capabilities } = useWebSocketContext();
  const [processStatus, setProcessStatus] = useState<BackendStatusEvent | null>(null);

  // The Electron main process reports the lifecycle of the Python process it spawned.
  useEffect(() => {
    if (!window.electronAPI?.on) return;
    const unsubscribe = window.electronAPI.on('backend-status', (payload) => {
      const event = payload as BackendStatusEvent;
      setProcessStatus(event);
      if (event.state === 'ready') connect();
    });
    return unsubscribe;
  }, [connect]);

  const meta = STATUS_META[connectionStatus];
  const processHint =
    processStatus?.state === 'starting'
      ? 'Starting the Python backend…'
      : processStatus?.state === 'error' || processStatus?.state === 'stopped'
        ? processStatus.message || 'The Python backend stopped. Use “Restart backend” from the menu.'
        : null;
  const tooltip =
    connectionStatus === 'connected'
      ? `Symbolic solver ready${capabilities?.llm ? ' · AI model loaded' : ' · AI model not loaded'}`
      : processHint || lastError || meta.label;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Tooltip title={tooltip}>
        <Chip
          size="small"
          color={meta.color}
          icon={meta.icon}
          label={compact ? undefined : meta.label}
          variant={connectionStatus === 'connected' ? 'filled' : 'outlined'}
          sx={{ color: 'inherit', '& .MuiChip-icon': { color: 'inherit' } }}
        />
      </Tooltip>
      {(connectionStatus === 'disconnected' || connectionStatus === 'error') && (
        <Button size="small" color="inherit" variant="outlined" onClick={() => connect()}>
          Retry
        </Button>
      )}
    </Box>
  );
};

export default ConnectionStatus;
