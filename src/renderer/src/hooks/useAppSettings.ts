import { useState, useEffect, useCallback } from 'react';
import { UserSettings, ModelInfo, ModelPerformanceMetrics } from '../types/MathTypes';

const defaultSettings: UserSettings = {
  audioSettings: {
    inputDevice: 'default',
    outputDevice: 'default',
    volume: 0.8,
    enableSpeechRecognition: true,
    enableTextToSpeech: true,
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
    showPerformanceMetrics: true,
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
      maxMemoryUsage: 8192, // 8GB
    },
  },
  appVersion: '2.0.0',
};

export const useAppSettings = () => {
  const [settings, setSettings] = useState<UserSettings>(defaultSettings);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [modelPerformance, setModelPerformance] = useState<ModelPerformanceMetrics[]>([]);
  const [isManagingModels, setIsManagingModels] = useState(false);

  const loadSettings = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Try to get settings from Electron main process
      if (window.electronAPI) {
        const electronSettings = await window.electronAPI.getSettings();
        setSettings({ ...defaultSettings, ...electronSettings });
      } else {
        // Fallback to localStorage for web development
        const savedSettings = localStorage.getItem('mathTutorSettings');
        if (savedSettings) {
          const parsed = JSON.parse(savedSettings);
          setSettings({ ...defaultSettings, ...parsed });
        }
      }
    } catch (err) {
      console.error('Failed to load settings:', err);
      setError('Failed to load settings');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateSettings = useCallback(async (newSettings: Partial<UserSettings>) => {
    try {
      const updatedSettings = { ...settings, ...newSettings };

      // Update state
      setSettings(updatedSettings);

      // Save to Electron main process
      if (window.electronAPI) {
        await window.electronAPI.updateSettings(updatedSettings);
      } else {
        // Fallback to localStorage
        localStorage.setItem('mathTutorSettings', JSON.stringify(updatedSettings));
      }

      return true;
    } catch (err) {
      console.error('Failed to update settings:', err);
      setError('Failed to update settings');
      return false;
    }
  }, [settings]);

  const resetSettings = useCallback(async () => {
    try {
      setSettings(defaultSettings);

      if (window.electronAPI) {
        await window.electronAPI.updateSettings(defaultSettings);
      } else {
        localStorage.removeItem('mathTutorSettings');
      }

      return true;
    } catch (err) {
      console.error('Failed to reset settings:', err);
      setError('Failed to reset settings');
      return false;
    }
  }, []);

  const updateAudioSettings = useCallback((audioSettings: Partial<UserSettings['audioSettings']>) => {
    return updateSettings({ audioSettings: { ...settings.audioSettings, ...audioSettings } });
  }, [settings, updateSettings]);

  const updateModelSettings = useCallback((modelSettings: Partial<UserSettings['modelSettings']>) => {
    return updateSettings({ modelSettings: { ...settings.modelSettings, ...modelSettings } });
  }, [settings, updateSettings]);

  const updateDisplaySettings = useCallback((displaySettings: Partial<UserSettings['displaySettings']>) => {
    return updateSettings({ displaySettings: { ...settings.displaySettings, ...displaySettings } });
  }, [settings, updateSettings]);

  const updateModelConfig = useCallback((modelConfig: Partial<UserSettings['modelConfig']>) => {
    return updateSettings({ modelConfig: { ...settings.modelConfig, ...modelConfig } });
  }, [settings, updateSettings]);

  // Model management functions
  const loadAvailableModels = useCallback(async () => {
    try {
      if (window.electronAPI?.getAvailableModels) {
        const models = await window.electronAPI.getAvailableModels();
        setAvailableModels(models);
      } else {
        // Fallback to default models
        const defaultModels: ModelInfo[] = [
          {
            id: 'Qwen3-Omni-30B-A3B-Thinking',
            name: 'Qwen3-Omni-30B-A3B-Thinking',
            description: 'Advanced reasoning model for mathematical problem solving',
            type: 'reasoning',
            size: '58.0 GB',
            memoryRequired: 32,
            gpuRequired: true,
            status: 'not_downloaded',
            supportedLanguages: ['en', 'zh', 'es', 'fr', 'de', 'ja', 'ko'],
            specialFeatures: ['chain_of_thought', 'mathematical_reasoning', 'step_by_step'],
          },
          {
            id: 'Microsoft-VibeVoice-1.5B',
            name: 'Microsoft VibeVoice 1.5B',
            description: 'Natural sounding text-to-speech with educational optimization',
            type: 'tts',
            size: '3.2 GB',
            memoryRequired: 4,
            gpuRequired: false,
            status: 'not_downloaded',
            supportedLanguages: ['en', 'zh', 'es', 'fr', 'de', 'ja', 'ko'],
            specialFeatures: ['educational_tone', 'clarity', 'mathematical_pronunciation'],
          },
          {
            id: 'MERaLiON-AudioLLM-Whisper-SEA-LION',
            name: 'MERaLiON-AudioLLM-Whisper-SEA-LION',
            description: 'Enhanced speech recognition optimized for educational content',
            type: 'stt',
            size: '2.8 GB',
            memoryRequired: 6,
            gpuRequired: false,
            status: 'not_downloaded',
            supportedLanguages: ['en', 'zh', 'ms', 'id', 'th', 'vi', 'tl', 'ja', 'ko'],
            specialFeatures: ['educational_content', 'mathematical_terms', 'classroom_noise_filtering'],
          },
        ];
        setAvailableModels(defaultModels);
      }
    } catch (err) {
      console.error('Failed to load available models:', err);
      setError('Failed to load available models');
    }
  }, []);

  const downloadModel = useCallback(async (modelId: string) => {
    try {
      setIsManagingModels(true);

      if (window.electronAPI?.downloadModel) {
        const result = await window.electronAPI.downloadModel(modelId);
        // Update model status
        setAvailableModels(prev => prev.map(model =>
          model.id === modelId
            ? { ...model, status: 'downloading', downloadProgress: 0 }
            : model
        ));
        return result;
      } else {
        // Simulate download
        setAvailableModels(prev => prev.map(model =>
          model.id === modelId
            ? { ...model, status: 'downloading', downloadProgress: 0 }
            : model
        ));

        // Simulate download progress
        let progress = 0;
        const interval = setInterval(() => {
          progress += Math.random() * 20;
          if (progress >= 100) {
            clearInterval(interval);
            setAvailableModels(prev => prev.map(model =>
              model.id === modelId
                ? { ...model, status: 'loaded', downloadProgress: 100 }
                : model
            ));
          } else {
            setAvailableModels(prev => prev.map(model =>
              model.id === modelId
                ? { ...model, downloadProgress: progress }
                : model
            ));
          }
        }, 500);

        return { success: true };
      }
    } catch (err) {
      console.error('Failed to download model:', err);
      setError('Failed to download model');
      return { success: false, error: String(err) };
    } finally {
      setIsManagingModels(false);
    }
  }, []);

  const optimizeModel = useCallback(async (modelId: string, optimizationType: string) => {
    try {
      setIsManagingModels(true);

      if (window.electronAPI?.optimizeModel) {
        const result = await window.electronAPI.optimizeModel(modelId, optimizationType);
        return result;
      } else {
        // Simulate optimization
        await new Promise(resolve => setTimeout(resolve, 2000));

        setAvailableModels(prev => prev.map(model =>
          model.id === modelId
            ? { ...model, isOptimized: true, optimizationType }
            : model
        ));

        return { success: true };
      }
    } catch (err) {
      console.error('Failed to optimize model:', err);
      setError('Failed to optimize model');
      return { success: false, error: String(err) };
    } finally {
      setIsManagingModels(false);
    }
  }, []);

  const getModelPerformance = useCallback(async () => {
    try {
      if (window.electronAPI?.getModelPerformance) {
        const performance = await window.electronAPI.getModelPerformance();
        setModelPerformance(performance);
      }
    } catch (err) {
      console.error('Failed to get model performance:', err);
    }
  }, []);

  // Load settings and models on mount
  useEffect(() => {
    loadSettings();
    loadAvailableModels();
  }, [loadSettings, loadAvailableModels]);

  return {
    settings,
    isLoading,
    error,
    availableModels,
    modelPerformance,
    isManagingModels,
    updateSettings,
    resetSettings,
    updateAudioSettings,
    updateModelSettings,
    updateDisplaySettings,
    updateModelConfig,
    loadSettings,
    loadAvailableModels,
    downloadModel,
    optimizeModel,
    getModelPerformance,
  };
};

// Extend Window interface for Electron API
declare global {
  interface Window {
    electronAPI?: {
      getSettings: () => Promise<any>;
      updateSettings: (settings: any) => Promise<boolean>;
      getSystemInfo: () => Promise<any>;
      openFile: () => Promise<any>;
      saveFile: () => Promise<any>;
      getVersion: () => string;
      getAppVersion: () => string;
      getAvailableModels: () => Promise<any>;
      downloadModel: (modelId: string) => Promise<any>;
      optimizeModel: (modelId: string, optimizationType: string) => Promise<any>;
      getModelPerformance: () => Promise<any>;
      getModelStatus: (modelId: string) => Promise<any>;
    };
  }
}