import { ThemeOptions } from '@mui/material/styles';

const baseTypography: ThemeOptions['typography'] = {
  fontFamily: "'Inter', 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  h4: { fontWeight: 700, letterSpacing: '-0.02em' },
  h5: { fontWeight: 700, letterSpacing: '-0.015em' },
  h6: { fontWeight: 600, letterSpacing: '-0.01em' },
  button: { textTransform: 'none', fontWeight: 600 },
};

export const operanDarkTheme: ThemeOptions = {
  palette: {
    mode: 'dark',
    background: {
      default: '#060B19',
      paper: '#0B1325',
    },
    primary: {
      main: '#0EA5E9',
      light: '#38BDF8',
      dark: '#0284C7',
      contrastText: '#F8FAFC',
    },
    secondary: {
      main: '#6366F1',
      light: '#818CF8',
      dark: '#4F46E5',
      contrastText: '#F8FAFC',
    },
    success: {
      main: '#10B981',
      contrastText: '#052E16',
    },
    warning: {
      main: '#F59E0B',
      contrastText: '#451A03',
    },
    error: {
      main: '#EF4444',
      contrastText: '#FEF2F2',
    },
    text: {
      primary: '#F1F5F9',
      secondary: '#94A3B8',
    },
    divider: 'rgba(148, 163, 184, 0.12)',
  },
  shape: {
    borderRadius: 12,
  },
  typography: baseTypography,
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: '#060B19',
          backgroundImage:
            'radial-gradient(circle at 15% 0%, rgba(14, 165, 233, 0.08), transparent 40%), radial-gradient(circle at 85% 10%, rgba(99, 102, 241, 0.06), transparent 40%)',
          backgroundAttachment: 'fixed',
          color: '#F1F5F9',
        },
        '*::-webkit-scrollbar': {
          width: '8px',
          height: '8px',
        },
        '*::-webkit-scrollbar-track': {
          background: '#060B19',
        },
        '*::-webkit-scrollbar-thumb': {
          background: '#1E293B',
          borderRadius: '4px',
        },
        'input:-webkit-autofill, input:-webkit-autofill:hover, input:-webkit-autofill:focus, textarea:-webkit-autofill': {
          WebkitBoxShadow: '0 0 0 1000px #24324C inset !important',
          WebkitTextFillColor: '#F8FAFC !important',
          caretColor: '#F8FAFC !important',
          transition: 'background-color 9999s ease-in-out 0s',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: '#0B1325',
          border: '1px solid rgba(56, 189, 248, 0.12)',
          boxShadow: '0 10px 30px -10px rgba(2, 6, 23, 0.7)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          padding: '8px 18px',
          fontWeight: 600,
          textTransform: 'none',
        },
        containedPrimary: {
          background: 'linear-gradient(135deg, #0EA5E9 0%, #2563EB 100%)',
          boxShadow: '0 4px 14px 0 rgba(14, 165, 233, 0.35)',
          '&:hover': {
            background: 'linear-gradient(135deg, #38BDF8 0%, #3B82F6 100%)',
            boxShadow: '0 6px 20px 0 rgba(14, 165, 233, 0.5)',
          },
        },
        outlined: {
          borderColor: 'rgba(148, 163, 184, 0.28)',
          '&:hover': {
            borderColor: '#38BDF8',
            backgroundColor: 'rgba(14, 165, 233, 0.08)',
          },
        },
      },
    },
    MuiTableContainer: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          border: '1px solid rgba(148, 163, 184, 0.12)',
          backgroundColor: '#091020',
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(15, 23, 42, 0.85)',
          '& .MuiTableCell-head': {
            color: '#94A3B8',
            fontWeight: 700,
            fontSize: '0.75rem',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            borderBottom: '1px solid rgba(148, 163, 184, 0.15)',
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: 'rgba(14, 165, 233, 0.05)',
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(148, 163, 184, 0.08)',
          color: '#E2E8F0',
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(6, 11, 25, 0.6)',
          borderRadius: 10,
          '& fieldset': {
            borderColor: 'rgba(148, 163, 184, 0.22)',
          },
          '&:hover fieldset': {
            borderColor: 'rgba(56, 189, 248, 0.5)',
          },
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: '#0B1325',
          border: '1px solid rgba(56, 189, 248, 0.22)',
          borderRadius: 16,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          fontSize: '0.9rem',
        },
      },
    },
  },
};

export const redDarkTheme: ThemeOptions = {
  palette: {
    mode: 'dark',
    background: { default: '#1A0808', paper: '#2A0E0E' },
    primary: { main: '#EF4444', contrastText: '#FEF2F2' },
    secondary: { main: '#B91C1C', contrastText: '#FCA5A5' },
    text: { primary: '#FEE2E2', secondary: '#FCA5A5' },
  },
  typography: baseTypography,
};

export const solarizedDarkTheme: ThemeOptions = {
  palette: {
    mode: 'dark',
    background: { default: '#002b36', paper: '#073642' },
    primary: { main: '#268bd2', contrastText: '#fdf6e3' },
    secondary: { main: '#2aa198', contrastText: '#93a1a1' },
    text: { primary: '#EEE8D5', secondary: '#93A1A1' },
  },
  typography: baseTypography,
};

export const greenForestTheme: ThemeOptions = {
  palette: {
    mode: 'dark',
    background: { default: '#071712', paper: '#0E261E' },
    primary: { main: '#10B981', contrastText: '#ECFDF5' },
    secondary: { main: '#059669', contrastText: '#A7F3D0' },
    text: { primary: '#ECFDF5', secondary: '#6EE7B7' },
  },
  typography: baseTypography,
};

export const oceanBlueTheme: ThemeOptions = {
  palette: {
    mode: 'dark',
    background: { default: '#0a2540', paper: '#13395c' },
    primary: { main: '#38BDF8', contrastText: '#e3f2fd' },
    secondary: { main: '#0288d1', contrastText: '#b3e5fc' },
    text: { primary: '#F0F9FF', secondary: '#93C5FD' },
  },
  typography: baseTypography,
};

export const purpleNightTheme: ThemeOptions = {
  palette: {
    mode: 'dark',
    background: { default: '#110C24', paper: '#1C143A' },
    primary: { main: '#A855F7', contrastText: '#FAF5FF' },
    secondary: { main: '#7E22CE', contrastText: '#E9D5FF' },
    text: { primary: '#F3E8FF', secondary: '#C084FC' },
  },
  typography: baseTypography,
};
