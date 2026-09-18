import { useCallback, useEffect, useRef, useState } from 'react';
import { UserSettings } from '../types/MathTypes';

const STORAGE_KEY = 'mathTutorSettings';

export const defaultSettings: UserSettings = {
  audioSettings: {
    inputDevice: 'default',
    outputDevice: 'default',
    volume: 0.8,
    enableSpeechRecognition: false,
    enableTextToSpeech: false,
    ttsVoice: 'default',
    ttsLanguage: 'en',
    ttsSpeed: 1.0,
    ttsPitch: 1.0,
    sttLanguage: 'en',
    sttModel: 'MERaLiON-AudioLLM-Whisper-SEA-LION',
    enableEducationalMode: true,
    enableNoiseReduction: true,
  },
  modelSettings: {
    temperature: 0.7,
    maxTokens: 2048,
    useGPU: true,
    modelPath: '',
    reasoningModel: 'Qwen3-Omni-30B-A3B-Thinking',
    enableThinking: true,
    showStepByStep: true,
    enableChainOfThought: true,
  },
  displaySettings: {
    theme: 'light',
    fontSize: 14,
    showStepByStep: true,
    showConfidence: true,
    showModelInfo: true,
    showPerformanceMetrics: false,
  },
  modelConfig: {
    reasoningModel: 'Qwen3-Omni-30B-A3B-Thinking',
    ttsModel: 'Microsoft-VibeVoice-1.5B',
    sttModel: 'MERaLiON-AudioLLM-Whisper-SEA-LION',
    enableFallback: true,
    autoOptimize: false,
    optimizationSettings: {
      quantization: false,
      pruning: false,
      useGPU: true,
      maxMemoryUsage: 8192,
    },
  },
  appVersion: process.env.REACT_APP_VERSION || '1.0.0',
};

const mergeSettings = (base: UserSettings, patch: Partial<UserSettings> | null | undefined): UserSettings => ({
  ...base,
  ...patch,
  audioSettings: { ...base.audioSettings, ...(patch?.audioSettings || {}) },
  modelSettings: { ...base.modelSettings, ...(patch?.modelSettings || {}) },
  displaySettings: { ...base.displaySettings, ...(patch?.displaySettings || {}) },
  modelConfig: {
    ...base.modelConfig,
    ...(patch?.modelConfig || {}),
    optimizationSettings: { ...base.modelConfig.optimizationSettings, ...(patch?.modelConfig?.optimizationSettings || {}) },
  },
});

/**
 * User preferences, persisted through Electron's store when available and
 * localStorage otherwise. Instantiate once (in SettingsProvider).
 */
export const useAppSettings = () => {
  const [settings, setSettings] = useState<UserSettings>(defaultSettings);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const settingsRef = useRef(settings);
  settingsRef.current = settings;

  const persist = useCallback(async (next: UserSettings) => {
    if (window.electronAPI) {
      await window.electronAPI.updateSettings({ userSettings: next });
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    }
  }, []);

  const loadSettings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      let stored: Partial<UserSettings> | null = null;
      if (window.electronAPI) {
        const electronSettings = await window.electronAPI.getSettings();
        stored = (electronSettings?.userSettings as Partial<UserSettings>) || null;
      } else {
        const raw = localStorage.getItem(STORAGE_KEY);
        stored = raw ? JSON.parse(raw) : null;
      }
      setSettings(mergeSettings(defaultSettings, stored));
    } catch (err) {
      console.error('Failed to load settings:', err);
      setError('Failed to load settings; using defaults.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateSettings = useCallback(
    async (patch: Partial<UserSettings>) => {
      const next = mergeSettings(settingsRef.current, patch);
      setSettings(next);
      try {
        await persist(next);
        return true;
      } catch (err) {
        console.error('Failed to save settings:', err);
        setError('Failed to save settings');
        return false;
      }
    },
    [persist],
  );

  const resetSettings = useCallback(async () => {
    setSettings(defaultSettings);
    try {
      if (window.electronAPI) {
        await window.electronAPI.updateSettings({ userSettings: defaultSettings });
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
      return true;
    } catch (err) {
      console.error('Failed to reset settings:', err);
      setError('Failed to reset settings');
      return false;
    }
  }, []);

  const updateAudioSettings = useCallback(
    (audioSettings: Partial<UserSettings['audioSettings']>) => updateSettings({ audioSettings: audioSettings as UserSettings['audioSettings'] }),
    [updateSettings],
  );
  const updateModelSettings = useCallback(
    (modelSettings: Partial<UserSettings['modelSettings']>) => updateSettings({ modelSettings: modelSettings as UserSettings['modelSettings'] }),
    [updateSettings],
  );
  const updateDisplaySettings = useCallback(
    (displaySettings: Partial<UserSettings['displaySettings']>) => updateSettings({ displaySettings: displaySettings as UserSettings['displaySettings'] }),
    [updateSettings],
  );
  const updateModelConfig = useCallback(
    (modelConfig: Partial<UserSettings['modelConfig']>) => updateSettings({ modelConfig: modelConfig as UserSettings['modelConfig'] }),
    [updateSettings],
  );

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  return {
    settings,
    isLoading,
    error,
    loadSettings,
    updateSettings,
    resetSettings,
    updateAudioSettings,
    updateModelSettings,
    updateDisplaySettings,
    updateModelConfig,
  };
};

export type AppSettingsApi = ReturnType<typeof useAppSettings>;
