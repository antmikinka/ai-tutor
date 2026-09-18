import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Box, Button, IconButton, Menu, MenuItem, Paper, Stack, ToggleButton, Tooltip, Typography } from '@mui/material';
import { CheckCircleOutline, FactCheck, Image as ImageIcon, Mic, Save, School, Stop } from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import { DrawingCanvas, DrawingCanvasRef, DrawingTool } from '../components/DrawingCanvas';
import { TOOL_HOTKEYS, WhiteboardToolbar } from '../components/WhiteboardToolbar';
import { ChatInterface } from '../components/ChatInterface';
import { MathInput } from '../components/MathInput';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import { useSettingsContext } from '../contexts/SettingsContext';
import { WebSocketRequestError } from '../hooks/useWebSocket';
import { ApiError, apiFetch } from '../lib/backend';
import type { ChatMessage, ChatMessageInput, UserInputSource } from '../types/MathTypes';
import type { BackendSolution, BackendVerification, DrawingAnalysis } from '../types/protocol';

const Layout = styled(Box)(({ theme }) => ({
  display: 'flex',
  height: '100%',
  gap: theme.spacing(2),
  [theme.breakpoints.down('md')]: { flexDirection: 'column' },
}));

const CanvasPane = styled(Paper)(({ theme }) => ({
  flex: 1,
  minWidth: 0,
  minHeight: 320,
  display: 'flex',
  flexDirection: 'column',
  padding: theme.spacing(2),
}));

const ChatPane = styled(Paper)(({ theme }) => ({
  width: 420,
  minHeight: 0,
  display: 'flex',
  flexDirection: 'column',
  padding: theme.spacing(2),
  [theme.breakpoints.down('lg')]: { width: 360 },
  [theme.breakpoints.down('md')]: { width: '100%', flex: 1 },
}));

/** Router state accepted by this page (sent from the Practice page). */
export interface WhiteboardHandoff {
  whiteboardText?: string;
  prefillInput?: string;
}

const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
const now = () => new Date().toISOString();

const isTypingTarget = (target: EventTarget | null) => {
  const el = target as HTMLElement | null;
  return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable);
};

const HOTKEY_TO_TOOL = Object.fromEntries(Object.entries(TOOL_HOTKEYS).map(([tool, key]) => [key.toLowerCase(), tool])) as Record<string, DrawingTool>;

const describeError = (error: unknown): { text: string; code?: string } => {
  if (error instanceof WebSocketRequestError) return { text: error.message, code: error.code };
  if (error instanceof ApiError) return { text: error.message, code: `HTTP ${error.status}` };
  if (error instanceof Error) return { text: error.message };
  return { text: String(error) };
};

export const MathTutorPage: React.FC = () => {
  const { connectionStatus, capabilities, request, subscribe } = useWebSocketContext();
  const { settings, updateWhiteboardSettings } = useSettingsContext();
  const navigate = useNavigate();
  const location = useLocation();
  const { whiteboardSettings } = settings;

  const [tool, setTool] = useState<DrawingTool>('pen');
  const color = whiteboardSettings.penColor;
  const lineWidth = whiteboardSettings.penWidth;
  const setColor = (penColor: string) => void updateWhiteboardSettings({ penColor });
  const setLineWidth = (penWidth: number) => void updateWhiteboardSettings({ penWidth });
  const [history, setHistory] = useState({ canUndo: false, canRedo: false });
  const [canvasEmpty, setCanvasEmpty] = useState(true);
  const [hasSelection, setHasSelection] = useState(false);

  const [input, setInput] = useState('');
  const [verifyMode, setVerifyMode] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [exportAnchor, setExportAnchor] = useState<null | HTMLElement>(null);
  const [recording, setRecording] = useState(false);

  const canvasRef = useRef<DrawingCanvasRef>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const lastSolution = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const m = messages[i];
      if (m.kind === 'solution' && m.solution.confidence > 0) return m.solution;
    }
    return null;
  }, [messages]);

  const push = useCallback((message: ChatMessageInput) => {
    setMessages((prev) => [...prev, { ...message, id: newId(), timestamp: now() } as ChatMessage]);
  }, []);

  const pushError = useCallback((error: unknown) => push({ kind: 'error', ...describeError(error) }), [push]);

  // ---- backend calls -------------------------------------------------

  const solve = useCallback(
    async (problem: string, source: UserInputSource = 'text') => {
      const content = problem.trim();
      if (!content) return;
      push({ kind: 'user', text: content, source });
      setIsProcessing(true);
      try {
        const metadata = {
          enable_tts: settings.audioSettings.enableTextToSpeech,
          source,
          enable_step_by_step: settings.displaySettings.showStepByStep,
          enable_thinking: settings.modelSettings.enableThinking,
          temperature: settings.modelSettings.temperature,
          max_tokens: settings.modelSettings.maxTokens,
        };
        let solution: BackendSolution;
        if (connectionStatus === 'connected') {
          const reply = await request({ type: 'math_input', content, metadata }, 'math_solution');
          solution = reply.solution;
        } else {
          // REST fallback keeps the app usable while the socket reconnects.
          solution = await apiFetch<BackendSolution>('/api/math/solve', {
            method: 'POST',
            body: JSON.stringify({ problem: content, context: metadata }),
          });
        }
        push({ kind: 'solution', solution });
      } catch (error) {
        pushError(error);
      } finally {
        setIsProcessing(false);
      }
    },
    [
      connectionStatus,
      push,
      pushError,
      request,
      settings.audioSettings.enableTextToSpeech,
      settings.displaySettings.showStepByStep,
      settings.modelSettings.enableThinking,
      settings.modelSettings.temperature,
      settings.modelSettings.maxTokens,
    ],
  );

  const verify = useCallback(
    async (problem: string, proposed: string) => {
      push({ kind: 'user', text: `Is "${proposed}" correct for ${problem}?`, source: 'text' });
      setIsProcessing(true);
      try {
        let verdict: BackendVerification;
        if (connectionStatus === 'connected') {
          verdict = (await request({ type: 'verify', problem, solution: proposed }, 'verification')).data;
        } else {
          verdict = await apiFetch<BackendVerification>('/api/math/verify', {
            method: 'POST',
            body: JSON.stringify({ problem, solution: proposed }),
          });
        }
        push({ kind: 'verification', problem, proposed, verdict });
      } catch (error) {
        pushError(error);
      } finally {
        setIsProcessing(false);
      }
    },
    [connectionStatus, push, pushError, request],
  );

  const analyzeImage = useCallback(
    async (dataUrl: string, source: 'drawing' | 'image') => {
      push({ kind: 'user', text: source === 'drawing' ? 'Recognize what I drew' : 'Recognize this image', source });
      setIsProcessing(true);
      try {
        let analysis: DrawingAnalysis;
        if (connectionStatus === 'connected') {
          analysis = (await request({ type: 'drawing', data: dataUrl }, 'drawing_analysis', 60_000)).data;
        } else {
          analysis = await apiFetch<DrawingAnalysis>('/api/math/analyze-drawing', {
            method: 'POST',
            body: JSON.stringify({ drawing_data: dataUrl }),
          });
        }
        push({ kind: 'drawing', analysis });
        if (analysis.available && analysis.recognized_text) {
          setInput(analysis.recognized_text);
        }
      } catch (error) {
        pushError(error);
      } finally {
        setIsProcessing(false);
      }
    },
    [connectionStatus, push, pushError, request],
  );

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || isProcessing) return;
    setInput('');
    if (verifyMode && lastSolution) {
      setVerifyMode(false);
      void verify(lastSolution.problem, text);
    } else {
      void solve(text, 'text');
    }
  }, [input, isProcessing, lastSolution, solve, verify, verifyMode]);

  // ---- voice ---------------------------------------------------------

  const stopRecording = useCallback(() => {
    recorderRef.current?.stop();
  }, []);

  const startRecording = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      push({ kind: 'error', text: 'Microphone access is not available in this environment.' });
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        recorderRef.current = null;
        setRecording(false);
        const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
        const base64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
          reader.onerror = () => reject(reader.error);
          reader.readAsDataURL(blob);
        });
        if (!base64) return;
        setIsProcessing(true);
        try {
          const reply = await request(
            { type: 'audio', data: base64, language: settings.audioSettings.sttLanguage, format: 'webm' },
            'audio_transcription',
            60_000,
          );
          if (reply.available && reply.text) {
            await solve(reply.text, 'voice');
          } else {
            push({ kind: 'info', text: reply.message || 'Speech recognition is not available. Load a speech model in Settings.' });
          }
        } catch (error) {
          pushError(error);
        } finally {
          setIsProcessing(false);
        }
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch (error) {
      pushError(error);
    }
  }, [push, pushError, request, settings.audioSettings.sttLanguage, solve]);

  const toggleRecording = useCallback(() => {
    if (recording) stopRecording();
    else void startRecording();
  }, [recording, startRecording, stopRecording]);

  // ---- TTS playback (server pushes audio_response after math_solution) ---

  useEffect(
    () =>
      subscribe('audio_response', (message) => {
        const { audio_data, format } = message.data;
        if (!audio_data) return;
        const audio = new Audio(`data:audio/${format || 'wav'};base64,${audio_data}`);
        audio.volume = settings.audioSettings.volume;
        audio.play().catch((error) => console.warn('Audio playback failed:', error));
      }),
    [subscribe, settings.audioSettings.volume],
  );

  // ---- image upload ----------------------------------------------------

  const handleImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) {
      push({ kind: 'error', text: 'Image is larger than 8 MB.' });
      return;
    }
    const reader = new FileReader();
    reader.onload = () => void analyzeImage(String(reader.result), 'image');
    reader.onerror = () => push({ kind: 'error', text: 'Could not read that file.' });
    reader.readAsDataURL(file);
  };

  // ---- export ----------------------------------------------------------

  const download = async (filename: string, data: string, encoding: 'utf8' | 'base64', mime: string) => {
    if (window.electronAPI?.saveFile) {
      await window.electronAPI.saveFile({ defaultPath: filename, data, encoding });
      return;
    }
    const href = encoding === 'base64' ? `data:${mime};base64,${data}` : URL.createObjectURL(new Blob([data], { type: mime }));
    const a = document.createElement('a');
    a.href = href;
    a.download = filename;
    a.click();
    if (encoding !== 'base64') URL.revokeObjectURL(href);
  };

  const transcript = () =>
    messages
      .map((m) => {
        switch (m.kind) {
          case 'user':
            return `You: ${m.text}`;
          case 'solution':
            return [`Tutor (${m.solution.problem_type}): ${m.solution.solution}`, ...m.solution.steps.map((s, i) => `  ${i + 1}. ${s}`)].join('\n');
          case 'verification':
            return `Check: ${m.verdict.feedback}`;
          case 'drawing':
            return `Drawing: ${m.analysis.available ? m.analysis.recognized_text : m.analysis.message}`;
          default:
            return `${m.kind}: ${m.text}`;
        }
      })
      .join('\n\n');

  const exportAs = async (format: 'txt' | 'png' | 'pdf') => {
    setExportAnchor(null);
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    try {
      if (format === 'txt') {
        await download(`math-tutor-${stamp}.txt`, transcript(), 'utf8', 'text/plain');
      } else if (format === 'png') {
        const dataUrl = canvasRef.current?.toDataURL({ multiplier: 2 }) || '';
        await download(`math-tutor-canvas-${stamp}.png`, dataUrl.split(',')[1] || '', 'base64', 'image/png');
      } else {
        const { jsPDF } = await import('jspdf');
        const doc = new jsPDF({ unit: 'pt', format: 'a4' });
        const pageWidth = doc.internal.pageSize.getWidth();
        const margin = 40;
        let y = margin;
        doc.setFontSize(16);
        doc.text('AI Math Tutor session', margin, y);
        y += 24;
        if (canvasRef.current && !canvasRef.current.isEmpty()) {
          const canvas = canvasRef.current.getCanvas();
          const ratio = canvas ? canvas.getHeight() / canvas.getWidth() : 0.6;
          const imgWidth = pageWidth - margin * 2;
          const imgHeight = imgWidth * ratio;
          doc.addImage(canvasRef.current.toDataURL(), 'PNG', margin, y, imgWidth, imgHeight);
          y += imgHeight + 16;
        }
        doc.setFontSize(10);
        const lines = doc.splitTextToSize(transcript(), pageWidth - margin * 2) as string[];
        lines.forEach((line) => {
          if (y > doc.internal.pageSize.getHeight() - margin) {
            doc.addPage();
            y = margin;
          }
          doc.text(line, margin, y);
          y += 13;
        });
        await download(`math-tutor-${stamp}.pdf`, doc.output('datauristring').split(',')[1], 'base64', 'application/pdf');
      }
    } catch (error) {
      pushError(error);
    }
  };

  // ---- keyboard shortcuts ---------------------------------------------

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      const key = e.key.toLowerCase();
      const typing = isTypingTarget(e.target);
      if (mod) {
        if (key === 's') {
          e.preventDefault();
          void exportAs('txt');
        } else if (key === 'm') {
          e.preventDefault();
          toggleRecording();
        } else if (!typing) {
          if (key === 'z' && !e.shiftKey) {
            e.preventDefault();
            canvasRef.current?.undo();
          } else if (key === 'y' || (key === 'z' && e.shiftKey)) {
            e.preventDefault();
            canvasRef.current?.redo();
          }
        }
        return;
      }
      if (typing || e.altKey) return;
      // Single-key tool switching and deletion, only when focus is not in a text field
      // (fabric's IText editor uses a hidden textarea, so typing on the canvas is safe too).
      if ((e.key === 'Delete' || e.key === 'Backspace') && canvasRef.current?.deleteSelection()) {
        e.preventDefault();
        return;
      }
      if (e.key === 'Escape') {
        canvasRef.current?.getCanvas()?.discardActiveObject().requestRenderAll();
        return;
      }
      const nextTool = HOTKEY_TO_TOOL[key];
      if (nextTool) {
        e.preventDefault();
        setTool(nextTool);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // exportAs/toggleRecording are stable enough per render; re-binding on every change is cheap.
  });

  useEffect(() => () => recorderRef.current?.stop(), []);

  // ---- hand-off from the Practice page ---------------------------------

  useEffect(() => {
    const state = location.state as WhiteboardHandoff | null;
    if (!state || (!state.whiteboardText && !state.prefillInput)) return;
    if (state.whiteboardText) {
      // The canvas mounts in the same commit; defer one frame so it has its size.
      const text = state.whiteboardText;
      requestAnimationFrame(() => canvasRef.current?.addText(text));
      setTool('pen');
    }
    if (state.prefillInput) setInput(state.prefillInput);
    navigate(location.pathname, { replace: true, state: null });
  }, [location.pathname, location.state, navigate]);

  const speechAvailable = Boolean(capabilities?.speech);
  const recognitionAvailable = Boolean(capabilities?.drawing_recognition);
  const busy = isProcessing || connectionStatus === 'connecting';

  return (
    <Layout>
      <CanvasPane elevation={1}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="h6">Whiteboard</Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            {whiteboardSettings.showShortcutHints && (
              <Typography variant="caption" color="text.secondary" sx={{ display: { xs: 'none', lg: 'block' } }}>
                P/E/V/T/L/R/O tools · Del delete · Ctrl+Z/Y undo/redo · Ctrl+S export · Ctrl+M mic
              </Typography>
            )}
            <Button size="small" startIcon={<School />} onClick={() => navigate('/practice')} sx={{ textTransform: 'none' }}>
              Practice
            </Button>
          </Stack>
        </Stack>

        <WhiteboardToolbar
          tool={tool}
          onToolChange={setTool}
          color={color}
          onColorChange={setColor}
          lineWidth={lineWidth}
          onLineWidthChange={setLineWidth}
          grid={whiteboardSettings.grid}
          onGridChange={(grid) => void updateWhiteboardSettings({ grid })}
          canUndo={history.canUndo}
          canRedo={history.canRedo}
          canvasEmpty={canvasEmpty}
          hasSelection={hasSelection}
          onUndo={() => canvasRef.current?.undo()}
          onRedo={() => canvasRef.current?.redo()}
          onDeleteSelection={() => canvasRef.current?.deleteSelection()}
          onClear={() => canvasRef.current?.clear()}
        >
          <Tooltip title={recognitionAvailable ? 'Recognize the drawing' : 'Handwriting recognition needs the Qwen3-Omni model (see Settings). Sends the canvas to the backend for basic analysis.'}>
            <span>
              <IconButton
                size="small"
                color={recognitionAvailable ? 'primary' : 'default'}
                disabled={canvasEmpty || busy}
                onClick={() => {
                  const dataUrl = canvasRef.current?.toDataURL();
                  if (dataUrl) void analyzeImage(dataUrl, 'drawing');
                }}
              >
                <FactCheck fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Upload an image of a problem">
            <span>
              <IconButton size="small" disabled={busy} onClick={() => fileInputRef.current?.click()}>
                <ImageIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <input ref={fileInputRef} type="file" accept="image/*" hidden onChange={handleImageUpload} />
          <Tooltip title={speechAvailable ? (recording ? 'Stop recording (Ctrl+M)' : 'Speak your problem (Ctrl+M)') : 'Speech-to-text needs the MERaLiON model (see Settings)'}>
            <span>
              <IconButton size="small" color={recording ? 'error' : 'default'} disabled={!speechAvailable || busy} onClick={toggleRecording}>
                {recording ? <Stop fontSize="small" /> : <Mic fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Export">
            <IconButton size="small" onClick={(e) => setExportAnchor(e.currentTarget)}>
              <Save fontSize="small" />
            </IconButton>
          </Tooltip>
          <Menu anchorEl={exportAnchor} open={Boolean(exportAnchor)} onClose={() => setExportAnchor(null)}>
            <MenuItem onClick={() => exportAs('txt')} disabled={messages.length === 0}>Transcript as text (Ctrl+S)</MenuItem>
            <MenuItem onClick={() => exportAs('png')} disabled={canvasEmpty}>Canvas as PNG</MenuItem>
            <MenuItem onClick={() => exportAs('pdf')} disabled={messages.length === 0 && canvasEmpty}>Canvas + transcript as PDF</MenuItem>
          </Menu>
        </WhiteboardToolbar>

        <Box sx={{ flex: 1, minHeight: 0, border: 1, borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
          <DrawingCanvas
            ref={canvasRef}
            tool={tool}
            color={color}
            lineWidth={lineWidth}
            grid={whiteboardSettings.grid}
            emptyHint="Work the problem out here — draw, add text or shapes. Type the expression below for an exact answer, or open Practice for a word problem to try."
            onChange={({ isEmpty }) => setCanvasEmpty(isEmpty)}
            onHistoryChange={setHistory}
            onSelectionChange={setHasSelection}
          />
        </Box>
      </CanvasPane>

      <ChatPane elevation={1}>
        <Typography variant="h6" gutterBottom>
          Tutor
        </Typography>

        <ChatInterface
          messages={messages}
          isProcessing={isProcessing}
          showConfidence={settings.displaySettings.showConfidence}
          showSteps={settings.displaySettings.showStepByStep}
          showModelInfo={settings.displaySettings.showModelInfo}
        />

        <Box sx={{ mt: 1.5 }}>
          {lastSolution && (
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
              <ToggleButton
                size="small"
                value="verify"
                selected={verifyMode}
                onChange={() => setVerifyMode((v) => !v)}
                sx={{ textTransform: 'none', py: 0.25 }}
              >
                <CheckCircleOutline fontSize="small" sx={{ mr: 0.5 }} />
                Check my own answer
              </ToggleButton>
              {verifyMode && (
                <Typography variant="caption" color="text.secondary" noWrap>
                  for “{lastSolution.problem}”
                </Typography>
              )}
            </Stack>
          )}
          <MathInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            disabled={isProcessing}
            placeholder={verifyMode ? 'Type your answer, e.g. x = 2 or x = 3' : undefined}
          />
          {connectionStatus !== 'connected' && (
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
              Live connection is {connectionStatus}; requests fall back to HTTP.
            </Typography>
          )}
        </Box>
      </ChatPane>
    </Layout>
  );
};
