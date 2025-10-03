import React, { useEffect, useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box, CircularProgress, Alert, AlertTitle } from '@mui/material';
import { MainLayout } from './components/layout/MainLayout';
import { MathTutorPage } from './pages/MathTutorPage';
import { SettingsPage } from './pages/SettingsPage';
import { HelpPage } from './pages/HelpPage';
import { useAppSettings } from './hooks/useAppSettings';
import { ErrorBoundary } from './components/ErrorBoundary';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { SettingsProvider } from './contexts/SettingsContext';

function App() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { loadSettings } = useAppSettings();

  useEffect(() => {
    // Initialize app and check backend connection
    const initializeApp = async () => {
      try {
        setIsLoading(true);

        // Check if running in Electron environment
        if (window.electronAPI) {
          try {
            const systemInfo = await window.electronAPI.getSystemInfo();
            console.log('System Info:', systemInfo);
          } catch (electronError) {
            console.warn('Electron API not available, running in browser mode:', electronError);
          }
        } else {
          console.log('Electron API not found, running in browser mode');
        }

        // Initialize settings with fallback
        try {
          await loadSettings();
        } catch (settingsError) {
          console.warn('Settings loading failed, using defaults:', settingsError);
        }

        setIsLoading(false);
      } catch (err) {
        console.error('Failed to initialize app:', err);
        setError('Failed to initialize application. Please restart the application.');
        setIsLoading(false);
      }
    };

    initializeApp();
  }, [loadSettings]);

  if (isLoading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        height="100vh"
        flexDirection="column"
        gap={2}
      >
        <CircularProgress size={48} />
        <h2>Loading AI Math Tutor...</h2>
      </Box>
    );
  }

  if (error) {
    return (
      <Box m={4}>
        <Alert severity="error">
          <AlertTitle>Application Error</AlertTitle>
          {error}
        </Alert>
      </Box>
    );
  }

  return (
    <ErrorBoundary>
      <SettingsProvider>
        <WebSocketProvider>
          <MainLayout>
            <Routes>
              <Route path="/" element={<MathTutorPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/help" element={<HelpPage />} />
            </Routes>
          </MainLayout>
        </WebSocketProvider>
      </SettingsProvider>
    </ErrorBoundary>
  );
}

export default App;