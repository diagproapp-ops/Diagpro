import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, InputAdornment, Paper, Stack,
  Switch, TextField, Tooltip, Typography,
} from '@mui/material';
import { CheckCircle, Close, ContentCopy, PersonAddAlt1 } from '@mui/icons-material';
import api from '../../api';
import { useAuth } from '../../contexts/AuthContext';
import { FotoAvatar, mensagemDaApi } from '../../components/usuarios/comum';

type Admin = { id: number; username: string; full_name?: string | null; email?: string | null; status?: string | null;
  totp_ativo?: boolean; tem_foto?: boolean; avatar_url?: string | null };
type Convite = { id: number; email: string; nome?: string | null; expira_em: string };

const situacao = (a: Admin) => (a.status || 'ativo').toLowerCase();

// Administradores gerais da plataforma (suporte às bancas): convite por link, aprovação por outro administrador geral.
// Ser administrador geral não abre questões de evento sem a senha do evento.
export default function PlataformaAdminsTab() {
  const { user } = useAuth();
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [convites, setConvites] = useState<Convite[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [novo, setNovo] = useState<{ email: string; nome: string } | null>(null);
  const [link, setLink] = useState<{ link: string; enviado: boolean } | null>(null);

  const carregar = useCallback(() => {
    api.get<Admin[]>('/plataforma/administradores').then(({ data }) => setAdmins(data))
      .catch((e) => setErro(mensagemDaApi(e, 'Não foi possível carregar.')));
    api.get<Convite[]>('/plataforma/administradores/convites').then(({ data }) => setConvites(data)).catch(() => setConvites([]));
  }, []);
  useEffect(() => { carregar(); }, [carregar]);

  const acao = async (fn: () => Promise<any>, ok: string) => {
    setErro(null); setMsg(null);
    try { await fn(); setMsg(ok); carregar(); } catch (e: any) { setErro(mensagemDaApi(e, 'Não foi possível concluir.')); }
  };
  const convidar = async () => {
    if (!novo) return;
    setErro(null);
    try {
      const { data } = await api.post('/plataforma/administradores/convites', { email: novo.email.trim(), nome: novo.nome.trim() || null });
      setNovo(null);
      setLink({ link: data.link, enviado: data.enviado_por_email });
      carregar();
    } catch (e: any) { setErro(mensagemDaApi(e, 'Não foi possível criar o convite.')); }
  };

  const pendentes = admins.filter(a => situacao(a) === 'pendente');
  const demais = admins.filter(a => situacao(a) !== 'pendente');

  return (
    <Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ sm: 'center' }} spacing={1.5} sx={{ mb: 2 }}>
        <Box>
          <Typography variant="h6" fontWeight={800}>Administradores da plataforma</Typography>
          <Typography variant="body2" color="text.secondary">
            Equipe de suporte às bancas. Cada pessoa tem conta própria, foto e 2FA. Nem o administrador geral abre questões
            de um evento sem a senha dele.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<PersonAddAlt1 />} onClick={() => setNovo({ email: '', nome: '' })} sx={{ whiteSpace: 'nowrap' }}>
          Convidar administrador geral
        </Button>
      </Stack>
      {erro && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErro(null)}>{erro}</Alert>}
      {msg && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMsg(null)}>{msg}</Alert>}

      {pendentes.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2.5, borderColor: 'warning.main' }}>
          <Typography fontWeight={800} sx={{ mb: 1.5 }}>Aguardando aprovação ({pendentes.length})</Typography>
          {pendentes.map(a => (
            <Stack key={a.id} direction="row" spacing={2} alignItems="center" sx={{ py: 1 }}>
              <FotoAvatar avatarUrl={a.avatar_url} nome={a.full_name || a.username} tamanho={64} />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography fontWeight={700}>{a.full_name || a.username}</Typography>
                <Typography variant="body2" color="text.secondary" noWrap>{a.username} · {a.email}</Typography>
              </Box>
              <Button variant="contained" color="success" startIcon={<CheckCircle />} disabled={!a.tem_foto}
                onClick={() => acao(() => api.patch(`/plataforma/administradores/${a.id}`, { status: 'ativo' }), `${a.full_name || a.username} aprovado(a).`)}>
                Aprovar
              </Button>
            </Stack>
          ))}
        </Paper>
      )}

      <Paper variant="outlined" sx={{ borderRadius: 2 }}>
        {demais.map(a => {
          const souEu = a.username === user?.username;
          return (
            <Stack key={a.id} direction="row" spacing={2} alignItems="center" sx={{ px: 2, py: 1.25, borderBottom: 1, borderColor: 'divider' }}>
              <FotoAvatar avatarUrl={a.avatar_url} nome={a.full_name || a.username} />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography fontWeight={700} noWrap>{a.full_name || a.username}{souEu ? ' (você)' : ''}</Typography>
                <Typography variant="caption" color="text.secondary" noWrap display="block">{a.username} · {a.email}</Typography>
              </Box>
              <Chip size="small" variant="outlined" label={a.totp_ativo ? '2FA ativo' : '2FA pendente'} color={a.totp_ativo ? 'success' : 'warning'} />
              <Tooltip title={souEu ? 'Você não pode desativar a si mesmo' : situacao(a) === 'ativo' ? 'Desativar (sai na hora)' : 'Reativar'}>
                <span>
                  <Switch checked={situacao(a) === 'ativo'} disabled={souEu}
                    onChange={() => acao(() => api.patch(`/plataforma/administradores/${a.id}`, { status: situacao(a) === 'ativo' ? 'inativo' : 'ativo' }),
                      situacao(a) === 'ativo' ? 'Administrador desativado: os acessos dele foram encerrados.' : 'Administrador reativado.')} />
                </span>
              </Tooltip>
            </Stack>
          );
        })}
      </Paper>

      {convites.length > 0 && (
        <Box sx={{ mt: 2.5 }}>
          <Typography fontWeight={800} sx={{ mb: 1 }}>Convites enviados</Typography>
          {convites.map(c => (
            <Stack key={c.id} direction="row" spacing={1.5} alignItems="center" sx={{ py: 0.5 }}>
              <Typography sx={{ flex: 1 }}>{c.nome ? `${c.nome} · ` : ''}{c.email}</Typography>
              <Typography variant="caption" color="text.secondary">até {new Date(c.expira_em).toLocaleDateString('pt-BR')}</Typography>
              <Tooltip title="Cancelar convite">
                <IconButton size="small" onClick={() => acao(() => api.delete(`/plataforma/administradores/convites/${c.id}`), 'Convite cancelado.')}><Close /></IconButton>
              </Tooltip>
            </Stack>
          ))}
        </Box>
      )}

      <Dialog open={!!novo} onClose={() => setNovo(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Convidar administrador geral</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            A pessoa recebe um link (7 dias, uso único) para se cadastrar com os próprios dados, senha e foto; no primeiro
            acesso cadastra o 2FA. Depois um administrador geral aprova aqui. Use um e-mail só para isso (não o de uma conta de banca).
          </Typography>
          <TextField label="E-mail *" type="email" fullWidth margin="normal" value={novo?.email || ''}
            onChange={(e) => setNovo(n => (n ? { ...n, email: e.target.value } : n))} />
          <TextField label="Nome (opcional)" fullWidth margin="normal" value={novo?.nome || ''}
            onChange={(e) => setNovo(n => (n ? { ...n, nome: e.target.value } : n))} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNovo(null)}>Cancelar</Button>
          <Button variant="contained" onClick={convidar} disabled={!/^\S+@\S+\.\S+$/.test((novo?.email || '').trim())}>Gerar convite</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!link} onClose={() => setLink(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Convite de administrador geral</DialogTitle>
        <DialogContent>
          <Alert severity={link?.enviado ? 'success' : 'info'} sx={{ mb: 2 }}>
            {link?.enviado ? 'Enviado por e-mail. Se preferir, copie e mande por outro canal seguro.'
              : 'O e-mail do sistema não está configurado: copie o link e envie por um canal seguro.'}
          </Alert>
          <TextField fullWidth value={link?.link || ''} InputProps={{
            readOnly: true,
            endAdornment: (
              <InputAdornment position="end">
                <IconButton onClick={() => { navigator.clipboard?.writeText(link?.link || ''); setMsg('Link copiado.'); }}><ContentCopy /></IconButton>
              </InputAdornment>
            ),
          }} />
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>O link aparece só agora; não fica guardado.</Typography>
        </DialogContent>
        <DialogActions><Button variant="contained" onClick={() => setLink(null)}>Fechar</Button></DialogActions>
      </Dialog>
    </Box>
  );
}
