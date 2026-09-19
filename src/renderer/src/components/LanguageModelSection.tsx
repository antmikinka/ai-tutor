import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
  InputLabel,
  Link,
  MenuItem,
  Select,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import { Bolt, Cloud, Computer, Memory, Refresh, RestartAlt, Visibility, VisibilityOff } from '@mui/icons-material';
import { useLLMConfig } from '../hooks/useLLMConfig';
import { ApiError, apiJson } from '../lib/backend';
import { describeLLMName, formatContext, formatPricePerMillion, presetById } from '../lib/llm';
import type { LLMConfig, LLMMode, LLMModelInfo, LLMPresetId, LLMTestResult } from '../types/MathTypes';

interface Draft {
  preset: LLMPresetId;
  base_url: string;
  api_key: string; // only what the user typed this session; '' = keep saved key
  model: string;
  timeout_seconds: number;
}

const draftFrom = (config: LLMConfig): Draft => ({
  preset: config.remote.preset,
  base_url: config.remote.base_url,
  api_key: '',
  model: config.remote.model,
  timeout_seconds: config.remote.timeout_seconds,
});

const MODE_HELP: Record<LLMMode, string> = {
  auto: 'Use the local model whenever it is loaded; otherwise fall back to the API provider below.',
  local: 'Only the model loaded in this app answers. Nothing leaves your machine. Word problems are unavailable until a reasoning model is loaded.',
  remote: 'Always use the API provider below, even if a local model is loaded.',
};

/**
 * Where free-form answers and generated practice problems come from:
 * the locally loaded model, OpenRouter / another OpenAI-compatible API, or
 * "auto" (local when loaded, otherwise the API). Saved on the backend so the
 * choice survives restarts and applies to every window.
 */
export const LanguageModelSection: React.FC<{ onToast: (message: string) => void }> = ({ onToast }) => {
  const { config, loading, error, update, reset, refresh } = useLLMConfig();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [clearKey, setClearKey] = useState(false);
  const [models, setModels] = useState<LLMModelInfo[]>([]);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<LLMTestResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [switchingMode, setSwitchingMode] = useState(false);

  useEffect(() => {
    if (config && draft === null) setDraft(draftFrom(config));
  }, [config, draft]);

  const preset = useMemo(() => (config && draft ? presetById(config.presets, draft.preset) : undefined), [config, draft]);

  const dirty = useMemo(() => {
    if (!config || !draft) return false;
    return (
      draft.preset !== config.remote.preset ||
      draft.base_url !== config.remote.base_url ||
      draft.model !== config.remote.model ||
      draft.timeout_seconds !== config.remote.timeout_seconds ||
      draft.api_key.trim() !== '' ||
      clearKey
    );
  }, [config, draft, clearKey]);

  const proposedPayload = useCallback(
    (d: Draft) => ({
      preset: d.preset,
      base_url: d.base_url,
      model: d.model,
      timeout_seconds: d.timeout_seconds,
      ...(d.api_key.trim() ? { api_key: d.api_key.trim() } : {}),
      ...(clearKey ? { clear_api_key: true } : {}),
    }),
    [clearKey],
  );

  const loadModels = useCallback(
    async (d: Draft, refreshList = false) => {
      if (!d.base_url) {
        setModels([]);
        return;
      }
      setModelsLoading(true);
      setModelsError(null);
      try {
        const body = await apiJson<{ models: LLMModelInfo[] }>(`/api/llm/models${refreshList ? '?refresh=true' : ''}`, 'POST', proposedPayload(d));
        setModels(body.models);
      } catch (err) {
        setModels([]);
        setModelsError(err instanceof ApiError ? String(err.detail ?? err.message) : err instanceof Error ? err.message : String(err));
      } finally {
        setModelsLoading(false);
      }
    },
    [proposedPayload],
  );

  // Fetch the model list when the provider/URL/key changes (debounced so typing a key doesn't spam the API).
  const listKey = draft ? `${draft.preset}|${draft.base_url}|${draft.api_key}|${clearKey}` : '';
  useEffect(() => {
    if (!draft) return;
    const timer = setTimeout(() => void loadModels(draft), 500);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listKey]);

  const changePreset = (id: LLMPresetId) => {
    if (!config || !draft) return;
    const next = presetById(config.presets, id);
    if (!next) return;
    const backToSaved = id === config.remote.preset;
    setDraft({
      ...draft,
      preset: id,
      base_url: backToSaved ? config.remote.base_url : next.base_url,
      model: backToSaved ? config.remote.model : next.default_model,
    });
    setTestResult(null);
  };

  const setMode = async (mode: LLMMode) => {
    if (!config || mode === config.mode) return;
    setSwitchingMode(true);
    try {
      const next = await update({ mode });
      onToast(next.active.name ? `Using ${describeLLMName(next.active.name)}` : 'Language model source changed (nothing available yet)');
    } catch (err) {
      onToast(err instanceof Error ? err.message : String(err));
    } finally {
      setSwitchingMode(false);
    }
  };

  const test = async () => {
    if (!draft) return;
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await apiJson<LLMTestResult>('/api/llm/test', 'POST', proposedPayload(draft)));
    } catch (err) {
      setTestResult({ ok: false, error: err instanceof Error ? err.message : String(err), latency_ms: 0, model: draft.model, provider: draft.preset });
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const next = await update(proposedPayload(draft));
      setDraft(draftFrom(next));
      setClearKey(false);
      onToast(next.remote.configured ? `Saved. ${next.active.name ? `Using ${describeLLMName(next.active.name)}.` : ''}` : 'Saved. Choose a model to finish setting up the provider.');
    } catch (err) {
      onToast(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const doReset = async () => {
    if (!window.confirm('Forget the provider, key and model chosen in the app and go back to the backend defaults (.env)?')) return;
    try {
      const next = await reset();
      setDraft(draftFrom(next));
      setClearKey(false);
      setTestResult(null);
      onToast('Language model settings reset');
    } catch (err) {
      onToast(err instanceof Error ? err.message : String(err));
    }
  };

  const selectedModel = useMemo(() => models.find((m) => m.id === draft?.model) ?? null, [models, draft?.model]);
  const keyNeeded = Boolean(preset?.needs_key) && !config?.remote.has_api_key && !(draft?.api_key.trim());

  return (
    <Card sx={{ mb: 3 }}>
      <CardHeader
        avatar={<Memory />}
        title="Language model"
        subheader="Answers free-form word problems and writes practice problems. The symbolic engine always verifies the result before you see it."
        action={
          <Button size="small" onClick={() => void refresh()} startIcon={<Refresh />}>
            Refresh
          </Button>
        }
      />
      <CardContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>Backend unreachable: {error}</Alert>}
        {!config || !draft ? (
          loading ? <CircularProgress size={24} /> : null
        ) : (
          <Stack spacing={3}>
            {/* ---- Source ---- */}
            <Box>
              <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" rowGap={1} sx={{ mb: 1 }}>
                <Typography variant="subtitle2">Source</Typography>
                <Chip
                  size="small"
                  color={config.active.backend ? 'success' : 'default'}
                  icon={config.active.backend === 'local' ? <Computer /> : config.active.backend === 'remote' ? <Cloud /> : undefined}
                  label={config.active.name ? `Active: ${describeLLMName(config.active.name)}` : 'Active: none (symbolic engine only)'}
                />
                {switchingMode && <CircularProgress size={16} />}
              </Stack>
              <ToggleButtonGroup exclusive size="small" value={config.mode} onChange={(_, v: LLMMode | null) => v && void setMode(v)} disabled={switchingMode}>
                <ToggleButton value="auto" aria-label="Automatic">
                  <Bolt fontSize="small" sx={{ mr: 0.5 }} /> Auto
                </ToggleButton>
                <ToggleButton value="local" aria-label="Local model only">
                  <Computer fontSize="small" sx={{ mr: 0.5 }} /> Local model
                </ToggleButton>
                <ToggleButton value="remote" aria-label="API provider">
                  <Cloud fontSize="small" sx={{ mr: 0.5 }} /> API (OpenRouter…)
                </ToggleButton>
              </ToggleButtonGroup>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.75 }}>
                {MODE_HELP[config.mode]}
              </Typography>
              {config.mode !== 'remote' && !config.local.ready && (
                <Alert severity="info" sx={{ mt: 1, py: 0 }}>
                  No local reasoning model is loaded{config.local.ml_stack ? '' : ' (the ML stack is not installed)'}. Load <strong>{config.local.model}</strong> from “AI models” below
                  {config.mode === 'auto' ? ', or the API provider below will be used.' : '.'}
                </Alert>
              )}
              {config.mode === 'remote' && !config.remote.configured && (
                <Alert severity="warning" sx={{ mt: 1, py: 0 }}>
                  Fill in the provider, key and model below, then Save.
                </Alert>
              )}
            </Box>

            {/* ---- Provider ---- */}
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                API provider
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={4}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Provider</InputLabel>
                    <Select value={draft.preset} label="Provider" onChange={(e) => changePreset(e.target.value as LLMPresetId)}>
                      {config.presets.map((p) => (
                        <MenuItem key={p.id} value={p.id}>
                          {p.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  {preset && (
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                      {preset.description}
                    </Typography>
                  )}
                </Grid>
                <Grid item xs={12} md={8}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Base URL"
                    value={draft.base_url}
                    onChange={(e) => setDraft({ ...draft, base_url: e.target.value })}
                    placeholder="https://openrouter.ai/api/v1"
                    helperText={preset?.local ? 'Start the local server first; the default port is shown.' : 'OpenAI-compatible: must expose /chat/completions and /models.'}
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    size="small"
                    type={showKey ? 'text' : 'password'}
                    label="API key"
                    value={draft.api_key}
                    onChange={(e) => {
                      setDraft({ ...draft, api_key: e.target.value });
                      if (e.target.value) setClearKey(false);
                    }}
                    autoComplete="off"
                    InputLabelProps={{ shrink: true }}
                    placeholder={clearKey ? 'Key will be removed on save' : config.remote.has_api_key ? `Saved: ${config.remote.api_key_hint} (type to replace)` : preset?.needs_key ? 'Required for this provider' : 'Optional'}
                    error={keyNeeded && config.mode !== 'local'}
                    InputProps={{
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton size="small" onClick={() => setShowKey((s) => !s)} aria-label={showKey ? 'Hide key' : 'Show key'}>
                            {showKey ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }}
                    helperText={
                      <>
                        {preset?.key_url && (
                          <Link href={preset.key_url} target="_blank" rel="noreferrer">
                            Get a {preset.label} key
                          </Link>
                        )}
                        {preset?.key_url && config.remote.has_api_key ? ' · ' : ''}
                        {config.remote.has_api_key && !clearKey && (
                          <Link component="button" type="button" onClick={() => setClearKey(true)}>
                            Remove saved key
                          </Link>
                        )}
                        {clearKey && (
                          <Link component="button" type="button" onClick={() => setClearKey(false)}>
                            Keep saved key
                          </Link>
                        )}
                      </>
                    }
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <Autocomplete<LLMModelInfo | string, false, false, true>
                    freeSolo
                    size="small"
                    options={models}
                    loading={modelsLoading}
                    value={selectedModel ?? draft.model}
                    inputValue={draft.model}
                    onInputChange={(_, value, reason) => {
                      if (reason === 'reset' && !value) return;
                      setDraft((d) => (d ? { ...d, model: value } : d));
                    }}
                    onChange={(_, value) => setDraft((d) => (d ? { ...d, model: typeof value === 'string' ? value : value?.id ?? '' } : d))}
                    getOptionLabel={(o) => (typeof o === 'string' ? o : o.id)}
                    isOptionEqualToValue={(o, v) => (typeof o === 'string' ? o : o.id) === (typeof v === 'string' ? v : v.id)}
                    filterOptions={(opts, state) => {
                      const q = state.inputValue.trim().toLowerCase();
                      const filtered = q ? opts.filter((o) => typeof o !== 'string' && (o.id.toLowerCase().includes(q) || o.name.toLowerCase().includes(q))) : opts;
                      return filtered.slice(0, 60);
                    }}
                    renderOption={(props, option) => {
                      if (typeof option === 'string') return <li {...props}>{option}</li>;
                      const price = formatPricePerMillion(option.prompt_price);
                      const ctx = formatContext(option.context_length);
                      return (
                        <li {...props} key={option.id}>
                          <Box sx={{ minWidth: 0, flex: 1 }}>
                            <Typography variant="body2" noWrap>
                              {option.id}
                            </Typography>
                            <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.25 }}>
                              {option.name !== option.id && (
                                <Typography variant="caption" color="text.secondary" noWrap sx={{ mr: 0.5 }}>
                                  {option.name}
                                </Typography>
                              )}
                              {option.recommended && <Chip size="small" color="primary" variant="outlined" label="good at math" sx={{ height: 18 }} />}
                              {option.free && <Chip size="small" color="success" variant="outlined" label="free" sx={{ height: 18 }} />}
                              {ctx && <Chip size="small" variant="outlined" label={ctx} sx={{ height: 18 }} />}
                              {price && price !== 'free' && <Chip size="small" variant="outlined" label={`${price} in`} sx={{ height: 18 }} />}
                            </Stack>
                          </Box>
                        </li>
                      );
                    }}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Model"
                        placeholder={preset?.default_model || 'model id'}
                        error={Boolean(modelsError) && !draft.model}
                        helperText={
                          modelsError ? `Could not list models: ${modelsError}` : models.length ? `${models.length} models available · type to search or enter an id` : 'Type a model id, or list models once the URL and key are filled in'
                        }
                        InputProps={{
                          ...params.InputProps,
                          endAdornment: (
                            <>
                              {modelsLoading ? <CircularProgress size={16} /> : null}
                              <Tooltip title="Reload the model list">
                                <IconButton size="small" onClick={() => void loadModels(draft, true)} aria-label="Reload models">
                                  <Refresh fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              {params.InputProps.endAdornment}
                            </>
                          ),
                        }}
                      />
                    )}
                  />
                </Grid>
                <Grid item xs={12} md={3}>
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    label="Timeout (s)"
                    value={draft.timeout_seconds}
                    inputProps={{ min: 5, max: 600, step: 5 }}
                    onChange={(e) => setDraft({ ...draft, timeout_seconds: Math.max(1, Math.min(600, Number(e.target.value) || 60)) })}
                  />
                </Grid>
              </Grid>

              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" rowGap={1} sx={{ mt: 2 }}>
                <Button variant="outlined" onClick={() => void test()} disabled={testing || !draft.base_url || !draft.model} startIcon={testing ? <CircularProgress size={16} /> : <Bolt />}>
                  Test connection
                </Button>
                <Button variant="contained" onClick={() => void save()} disabled={saving || !dirty} startIcon={saving ? <CircularProgress size={16} /> : undefined}>
                  Save & use
                </Button>
                <Button color="inherit" onClick={() => void doReset()} startIcon={<RestartAlt />} sx={{ ml: 'auto' }}>
                  Reset to defaults
                </Button>
              </Stack>
              {testResult && (
                <Alert severity={testResult.ok ? 'success' : 'error'} sx={{ mt: 1.5 }} onClose={() => setTestResult(null)}>
                  {testResult.ok
                    ? `${describeLLMName(`${testResult.provider}:${testResult.model}`)} answered in ${testResult.latency_ms} ms${testResult.reply ? ` (“${testResult.reply}”)` : ''}. ${dirty ? 'Press “Save & use” to keep these settings.' : ''}`
                    : testResult.error}
                </Alert>
              )}
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
                The key is stored only on this computer ({config.config_path}) and sent solely to the base URL above. When a problem is answered by the API, the problem text and, for practice, the retrieved course-material passages are sent to that provider.
              </Typography>
            </Box>
          </Stack>
        )}
      </CardContent>
    </Card>
  );
};
