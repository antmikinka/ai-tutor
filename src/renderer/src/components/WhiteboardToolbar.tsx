import React from 'react';
import { Box, Divider, IconButton, Menu, MenuItem, ListItemIcon, ListItemText, Stack, ToggleButton, ToggleButtonGroup, Tooltip } from '@mui/material';
import { alpha, styled } from '@mui/material/styles';
import {
  AutoFixHigh,
  Brush,
  Check,
  CropSquare,
  Delete,
  DeleteOutline,
  Grid4x4,
  GridOff,
  Highlight,
  NearMe,
  PanoramaFishEye,
  Redo,
  Remove,
  TextFields,
  Undo,
} from '@mui/icons-material';
import type { DrawingTool } from './DrawingCanvas';
import type { WhiteboardGrid } from '../types/MathTypes';

export const TOOL_HOTKEYS: Record<DrawingTool, string> = {
  pen: 'P',
  eraser: 'E',
  select: 'V',
  text: 'T',
  line: 'L',
  rect: 'R',
  ellipse: 'O',
};

export const SWATCHES = ['#1a237e', '#d32f2f', '#2e7d32', '#f57c00', '#6a1b9a', '#212121'];
export const WIDTH_PRESETS = [2, 4, 7, 12];

const Swatch = styled('button', { shouldForwardProp: (p) => p !== 'selected' && p !== 'swatch' })<{ selected: boolean; swatch: string }>(
  ({ theme, selected, swatch }) => ({
    width: 22,
    height: 22,
    borderRadius: '50%',
    border: `2px solid ${selected ? theme.palette.primary.main : alpha(theme.palette.text.primary, 0.15)}`,
    background: swatch,
    cursor: 'pointer',
    padding: 0,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
    boxShadow: selected ? `0 0 0 2px ${alpha(theme.palette.primary.main, 0.25)}` : 'none',
    transition: 'transform 120ms',
    '&:hover': { transform: 'scale(1.12)' },
  }),
);

const WidthDot = styled('button', { shouldForwardProp: (p) => p !== 'selected' })<{ selected: boolean }>(({ theme, selected }) => ({
  width: 26,
  height: 26,
  borderRadius: 6,
  border: `1px solid ${selected ? theme.palette.primary.main : alpha(theme.palette.text.primary, 0.15)}`,
  background: selected ? alpha(theme.palette.primary.main, 0.12) : 'transparent',
  cursor: 'pointer',
  padding: 0,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  '&:hover': { background: alpha(theme.palette.primary.main, 0.08) },
}));

interface WhiteboardToolbarProps {
  tool: DrawingTool;
  onToolChange: (tool: DrawingTool) => void;
  color: string;
  onColorChange: (color: string) => void;
  lineWidth: number;
  onLineWidthChange: (width: number) => void;
  grid: WhiteboardGrid;
  onGridChange: (grid: WhiteboardGrid) => void;
  canUndo: boolean;
  canRedo: boolean;
  canvasEmpty: boolean;
  hasSelection: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onDeleteSelection: () => void;
  onClear: () => void;
  /** Extra action buttons rendered at the end of the row. */
  children?: React.ReactNode;
}

const tools: Array<{ value: DrawingTool; label: string; icon: React.ReactNode }> = [
  { value: 'pen', label: 'Pen', icon: <Brush fontSize="small" /> },
  { value: 'eraser', label: 'Eraser — removes any stroke you touch', icon: <AutoFixHigh fontSize="small" /> },
  { value: 'select', label: 'Select — move, resize or delete objects', icon: <NearMe fontSize="small" /> },
  { value: 'text', label: 'Text — click to type', icon: <TextFields fontSize="small" /> },
  { value: 'line', label: 'Line', icon: <Remove fontSize="small" /> },
  { value: 'rect', label: 'Rectangle', icon: <CropSquare fontSize="small" /> },
  { value: 'ellipse', label: 'Ellipse', icon: <PanoramaFishEye fontSize="small" /> },
];

export const WhiteboardToolbar: React.FC<WhiteboardToolbarProps> = ({
  tool,
  onToolChange,
  color,
  onColorChange,
  lineWidth,
  onLineWidthChange,
  grid,
  onGridChange,
  canUndo,
  canRedo,
  canvasEmpty,
  hasSelection,
  onUndo,
  onRedo,
  onDeleteSelection,
  onClear,
  children,
}) => {
  const [gridAnchor, setGridAnchor] = React.useState<null | HTMLElement>(null);
  const customColor = !SWATCHES.includes(color.toLowerCase());

  return (
    <Stack direction="row" alignItems="center" flexWrap="wrap" rowGap={1} columnGap={1} sx={{ mb: 1.5 }}>
      <ToggleButtonGroup size="small" exclusive value={tool} onChange={(_, value: DrawingTool | null) => value && onToolChange(value)} aria-label="Drawing tool">
        {tools.map((t) => (
          <ToggleButton key={t.value} value={t.value} aria-label={t.label} sx={{ px: 1 }}>
            <Tooltip title={`${t.label} (${TOOL_HOTKEYS[t.value]})`} enterDelay={400}>
              <span style={{ display: 'inline-flex' }}>{t.icon}</span>
            </Tooltip>
          </ToggleButton>
        ))}
      </ToggleButtonGroup>

      <Divider orientation="vertical" flexItem />

      <Stack direction="row" spacing={0.75} alignItems="center" aria-label="Stroke colour">
        {SWATCHES.map((swatch) => (
          <Tooltip key={swatch} title={swatch} enterDelay={600}>
            <Swatch type="button" swatch={swatch} selected={swatch === color.toLowerCase()} onClick={() => onColorChange(swatch)} aria-label={`Colour ${swatch}`}>
              {swatch === color.toLowerCase() && <Check sx={{ fontSize: 14 }} />}
            </Swatch>
          </Tooltip>
        ))}
        <Tooltip title="Custom colour">
          <Box
            component="label"
            sx={{
              width: 22,
              height: 22,
              borderRadius: '50%',
              cursor: 'pointer',
              overflow: 'hidden',
              border: (t) => `2px solid ${customColor ? t.palette.primary.main : alpha(t.palette.text.primary, 0.15)}`,
              background: customColor ? color : 'conic-gradient(#f44336, #ffeb3b, #4caf50, #2196f3, #9c27b0, #f44336)',
              display: 'inline-block',
            }}
          >
            <input type="color" value={color} aria-label="Custom colour" onChange={(e) => onColorChange(e.target.value)} style={{ opacity: 0, width: 0, height: 0, border: 0 }} />
          </Box>
        </Tooltip>
      </Stack>

      <Divider orientation="vertical" flexItem />

      <Stack direction="row" spacing={0.5} alignItems="center" aria-label="Stroke width">
        {WIDTH_PRESETS.map((w) => (
          <Tooltip key={w} title={`${w}px`} enterDelay={600}>
            <WidthDot type="button" selected={w === lineWidth} onClick={() => onLineWidthChange(w)} aria-label={`Width ${w}`}>
              <Box sx={{ width: Math.min(w + 4, 18), height: Math.min(w + 4, 18), borderRadius: '50%', bgcolor: color }} />
            </WidthDot>
          </Tooltip>
        ))}
      </Stack>

      <Divider orientation="vertical" flexItem />

      <Tooltip title="Undo (Ctrl+Z)">
        <span>
          <IconButton size="small" onClick={onUndo} disabled={!canUndo} aria-label="Undo">
            <Undo fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Redo (Ctrl+Y)">
        <span>
          <IconButton size="small" onClick={onRedo} disabled={!canRedo} aria-label="Redo">
            <Redo fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Delete selection (Del)">
        <span>
          <IconButton size="small" onClick={onDeleteSelection} disabled={!hasSelection} aria-label="Delete selection">
            <DeleteOutline fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Clear whiteboard">
        <span>
          <IconButton size="small" onClick={onClear} disabled={canvasEmpty} aria-label="Clear whiteboard">
            <Delete fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Background grid">
        <IconButton size="small" onClick={(e) => setGridAnchor(e.currentTarget)} aria-label="Background grid" color={grid === 'none' ? 'default' : 'primary'}>
          {grid === 'none' ? <GridOff fontSize="small" /> : <Grid4x4 fontSize="small" />}
        </IconButton>
      </Tooltip>
      <Menu anchorEl={gridAnchor} open={Boolean(gridAnchor)} onClose={() => setGridAnchor(null)}>
        {(
          [
            ['none', 'Plain', <GridOff fontSize="small" />],
            ['dots', 'Dots', <Highlight fontSize="small" />],
            ['lines', 'Squares', <Grid4x4 fontSize="small" />],
          ] as Array<[WhiteboardGrid, string, React.ReactNode]>
        ).map(([value, label, icon]) => (
          <MenuItem
            key={value}
            selected={grid === value}
            onClick={() => {
              onGridChange(value);
              setGridAnchor(null);
            }}
          >
            <ListItemIcon>{icon}</ListItemIcon>
            <ListItemText>{label}</ListItemText>
          </MenuItem>
        ))}
      </Menu>

      {children && (
        <>
          <Box sx={{ flex: 1 }} />
          {children}
        </>
      )}
    </Stack>
  );
};
