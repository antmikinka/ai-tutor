import React, { Component, ErrorInfo, ReactNode } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Alert,
  AlertTitle,
  Divider,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import { Refresh, BugReport } from '@mui/icons-material';

const ErrorContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  minHeight: '100vh',
  padding: theme.spacing(4),
  backgroundColor: theme.palette.background.default,
}));

const ErrorPaper = styled(Paper)(({ theme }) => ({
  maxWidth: 600,
  width: '100%',
  padding: theme.spacing(4),
  backgroundColor: theme.palette.background.paper,
}));

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

interface ErrorBoundaryProps {
  children: ReactNode;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      error,
      errorInfo: null,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);

    this.setState({
      hasError: true,
      error,
      errorInfo,
    });

    // Log error to external service (optional)
    this.logErrorToService(error, errorInfo);
  }

  logErrorToService = (error: Error, errorInfo: ErrorInfo) => {
    // This is where you would send the error to an external monitoring service
    // For now, we'll just log to console
    console.group('Error Boundary Log');
    console.error('Error:', error);
    console.error('Error Info:', errorInfo);
    console.error('Component Stack:', errorInfo.componentStack);
    console.groupEnd();
  };

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render() {
    if (this.state.hasError) {
      return (
        <ErrorContainer>
          <ErrorPaper elevation={3}>
            <Box sx={{ textAlign: 'center', mb: 3 }}>
              <BugReport sx={{ fontSize: 64, color: 'error.main', mb: 2 }} />
              <Typography variant="h4" component="h1" gutterBottom color="error">
                Oops! Something went wrong
              </Typography>
              <Typography variant="body1" color="text.secondary">
                The application encountered an unexpected error. Don't worry, your work is safe.
              </Typography>
            </Box>

            <Alert severity="error" sx={{ mb: 3 }}>
              <AlertTitle>Error Details</AlertTitle>
              <Typography variant="body2" component="pre" sx={{
                fontFamily: 'monospace',
                fontSize: '0.875rem',
                overflow: 'auto',
                maxHeight: 100,
                backgroundColor: 'grey.100',
                p: 1,
                borderRadius: 1,
              }}>
                {this.state.error?.message || 'Unknown error'}
              </Typography>
            </Alert>

            {this.state.errorInfo && (
              <>
                <Divider sx={{ my: 2 }} />
                <Typography variant="h6" gutterBottom>
                  Technical Details
                </Typography>
                <List dense>
                  <ListItem>
                    <ListItemText
                      primary="Error Type"
                      secondary={this.state.error?.name || 'Unknown'}
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Component Stack"
                      secondary={
                        <Typography
                          variant="body2"
                          component="pre"
                          sx={{
                            fontFamily: 'monospace',
                            fontSize: '0.75rem',
                            overflow: 'auto',
                            maxHeight: 100,
                            backgroundColor: 'grey.100',
                            p: 1,
                            borderRadius: 1,
                          }}
                        >
                          {this.state.errorInfo.componentStack}
                        </Typography>
                      }
                    />
                  </ListItem>
                </List>
              </>
            )}

            <Divider sx={{ my: 3 }} />

            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
              <Button
                variant="contained"
                startIcon={<Refresh />}
                onClick={this.handleReload}
                color="primary"
              >
                Reload Application
              </Button>
              <Button
                variant="outlined"
                onClick={this.handleReset}
                color="secondary"
              >
                Try Again
              </Button>
            </Box>

            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                If this problem persists, please contact support or restart the application.
              </Typography>
            </Box>
          </ErrorPaper>
        </ErrorContainer>
      );
    }

    return this.props.children;
  }
}