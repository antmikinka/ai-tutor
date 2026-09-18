import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  useTheme,
  useMediaQuery,
  Divider,
  Menu,
  MenuItem,
  Tooltip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Calculate,
  Settings,
  Help,
  Fullscreen,
  FullscreenExit,
  MoreVert,
  RestartAlt,
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import ConnectionStatus from '../ConnectionStatus';
import { useSettingsContext } from '../../contexts/SettingsContext';

const drawerWidth = 240;

const Main = styled('main', { shouldForwardProp: (prop) => prop !== 'open' })<{ open?: boolean }>(({ theme, open }) => ({
  flexGrow: 1,
  padding: theme.spacing(3),
  transition: theme.transitions.create('margin', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  marginLeft: 0,
  [theme.breakpoints.up('md')]: {
    marginLeft: open ? 0 : `-${drawerWidth}px`,
  },
}));

const menuItems = [
  { text: 'Math Tutor', icon: <Calculate />, path: '/' },
  { text: 'Settings', icon: <Settings />, path: '/settings' },
  { text: 'Help', icon: <Help />, path: '/help' },
];

interface MainLayoutProps {
  children: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();
  const location = useLocation();
  const { settings } = useSettingsContext();

  const [drawerOpen, setDrawerOpen] = useState(!isMobile);
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(Boolean(document.fullscreenElement));
  const [appVersion, setAppVersion] = useState<string>(settings.appVersion);

  useEffect(() => {
    window.electronAPI?.getAppVersion().then(setAppVersion).catch(() => undefined);
  }, []);

  useEffect(() => {
    const onChange = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  const toggleFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch (error) {
      console.warn('Fullscreen toggle failed:', error);
    }
  };

  const go = (path: string) => {
    navigate(path);
    setMenuAnchor(null);
    if (isMobile) setDrawerOpen(false);
  };

  const drawer = (
    <div>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          AI Math Tutor
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        {menuItems.map((item) => (
          <ListItemButton key={item.text} onClick={() => go(item.path)} selected={location.pathname === item.path}>
            <ListItemIcon>{item.icon}</ListItemIcon>
            <ListItemText primary={item.text} />
          </ListItemButton>
        ))}
      </List>
    </div>
  );

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      <AppBar
        position="fixed"
        sx={{
          width: { md: drawerOpen ? `calc(100% - ${drawerWidth}px)` : '100%' },
          ml: { md: drawerOpen ? `${drawerWidth}px` : 0 },
          transition: 'width 0.3s, margin 0.3s',
        }}
      >
        <Toolbar>
          <IconButton color="inherit" aria-label="toggle navigation" edge="start" onClick={() => setDrawerOpen((o) => !o)} sx={{ mr: 2 }}>
            <MenuIcon />
          </IconButton>

          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            AI Math Tutor
          </Typography>

          <Box sx={{ mr: 2 }}>
            <ConnectionStatus compact={isMobile} />
          </Box>

          <Tooltip title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}>
            <IconButton color="inherit" onClick={toggleFullscreen}>
              {isFullscreen ? <FullscreenExit /> : <Fullscreen />}
            </IconButton>
          </Tooltip>

          <IconButton size="large" aria-label="more options" aria-controls="menu-appbar" aria-haspopup="true" onClick={(e) => setMenuAnchor(e.currentTarget)} color="inherit">
            <MoreVert />
          </IconButton>

          <Menu
            id="menu-appbar"
            anchorEl={menuAnchor}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            open={Boolean(menuAnchor)}
            onClose={() => setMenuAnchor(null)}
          >
            <MenuItem onClick={() => go('/settings')}>
              <Settings sx={{ mr: 1 }} fontSize="small" />
              Settings
            </MenuItem>
            <MenuItem onClick={() => go('/help')}>
              <Help sx={{ mr: 1 }} fontSize="small" />
              Help
            </MenuItem>
            {window.electronAPI && (
              <MenuItem
                onClick={() => {
                  setMenuAnchor(null);
                  window.electronAPI?.restartBackend();
                }}
              >
                <RestartAlt sx={{ mr: 1 }} fontSize="small" />
                Restart backend
              </MenuItem>
            )}
            <Divider />
            <MenuItem disabled>Version {appVersion}</MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      <Drawer
        variant={isMobile ? 'temporary' : 'persistent'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{ '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth } }}
      >
        {drawer}
      </Drawer>

      <Main open={drawerOpen}>
        <Toolbar />
        <Box sx={{ height: 'calc(100vh - 64px - 48px)', overflow: 'auto' }}>{children}</Box>
      </Main>
    </Box>
  );
};
