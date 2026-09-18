import React from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Grid,
  List,
  ListItem,
  ListItemText,
  Typography,
} from '@mui/material';
import { Book, Edit, Functions, Mic, QuestionAnswer, School } from '@mui/icons-material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { styled } from '@mui/material/styles';

const Container = styled(Box)(({ theme }) => ({
  padding: theme.spacing(3),
  maxWidth: 1000,
  margin: '0 auto',
}));

const Code = styled('code')(({ theme }) => ({
  fontFamily: '"Cascadia Code", "Fira Code", Consolas, monospace',
  fontSize: '0.9em',
  padding: '0 4px',
  borderRadius: 4,
  backgroundColor: theme.palette.action.hover,
}));

const EXAMPLES = [
  ['Equations', 'solve x^2 - 5x + 6 = 0', '2y - 4 = 10'],
  ['Systems', '2x + 3 = 7 and x - y = 1'],
  ['Inequalities', 'x^2 > 4'],
  ['Derivatives', 'derivative of x^3 + sin(x)', 'd/dx x^3'],
  ['Integrals', 'integrate sin(x) dx', 'integrate x^2 from 0 to 3'],
  ['Limits', 'limit of sin(x)/x as x->0'],
  ['Algebra', 'simplify (x^2-1)/(x-1)', 'factor x^2 - 5x + 6', 'expand (x+1)^3'],
  ['Arithmetic', 'sqrt(16) + 2^3', '1/3 + 1/6'],
];

const FEATURES = [
  {
    icon: <Functions />,
    title: 'Symbolic engine',
    description: 'Every problem is first handled by an exact, offline computer-algebra engine (SymPy). Answers are deterministic and come with the steps used.',
    tags: ['Always available', 'Exact results', 'LaTeX output'],
  },
  {
    icon: <Edit />,
    title: 'Whiteboard',
    description: 'Sketch working, diagrams or equations with pen, shapes and text; select, move and delete objects; optional dot or square grid. Undo/redo, export as PNG or PDF.',
    tags: ['Vector canvas', 'Tool hotkeys', 'Grid', 'Export'],
  },
  {
    icon: <School />,
    title: 'Practice (learn by doing)',
    description:
      'Upload lecture notes or a textbook chapter and the tutor writes word problems from that material. Set up the equation yourself, check your answer, ask for hints, then compare with the modelling equation and worked solution.',
    tags: ['Chroma course index', 'Engine-verified problems', 'Hints & streaks'],
  },
  {
    icon: <QuestionAnswer />,
    title: 'Language model (optional)',
    description:
      'Pick the source in Settings → Language model (or the AI-source toggle in Quick settings): the local Qwen3-Omni model, OpenRouter, OpenAI, Ollama, LM Studio or any OpenAI-compatible endpoint, or Auto (local when loaded, otherwise the API). It solves free-form word problems and writes richer practice problems; every model answer is cross-checked by the symbolic engine.',
    tags: ['Local / OpenRouter / API', 'Auto fallback', 'Engine cross-check'],
  },
  {
    icon: <Mic />,
    title: 'Speech (optional)',
    description: 'With the MERaLiON speech model loaded you can dictate problems; with VibeVoice loaded answers can be read aloud.',
    tags: ['Requires speech models', 'Local only'],
  },
];

const FAQ = [
  {
    q: 'Why does it say "I couldn\'t interpret that as a math problem"?',
    a: 'The built-in engine understands mathematical expressions and a small set of instructions (solve, derivative, integrate, limit, simplify, factor, expand). Free-form word problems need a language model: load Qwen3-Omni from Settings, or connect OpenRouter / another API provider under Settings → Language model. The Quick settings toggle switches between Local, API and Auto at any time.',
  },
  {
    q: 'How does Practice use my course material?',
    a: 'Uploaded files are split into passages and embedded into a local Chroma index (all-MiniLM-L6-v2 when it can be downloaded, otherwise an offline hashing embedder). When you ask for a problem, the most relevant passages are retrieved and handed to the problem writer. If a language model is available it writes a fresh word problem plus its equation, which the symbolic engine must be able to solve before you see it; otherwise a verified template that matches the topic is used.',
  },
  {
    q: 'Do I have to type the answer in a particular form?',
    a: 'No. Enter a number, a fraction, an expression, or "x = 12". Equivalent forms count. If your value solves the equation but does not fit the situation (for example a negative length), you will be told exactly that.',
  },
  {
    q: 'Why is the microphone or drawing recognition disabled?',
    a: 'Those features depend on optional local models. The toolbar buttons enable themselves automatically once the backend reports the corresponding model as loaded. Nothing is sent to the cloud.',
  },
  {
    q: 'How do I check my own answer?',
    a: 'After the tutor solves a problem, press "Check my own answer" under the input, type your answer (for example x = 2 or x = 3) and send. The engine compares it symbolically, so equivalent forms count as correct.',
  },
  {
    q: 'Where does my API key go, and what is sent to the provider?',
    a: 'The key is saved on this computer only (in the backend data folder, readable by your user account) and is sent solely to the provider base URL you configured. When the API answers a question, the problem text is sent; for practice generation, the retrieved passages from your course material are included so the problem matches what you are studying. In "Local" mode nothing leaves your machine.',
  },
  {
    q: 'What does the confidence badge mean?',
    a: 'Results from the symbolic engine are exact and show high confidence. Results from a language model carry the confidence the model reported. Zero confidence means no engine could answer.',
  },
  {
    q: 'Where is my data?',
    a: 'Everything runs on this machine: the backend listens on localhost only, and solution history lives in memory for the current session.',
  },
];

const SHORTCUTS = [
  ['Enter', 'Send the problem (Shift+Enter for a new line)'],
  ['P / E / V / T', 'Pen · Eraser · Select · Text'],
  ['L / R / O', 'Line · Rectangle · Ellipse'],
  ['Del / Backspace', 'Delete the selected objects'],
  ['Esc', 'Deselect'],
  ['Ctrl + Z', 'Undo on the whiteboard'],
  ['Ctrl + Y', 'Redo on the whiteboard'],
  ['Ctrl + S', 'Export the transcript as text'],
  ['Ctrl + M', 'Start / stop the microphone (when speech is available)'],
];

export const HelpPage: React.FC = () => (
  <Container>
    <Typography variant="h4" component="h1" gutterBottom>
      Help
    </Typography>

    <Alert severity="info" sx={{ mb: 3 }}>
      Type a problem in the Tutor panel and press Enter. The symbolic engine answers instantly and works fully offline.
    </Alert>

    <Card sx={{ mb: 3 }}>
      <CardHeader avatar={<School />} title="What you can ask" subheader="Examples the built-in engine understands" />
      <CardContent>
        <Grid container spacing={1}>
          {EXAMPLES.map(([category, ...examples]) => (
            <Grid item xs={12} sm={6} key={category}>
              <Typography variant="subtitle2">{category}</Typography>
              {examples.map((example) => (
                <Typography key={example} variant="body2">
                  <Code>{example}</Code>
                </Typography>
              ))}
            </Grid>
          ))}
        </Grid>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 2 }}>
          Use <Code>^</Code> for powers, <Code>*</Code> for multiplication (or write <Code>2x</Code>), <Code>sqrt()</Code>, <Code>pi</Code>,{' '}
          <Code>E</Code>, <Code>oo</Code> for infinity. Unicode symbols such as √, π, ², ≤ are accepted too.
        </Typography>
      </CardContent>
    </Card>

    <Typography variant="h5" component="h2" gutterBottom>
      Features
    </Typography>
    <Grid container spacing={2} sx={{ mb: 3 }}>
      {FEATURES.map((feature) => (
        <Grid item xs={12} md={6} key={feature.title}>
          <Card sx={{ height: '100%' }}>
            <CardHeader avatar={feature.icon} title={feature.title} />
            <CardContent>
              <Typography variant="body2" paragraph>
                {feature.description}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {feature.tags.map((tag) => (
                  <Chip key={tag} label={tag} size="small" variant="outlined" />
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>

    <Typography variant="h5" component="h2" gutterBottom>
      Keyboard shortcuts
    </Typography>
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Grid container spacing={1.5}>
          {SHORTCUTS.map(([key, description]) => (
            <Grid item xs={12} sm={6} key={key}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Chip label={key} variant="outlined" color="primary" size="small" />
                <Typography variant="body2">{description}</Typography>
              </Box>
            </Grid>
          ))}
        </Grid>
      </CardContent>
    </Card>

    <Typography variant="h5" component="h2" gutterBottom>
      Frequently asked questions
    </Typography>
    {FAQ.map((item) => (
      <Accordion key={item.q} sx={{ mb: 1 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle1">{item.q}</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2">{item.a}</Typography>
        </AccordionDetails>
      </Accordion>
    ))}

    <Typography variant="h5" component="h2" gutterBottom sx={{ mt: 4 }}>
      Under the hood
    </Typography>
    <Card>
      <CardHeader avatar={<Book />} title="Technology" />
      <CardContent>
        <List dense>
          <ListItem>
            <ListItemText primary="Electron desktop shell with a React + Material UI renderer" />
          </ListItem>
          <ListItem>
            <ListItemText primary="Python FastAPI backend on localhost with a WebSocket for live requests" />
          </ListItem>
          <ListItem>
            <ListItemText primary="SymPy computer-algebra engine for exact, deterministic solving" />
          </ListItem>
          <ListItem>
            <ListItemText primary="Optional local models: Qwen3-Omni (reasoning and vision), MERaLiON (speech-to-text), VibeVoice (text-to-speech), with Whisper and XTTS as fallbacks" />
          </ListItem>
        </List>
      </CardContent>
    </Card>
  </Container>
);
