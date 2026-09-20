import React, { useEffect, useMemo, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box, CircularProgress, Typography } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { MainLayout } from './components/layout/MainLayout';
import { MathTutorPage } from './pages/MathTutorPage';
import { PracticePage } from './pages/PracticePage';
import { SettingsPage } from './pages/SettingsPage';
import { HelpPage } from './pages/HelpPage';
import { ErrorBoundary } from './components/ErrorBoundary';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { SettingsProvider, useSettingsContext } from './contexts/SettingsContext';
import { buildTheme, resolveMode } from './theme';

const ThemedShell: React.FC = () => {
  const { settings, isLoading } = useSettingsContext();
  const { theme: preference, fontSize } = settings.displaySettings;

  // Re-evaluate "auto" when the OS colour scheme flips.
  const [systemTick, setSystemTick] = useState(0);
  useEffect(() => {
    if (preference !== 'auto' || !window.matchMedia) return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => setSystemTick((t) => t + 1);
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [preference]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const theme = useMemo(() => buildTheme(resolveMode(preference), fontSize), [preference, fontSize, systemTick]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {isLoading ? (
        <Box display="flex" justifyContent="center" alignItems="center" height="100vh" flexDirection="column" gap={2}>
          <CircularProgress size={48} />
          <Typography variant="h6">Loading AI Math Tutor…</Typography>
        </Box>
      ) : (
        <WebSocketProvider>
          <MainLayout>
            <Routes>
              <Route path="/" element={<MathTutorPage />} />
              <Route path="/practice" element={<PracticePage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/help" element={<HelpPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </MainLayout>
        </WebSocketProvider>
      )}
    </ThemeProvider>
  );
};

const App: React.FC = () => (
  <ErrorBoundary>
    <SettingsProvider>
      <ThemedShell />
    </SettingsProvider>
  </ErrorBoundary>
);

export default App;
