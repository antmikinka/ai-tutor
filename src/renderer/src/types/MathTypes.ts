import type { BackendSolution, BackendVerification, DrawingAnalysis } from './protocol';

// ---- chat --------------------------------------------------------------

interface ChatBase {
  id: string;
  timestamp: string;
}

export type UserInputSource = 'text' | 'voice' | 'drawing' | 'image';

export type ChatMessage =
  | (ChatBase & { kind: 'user'; text: string; source: UserInputSource })
  | (ChatBase & { kind: 'solution'; solution: BackendSolution })
  | (ChatBase & { kind: 'verification'; problem: string; proposed: string; verdict: BackendVerification })
  | (ChatBase & { kind: 'drawing'; analysis: DrawingAnalysis })
  | (ChatBase & { kind: 'info'; text: string })
  | (ChatBase & { kind: 'error'; text: string; code?: string });

/** Distributive Omit so each union member keeps its own fields. */
type DistributiveOmit<T, K extends keyof T> = T extends unknown ? Omit<T, K> : never;
export type ChatMessageInput = DistributiveOmit<ChatMessage, 'id' | 'timestamp'>;

// ---- settings ----------------------------------------------------------

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

// ---- backend model management (GET /api/models) -------------------------

export type BackendModelStatus = 'loaded' | 'loading' | 'error' | 'unavailable' | 'available' | 'not_downloaded';

export interface BackendModel {
  name: string;
  model_name: string;
  type: string;
  model_id: string;
  description: string;
  status: BackendModelStatus;
  downloaded: boolean;
  path: string;
  device: string | null;
  memory_usage: number;
  loading_progress: number;
  loaded_at: string | null;
  error: string | null;
  requirements: { file_size_gb: number; memory_required_gb: number; gpu_required: boolean };
}

export interface SystemResources {
  cpu: { percent_used: number | null; count: number | null };
  memory: { total_gb?: number; available_gb?: number; used_gb?: number; percent_used?: number };
  disk: { total_gb?: number; free_gb?: number; used_gb?: number; percent_used?: number };
  gpu: Array<{ device_id: number; name: string; memory_total_gb: number; memory_allocated_gb: number }>;
  ml_stack: Record<string, unknown>;
  timestamp: string;
}
