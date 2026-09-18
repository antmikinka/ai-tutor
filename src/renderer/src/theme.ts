import { createTheme, Theme } from '@mui/material/styles';
import type { DisplaySettings } from './types/MathTypes';

export const resolveMode = (preference: DisplaySettings['theme']): 'light' | 'dark' => {
  if (preference === 'auto') {
    return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return preference;
};

export const buildTheme = (mode: 'light' | 'dark', fontSize: number): Theme =>
  createTheme({
    palette: {
      mode,
      primary: { main: '#1976d2', light: '#42a5f5', dark: '#1565c0' },
      secondary: { main: '#dc004e', light: '#ff5983', dark: '#9a0036' },
      ...(mode === 'light'
        ? { background: { default: '#f5f5f5', paper: '#ffffff' } }
        : { background: { default: '#121212', paper: '#1e1e1e' } }),
    },
    typography: {
      fontSize,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      h4: { fontSize: '1.5rem', fontWeight: 500 },
      h5: { fontSize: '1.25rem', fontWeight: 500 },
      h6: { fontSize: '1rem', fontWeight: 500 },
    },
    shape: { borderRadius: 8 },
    components: {
      MuiButton: { styleOverrides: { root: { textTransform: 'none', borderRadius: 8 } } },
      MuiPaper: { styleOverrides: { root: { borderRadius: 12 } } },
    },
  });
