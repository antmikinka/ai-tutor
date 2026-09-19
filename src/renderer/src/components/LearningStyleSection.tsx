import React from 'react';
import { Box, Button, Card, CardContent, CardHeader, Chip, Grid, Link, Slider, Stack, Typography } from '@mui/material';
import { Psychology } from '@mui/icons-material';
import type { LearningStyleSettings, UserSettings } from '../types/MathTypes';
import { VARK_MAX, VARK_MODES, isStyleSet, preferredModes, styleLabel } from '../lib/vark';

interface Props {
  value: LearningStyleSettings;
  onChange: (patch: Partial<LearningStyleSettings>) => void;
  /** Apply presentation defaults that suit the profile (steps, read-aloud, grid, ...). */
  onApplyDefaults: (patch: Partial<UserSettings>) => void;
}

const MODE_COLORS: Record<keyof LearningStyleSettings, string> = {
  visual: '#1e88e5',
  aural: '#e53935',
  readWrite: '#fb8c00',
  kinesthetic: '#43a047',
};

/**
 * VARK questionnaire scores. The tutor uses them to decide *how* to present
 * things (sketch ideas, hint style, read-aloud, structured steps); the maths
 * itself is unchanged.
 */
export const LearningStyleSection: React.FC<Props> = ({ value, onChange, onApplyDefaults }) => {
  const prefs = preferredModes(value);
  const label = styleLabel(value);

  const suggestedDefaults = (): Partial<UserSettings> => {
    const patch: Partial<UserSettings> = {};
    const p = new Set(prefs);
    patch.displaySettings = { showStepByStep: true } as UserSettings['displaySettings'];
    if (p.has('visual')) patch.whiteboardSettings = { grid: 'dots' } as UserSettings['whiteboardSettings'];
    if (p.has('aural')) patch.audioSettings = { enableTextToSpeech: true } as UserSettings['audioSettings'];
    if (p.has('readWrite') || p.has('visual')) patch.practiceSettings = { showEquationImmediately: false } as UserSettings['practiceSettings'];
    return patch;
  };

  const whatChanges: string[] = [];
  if (prefs.includes('visual')) whatChanges.push('a "Sketch it" idea with every practice problem and solution');
  if (prefs.includes('readWrite')) whatChanges.push('precise, fully worded hints that name each quantity');
  if (prefs.includes('kinesthetic')) whatChanges.push('a hands-on first hint (try a number, build a table) and the whiteboard hand-off up front');
  if (prefs.includes('aural')) whatChanges.push('a "Read aloud" button on problems and an explain-it-out-loud hint');

  return (
    <Card sx={{ mb: 3 }}>
      <CardHeader
        avatar={<Psychology />}
        title="Learning style (VARK)"
        subheader="Enter your VARK questionnaire scores. The tutor adapts how it presents problems, hints and solutions; the maths and the checking stay the same."
        action={<Chip color={isStyleSet(value) ? 'primary' : 'default'} label={label} sx={{ mt: 1 }} />}
      />
      <CardContent>
        <Grid container spacing={3}>
          {VARK_MODES.map((mode) => (
            <Grid item xs={12} sm={6} key={mode.id}>
              <Stack direction="row" justifyContent="space-between" alignItems="baseline">
                <Typography variant="subtitle2">
                  {mode.label}{' '}
                  <Typography component="span" variant="caption" color="text.secondary">
                    {mode.blurb}
                  </Typography>
                </Typography>
                <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums' }}>
                  {value[mode.id]}
                </Typography>
              </Stack>
              <Slider
                value={value[mode.id]}
                min={0}
                max={VARK_MAX}
                step={1}
                marks={[{ value: 0 }, { value: 8 }, { value: 16 }]}
                onChange={(_, v) => onChange({ [mode.id]: v as number })}
                valueLabelDisplay="auto"
                aria-label={`${mode.label} score`}
                sx={{ color: MODE_COLORS[mode.id] }}
              />
            </Grid>
          ))}
          <Grid item xs={12}>
            {isStyleSet(value) ? (
              <Box>
                <Typography variant="body2" sx={{ mb: 0.5 }}>
                  With this profile you get {whatChanges.length ? whatChanges.join('; ') : 'the standard presentation'}.
                </Typography>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" rowGap={1}>
                  <Button size="small" variant="outlined" onClick={() => onApplyDefaults(suggestedDefaults())}>
                    Apply suggested defaults
                  </Button>
                  <Button size="small" color="inherit" onClick={() => onChange({ visual: 0, aural: 0, readWrite: 0, kinesthetic: 0 })}>
                    Clear
                  </Button>
                  <Typography variant="caption" color="text.secondary">
                    Sets steps on{prefs.includes('aural') ? ', read-aloud on' : ''}{prefs.includes('visual') ? ', dot grid' : ''}. You can change any of them afterwards.
                  </Typography>
                </Stack>
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Not set: the tutor uses its standard presentation. Take the free questionnaire at{' '}
                <Link href="https://vark-learn.com/the-vark-questionnaire/" target="_blank" rel="noreferrer">
                  vark-learn.com
                </Link>{' '}
                and enter the four scores above.
              </Typography>
            )}
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};
