import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Slider,
  Snackbar,
  Stack,
  Switch,
  Tooltip,
  Typography,
} from '@mui/material';
import { CheckCircle, Delete, Download, ErrorOutline, Memory, Mic, Monitor, Refresh, Save, School, Speed, VolumeUp } from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import { useSettingsContext } from '../contexts/SettingsContext';
import { LanguageModelSection } from '../components/LanguageModelSection';
import { ApiError, apiFetch } from '../lib/backend';
import { describeLLMName } from '../lib/llm';
import type { BackendModel, BackendModelStatus, KnowledgeStatus, PracticeStatus, SystemResources, UserSettings } from '../types/MathTypes';

const Container = styled(Box)(({ theme }) => ({
  padding: theme.spacing(3),
  maxWidth: 1100,
  margin: '0 auto',
}));

const Section = styled(Card)(({ theme }) => ({
  marginBottom: theme.spacing(3),
}));

const STATUS_META: Record<BackendModelStatus, { label: string; color: 'success' | 'warning' | 'error' | 'default' | 'info' }> = {
  loaded: { label: 'Loaded', color: 'success' },
  loading: { label: 'Loading', color: 'warning' },
  error: { label: 'Error', color: 'error' },
  available: { label: 'Downloaded', color: 'info' },
  not_downloaded: { label: 'Not downloaded', color: 'default' },
  unavailable: { label: 'ML stack missing', color: 'default' },
};

const MODEL_ICON: Record<string, React.ReactNode> = {
  reasoning: <Memory />,
  tts: <VolumeUp />,
  fallback_tts: <VolumeUp />,
  stt: <Mic />,
  fallback_stt: <Mic />,
};

const gb = (value?: number | null) => (value == null ? '—' : `${value.toFixed(1)} GB`);
const mb = (value: number) => (value >= 1024 ? `${(value / 1024).toFixed(1)} GB` : `${value.toFixed(0)} MB`);

const POLL_MS = 4000;

export const SettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const { settings, updateSettings, resetSettings, isLoading, error } = useSettingsContext();
  const [draft, setDraft] = useState<UserSettings>(settings);
  const [learning, setLearning] = useState<{ knowledge: KnowledgeStatus; practice: PracticeStatus } | null>(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const [models, setModels] = useState<BackendModel[] | null>(null);
  const [resources, setResources] = useState<SystemResources | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [autoLoad, setAutoLoad] = useState<{ enabled: boolean; models: string[] } | null>(null);
  const [devices, setDevices] = useState<{ inputs: MediaDeviceInfo[]; outputs: MediaDeviceInfo[] }>({ inputs: [], outputs: [] });

  const pollTimers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  useEffect(() => setDraft(settings), [settings]);
  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(settings), [draft, settings]);

  // ---- backend data ------------------------------------------------------

  const refresh = useCallback(async () => {
    try {
      const [modelsBody, resourcesBody, persistence] = await Promise.all([
        apiFetch<{ models: BackendModel[] }>('/api/models'),
        apiFetch<SystemResources>('/api/models/system/resources'),
        apiFetch<{ config: { enabled: boolean; models: string[] } }>('/api/models/persistence/config'),
      ]);
      setModels(modelsBody.models);
      setResources(resourcesBody);
      setAutoLoad(persistence.config);
      setBackendError(null);
    } catch (err) {
      setBackendError(err instanceof Error ? err.message : 'Backend unreachable');
    }
    try {
      const [knowledge, practice] = await Promise.all([apiFetch<KnowledgeStatus>('/api/knowledge/status'), apiFetch<PracticeStatus>('/api/practice/status')]);
      setLearning({ knowledge, practice });
    } catch {
      setLearning(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 15_000);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    navigator.mediaDevices
      .enumerateDevices()
      .then((list) =>
        setDevices({
          inputs: list.filter((d) => d.kind === 'audioinput'),
          outputs: list.filter((d) => d.kind === 'audiooutput'),
        }),
      )
      .catch(() => undefined);
  }, []);

  useEffect(() => () => Object.values(pollTimers.current).forEach(clearInterval), []);

  const pollUntilSettled = (name: string) => {
    if (pollTimers.current[name]) clearInterval(pollTimers.current[name]);
    pollTimers.current[name] = setInterval(async () => {
      try {
        const info = await apiFetch<BackendModel>(`/api/models/${encodeURIComponent(name)}/status`);
        setModels((prev) => prev?.map((m) => (m.name === name ? { ...m, ...info } : m)) ?? prev);
        if (info.status !== 'loading') {
          clearInterval(pollTimers.current[name]);
          delete pollTimers.current[name];
          setBusy((b) => ({ ...b, [name]: false }));
          setToast(info.status === 'loaded' ? `${name} loaded` : `${name}: ${info.error || info.status}`);
        }
      } catch {
        clearInterval(pollTimers.current[name]);
        delete pollTimers.current[name];
        setBusy((b) => ({ ...b, [name]: false }));
      }
    }, POLL_MS);
  };

  const loadModel = async (model: BackendModel) => {
    setBusy((b) => ({ ...b, [model.name]: true }));
    try {
      const result = await apiFetch<{ status: string; message: string }>(`/api/models/load/${encodeURIComponent(model.name)}`, {
        method: 'POST',
        body: JSON.stringify({ options: {}, wait: false }),
      });
      setToast(result.message);
      if (result.status === 'loading') pollUntilSettled(model.name);
      else {
        setBusy((b) => ({ ...b, [model.name]: false }));
        void refresh();
      }
    } catch (err) {
      setBusy((b) => ({ ...b, [model.name]: false }));
      setToast(err instanceof ApiError ? String(err.detail ?? err.message) : String(err));
    }
  };

  const unloadModel = async (model: BackendModel) => {
    setBusy((b) => ({ ...b, [model.name]: true }));
    try {
      await apiFetch(`/api/models/unload/${encodeURIComponent(model.name)}`, { method: 'DELETE' });
      setToast(`${model.name} unloaded`);
      await refresh();
    } catch (err) {
      setToast(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy((b) => ({ ...b, [model.name]: false }));
    }
  };

  const toggleAutoLoad = async (enabled: boolean) => {
    const next = { enabled, models: autoLoad?.models ?? [] };
    setAutoLoad(next);
    try {
      await apiFetch('/api/models/persistence/config', { method: 'POST', body: JSON.stringify(next) });
    } catch (err) {
      setToast(err instanceof Error ? err.message : String(err));
    }
  };

  // ---- local settings ----------------------------------------------------

  const setField = <S extends keyof UserSettings>(section: S, patch: Partial<UserSettings[S]>) =>
    setDraft((prev) => ({ ...prev, [section]: { ...(prev[section] as object), ...patch } }));

  const save = async () => {
    setSaving(true);
    const ok = await updateSettings(draft);
    setSaving(false);
    setToast(ok ? 'Settings saved' : 'Failed to save settings');
  };

  const reset = async () => {
    if (!window.confirm('Reset all settings to their defaults?')) return;
    setSaving(true);
    await resetSettings();
    setSaving(false);
    setToast('Settings reset');
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="60vh">
        <CircularProgress />
      </Box>
    );
  }

  const mlStackMissing = resources && resources.ml_stack && resources.ml_stack.torch === false;

  return (
    <Container>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h4" component="h1">
          Settings
        </Typography>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" color="error" onClick={reset} disabled={saving}>
            Reset to defaults
          </Button>
          <Button variant="contained" onClick={save} disabled={saving || !dirty} startIcon={saving ? <CircularProgress size={18} /> : <Save />}>
            Save
          </Button>
        </Stack>
      </Stack>

      {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
      {dirty && <Alert severity="info" sx={{ mb: 2 }}>You have unsaved changes.</Alert>}

      {/* ---- Display ---- */}
      <Section>
        <CardHeader avatar={<Monitor />} title="Display" subheader="Appearance of the tutor" />
        <CardContent>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Theme</InputLabel>
                <Select value={draft.displaySettings.theme} label="Theme" onChange={(e) => setField('displaySettings', { theme: e.target.value as UserSettings['displaySettings']['theme'] })}>
                  <MenuItem value="light">Light</MenuItem>
                  <MenuItem value="dark">Dark</MenuItem>
                  <MenuItem value="auto">Follow system</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Base font size: {draft.displaySettings.fontSize}px</Typography>
              <Slider value={draft.displaySettings.fontSize} min={11} max={20} onChange={(_, v) => setField('displaySettings', { fontSize: v as number })} valueLabelDisplay="auto" />
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControlLabel control={<Switch checked={draft.displaySettings.showStepByStep} onChange={(e) => setField('displaySettings', { showStepByStep: e.target.checked })} />} label="Show step-by-step working" />
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControlLabel control={<Switch checked={draft.displaySettings.showConfidence} onChange={(e) => setField('displaySettings', { showConfidence: e.target.checked })} />} label="Show confidence" />
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControlLabel control={<Switch checked={draft.displaySettings.showModelInfo} onChange={(e) => setField('displaySettings', { showModelInfo: e.target.checked })} />} label="Show engine and timing" />
            </Grid>
          </Grid>
        </CardContent>
      </Section>

      {/* ---- Whiteboard & practice ---- */}
      <Section>
        <CardHeader avatar={<School />} title="Whiteboard & practice" subheader="Learn-by-doing defaults. The quick-settings button in the top bar changes the same options mid-session." />
        <CardContent>
          <Grid container spacing={3}>
            <Grid item xs={12} md={4}>
              <FormControl fullWidth>
                <InputLabel>Whiteboard background</InputLabel>
                <Select value={draft.whiteboardSettings.grid} label="Whiteboard background" onChange={(e) => setField('whiteboardSettings', { grid: e.target.value as UserSettings['whiteboardSettings']['grid'] })}>
                  <MenuItem value="none">Plain</MenuItem>
                  <MenuItem value="dots">Dot grid</MenuItem>
                  <MenuItem value="lines">Square grid</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControl fullWidth>
                <InputLabel>Default difficulty</InputLabel>
                <Select value={draft.practiceSettings.difficulty} label="Default difficulty" onChange={(e) => setField('practiceSettings', { difficulty: e.target.value as UserSettings['practiceSettings']['difficulty'] })}>
                  <MenuItem value="easy">Easy</MenuItem>
                  <MenuItem value="medium">Medium</MenuItem>
                  <MenuItem value="hard">Hard</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={4}>
              <FormControlLabel control={<Switch checked={draft.whiteboardSettings.showShortcutHints} onChange={(e) => setField('whiteboardSettings', { showShortcutHints: e.target.checked })} />} label="Show keyboard shortcut hints" />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={<Switch checked={draft.practiceSettings.showEquationImmediately} onChange={(e) => setField('practiceSettings', { showEquationImmediately: e.target.checked })} />}
                label="Show the modelling equation as soon as a problem appears"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={<Switch checked={draft.practiceSettings.preferLanguageModel} onChange={(e) => setField('practiceSettings', { preferLanguageModel: e.target.checked })} />}
                label="Use the language model to write problems when one is available"
              />
            </Grid>
            <Grid item xs={12}>
              <Stack direction="row" spacing={1} flexWrap="wrap" rowGap={1} alignItems="center">
                <Typography variant="body2" color="text.secondary">
                  Backend:
                </Typography>
                {learning ? (
                  <>
                    <Chip
                      size="small"
                      color={learning.knowledge.available ? 'success' : 'default'}
                      label={
                        learning.knowledge.available
                          ? `Course material: ${learning.knowledge.documents} docs, ${learning.knowledge.chunks} passages (${learning.knowledge.backend === 'chroma' ? 'Chroma' : 'local'}, ${learning.knowledge.embedding === 'minilm' ? 'MiniLM' : 'hashing'})`
                          : `Course material unavailable${learning.knowledge.error ? `: ${learning.knowledge.error}` : ''}`
                      }
                    />
                    <Chip size="small" color={learning.practice.llm_available ? 'success' : 'default'} label={learning.practice.llm_available ? `Problem writer: ${describeLLMName(learning.practice.llm)}` : 'Problem writer: verified templates'} />
                  </>
                ) : (
                  <Chip size="small" label="Backend unreachable" />
                )}
                <Button size="small" onClick={() => navigate('/practice')} sx={{ textTransform: 'none' }}>
                  Manage course material
                </Button>
              </Stack>
              {learning && !learning.practice.llm_available && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                  To have word problems written by a language model, load the local reasoning model or connect an API provider such as OpenRouter in the “Language model” section below. Every generated problem is still checked by the
                  symbolic engine before you see it.
                </Typography>
              )}
            </Grid>
          </Grid>
        </CardContent>
      </Section>

      {/* ---- Language model source ---- */}
      <LanguageModelSection onToast={setToast} />

      {/* ---- Audio ---- */}
      <Section>
        <CardHeader avatar={<VolumeUp />} title="Audio" subheader="Voice input and spoken answers (require the speech models below)" />
        <CardContent>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Microphone</InputLabel>
                <Select value={draft.audioSettings.inputDevice} label="Microphone" onChange={(e) => setField('audioSettings', { inputDevice: e.target.value })}>
                  <MenuItem value="default">System default</MenuItem>
                  {devices.inputs.map((d) => (
                    <MenuItem key={d.deviceId} value={d.deviceId}>{d.label || `Microphone ${d.deviceId.slice(0, 6)}`}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Speaker</InputLabel>
                <Select value={draft.audioSettings.outputDevice} label="Speaker" onChange={(e) => setField('audioSettings', { outputDevice: e.target.value })}>
                  <MenuItem value="default">System default</MenuItem>
                  {devices.outputs.map((d) => (
                    <MenuItem key={d.deviceId} value={d.deviceId}>{d.label || `Speaker ${d.deviceId.slice(0, 6)}`}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Playback volume: {Math.round(draft.audioSettings.volume * 100)}%</Typography>
              <Slider value={Math.round(draft.audioSettings.volume * 100)} min={0} max={100} onChange={(_, v) => setField('audioSettings', { volume: (v as number) / 100 })} valueLabelDisplay="auto" />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Speech language</InputLabel>
                <Select value={draft.audioSettings.sttLanguage} label="Speech language" onChange={(e) => setField('audioSettings', { sttLanguage: e.target.value, ttsLanguage: e.target.value })}>
                  {['en', 'zh', 'ms', 'ta', 'id', 'th', 'vi'].map((code) => (
                    <MenuItem key={code} value={code}>{code}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControlLabel control={<Switch checked={draft.audioSettings.enableTextToSpeech} onChange={(e) => setField('audioSettings', { enableTextToSpeech: e.target.checked })} />} label="Read solutions aloud" />
            </Grid>
          </Grid>
        </CardContent>
      </Section>

      {/* ---- Models ---- */}
      <Section>
        <CardHeader
          avatar={<Memory />}
          title="AI models"
          subheader="The symbolic engine is always on. Optional local models add handwriting recognition, word problems and speech."
          action={
            <Button size="small" onClick={() => void refresh()} startIcon={<Refresh />}>
              Refresh
            </Button>
          }
        />
        <CardContent>
          {backendError && <Alert severity="error" sx={{ mb: 2 }}>Backend unreachable: {backendError}</Alert>}
          {mlStackMissing && (
            <Alert severity="info" sx={{ mb: 2 }}>
              PyTorch/transformers are not installed in the backend environment, so models cannot be loaded. Install{' '}
              <code>src/backend/requirements-ml.txt</code> and restart the backend to enable them.
            </Alert>
          )}

          {resources && (
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid item xs={6} md={3}>
                <Stat icon={<Speed color="primary" />} label="CPU" value={resources.cpu.percent_used == null ? '—' : `${resources.cpu.percent_used}%`} />
              </Grid>
              <Grid item xs={6} md={3}>
                <Stat icon={<Memory color="primary" />} label="RAM free" value={gb(resources.memory.available_gb)} />
              </Grid>
              <Grid item xs={6} md={3}>
                <Stat icon={<Download color="primary" />} label="Disk free (models)" value={gb(resources.disk.free_gb)} />
              </Grid>
              <Grid item xs={6} md={3}>
                <Stat icon={<Monitor color="primary" />} label="GPU" value={resources.gpu.length ? resources.gpu.map((g) => `${g.name} (${gb(g.memory_total_gb)})`).join(', ') : 'None detected'} />
              </Grid>
            </Grid>
          )}

          {autoLoad && (
            <FormControlLabel
              sx={{ mb: 2 }}
              control={<Switch checked={autoLoad.enabled} onChange={(e) => void toggleAutoLoad(e.target.checked)} />}
              label="Reload previously loaded models when the backend starts"
            />
          )}

          {models === null && !backendError && <LinearProgress />}

          <Grid container spacing={2}>
            {models?.map((model) => {
              const meta = STATUS_META[model.status] ?? STATUS_META.unavailable;
              const working = busy[model.name] || model.status === 'loading';
              const canLoad = model.status === 'available' || model.status === 'error';
              return (
                <Grid item xs={12} md={6} key={model.name}>
                  <Card variant="outlined" sx={{ height: '100%' }}>
                    <CardHeader
                      avatar={MODEL_ICON[model.type] ?? <Memory />}
                      title={model.name}
                      subheader={model.description}
                      action={<Chip size="small" color={meta.color} label={meta.label} sx={{ mt: 1 }} />}
                    />
                    <CardContent sx={{ pt: 0 }}>
                      <Typography variant="caption" color="text.secondary" display="block">
                        {model.model_id} · {gb(model.requirements.file_size_gb)} on disk · needs {gb(model.requirements.memory_required_gb)} RAM
                        {model.requirements.gpu_required ? ' · GPU required' : ''}
                      </Typography>
                      {model.status === 'loaded' && (
                        <Typography variant="caption" color="text.secondary" display="block">
                          On {model.device} · {mb(model.memory_usage)}{model.loaded_at ? ` · since ${new Date(model.loaded_at).toLocaleTimeString()}` : ''}
                        </Typography>
                      )}
                      {model.status === 'loading' && (
                        <Box sx={{ my: 1 }}>
                          <LinearProgress variant={model.loading_progress > 0 ? 'determinate' : 'indeterminate'} value={model.loading_progress} />
                        </Box>
                      )}
                      {model.status === 'not_downloaded' && (
                        <Alert severity="info" icon={false} sx={{ my: 1, py: 0 }}>
                          Not on disk. Run <code>python scripts/setup_models.py --model {model.name}</code>, expected at <code>{model.path}</code>.
                        </Alert>
                      )}
                      {model.error && (
                        <Alert severity="error" icon={<ErrorOutline fontSize="inherit" />} sx={{ my: 1, py: 0 }}>
                          {model.error}
                        </Alert>
                      )}
                      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                        {model.status === 'loaded' ? (
                          <Button size="small" variant="outlined" color="error" disabled={working} onClick={() => void unloadModel(model)} startIcon={working ? <CircularProgress size={14} /> : <Delete />}>
                            Unload
                          </Button>
                        ) : (
                          <Tooltip title={canLoad ? '' : meta.label}>
                            <span>
                              <Button size="small" variant="contained" disabled={!canLoad || working} onClick={() => void loadModel(model)} startIcon={working ? <CircularProgress size={14} /> : <CheckCircle />}>
                                Load
                              </Button>
                            </span>
                          </Tooltip>
                        )}
                      </Stack>
                    </CardContent>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        </CardContent>
      </Section>

      {/* ---- Generation ---- */}
      <Section>
        <CardHeader avatar={<Memory />} title="Generation options" subheader="Apply to whichever language model is active" />
        <CardContent>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Temperature: {draft.modelSettings.temperature.toFixed(2)}</Typography>
              <Slider value={draft.modelSettings.temperature} min={0} max={1} step={0.05} onChange={(_, v) => setField('modelSettings', { temperature: v as number })} valueLabelDisplay="auto" />
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Max tokens: {draft.modelSettings.maxTokens}</Typography>
              <Slider value={draft.modelSettings.maxTokens} min={256} max={4096} step={256} onChange={(_, v) => setField('modelSettings', { maxTokens: v as number })} valueLabelDisplay="auto" />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControlLabel control={<Switch checked={draft.modelSettings.enableThinking} onChange={(e) => setField('modelSettings', { enableThinking: e.target.checked })} />} label="Show the model's thinking process" />
            </Grid>
          </Grid>
        </CardContent>
      </Section>

      <Snackbar open={Boolean(toast)} autoHideDuration={4000} onClose={() => setToast(null)} message={toast} />
    </Container>
  );
};

const Stat: React.FC<{ icon: React.ReactNode; label: string; value: string }> = ({ icon, label, value }) => (
  <Stack direction="row" spacing={1} alignItems="center">
    {icon}
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2" noWrap title={value}>
        {value}
      </Typography>
    </Box>
  </Stack>
);
