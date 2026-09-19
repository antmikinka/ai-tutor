import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  FormControl,
  InputLabel,
  Link,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import { AutoAwesome, Check, Close, Draw, Functions, Gesture, Lightbulb, Refresh, VolumeUp, Visibility } from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import { BlockMath } from 'react-katex';
import 'katex/dist/katex.min.css';
import { CourseMaterialPanel } from '../components/CourseMaterialPanel';
import { useSettingsContext } from '../contexts/SettingsContext';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import { ApiError, apiFetch, apiJson } from '../lib/backend';
import { describeLLMName } from '../lib/llm';
import { canSpeak, prefers, speak, styleLabel, toBackendStyle } from '../lib/vark';
import type { KnowledgeDocument, PracticeCheck, PracticeDifficulty, PracticeProblem, PracticeSolution, PracticeStats, PracticeStatus } from '../types/MathTypes';
import type { WhiteboardHandoff } from './MathTutorPage';

const Layout = styled(Box)(({ theme }) => ({
  display: 'flex',
  gap: theme.spacing(2),
  height: '100%',
  [theme.breakpoints.down('md')]: { flexDirection: 'column' },
}));

const MainPane = styled(Paper)(({ theme }) => ({
  flex: 1,
  minWidth: 0,
  padding: theme.spacing(2.5),
  display: 'flex',
  flexDirection: 'column',
  gap: theme.spacing(2),
  overflow: 'auto',
}));

const SidePane = styled(Box)(({ theme }) => ({
  width: 380,
  display: 'flex',
  flexDirection: 'column',
  gap: theme.spacing(2),
  overflow: 'auto',
  [theme.breakpoints.down('lg')]: { width: 320 },
  [theme.breakpoints.down('md')]: { width: '100%' },
}));

const TOPIC_SUGGESTIONS = ['linear equations', 'percent and discounts', 'ratios and proportion', 'speed distance time', 'area and perimeter', 'quadratics', 'exponential growth', 'derivatives'];

const describe = (error: unknown) => (error instanceof ApiError ? error.message : error instanceof Error ? error.message : String(error));

const StatChip: React.FC<{ label: string; value: React.ReactNode; color?: 'default' | 'primary' | 'success' | 'warning' }> = ({ label, value, color = 'default' }) => (
  <Chip size="small" color={color} variant={color === 'default' ? 'outlined' : 'filled'} label={`${label}: ${value}`} />
);

/**
 * Learn by doing: a word problem grounded in the student's own course
 * material, the modelling equation on demand, answer checking with graded
 * feedback, hints, and a worked solution.
 */
export const PracticePage: React.FC = () => {
  const navigate = useNavigate();
  const { settings, updatePracticeSettings } = useSettingsContext();
  const { practiceSettings, learningStyle } = settings;
  const likesVisual = prefers(learningStyle, 'visual');
  const likesAural = prefers(learningStyle, 'aural');
  const likesKinesthetic = prefers(learningStyle, 'kinesthetic');
  const { capabilities } = useWebSocketContext();

  const [status, setStatus] = useState<PracticeStatus | null>(null);
  const [topic, setTopic] = useState('');
  const [family, setFamily] = useState<string>('');
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);

  const [problem, setProblem] = useState<PracticeProblem | null>(null);
  const [generating, setGenerating] = useState(false);
  const [answer, setAnswer] = useState('');
  const [checking, setChecking] = useState(false);
  const [lastCheck, setLastCheck] = useState<PracticeCheck | null>(null);
  const [hints, setHints] = useState<string[]>([]);
  const [showEquation, setShowEquation] = useState(false);
  const [showSketch, setShowSketch] = useState(false);
  const [solution, setSolution] = useState<PracticeSolution | null>(null);
  const [stats, setStats] = useState<PracticeStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const answerRef = useRef<HTMLInputElement>(null);

  // Re-read status when the language model source changes (backend pushes new capabilities).
  const llmName = capabilities?.llm_name ?? null;
  useEffect(() => {
    apiFetch<PracticeStatus>('/api/practice/status')
      .then((s) => {
        setStatus(s);
        setStats((prev) => prev ?? s.stats);
      })
      .catch((err) => setError(describe(err)));
  }, [llmName]);

  const difficulty = practiceSettings.difficulty;
  const setDifficulty = (d: PracticeDifficulty) => void updatePracticeSettings({ difficulty: d });

  const generate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    setLastCheck(null);
    setSolution(null);
    setAnswer('');
    try {
      const next = await apiJson<PracticeProblem>('/api/practice/generate', 'POST', {
        topic,
        difficulty,
        family: family || null,
        doc_ids: selectedDocs.length ? selectedDocs : null,
        mode: practiceSettings.preferLanguageModel ? 'auto' : 'templates',
        learning_style: toBackendStyle(learningStyle),
      });
      setProblem(next);
      setHints(next.hints);
      setShowEquation(practiceSettings.showEquationImmediately);
      setShowSketch(likesVisual && Boolean(next.sketch));
      setTimeout(() => answerRef.current?.focus(), 50);
    } catch (err) {
      setError(describe(err));
    } finally {
      setGenerating(false);
    }
  }, [difficulty, family, learningStyle, likesVisual, practiceSettings.preferLanguageModel, practiceSettings.showEquationImmediately, selectedDocs, topic]);

  const check = useCallback(async () => {
    if (!problem || !answer.trim() || checking) return;
    setChecking(true);
    setError(null);
    try {
      const verdict = await apiJson<PracticeCheck>(`/api/practice/problems/${problem.id}/check`, 'POST', { answer });
      setLastCheck(verdict);
      setStats(verdict.stats);
      if (verdict.hint) setHints((h) => (h.includes(verdict.hint as string) ? h : [...h, verdict.hint as string]));
      if (verdict.correct) setProblem((p) => (p ? { ...p, solved: true, attempts: verdict.attempts } : p));
      else setProblem((p) => (p ? { ...p, attempts: verdict.attempts } : p));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError('That problem expired on the server. Generate a new one.');
      } else {
        setError(describe(err));
      }
    } finally {
      setChecking(false);
    }
  }, [answer, checking, problem]);

  const requestHint = useCallback(async () => {
    if (!problem) return;
    try {
      const result = await apiJson<{ hints: string[] }>(`/api/practice/problems/${problem.id}/hint`, 'POST');
      setHints(result.hints);
    } catch (err) {
      setError(describe(err));
    }
  }, [problem]);

  const reveal = useCallback(async () => {
    if (!problem) return;
    try {
      const result = await apiJson<PracticeSolution>(`/api/practice/problems/${problem.id}/solution`, 'POST');
      setSolution(result);
      setStats(result.stats);
      setShowEquation(true);
    } catch (err) {
      setError(describe(err));
    }
  }, [problem]);

  const toWhiteboard = () => {
    if (!problem) return;
    const state: WhiteboardHandoff = {
      whiteboardText: `${problem.problem}${showEquation ? `\n\nEquation: ${problem.equation}` : ''}`,
      prefillInput: showEquation ? problem.equation : undefined,
    };
    navigate('/', { state });
  };

  const families = status?.families ?? [];
  const noKnowledge = documents.length === 0;
  const generatorLabel = useMemo(() => {
    if (!problem) return '';
    const base = problem.generator === 'templates' ? 'Verified template' : `Language model (${describeLLMName(problem.generator)}) — verified by the symbolic engine`;
    return problem.learning_style ? `${base} · presented for ${styleLabel(learningStyle)}` : base;
  }, [learningStyle, problem]);

  return (
    <Layout>
      <MainPane elevation={1}>
        <Box>
          <Typography variant="h5" gutterBottom>
            Practice
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Get a word problem built from your course material, translate it into an equation yourself, then check your answer. The equation is there whenever you want to compare set-ups.
          </Typography>
        </Box>

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ sm: 'center' }} flexWrap="wrap" rowGap={1.5} useFlexGap>
          <TextField
            size="small"
            sx={{ flex: 1, minWidth: 240 }}
            label="Topic"
            placeholder={noKnowledge ? 'e.g. percent discounts, quadratics, derivatives' : 'Leave blank to practise from your material'}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !generating && void generate()}
          />
          <ToggleButtonGroup size="small" exclusive value={difficulty} onChange={(_, v: PracticeDifficulty | null) => v && setDifficulty(v)} aria-label="Difficulty">
            <ToggleButton value="easy">Easy</ToggleButton>
            <ToggleButton value="medium">Medium</ToggleButton>
            <ToggleButton value="hard">Hard</ToggleButton>
          </ToggleButtonGroup>
          <FormControl size="small" sx={{ minWidth: 170 }}>
            <InputLabel id="family-label">Skill</InputLabel>
            <Select labelId="family-label" label="Skill" value={family} onChange={(e) => setFamily(e.target.value)}>
              <MenuItem value="">
                <em>Auto</em>
              </MenuItem>
              {families.map((f) => (
                <MenuItem key={f.id} value={f.id}>
                  {f.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button variant="contained" onClick={() => void generate()} disabled={generating} startIcon={generating ? <CircularProgress size={16} color="inherit" /> : <AutoAwesome />} sx={{ whiteSpace: 'nowrap' }}>
            {problem ? 'New problem' : 'Generate'}
          </Button>
        </Stack>

        {!problem && !generating && (
          <Stack direction="row" spacing={0.75} flexWrap="wrap" rowGap={0.75}>
            {TOPIC_SUGGESTIONS.map((s) => (
              <Chip key={s} size="small" label={s} onClick={() => setTopic(s)} variant="outlined" />
            ))}
          </Stack>
        )}

        {error && (
          <Alert severity="error" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {problem && (
          <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" rowGap={1} sx={{ mb: 1.5 }}>
              <Chip size="small" color="primary" label={problem.family_label} />
              <Chip size="small" variant="outlined" label={problem.difficulty} />
              <Chip size="small" variant="outlined" label={problem.concept} />
              {problem.sources.map((s) => (
                <Tooltip key={`${s.doc_id}-${s.page ?? 0}`} title={s.snippet}>
                  <Chip size="small" variant="outlined" color="secondary" label={`${s.title}${s.page ? ` p.${s.page}` : ''}`} />
                </Tooltip>
              ))}
              <Box sx={{ flex: 1 }} />
              {likesAural && canSpeak() && (
                <Tooltip title="Read the problem aloud (browser voice)">
                  <Button size="small" startIcon={<VolumeUp />} onClick={() => speak(problem.problem)} sx={{ textTransform: 'none' }}>
                    Read aloud
                  </Button>
                </Tooltip>
              )}
              <Tooltip title="Send the problem to the whiteboard to work it out by hand">
                <Button size="small" variant={likesKinesthetic ? 'contained' : 'text'} startIcon={<Draw />} onClick={toWhiteboard} sx={{ textTransform: 'none' }}>
                  Work on whiteboard
                </Button>
              </Tooltip>
            </Stack>

            <Typography variant="h6" sx={{ fontWeight: 400, lineHeight: 1.5 }}>
              {problem.problem}
            </Typography>

            {problem.note && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                {problem.note}
              </Typography>
            )}

            <Divider sx={{ my: 2 }} />

            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" rowGap={1}>
              <Button size="small" variant={showEquation ? 'contained' : 'outlined'} startIcon={<Functions />} onClick={() => setShowEquation((v) => !v)} sx={{ textTransform: 'none' }}>
                {showEquation ? 'Hide equation' : 'Show the equation'}
              </Button>
              <Button size="small" variant="outlined" startIcon={<Lightbulb />} onClick={() => void requestHint()} disabled={hints.length >= problem.hints_available} sx={{ textTransform: 'none' }}>
                Hint ({hints.length}/{problem.hints_available})
              </Button>
              {problem.sketch && (
                <Button size="small" variant={showSketch ? 'contained' : 'outlined'} color="secondary" startIcon={<Gesture />} onClick={() => setShowSketch((v) => !v)} sx={{ textTransform: 'none' }}>
                  {showSketch ? 'Hide sketch idea' : 'Sketch it'}
                </Button>
              )}
              <Button size="small" variant="outlined" color="warning" startIcon={<Visibility />} onClick={() => void reveal()} disabled={Boolean(solution)} sx={{ textTransform: 'none' }}>
                Show solution
              </Button>
            </Stack>

            <Collapse in={showEquation}>
              <Box sx={{ mt: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  Model the situation{problem.variable ? ` (unknown: ${problem.variable})` : ''}:
                </Typography>
                {problem.equation_latex ? (
                  <BlockMath math={problem.equation_latex} renderError={() => <code>{problem.equation}</code>} />
                ) : (
                  <Typography variant="body1" sx={{ fontFamily: 'monospace', mt: 0.5 }}>
                    {problem.equation}
                  </Typography>
                )}
                <Button size="small" onClick={() => navigate('/', { state: { prefillInput: problem.equation } as WhiteboardHandoff })} sx={{ textTransform: 'none' }}>
                  Solve this in the tutor
                </Button>
              </Box>
            </Collapse>

            <Collapse in={showSketch && Boolean(problem.sketch)}>
              <Alert severity="info" icon={<Gesture fontSize="inherit" />} sx={{ mt: 2 }} action={
                <Button size="small" color="inherit" onClick={toWhiteboard} sx={{ textTransform: 'none' }}>
                  Open whiteboard
                </Button>
              }>
                <Typography variant="body2">
                  <strong>Sketch it:</strong> {problem.sketch}
                </Typography>
              </Alert>
            </Collapse>

            {hints.length > 0 && (
              <Stack spacing={0.5} sx={{ mt: 2 }}>
                {hints.map((hint, i) => (
                  <Alert key={i} severity="info" icon={<Lightbulb fontSize="inherit" />} sx={{ py: 0 }}>
                    <Typography variant="body2">{hint}</Typography>
                  </Alert>
                ))}
              </Stack>
            )}

            <Stack direction="row" spacing={1} sx={{ mt: 2 }} alignItems="flex-start">
              <TextField
                inputRef={answerRef}
                size="small"
                fullWidth
                label="Your answer"
                placeholder={problem.variable ? `e.g. ${problem.variable} = 12 or just 12` : 'e.g. 6*t + 2'}
                value={answer}
                disabled={problem.solved}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && void check()}
                error={Boolean(lastCheck && !lastCheck.correct && !lastCheck.unreadable)}
                helperText={lastCheck?.unreadable ? lastCheck.feedback : problem.solved ? 'Solved' : `${problem.attempts} attempt${problem.attempts === 1 ? '' : 's'}`}
              />
              <Button variant="contained" onClick={() => void check()} disabled={!answer.trim() || checking || problem.solved} startIcon={checking ? <CircularProgress size={16} color="inherit" /> : <Check />} sx={{ whiteSpace: 'nowrap', mt: '1px' }}>
                Check
              </Button>
            </Stack>

            {lastCheck && !lastCheck.unreadable && (
              <Alert severity={lastCheck.correct ? 'success' : 'warning'} icon={lastCheck.correct ? <Check fontSize="inherit" /> : <Close fontSize="inherit" />} sx={{ mt: 1.5 }}>
                {lastCheck.feedback}
                {lastCheck.correct && lastCheck.answer && (
                  <>
                    {' '}
                    <strong>{lastCheck.answer}</strong>
                  </>
                )}
              </Alert>
            )}

            {lastCheck?.correct && (
              <Button sx={{ mt: 1.5, textTransform: 'none' }} variant="outlined" startIcon={<Refresh />} onClick={() => void generate()}>
                Next problem
              </Button>
            )}

            <Collapse in={Boolean(solution)}>
              {solution && (
                <Box sx={{ mt: 2, p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                  <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
                    <Typography variant="subtitle2" sx={{ flex: 1 }}>
                      Worked solution — {solution.answer}
                    </Typography>
                    {likesAural && canSpeak() && (
                      <Button size="small" startIcon={<VolumeUp />} onClick={() => speak(solution.steps.join('. '))} sx={{ textTransform: 'none' }}>
                        Read steps
                      </Button>
                    )}
                  </Stack>
                  {solution.sketch && (
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      <Gesture fontSize="inherit" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
                      {solution.sketch}
                    </Typography>
                  )}
                  <Stack component="ol" spacing={0.5} sx={{ pl: 2.5, m: 0 }}>
                    {solution.steps.map((step, i) => (
                      <Typography key={i} component="li" variant="body2">
                        {step}
                      </Typography>
                    ))}
                  </Stack>
                  {solution.solution_latex && <BlockMath math={solution.solution_latex} renderError={() => <code>{solution.engine_solution}</code>} />}
                </Box>
              )}
            </Collapse>

            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
              {generatorLabel}
            </Typography>
          </Paper>
        )}

        {!problem && generating && (
          <Box display="flex" alignItems="center" gap={1.5} py={4} justifyContent="center">
            <CircularProgress size={22} />
            <Typography color="text.secondary">Writing a problem…</Typography>
          </Box>
        )}
      </MainPane>

      <SidePane>
        <Paper elevation={1} sx={{ p: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            Session
          </Typography>
          {stats ? (
            <Stack direction="row" flexWrap="wrap" gap={0.75}>
              <StatChip label="Solved" value={`${stats.solved}/${stats.generated}`} color={stats.solved ? 'success' : 'default'} />
              <StatChip label="First try" value={stats.first_try} />
              <StatChip label="Streak" value={stats.streak} color={stats.streak >= 3 ? 'primary' : 'default'} />
              <StatChip label="Best" value={stats.best_streak} />
              <StatChip label="Revealed" value={stats.revealed} color={stats.revealed ? 'warning' : 'default'} />
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">
              No problems yet.
            </Typography>
          )}
          {status && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
              Problem writer: {status.llm_available ? `${describeLLMName(status.llm)} with engine verification` : 'verified templates (no language model active)'}.{' '}
              <Link component="button" type="button" variant="caption" onClick={() => navigate('/settings')}>
                Change
              </Link>
            </Typography>
          )}
        </Paper>

        <CourseMaterialPanel selectedIds={selectedDocs} onSelectionChange={setSelectedDocs} onDocumentsChange={setDocuments} dense />
      </SidePane>
    </Layout>
  );
};
