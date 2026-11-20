import React, { useEffect, useState } from 'react';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  CssBaseline,
  IconButton,
  Tooltip,
  Dialog,
  DialogContent,
  TextField,
  InputAdornment,
  Stack,
  Select,
  MenuItem,
} from '@mui/material';
import EventIcon from '@mui/icons-material/Event';
import LogoutIcon from '@mui/icons-material/Logout';
import SettingsIcon from '@mui/icons-material/Settings';
import WorkIcon from '@mui/icons-material/Work';
import SubjectIcon from '@mui/icons-material/Subject';
import AssignmentIcon from '@mui/icons-material/Assignment';
import BuildIcon from '@mui/icons-material/Build';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import RecordVoiceOverIcon from '@mui/icons-material/RecordVoiceOver';
import SearchIcon from '@mui/icons-material/Search';
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined';
import SinoNotificacoes from './SinoNotificacoes';
import BusinessOutlinedIcon from '@mui/icons-material/BusinessOutlined';
import AutoAwesomeMosaicIcon from '@mui/icons-material/AutoAwesomeMosaic';
import { useAuth } from '../contexts/AuthContext';
import { useLocation, useNavigate } from 'react-router-dom';
import api, { CLIENTE_EM_GESTAO_KEY } from '../api';

const VISAO_GLOBAL = '__global__';

const drawerWidth = 264;

const navItemSx = (active: boolean) => ({
  mx: 1.5,
  my: 0.4,
  px: 1.75,
  py: 1,
  borderRadius: '10px',
  transition: 'all 0.18s ease',
  border: active ? '1px solid rgba(56, 189, 248, 0.35)' : '1px solid transparent',
  background: active
    ? 'linear-gradient(90deg, rgba(14, 165, 233, 0.18) 0%, rgba(14, 165, 233, 0.04) 100%)'
    : 'transparent',
  color: active ? '#F8FAFC' : '#94A3B8',
  '& .MuiListItemIcon-root': {
    minWidth: 36,
    color: active ? '#38BDF8' : '#64748B',
    transition: 'color 0.18s ease',
  },
  '& .MuiListItemText-primary': {
    fontSize: '0.88rem',
    fontWeight: active ? 600 : 500,
  },
  '&:hover': {
    backgroundColor: active ? 'rgba(14, 165, 233, 0.22)' : 'rgba(148, 163, 184, 0.07)',
    color: '#F8FAFC',
    '& .MuiListItemIcon-root': {
      color: '#38BDF8',
    },
  },
});

const sectionTitleSx = {
  px: 3,
  pt: 2.5,
  pb: 0.75,
  fontSize: '0.68rem',
  fontWeight: 700,
  letterSpacing: '0.09em',
  textTransform: 'uppercase' as const,
  color: '#475569',
};

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { logout, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [tenantName, setTenantName] = useState<string>('Banca Central');
  const [cmdOpen, setCmdOpen] = useState(false);
  const [cmdQuery, setCmdQuery] = useState('');
  const tenantId = user?.tenant_id ?? localStorage.getItem('tenantId');
  const isAdminGeral = user?.role === 'administrador geral';
  const [clientes, setClientes] = useState<{ id: number; name: string }[]>([]);
  const clienteEmGestao = (() => {
    try { return localStorage.getItem(CLIENTE_EM_GESTAO_KEY) || ''; } catch { return ''; }
  })();

  useEffect(() => {
    if (!isAdminGeral) return;
    api.get('/admin/clients')
      .then(({ data }) => setClientes(Array.isArray(data) ? data : []))
      .catch(() => setClientes([]));
  }, [isAdminGeral]);

  // Trocar de cliente recarrega o sistema do zero no painel, para nada da tela anterior
  // (de outro cliente) continuar visível ou em memória.
  const trocarCliente = (valor: string) => {
    try {
      if (valor === VISAO_GLOBAL) localStorage.removeItem(CLIENTE_EM_GESTAO_KEY);
      else localStorage.setItem(CLIENTE_EM_GESTAO_KEY, valor);
    } catch { /* sem armazenamento: permanece na visão atual */ }
    window.location.assign('/dashboard');
  };

  const [eventoCabecalho, setEventoCabecalho] = useState<{
    nome_evento?: string;
    identificador_evento?: string;
  } | null>(null);

  const eventoMatch = location.pathname.match(/^\/eventos\/([^/]+)/);
  const eventId = eventoMatch && eventoMatch[1] !== 'novo' ? eventoMatch[1] : null;

  useEffect(() => {
    const fetchTenantName = async () => {
      if (tenantId) {
        try {
          const response = await api.get(`/admin/clients/${tenantId}`);
          setTenantName(response.data.name);
        } catch {
          setTenantName('Banca Organizadora');
        }
      } else if (user?.role === 'administrador geral') {
        setTenantName('Governança Global');
      }
    };
    fetchTenantName();
  }, [tenantId, user?.role]);

  useEffect(() => {
    async function fetchEventoCabecalho() {
      if (!eventId) {
        setEventoCabecalho(null);
        return;
      }
      try {
        const response = await api.get(`/eventos/${eventId}`);
        setEventoCabecalho({
          nome_evento: response.data.nome_evento,
          identificador_evento: response.data.identificador_evento,
        });
      } catch {
        setEventoCabecalho(null);
      }
    }
    fetchEventoCabecalho();
  }, [eventId, location.pathname]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCmdOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  function isActiveSubroute(base: string) {
    return location.pathname.startsWith(base);
  }

  const isAdmin =
    user?.role === 'administrador' ||
    user?.role === 'administrador geral' ||
    user?.role === 'admin';

  const isProfessor = user?.role === 'professor';

  const displayName = user?.full_name || user?.username || 'Usuário';
  const roleLabel = (user?.role || 'usuário').toUpperCase();
  const avatarInitial = displayName.trim().charAt(0).toUpperCase();

  const quickDestinations = [
    ...(!isProfessor
      ? [
          { label: 'Eventos & Concursos', sub: 'Painel principal de concursos', path: '/dashboard' },
          { label: 'Novo Evento / Concurso', sub: 'Cadastrar novo edital', path: '/eventos/novo' },
        ]
      : [{ label: 'Meus Conteúdos', sub: 'Conteúdos atribuídos para elaboração', path: '/conteudos' }]),
    ...(eventId && !isProfessor
      ? [
          { label: 'Cargos do Evento', sub: eventoCabecalho?.nome_evento || 'Evento ativo', path: `/eventos/${eventId}/cargo` },
          { label: 'Conteúdos & Questões', sub: eventoCabecalho?.nome_evento || 'Evento ativo', path: `/eventos/${eventId}/conteudo` },
          { label: 'Montagem de Provas', sub: eventoCabecalho?.nome_evento || 'Evento ativo', path: `/eventos/${eventId}/provas` },
          { label: 'Geração & Simulações', sub: eventoCabecalho?.nome_evento || 'Evento ativo', path: `/eventos/${eventId}/geracao` },
          { label: 'Exportação & Pacotes ZIP', sub: eventoCabecalho?.nome_evento || 'Evento ativo', path: `/eventos/${eventId}/exportacao` },
          { label: 'Gabaritos & Variações', sub: eventoCabecalho?.nome_evento || 'Evento ativo', path: `/eventos/${eventId}/recursos` },
          { label: 'Templates de Prova', sub: eventoCabecalho?.nome_evento || 'Evento ativo', path: `/eventos/${eventId}/templates` },
        ]
      : []),
    ...(isAdmin
      ? [{ label: 'Configurações & Governança', sub: 'Usuários, banca, frases, clientes e temas', path: '/settings' }]
      : []),
  ];

  const filteredDestinations = quickDestinations.filter(
    (d) =>
      d.label.toLowerCase().includes(cmdQuery.toLowerCase()) ||
      d.sub.toLowerCase().includes(cmdQuery.toLowerCase())
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <CssBaseline />

      {/* Top Header Bar (Operan Style) */}
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          width: `calc(100% - ${drawerWidth}px)`,
          ml: `${drawerWidth}px`,
          bgcolor: 'rgba(6, 11, 25, 0.85)',
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
          color: 'text.primary',
        }}
      >
        <Toolbar sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: 64, px: 3 }}>
          {/* Quick Command Search Bar */}
          <Box
            onClick={() => setCmdOpen(true)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              width: { xs: 220, sm: 340 },
              px: 1.75,
              py: 0.85,
              borderRadius: '10px',
              bgcolor: '#0B1325',
              border: '1px solid rgba(148, 163, 184, 0.16)',
              cursor: 'pointer',
              transition: 'border-color 0.18s ease',
              '&:hover': { borderColor: 'rgba(56, 189, 248, 0.45)' },
            }}
          >
            <Stack direction="row" spacing={1.25} alignItems="center">
              <SearchIcon sx={{ fontSize: 18, color: '#64748B' }} />
              <Typography sx={{ fontSize: '0.84rem', color: '#64748B' }}>Ir para tela...</Typography>
            </Stack>
            <Box
              sx={{
                px: 1,
                py: 0.2,
                borderRadius: '6px',
                bgcolor: 'rgba(148, 163, 184, 0.1)',
                border: '1px solid rgba(148, 163, 184, 0.18)',
                fontSize: '0.7rem',
                fontWeight: 600,
                color: '#94A3B8',
              }}
            >
              Ctrl K
            </Box>
          </Box>

          {/* Center & Right Status Pills */}
          <Stack direction="row" spacing={1.5} alignItems="center">
            {!isProfessor && eventId && eventoCabecalho?.nome_evento && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  px: 1.75,
                  py: 0.65,
                  borderRadius: '999px',
                  bgcolor: 'rgba(14, 165, 233, 0.12)',
                  border: '1px solid rgba(56, 189, 248, 0.35)',
                  color: '#38BDF8',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                }}
              >
                <EventIcon sx={{ fontSize: 16 }} />
                <span>{eventoCabecalho.nome_evento}</span>
                {eventoCabecalho.identificador_evento && (
                  <span style={{ opacity: 0.75 }}>({eventoCabecalho.identificador_evento})</span>
                )}
              </Box>
            )}

            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.85,
                px: 1.6,
                py: 0.6,
                borderRadius: '999px',
                bgcolor: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid rgba(245, 158, 11, 0.35)',
                color: '#FBBF24',
                fontSize: '0.78rem',
                fontWeight: 600,
              }}
            >
              <BusinessOutlinedIcon sx={{ fontSize: 15 }} />
              {isAdminGeral ? (
                <Tooltip title="Cliente em gestão: tudo o que você vê e cria fica só nesse cliente. Visão global = todos os clientes.">
                  <Select
                    variant="standard"
                    disableUnderline
                    value={clientes.some((c) => String(c.id) === clienteEmGestao) ? clienteEmGestao : VISAO_GLOBAL}
                    onChange={(e) => trocarCliente(String(e.target.value))}
                    sx={{
                      color: '#FBBF24',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      '& .MuiSelect-icon': { color: '#FBBF24' },
                      '& .MuiSelect-select': { py: 0, pr: '22px !important' },
                    }}
                  >
                    <MenuItem value={VISAO_GLOBAL}>Governança Global (todos os clientes)</MenuItem>
                    {clientes.map((c) => (
                      <MenuItem key={c.id} value={String(c.id)}>{c.name}</MenuItem>
                    ))}
                  </Select>
                </Tooltip>
              ) : (
                <span>{tenantName}</span>
              )}
            </Box>

            <SinoNotificacoes />

            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 0.75,
                px: 1.6,
                py: 0.6,
                borderRadius: '999px',
                bgcolor: 'rgba(14, 165, 233, 0.12)',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                color: '#E2E8F0',
                fontSize: '0.76rem',
                fontWeight: 700,
                letterSpacing: '0.04em',
              }}
            >
              <ShieldOutlinedIcon sx={{ fontSize: 15, color: '#38BDF8' }} />
              <span>{roleLabel}</span>
            </Box>
          </Stack>
        </Toolbar>
      </AppBar>

      {/* Left Sidebar (Operan Pro Dark Navy) */}
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            bgcolor: '#070D1D',
            borderRight: '1px solid rgba(148, 163, 184, 0.12)',
            display: 'flex',
            flexDirection: 'column',
          },
        }}
      >
        {/* Brand Header */}
        <Box
          onClick={() => navigate(isProfessor ? '/conteudos' : '/dashboard')}
          sx={{
            px: 2.5,
            py: 2.25,
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
            cursor: 'pointer',
          }}
        >
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #0EA5E9 0%, #2563EB 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 14px rgba(14, 165, 233, 0.4)',
            }}
          >
            <AutoAwesomeMosaicIcon sx={{ fontSize: 20, color: '#FFF' }} />
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Typography sx={{ fontWeight: 800, fontSize: '1.02rem', letterSpacing: '0.03em', color: '#F8FAFC' }}>
                DIAGPRO
              </Typography>
              <Box
                sx={{
                  px: 0.85,
                  py: 0.1,
                  borderRadius: '6px',
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  color: '#38BDF8',
                  bgcolor: 'rgba(14, 165, 233, 0.14)',
                  border: '1px solid rgba(56, 189, 248, 0.4)',
                }}
              >
                PRO
              </Box>
            </Stack>
            <Typography
              noWrap
              sx={{ fontSize: '0.72rem', color: '#64748B', mt: 0.15 }}
            >
              Gestão de Concursos & Provas
            </Typography>
          </Box>
        </Box>

        {/* Scrollable Navigation Sections */}
        <Box sx={{ overflowY: 'auto', flexGrow: 1, py: 1 }}>
          <Typography sx={sectionTitleSx}>OPERAÇÕES & CONCURSOS</Typography>
          <List disablePadding>
            {!isProfessor ? (
              <ListItem disablePadding>
                <ListItemButton
                  onClick={() => navigate('/dashboard')}
                  sx={navItemSx(location.pathname === '/dashboard' || location.pathname === '/eventos/novo')}
                >
                  <ListItemIcon><EventIcon fontSize="small" /></ListItemIcon>
                  <ListItemText primary="Eventos & Editais" />
                </ListItemButton>
              </ListItem>
            ) : (
              <ListItem disablePadding>
                <ListItemButton
                  onClick={() => navigate('/conteudos')}
                  sx={navItemSx(location.pathname.startsWith('/conteudos'))}
                >
                  <ListItemIcon><SubjectIcon fontSize="small" /></ListItemIcon>
                  <ListItemText primary="Meus Conteúdos" />
                </ListItemButton>
              </ListItem>
            )}
          </List>

          {eventId && !isProfessor && (
            <>
              <Typography sx={sectionTitleSx}>
                EVENTO ATIVO {eventoCabecalho?.identificador_evento ? `• ${eventoCabecalho.identificador_evento}` : ''}
              </Typography>
              <List disablePadding>
                <ListItem disablePadding>
                  <ListItemButton
                    onClick={() => navigate(`/eventos/${eventId}/cargo`)}
                    sx={navItemSx(isActiveSubroute(`/eventos/${eventId}/cargo`))}
                  >
                    <ListItemIcon><WorkIcon fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Cargos & Vagas" />
                  </ListItemButton>
                </ListItem>
                <ListItem disablePadding>
                  <ListItemButton
                    onClick={() => navigate(`/eventos/${eventId}/conteudo`)}
                    sx={navItemSx(isActiveSubroute(`/eventos/${eventId}/conteudo`))}
                  >
                    <ListItemIcon><SubjectIcon fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Conteúdos & Questões" />
                  </ListItemButton>
                </ListItem>
                <ListItem disablePadding>
                  <ListItemButton
                    onClick={() => navigate(`/eventos/${eventId}/provas`)}
                    sx={navItemSx(isActiveSubroute(`/eventos/${eventId}/provas`))}
                  >
                    <ListItemIcon><AssignmentIcon fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Montagem de Provas" />
                  </ListItemButton>
                </ListItem>
                <ListItem disablePadding>
                  <ListItemButton
                    onClick={() => navigate(`/eventos/${eventId}/geracao`)}
                    sx={navItemSx(isActiveSubroute(`/eventos/${eventId}/geracao`))}
                  >
                    <ListItemIcon><BuildIcon fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Geração & Variações" />
                  </ListItemButton>
                </ListItem>
                <ListItem disablePadding>
                  <ListItemButton
                    onClick={() => navigate(`/eventos/${eventId}/exportacao`)}
                    sx={navItemSx(isActiveSubroute(`/eventos/${eventId}/exportacao`))}
                  >
                    <ListItemIcon><FileDownloadIcon fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Exportação & Pacotes" />
                  </ListItemButton>
                </ListItem>
                <ListItem disablePadding>
                  <ListItemButton
                    onClick={() => navigate(`/eventos/${eventId}/recursos`)}
                    sx={navItemSx(isActiveSubroute(`/eventos/${eventId}/recursos`))}
                  >
                    <ListItemIcon><RecordVoiceOverIcon fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Gabaritos & Recursos" />
                  </ListItemButton>
                </ListItem>
                <ListItem disablePadding>
                  <ListItemButton
                    onClick={() => navigate(`/eventos/${eventId}/templates`)}
                    sx={navItemSx(isActiveSubroute(`/eventos/${eventId}/templates`))}
                  >
                    <ListItemIcon><AssignmentIcon fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Templates de Prova" />
                  </ListItemButton>
                </ListItem>
              </List>
            </>
          )}

          {isAdmin && (
            <>
              <Typography sx={sectionTitleSx}>GOVERNANÇA & SISTEMA</Typography>
              <List disablePadding>
                <ListItem disablePadding>
                  <ListItemButton
                    onClick={() => navigate('/settings')}
                    sx={navItemSx(location.pathname.startsWith('/settings'))}
                  >
                    <ListItemIcon><SettingsIcon fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Configurações" />
                  </ListItemButton>
                </ListItem>
              </List>
            </>
          )}
        </Box>

        {/* Bottom User Profile Footer (Operan Style) */}
        <Box
          sx={{
            p: 1.75,
            borderTop: '1px solid rgba(148, 163, 184, 0.12)',
            bgcolor: 'rgba(11, 19, 37, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1.25,
          }}
        >
          <Stack
            direction="row" spacing={1.25} alignItems="center"
            sx={{ minWidth: 0, cursor: 'pointer', borderRadius: 2, '&:hover': { opacity: 0.85 } }}
            title="Minha conta: senha, verificação em duas etapas e sessão"
            onClick={() => navigate('/minha-conta')}
          >
            <Box
              sx={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #6366F1 0%, #0EA5E9 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                fontSize: '0.9rem',
                color: '#FFF',
                flexShrink: 0,
              }}
            >
              {avatarInitial}
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography noWrap sx={{ fontSize: '0.84rem', fontWeight: 600, color: '#F1F5F9' }}>
                {displayName}
              </Typography>
              <Typography noWrap sx={{ fontSize: '0.72rem', color: '#64748B' }}>
                {user?.email || user?.role || tenantName}
              </Typography>
            </Box>
          </Stack>
          <Tooltip title="Sair do sistema">
            <IconButton
              size="small"
              onClick={logout}
              sx={{
                color: '#94A3B8',
                '&:hover': { color: '#EF4444', bgcolor: 'rgba(239, 68, 68, 0.12)' },
              }}
            >
              <LogoutIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Drawer>

      {/* Main Content Area */}
      <Box component="main" sx={{ flexGrow: 1, p: { xs: 2.5, md: 4 }, maxWidth: '100%', overflowX: 'hidden' }}>
        <Toolbar sx={{ minHeight: 64 }} />
        {children}
      </Box>

      {/* Ctrl+K Quick Navigation Dialog */}
      <Dialog
        open={cmdOpen}
        onClose={() => setCmdOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogContent sx={{ p: 2.5 }}>
          <TextField
            autoFocus
            fullWidth
            placeholder="Digite para buscar uma tela ou módulo..."
            value={cmdQuery}
            onChange={(e) => setCmdQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ color: '#38BDF8' }} />
                </InputAdornment>
              ),
            }}
            sx={{ mb: 2 }}
          />
          <List disablePadding>
            {filteredDestinations.map((dest) => (
              <ListItem key={dest.path} disablePadding>
                <ListItemButton
                  onClick={() => {
                    setCmdOpen(false);
                    setCmdQuery('');
                    navigate(dest.path);
                  }}
                  sx={{
                    borderRadius: 2,
                    mb: 0.5,
                    '&:hover': { bgcolor: 'rgba(14, 165, 233, 0.12)' },
                  }}
                >
                  <ListItemText
                    primary={dest.label}
                    secondary={dest.sub}
                    primaryTypographyProps={{ fontWeight: 600, color: '#F1F5F9' }}
                    secondaryTypographyProps={{ color: '#64748B', fontSize: '0.78rem' }}
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </DialogContent>
      </Dialog>
    </Box>
  );
};

export default Layout;
