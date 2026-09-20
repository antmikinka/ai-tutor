import React, { createContext, useContext, ReactNode } from 'react';
import { AppSettingsApi, useAppSettings } from '../hooks/useAppSettings';

const SettingsContext = createContext<AppSettingsApi | undefined>(undefined);

export const SettingsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const value = useAppSettings();
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
};

export const useSettingsContext = (): AppSettingsApi => {
  const context = useContext(SettingsContext);
  if (context === undefined) {
    throw new Error('useSettingsContext must be used within a SettingsProvider');
  }
  return context;
};
