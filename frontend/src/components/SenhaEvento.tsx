import React, { useEffect, useState } from 'react';
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Paper, TextField, Typography,
} from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../contexts/AuthContext';
import Layout from './Layout';

function mensagem(e: any, padrao: string): string {
  const d = e?.response?.data?.detail;
  if (typeof d === 'string') return d;
  if (d?.mensagem) return d.mensagem;
  return padrao;
}

// Pede a senha do evento e libera o evento NESTA sessão (o servidor guarda; a senha não fica no navegador).
export const DialogoSenhaEvento: React.FC<{
  aberto: boolean;
  eventoId: string;
  nomeEvento?: string | null;
  onLiberado: () => void;
  onCancelar: () => void;
}> = ({ aberto, eventoId, nomeEvento, onLiberado, onCancelar }) => {
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { if (aberto) { setSenha(''); setErro(null); } }, [aberto]);

  const liberar = async () => {
    setEnviando(true);
    setErro(null);
    try {
      await api.post(`/revisao/eventos/${eventoId}/liberar`, { senha });
      setSenha('');
      onLiberado();
    } catch (e: any) {
      setErro(mensagem(e, 'Senha do evento inválida.'));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Dialog open={aberto} onClose={onCancelar} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <LockOutlinedIcon fontSize="small" /> Senha do evento
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {nomeEvento ? <><b>{nomeEvento}</b>: as</> : 'As'} questões deste evento só abrem com a senha dele. Ela vale
          enquanto você estiver neste acesso.
        </Typography>
        <TextField autoFocus fullWidth type="password" label="Senha do evento" value={senha}
          autoComplete="off" onChange={(e) => setSenha(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && senha && !enviando) liberar(); }} />
        {erro && <Alert severity="error" sx={{ mt: 2 }}>{erro}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancelar}>Cancelar</Button>
        <Button variant="contained" onClick={liberar} disabled={!senha || enviando}>{enviando ? 'Conferindo...' : 'Liberar'}</Button>
      </DialogActions>
    </Dialog>
  );
};

const PERFIS_SEMPRE = ['administrador geral', 'revisor'];

// Protege uma tela de evento: só mostra (e só busca) o conteúdo depois da senha do evento.
// sempre=true (telas de revisão): para todos os perfis. Sem ele: só para administrador geral e revisor.
const GuardaSenhaEvento: React.FC<{ children: React.ReactNode; sempre?: boolean }> = ({ children, sempre = false }) => {
  const { eventId = '' } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const precisa = sempre || PERFIS_SEMPRE.includes(user?.role || '');
  const [estado, setEstado] = useState<'conferindo' | 'liberado' | 'bloqueado'>(precisa ? 'conferindo' : 'liberado');

  useEffect(() => {
    if (!precisa) { setEstado('liberado'); return; }
    setEstado('conferindo');
    api.get(`/revisao/eventos/${eventId}/liberado`)
      .then(({ data }) => setEstado(data?.liberado ? 'liberado' : 'bloqueado'))
      .catch(() => setEstado('bloqueado'));
  }, [eventId, precisa]);

  if (estado === 'liberado') return <>{children}</>;
  return (
    <Layout>
      <Paper sx={{ p: 4, borderRadius: 3, maxWidth: 560, mx: 'auto', mt: 4, textAlign: 'center' }}>
        {estado === 'conferindo' ? <CircularProgress /> : (
          <Box>
            <LockOutlinedIcon sx={{ fontSize: 42, color: 'warning.main' }} />
            <Typography variant="h6" fontWeight={800} sx={{ mt: 1 }}>Evento protegido</Typography>
            <Typography variant="body2" color="text.secondary">Digite a senha do evento para abrir as questões.</Typography>
            <Button sx={{ mt: 2 }} onClick={() => navigate(-1)}>Voltar</Button>
          </Box>
        )}
      </Paper>
      <DialogoSenhaEvento aberto={estado === 'bloqueado'} eventoId={eventId}
        onLiberado={() => setEstado('liberado')} onCancelar={() => navigate(-1)} />
    </Layout>
  );
};

export default GuardaSenhaEvento;
