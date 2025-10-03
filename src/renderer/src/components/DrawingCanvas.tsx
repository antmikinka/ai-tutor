import React, { useEffect, useRef, forwardRef, useImperativeHandle, useCallback } from 'react';
import { Box } from '@mui/material';
import { fabric } from 'fabric';

interface DrawingCanvasProps {
  tool: 'pen' | 'eraser' | 'text' | 'shape';
  color: string;
  lineWidth: number;
  onChange?: (canvasData: string) => void;
  width?: number;
  height?: number;
}

export interface DrawingCanvasRef {
  getCanvas: () => fabric.Canvas | null;
  clear: () => void;
  undo: () => void;
  redo: () => void;
  toDataURL: () => string;
  setDrawingMode: (isDrawing: boolean) => void;
}

export const DrawingCanvas = forwardRef<DrawingCanvasRef, DrawingCanvasProps>(
  ({ tool, color, lineWidth, onChange, width = '100%', height = '100%' }, ref) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const fabricCanvasRef = useRef<fabric.Canvas | null>(null);
    const historyRef = useRef<string[]>([]);
    const historyIndexRef = useRef<number>(-1);

    // Initialize Fabric.js canvas
    useEffect(() => {
      if (canvasRef.current) {
        const parentElement = canvasRef.current.parentElement;
        const canvasWidth = parentElement?.clientWidth || 800;
        const canvasHeight = parentElement?.clientHeight || 600;

        // Set canvas element dimensions
        canvasRef.current.width = canvasWidth;
        canvasRef.current.height = canvasHeight;

        const canvas = new fabric.Canvas(canvasRef.current, {
          isDrawingMode: tool === 'pen',
          width: canvasWidth,
          height: canvasHeight,
          backgroundColor: '#ffffff',
          selection: false,
        });

        // Set default drawing styles
        if (tool === 'pen') {
          canvas.freeDrawingBrush.color = color;
          canvas.freeDrawingBrush.width = lineWidth;
        }

        // Canvas event handlers
        canvas.on('path:created', () => {
          saveCanvasState();
          notifyChange();
        });

        canvas.on('object:added', () => {
          saveCanvasState();
          notifyChange();
        });

        canvas.on('object:modified', () => {
          saveCanvasState();
          notifyChange();
        });

        canvas.on('object:removed', () => {
          saveCanvasState();
          notifyChange();
        });

        fabricCanvasRef.current = canvas;
        saveCanvasState();

        // Handle window resize
        const handleResize = () => {
          if (canvasRef.current && canvasRef.current.parentElement) {
            const parentElement = canvasRef.current.parentElement;
            const newWidth = parentElement.clientWidth;
            const newHeight = parentElement.clientHeight;

            // Update canvas element dimensions
            canvasRef.current.width = newWidth;
            canvasRef.current.height = newHeight;

            // Update Fabric.js canvas dimensions
            canvas.setDimensions({
              width: newWidth,
              height: newHeight,
            });

            // Re-render canvas
            canvas.renderAll();
          }
        };

        window.addEventListener('resize', handleResize);

        return () => {
          canvas.dispose();
          window.removeEventListener('resize', handleResize);
        };
      }
    }, []); // Only run once on mount

    const notifyChange = useCallback(() => {
      if (onChange && fabricCanvasRef.current) {
        onChange(fabricCanvasRef.current.toDataURL());
      }
    }, [onChange]);

    const saveCanvasState = () => {
      if (fabricCanvasRef.current) {
        const json = JSON.stringify(fabricCanvasRef.current.toJSON());

        // Remove any states after current index
        historyRef.current = historyRef.current.slice(0, historyIndexRef.current + 1);

        // Add new state
        historyRef.current.push(json);
        historyIndexRef.current = historyRef.current.length - 1;

        // Limit history size
        if (historyRef.current.length > 50) {
          historyRef.current.shift();
          historyIndexRef.current--;
        }
      }
    };

    // Update drawing mode and styles when tool changes
    useEffect(() => {
      if (fabricCanvasRef.current) {
        const canvas = fabricCanvasRef.current;

        switch (tool) {
          case 'pen':
            canvas.isDrawingMode = true;
            canvas.freeDrawingBrush.color = color;
            canvas.freeDrawingBrush.width = lineWidth;
            canvas.selection = false;
            break;

          case 'eraser':
            canvas.isDrawingMode = true;
            canvas.freeDrawingBrush.color = '#ffffff';
            canvas.freeDrawingBrush.width = lineWidth * 3;
            canvas.selection = false;
            break;

          case 'text':
            canvas.isDrawingMode = false;
            canvas.selection = true;
            setupTextTool(canvas);
            break;

          case 'shape':
            canvas.isDrawingMode = false;
            canvas.selection = true;
            setupShapeTool(canvas);
            break;
        }
      }
    }, [tool, color, lineWidth]);

    // Update color and line width
    useEffect(() => {
      if (fabricCanvasRef.current && (tool === 'pen' || tool === 'eraser')) {
        const brush = fabricCanvasRef.current.freeDrawingBrush;
        brush.color = tool === 'eraser' ? '#ffffff' : color;
        brush.width = tool === 'eraser' ? lineWidth * 3 : lineWidth;
      }
    }, [color, lineWidth, tool]);

    // Handle container size changes
    useEffect(() => {
      if (fabricCanvasRef.current && canvasRef.current?.parentElement) {
        const parentElement = canvasRef.current.parentElement;
        const newWidth = parentElement.clientWidth;
        const newHeight = parentElement.clientHeight;

        // Update canvas element dimensions
        canvasRef.current.width = newWidth;
        canvasRef.current.height = newHeight;

        // Update Fabric.js canvas dimensions
        fabricCanvasRef.current.setDimensions({
          width: newWidth,
          height: newHeight,
        });

        // Re-render canvas
        fabricCanvasRef.current.renderAll();
      }
    }, [width, height]);

    const setupTextTool = useCallback((canvas: fabric.Canvas) => {
      // Remove existing event listeners
      canvas.off('mouse:down');
      canvas.off('mouse:up');

      canvas.on('mouse:down', (options) => {
        if (options.target) return;

        const pointer = canvas.getPointer(options.e);
        const text = new fabric.IText('Click to edit', {
          left: pointer.x,
          top: pointer.y,
          fontFamily: 'Arial',
          fontSize: 16,
          fill: color,
        });

        canvas.add(text);
        canvas.setActiveObject(text);
        text.enterEditing();
        text.selectAll();
      });
    }, [color]);

    const setupShapeTool = useCallback((canvas: fabric.Canvas) => {
      // Remove existing event listeners
      canvas.off('mouse:down');
      canvas.off('mouse:move');
      canvas.off('mouse:up');

      let isDrawing = false;
      let startX = 0;
      let startY = 0;
      let currentShape: fabric.Object | null = null;

      canvas.on('mouse:down', (options) => {
        if (options.target) return;

        isDrawing = true;
        const pointer = canvas.getPointer(options.e);
        startX = pointer.x;
        startY = pointer.y;
      });

      canvas.on('mouse:move', (options) => {
        if (!isDrawing) return;

        const pointer = canvas.getPointer(options.e);
        const width = pointer.x - startX;
        const height = pointer.y - startY;

        // Remove previous shape
        if (currentShape) {
          canvas.remove(currentShape);
        }

        // Create rectangle
        currentShape = new fabric.Rect({
          left: Math.min(startX, pointer.x),
          top: Math.min(startY, pointer.y),
          width: Math.abs(width),
          height: Math.abs(height),
          fill: 'transparent',
          stroke: color,
          strokeWidth: lineWidth,
        });

        canvas.add(currentShape);
      });

      canvas.on('mouse:up', () => {
        isDrawing = false;
        currentShape = null;
      });
    }, [color, lineWidth]);

    // Expose canvas methods via ref
    useImperativeHandle(ref, () => ({
      getCanvas: () => fabricCanvasRef.current,
      clear: () => {
        if (fabricCanvasRef.current) {
          fabricCanvasRef.current.clear();
          fabricCanvasRef.current.backgroundColor = '#ffffff';
          saveCanvasState();
          notifyChange();
        }
      },
      undo: () => {
        if (historyIndexRef.current > 0) {
          historyIndexRef.current--;
          const state = historyRef.current[historyIndexRef.current];
          if (fabricCanvasRef.current && state) {
            fabricCanvasRef.current.loadFromJSON(state, () => {
              fabricCanvasRef.current?.renderAll();
              notifyChange();
            });
          }
        }
      },
      redo: () => {
        if (historyIndexRef.current < historyRef.current.length - 1) {
          historyIndexRef.current++;
          const state = historyRef.current[historyIndexRef.current];
          if (fabricCanvasRef.current && state) {
            fabricCanvasRef.current.loadFromJSON(state, () => {
              fabricCanvasRef.current?.renderAll();
              notifyChange();
            });
          }
        }
      },
      toDataURL: () => {
        return fabricCanvasRef.current?.toDataURL() || '';
      },
      setDrawingMode: (isDrawing: boolean) => {
        if (fabricCanvasRef.current) {
          fabricCanvasRef.current.isDrawingMode = isDrawing;
        }
      },
    }));

    return (
      <Box
        sx={{
          width,
          height,
          position: 'relative',
          '& canvas': {
            border: '1px solid #ddd',
            borderRadius: 1,
            cursor: tool === 'pen' || tool === 'eraser' ? 'crosshair' : 'default',
          },
        }}
      >
        <canvas
          ref={canvasRef}
          style={{
            width: '100%',
            height: '100%',
            display: 'block',
          }}
        />
      </Box>
    );
  }
);

DrawingCanvas.displayName = 'DrawingCanvas';