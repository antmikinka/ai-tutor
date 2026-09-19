import React, { useCallback, useRef, useState } from 'react';
import { Box, Button, Chip, IconButton, Paper, Popover, Stack, TextField, Tooltip, Typography } from '@mui/material';
import { Functions, Send } from '@mui/icons-material';
import { styled } from '@mui/material/styles';

const Palette = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(1.5),
  width: 340,
}));

const Grid = styled(Box)(({ theme }) => ({
  display: 'grid',
  gridTemplateColumns: 'repeat(6, 1fr)',
  gap: theme.spacing(0.5),
}));

interface MathInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
  placeholder?: string;
}

/** `text` is inserted literally; `cursorOffset` moves the caret back inside e.g. `sqrt()`. */
interface Insert {
  label: string;
  text: string;
  cursorOffset?: number;
  hint?: string;
}

const OPERATORS: Insert[] = [
  { label: '+', text: '+' },
  { label: '−', text: '-' },
  { label: '×', text: '*' },
  { label: '÷', text: '/' },
  { label: '^', text: '^' },
  { label: '=', text: '=' },
  { label: '≠', text: '!=' },
  { label: '<', text: '<' },
  { label: '>', text: '>' },
  { label: '≤', text: '<=' },
  { label: '≥', text: '>=' },
  { label: '( )', text: '()', cursorOffset: 1 },
];

const CONSTANTS: Insert[] = [
  { label: 'π', text: 'pi' },
  { label: 'e', text: 'E', hint: "Euler's number" },
  { label: '∞', text: 'oo', hint: 'infinity' },
  { label: 'i', text: 'I', hint: 'imaginary unit' },
  { label: 'x²', text: '^2' },
  { label: 'x³', text: '^3' },
];

const FUNCTIONS: Insert[] = ['sqrt', 'sin', 'cos', 'tan', 'ln', 'log', 'exp', 'abs', 'asin', 'acos', 'atan', 'sinh'].map(
  (name) => ({ label: name, text: `${name}()`, cursorOffset: 1 }),
);

const TEMPLATES: Insert[] = [
  { label: 'Solve', text: 'solve ' },
  { label: 'Derivative', text: 'derivative of ' },
  { label: 'Integral', text: 'integrate ' },
  { label: 'Definite ∫', text: 'integrate  from 0 to 1', cursorOffset: 12 },
  { label: 'Limit', text: 'limit of  as x->0', cursorOffset: 8 },
  { label: 'Simplify', text: 'simplify ' },
  { label: 'Factor', text: 'factor ' },
  { label: 'Expand', text: 'expand ' },
];

export const MathInput: React.FC<MathInputProps> = ({
  value,
  onChange,
  onSend,
  disabled = false,
  placeholder = 'Type a math problem, e.g. solve x^2 - 5x + 6 = 0',
}) => {
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const insert = useCallback(
    ({ text, cursorOffset = 0 }: Insert) => {
      const el = inputRef.current;
      const start = el?.selectionStart ?? value.length;
      const end = el?.selectionEnd ?? value.length;
      const next = value.slice(0, start) + text + value.slice(end);
      onChange(next);
      const caret = start + text.length - cursorOffset;
      requestAnimationFrame(() => {
        el?.focus();
        el?.setSelectionRange(caret, caret);
      });
    },
    [value, onChange],
  );

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="flex-start">
        <TextField
          fullWidth
          size="small"
          multiline
          minRows={2}
          maxRows={5}
          placeholder={placeholder}
          value={value}
          disabled={disabled}
          inputRef={inputRef}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              if (canSend) onSend();
            }
          }}
          inputProps={{ 'aria-label': 'Math problem', spellCheck: false }}
          sx={{ '& textarea': { fontFamily: '"Cascadia Code", "Fira Code", Consolas, monospace' } }}
        />
        <Tooltip title="Symbols and templates">
          <IconButton onClick={(e) => setAnchorEl(e.currentTarget)} aria-label="Insert symbol" disabled={disabled}>
            <Functions />
          </IconButton>
        </Tooltip>
        <Tooltip title="Send (Enter)">
          <span>
            <Button onClick={onSend} variant="contained" disabled={!canSend} sx={{ minWidth: 0, px: 1.5, height: 40 }}>
              <Send fontSize="small" />
            </Button>
          </span>
        </Tooltip>
      </Stack>

      <Popover
        open={Boolean(anchorEl)}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        transformOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Palette elevation={0}>
          <Typography variant="overline">Templates</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
            {TEMPLATES.map((item) => (
              <Chip key={item.label} label={item.label} size="small" clickable onClick={() => insert(item)} />
            ))}
          </Box>

          <Typography variant="overline">Operators</Typography>
          <Grid sx={{ mb: 1 }}>
            {OPERATORS.map((item) => (
              <Button key={item.label} size="small" variant="outlined" onClick={() => insert(item)} sx={{ minWidth: 0 }}>
                {item.label}
              </Button>
            ))}
          </Grid>

          <Typography variant="overline">Constants</Typography>
          <Grid sx={{ mb: 1 }}>
            {CONSTANTS.map((item) => (
              <Tooltip key={item.label} title={item.hint || item.text}>
                <Button size="small" variant="outlined" onClick={() => insert(item)} sx={{ minWidth: 0 }}>
                  {item.label}
                </Button>
              </Tooltip>
            ))}
          </Grid>

          <Typography variant="overline">Functions</Typography>
          <Grid>
            {FUNCTIONS.map((item) => (
              <Button key={item.label} size="small" variant="text" onClick={() => insert(item)} sx={{ minWidth: 0, textTransform: 'none' }}>
                {item.label}
              </Button>
            ))}
          </Grid>
        </Palette>
      </Popover>
    </Box>
  );
};
