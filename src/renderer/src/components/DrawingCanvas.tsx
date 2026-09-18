import React, { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Box, Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import { fabric } from 'fabric';
import type { WhiteboardGrid } from '../types/MathTypes';

export type DrawingTool = 'pen' | 'eraser' | 'select' | 'text' | 'rect' | 'ellipse' | 'line';

interface DrawingCanvasProps {
  tool: DrawingTool;
  color: string;
  lineWidth: number;
  /** Background guide; drawn with CSS so it never appears in exported images. */
  grid?: WhiteboardGrid;
  /** Shown centred on the canvas while it is empty. */
  emptyHint?: React.ReactNode;
  /** Debounced notification that the drawing changed. Call `toDataURL()` if you need pixels. */
  onChange?: (info: { isEmpty: boolean }) => void;
  onHistoryChange?: (state: { canUndo: boolean; canRedo: boolean }) => void;
  onSelectionChange?: (hasSelection: boolean) => void;
}

export interface DrawingCanvasRef {
  getCanvas: () => fabric.Canvas | null;
  clear: () => void;
  undo: () => void;
  redo: () => void;
  isEmpty: () => boolean;
  /** Remove the currently selected object(s). Returns true if something was removed. */
  deleteSelection: () => boolean;
  /** Place a text block on the canvas (used to bring a practice problem onto the whiteboard). */
  addText: (text: string, options?: { fontSize?: number; color?: string; top?: number }) => void;
  toDataURL: (options?: { multiplier?: number }) => string;
  toJSON: () => string;
  loadJSON: (json: string) => Promise<void>;
}

const HISTORY_LIMIT = 50;
const CHANGE_DEBOUNCE_MS = 300;
const BACKGROUND = '#ffffff';
const GRID_SIZE = 24;

const gridBackground = (grid: WhiteboardGrid, lineColor: string): Record<string, string> => {
  if (grid === 'dots') {
    return {
      backgroundImage: `radial-gradient(circle, ${lineColor} 1px, transparent 1.2px)`,
      backgroundSize: `${GRID_SIZE}px ${GRID_SIZE}px`,
      backgroundPosition: `${GRID_SIZE / 2}px ${GRID_SIZE / 2}px`,
    };
  }
  if (grid === 'lines') {
    return {
      backgroundImage: `linear-gradient(${lineColor} 1px, transparent 1px), linear-gradient(90deg, ${lineColor} 1px, transparent 1px)`,
      backgroundSize: `${GRID_SIZE}px ${GRID_SIZE}px`,
    };
  }
  return {};
};

/**
 * Fabric.js drawing surface.
 *
 * History is recorded once per user action (debounced) and suspended while a
 * snapshot is being restored, so undo/redo behave predictably. Tool handlers
 * are attached per tool and torn down on every tool change, so switching tools
 * never leaves stale listeners behind. Size follows the parent element via
 * ResizeObserver.
 */
export const DrawingCanvas = forwardRef<DrawingCanvasRef, DrawingCanvasProps>(
  ({ tool, color, lineWidth, grid = 'none', emptyHint, onChange, onHistoryChange, onSelectionChange }, ref) => {
    const theme = useTheme();
    const hostRef = useRef<HTMLDivElement>(null);
    const canvasElRef = useRef<HTMLCanvasElement>(null);
    const fabricRef = useRef<fabric.Canvas | null>(null);
    const [isEmpty, setIsEmpty] = useState(true);

    const historyRef = useRef<string[]>([]);
    const historyIndexRef = useRef(-1);
    const restoringRef = useRef(false);
    const changeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const onChangeRef = useRef(onChange);
    const onHistoryChangeRef = useRef(onHistoryChange);
    const onSelectionChangeRef = useRef(onSelectionChange);
    const gridRef = useRef(grid);
    onChangeRef.current = onChange;
    onHistoryChangeRef.current = onHistoryChange;
    onSelectionChangeRef.current = onSelectionChange;
    gridRef.current = grid;

    /** Fabric paints its own background; keep it transparent while a CSS grid shows through. */
    const applyBackground = useCallback((canvas: fabric.Canvas) => {
      canvas.backgroundColor = gridRef.current === 'none' ? BACKGROUND : '';
    }, []);

    const emitChange = useCallback((canvas: fabric.Canvas | null) => {
      const empty = !canvas || canvas.getObjects().length === 0;
      setIsEmpty(empty);
      onChangeRef.current?.({ isEmpty: empty });
    }, []);

    const emitHistory = useCallback(() => {
      onHistoryChangeRef.current?.({
        canUndo: historyIndexRef.current > 0,
        canRedo: historyIndexRef.current < historyRef.current.length - 1,
      });
    }, []);

    const snapshot = useCallback(() => {
      const canvas = fabricRef.current;
      if (!canvas) return;
      const json = JSON.stringify(canvas.toJSON());
      if (historyRef.current[historyIndexRef.current] === json) return;
      historyRef.current = historyRef.current.slice(0, historyIndexRef.current + 1);
      historyRef.current.push(json);
      if (historyRef.current.length > HISTORY_LIMIT) historyRef.current.shift();
      historyIndexRef.current = historyRef.current.length - 1;
      emitHistory();
    }, [emitHistory]);

    /** Called for every fabric mutation; coalesces bursts into one history entry + one onChange. */
    const scheduleCommit = useCallback(() => {
      if (restoringRef.current) return;
      if (changeTimerRef.current) clearTimeout(changeTimerRef.current);
      changeTimerRef.current = setTimeout(() => {
        changeTimerRef.current = null;
        snapshot();
        emitChange(fabricRef.current);
      }, CHANGE_DEBOUNCE_MS);
    }, [emitChange, snapshot]);

    const restore = useCallback(
      (json: string) =>
        new Promise<void>((resolve) => {
          const canvas = fabricRef.current;
          if (!canvas) return resolve();
          restoringRef.current = true;
          canvas.loadFromJSON(json, () => {
            applyBackground(canvas);
            canvas.renderAll();
            restoringRef.current = false;
            emitChange(canvas);
            resolve();
          });
        }),
      [applyBackground, emitChange],
    );

    // ---- lifecycle -------------------------------------------------------

    useEffect(() => {
      const host = hostRef.current;
      const el = canvasElRef.current;
      if (!host || !el) return;

      const canvas = new fabric.Canvas(el, {
        width: host.clientWidth || 800,
        height: host.clientHeight || 600,
        backgroundColor: gridRef.current === 'none' ? BACKGROUND : '',
        selection: false,
        preserveObjectStacking: true,
        enableRetinaScaling: true,
        stopContextMenu: true,
        fireRightClick: false,
      });
      fabricRef.current = canvas;

      // Smoother freehand strokes: fabric's PencilBrush simplifies paths by this tolerance.
      (canvas.freeDrawingBrush as fabric.PencilBrush & { decimate?: number }).decimate = 1.5;

      const onMutation = () => scheduleCommit();
      canvas.on('object:added', onMutation);
      canvas.on('object:modified', onMutation);
      canvas.on('object:removed', onMutation);
      canvas.on('text:changed', onMutation);

      const onSelection = () => onSelectionChangeRef.current?.(Boolean(canvas.getActiveObject()));
      canvas.on('selection:created', onSelection);
      canvas.on('selection:updated', onSelection);
      canvas.on('selection:cleared', onSelection);

      snapshot();

      const observer = new ResizeObserver(() => {
        const { clientWidth, clientHeight } = host;
        if (clientWidth > 0 && clientHeight > 0) {
          canvas.setDimensions({ width: clientWidth, height: clientHeight });
          canvas.requestRenderAll();
        }
      });
      observer.observe(host);

      return () => {
        observer.disconnect();
        if (changeTimerRef.current) clearTimeout(changeTimerRef.current);
        canvas.dispose();
        fabricRef.current = null;
      };
    }, [scheduleCommit, snapshot]);

    // ---- tools -----------------------------------------------------------

    useEffect(() => {
      const canvas = fabricRef.current;
      if (!canvas) return;

      const interactive = tool === 'select' || tool === 'text';
      canvas.isDrawingMode = tool === 'pen';
      canvas.selection = tool === 'select'; // rubber-band multi-select only in select mode
      canvas.defaultCursor = tool === 'eraser' ? 'cell' : tool === 'text' ? 'text' : tool === 'select' ? 'default' : 'crosshair';
      canvas.hoverCursor = tool === 'eraser' ? 'cell' : tool === 'select' || tool === 'text' ? 'move' : canvas.defaultCursor;
      canvas.forEachObject((obj) => {
        obj.selectable = interactive;
        obj.evented = interactive || tool === 'eraser';
      });
      canvas.discardActiveObject();
      canvas.requestRenderAll();

      if (tool === 'pen') {
        const brush = canvas.freeDrawingBrush;
        brush.color = color;
        brush.width = lineWidth;
        return;
      }
      if (tool === 'select') return;

      const disposers: Array<() => void> = [];
      const on = <T extends Event = Event>(event: string, handler: (e: fabric.IEvent<T>) => void) => {
        canvas.on(event, handler as (e: fabric.IEvent) => void);
        disposers.push(() => canvas.off(event, handler as (e: fabric.IEvent) => void));
      };

      if (tool === 'eraser') {
        let pressed = false;
        const eraseAt = (e: fabric.IEvent<MouseEvent>) => {
          const target = canvas.findTarget(e.e, false);
          if (target) canvas.remove(target);
        };
        on<MouseEvent>('mouse:down', (e) => {
          pressed = true;
          eraseAt(e);
        });
        on<MouseEvent>('mouse:move', (e) => {
          if (pressed) eraseAt(e);
        });
        on('mouse:up', () => {
          pressed = false;
        });
      } else if (tool === 'text') {
        on<MouseEvent>('mouse:down', (e) => {
          if (e.target) return;
          const pointer = canvas.getPointer(e.e);
          const text = new fabric.IText('', {
            left: pointer.x,
            top: pointer.y,
            fontFamily: 'Segoe UI, Roboto, sans-serif',
            fontSize: Math.max(16, lineWidth * 8),
            fill: color,
          });
          canvas.add(text);
          canvas.setActiveObject(text);
          text.enterEditing();
        });
        on('text:editing:exited', (e) => {
          const target = e.target as fabric.IText | undefined;
          if (target && !target.text?.trim()) canvas.remove(target);
        });
      } else {
        // rect / ellipse / line: rubber-band a single object, mutate it while dragging
        let start: { x: number; y: number } | null = null;
        let shape: fabric.Object | null = null;

        on<MouseEvent>('mouse:down', (e) => {
          start = canvas.getPointer(e.e);
          const common = { stroke: color, strokeWidth: lineWidth, fill: 'transparent', selectable: false, evented: false };
          if (tool === 'rect') {
            shape = new fabric.Rect({ ...common, left: start.x, top: start.y, width: 0, height: 0 });
          } else if (tool === 'ellipse') {
            shape = new fabric.Ellipse({ ...common, left: start.x, top: start.y, rx: 0, ry: 0 });
          } else {
            shape = new fabric.Line([start.x, start.y, start.x, start.y], { ...common });
          }
          restoringRef.current = true; // do not record the in-progress shape
          canvas.add(shape);
          restoringRef.current = false;
        });
        on<MouseEvent>('mouse:move', (e) => {
          if (!start || !shape) return;
          const p = canvas.getPointer(e.e);
          const left = Math.min(start.x, p.x);
          const top = Math.min(start.y, p.y);
          const w = Math.abs(p.x - start.x);
          const h = Math.abs(p.y - start.y);
          if (shape instanceof fabric.Rect) {
            shape.set({ left, top, width: w, height: h });
          } else if (shape instanceof fabric.Ellipse) {
            shape.set({ left, top, rx: w / 2, ry: h / 2 });
          } else if (shape instanceof fabric.Line) {
            shape.set({ x2: p.x, y2: p.y });
          }
          shape.setCoords();
          canvas.requestRenderAll();
        });
        on('mouse:up', () => {
          if (shape) {
            const tiny =
              (shape instanceof fabric.Line && shape.x1 === shape.x2 && shape.y1 === shape.y2) ||
              (!(shape instanceof fabric.Line) && (shape.width || 0) < 2 && (shape.height || 0) < 2);
            if (tiny) {
              restoringRef.current = true;
              canvas.remove(shape);
              restoringRef.current = false;
            } else {
              scheduleCommit();
            }
          }
          start = null;
          shape = null;
        });
      }

      return () => disposers.forEach((dispose) => dispose());
    }, [tool, color, lineWidth, scheduleCommit]);

    // ---- imperative API --------------------------------------------------

    useImperativeHandle(
      ref,
      () => ({
        getCanvas: () => fabricRef.current,
        isEmpty: () => !fabricRef.current || fabricRef.current.getObjects().length === 0,
        clear: () => {
          const canvas = fabricRef.current;
          if (!canvas) return;
          restoringRef.current = true;
          canvas.clear();
          applyBackground(canvas);
          canvas.renderAll();
          restoringRef.current = false;
          snapshot();
          emitChange(canvas);
        },
        deleteSelection: () => {
          const canvas = fabricRef.current;
          if (!canvas) return false;
          const active = canvas.getActiveObjects();
          if (active.length === 0) return false;
          const editing = active.some((o) => (o as fabric.IText).isEditing);
          if (editing) return false; // Backspace inside a text box edits text, not the object
          restoringRef.current = true;
          active.forEach((o) => canvas.remove(o));
          canvas.discardActiveObject();
          restoringRef.current = false;
          canvas.requestRenderAll();
          scheduleCommit();
          return true;
        },
        addText: (text, options) => {
          const canvas = fabricRef.current;
          if (!canvas || !text.trim()) return;
          const width = Math.max(240, canvas.getWidth() - 48);
          const textbox = new fabric.Textbox(text, {
            left: 24,
            top: options?.top ?? 24,
            width,
            fontFamily: 'Segoe UI, Roboto, sans-serif',
            fontSize: options?.fontSize ?? 18,
            fill: options?.color ?? '#212121',
            lineHeight: 1.3,
            selectable: true,
            evented: true,
          });
          canvas.add(textbox);
          canvas.requestRenderAll();
        },
        undo: () => {
          if (historyIndexRef.current <= 0) return;
          historyIndexRef.current -= 1;
          emitHistory();
          void restore(historyRef.current[historyIndexRef.current]);
        },
        redo: () => {
          if (historyIndexRef.current >= historyRef.current.length - 1) return;
          historyIndexRef.current += 1;
          emitHistory();
          void restore(historyRef.current[historyIndexRef.current]);
        },
        toDataURL: (options) => {
          const canvas = fabricRef.current;
          if (!canvas) return '';
          // Exports are always on white, regardless of the on-screen grid.
          const previous = canvas.backgroundColor;
          canvas.backgroundColor = BACKGROUND;
          const url = canvas.toDataURL({ format: 'png', multiplier: options?.multiplier ?? 1 });
          canvas.backgroundColor = previous;
          canvas.requestRenderAll();
          return url;
        },
        toJSON: () => (fabricRef.current ? JSON.stringify(fabricRef.current.toJSON()) : ''),
        loadJSON: async (json) => {
          await restore(json);
          snapshot();
        },
      }),
      [applyBackground, emitChange, emitHistory, restore, scheduleCommit, snapshot],
    );

    useEffect(() => {
      const canvas = fabricRef.current;
      if (!canvas) return;
      applyBackground(canvas);
      canvas.requestRenderAll();
    }, [applyBackground, grid]);

    const gridColor = alpha(theme.palette.text.primary, 0.12);

    return (
      <Box
        ref={hostRef}
        sx={{
          width: '100%',
          height: '100%',
          position: 'relative',
          overflow: 'hidden',
          backgroundColor: BACKGROUND,
          touchAction: 'none', // stylus / finger drawing must not scroll the page
          userSelect: 'none',
          ...gridBackground(grid, gridColor),
        }}
      >
        <canvas ref={canvasElRef} />
        {isEmpty && emptyHint && (
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
              p: 4,
              textAlign: 'center',
            }}
          >
            <Typography variant="body2" sx={{ color: alpha('#000', 0.38), maxWidth: 420 }}>
              {emptyHint}
            </Typography>
          </Box>
        )}
      </Box>
    );
  },
);

DrawingCanvas.displayName = 'DrawingCanvas';
