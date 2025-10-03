export interface MathSolution {
  id: string;
  problem: string;
  solution: string;
  steps?: string[];
  confidence: number;
  timestamp: string;
  metadata?: {
    toolUsed?: string;
    difficulty?: 'easy' | 'medium' | 'hard';
    category?: string;
    tags?: string[];
    modelUsed?: string;
    thinkingProcess?: string;
  };
}

export interface DrawingData {
  type: 'drawing' | 'text' | 'shape';
  data: string;
  timestamp: string;
  metadata?: {
    tool: string;
    color: string;
    lineWidth: number;
  };
}

export interface AudioData {
  type: 'speech_input' | 'speech_output';
  data: string;
  timestamp: string;
  metadata?: {
    duration?: number;
    language?: string;
    confidence?: number;
    modelUsed?: string;
    educationalMode?: boolean;
    noiseReduction?: boolean;
  };
}

export interface ModelInfo {
  id: string;
  name: string;
  description: string;
  type: 'reasoning' | 'tts' | 'stt';
  size: string;
  memoryRequired: number;
  gpuRequired: boolean;
  status: 'not_downloaded' | 'downloading' | 'loaded' | 'error';
  downloadProgress?: number;
  supportedLanguages: string[];
  specialFeatures: string[];
  lastUsed?: string;
  isOptimized?: boolean;
  optimizationType?: string;
}

export interface ModelConfig {
  reasoningModel: string;
  ttsModel: string;
  sttModel: string;
  enableFallback: boolean;
  autoOptimize: boolean;
  optimizationSettings: {
    quantization: boolean;
    pruning: boolean;
    useGPU: boolean;
    maxMemoryUsage: number;
  };
}

export interface AudioSettings {
  inputDevice: string;
  outputDevice: string;
  volume: number;
  enableSpeechRecognition: boolean;
  enableTextToSpeech: boolean;
  ttsVoice: string;
  ttsLanguage: string;
  ttsSpeed: number;
  ttsPitch: number;
  sttLanguage: string;
  sttModel: string;
  enableEducationalMode: boolean;
  enableNoiseReduction: boolean;
}

export interface ModelSettings {
  temperature: number;
  maxTokens: number;
  useGPU: boolean;
  modelPath: string;
  reasoningModel: string;
  enableThinking: boolean;
  showStepByStep: boolean;
  enableChainOfThought: boolean;
}

export interface DisplaySettings {
  theme: 'light' | 'dark' | 'auto';
  fontSize: number;
  showStepByStep: boolean;
  showConfidence: boolean;
  showModelInfo: boolean;
  showPerformanceMetrics: boolean;
}

export interface UserSettings {
  audioSettings: AudioSettings;
  modelSettings: ModelSettings;
  displaySettings: DisplaySettings;
  modelConfig: ModelConfig;
  appVersion: string;
}

export interface SystemInfo {
  platform: string;
  arch: string;
  version: string;
  electronVersion: string;
  screens: Array<{
    id: number;
    width: number;
    height: number;
    scaleFactor: number;
  }>;
  memory: {
    total: number;
    free: number;
    used: number;
  };
  cpu: {
    model: string;
    cores: number;
    architecture: string;
  };
  gpu?: Array<{
    id: number;
    name: string;
    memory: number;
    isAvailable: boolean;
  }>;
}

export interface ModelPerformanceMetrics {
  modelId: string;
  loadTime: number;
  inferenceTime: number;
  memoryUsage: number;
  accuracy: number;
  timestamp: string;
}