import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  LinearProgress,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { Article, DeleteOutline, ExpandLess, ExpandMore, NoteAdd, PictureAsPdf, Search, UploadFile } from '@mui/icons-material';
import { ApiError, apiFetch, apiJson, apiUpload } from '../lib/backend';
import type { KnowledgeDocument, KnowledgeHit, KnowledgeStatus } from '../types/MathTypes';

interface CourseMaterialPanelProps {
  /** Selected document ids used to restrict practice generation; empty = all. */
  selectedIds: string[];
  onSelectionChange: (ids: string[]) => void;
  /** Called whenever the document list changes so parents can refresh counts. */
  onDocumentsChange?: (docs: KnowledgeDocument[]) => void;
  dense?: boolean;
}

const formatBytes = (n: number) => (n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`);

const describe = (error: unknown) => (error instanceof ApiError ? error.message : error instanceof Error ? error.message : String(error));

/**
 * Upload / paste course material into the Chroma knowledge base, pick which
 * documents practice problems should draw on, and sanity-check retrieval.
 */
export const CourseMaterialPanel: React.FC<CourseMaterialPanelProps> = ({ selectedIds, onSelectionChange, onDocumentsChange, dense }) => {
  const [status, setStatus] = useState<KnowledgeStatus | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteTitle, setPasteTitle] = useState('');
  const [pasteText, setPasteText] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<KnowledgeHit[] | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([
        apiFetch<KnowledgeStatus>('/api/knowledge/status'),
        apiFetch<{ documents: KnowledgeDocument[] }>('/api/knowledge/documents').catch(() => ({ documents: [] })),
      ]);
      setStatus(s);
      setDocuments(d.documents);
      onDocumentsChange?.(d.documents);
      setError(s.available ? null : s.error || 'Knowledge base is unavailable.');
    } catch (err) {
      setError(describe(err));
    } finally {
      setLoading(false);
    }
  }, [onDocumentsChange]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const uploadFiles = async (files: FileList | File[]) => {
    const list = Array.from(files);
    if (!list.length) return;
    setError(null);
    for (const file of list) {
      setBusy(`Indexing ${file.name}…`);
      try {
        const form = new FormData();
        form.append('file', file);
        await apiUpload<KnowledgeDocument>('/api/knowledge/documents/upload', form);
      } catch (err) {
        setError(`${file.name}: ${describe(err)}`);
      }
    }
    setBusy(null);
    await refresh();
  };

  const submitPaste = async () => {
    if (!pasteText.trim()) return;
    setBusy('Indexing…');
    setError(null);
    try {
      await apiJson<KnowledgeDocument>('/api/knowledge/documents/text', 'POST', { title: pasteTitle.trim() || 'Pasted notes', text: pasteText });
      setPasteOpen(false);
      setPasteTitle('');
      setPasteText('');
      await refresh();
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(null);
    }
  };

  const remove = async (doc: KnowledgeDocument) => {
    setBusy(`Removing ${doc.title}…`);
    try {
      await apiJson(`/api/knowledge/documents/${doc.id}`, 'DELETE');
      onSelectionChange(selectedIds.filter((id) => id !== doc.id));
      await refresh();
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(null);
    }
  };

  const runSearch = async () => {
    if (!query.trim()) return;
    setBusy('Searching…');
    try {
      const result = await apiJson<{ results: KnowledgeHit[] }>('/api/knowledge/search', 'POST', { query, k: 4 });
      setHits(result.results);
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(null);
    }
  };

  const toggle = (id: string) => onSelectionChange(selectedIds.includes(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id]);

  const accept = status?.supported_extensions.join(',') || '.txt,.md,.pdf';

  return (
    <Box
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        void uploadFiles(e.dataTransfer.files);
      }}
      sx={{
        border: 1,
        borderColor: dragging ? 'primary.main' : 'divider',
        borderStyle: dragging ? 'dashed' : 'solid',
        borderRadius: 1,
        p: dense ? 1.5 : 2,
        bgcolor: dragging ? 'action.hover' : 'transparent',
        transition: 'border-color 120ms, background-color 120ms',
      }}
    >
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Box>
          <Typography variant="subtitle1">Course material</Typography>
          {status && (
            <Typography variant="caption" color="text.secondary">
              {status.documents} document{status.documents === 1 ? '' : 's'} · {status.chunks} passages ·{' '}
              {status.backend === 'chroma' ? 'Chroma' : 'local index'} · {status.embedding === 'minilm' ? 'MiniLM embeddings' : 'offline hashing embeddings'}
            </Typography>
          )}
        </Box>
        <Stack direction="row" spacing={0.5}>
          <Tooltip title="Upload PDF, Markdown or text">
            <span>
              <IconButton size="small" onClick={() => fileRef.current?.click()} disabled={!status?.available || Boolean(busy)} aria-label="Upload course material">
                <UploadFile fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Paste notes">
            <span>
              <IconButton size="small" onClick={() => setPasteOpen(true)} disabled={!status?.available || Boolean(busy)} aria-label="Paste notes">
                <NoteAdd fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Test what the tutor retrieves for a question">
            <span>
              <IconButton size="small" onClick={() => setSearchOpen((o) => !o)} disabled={!documents.length} aria-label="Search material" color={searchOpen ? 'primary' : 'default'}>
                <Search fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      </Stack>
      <input ref={fileRef} type="file" hidden multiple accept={accept} onChange={(e) => e.target.files && void uploadFiles(e.target.files).then(() => (e.target.value = ''))} />

      {busy && (
        <Box sx={{ mb: 1 }}>
          <LinearProgress />
          <Typography variant="caption" color="text.secondary">
            {busy}
          </Typography>
        </Box>
      )}
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 1 }}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box display="flex" justifyContent="center" py={2}>
          <CircularProgress size={20} />
        </Box>
      ) : documents.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Drop lecture notes, a textbook chapter (PDF) or paste your own summary. Practice problems will be built from what you upload.
          </Typography>
          <Button size="small" startIcon={<UploadFile />} sx={{ mt: 1 }} onClick={() => fileRef.current?.click()} disabled={!status?.available}>
            Add material
          </Button>
        </Box>
      ) : (
        <>
          <Typography variant="caption" color="text.secondary">
            {selectedIds.length ? `Practising from ${selectedIds.length} selected document${selectedIds.length === 1 ? '' : 's'}` : 'Practising from all documents'}
          </Typography>
          <List dense disablePadding sx={{ maxHeight: dense ? 220 : 320, overflow: 'auto' }}>
            {documents.map((doc) => (
              <ListItem
                key={doc.id}
                disablePadding
                secondaryAction={
                  <Tooltip title="Remove">
                    <IconButton edge="end" size="small" onClick={() => void remove(doc)} aria-label={`Remove ${doc.title}`}>
                      <DeleteOutline fontSize="small" />
                    </IconButton>
                  </Tooltip>
                }
              >
                <ListItemButton dense onClick={() => toggle(doc.id)} sx={{ pr: 6 }}>
                  <ListItemIcon sx={{ minWidth: 32 }}>
                    <Checkbox edge="start" size="small" checked={selectedIds.includes(doc.id)} tabIndex={-1} disableRipple />
                  </ListItemIcon>
                  <ListItemIcon sx={{ minWidth: 28 }}>{doc.source.toLowerCase().endsWith('.pdf') ? <PictureAsPdf fontSize="small" /> : <Article fontSize="small" />}</ListItemIcon>
                  <ListItemText
                    primary={doc.title}
                    secondary={`${doc.chunks} passages · ${formatBytes(doc.chars)}${doc.pages ? ` · ${doc.pages} pages` : ''}${doc.tags.length ? ` · ${doc.tags.join(', ')}` : ''}`}
                    primaryTypographyProps={{ noWrap: true }}
                    secondaryTypographyProps={{ noWrap: true }}
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </>
      )}

      <Collapse in={searchOpen}>
        <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
          <TextField
            size="small"
            fullWidth
            placeholder="e.g. how do I set up a proportion?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void runSearch()}
          />
          <Button size="small" variant="outlined" onClick={() => void runSearch()} disabled={!query.trim()}>
            Find
          </Button>
        </Stack>
        {hits && (
          <Stack spacing={1} sx={{ mt: 1 }}>
            {hits.length === 0 && (
              <Typography variant="caption" color="text.secondary">
                Nothing relevant found.
              </Typography>
            )}
            {hits.map((hit) => (
              <HitCard key={hit.chunk_id} hit={hit} />
            ))}
          </Stack>
        )}
      </Collapse>

      <Dialog open={pasteOpen} onClose={() => setPasteOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Paste notes</DialogTitle>
        <DialogContent>
          <TextField autoFocus fullWidth size="small" label="Title" value={pasteTitle} onChange={(e) => setPasteTitle(e.target.value)} sx={{ mb: 1.5, mt: 0.5 }} />
          <TextField
            fullWidth
            multiline
            minRows={8}
            maxRows={16}
            label="Text"
            placeholder="Paste a chapter summary, definitions, worked examples…"
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPasteOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => void submitPaste()} disabled={!pasteText.trim() || Boolean(busy)}>
            Add to material
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

const HitCard: React.FC<{ hit: KnowledgeHit }> = ({ hit }) => {
  const [open, setOpen] = useState(false);
  return (
    <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1 }}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Chip size="small" label={`${Math.round(hit.score * 100)}%`} color={hit.score > 0.5 ? 'success' : 'default'} />
        <Typography variant="body2" sx={{ flex: 1 }} noWrap>
          {hit.title}
          {hit.page ? ` · p.${hit.page}` : ''}
        </Typography>
        <IconButton size="small" onClick={() => setOpen((o) => !o)} aria-label="Toggle passage">
          {open ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
        </IconButton>
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', whiteSpace: 'pre-wrap' }}>
        {open ? hit.text : `${hit.text.slice(0, 160)}${hit.text.length > 160 ? '…' : ''}`}
      </Typography>
    </Box>
  );
};
