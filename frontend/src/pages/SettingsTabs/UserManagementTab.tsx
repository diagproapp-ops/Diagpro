import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, InputAdornment,
  ListItemIcon, Menu, MenuItem, Paper, Stack, Switch, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Tooltip,
  Typography,
} from '@mui/material';
import {
  Edit, Delete, PhonelinkLock, Logout, PersonOff, PersonAddAlt1, ContentCopy, LockReset, CheckCircle, Block, Close, MoreVert,
} from '@mui/icons-material';
import api from '../../api';
import { useAuth } from '../../contexts/AuthContext';
import { FotoAvatar, ROTULO_PAPEL, mensagemDaApi, useFoto } from '../../components/usuarios/comum';

type Usuario = {
  id: number;
  username: string;
  email?: string | null;
  full_name?: string | null;
  cpf?: string | null;
  phone?: string | null;
  department?: string | null;
  institution?: string | null;
  birth_date?: string | null;
  status?: string | null;
  notes?: string | null;
  address?: string | null;
  avatar_url?: string | null;
  specialty?: string | null;
  pix_key?: string | null;
  role: string;
  tenant_id?: number | null;
  totp_ativo?: boolean;
  tem_foto?: boolean;
  outra_banca?: boolean | null;
};

type Convite = { id: number; email: string; nome?: string | null; role?: string | null; tipo: string; expira_em: string; estado: string };

const PAPEIS_CONVITE = ['professor', 'revisor', 'diagramador', 'administrador'];
const CAMPOS_EDITAVEIS: [keyof Usuario, string][] = [
  ['full_name', 'Nome completo'], ['email', 'E-mail'], ['phone', 'Telefone'], ['cpf', 'CPF'], ['department', 'Departamento'],
  ['institution', 'Instituição'], ['specialty', 'Especialidade'], ['birth_date', 'Data de nascimento'], ['address', 'Endereço'],
  ['pix_key', 'Chave Pix'], ['notes', 'Observações'],
];

const situacao = (u: Usuario) => (u.status || 'ativo').toLowerCase();

const FotoGrande: React.FC<{ avatarUrl?: string | null }> = ({ avatarUrl }) => {
  const src = useFoto(avatarUrl);
  return src ? (
    <Box component="img" src={src} alt="Foto do usuário" draggable={false}
      onContextMenu={(e: React.MouseEvent) => e.preventDefault()} sx={{ width: '100%', minWidth: 280, borderRadius: 2, display: 'block' }} />
  ) : <Typography color="text.secondary">Carregando...</Typography>;
};

// Usuários da banca: ninguém é criado com senha escolhida pelo administrador. Ele convida por link; a pessoa se
// cadastra com os próprios dados, senha e foto (obrigatória); o administrador confere a foto e aprova.
// Professores e revisores podem vir de outra banca (uma conta, várias bancas): aqui só se controla o vínculo.
export default function UserManagementTab() {
  const { user } = useAuth();
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [convites, setConvites] = useState<Convite[]>([]);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [convidar, setConvidar] = useState(false);
  const [novo, setNovo] = useState({ email: '', nome: '', role: 'professor' });
  const [linkGerado, setLinkGerado] = useState<{ titulo: string; link: string; enviado: boolean } | null>(null);
  const [editar, setEditar] = useState<Usuario | null>(null);
  const [fotoAberta, setFotoAberta] = useState<Usuario | null>(null);
  const [menu, setMenu] = useState<{ el: HTMLElement; u: Usuario } | null>(null);
  const semBanca = user?.role === 'administrador geral' && !user?.tenant_id;

  const carregar = useCallback(() => {
    setCarregando(true);
    api.get<Usuario[]>('/users/')
      .then(({ data }) => setUsuarios(data))
      .catch((e) => setErro(mensagemDaApi(e, 'Falha ao buscar usuários.')))
      .finally(() => setCarregando(false));
    if (!semBanca) api.get<Convite[]>('/convites').then(({ data }) => setConvites(data)).catch(() => setConvites([]));
  }, [semBanca]);
  useEffect(() => { carregar(); }, [carregar]);

  const pendentes = useMemo(() => usuarios.filter(u => situacao(u) === 'pendente'), [usuarios]);
  const demais = useMemo(() => usuarios.filter(u => situacao(u) !== 'pendente'), [usuarios]);
  const convitesAbertos = convites.filter(c => c.estado === 'pendente' && c.tipo === 'cadastro');

  const acao = async (fn: () => Promise<any>, ok: string, falha: string) => {
    setErro(null); setMsg(null);
    try { await fn(); setMsg(ok); carregar(); } catch (e: any) { setErro(mensagemDaApi(e, falha)); }
  };

  const enviarConvite = async () => {
    setErro(null);
    try {
      const { data } = await api.post('/convites', { email: novo.email.trim(), role: novo.role, nome: novo.nome.trim() || null });
      setConvidar(false);
      setNovo({ email: '', nome: '', role: 'professor' });
      setLinkGerado({ titulo: `Convite para ${data.email}`, link: data.link, enviado: data.enviado_por_email });
      carregar();
    } catch (e: any) { setErro(mensagemDaApi(e, 'Não foi possível criar o convite.')); }
  };

  const linkSenha = async (u: Usuario) => {
    if (!window.confirm(`Gerar um link para ${u.full_name || u.username} criar uma nova senha?\n\nO link vale 24 horas e uma única vez.`)) return;
    setErro(null);
    try {
      const { data } = await api.post(`/users/${u.id}/link-senha`);
      setLinkGerado({ titulo: `Nova senha de ${u.full_name || u.username}`, link: data.link, enviado: data.enviado_por_email });
    } catch (e: any) { setErro(mensagemDaApi(e, 'Não foi possível gerar o link.')); }
  };

  const aprovar = (u: Usuario) => acao(() => api.patch(`/users/${u.id}`, { status: 'ativo' }),
    `${u.full_name || u.username} aprovado(a): já pode entrar.`, 'Não foi possível aprovar.');
  const recusar = (u: Usuario) => {
    if (!window.confirm(`Recusar o cadastro de ${u.full_name || u.username}?${u.outra_banca ? '' : '\n\nA conta será excluída.'}`)) return;
    acao(() => api.delete(`/users/${u.id}`), 'Cadastro recusado.', 'Não foi possível recusar.');
  };
  const alternar = (u: Usuario) => {
    const novoStatus = situacao(u) === 'ativo' ? 'inativo' : 'ativo';
    acao(() => api.patch(`/users/${u.id}`, { status: novoStatus }),
      novoStatus === 'ativo' ? 'Acesso liberado.' : 'Acesso desativado: a pessoa sai desta banca na hora.', 'Erro ao mudar a situação.');
  };
  const mudarFuncao = (u: Usuario, role: string) => acao(() => api.patch(`/users/${u.id}`, { role }), 'Função alterada.', 'Erro ao mudar a função.');
  const resetar2fa = (u: Usuario) => {
    if (!window.confirm(`Resetar a verificação em duas etapas de ${u.username}?\n\nNo próximo login a pessoa vai cadastrar o autenticador de novo. Faça isso só depois de confirmar a identidade dela.`)) return;
    acao(() => api.post(`/users/${u.id}/2fa/resetar`), `2FA de ${u.username} resetado.`, 'Erro ao resetar o 2FA.');
  };
  const desconectar = (u: Usuario) => {
    if (!window.confirm(`Desconectar ${u.username}${u.outra_banca ? ' desta banca' : ' de todos os aparelhos'}?`)) return;
    acao(() => api.post(`/users/${u.id}/sessoes/encerrar`), `${u.username} desconectado(a).`, 'Erro ao desconectar.');
  };
  const anonimizar = (u: Usuario) => {
    const digitado = window.prompt(
      `ANONIMIZAR ${u.username} (LGPD)\n\nApaga para sempre nome, e-mail, CPF, telefone, endereço e dados bancários, ` +
      `desativa a conta e encerra os acessos. As questões que a pessoa elaborou continuam da banca.\n\nPara confirmar, digite o usuário: ${u.username}`);
    if (digitado === null) return;
    if (digitado.trim() !== u.username) { setErro('Confirmação não confere: nada foi alterado.'); return; }
    acao(() => api.post(`/lgpd/usuarios/${u.id}/anonimizar`), `Dados pessoais de ${u.username} eliminados (LGPD).`, 'Erro ao anonimizar.');
  };
  const excluir = (u: Usuario) => {
    const texto = u.outra_banca
      ? `Remover ${u.full_name || u.username} desta banca?\n\nA conta continua sendo da pessoa (ela trabalha também para outra banca).`
      : `Excluir a conta de ${u.full_name || u.username}?`;
    if (!window.confirm(texto)) return;
    acao(() => api.delete(`/users/${u.id}`), u.outra_banca ? 'Vínculo removido.' : 'Usuário excluído.', 'Erro ao excluir.');
  };
  const salvarEdicao = async () => {
    if (!editar) return;
    const corpo: any = {};
    CAMPOS_EDITAVEIS.forEach(([k]) => { corpo[k] = (editar as any)[k] ?? null; });
    corpo.role = editar.role;
    await acao(() => api.patch(`/users/${editar.id}`, corpo), 'Dados salvos.', 'Erro ao salvar.');
    setEditar(null);
  };

  const foto = (u: Usuario, tamanho = 40) => (
    <Tooltip title={u.tem_foto ? 'Ver foto' : 'Sem foto: a pessoa envia no próximo acesso'}>
      <span>
        <FotoAvatar avatarUrl={u.avatar_url} nome={u.full_name || u.username} tamanho={tamanho}
          onClick={() => u.tem_foto && setFotoAberta(u)}
          sx={{ cursor: u.tem_foto ? 'zoom-in' : 'default', bgcolor: u.tem_foto ? undefined : 'warning.dark' }} />
      </span>
    </Tooltip>
  );

  return (
    <Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ sm: 'center' }} spacing={1.5} sx={{ mb: 2 }}>
        <Box>
          <Typography variant="h6">Usuários da banca</Typography>
          <Typography variant="body2" color="text.secondary">
            Convide por link: a pessoa cria a própria senha e envia a foto. Você confere e aprova.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<PersonAddAlt1 />} disabled={semBanca} onClick={() => setConvidar(true)}>Convidar pessoa</Button>
      </Stack>
      {semBanca && <Alert severity="info" sx={{ mb: 2 }}>Escolha um cliente no topo da tela para convidar e aprovar usuários.</Alert>}
      {erro && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErro(null)}>{erro}</Alert>}
      {msg && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMsg(null)}>{msg}</Alert>}

      {pendentes.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3, borderColor: 'warning.main' }}>
          <Typography fontWeight={800} sx={{ mb: 1.5 }}>Aguardando aprovação ({pendentes.length})</Typography>
          <Stack spacing={1.5}>
            {pendentes.map(u => (
              <Stack key={u.id} direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ md: 'center' }}
                sx={{ p: 1.5, border: 1, borderColor: 'divider', borderRadius: 2 }}>
                {foto(u, 72)}
                <Box sx={{ flex: 1 }}>
                  <Typography fontWeight={700}>{u.full_name || u.username}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {u.username} · {u.email} · {ROTULO_PAPEL[u.role] || u.role}
                    {u.outra_banca ? ' · já tem conta em outra banca' : ''}
                  </Typography>
                  {!u.tem_foto && <Typography variant="caption" color="warning.main">Sem foto: não dá para aprovar ainda.</Typography>}
                </Box>
                <Stack direction="row" spacing={1}>
                  <Button variant="contained" color="success" startIcon={<CheckCircle />} disabled={!u.tem_foto} onClick={() => aprovar(u)}>Aprovar</Button>
                  <Button variant="outlined" color="error" startIcon={<Block />} onClick={() => recusar(u)}>Recusar</Button>
                </Stack>
              </Stack>
            ))}
          </Stack>
        </Paper>
      )}

      {convitesAbertos.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Typography fontWeight={800} sx={{ mb: 1 }}>Convites enviados ({convitesAbertos.length})</Typography>
          {convitesAbertos.map(c => (
            <Stack key={c.id} direction="row" spacing={1.5} alignItems="center" sx={{ py: 0.75 }}>
              <Typography sx={{ flex: 1 }}>{c.nome ? `${c.nome} · ` : ''}{c.email}</Typography>
              <Chip size="small" label={ROTULO_PAPEL[c.role || ''] || c.role} />
              <Typography variant="caption" color="text.secondary">até {new Date(c.expira_em).toLocaleDateString('pt-BR')}</Typography>
              <Tooltip title="Cancelar convite">
                <IconButton size="small" onClick={() => acao(() => api.delete(`/convites/${c.id}`), 'Convite cancelado.', 'Erro ao cancelar.')}><Close /></IconButton>
              </Tooltip>
            </Stack>
          ))}
        </Paper>
      )}

      {carregando && <Typography>Carregando...</Typography>}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Acesso</TableCell>
              <TableCell>Pessoa</TableCell>
              <TableCell>Função</TableCell>
              <TableCell>2FA</TableCell>
              <TableCell align="right">Ações</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {demais.map(u => {
              const souEu = u.username === user?.username;
              const outra = !!u.outra_banca;
              return (
                <TableRow key={u.id}>
                  <TableCell>
                    <Tooltip title={situacao(u) === 'ativo' ? 'Desativar o acesso a esta banca' : 'Liberar o acesso'}>
                      <span><Switch checked={situacao(u) === 'ativo'} disabled={souEu} onChange={() => alternar(u)} /></span>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                      {foto(u)}
                      <Box>
                        <Typography fontWeight={600}>{u.full_name || u.username}</Typography>
                        <Typography variant="caption" color="text.secondary">{u.full_name ? `${u.username} · ` : ''}{u.email}</Typography>
                        {outra && <Chip size="small" variant="outlined" color="info" label="Conta própria · vinculada" sx={{ ml: 1 }} />}
                      </Box>
                    </Stack>
                  </TableCell>
                  <TableCell>
                    {souEu || u.role === 'administrador geral' ? (ROTULO_PAPEL[u.role] || u.role) : (
                      <TextField select size="small" value={u.role} onChange={(e) => mudarFuncao(u, e.target.value)} sx={{ minWidth: 150 }}>
                        {(outra ? PAPEIS_CONVITE.filter(p => p !== 'administrador') : PAPEIS_CONVITE).map(p => (
                          <MenuItem key={p} value={p}>{ROTULO_PAPEL[p]}</MenuItem>
                        ))}
                      </TextField>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={u.totp_ativo ? 'Ativo' : 'Pendente'} color={u.totp_ativo ? 'success' : 'warning'} variant="outlined" />
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                    {!outra && <Tooltip title="Editar dados"><IconButton onClick={() => setEditar({ ...u })}><Edit /></IconButton></Tooltip>}
                    <Tooltip title="Mais ações">
                      <IconButton onClick={(e) => setMenu({ el: e.currentTarget, u })}><MoreVert /></IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      {/* ações menos usadas: menu por pessoa (as de dados pessoais só para quem é desta banca de origem) */}
      <Menu anchorEl={menu?.el} open={!!menu} onClose={() => setMenu(null)}>
        {menu && !menu.u.outra_banca && (
          <MenuItem onClick={() => { const u = menu.u; setMenu(null); linkSenha(u); }}>
            <ListItemIcon><LockReset fontSize="small" /></ListItemIcon>Enviar link de nova senha
          </MenuItem>
        )}
        {menu && !menu.u.outra_banca && (
          <MenuItem disabled={!menu.u.totp_ativo || menu.u.username === user?.username}
            onClick={() => { const u = menu.u; setMenu(null); resetar2fa(u); }}>
            <ListItemIcon><PhonelinkLock fontSize="small" /></ListItemIcon>Resetar 2FA (celular perdido)
          </MenuItem>
        )}
        {menu && (
          <MenuItem onClick={() => { const u = menu.u; setMenu(null); desconectar(u); }}>
            <ListItemIcon><Logout fontSize="small" /></ListItemIcon>{menu.u.outra_banca ? 'Desconectar desta banca' : 'Desconectar de todos os aparelhos'}
          </MenuItem>
        )}
        {menu && !menu.u.outra_banca && (
          <MenuItem disabled={menu.u.username === user?.username} onClick={() => { const u = menu.u; setMenu(null); anonimizar(u); }}>
            <ListItemIcon><PersonOff fontSize="small" /></ListItemIcon>Anonimizar (LGPD)
          </MenuItem>
        )}
        {menu && (
          <MenuItem disabled={menu.u.username === user?.username} onClick={() => { const u = menu.u; setMenu(null); excluir(u); }}
            sx={{ color: 'error.main' }}>
            <ListItemIcon><Delete fontSize="small" color="error" /></ListItemIcon>{menu.u.outra_banca ? 'Remover desta banca' : 'Excluir conta'}
          </MenuItem>
        )}
      </Menu>

      {/* convidar */}
      <Dialog open={convidar} onClose={() => setConvidar(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Convidar pessoa</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            A pessoa recebe um link (vale 7 dias, uma vez) para se cadastrar com os próprios dados, senha e foto. Professores
            e revisores que já usam o DiagPro em outra banca entram com a própria conta para aceitar. Depois você aprova aqui.
          </Typography>
          <TextField label="E-mail *" type="email" fullWidth margin="normal" value={novo.email}
            onChange={(e) => setNovo(n => ({ ...n, email: e.target.value }))} />
          <TextField label="Nome (opcional)" fullWidth margin="normal" value={novo.nome}
            onChange={(e) => setNovo(n => ({ ...n, nome: e.target.value }))} />
          <TextField label="Função *" select fullWidth margin="normal" value={novo.role}
            onChange={(e) => setNovo(n => ({ ...n, role: e.target.value }))}>
            {PAPEIS_CONVITE.map(p => <MenuItem key={p} value={p}>{ROTULO_PAPEL[p]}</MenuItem>)}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConvidar(false)}>Cancelar</Button>
          <Button variant="contained" onClick={enviarConvite} disabled={!/^\S+@\S+\.\S+$/.test(novo.email.trim())}>Gerar convite</Button>
        </DialogActions>
      </Dialog>

      {/* link gerado: mostrado uma única vez */}
      <Dialog open={!!linkGerado} onClose={() => setLinkGerado(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{linkGerado?.titulo}</DialogTitle>
        <DialogContent>
          <Alert severity={linkGerado?.enviado ? 'success' : 'info'} sx={{ mb: 2 }}>
            {linkGerado?.enviado
              ? 'Enviado por e-mail. Se preferir, copie o link abaixo e mande por outro canal seguro.'
              : 'O e-mail do sistema não está configurado: copie o link e envie para a pessoa por um canal seguro.'}
          </Alert>
          <TextField fullWidth value={linkGerado?.link || ''} InputProps={{
            readOnly: true,
            endAdornment: (
              <InputAdornment position="end">
                <IconButton onClick={() => { navigator.clipboard?.writeText(linkGerado?.link || ''); setMsg('Link copiado.'); }}><ContentCopy /></IconButton>
              </InputAdornment>
            ),
          }} />
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
            Por segurança, o link não fica guardado: ele aparece só agora. Se perder, gere outro.
          </Typography>
        </DialogContent>
        <DialogActions><Button variant="contained" onClick={() => setLinkGerado(null)}>Fechar</Button></DialogActions>
      </Dialog>

      {/* editar (só quem é desta banca de origem) */}
      <Dialog open={!!editar} onClose={() => setEditar(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Editar usuário</DialogTitle>
        <DialogContent>
          {editar && (
            <>
              <Stack direction="row" spacing={2} alignItems="center" sx={{ my: 1 }}>
                {foto(editar, 64)}
                <Typography variant="body2" color="text.secondary">
                  A foto e a senha são da própria pessoa: ela troca em Minha conta. Para senha esquecida, use "Enviar link de nova senha".
                </Typography>
              </Stack>
              {CAMPOS_EDITAVEIS.map(([k, rotulo]) => (
                <TextField key={k} label={rotulo} fullWidth margin="dense" value={(editar as any)[k] || ''}
                  type={k === 'birth_date' ? 'date' : 'text'} InputLabelProps={k === 'birth_date' ? { shrink: true } : undefined}
                  onChange={(e) => setEditar(u => (u ? { ...u, [k]: e.target.value } : u))} />
              ))}
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditar(null)}>Cancelar</Button>
          <Button variant="contained" onClick={salvarEdicao}>Salvar</Button>
        </DialogActions>
      </Dialog>

      {/* foto ampliada */}
      <Dialog open={!!fotoAberta} onClose={() => setFotoAberta(null)} maxWidth="xs">
        <DialogTitle>{fotoAberta?.full_name || fotoAberta?.username}</DialogTitle>
        <DialogContent>
          <FotoGrande avatarUrl={fotoAberta?.avatar_url} />
        </DialogContent>
      </Dialog>
    </Box>
  );
}
