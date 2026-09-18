import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Divider,
  FormControlLabel,
  IconButton,
  Popover,
  Slider,
  Stack,
  Switch,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import { Bolt, BrightnessAuto, Cloud, Computer, DarkMode, Grid4x4, GridOff, Highlight, LightMode, Tune } from '@mui/icons-material';
import { useSettingsContext } from '../contexts/SettingsContext';
import { useLLMConfig } from '../hooks/useLLMConfig';
import { describeLLMName } from '../lib/llm';
import type { LLMMode, WhiteboardGrid } from '../types/MathTypes';

const Row: React.FC<{ label: string; checked: boolean; onChange: (checked: boolean) => void }> = ({ label, checked, onChange }) => (
  <FormControlLabel
    sx={{ m: 0, justifyContent: 'space-between', width: '100%' }}
    labelPlacement="start"
    control={<Switch size="small" checked={checked} onChange={(e) => onChange(e.target.checked)} />}
    label={<Typography variant="body2">{label}</Typography>}
  />
);

/**
 * One-click access to the settings people flip mid-session (theme, text size,
 * what the tutor shows, whiteboard grid, speech). Everything else lives on the
 * full Settings page.
 */
export const QuickSettings: React.FC<{ color?: 'inherit' | 'default' }> = ({ color = 'inherit' }) => {
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const { settings, updateDisplaySettings, updateWhiteboardSettings, updateAudioSettings, updatePracticeSettings } = useSettingsContext();
  const { displaySettings, whiteboardSettings, audioSettings, practiceSettings } = settings;
  const open = Boolean(anchor);
  const llm = useLLMConfig(open);
  const [switching, setSwitching] = useState(false);

  const setMode = async (mode: LLMMode) => {
    if (!llm.config || llm.config.mode === mode) return;
    setSwitching(true);
    try {
      await llm.update({ mode });
    } catch {
      // error surfaces through llm.error
    } finally {
      setSwitching(false);
    }
  };

  const goToSettings = () => {
    setAnchor(null);
    navigate('/settings');
  };

  return (
    <>
      <Tooltip title="Quick settings">
        <IconButton color={color} onClick={(e) => setAnchor(e.currentTarget)} aria-label="Quick settings" aria-haspopup="true">
          <Tune />
        </IconButton>
      </Tooltip>
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { sx: { width: 300, p: 2 } } }}
      >
        <Stack spacing={1.5}>
          <Box>
            <Typography variant="overline" color="text.secondary">
              AI source
            </Typography>
            <ToggleButtonGroup
              fullWidth
              size="small"
              exclusive
              value={llm.config?.mode ?? 'auto'}
              disabled={!llm.config || switching}
              onChange={(_, v: LLMMode | null) => v && void setMode(v)}
              sx={{ mt: 0.5 }}
            >
              <ToggleButton value="auto" aria-label="Automatic AI source">
                <Bolt fontSize="small" sx={{ mr: 0.5 }} /> Auto
              </ToggleButton>
              <ToggleButton value="local" aria-label="Local model only">
                <Computer fontSize="small" sx={{ mr: 0.5 }} /> Local
              </ToggleButton>
              <ToggleButton value="remote" aria-label="API provider (OpenRouter)">
                <Cloud fontSize="small" sx={{ mr: 0.5 }} /> API
              </ToggleButton>
            </ToggleButtonGroup>
            <Typography variant="caption" color={llm.config?.active.backend ? 'text.secondary' : 'warning.main'} sx={{ display: 'block', mt: 0.5, px: 0.5 }} noWrap title={llm.config?.active.name ?? undefined}>
              {llm.error
                ? 'Backend unreachable'
                : !llm.config
                  ? 'Loading…'
                  : llm.config.active.name
                    ? describeLLMName(llm.config.active.name)
                    : llm.config.mode === 'local'
                      ? 'No local model loaded'
                      : 'No API provider set up'}
              {llm.config && !llm.config.active.backend && (
                <>
                  {' · '}
                  <Typography component="button" type="button" variant="caption" onClick={goToSettings} sx={{ p: 0, border: 0, background: 'none', color: 'primary.main', cursor: 'pointer', font: 'inherit' }}>
                    set up
                  </Typography>
                </>
              )}
            </Typography>
          </Box>

          <Divider />

          <Box>
            <Typography variant="overline" color="text.secondary">
              Appearance
            </Typography>
            <ToggleButtonGroup
              fullWidth
              size="small"
              exclusive
              value={displaySettings.theme}
              onChange={(_, v: 'light' | 'dark' | 'auto' | null) => v && updateDisplaySettings({ theme: v })}
              sx={{ mt: 0.5 }}
            >
              <ToggleButton value="light" aria-label="Light theme">
                <LightMode fontSize="small" sx={{ mr: 0.5 }} /> Light
              </ToggleButton>
              <ToggleButton value="dark" aria-label="Dark theme">
                <DarkMode fontSize="small" sx={{ mr: 0.5 }} /> Dark
              </ToggleButton>
              <ToggleButton value="auto" aria-label="Follow system theme">
                <BrightnessAuto fontSize="small" sx={{ mr: 0.5 }} /> Auto
              </ToggleButton>
            </ToggleButtonGroup>
            <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mt: 1, px: 0.5 }}>
              <Typography variant="body2" sx={{ minWidth: 64 }}>
                Text {displaySettings.fontSize}px
              </Typography>
              <Slider
                size="small"
                min={12}
                max={20}
                step={1}
                value={displaySettings.fontSize}
                onChange={(_, v) => updateDisplaySettings({ fontSize: v as number })}
                aria-label="Font size"
              />
            </Stack>
          </Box>

          <Divider />

          <Box>
            <Typography variant="overline" color="text.secondary">
              Tutor
            </Typography>
            <Row label="Show steps" checked={displaySettings.showStepByStep} onChange={(v) => updateDisplaySettings({ showStepByStep: v })} />
            <Row label="Show confidence" checked={displaySettings.showConfidence} onChange={(v) => updateDisplaySettings({ showConfidence: v })} />
            <Row label="Show engine / model" checked={displaySettings.showModelInfo} onChange={(v) => updateDisplaySettings({ showModelInfo: v })} />
            <Row label="Read answers aloud" checked={audioSettings.enableTextToSpeech} onChange={(v) => updateAudioSettings({ enableTextToSpeech: v })} />
          </Box>

          <Divider />

          <Box>
            <Typography variant="overline" color="text.secondary">
              Whiteboard
            </Typography>
            <ToggleButtonGroup
              fullWidth
              size="small"
              exclusive
              value={whiteboardSettings.grid}
              onChange={(_, v: WhiteboardGrid | null) => v && updateWhiteboardSettings({ grid: v })}
              sx={{ mt: 0.5 }}
            >
              <ToggleButton value="none" aria-label="No grid">
                <GridOff fontSize="small" sx={{ mr: 0.5 }} /> Plain
              </ToggleButton>
              <ToggleButton value="dots" aria-label="Dot grid">
                <Highlight fontSize="small" sx={{ mr: 0.5 }} /> Dots
              </ToggleButton>
              <ToggleButton value="lines" aria-label="Square grid">
                <Grid4x4 fontSize="small" sx={{ mr: 0.5 }} /> Squares
              </ToggleButton>
            </ToggleButtonGroup>
            <Row label="Shortcut hints" checked={whiteboardSettings.showShortcutHints} onChange={(v) => updateWhiteboardSettings({ showShortcutHints: v })} />
          </Box>

          <Divider />

          <Box>
            <Typography variant="overline" color="text.secondary">
              Practice
            </Typography>
            <Row
              label="Show equation right away"
              checked={practiceSettings.showEquationImmediately}
              onChange={(v) => updatePracticeSettings({ showEquationImmediately: v })}
            />
          </Box>

          <Button size="small" variant="outlined" onClick={goToSettings}>
            All settings
          </Button>
        </Stack>
      </Popover>
    </>
  );
};
