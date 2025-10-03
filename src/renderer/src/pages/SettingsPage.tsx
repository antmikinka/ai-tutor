import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  Switch,
  FormControlLabel,
  Button,
  Grid,
  Card,
  CardContent,
  CardHeader,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Alert,
  CircularProgress,
  LinearProgress,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  } from '@mui/material';
import {
  Save,
  Refresh,
  VolumeUp,
  Mic,
  Monitor,
  Memory,
  Download,
  Delete,
  CheckCircle,
  Error,
  Info,
  Timer,
  Storage,
  Speed,
} from '@mui/icons-material';
import { styled, useTheme } from '@mui/material/styles';
import { useSettingsContext } from '../contexts/SettingsContext';
import { useAppSettings } from '../hooks/useAppSettings';

// Types for model management
interface ModelStatus {
  model_name: string;
  status: 'not_loaded' | 'loading' | 'loaded' | 'error' | 'unloading';
  device?: string;
  memory_usage: number;
  loading_progress: number;
  loaded_at?: string;
  error?: string;
  timestamp: string;
}

interface ModelType {
  name: string;
  description: string;
  estimated_size_mb: number;
  loading_time_estimate: number;
  icon: React.ReactNode;
}

interface SystemResources {
  cpu: { percent_used: number; count: number; count_logical: number };
  memory: { total_gb: number; available_gb: number; used_gb: number; percent_used: number };
  disk: { total_gb: number; free_gb: number; used_gb: number; percent_used: number };
  gpu: Array<{
    device_id: number;
    name: string;
    memory_total_gb: number;
    memory_allocated_gb: number;
    memory_cached_gb: number;
  }>;
}

const SettingsContainer = styled(Box)(({ theme }) => ({
  padding: theme.spacing(3),
  maxWidth: 1200,
  margin: '0 auto',
}));

const ModelCard = styled(Card)(({ theme }) => ({
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
  transition: 'transform 0.2s',
  '&:hover': {
    transform: 'translateY(-2px)',
  },
}));

const StatusChip = styled(Chip)(({ theme, status }: { theme: any; status: string }) => {
  const colors: { [key: string]: string } = {
    loaded: theme.palette.success.main,
    loading: theme.palette.warning.main,
    not_loaded: theme.palette.grey[500],
    error: theme.palette.error.main,
    unloading: theme.palette.info.main,
  };

  return {
    backgroundColor: colors[status] || colors.not_loaded,
    color: theme.palette.getContrastText(colors[status] || colors.not_loaded),
    fontWeight: 'bold',
  };
});

const SettingsCard = styled(Card)(({ theme }) => ({
  marginBottom: theme.spacing(3),
}));

export const SettingsPage: React.FC = () => {
  const theme = useTheme();
  const { settings, updateSettings, isLoading, error } = useSettingsContext();
  const { resetSettings } = useAppSettings();
  const [localSettings, setLocalSettings] = useState(settings);
  const [hasChanges, setHasChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Model management state
  const [modelStatuses, setModelStatuses] = useState<ModelStatus[]>([]);
  const [systemResources, setSystemResources] = useState<SystemResources | null>(null);
  const [loadingActions, setLoadingActions] = useState<{[key: string]: boolean}>({});
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [showResourceDialog, setShowResourceDialog] = useState(false);
  const [autoLoadEnabled, setAutoLoadEnabled] = useState(true);

  // Model types configuration
  const modelTypes: {[key: string]: ModelType} = {
    ai: {
      name: 'Qwen3-Omni-30B-A3B-Thinking',
      description: 'AI Math Tutor Model',
      estimated_size_mb: 15000,
      loading_time_estimate: 120,
      icon: <Memory />
    },
    tts: {
      name: 'VibeVoice',
      description: 'Text-to-Speech Model',
      estimated_size_mb: 2000,
      loading_time_estimate: 30,
      icon: <VolumeUp />
    },
    stt: {
      name: 'MERaLiON',
      description: 'Speech-to-Text Model',
      estimated_size_mb: 1500,
      loading_time_estimate: 25,
      icon: <Mic />
    },
    whisper: {
      name: 'Whisper',
      description: 'OpenAI Whisper Model',
      estimated_size_mb: 750,
      loading_time_estimate: 15,
      icon: <Mic />
    },
    xtts: {
      name: 'XTTS-v2',
      description: 'Coqui XTTS Model',
      estimated_size_mb: 500,
      loading_time_estimate: 10,
      icon: <VolumeUp />
    }
  };

  useEffect(() => {
    setLocalSettings(settings);
    setHasChanges(false);
  }, [settings]);

  // Model management effects
  useEffect(() => {
    fetchModelStatuses();
    fetchSystemResources();

    // Set up polling for model status updates
    const interval = setInterval(() => {
      fetchModelStatuses();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // API functions for model management
  const fetchModelStatuses = async () => {
    try {
      const response = await fetch('/api/models');
      if (response.ok) {
        const data = await response.json();
        setModelStatuses(data.models);
        setSystemResources(data.system_memory);
      }
    } catch (error) {
      console.error('Error fetching model statuses:', error);
    }
  };

  const fetchSystemResources = async () => {
    try {
      const response = await fetch('/api/models/system/resources');
      if (response.ok) {
        const data = await response.json();
        setSystemResources(data);
      }
    } catch (error) {
      console.error('Error fetching system resources:', error);
    }
  };

  const loadModel = async (modelType: string) => {
    try {
      setLoadingActions(prev => ({ ...prev, [modelType]: true }));

      const response = await fetch(`/api/models/load/${modelType}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model_type: modelType,
          options: { auto_load: autoLoadEnabled }
        }),
      });

      if (response.ok) {
        // Start polling for updates
        const pollInterval = setInterval(async () => {
          await fetchModelStatuses();

          // Check if model is loaded or error occurred
          const currentStatus = modelStatuses.find(
            status => status.model_name === modelTypes[modelType].name
          );

          if (currentStatus && (currentStatus.status === 'loaded' || currentStatus.status === 'error')) {
            clearInterval(pollInterval);
            setLoadingActions(prev => ({ ...prev, [modelType]: false }));
          }
        }, 1000);
      } else {
        console.error('Error loading model:', response.statusText);
        setLoadingActions(prev => ({ ...prev, [modelType]: false }));
      }
    } catch (error) {
      console.error('Error loading model:', error);
      setLoadingActions(prev => ({ ...prev, [modelType]: false }));
    }
  };

  const unloadModel = async (modelType: string) => {
    try {
      setLoadingActions(prev => ({ ...prev, [modelType]: true }));

      const response = await fetch(`/api/models/unload/${modelType}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        await fetchModelStatuses();
      } else {
        console.error('Error unloading model:', response.statusText);
      }
    } catch (error) {
      console.error('Error unloading model:', error);
    } finally {
      setLoadingActions(prev => ({ ...prev, [modelType]: false }));
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'loaded':
        return <CheckCircle color="success" />;
      case 'loading':
        return <CircularProgress size={20} />;
      case 'error':
        return <Error color="error" />;
      case 'unloading':
        return <Timer color="info" />;
      default:
        return <Info color="disabled" />;
    }
  };

  const formatMemory = (mb: number) => {
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(1)} GB`;
    }
    return `${mb.toFixed(0)} MB`;
  };

  const formatTime = (seconds: number) => {
    if (seconds >= 60) {
      return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    }
    return `${seconds}s`;
  };

  const handleSettingChange = (section: keyof typeof settings, field: string, value: any) => {
    setLocalSettings(prev => {
      const prevSettings = prev as any;
      return {
        ...prev,
        [section]: {
          ...prevSettings[section],
          [field]: value,
        },
      };
    });
    setHasChanges(true);
  };

  const handleSaveSettings = async () => {
    setIsSaving(true);
    try {
      await updateSettings(localSettings);
      setHasChanges(false);
    } catch (error) {
      console.error('Failed to save settings:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetSettings = async () => {
    if (window.confirm('Are you sure you want to reset all settings to default?')) {
      setIsSaving(true);
      try {
        await resetSettings();
        setHasChanges(false);
      } catch (error) {
        console.error('Failed to reset settings:', error);
      } finally {
        setIsSaving(false);
      }
    }
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <SettingsContainer>
        <Alert severity="error">{error}</Alert>
      </SettingsContainer>
    );
  }

  return (
    <SettingsContainer>
      <Typography variant="h4" component="h1" gutterBottom>
        Settings
      </Typography>

      {hasChanges && (
        <Alert severity="info" sx={{ mb: 2 }}>
          You have unsaved changes. Don't forget to save your settings.
        </Alert>
      )}

      {/* Audio Settings */}
      <SettingsCard>
        <CardHeader
          avatar={<VolumeUp />}
          title="Audio Settings"
          subheader="Configure speech recognition and text-to-speech options"
        />
        <CardContent>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Input Device</InputLabel>
                <Select
                  value={localSettings.audioSettings.inputDevice}
                  label="Input Device"
                  onChange={(e) => handleSettingChange('audioSettings', 'inputDevice', e.target.value)}
                >
                  <MenuItem value="default">Default Microphone</MenuItem>
                  <MenuItem value="microphone-1">Microphone 1</MenuItem>
                  <MenuItem value="microphone-2">Microphone 2</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Output Device</InputLabel>
                <Select
                  value={localSettings.audioSettings.outputDevice}
                  label="Output Device"
                  onChange={(e) => handleSettingChange('audioSettings', 'outputDevice', e.target.value)}
                >
                  <MenuItem value="default">Default Speaker</MenuItem>
                  <MenuItem value="speaker-1">Speaker 1</MenuItem>
                  <MenuItem value="headphones">Headphones</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12}>
              <Typography gutterBottom>Volume</Typography>
              <Slider
                value={localSettings.audioSettings.volume * 100}
                onChange={(_, value) => handleSettingChange('audioSettings', 'volume', value as number / 100)}
                valueLabelDisplay="auto"
                min={0}
                max={100}
              />
              <Typography variant="caption" color="text.secondary">
                Current: {Math.round(localSettings.audioSettings.volume * 100)}%
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={localSettings.audioSettings.enableSpeechRecognition}
                    onChange={(e) => handleSettingChange('audioSettings', 'enableSpeechRecognition', e.target.checked)}
                  />
                }
                label="Enable Speech Recognition"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={localSettings.audioSettings.enableTextToSpeech}
                    onChange={(e) => handleSettingChange('audioSettings', 'enableTextToSpeech', e.target.checked)}
                  />
                }
                label="Enable Text-to-Speech"
              />
            </Grid>
          </Grid>
        </CardContent>
      </SettingsCard>

      {/* AI Model Settings */}
      <SettingsCard>
        <CardHeader
          avatar={<Memory />}
          title="AI Model Settings"
          subheader="Configure AI model parameters and performance options"
        />
        <CardContent>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Model Path"
                value={localSettings.modelSettings.modelPath}
                onChange={(e) => handleSettingChange('modelSettings', 'modelPath', e.target.value)}
                helperText="Path to the AI model files"
              />
            </Grid>

            <Grid item xs={12}>
              <Typography gutterBottom>Creativity (Temperature)</Typography>
              <Slider
                value={localSettings.modelSettings.temperature * 100}
                onChange={(_, value) => handleSettingChange('modelSettings', 'temperature', value as number / 100)}
                valueLabelDisplay="auto"
                min={0}
                max={100}
              />
              <Typography variant="caption" color="text.secondary">
                Current: {Math.round(localSettings.modelSettings.temperature * 100)}%
                (Higher values make the AI more creative, lower values make it more focused)
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <Typography gutterBottom>Response Length (Max Tokens)</Typography>
              <Slider
                value={localSettings.modelSettings.maxTokens}
                onChange={(_, value) => handleSettingChange('modelSettings', 'maxTokens', value as number)}
                valueLabelDisplay="auto"
                min={256}
                max={4096}
                step={256}
              />
              <Typography variant="caption" color="text.secondary">
                Current: {localSettings.modelSettings.maxTokens} tokens
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={localSettings.modelSettings.useGPU}
                    onChange={(e) => handleSettingChange('modelSettings', 'useGPU', e.target.checked)}
                  />
                }
                label="Use GPU Acceleration"
              />
            </Grid>
          </Grid>
        </CardContent>
      </SettingsCard>

      {/* Model Management */}
      <SettingsCard>
        <CardHeader
          avatar={<Memory />}
          title="Model Management"
          subheader="Manually load and unload AI models"
          action={
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                size="small"
                onClick={() => setShowResourceDialog(true)}
                startIcon={<Speed />}
              >
                System Resources
              </Button>
              <Button
                size="small"
                onClick={fetchModelStatuses}
                startIcon={<Refresh />}
              >
                Refresh
              </Button>
            </Box>
          }
        />
        <CardContent>
          {/* System Resource Overview */}
          {systemResources && (
            <Box sx={{ mb: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Grid container spacing={2}>
                <Grid item xs={12} md={3}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Speed color="primary" />
                    <Box>
                      <Typography variant="body2" color="text.secondary">CPU</Typography>
                      <Typography variant="h6">{systemResources.cpu.percent_used}%</Typography>
                    </Box>
                  </Box>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Storage color="primary" />
                    <Box>
                      <Typography variant="body2" color="text.secondary">Memory</Typography>
                      <Typography variant="h6">{systemResources.memory.percent_used}%</Typography>
                      <Typography variant="caption">
                        {systemResources.memory.available_gb.toFixed(1)} GB free
                      </Typography>
                    </Box>
                  </Box>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Timer color="primary" />
                    <Box>
                      <Typography variant="body2" color="text.secondary">Models</Typography>
                      <Typography variant="h6">
                        {modelStatuses.filter(m => m.status === 'loaded').length} loaded
                      </Typography>
                    </Box>
                  </Box>
                </Grid>
                <Grid item xs={12} md={3}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Storage color="primary" />
                    <Box>
                      <Typography variant="body2" color="text.secondary">Total Model Memory</Typography>
                      <Typography variant="h6">
                        {formatMemory(modelStatuses.reduce((sum, m) => sum + m.memory_usage, 0))}
                      </Typography>
                    </Box>
                  </Box>
                </Grid>
              </Grid>
            </Box>
          )}

          {/* Auto-load Toggle */}
          <Box sx={{ mb: 3 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={autoLoadEnabled}
                  onChange={(e) => setAutoLoadEnabled(e.target.checked)}
                />
              }
              label="Auto-load models on startup"
            />
            <Typography variant="caption" color="text.secondary" display="block">
              When enabled, models will be loaded automatically when the application starts
            </Typography>
          </Box>

          {/* Model Cards */}
          <Grid container spacing={3}>
            {Object.entries(modelTypes).map(([modelType, modelInfo]) => {
              const modelStatus = modelStatuses.find(m => m.model_name === modelInfo.name);
              const isLoading = loadingActions[modelType] || modelStatus?.status === 'loading';

              return (
                <Grid item xs={12} md={6} lg={4} key={modelType}>
                  <ModelCard>
                    <CardHeader
                      avatar={modelInfo.icon}
                      title={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {modelInfo.name}
                          {modelStatus && getStatusIcon(modelStatus.status)}
                        </Box>
                      }
                      subheader={modelInfo.description}
                      action={
                        <StatusChip
                          theme={theme}
                          status={modelStatus?.status || 'not_loaded'}
                          label={modelStatus?.status?.replace('_', ' ') || 'Not Loaded'}
                          size="small"
                        />
                      }
                    />
                    <CardContent>
                      {/* Model Info */}
                      <Box sx={{ mb: 2 }}>
                        <Grid container spacing={1}>
                          <Grid item xs={6}>
                            <Typography variant="caption" color="text.secondary">
                              Size
                            </Typography>
                            <Typography variant="body2">
                              {formatMemory(modelInfo.estimated_size_mb)}
                            </Typography>
                          </Grid>
                          <Grid item xs={6}>
                            <Typography variant="caption" color="text.secondary">
                              Load Time
                            </Typography>
                            <Typography variant="body2">
                              {formatTime(modelInfo.loading_time_estimate)}
                            </Typography>
                          </Grid>
                        </Grid>
                      </Box>

                      {/* Progress Bar */}
                      {modelStatus && (modelStatus.status === 'loading' || modelStatus.status === 'unloading') && (
                        <Box sx={{ mb: 2 }}>
                          <LinearProgress
                            variant="determinate"
                            value={modelStatus.loading_progress}
                            sx={{ height: 6, borderRadius: 3 }}
                          />
                          <Typography variant="caption" color="text.secondary">
                            {modelStatus.loading_progress.toFixed(0)}% complete
                          </Typography>
                        </Box>
                      )}

                      {/* Status Details */}
                      {modelStatus && (
                        <Box sx={{ mb: 2 }}>
                          {modelStatus.status === 'loaded' && (
                            <Box>
                              <Typography variant="caption" color="text.secondary">
                                Device: {modelStatus.device}
                              </Typography>
                              <Typography variant="caption" color="text.secondary" display="block">
                                Memory: {formatMemory(modelStatus.memory_usage)}
                              </Typography>
                              {modelStatus.loaded_at && (
                                <Typography variant="caption" color="text.secondary" display="block">
                                  Loaded: {new Date(modelStatus.loaded_at).toLocaleTimeString()}
                                </Typography>
                              )}
                            </Box>
                          )}
                          {modelStatus.status === 'error' && (
                            <Typography variant="caption" color="error" display="block">
                              {modelStatus.error}
                            </Typography>
                          )}
                        </Box>
                      )}

                      {/* Action Buttons */}
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        {modelStatus?.status === 'loaded' ? (
                          <Button
                            size="small"
                            variant="outlined"
                            color="error"
                            onClick={() => unloadModel(modelType)}
                            disabled={isLoading}
                            startIcon={isLoading ? <CircularProgress size={16} /> : <Delete />}
                          >
                            Unload
                          </Button>
                        ) : (
                          <Button
                            size="small"
                            variant="contained"
                            onClick={() => loadModel(modelType)}
                            disabled={isLoading}
                            startIcon={isLoading ? <CircularProgress size={16} /> : <Download />}
                          >
                            Load
                          </Button>
                        )}
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => setSelectedModel(modelType)}
                        >
                          Details
                        </Button>
                      </Box>
                    </CardContent>
                  </ModelCard>
                </Grid>
              );
            })}
          </Grid>
        </CardContent>
      </SettingsCard>

      {/* Display Settings */}
      <SettingsCard>
        <CardHeader
          avatar={<Monitor />}
          title="Display Settings"
          subheader="Customize the appearance and behavior of the interface"
        />
        <CardContent>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Theme</InputLabel>
                <Select
                  value={localSettings.displaySettings.theme}
                  label="Theme"
                  onChange={(e) => handleSettingChange('displaySettings', 'theme', e.target.value)}
                >
                  <MenuItem value="light">Light</MenuItem>
                  <MenuItem value="dark">Dark</MenuItem>
                  <MenuItem value="auto">Auto (System)</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Font Size</Typography>
              <Slider
                value={localSettings.displaySettings.fontSize}
                onChange={(_, value) => handleSettingChange('displaySettings', 'fontSize', value as number)}
                valueLabelDisplay="auto"
                min={10}
                max={20}
              />
              <Typography variant="caption" color="text.secondary">
                Current: {localSettings.displaySettings.fontSize}px
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={localSettings.displaySettings.showStepByStep}
                    onChange={(e) => handleSettingChange('displaySettings', 'showStepByStep', e.target.checked)}
                  />
                }
                label="Show Step-by-Step Solutions"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={localSettings.displaySettings.showConfidence}
                    onChange={(e) => handleSettingChange('displaySettings', 'showConfidence', e.target.checked)}
                  />
                }
                label="Show Confidence Scores"
              />
            </Grid>
          </Grid>
        </CardContent>
      </SettingsCard>

      {/* Action Buttons */}
      <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 3 }}>
        <Button
          variant="outlined"
          color="error"
          onClick={handleResetSettings}
          disabled={isSaving}
        >
          Reset to Default
        </Button>
        <Button
          variant="contained"
          onClick={handleSaveSettings}
          disabled={isSaving || !hasChanges}
          startIcon={isSaving ? <CircularProgress size={20} /> : <Save />}
        >
          {isSaving ? 'Saving...' : 'Save Settings'}
        </Button>
      </Box>

      {/* System Resources Dialog */}
      <Dialog
        open={showResourceDialog}
        onClose={() => setShowResourceDialog(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>System Resources</DialogTitle>
        <DialogContent>
          {systemResources ? (
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>CPU Information</Typography>
                <List dense>
                  <ListItem>
                    <ListItemText
                      primary="Usage"
                      secondary={`${systemResources.cpu.percent_used}%`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Cores"
                      secondary={`${systemResources.cpu.count} physical, ${systemResources.cpu.count_logical} logical`}
                    />
                  </ListItem>
                </List>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>Memory Information</Typography>
                <List dense>
                  <ListItem>
                    <ListItemText
                      primary="Total"
                      secondary={`${systemResources.memory.total_gb.toFixed(1)} GB`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Available"
                      secondary={`${systemResources.memory.available_gb.toFixed(1)} GB`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Used"
                      secondary={`${systemResources.memory.used_gb.toFixed(1)} GB (${systemResources.memory.percent_used}%)`}
                    />
                  </ListItem>
                </List>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="h6" gutterBottom>Disk Information</Typography>
                <List dense>
                  <ListItem>
                    <ListItemText
                      primary="Total"
                      secondary={`${systemResources.disk.total_gb.toFixed(1)} GB`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Free"
                      secondary={`${systemResources.disk.free_gb.toFixed(1)} GB`}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Used"
                      secondary={`${systemResources.disk.used_gb.toFixed(1)} GB (${systemResources.disk.percent_used}%)`}
                    />
                  </ListItem>
                </List>
              </Grid>

              {systemResources.gpu && systemResources.gpu.length > 0 && (
                <Grid item xs={12} md={6}>
                  <Typography variant="h6" gutterBottom>GPU Information</Typography>
                  {systemResources.gpu.map((gpu, index) => (
                    <List dense key={index}>
                      <ListItem>
                        <ListItemText
                          primary={`GPU ${gpu.device_id}`}
                          secondary={gpu.name}
                        />
                      </ListItem>
                      <ListItem>
                        <ListItemText
                          primary="Memory"
                          secondary={`${gpu.memory_allocated_gb.toFixed(1)} GB / ${gpu.memory_total_gb.toFixed(1)} GB`}
                        />
                      </ListItem>
                    </List>
                  ))}
                </Grid>
              )}
            </Grid>
          ) : (
            <Typography>Loading system resources...</Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowResourceDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </SettingsContainer>
  );
};