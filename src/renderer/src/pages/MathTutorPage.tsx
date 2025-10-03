import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  IconButton,
  Divider,
  CircularProgress,
  TextField,
  Menu,
  MenuItem,
} from '@mui/material';
import {
  Send,
  Mic,
  Image,
  Save,
  Clear,
  Undo,
  Redo,
  Functions,
  FormatBold,
  GridOn,
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import { DrawingCanvas, DrawingCanvasRef } from '../components/DrawingCanvas';
import { ChatInterface } from '../components/ChatInterface';
import { MathInput } from '../components/MathInput';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAppSettings } from '../hooks/useAppSettings';
import { MathSolution } from '../types/MathTypes';

const MainContent = styled(Box)(({ theme }) => ({
  display: 'flex',
  height: '100%',
  gap: theme.spacing(2),
}));

const CanvasSection = styled(Paper)(({ theme }) => ({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  padding: theme.spacing(2),
  minHeight: 0,
}));

const ChatSection = styled(Paper)(({ theme }) => ({
  width: 400,
  display: 'flex',
  flexDirection: 'column',
  padding: theme.spacing(2),
  [theme.breakpoints.down('md')]: {
    width: 300,
  },
}));

const ToolBar = styled(Box)(({ theme }) => ({
  display: 'flex',
  gap: theme.spacing(1),
  marginBottom: theme.spacing(2),
  padding: theme.spacing(1),
  backgroundColor: theme.palette.grey[100],
  borderRadius: theme.shape.borderRadius,
  flexWrap: 'wrap',
}));

export const MathTutorPage: React.FC = () => {
  const [activeTool, setActiveTool] = useState<'pen' | 'eraser' | 'text' | 'shape'>('pen');
  const [color] = useState('#000000');
  const [lineWidth] = useState(2);
  const [textInput, setTextInput] = useState('');
  const [mathInput, setMathInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [solutions, setSolutions] = useState<MathSolution[]>([]);
  const [currentSolution, setCurrentSolution] = useState<MathSolution | null>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const canvasRef = useRef<DrawingCanvasRef>(null);
  const { sendMessage, connectionStatus } = useWebSocket();

  useEffect(() => {
    // Initialize canvas settings
    if (canvasRef.current) {
      canvasRef.current.setDrawingMode(true);
    }
  }, []);

  const handleSendMessage = async () => {
    if (!textInput.trim() && !mathInput.trim()) return;

    const message = {
      type: 'math_input',
      content: textInput || mathInput,
      timestamp: new Date().toISOString(),
      metadata: {
        tool: activeTool,
        canvasData: canvasRef.current?.toDataURL(),
      },
    };

    setIsProcessing(true);
    try {
      sendMessage(message);

      // Simulate AI response (will be replaced with actual backend integration)
      setTimeout(() => {
        const solution: MathSolution = {
          id: Date.now().toString(),
          problem: textInput || mathInput,
          solution: generateMockSolution(textInput || mathInput),
          steps: generateMockSteps(textInput || mathInput),
          confidence: 0.85,
          timestamp: new Date().toISOString(),
        };

        setCurrentSolution(solution);
        setSolutions(prev => [solution, ...prev]);
        setIsProcessing(false);
        setTextInput('');
        setMathInput('');
      }, 2000);
    } catch (error) {
      console.error('Failed to send message:', error);
      setIsProcessing(false);
    }
  };

  const handleCanvasChange = (canvasData: string) => {
    // Send canvas data to backend for analysis
    if (connectionStatus === 'connected') {
      sendMessage({
        type: 'drawing_update',
        data: canvasData,
        timestamp: new Date().toISOString(),
      });
    }
  };

  const handleVoiceInput = () => {
    // Voice input will be integrated with Whisper STT
    console.log('Voice input triggered');
  };

  const handleImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const imageData = e.target?.result as string;
        // Process image with OCR (will be implemented)
        console.log('Image uploaded:', imageData);
      };
      reader.readAsDataURL(file);
    }
  };

  const exportSolution = (format: 'pdf' | 'png' | 'txt') => {
    if (!currentSolution) return;

    console.log(`Exporting solution as ${format}:`, currentSolution);
    // Implementation will be added
  };

  const clearCanvas = () => {
    if (canvasRef.current) {
      canvasRef.current.clear();
    }
  };

  const generateMockSolution = (problem: string): string => {
    // Mock solution generation - will be replaced with AI integration
    const solutions = [
      `To solve ${problem}, we can use the quadratic formula: x = (-b ± √(b² - 4ac)) / 2a`,
      `The derivative of ${problem} is 2x + 3`,
      `The integral of ${problem} is (1/2)x² + 3x + C`,
      `The solution to ${problem} is x = 5`,
    ];
    return solutions[Math.floor(Math.random() * solutions.length)];
  };

  const generateMockSteps = (problem: string): string[] => {
    // Mock step generation - will be replaced with AI integration
    return [
      `Step 1: Identify the variables in ${problem}`,
      'Step 2: Apply the appropriate mathematical formula',
      'Step 3: Simplify the expression',
      'Step 4: Solve for the unknown variable',
      'Step 5: Verify the solution',
    ];
  };

  return (
    <MainContent>
      {/* Canvas Section */}
      <CanvasSection elevation={2}>
        <Typography variant="h6" gutterBottom>
          Drawing Canvas
        </Typography>

        <ToolBar>
          <IconButton
            color={activeTool === 'pen' ? 'primary' : 'default'}
            onClick={() => setActiveTool('pen')}
            title="Pen"
          >
            <FormatBold />
          </IconButton>

          <IconButton
            color={activeTool === 'eraser' ? 'primary' : 'default'}
            onClick={() => setActiveTool('eraser')}
            title="Eraser"
          >
            <Clear />
          </IconButton>

          <IconButton
            color={activeTool === 'text' ? 'primary' : 'default'}
            onClick={() => setActiveTool('text')}
            title="Text"
          >
            <Functions />
          </IconButton>

          <IconButton
            color={activeTool === 'shape' ? 'primary' : 'default'}
            onClick={() => setActiveTool('shape')}
            title="Shapes"
          >
            <GridOn />
          </IconButton>

          <Divider orientation="vertical" flexItem />

          <IconButton onClick={clearCanvas} title="Clear Canvas">
            <Clear />
          </IconButton>

          <IconButton onClick={() => canvasRef.current?.undo()} title="Undo">
            <Undo />
          </IconButton>

          <IconButton onClick={() => canvasRef.current?.redo()} title="Redo">
            <Redo />
          </IconButton>

          <Divider orientation="vertical" flexItem />

          <IconButton onClick={handleVoiceInput} title="Voice Input">
            <Mic />
          </IconButton>

          <IconButton component="label" title="Upload Image">
            <input
              type="file"
              accept="image/*"
              hidden
              onChange={handleImageUpload}
            />
            <Image />
          </IconButton>

          <IconButton onClick={() => exportSolution('png')} title="Save as Image">
            <Save />
          </IconButton>
        </ToolBar>

        <Box sx={{ flex: 1, border: '1px solid #ddd', borderRadius: 1, overflow: 'hidden' }}>
          <DrawingCanvas
            ref={canvasRef}
            tool={activeTool}
            color={color}
            lineWidth={lineWidth}
            onChange={handleCanvasChange}
          />
        </Box>
      </CanvasSection>

      {/* Chat Section */}
      <ChatSection elevation={2}>
        <Typography variant="h6" gutterBottom>
          AI Assistant
        </Typography>

        <ChatInterface
          solutions={solutions}
          currentSolution={currentSolution}
          isProcessing={isProcessing}
        />

        <Box sx={{ mt: 2 }}>
          <TextField
            fullWidth
            multiline
            rows={2}
            variant="outlined"
            placeholder="Type your math problem or question..."
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
          />

          <MathInput
            value={mathInput}
            onChange={setMathInput}
            onSend={handleSendMessage}
          />

          <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
            <Button
              variant="contained"
              endIcon={<Send />}
              onClick={handleSendMessage}
              disabled={isProcessing || (!textInput.trim() && !mathInput.trim())}
              fullWidth
            >
              {isProcessing ? <CircularProgress size={20} /> : 'Send'}
            </Button>

            <IconButton onClick={(event) => setAnchorEl(event.currentTarget)}>
              <Save />
            </IconButton>

            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={() => setAnchorEl(null)}
            >
              <MenuItem onClick={() => exportSolution('pdf')}>Export as PDF</MenuItem>
              <MenuItem onClick={() => exportSolution('png')}>Export as PNG</MenuItem>
              <MenuItem onClick={() => exportSolution('txt')}>Export as Text</MenuItem>
            </Menu>
          </Box>
        </Box>
      </ChatSection>
    </MainContent>
  );
};