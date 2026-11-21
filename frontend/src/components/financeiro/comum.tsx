import React, { useState } from 'react';
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Paper, TextField, Typography,
} from '@mui/material';
import api from '../../api';

export const moeda = (v?: number | null) =>
  (Number(v) || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
export const dataBR = (iso?: string | null) => (iso ? new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString('pt-BR') : '—');
export const dataHoraBR = (iso?: string | null) => (iso ? new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '—');

export function erroApi(e: any, padrao: string): string {
  const d = e?.response?.data?.detail;
  if (typeof d === 'string') return d;
  if (d?.mensagem) return [d.mensagem, ...(d.problemas || [])].join(' ');
  if (Array.isArray(d)) return 'Confira os campos preenchidos.';
  return padrao;
}

export const BarraUso: React.FC<{ rotulo: string; uso: number; limite: number | null }> = ({ rotulo, uso, limite }) => {
  const pct = limite ? Math.min(100, Math.round((uso / limite) * 100)) : 0;
  const cor = !limite ? '#64748b' : pct >= 100 ? '#ef4444' : pct >= 80 ? '#f59e0b' : '#10b981';
  return (
    <Box sx={{ mb: 1.25 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Typography variant="body2">{rotulo}</Typography>
        <Typography variant="body2" fontWeight={700}>{uso}{limite ? ` de ${limite}` : ' (sem limite)'}</Typography>
      </Box>
      <Box sx={{ height: 8, borderRadius: 4, bgcolor: 'action.hover', overflow: 'hidden' }}>
        <Box sx={{ width: `${limite ? pct : 100}%`, height: '100%', bgcolor: cor, opacity: limite ? 1 : 0.25 }} />
      </Box>
    </Box>
  );
};

type Cor = 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info';
const STATUS: Record<string, [string, Cor]> = {
  rascunho: ['Rascunho', 'default'], enviado: ['Aguardando aceite', 'warning'], aceito: ['Aceito', 'success'],
  recusado: ['Recusado', 'error'], encerrado: ['Encerrado', 'info'], cancelado: ['Cancelado', 'default'],
  prevista: ['Prevista', 'default'], liberada: ['Liberada', 'warning'], paga: ['Paga', 'info'], confirmada: ['Recebida', 'success'],
  cancelada: ['Cancelada', 'default'], enviada: ['Aguardando resposta', 'warning'], aceita: ['Aceita', 'success'],
  recusada: ['Recusada', 'error'], substituida: ['Substituída', 'default'], pendente: ['Aguardando aceite', 'warning'],
  aberta: ['Em aberto', 'warning'], atrasada: ['Atrasada', 'error'], em_analise: ['Comprovante em análise', 'info'],
};
export const StatusChip: React.FC<{ status: string; size?: 'small' | 'medium' }> = ({ status, size = 'small' }) => {
  const [rotulo, cor] = STATUS[status] || [status, 'default'];
  return <Chip size={size} color={cor} label={rotulo} variant={cor === 'default' ? 'outlined' : 'filled'} />;
};

export const Indicador: React.FC<{ rotulo: string; valor: React.ReactNode; detalhe?: React.ReactNode; cor?: string }> = ({ rotulo, valor, detalhe, cor }) => (
  <Paper variant="outlined" sx={{ p: 2, borderRadius: 3, minWidth: 0 }}>
    <Typography variant="caption" color="text.secondary" noWrap display="block">{rotulo}</Typography>
    <Typography fontWeight={800} fontSize={24} sx={{ color: cor }} noWrap>{valor}</Typography>
    {detalhe && <Typography variant="caption" color="text.secondary" display="block">{detalhe}</Typography>}
  </Paper>
);

export async function baixar(url: string, nome: string) {
  const { data } = await api.get(url, { responseType: 'blob' });
  const link = URL.createObjectURL(data as Blob);
  const a = document.createElement('a');
  a.href = link; a.download = nome; a.click();
  setTimeout(() => URL.revokeObjectURL(link), 2000);
}

// Aceite eletrônico: a senha pessoal confirma que é a própria pessoa (data, hora, IP e o hash do documento ficam registrados).
export const DialogoAceite: React.FC<{
  aberto: boolean; titulo: string; texto: React.ReactNode; onConfirmar: (senha: string) => Promise<void>; onFechar: () => void;
}> = ({ aberto, titulo, texto, onConfirmar, onFechar }) => {
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const confirmar = async () => {
    setEnviando(true); setErro(null);
    try { await onConfirmar(senha); setSenha(''); } catch (e: any) { setErro(erroApi(e, 'Não foi possível registrar o aceite.')); }
    finally { setEnviando(false); }
  };
  return (
    <Dialog open={aberto} onClose={onFechar} maxWidth="sm" fullWidth>
      <DialogTitle>{titulo}</DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 2 }}>{texto}</Box>
        <Alert severity="info" sx={{ mb: 2 }}>
          O aceite vale como assinatura eletrônica: ficam registrados você, a data e a hora, o endereço IP e o código do documento.
        </Alert>
        <TextField type="password" label="Sua senha" fullWidth autoFocus value={senha} onChange={(e) => setSenha(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && senha) confirmar(); }} />
        {erro && <Alert severity="error" sx={{ mt: 2 }}>{erro}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onFechar}>Cancelar</Button>
        <Button variant="contained" color="success" disabled={!senha || enviando} onClick={confirmar}>{enviando ? 'Registrando...' : 'Li e aceito'}</Button>
      </DialogActions>
    </Dialog>
  );
};

export const DialogoTexto: React.FC<{
  aberto: boolean; titulo: string; rotulo: string; minimo?: number; botao: string; cor?: 'error' | 'primary';
  onConfirmar: (texto: string) => Promise<void>; onFechar: () => void;
}> = ({ aberto, titulo, rotulo, minimo = 0, botao, cor = 'primary', onConfirmar, onFechar }) => {
  const [texto, setTexto] = useState('');
  const [erro, setErro] = useState<string | null>(null);
  const confirmar = async () => {
    setErro(null);
    try { await onConfirmar(texto); setTexto(''); } catch (e: any) { setErro(erroApi(e, 'Não foi possível concluir.')); }
  };
  return (
    <Dialog open={aberto} onClose={onFechar} maxWidth="sm" fullWidth>
      <DialogTitle>{titulo}</DialogTitle>
      <DialogContent>
        <TextField label={rotulo} fullWidth multiline minRows={3} sx={{ mt: 1 }} value={texto} onChange={(e) => setTexto(e.target.value)} />
        {erro && <Alert severity="error" sx={{ mt: 2 }}>{erro}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onFechar}>Cancelar</Button>
        <Button variant="contained" color={cor} disabled={texto.trim().length < minimo} onClick={confirmar}>{botao}</Button>
      </DialogActions>
    </Dialog>
  );
};
