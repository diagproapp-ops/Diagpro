import React, { useEffect, useState } from 'react';
import {
  Box, Drawer, AppBar, Toolbar, Typography, List, ListItem,
  ListItemButton, ListItemIcon, ListItemText, CssBaseline, Divider
} from '@mui/material';
import EventIcon from '@mui/icons-material/Event';
import LogoutIcon from '@mui/icons-material/Logout';
import SettingsIcon from '@mui/icons-material/Settings';
import WorkIcon from '@mui/icons-material/Work'; // Cargo
import SubjectIcon from '@mui/icons-material/Subject'; // Conteúdo
import AssignmentIcon from '@mui/icons-material/Assignment'; // Provas
import BuildIcon from '@mui/icons-material/Build'; // Geração
import FileDownloadIcon from '@mui/icons-material/FileDownload'; // Exportação
import RecordVoiceOverIcon from '@mui/icons-material/RecordVoiceOver'; // Recursos
import { useAuth } from '../contexts/AuthContext';
import { useLocation, useNavigate } from 'react-router-dom';
import api from '../api';

const drawerWidth = 240;

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { logout, user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [tenantName, setTenantName] = useState<string>('Cliente Exemplo');
  const tenantId = user?.tenant_id ?? localStorage.getItem('tenantId');

  // Dados do evento para mostrar no AppBar
  const [eventoCabecalho, setEventoCabecalho] = useState<{ nome_evento?: string; identificador_evento?: string } | null>(null);

  // Detecta se está em rota de evento /eventos/{id}/...
  const eventoMatch = location.pathname.match(/^\/eventos\/([^/]+)/);
  const eventId = eventoMatch ? eventoMatch[1] : null;

  useEffect(() => {
    const fetchTenantName = async () => {
      if (tenantId) {
        try {
          const response = await api.get(`/admin/clients/${tenantId}`);
          setTenantName(response.data.name);
        } catch {
          setTenantName('Cliente Exemplo');
        }
      }
    };
    fetchTenantName();
  }, [tenantId]);

  // Buscar dados do evento para o AppBar
  useEffect(() => {
    async function fetchEventoCabecalho() {
      if (!eventId) {
        setEventoCabecalho(null);
        return;
      }
      try {
        // Busca apenas nome e identificador
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

  // Função para saber se está em rota de subfunção
  function isActiveSubroute(base: string) {
    return location.pathname.startsWith(base);
  }

  // Defina o(s) papel(is) de administrador
  const isAdmin =
    user?.role === 'administrador' ||
    user?.role === 'administrador geral' ||
    user?.role === 'admin';

  const isProfessor = user?.role === 'professor';

  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />
      <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
        <Toolbar sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          width: '100%',
          minHeight: 64,
        }}>
          {/* Esquerda: DiagPro */}
          <Typography variant="h6" noWrap component="div">
            DiagPro
          </Typography>

          {/* Centro: Evento aberto (não mostra para professor) */}
          <Box sx={{ flexGrow: 1, textAlign: 'center' }}>
            {!isProfessor && eventId && eventoCabecalho?.nome_evento && (
              <Typography variant="h6" sx={{ color: "#fff", fontWeight: 'bold' }}>
                {eventoCabecalho.nome_evento}
                <span style={{ color: '#e3e3e3', fontWeight: 'normal', marginLeft: 12 }}>
                  ({eventoCabecalho.identificador_evento})
                </span>
              </Typography>
            )}
          </Box>

          {/* Direita: Cliente e Usuário */}
          <Box sx={{ textAlign: 'right' }}>
            <Typography variant="subtitle1">
              Cliente: {tenantName}
            </Typography>
            <Typography variant="subtitle2">
              Usuário: {user?.full_name ?? user?.username ?? 'Usuário Logado'}
            </Typography>
          </Box>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: { width: drawerWidth, boxSizing: 'border-box' },
        }}
      >
        <Toolbar />
        <Box sx={{ overflow: 'auto', display: 'flex', flexDirection: 'column', height: '100%' }}>
          <List>
            {/* Só mostra o botão de Eventos para quem NÃO é professor */}
            {!isProfessor && (
              <ListItem key="eventos" disablePadding>
                <ListItemButton
                  selected={location.pathname.startsWith('/dashboard') || location.pathname.startsWith('/eventos')}
                  onClick={() => navigate('/dashboard')}
                >
                  <ListItemIcon><EventIcon /></ListItemIcon>
                  <ListItemText primary="Eventos" />
                </ListItemButton>
              </ListItem>
            )}
          </List>
          {/* Botões das funções do evento, destacados */}
          {eventId && !isProfessor && (
            <>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" sx={{ ml: 2, mb: 1, color: "primary.main", fontWeight: 'bold', letterSpacing: 1 }}>
                Gerenciar Evento
              </Typography>
            </>
          )}
          <List>
            {/* Para professor, só mostra Conteúdo sem vincular ao evento */}
            {isProfessor ? (
              <ListItem key="conteudo" disablePadding>
                <ListItemButton
                  selected={location.pathname.startsWith('/eventos') || location.pathname.startsWith('/conteudos')}
                  onClick={() => navigate('/conteudos')}
                  sx={{
                    my: 0.5,
                    borderRadius: 2,
                    bgcolor: location.pathname.startsWith('/conteudos') ? "#e3f2fd" : undefined,
                    '&:hover': {
                      bgcolor: "#bbdefb",
                      '.MuiListItemIcon-root': { color: "#1976d2" }
                    }
                  }}
                >
                  <ListItemIcon sx={{ color: "#1976d2" }}><SubjectIcon /></ListItemIcon>
                  <ListItemText primary="Conteúdo" />
                </ListItemButton>
              </ListItem>
            ) : (
              <>
                {/* Botões para quem NÃO é professor */}
                {eventId && (
                  <>
                    {/* Cargo */}
                    <ListItem key="cargo" disablePadding>
                      <ListItemButton
                        selected={isActiveSubroute(`/eventos/${eventId}/cargo`)}
                        onClick={() => navigate(`/eventos/${eventId}/cargo`)}
                        sx={{
                          my: 0.5,
                          borderRadius: 2,
                          bgcolor: isActiveSubroute(`/eventos/${eventId}/cargo`) ? "#e3f2fd" : undefined,
                          '&:hover': {
                            bgcolor: "#bbdefb",
                            '.MuiListItemIcon-root': { color: "#1976d2" }
                          }
                        }}
                      >
                        <ListItemIcon sx={{ color: "#1976d2" }}><WorkIcon /></ListItemIcon>
                        <ListItemText primary="Cargo" />
                      </ListItemButton>
                    </ListItem>
                    {/* Conteúdo */}
                    <ListItem key="conteudo" disablePadding>
                      <ListItemButton
                        selected={isActiveSubroute(`/eventos/${eventId}/conteudo`)}
                        onClick={() => navigate(`/eventos/${eventId}/conteudo`)}
                        sx={{
                          my: 0.5,
                          borderRadius: 2,
                          bgcolor: isActiveSubroute(`/eventos/${eventId}/conteudo`) ? "#e3f2fd" : undefined,
                          '&:hover': {
                            bgcolor: "#bbdefb",
                            '.MuiListItemIcon-root': { color: "#1976d2" }
                          }
                        }}
                      >
                        <ListItemIcon sx={{ color: "#1976d2" }}><SubjectIcon /></ListItemIcon>
                        <ListItemText primary="Conteúdo" />
                      </ListItemButton>
                    </ListItem>
                    {/* Provas */}
                    <ListItem key="provas" disablePadding>
                      <ListItemButton
                        selected={isActiveSubroute(`/eventos/${eventId}/provas`)}
                        onClick={() => navigate(`/eventos/${eventId}/provas`)}
                        sx={{
                          my: 0.5,
                          borderRadius: 2,
                          bgcolor: isActiveSubroute(`/eventos/${eventId}/provas`) ? "#e3f2fd" : undefined,
                          '&:hover': {
                            bgcolor: "#bbdefb",
                            '.MuiListItemIcon-root': { color: "#1976d2" }
                          }
                        }}
                      >
                        <ListItemIcon sx={{ color: "#1976d2" }}><AssignmentIcon /></ListItemIcon>
                        <ListItemText primary="Provas" />
                      </ListItemButton>
                    </ListItem>
                    {/* Geração */}
                    <ListItem key="geracao" disablePadding>
                      <ListItemButton
                        selected={isActiveSubroute(`/eventos/${eventId}/geracao`)}
                        onClick={() => navigate(`/eventos/${eventId}/geracao`)}
                        sx={{
                          my: 0.5,
                          borderRadius: 2,
                          bgcolor: isActiveSubroute(`/eventos/${eventId}/geracao`) ? "#e3f2fd" : undefined,
                          '&:hover': {
                            bgcolor: "#bbdefb",
                            '.MuiListItemIcon-root': { color: "#1976d2" }
                          }
                        }}
                      >
                        <ListItemIcon sx={{ color: "#1976d2" }}><BuildIcon /></ListItemIcon>
                        <ListItemText primary="Geração" />
                      </ListItemButton>
                    </ListItem>
                    {/* Exportação */}
                    <ListItem key="exportacao" disablePadding>
                      <ListItemButton
                        selected={isActiveSubroute(`/eventos/${eventId}/exportacao`)}
                        onClick={() => navigate(`/eventos/${eventId}/exportacao`)}
                        sx={{
                          my: 0.5,
                          borderRadius: 2,
                          bgcolor: isActiveSubroute(`/eventos/${eventId}/exportacao`) ? "#e3f2fd" : undefined,
                          '&:hover': {
                            bgcolor: "#bbdefb",
                            '.MuiListItemIcon-root': { color: "#1976d2" }
                          }
                        }}
                      >
                        <ListItemIcon sx={{ color: "#1976d2" }}><FileDownloadIcon /></ListItemIcon>
                        <ListItemText primary="Exportação" />
                      </ListItemButton>
                    </ListItem>
                    {/* Recursos */}
                    <ListItem key="recursos" disablePadding>
                      <ListItemButton
                        selected={isActiveSubroute(`/eventos/${eventId}/recursos`)}
                        onClick={() => navigate(`/eventos/${eventId}/recursos`)}
                        sx={{
                          my: 0.5,
                          borderRadius: 2,
                          bgcolor: isActiveSubroute(`/eventos/${eventId}/recursos`) ? "#e3f2fd" : undefined,
                          '&:hover': {
                            bgcolor: "#bbdefb",
                            '.MuiListItemIcon-root': { color: "#1976d2" }
                          }
                        }}
                      >
                        <ListItemIcon sx={{ color: "#1976d2" }}><RecordVoiceOverIcon /></ListItemIcon>
                        <ListItemText primary="Recursos" />
                      </ListItemButton>
                    </ListItem>
                  </>
                )}
              </>
            )}
          </List>
          <Box sx={{ flexGrow: 1 }} />
          <List>
            {/* Botão de Configurações só para administrador */}
            {isAdmin && (
              <ListItem key="settings" disablePadding>
                <ListItemButton
                  selected={location.pathname.startsWith('/settings')}
                  onClick={() => navigate('/settings')}
                >
                  <ListItemIcon><SettingsIcon /></ListItemIcon>
                  <ListItemText primary="Configurações" />
                </ListItemButton>
              </ListItem>
            )}
            <ListItem key="sair" disablePadding>
              <ListItemButton onClick={logout}>
                <ListItemIcon><LogoutIcon /></ListItemIcon>
                <ListItemText primary="Sair" />
              </ListItemButton>
            </ListItem>
          </List>
        </Box>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
};

export default Layout;