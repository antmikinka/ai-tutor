import React from 'react';
import { Alert, Box, Button, Chip, Collapse, Paper, Stack, TextField, Typography } from '@mui/material';
import { Check, Functions, Gesture, Lightbulb, School, Visibility } from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import { BlockMath } from 'react-katex';
import 'katex/dist/katex.min.css';
import type { BoardReading, PracticeCheck, PracticeProblem, PracticeSolution } from '../types/MathTypes';

const Deck = styled(Paper)(({ theme }) => ({
  flex: 1,
  minWidth: 0,
  minHeight: 0,
  padding: theme.spacing(1.5, 2),
  display: 'flex',
  flexDirection: 'column',
  overflow: 'auto',
  borderRadius: 8,
}));

interface Props {
  problem: PracticeProblem | null;
  showEquation: boolean;
  onToggleEquation: () => void;
  showSketch: boolean;
  onToggleSketch: () => void;
  hints: string[];
  onHint: () => void;
  onReveal: () => void;
  solution: PracticeSolution | null;
  answer: string;
  onAnswerChange: (value: string) => void;
  onCheck: () => void;
  checking: boolean;
  lastCheck: PracticeCheck | null;
  reading: BoardReading | null;
  readingBusy: boolean;
  objectCount: number;
  onGoPractice: () => void;
}

/**
 * Top of the whiteboard: the word problem on the left, the equation / live
 * reading on the right. The canvas below is for working — the problem itself
 * is never dumped onto the drawing surface.
 */
export const PracticeDecks: React.FC<Props> = ({
  problem,
  showEquation,
  onToggleEquation,
  showSketch,
  onToggleSketch,
  hints,
  onHint,
  onReveal,
  solution,
  answer,
  onAnswerChange,
  onCheck,
  checking,
  lastCheck,
  reading,
  readingBusy,
  objectCount,
  onGoPractice,
}) => {
  const candidate = reading?.candidate;
  const live = reading?.reading;

  return (
    <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ height: { xs: 'auto', md: '100%' }, minHeight: 0 }}>
      <Deck variant="outlined">
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="overline" color="text.secondary" sx={{ letterSpacing: 0.6 }}>
            Word problem
          </Typography>
          {problem && (
            <>
              <Chip size="small" color="primary" label={problem.family_label} />
              <Chip size="small" variant="outlined" label={problem.difficulty} />
              <Box sx={{ flex: 1 }} />
              {problem.solved && <Chip size="small" color="success" label="Solved" />}
            </>
          )}
        </Stack>
        {problem ? (
          <>
            <Typography variant="body1" sx={{ lineHeight: 1.55, flex: 1 }}>
              {problem.problem}
            </Typography>
            {problem.note && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                {problem.note}
              </Typography>
            )}
            <Stack direction="row" spacing={1} flexWrap="wrap" rowGap={1} sx={{ mt: 1.5 }}>
              <Button size="small" startIcon={<Lightbulb />} onClick={onHint} disabled={hints.length >= problem.hints_available} sx={{ textTransform: 'none' }}>
                Hint ({hints.length}/{problem.hints_available})
              </Button>
              {problem.sketch && (
                <Button size="small" startIcon={<Gesture />} onClick={onToggleSketch} sx={{ textTransform: 'none' }}>
                  {showSketch ? 'Hide sketch' : 'Sketch it'}
                </Button>
              )}
            </Stack>
            <Collapse in={showSketch && Boolean(problem.sketch)}>
              <Alert severity="info" icon={<Gesture fontSize="inherit" />} sx={{ mt: 1 }}>
                <Typography variant="body2">{problem.sketch}</Typography>
              </Alert>
            </Collapse>
            {hints.length > 0 && (
              <Stack spacing={0.5} sx={{ mt: 1 }}>
                {hints.map((hint) => (
                  <Alert key={hint} severity="info" icon={<Lightbulb fontSize="inherit" />} sx={{ py: 0 }}>
                    <Typography variant="body2">{hint}</Typography>
                  </Alert>
                ))}
              </Stack>
            )}
          </>
        ) : (
          <Box sx={{ m: 'auto', textAlign: 'center', maxWidth: 360 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              Generate a practice problem and it stays here — left deck is the situation, right deck is the set-up. The board below is yours to work on.
            </Typography>
            <Button variant="contained" startIcon={<School />} onClick={onGoPractice} sx={{ textTransform: 'none' }}>
              Get a problem
            </Button>
          </Box>
        )}
      </Deck>

      <Deck variant="outlined">
        <Typography variant="overline" color="text.secondary" sx={{ letterSpacing: 0.6, mb: 1 }}>
          Equation &amp; live reading
        </Typography>

        {problem && (
          <>
            <Stack direction="row" spacing={1} flexWrap="wrap" rowGap={1} sx={{ mb: 1 }}>
              <Button size="small" variant={showEquation ? 'contained' : 'outlined'} startIcon={<Functions />} onClick={onToggleEquation} sx={{ textTransform: 'none' }}>
                {showEquation ? 'Hide equation' : 'Show the equation'}
              </Button>
              <Button size="small" color="warning" startIcon={<Visibility />} onClick={onReveal} disabled={Boolean(solution)} sx={{ textTransform: 'none' }}>
                Show solution
              </Button>
            </Stack>
            <Collapse in={showEquation}>
              <Box sx={{ mb: 1.5, p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Model the situation{problem.variable ? ` (unknown: ${problem.variable})` : ''}:
                </Typography>
                {problem.equation_latex ? (
                  <BlockMath math={problem.equation_latex} renderError={() => <code>{problem.equation}</code>} />
                ) : (
                  <Typography sx={{ fontFamily: 'monospace', mt: 0.5 }}>{problem.equation}</Typography>
                )}
              </Box>
            </Collapse>
          </>
        )}

        <Box sx={{ p: 1, border: 1, borderColor: 'divider', borderRadius: 1, mb: 1.5, minHeight: 64 }}>
          <Typography variant="caption" color="text.secondary" display="block">
            {readingBusy ? 'Reading the board…' : objectCount === 0 ? 'Write on the board — typed math (T) is read live. Ink is counted until a vision model is loaded.' : 'On the board'}
          </Typography>
          {candidate ? (
            <>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', mt: 0.5 }}>
                {candidate}
              </Typography>
              {live?.error && (
                <Typography variant="caption" color="text.secondary">
                  {live.error}
                </Typography>
              )}
              {live?.solution && !reading?.setup?.matches_model && !reading?.preview && (
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  → {live.solution}
                </Typography>
              )}
              {reading?.setup && (
                <Typography variant="caption" color={reading.setup.matches_model ? 'success.main' : 'text.secondary'} display="block" sx={{ mt: 0.5 }}>
                  {reading.setup.feedback}
                </Typography>
              )}
              {reading?.preview && (
                <Typography variant="caption" color={reading.preview.correct ? 'success.main' : 'text.secondary'} display="block">
                  {reading.preview.feedback}
                </Typography>
              )}
            </>
          ) : (
            objectCount > 0 && (
              <Typography variant="caption" color="text.secondary">
                {objectCount} mark{objectCount === 1 ? '' : 's'} on the canvas. Add a text box (T) with the equation or answer for an exact reading.
              </Typography>
            )
          )}
        </Box>

        {problem && (
          <>
            <Stack direction="row" spacing={1} alignItems="flex-start">
              <TextField
                size="small"
                fullWidth
                label="Your answer"
                placeholder={problem.variable ? `e.g. ${problem.variable} = 12` : 'e.g. 12 or 6*t + 2'}
                value={answer}
                disabled={problem.solved}
                onChange={(e) => onAnswerChange(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && onCheck()}
              />
              <Button variant="contained" onClick={onCheck} disabled={!answer.trim() || checking || problem.solved} startIcon={<Check />} sx={{ whiteSpace: 'nowrap' }}>
                Check
              </Button>
            </Stack>
            {lastCheck && !lastCheck.unreadable && (
              <Alert severity={lastCheck.correct ? 'success' : 'warning'} sx={{ mt: 1 }} icon={false}>
                {lastCheck.feedback}
                {lastCheck.correct && lastCheck.answer ? ` ${lastCheck.answer}` : ''}
              </Alert>
            )}
            <Collapse in={Boolean(solution)}>
              {solution && (
                <Box sx={{ mt: 1.5 }}>
                  <Typography variant="subtitle2">Worked solution — {solution.answer}</Typography>
                  <Stack component="ol" spacing={0.25} sx={{ pl: 2.5, m: 0 }}>
                    {solution.steps.slice(0, 6).map((step) => (
                      <Typography key={step} component="li" variant="caption">
                        {step}
                      </Typography>
                    ))}
                  </Stack>
                </Box>
              )}
            </Collapse>
          </>
        )}
      </Deck>
    </Stack>
  );
};
