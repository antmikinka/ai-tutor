import React, { useEffect, useRef } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import HelpIcon from '@mui/icons-material/Help';
import MicIcon from '@mui/icons-material/Mic';
import BrushIcon from '@mui/icons-material/Brush';
import ImageIcon from '@mui/icons-material/Image';
import { BlockMath } from 'react-katex';
import 'katex/dist/katex.min.css';
import type { ChatMessage } from '../types/MathTypes';
import type { BackendSolution } from '../types/protocol';

const Scroller = styled(Box)(({ theme }) => ({
  flex: 1,
  minHeight: 0,
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: theme.spacing(1.5),
  paddingRight: theme.spacing(0.5),
}));

const Bubble = styled(Paper, { shouldForwardProp: (prop) => prop !== 'align' })<{ align: 'left' | 'right' }>(
  ({ theme, align }) => ({
    padding: theme.spacing(1.5),
    maxWidth: '92%',
    alignSelf: align === 'right' ? 'flex-end' : 'flex-start',
    backgroundColor:
      align === 'right' ? theme.palette.primary.main : theme.palette.mode === 'dark' ? theme.palette.grey[800] : theme.palette.grey[100],
    color: align === 'right' ? theme.palette.primary.contrastText : theme.palette.text.primary,
    borderRadius: align === 'right' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
    wordBreak: 'break-word',
  }),
);

const Mono = styled('span')({ fontFamily: '"Cascadia Code", "Fira Code", Consolas, monospace' });

interface ChatInterfaceProps {
  messages: ChatMessage[];
  isProcessing: boolean;
  showConfidence?: boolean;
  showSteps?: boolean;
  showModelInfo?: boolean;
  onVerify?: (solution: BackendSolution) => void;
}

const confidenceMeta = (confidence: number) => {
  if (confidence >= 0.8) return { color: 'success' as const, icon: <CheckCircleIcon fontSize="small" />, label: 'High' };
  if (confidence >= 0.5) return { color: 'warning' as const, icon: <HelpIcon fontSize="small" />, label: 'Medium' };
  return { color: 'error' as const, icon: <ErrorIcon fontSize="small" />, label: 'Low' };
};

const humanModel = (modelUsed: string) => {
  if (modelUsed === 'sympy') return 'Symbolic engine (SymPy)';
  if (modelUsed === 'none') return 'No engine could answer';
  return modelUsed.replace(/^llm:/, 'AI model: ');
};

const SourceIcon: React.FC<{ source: 'text' | 'voice' | 'drawing' | 'image' }> = ({ source }) => {
  if (source === 'voice') return <MicIcon fontSize="inherit" />;
  if (source === 'drawing') return <BrushIcon fontSize="inherit" />;
  if (source === 'image') return <ImageIcon fontSize="inherit" />;
  return null;
};

const SolutionBubble: React.FC<{
  solution: BackendSolution;
  showConfidence: boolean;
  showSteps: boolean;
  showModelInfo: boolean;
}> = ({ solution, showConfidence, showSteps, showModelInfo }) => {
  const meta = confidenceMeta(solution.confidence);
  const unsolved = solution.confidence === 0;

  return (
    <Bubble align="left" elevation={0} variant="outlined">
      {unsolved ? (
        <Alert severity="warning" sx={{ mb: 1 }} icon={false}>
          {solution.solution}
        </Alert>
      ) : (
        <>
          <Typography variant="overline" color="text.secondary">
            {solution.problem_type.replace(/_/g, ' ')}
          </Typography>
          {solution.solution_latex ? (
            <Box sx={{ overflowX: 'auto', my: 0.5 }}>
              <BlockMath math={solution.solution_latex} renderError={() => <Mono>{solution.solution}</Mono>} />
            </Box>
          ) : (
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              <Mono>{solution.solution}</Mono>
            </Typography>
          )}
        </>
      )}

      {showSteps && solution.steps.length > 0 && (
        <Accordion disableGutters elevation={0} sx={{ bgcolor: 'transparent', '&:before': { display: 'none' } }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0, minHeight: 36 }}>
            <Typography variant="body2">{unsolved ? 'Why' : `${solution.steps.length} steps`}</Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ px: 0, pt: 0 }}>
            <Stack component="ol" spacing={0.5} sx={{ m: 0, pl: 2.5 }}>
              {solution.steps.map((step, index) => (
                <Typography component="li" variant="body2" key={index}>
                  <Mono>{step}</Mono>
                </Typography>
              ))}
            </Stack>
          </AccordionDetails>
        </Accordion>
      )}

      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" sx={{ mt: 1 }}>
        {showConfidence && (
          <Tooltip title={`${Math.round(solution.confidence * 100)}% confidence`}>
            <Chip size="small" color={meta.color} icon={meta.icon} label={`${meta.label} confidence`} variant="outlined" />
          </Tooltip>
        )}
        {showModelInfo && (
          <Typography variant="caption" color="text.secondary">
            {humanModel(solution.model_used)} · {(solution.processing_time * 1000).toFixed(0)} ms
          </Typography>
        )}
      </Stack>
    </Bubble>
  );
};

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  messages,
  isProcessing,
  showConfidence = true,
  showSteps = true,
  showModelInfo = true,
}) => {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, isProcessing]);

  return (
    <Scroller>
      {messages.length === 0 && !isProcessing && (
        <Alert severity="info">
          <Typography variant="body2" gutterBottom>
            Ask a math question. The built-in symbolic engine solves equations, systems, inequalities, derivatives,
            integrals, limits, simplification and arithmetic instantly and offline.
          </Typography>
          <Typography variant="body2" component="div">
            Try: <Mono>solve x^2 - 5x + 6 = 0</Mono>, <Mono>derivative of sin(x)*x</Mono>,{' '}
            <Mono>integrate x^2 from 0 to 3</Mono>, <Mono>limit of sin(x)/x as x-&gt;0</Mono>
          </Typography>
        </Alert>
      )}

      {messages.map((message) => {
        switch (message.kind) {
          case 'user':
            return (
              <Bubble key={message.id} align="right" elevation={0}>
                <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <SourceIcon source={message.source} />
                  <Mono>{message.text}</Mono>
                </Typography>
              </Bubble>
            );
          case 'solution':
            return (
              <SolutionBubble
                key={message.id}
                solution={message.solution}
                showConfidence={showConfidence}
                showSteps={showSteps}
                showModelInfo={showModelInfo}
              />
            );
          case 'verification':
            return (
              <Bubble key={message.id} align="left" elevation={0} variant="outlined">
                <Alert severity={message.verdict.is_correct ? 'success' : 'warning'} icon={false} sx={{ mb: 0.5 }}>
                  {message.verdict.feedback}
                </Alert>
                <Typography variant="caption" color="text.secondary">
                  Checked <Mono>{message.proposed}</Mono> against <Mono>{message.problem}</Mono>
                </Typography>
              </Bubble>
            );
          case 'drawing':
            return (
              <Bubble key={message.id} align="left" elevation={0} variant="outlined">
                {message.analysis.available ? (
                  <>
                    <Typography variant="body2">Recognized: <Mono>{message.analysis.recognized_text || '—'}</Mono></Typography>
                    {message.analysis.equations.map((eq, i) => (
                      <Typography key={i} variant="body2">
                        <Mono>{eq.text || eq.equation}</Mono>
                      </Typography>
                    ))}
                  </>
                ) : (
                  <Alert severity="info" icon={false}>
                    {message.analysis.message || 'Drawing recognition is not available.'}
                  </Alert>
                )}
                {message.analysis.image_analysis && (
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                    {message.analysis.image_analysis.is_blank
                      ? 'The canvas is blank.'
                      : `${message.analysis.image_analysis.components} stroke group(s), ${(
                          message.analysis.image_analysis.ink_coverage * 100
                        ).toFixed(1)}% ink coverage`}
                  </Typography>
                )}
              </Bubble>
            );
          case 'info':
            return (
              <Alert key={message.id} severity="info" variant="outlined" sx={{ py: 0 }}>
                {message.text}
              </Alert>
            );
          case 'error':
            return (
              <Alert key={message.id} severity="error" variant="outlined" sx={{ py: 0 }}>
                {message.text}
                {message.code && (
                  <Typography variant="caption" display="block" color="text.secondary">
                    {message.code}
                  </Typography>
                )}
              </Alert>
            );
          default:
            return null;
        }
      })}

      {isProcessing && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 1 }}>
          <CircularProgress size={18} />
          <Typography variant="body2" color="text.secondary">
            Working on it…
          </Typography>
        </Box>
      )}
      <div ref={endRef} />
    </Scroller>
  );
};
