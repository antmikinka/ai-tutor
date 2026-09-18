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

export type WhiteboardGrid = 'none' | 'dots' | 'lines';

export interface WhiteboardSettings {
  grid: WhiteboardGrid;
  penColor: string;
  penWidth: number;
  /** Show the keyboard-shortcut hint row above the canvas. */
  showShortcutHints: boolean;
}

export type PracticeDifficulty = 'easy' | 'medium' | 'hard';

export interface PracticeSettings {
  difficulty: PracticeDifficulty;
  /** Reveal the modelling equation alongside the word problem immediately. */
  showEquationImmediately: boolean;
  /** Prefer the language model (when available) over the template generator. */
  preferLanguageModel: boolean;
}

export interface UserSettings {
  audioSettings: AudioSettings;
  modelSettings: ModelSettings;
  displaySettings: DisplaySettings;
  whiteboardSettings: WhiteboardSettings;
  practiceSettings: PracticeSettings;
  modelConfig: ModelConfig;
  appVersion: string;
}

// ---- knowledge base (/api/knowledge) --------------------------------------

export interface KnowledgeStatus {
  available: boolean;
  error: string | null;
  backend: 'chroma' | 'local' | null;
  embedding: 'minilm' | 'hashing' | null;
  documents: number;
  chunks: number;
  supported_extensions: string[];
  max_upload_bytes: number;
}

export interface KnowledgeDocument {
  id: string;
  title: string;
  source: string;
  tags: string[];
  chars: number;
  chunks: number;
  pages: number | null;
  created_at: string;
  preview: string;
}

export interface KnowledgeHit {
  chunk_id: string;
  doc_id: string;
  title: string;
  source: string;
  page: number | null;
  chunk_index: number;
  score: number;
  text: string;
}

// ---- practice (/api/practice) ---------------------------------------------

export interface PracticeSource {
  doc_id: string;
  title: string;
  page: number | null;
  score: number;
  text: string;
  snippet: string;
}

export interface PracticeProblem {
  id: string;
  topic: string;
  difficulty: PracticeDifficulty;
  family: string;
  family_label: string;
  concept: string;
  problem: string;
  equation: string;
  equation_latex: string;
  variable: string | null;
  hints_available: number;
  hints_used: number;
  hints: string[];
  sources: PracticeSource[];
  generator: string;
  note: string | null;
  attempts: number;
  solved: boolean;
  revealed: boolean;
  created_at: string;
  processing_time?: number;
}

export interface PracticeStats {
  generated: number;
  solved: number;
  first_try: number;
  attempts: number;
  revealed: number;
  streak: number;
  best_streak: number;
  by_family: Record<string, number>;
}

export interface PracticeCheck {
  problem_id: string;
  correct: boolean;
  unreadable: boolean;
  feedback: string;
  attempts: number;
  solved: boolean;
  hint: string | null;
  hints_used: number;
  hints_available: number;
  answer: string | null;
  stats: PracticeStats;
}

export interface PracticeSolution {
  problem_id: string;
  equation: string;
  equation_latex: string;
  answer: string;
  engine_solution: string;
  solution_latex: string;
  steps: string[];
  hints: string[];
  stats: PracticeStats;
}

export interface PracticeStatus {
  llm_available: boolean;
  llm: string | null;
  knowledge_available: boolean;
  documents: number;
  families: Array<{ id: string; label: string; keywords: string[] }>;
  difficulties: PracticeDifficulty[];
  stats: PracticeStats;
}

// ---- language model source (/api/llm) -------------------------------------

export type LLMMode = 'auto' | 'local' | 'remote';
export type LLMPresetId = 'openrouter' | 'openai' | 'ollama' | 'lmstudio' | 'custom' | (string & {});

export interface LLMPreset {
  id: LLMPresetId;
  label: string;
  base_url: string;
  needs_key: boolean;
  key_url: string | null;
  default_model: string;
  description: string;
  local: boolean;
}

export interface LLMRemoteConfig {
  preset: LLMPresetId;
  base_url: string;
  model: string;
  timeout_seconds: number;
  has_api_key: boolean;
  api_key_hint: string | null;
  configured: boolean;
}

export interface LLMConfig {
  mode: LLMMode;
  remote: LLMRemoteConfig;
  presets: LLMPreset[];
  config_path: string;
  active: { backend: 'local' | 'remote' | null; name: string | null };
  local: { ready: boolean; model: string; ml_stack: boolean; allowed: boolean };
  remote_active: boolean;
}

export interface LLMConfigUpdate {
  mode?: LLMMode;
  preset?: LLMPresetId;
  base_url?: string;
  api_key?: string;
  clear_api_key?: boolean;
  model?: string;
  timeout_seconds?: number;
}

export interface LLMModelInfo {
  id: string;
  name: string;
  context_length: number | null;
  prompt_price: number | null;
  completion_price: number | null;
  free: boolean | null;
  recommended: boolean;
}

export interface LLMTestResult {
  ok: boolean;
  error: string | null;
  reply?: string;
  latency_ms: number;
  model: string;
  provider: string;
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
