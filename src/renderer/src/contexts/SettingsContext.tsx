import React, { createContext, useContext, ReactNode } from 'react';
import { useAppSettings } from '../hooks/useAppSettings';
import { UserSettings } from '../types/MathTypes';

interface SettingsContextType {
  settings: UserSettings;
  isLoading: boolean;
  error: string | null;
  updateSettings: (settings: Partial<UserSettings>) => Promise<boolean>;
  resetSettings: () => Promise<boolean>;
  updateAudioSettings: (settings: Partial<UserSettings['audioSettings']>) => Promise<boolean>;
  updateModelSettings: (settings: Partial<UserSettings['modelSettings']>) => Promise<boolean>;
  updateDisplaySettings: (settings: Partial<UserSettings['displaySettings']>) => Promise<boolean>;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

interface SettingsProviderProps {
  children: ReactNode;
}

export const SettingsProvider: React.FC<SettingsProviderProps> = ({ children }) => {
  const settingsHook = useAppSettings();

  return (
    <SettingsContext.Provider value={settingsHook}>
      {children}
    </SettingsContext.Provider>
  );
};

export const useSettingsContext = () => {
  const context = useContext(SettingsContext);
  if (context === undefined) {
    throw new Error('useSettingsContext must be used within a SettingsProvider');
  }
  return context;
};