import React, { useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemText,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  LinearProgress,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import HelpIcon from '@mui/icons-material/Help';
import { MathSolution } from '../types/MathTypes';
import { InlineMath } from 'react-katex';
import 'katex/dist/katex.min.css';

const ChatContainer = styled(Box)(({ theme }) => ({
  flex: 1,
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: theme.spacing(1),
  maxHeight: 400,
}));

const MessageBubble = styled(Paper, { shouldForwardProp: (prop) => prop !== 'isUser' })<{
  isUser?: boolean;
}>(({ theme, isUser }) => ({
  padding: theme.spacing(1.5),
  backgroundColor: isUser ? theme.palette.primary.light : theme.palette.grey[100],
  color: isUser ? theme.palette.primary.contrastText : theme.palette.text.primary,
  borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
  maxWidth: '80%',
  wordWrap: 'break-word',
}));

interface ChatInterfaceProps {
  solutions: MathSolution[];
  currentSolution: MathSolution | null;
  isProcessing: boolean;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  solutions,
  currentSolution,
  isProcessing,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [solutions, currentSolution, isProcessing]);

  const formatConfidence = (confidence: number) => {
    if (confidence >= 0.8) return { color: 'success', icon: <CheckCircleIcon />, label: 'High' };
    if (confidence >= 0.6) return { color: 'warning', icon: <HelpIcon />, label: 'Medium' };
    return { color: 'error', icon: <ErrorIcon />, label: 'Low' };
  };

  const formatMathExpression = (text: string) => {
    // Simple regex to detect mathematical expressions
    const mathRegex = /\$([^$]+)\$/g;
    const parts = text.split(mathRegex);

    return parts.map((part, index) => {
      if (index % 2 === 1) {
        // This is a mathematical expression
        return <InlineMath key={index} math={part} />;
      }
      return part;
    });
  };

  return (
    <ChatContainer>
      {/* Welcome Message */}
      {solutions.length === 0 && !isProcessing && (
        <Alert severity="info" sx={{ mb: 2 }}>
          <Typography variant="body2">
            Hello! I'm your AI Math Tutor. You can:
          </Typography>
          <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
            <li>Type or speak your math problem</li>
            <li>Draw equations on the canvas</li>
            <li>Upload images of math problems</li>
            <li>Ask for step-by-step explanations</li>
          </ul>
        </Alert>
      )}

      {/* Processing Indicator */}
      {isProcessing && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 2 }}>
          <CircularProgress size={20} />
          <Typography variant="body2">Analyzing your problem...</Typography>
          <LinearProgress sx={{ flex: 1 }} />
        </Box>
      )}

      {/* Solution Messages */}
      <List sx={{ flex: 1, overflowY: 'auto' }}>
        {solutions.map((solution, index) => (
          <ListItem key={solution.id} sx={{ flexDirection: 'column', alignItems: 'flex-start' }}>
            <MessageBubble isUser={false} elevation={1}>
              <Box sx={{ width: '100%' }}>
                {/* Problem Statement */}
                <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
                  Problem:
                </Typography>
                <Typography variant="body2" gutterBottom>
                  {formatMathExpression(solution.problem)}
                </Typography>

                {/* Solution */}
                <Typography variant="subtitle2" fontWeight="bold" gutterBottom sx={{ mt: 1 }}>
                  Solution:
                </Typography>
                <Typography variant="body2" gutterBottom>
                  {formatMathExpression(solution.solution)}
                </Typography>

                {/* Confidence Score */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    Confidence:
                  </Typography>
                  <Chip
                    size="small"
                    label={formatConfidence(solution.confidence).label}
                    color={formatConfidence(solution.confidence).color as any}
                    icon={formatConfidence(solution.confidence).icon}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {Math.round(solution.confidence * 100)}%
                  </Typography>
                </Box>

                {/* Steps Accordion */}
                {solution.steps && solution.steps.length > 0 && (
                  <Accordion sx={{ mt: 1, boxShadow: 'none' }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="body2">View Step-by-Step Solution</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <List dense>
                        {solution.steps.map((step, stepIndex) => (
                          <ListItem key={stepIndex} sx={{ py: 0.5 }}>
                            <ListItemText
                              primary={
                                <Typography variant="body2">
                                  <strong>Step {stepIndex + 1}:</strong> {formatMathExpression(step)}
                                </Typography>
                              }
                            />
                          </ListItem>
                        ))}
                      </List>
                    </AccordionDetails>
                  </Accordion>
                )}
              </Box>
            </MessageBubble>

            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
              {new Date(solution.timestamp).toLocaleTimeString()}
            </Typography>
          </ListItem>
        ))}
      </List>

      <div ref={messagesEndRef} />
    </ChatContainer>
  );
};