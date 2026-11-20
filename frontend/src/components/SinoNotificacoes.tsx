import React, { useCallback, useEffect, useState } from 'react';
import {
  Badge, Box, Button, Divider, IconButton, List, ListItemButton, ListItemText, Popover, Tooltip, Typography,
} from '@mui/material';
import NotificationsNoneOutlinedIcon from '@mui/icons-material/NotificationsNoneOutlined';
import { useNavigate } from 'react-router-dom';
import api from '../api';

type Aviso = { id: number; tipo: string; titulo: string; mensagem: string; link: string | null; criado_em: string; lida: boolean };

function quando(iso: string): string {
  const d = new Date(iso);
  const min = Math.round((Date.now() - d.getTime()) / 60000);
  if (min < 1) return 'agora';
  if (min < 60) return `há ${min} min`;
  if (min < 24 * 60) return `há ${Math.round(min / 60)} h`;
  return d.toLocaleDateString('pt-BR');
}

// Sino de avisos no topo da tela (atualiza a cada minuto)
const SinoNotificacoes: React.FC = () => {
  const navigate = useNavigate();
  const [ancora, setAncora] = useState<HTMLElement | null>(null);
  const [naoLidas, setNaoLidas] = useState(0);
  const [itens, setItens] = useState<Aviso[]>([]);

  const contar = useCallback(() => {
    api.get('/notificacoes/contagem').then(({ data }) => setNaoLidas(data.nao_lidas || 0)).catch(() => {});
  }, []);

  useEffect(() => {
    contar();
    const t = window.setInterval(contar, 60000);
    return () => window.clearInterval(t);
  }, [contar]);

  const abrir = async (e: React.MouseEvent<HTMLElement>) => {
    setAncora(e.currentTarget);
    try {
      const { data } = await api.get('/notificacoes');
      setItens(data.itens || []);
      setNaoLidas(data.nao_lidas || 0);
    } catch { /* sem avisos */ }
  };

  const clicar = async (a: Aviso) => {
    if (!a.lida) {
      await api.post(`/notificacoes/${a.id}/lida`).catch(() => {});
      setItens(itens.map(x => (x.id === a.id ? { ...x, lida: true } : x)));
      setNaoLidas(n => Math.max(0, n - 1));
    }
    if (a.link) { setAncora(null); navigate(a.link); }
  };

  const marcarTodas = async () => {
    await api.post('/notificacoes/marcar-todas').catch(() => {});
    setItens(itens.map(x => ({ ...x, lida: true })));
    setNaoLidas(0);
  };

  return (
    <>
      <Tooltip title="Avisos">
        <IconButton onClick={abrir} size="small" sx={{ color: '#E2E8F0' }} aria-label="Avisos">
          <Badge badgeContent={naoLidas} color="error" max={99}>
            <NotificationsNoneOutlinedIcon />
          </Badge>
        </IconButton>
      </Tooltip>
      <Popover open={!!ancora} anchorEl={ancora} onClose={() => setAncora(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        PaperProps={{ sx: { width: 380, maxWidth: '95vw', maxHeight: 480 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2, py: 1.25 }}>
          <Typography fontWeight={700}>Avisos</Typography>
          {naoLidas > 0 && <Button size="small" onClick={marcarTodas}>Marcar todos como lidos</Button>}
        </Box>
        <Divider />
        {!itens.length ? (
          <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>Nenhum aviso por enquanto.</Typography>
        ) : (
          <List dense disablePadding>
            {itens.map(a => (
              <ListItemButton key={a.id} onClick={() => clicar(a)} sx={{ alignItems: 'flex-start', opacity: a.lida ? 0.65 : 1 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', mt: 1, mr: 1.25, flexShrink: 0, bgcolor: a.lida ? 'transparent' : 'primary.main' }} />
                <ListItemText
                  primary={<Typography variant="body2" fontWeight={a.lida ? 400 : 700}>{a.titulo}</Typography>}
                  secondary={<>
                    <Typography component="span" variant="caption" sx={{ display: 'block', whiteSpace: 'pre-line' }}>{a.mensagem}</Typography>
                    <Typography component="span" variant="caption" color="text.secondary">{quando(a.criado_em)}</Typography>
                  </>}
                />
              </ListItemButton>
            ))}
          </List>
        )}
      </Popover>
    </>
  );
};

export default SinoNotificacoes;
