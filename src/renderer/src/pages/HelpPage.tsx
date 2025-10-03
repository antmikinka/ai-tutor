import React from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardHeader,
  List,
  ListItem,
  ListItemText,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  Alert,
} from '@mui/material';
import {
  School,
  Mic,
  CameraAlt,
  Edit,
  QuestionAnswer,
  Book,
  GitHub,
  ContactSupport,
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

const HelpContainer = styled(Box)(({ theme }) => ({
  padding: theme.spacing(3),
  maxWidth: 1000,
  margin: '0 auto',
}));

const FeatureCard = styled(Card)(({ theme }) => ({
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
}));

export const HelpPage: React.FC = () => {
  const features = [
    {
      icon: <Edit />,
      title: 'Drawing Canvas',
      description: 'Draw mathematical equations, graphs, and diagrams using the interactive canvas.',
      features: ['Multiple drawing tools', 'Shape recognition', 'Export as image'],
    },
    {
      icon: <Mic />,
      title: 'Voice Input',
      description: 'Speak your math problems naturally using advanced speech recognition.',
      features: ['Natural language processing', 'Multi-language support', 'Real-time transcription'],
    },
    {
      icon: <CameraAlt />,
      title: 'Image Recognition',
      description: 'Upload or capture images of handwritten or printed math problems.',
      features: ['OCR technology', 'Handwriting recognition', 'Multiple formats supported'],
    },
    {
      icon: <QuestionAnswer />,
      title: 'AI Assistant',
      description: 'Get step-by-step explanations and solutions powered by advanced AI.',
      features: ['Qwen3-Omni-30B-A3B-Thinking model', 'Confidence scoring', 'Detailed explanations'],
    },
  ];

  const faqs = [
    {
      question: 'How do I start solving a math problem?',
      answer: 'You can start by typing your problem in the chat interface, drawing on the canvas, speaking your question, or uploading an image of the problem.',
    },
    {
      question: 'What types of math problems can it solve?',
      answer: 'The AI can handle arithmetic, algebra, calculus, geometry, trigonometry, statistics, and more advanced mathematical concepts.',
    },
    {
      question: 'How accurate are the solutions?',
      answer: 'The AI provides confidence scores for each solution. Most problems have high accuracy (80%+), but complex problems may vary.',
    },
    {
      question: 'Can I save my work?',
      answer: 'Yes! You can export solutions as PDF, PNG images, or text files using the export options in the chat interface.',
    },
    {
      question: 'Is my data private?',
      answer: 'All processing happens locally on your Windows machine. No data is sent to external servers, ensuring complete privacy.',
    },
    {
      question: 'How do I adjust the difficulty level?',
      answer: 'You can adjust the AI\'s creativity and response length in the Settings page under AI Model Settings.',
    },
  ];

  const shortcuts = [
    { key: 'Ctrl + Enter', description: 'Send message' },
    { key: 'Ctrl + Z', description: 'Undo on canvas' },
    { key: 'Ctrl + Y', description: 'Redo on canvas' },
    { key: 'F1', description: 'Open help' },
    { key: 'Ctrl + S', description: 'Export solution' },
    { key: 'Ctrl + M', description: 'Toggle microphone' },
  ];

  return (
    <HelpContainer>
      <Typography variant="h4" component="h1" gutterBottom>
        Help & Documentation
      </Typography>

      <Alert severity="info" sx={{ mb: 3 }}>
        Welcome to AI Math Tutor! This guide will help you get started and make the most of all features.
      </Alert>

      {/* Getting Started */}
      <Card sx={{ mb: 3 }}>
        <CardHeader
          avatar={<School />}
          title="Getting Started"
          subheader="Quick start guide to using AI Math Tutor"
        />
        <CardContent>
          <Typography variant="body1" paragraph>
            AI Math Tutor is your personal mathematical learning assistant. Here\'s how to get started:
          </Typography>
          <List>
            <ListItem>
              <ListItemText primary="1. Type your math problem in the chat area or draw it on the canvas" />
            </ListItem>
            <ListItem>
              <ListItemText primary="2. Use voice input by clicking the microphone icon" />
            </ListItem>
            <ListItem>
              <ListItemText primary="3. Upload images of math problems for automatic recognition" />
            </ListItem>
            <ListItem>
              <ListItemText primary="4. Review the step-by-step solution provided by the AI" />
            </ListItem>
            <ListItem>
              <ListItemText primary="5. Export your work or ask follow-up questions" />
            </ListItem>
          </List>
        </CardContent>
      </Card>

      {/* Features */}
      <Typography variant="h5" component="h2" gutterBottom sx={{ mt: 4 }}>
        Key Features
      </Typography>
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {features.map((feature, index) => (
          <Grid item xs={12} md={6} lg={3} key={index}>
            <FeatureCard>
              <CardHeader avatar={feature.icon} title={feature.title} />
              <CardContent>
                <Typography variant="body2" paragraph>
                  {feature.description}
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {feature.features.map((feat, i) => (
                    <Chip key={i} label={feat} size="small" variant="outlined" />
                  ))}
                </Box>
              </CardContent>
            </FeatureCard>
          </Grid>
        ))}
      </Grid>

      {/* FAQ */}
      <Typography variant="h5" component="h2" gutterBottom sx={{ mt: 4 }}>
        Frequently Asked Questions
      </Typography>
      {faqs.map((faq, index) => (
        <Accordion key={index} sx={{ mb: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6">{faq.question}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body1">{faq.answer}</Typography>
          </AccordionDetails>
        </Accordion>
      ))}

      {/* Keyboard Shortcuts */}
      <Typography variant="h5" component="h2" gutterBottom sx={{ mt: 4 }}>
        Keyboard Shortcuts
      </Typography>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2}>
            {shortcuts.map((shortcut, index) => (
              <Grid item xs={12} sm={6} md={4} key={index}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Chip label={shortcut.key} variant="outlined" color="primary" />
                  <Typography variant="body2">{shortcut.description}</Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>

      {/* Technical Information */}
      <Typography variant="h5" component="h2" gutterBottom sx={{ mt: 4 }}>
        Technical Information
      </Typography>
      <Card>
        <CardHeader
          avatar={<Book />}
          title="System Requirements & Technology Stack"
        />
        <CardContent>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography variant="h6" gutterBottom>
                Minimum Requirements
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText primary="Windows 10 or later" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="8GB RAM (16GB recommended)" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="2GB free disk space" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="DirectX 11 compatible graphics" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Microphone for voice input" />
                </ListItem>
              </List>
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="h6" gutterBottom>
                Technology Stack
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText primary="Electron for cross-platform desktop app" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="React & Material-UI for user interface" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="FastAPI backend with WebSocket support" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Qwen3-Omni-30B-A3B-Thinking AI model" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="OpenAI Whisper for speech recognition" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Coqui XTTS-v2 for text-to-speech" />
                </ListItem>
              </List>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Support */}
      <Typography variant="h5" component="h2" gutterBottom sx={{ mt: 4 }}>
        Support & Resources
      </Typography>
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader
              avatar={<ContactSupport />}
              title="Get Help"
            />
            <CardContent>
              <List>
                <ListItem>
                  <ListItemText primary="Email: support@aimathtutor.com" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Documentation: docs.aimathtutor.com" />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Community: community.aimathtutor.com" />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader
              avatar={<GitHub />}
              title="Contribute"
            />
            <CardContent>
              <Typography variant="body2" paragraph>
                AI Math Tutor is open source! Contribute to the project on GitHub.
              </Typography>
              <Chip label="github.com/aimathtutor" variant="outlined" />
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </HelpContainer>
  );
};