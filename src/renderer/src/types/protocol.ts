/**
 * WebSocket protocol shared with src/backend/main.py.
 */

export interface BackendSolution {
  id: string;
  problem: string;
  solution: string;
  solution_latex: string;
  steps: string[];
  thinking_process: string[];
  confidence: number;
  problem_type: string;
  variable: string | null;
  processing_time: number;
  model_used: string;
  tokens_used: number;
  verification: { is_correct: boolean | null; confidence: number; method: string };
  timestamp: string;
}

export interface BackendVerification {
  is_correct: boolean;
  confidence: number;
  feedback: string;
  expected: string | null;
  expected_steps: string[];
  alternative_solutions: string[];
  timestamp: string;
}

export interface ImageAnalysis {
  is_blank: boolean;
  ink_coverage: number;
  components: number;
  bounding_box: { x: number; y: number; width: number; height: number } | null;
}

export interface DrawingAnalysis {
  available: boolean;
  recognized_text: string;
  equations: Array<{ text?: string; equation?: string; confidence?: number }>;
  shapes: unknown[];
  concepts: string[];
  confidence: number;
  model_used: string;
  message?: string;
  image_analysis?: ImageAnalysis;
  timestamp: string;
}

export interface Capabilities {
  symbolic_solver: boolean;
  /** A language model (local Qwen3-Omni or a configured OpenAI-compatible endpoint) is available. */
  llm: boolean;
  /** `provider:model`, e.g. `qwen3-omni:...`, `openrouter:openai/gpt-4o-mini`, `ollama:llama3.1`. */
  llm_name?: string | null;
  llm_mode?: 'auto' | 'local' | 'remote';
  speech: boolean;
  drawing_recognition: boolean;
  knowledge_base?: boolean;
  practice?: boolean;
}

// ---- outbound ------------------------------------------------------------

export type OutboundMessage =
  | { type: 'ping'; request_id?: string }
  | { type: 'math_input'; content: string; metadata?: Record<string, unknown>; request_id?: string }
  | { type: 'verify'; problem: string; solution: string; request_id?: string }
  | { type: 'drawing'; data: string | { image: string; objects?: unknown[] }; analysis_type?: string; request_id?: string }
  | { type: 'audio'; data: string; language?: string; format?: string; request_id?: string };

// ---- inbound -------------------------------------------------------------

interface Envelope {
  request_id?: string | null;
  timestamp: string;
}

export type InboundMessage =
  | (Envelope & { type: 'connected'; client_id: string; server_version: string; capabilities: Capabilities })
  /** Pushed when a capability changes mid-session (e.g. the language model source was switched). */
  | (Envelope & { type: 'capabilities'; capabilities: Capabilities })
  | (Envelope & { type: 'pong' })
  | (Envelope & { type: 'math_solution'; solution: BackendSolution })
  | (Envelope & { type: 'verification'; data: BackendVerification })
  | (Envelope & { type: 'drawing_analysis'; data: DrawingAnalysis })
  | (Envelope & { type: 'audio_transcription'; text: string; confidence: number; available: boolean; message?: string | null })
  | (Envelope & { type: 'audio_response'; data: { audio_data: string | null; sample_rate: number; format: string } })
  | (Envelope & { type: 'error'; code: string; message: string });

export type InboundType = InboundMessage['type'];
export type MessageOf<T extends InboundType> = Extract<InboundMessage, { type: T }>;
