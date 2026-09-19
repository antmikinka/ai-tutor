import React from 'react';
import { Box, Button, Chip, List, ListItemButton, ListItemText, Stack, Typography } from '@mui/material';
import { DeleteOutline, Draw } from '@mui/icons-material';
import type { PracticeHistory as HistoryPayload, PracticeHistoryItem } from '../types/MathTypes';

interface Props {
  history: HistoryPayload | null;
  activeId: string | null;
  onOpen: (id: string) => void;
  onWhiteboard: (id: string) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
}

const status = (item: PracticeHistoryItem) => {
  if (item.solved) return { label: 'Solved', color: 'success' as const };
  if (item.revealed) return { label: 'Revealed', color: 'warning' as const };
  if (item.attempts > 0) return { label: `${item.attempts} try`, color: 'default' as const };
  return { label: 'Open', color: 'default' as const };
};

export const PracticeHistory: React.FC<Props> = ({ history, activeId, onOpen, onWhiteboard, onDelete, onClear }) => {
  const items = history?.items ?? [];
  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
        <Typography variant="subtitle2" sx={{ flex: 1 }}>
          History
        </Typography>
        {items.length > 0 && (
          <Button size="small" color="inherit" onClick={onClear} sx={{ textTransform: 'none' }}>
            Clear
          </Button>
        )}
      </Stack>
      {items.length === 0 ? (
        <Typography variant="caption" color="text.secondary">
          Problems you generate are saved here and on the whiteboard, so you can come back to any of them.
        </Typography>
      ) : (
        <List dense disablePadding>
          {items.map((item) => {
            const chip = status(item);
            return (
              <ListItemButton key={item.id} selected={item.id === activeId} onClick={() => onOpen(item.id)} alignItems="flex-start" sx={{ borderRadius: 1, mb: 0.5 }}>
                <ListItemText
                  primary={
                    <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap" rowGap={0.5}>
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        {item.family_label}
                      </Typography>
                      <Chip size="small" label={chip.label} color={chip.color} variant={chip.color === 'default' ? 'outlined' : 'filled'} />
                      {item.has_whiteboard && <Chip size="small" variant="outlined" label="board" />}
                    </Stack>
                  }
                  secondary={item.preview}
                  secondaryTypographyProps={{ noWrap: true }}
                />
                <Stack direction="row" onClick={(e) => e.stopPropagation()}>
                  <Button size="small" startIcon={<Draw />} onClick={() => onWhiteboard(item.id)} sx={{ textTransform: 'none', minWidth: 0 }}>
                    Board
                  </Button>
                  <Button size="small" color="inherit" onClick={() => onDelete(item.id)} sx={{ minWidth: 0, px: 0.5 }} aria-label="Delete problem">
                    <DeleteOutline fontSize="small" />
                  </Button>
                </Stack>
              </ListItemButton>
            );
          })}
        </List>
      )}
    </Box>
  );
};
