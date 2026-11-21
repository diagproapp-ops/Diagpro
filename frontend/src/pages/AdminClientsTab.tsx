import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert, Avatar, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, IconButton, InputAdornment,
  MenuItem, Paper, Stack, TextField, Tooltip, Typography,
} from '@mui/material';
import {
  Add, Block, CheckCircle, ContentCopy, EditOutlined, History, PersonAddAlt1, Search, WarningAmber,
} from '@mui/icons-material';
import api from '../api';
import { ROTULO_PAPEL, mensagemDaApi } from '../components/usuarios/comum';

interface Atividade { type: string; user: string; timestamp: string }
interface Cliente {
  id: number;
  name: string;
  domain: string;
  status: string;
  tenant_type: string;
  created_at?: string | null;
  responsible_name?: string | null;
  responsible_email?: string | null;
  responsible_phone?: string | null;
  plan_type?: string | null;
  plan_expires_at?: string | null;
  users_total: number;
  users_by_role: Record<string, number>;
  questions_total: number;
  exams_total: number;
  events_total: number;
  admins_total: number;
  blocked_users_total: number;
  pending_users_total?: number;
  accesses_total_month: number;
  last_access?: string | null;
  recent_activities: Atividade[];
}

const FORM_VAZIO = {
  name: '', domain: '', status: 'ativo', tenant_type: 'empresa_concurso', responsible_name: '', responsible_email: '',
  responsible_phone: '', plan_type: '', plan_expires_at: '',
};
type Form = typeof FORM_VAZIO;

const SITUACAO: Record<string, { rotulo: string; cor: 'success' | 'error' | 'default' }> = {
  ativo: { rotulo: 'Ativo', cor: 'success' },
  bloqueado: { rotulo: 'Bloqueado', cor: 'error' },
  inativo: { rotulo: 'Inativo', cor: 'default' },
};

const ACOES: Record<string, string> = {
  exportacao: 'Exportou provas', previsualizacao_prova: 'Pré-visualizou a prova', geracao: 'Gerou provas',
  download_pacote: 'Baixou pacote', gabarito: 'Gerou gabarito',
};
const rotuloAcao = (a: string) => ACOES[a] || (a || '').replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());

function quando(iso?: string | null): string {
  if (!iso) return 'nunca';
  const d = new Date(iso);
  const min = Math.round((Date.now() - d.getTime()) / 60000);
  if (min < 1) return 'agora';
  if (min < 60) return `há ${min} min`;
  if (min < 60 * 24) return `há ${Math.round(min / 60)} h`;
  if (min < 60 * 24 * 30) return `há ${Math.round(min / 1440)} dia(s)`;
  return d.toLocaleDateString('pt-BR');
}

function vencimento(iso?: string | null): { texto: string; alerta: boolean } | null {
  if (!iso) return null;
  const d = new Date(`${iso.slice(0, 10)}T23:59:59`);
  const dias = Math.ceil((d.getTime() - Date.now()) / 86400000);
  const data = d.toLocaleDateString('pt-BR');
  if (dias < 0) return { texto: `venceu em ${data}`, alerta: true };
  if (dias <= 30) return { texto: `vence em ${data} (${dias} dia${dias === 1 ? '' : 's'})`, alerta: true };
  return { texto: `até ${data}`, alerta: false };
}

const Numero: React.FC<{ rotulo: string; valor: React.ReactNode; detalhe?: React.ReactNode }> = ({ rotulo, valor, detalhe }) => (
  <Box sx={{ p: 1.25, borderRadius: 2, bgcolor: 'action.hover', minWidth: 0 }}>
    <Typography variant="caption" color="text.secondary" noWrap display="block">{rotulo}</Typography>
    <Typography fontWeight={800} fontSize={20} lineHeight={1.2} noWrap>{valor}</Typography>
    {detalhe && <Typography variant="caption" color="text.secondary" noWrap display="block">{detalhe}</Typography>}
  </Box>
);

// Bancas & Clientes (administrador geral): números reais de cada cliente, edição, bloqueio que derruba os acessos na
// hora e administrador por CONVITE (a pessoa cria a própria senha e envia a foto; ninguém recebe senha inventada).
export default function AdminClientsTab() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [busca, setBusca] = useState('');
  const [erro, setErro] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [editando, setEditando] = useState<{ id: number | null; form: Form } | null>(null);
  const [erroForm, setErroForm] = useState<string | null>(null);
  const [convite, setConvite] = useState<{ cliente: Cliente; email: string; nome: string } | null>(null);
  const [link, setLink] = useState<{ titulo: string; link: string; enviado: boolean } | null>(null);
  const [atividade, setAtividade] = useState<{ cliente: Cliente; itens: Atividade[] | null } | null>(null);

  // só a carga mais recente vale: uma resposta atrasada não desfaz um bloqueio/desbloqueio feito depois
  const ultimaCarga = useRef(0);
  const carregar = useCallback(() => {
    const minha = ++ultimaCarga.current;
    setCarregando(true);
    api.get<Cliente[]>('/admin/clients/dashboard')
      .then(({ data }) => { if (minha === ultimaCarga.current) setClientes(data); })
      .catch((e) => setErro(mensagemDaApi(e, 'Não foi possível carregar os clientes.')))
      .finally(() => setCarregando(false));
  }, []);
  useEffect(() => { carregar(); }, [carregar]);

  const filtrados = useMemo(() => {
    const t = busca.trim().toLowerCase();
    return t ? clientes.filter(c => `${c.name} ${c.domain} ${c.responsible_name || ''}`.toLowerCase().includes(t)) : clientes;
  }, [clientes, busca]);

  const resumo = useMemo(() => ({
    ativos: clientes.filter(c => c.status === 'ativo').length,
    bloqueados: clientes.filter(c => c.status !== 'ativo').length,
    pessoas: clientes.reduce((n, c) => n + c.users_total, 0),
    pendentes: clientes.reduce((n, c) => n + (c.pending_users_total || 0), 0),
    acessos: clientes.reduce((n, c) => n + c.accesses_total_month, 0),
    questoes: clientes.reduce((n, c) => n + c.questions_total, 0),
  }), [clientes]);

  const abrirEdicao = (c?: Cliente) => {
    setErroForm(null);
    setEditando(c ? {
      id: c.id,
      form: {
        name: c.name || '', domain: c.domain || '', status: c.status || 'ativo', tenant_type: c.tenant_type || 'empresa_concurso',
        responsible_name: c.responsible_name || '', responsible_email: c.responsible_email || '',
        responsible_phone: c.responsible_phone || '', plan_type: c.plan_type || '', plan_expires_at: (c.plan_expires_at || '').slice(0, 10),
      },
    } : { id: null, form: { ...FORM_VAZIO } });
  };

  const salvar = async () => {
    if (!editando) return;
    setErroForm(null);
    try {
      const corpo = { ...editando.form, plan_expires_at: editando.form.plan_expires_at || null };
      if (editando.id) await api.put(`/admin/clients/${editando.id}`, corpo);
      else await api.post('/admin/clients', corpo);
      setMsg(editando.id ? 'Cliente atualizado.' : 'Cliente criado. Agora convide o administrador dele.');
      setEditando(null);
      carregar();
    } catch (e: any) { setErroForm(mensagemDaApi(e, 'Não foi possível salvar.')); }
  };

  const bloquear = async (c: Cliente) => {
    const ativo = c.status === 'ativo';
    if (ativo && !window.confirm(`Bloquear ${c.name}?\n\nNinguém desse cliente consegue entrar e quem está dentro é desconectado na hora. Os dados ficam guardados.`)) return;
    setErro(null);
    try {
      const { data } = await api.post(`/admin/clients/${c.id}/${ativo ? 'bloquear' : 'desbloquear'}`);
      // atualiza o cartão na hora: um "Editar" logo em seguida já parte da situação nova (nunca da antiga)
      ultimaCarga.current += 1; // descarta cargas que ainda estão a caminho com a situação anterior
      setClientes(cs => cs.map(x => (x.id === c.id ? { ...x, status: data.status } : x)));
      setMsg(ativo ? `${c.name} bloqueado: ${data.acessos_encerrados} acesso(s) encerrado(s).` : `${c.name} desbloqueado.`);
      carregar();
    } catch (e: any) { setErro(mensagemDaApi(e, 'Não foi possível mudar a situação.')); }
  };

  const convidarAdmin = async () => {
    if (!convite) return;
    setErro(null);
    try {
      // convite feito DENTRO do cliente escolhido (o servidor usa o RLS dele)
      const { data } = await api.post('/convites', { email: convite.email.trim(), role: 'administrador', nome: convite.nome.trim() || null },
        { headers: { 'X-Tenant-Id': String(convite.cliente.id) } });
      setLink({ titulo: `Administrador de ${convite.cliente.name}`, link: data.link, enviado: data.enviado_por_email });
      setConvite(null);
    } catch (e: any) { setErro(mensagemDaApi(e, 'Não foi possível criar o convite.')); setConvite(null); }
  };

  const verAtividade = async (c: Cliente) => {
    setAtividade({ cliente: c, itens: null });
    try {
      const { data } = await api.get<Atividade[]>(`/admin/clients/${c.id}/logs`);
      setAtividade({ cliente: c, itens: data });
    } catch { setAtividade({ cliente: c, itens: [] }); }
  };

  const campo = (k: keyof Form, rotulo: string, extra: any = {}) => (
    <TextField label={rotulo} value={editando?.form[k] || ''} fullWidth size="small"
      onChange={(e) => setEditando(ed => (ed ? { ...ed, form: { ...ed.form, [k]: e.target.value } } : ed))} {...extra} />
  );

  return (
    <Box>
      <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" alignItems={{ md: 'center' }} spacing={2} sx={{ mb: 2.5 }}>
        <Box>
          <Typography variant="h6" fontWeight={800}>Bancas & Clientes</Typography>
          <Typography variant="body2" color="text.secondary">Cada cliente é isolado dos demais. Números reais dos últimos 30 dias.</Typography>
        </Box>
        <Stack direction="row" spacing={1.5}>
          <TextField size="small" placeholder="Buscar cliente" value={busca} onChange={(e) => setBusca(e.target.value)}
            InputProps={{ startAdornment: <InputAdornment position="start"><Search fontSize="small" /></InputAdornment> }} />
          <Button variant="contained" startIcon={<Add />} onClick={() => abrirEdicao()} sx={{ whiteSpace: 'nowrap' }}>Novo cliente</Button>
        </Stack>
      </Stack>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', md: 'repeat(4, minmax(0, 1fr))' }, gap: 1.5, mb: 3 }}>
        <Numero rotulo="Clientes" valor={clientes.length} detalhe={`${resumo.ativos} ativo(s) · ${resumo.bloqueados} bloqueado(s)/inativo(s)`} />
        <Numero rotulo="Pessoas" valor={resumo.pessoas} detalhe={resumo.pendentes ? `${resumo.pendentes} aguardando aprovação` : 'nenhuma pendente'} />
        <Numero rotulo="Acessos (30 dias)" valor={resumo.acessos} />
        <Numero rotulo="Questões" valor={resumo.questoes} />
      </Box>

      {erro && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErro(null)}>{erro}</Alert>}
      {msg && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMsg(null)}>{msg}</Alert>}
      {carregando && <Typography color="text.secondary">Carregando...</Typography>}
      {!carregando && filtrados.length === 0 && <Typography color="text.secondary">Nenhum cliente encontrado.</Typography>}

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr)', xl: 'repeat(2, minmax(0, 1fr))' }, gap: 2 }}>
        {filtrados.map(c => {
          const sit = SITUACAO[c.status] || { rotulo: c.status, cor: 'default' as const };
          const venc = vencimento(c.plan_expires_at);
          const ativo = c.status === 'ativo';
          return (
            <Paper key={c.id} variant="outlined" sx={{ p: 2.25, borderRadius: 3, opacity: ativo ? 1 : 0.85,
              borderColor: ativo ? 'divider' : 'error.dark' }}>
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Avatar sx={{ bgcolor: ativo ? 'primary.dark' : 'grey.700', fontWeight: 800 }}>{(c.name || '?').charAt(0).toUpperCase()}</Avatar>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography fontWeight={800} noWrap>{c.name}</Typography>
                  <Typography variant="body2" color="text.secondary" noWrap>{c.domain}</Typography>
                </Box>
                <Chip size="small" color={sit.cor} label={sit.rotulo} />
                <Chip size="small" variant="outlined" label={c.tenant_type === 'escola' ? 'Escola' : 'Banca'} />
              </Stack>

              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={{ xs: 0.5, sm: 3 }} sx={{ mt: 1.5 }}>
                <Typography variant="body2" color="text.secondary" noWrap>
                  Responsável: <b>{c.responsible_name || '—'}</b>{c.responsible_email ? ` · ${c.responsible_email}` : ''}
                </Typography>
                <Typography variant="body2" color={venc?.alerta ? 'warning.main' : 'text.secondary'} noWrap
                  sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  {venc?.alerta && <WarningAmber sx={{ fontSize: 16 }} />}
                  Plano: <b>{c.plan_type || '—'}</b>{venc ? ` · ${venc.texto}` : ''}
                </Typography>
              </Stack>

              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 1, mt: 1.75 }}>
                <Numero rotulo="Pessoas" valor={c.users_total}
                  detalhe={c.pending_users_total ? `${c.pending_users_total} pendente(s)` : `${c.admins_total} admin(s)`} />
                <Numero rotulo="Eventos" valor={c.events_total} />
                <Numero rotulo="Questões" valor={c.questions_total} detalhe={`${c.exams_total} prova(s) montada(s)`} />
                <Numero rotulo="Acessos (30 dias)" valor={c.accesses_total_month} />
                <Numero rotulo="Último acesso" valor={<span style={{ fontSize: 16 }}>{quando(c.last_access)}</span>} />
                <Numero rotulo="Inativos" valor={c.blocked_users_total} />
              </Box>

              {Object.keys(c.users_by_role).length > 0 && (
                <Stack direction="row" spacing={0.75} sx={{ mt: 1.5, flexWrap: 'wrap', rowGap: 0.75 }}>
                  {Object.entries(c.users_by_role).sort((a, b) => b[1] - a[1]).map(([role, n]) => (
                    <Chip key={role} size="small" variant="outlined" label={`${ROTULO_PAPEL[role] || role}: ${n}`} />
                  ))}
                </Stack>
              )}

              <Divider sx={{ my: 1.5 }} />
              <Typography variant="caption" color="text.secondary" fontWeight={700}>ATIVIDADE RECENTE</Typography>
              {c.recent_activities.length === 0 ? (
                <Typography variant="body2" color="text.secondary">Nada registrado ainda.</Typography>
              ) : c.recent_activities.map((a, i) => (
                <Typography key={i} variant="body2" noWrap>
                  {rotuloAcao(a.type)} · <b>{a.user}</b> · <span style={{ opacity: 0.7 }}>{quando(a.timestamp)}</span>
                </Typography>
              ))}

              <Stack direction="row" spacing={1} sx={{ mt: 1.75, flexWrap: 'wrap', rowGap: 1 }}>
                <Button size="small" variant="outlined" startIcon={<EditOutlined />} onClick={() => abrirEdicao(c)}>Editar</Button>
                <Button size="small" variant="outlined" startIcon={<PersonAddAlt1 />} disabled={!ativo}
                  onClick={() => setConvite({ cliente: c, email: c.responsible_email || '', nome: c.responsible_name || '' })}>
                  Convidar administrador
                </Button>
                <Button size="small" startIcon={<History />} onClick={() => verAtividade(c)}>Atividade</Button>
                <Box sx={{ flex: 1 }} />
                <Tooltip title={ativo ? 'Ninguém entra e quem está dentro sai na hora' : 'Libera o acesso de novo'}>
                  <Button size="small" color={ativo ? 'error' : 'success'} startIcon={ativo ? <Block /> : <CheckCircle />} onClick={() => bloquear(c)}>
                    {ativo ? 'Bloquear' : 'Desbloquear'}
                  </Button>
                </Tooltip>
              </Stack>
            </Paper>
          );
        })}
      </Box>

      {/* novo / editar */}
      <Dialog open={!!editando} onClose={() => setEditando(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{editando?.id ? 'Editar cliente' : 'Novo cliente'}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2, mt: 1 }}>
            {campo('name', 'Nome *')}
            {campo('domain', 'Domínio *', { helperText: 'Ex.: minhabanca.com' })}
            {campo('tenant_type', 'Tipo', { select: true, children: [
              <MenuItem key="b" value="empresa_concurso">Banca / empresa de concurso</MenuItem>,
              <MenuItem key="e" value="escola">Escola</MenuItem>] })}
            {campo('status', 'Situação', { select: true, children: [
              <MenuItem key="a" value="ativo">Ativo</MenuItem>,
              <MenuItem key="i" value="inativo">Inativo</MenuItem>,
              <MenuItem key="b" value="bloqueado">Bloqueado</MenuItem>] })}
            {campo('responsible_name', 'Responsável')}
            {campo('responsible_email', 'E-mail do responsável', { type: 'email' })}
            {campo('responsible_phone', 'Telefone do responsável')}
            {campo('plan_type', 'Plano', { placeholder: 'Ex.: Anual' })}
            {campo('plan_expires_at', 'Plano vale até', { type: 'date', InputLabelProps: { shrink: true } })}
          </Box>
          {editando?.id && editando.form.status !== 'ativo' && (
            <Alert severity="warning" sx={{ mt: 2 }}>Fora de "Ativo", ninguém do cliente entra e os acessos abertos são encerrados.</Alert>
          )}
          {erroForm && <Alert severity="error" sx={{ mt: 2 }}>{erroForm}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditando(null)}>Cancelar</Button>
          <Button variant="contained" onClick={salvar} disabled={!editando?.form.name.trim() || !editando?.form.domain.trim()}>Salvar</Button>
        </DialogActions>
      </Dialog>

      {/* convidar administrador do cliente */}
      <Dialog open={!!convite} onClose={() => setConvite(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Convidar administrador · {convite?.cliente.name}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            A pessoa recebe um link (7 dias, uso único) para se cadastrar com os próprios dados, senha e foto.
            Depois do cadastro, aprove em Usuários e contas, com o cliente escolhido no topo da tela.
          </Typography>
          <TextField label="E-mail *" type="email" fullWidth margin="normal" value={convite?.email || ''}
            onChange={(e) => setConvite(cv => (cv ? { ...cv, email: e.target.value } : cv))} />
          <TextField label="Nome (opcional)" fullWidth margin="normal" value={convite?.nome || ''}
            onChange={(e) => setConvite(cv => (cv ? { ...cv, nome: e.target.value } : cv))} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConvite(null)}>Cancelar</Button>
          <Button variant="contained" onClick={convidarAdmin} disabled={!/^\S+@\S+\.\S+$/.test((convite?.email || '').trim())}>Gerar convite</Button>
        </DialogActions>
      </Dialog>

      {/* link gerado (aparece uma única vez) */}
      <Dialog open={!!link} onClose={() => setLink(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{link?.titulo}</DialogTitle>
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
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
            Por segurança, o link não fica guardado: ele aparece só agora.
          </Typography>
        </DialogContent>
        <DialogActions><Button variant="contained" onClick={() => setLink(null)}>Fechar</Button></DialogActions>
      </Dialog>

      {/* atividade */}
      <Dialog open={!!atividade} onClose={() => setAtividade(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Atividade · {atividade?.cliente.name}</DialogTitle>
        <DialogContent>
          {atividade?.itens === null ? <Typography color="text.secondary">Carregando...</Typography>
            : atividade?.itens.length === 0 ? <Typography color="text.secondary">Nada registrado ainda.</Typography>
              : atividade?.itens.map((a, i) => (
                <Stack key={i} direction="row" spacing={1.5} sx={{ py: 0.75, borderBottom: 1, borderColor: 'divider' }}>
                  <Typography variant="body2" sx={{ minWidth: 140 }} color="text.secondary">{new Date(a.timestamp).toLocaleString('pt-BR')}</Typography>
                  <Typography variant="body2" sx={{ flex: 1 }}>{rotuloAcao(a.type)}</Typography>
                  <Typography variant="body2" fontWeight={700}>{a.user}</Typography>
                </Stack>
              ))}
        </DialogContent>
        <DialogActions><Button onClick={() => setAtividade(null)}>Fechar</Button></DialogActions>
      </Dialog>
    </Box>
  );
}
