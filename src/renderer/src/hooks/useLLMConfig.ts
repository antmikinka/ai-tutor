import { useCallback, useEffect, useState } from 'react';
import { ApiError, apiFetch, apiJson } from '../lib/backend';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import type { LLMConfig, LLMConfigUpdate } from '../types/MathTypes';

/**
 * Backend-owned language model source (local / OpenRouter / other API / auto).
 *
 * The backend broadcasts new capabilities whenever the source changes, so
 * every mounted consumer refreshes without polling.
 */
export const useLLMConfig = (enabled = true) => {
  const { capabilities, connectionStatus } = useWebSocketContext();
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setConfig(await apiFetch<LLMConfig>('/api/llm/config'));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (enabled) void refresh();
  }, [enabled, refresh]);

  // Any capability push (llm_name / llm_mode change) means our snapshot is stale.
  const llmSignature = `${capabilities?.llm_name ?? ''}|${capabilities?.llm_mode ?? ''}|${connectionStatus}`;
  useEffect(() => {
    if (enabled && connectionStatus === 'connected') void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [llmSignature]);

  const update = useCallback(async (patch: LLMConfigUpdate): Promise<LLMConfig> => {
    try {
      const next = await apiJson<LLMConfig>('/api/llm/config', 'PUT', patch);
      setConfig(next);
      setError(null);
      return next;
    } catch (err) {
      const message = err instanceof ApiError ? String(err.detail ?? err.message) : err instanceof Error ? err.message : String(err);
      setError(message);
      throw new Error(message);
    }
  }, []);

  const reset = useCallback(async (): Promise<LLMConfig> => {
    const next = await apiJson<LLMConfig>('/api/llm/config', 'DELETE');
    setConfig(next);
    return next;
  }, []);

  return { config, loading, error, refresh, update, reset };
};
