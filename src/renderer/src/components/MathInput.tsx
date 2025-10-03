import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Popover,
  Paper,
  Typography,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Chip,
} from '@mui/material';
import {
  Functions,
  Close,
  Send,
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import { InlineMath } from 'react-katex';
import 'katex/dist/katex.min.css';

const MathSymbolsContainer = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(2),
  maxWidth: 400,
  maxHeight: 300,
  overflowY: 'auto',
}));

const SymbolGrid = styled(Box)(({ theme }) => ({
  display: 'grid',
  gridTemplateColumns: 'repeat(6, 1fr)',
  gap: theme.spacing(1),
  marginTop: theme.spacing(1),
}));

interface MathInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
}

export const MathInput: React.FC<MathInputProps> = ({ value, onChange, onSend }) => {
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const [selectedMode, setSelectedMode] = useState<'basic' | 'advanced'>('basic');

  const basicSymbols = [
    { symbol: '+', latex: '+', display: '+' },
    { symbol: '-', latex: '-', display: '-' },
    { symbol: '×', latex: '\\times', display: '×' },
    { symbol: '÷', latex: '\\div', display: '÷' },
    { symbol: '=', latex: '=', display: '=' },
    { symbol: '≠', latex: '\\neq', display: '≠' },
    { symbol: '<', latex: '<', display: '<' },
    { symbol: '>', latex: '>', display: '>' },
    { symbol: '≤', latex: '\\leq', display: '≤' },
    { symbol: '≥', latex: '\\geq', display: '≥' },
    { symbol: '±', latex: '\\pm', display: '±' },
    { symbol: '∞', latex: '\\infty', display: '∞' },
  ];

  const advancedSymbols = [
    { symbol: '√', latex: '\\sqrt{}', display: '√' },
    { symbol: '²', latex: '^2', display: '²' },
    { symbol: '³', latex: '^3', display: '³' },
    { symbol: 'π', latex: '\\pi', display: 'π' },
    { symbol: 'θ', latex: '\\theta', display: 'θ' },
    { symbol: 'α', latex: '\\alpha', display: 'α' },
    { symbol: 'β', latex: '\\beta', display: 'β' },
    { symbol: 'γ', latex: '\\gamma', display: 'γ' },
    { symbol: 'Δ', latex: '\\Delta', display: 'Δ' },
    { symbol: '∫', latex: '\\int', display: '∫' },
    { symbol: '∑', latex: '\\sum', display: '∑' },
    { symbol: '∏', latex: '\\prod', display: '∏' },
  ];

  const functions = [
    { symbol: 'sin', latex: '\\sin', display: 'sin' },
    { symbol: 'cos', latex: '\\cos', display: 'cos' },
    { symbol: 'tan', latex: '\\tan', display: 'tan' },
    { symbol: 'log', latex: '\\log', display: 'log' },
    { symbol: 'ln', latex: '\\ln', display: 'ln' },
    { symbol: 'lim', latex: '\\lim', display: 'lim' },
  ];

  const handleSymbolClick = (latex: string, display: string) => {
    const newValue = value + display;
    onChange(newValue);
  };

  const handleFunctionClick = (latex: string, display: string) => {
    const newValue = value + display + '()';
    onChange(newValue);
  };

  const open = Boolean(anchorEl);
  const id = open ? 'math-symbol-popover' : undefined;

  return (
    <Box sx={{ mt: 1 }}>
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
        <TextField
          fullWidth
          size="small"
          variant="outlined"
          placeholder="Enter mathematical expression..."
          value={value}
          onChange={(e) => onChange(e.target.value)}
          multiline
          rows={2}
          sx={{ fontFamily: 'monospace' }}
        />

        <Button
          aria-describedby={id}
          onClick={(e) => setAnchorEl(e.currentTarget)}
          variant="outlined"
          size="small"
          startIcon={<Functions />}
        >
          Symbols
        </Button>

        <Button
          onClick={onSend}
          variant="contained"
          size="small"
          disabled={!value.trim()}
          startIcon={<Send />}
        >
          Send
        </Button>
      </Box>

      {/* Preview */}
      {value && (
        <Box sx={{ mt: 1, p: 1, backgroundColor: 'grey.100', borderRadius: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Preview:
          </Typography>
          <Box sx={{ mt: 0.5 }}>
            <InlineMath math={value} />
          </Box>
        </Box>
      )}

      {/* Math Symbols Popover */}
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}
      >
        <MathSymbolsContainer>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h6">Mathematical Symbols</Typography>
            <IconButton onClick={() => setAnchorEl(null)} size="small">
              <Close />
            </IconButton>
          </Box>

          {/* Mode Toggle */}
          <ToggleButtonGroup
            value={selectedMode}
            exclusive
            onChange={(_, newMode) => newMode && setSelectedMode(newMode)}
            size="small"
            sx={{ mt: 1 }}
          >
            <ToggleButton value="basic">Basic</ToggleButton>
            <ToggleButton value="advanced">Advanced</ToggleButton>
          </ToggleButtonGroup>

          {/* Basic Symbols */}
          {selectedMode === 'basic' && (
            <SymbolGrid>
              {basicSymbols.map((item, index) => (
                <Button
                  key={index}
                  size="small"
                  onClick={() => handleSymbolClick(item.latex, item.display)}
                  sx={{ minWidth: 40, height: 40, fontSize: '1.2em' }}
                >
                  {item.display}
                </Button>
              ))}
            </SymbolGrid>
          )}

          {/* Advanced Symbols */}
          {selectedMode === 'advanced' && (
            <>
              <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
                Advanced Symbols
              </Typography>
              <SymbolGrid>
                {advancedSymbols.map((item, index) => (
                  <Button
                    key={index}
                    size="small"
                    onClick={() => handleSymbolClick(item.latex, item.display)}
                    sx={{ minWidth: 40, height: 40, fontSize: '1.2em' }}
                  >
                    {item.display}
                  </Button>
                ))}
              </SymbolGrid>

              <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
                Functions
              </Typography>
              <SymbolGrid>
                {functions.map((item, index) => (
                  <Button
                    key={index}
                    size="small"
                    onClick={() => handleFunctionClick(item.latex, item.display)}
                    sx={{ minWidth: 50, height: 40 }}
                  >
                    {item.display}
                  </Button>
                ))}
              </SymbolGrid>
            </>
          )}

          {/* Quick Templates */}
          <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
            Quick Templates
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            <Chip
              label="Fraction"
              size="small"
              clickable
              onClick={() => handleSymbolClick('\\frac{}{}', 'frac{}{}')}
            />
            <Chip
              label="Square Root"
              size="small"
              clickable
              onClick={() => handleSymbolClick('\\sqrt{}', 'sqrt{}')}
            />
            <Chip
              label="Exponent"
              size="small"
              clickable
              onClick={() => handleSymbolClick('^{}', '^{}')}
            />
            <Chip
              label="Subscript"
              size="small"
              clickable
              onClick={() => handleSymbolClick('_{}', '_{}')}
            />
          </Box>
        </MathSymbolsContainer>
      </Popover>
    </Box>
  );
};