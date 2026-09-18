import type { LLMPreset, LLMPresetId } from '../types/MathTypes';

const PROVIDER_LABELS: Record<string, string> = {
  'qwen3-omni': 'Local model',
  openrouter: 'OpenRouter',
  openai: 'OpenAI',
  ollama: 'Ollama',
  lmstudio: 'LM Studio',
  custom: 'API',
  remote: 'API',
  sympy: 'Symbolic engine (SymPy)',
};

/** Split a backend `provider:model` name into something people can read. */
export const describeLLMName = (name: string | null | undefined): string => {
  if (!name) return 'No language model';
  if (name === 'sympy') return PROVIDER_LABELS.sympy;
  if (name === 'none') return 'No engine could answer';
  const idx = name.indexOf(':');
  if (idx === -1) return name;
  const provider = name.slice(0, idx);
  const model = name.slice(idx + 1);
  const label = PROVIDER_LABELS[provider] ?? provider;
  return model ? `${label} · ${model}` : label;
};

export const presetById = (presets: LLMPreset[] | undefined, id: LLMPresetId): LLMPreset | undefined => presets?.find((p) => p.id === id);

/** USD per token -> "$0.15 / 1M tokens". */
export const formatPricePerMillion = (perToken: number | null | undefined): string | null => {
  if (perToken == null) return null;
  if (perToken === 0) return 'free';
  const perMillion = perToken * 1_000_000;
  return perMillion >= 1 ? `$${perMillion.toFixed(2)}/M` : `$${perMillion.toFixed(3)}/M`;
};

export const formatContext = (tokens: number | null | undefined): string | null => {
  if (!tokens) return null;
  return tokens >= 1000 ? `${Math.round(tokens / 1000)}k ctx` : `${tokens} ctx`;
};
