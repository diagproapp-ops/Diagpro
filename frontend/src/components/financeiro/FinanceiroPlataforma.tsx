import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, Divider, FormControlLabel, IconButton, MenuItem,
  Paper, Stack, Tab, Table, TableBody, TableCell, TableHead, TableRow, Tabs, TextField, Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DownloadIcon from '@mui/icons-material/Download';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import api from '../../api';
import { DialogoTexto, Indicador, StatusChip, baixar, dataBR, dataHoraBR, erroApi, moeda } from './comum';

// Financeiro da PLATAFORMA (administrador geral): planos, propostas, contratos/termos, faturas e documentos de cada banca.
// A negociação das bancas com os professores não aparece aqui (é só da banca).
const FinanceiroPlataforma: React.FC = () => {
  const [aba, setAba] = useState<'bancas' | 'planos' | 'cobranca'>('bancas');
  const [banca, setBanca] = useState<number | null>(null);
  return (
    <Box>
      <Alert severity="info" sx={{ mb: 2 }}>Aqui fica só a relação da plataforma com as bancas. Os pagamentos das bancas aos professores são de cada banca e não aparecem para a administração geral.</Alert>
      {banca ? <DetalheBanca id={banca} onVoltar={() => setBanca(null)} /> : (
        <>
          <Tabs value={aba} onChange={(_, v) => setAba(v)} sx={{ mb: 2.5 }}>
            <Tab value="bancas" label="Bancas" />
            <Tab value="planos" label="Planos" />
            <Tab value="cobranca" label="Cobrança automática e relatórios" />
          </Tabs>
          {aba === 'bancas' && <ListaBancas onAbrir={setBanca} />}
          {aba === 'planos' && <Planos />}
          {aba === 'cobranca' && <Cobranca />}
        </>
      )}
    </Box>
  );
};

const ListaBancas: React.FC<{ onAbrir: (id: number) => void }> = ({ onAbrir }) => {
  const [lista, setLista] = useState<any[] | null>(null);
  useEffect(() => { api.get('/plataforma/financeiro/bancas').then(({ data }) => setLista(data)).catch(() => setLista([])); }, []);
  if (!lista) return <Typography>Carregando...</Typography>;
  const soma = (k: string) => lista.reduce((s, b) => s + (b[k] || 0), 0);
  return (
    <Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, minmax(0,1fr))', md: 'repeat(4, minmax(0,1fr))' }, gap: 1.5, mb: 2.5 }}>
        <Indicador rotulo="Bancas" valor={lista.length} />
        <Indicador rotulo="Em aberto" valor={moeda(soma('em_aberto'))} cor="#f59e0b" />
        <Indicador rotulo="Faturas atrasadas" valor={soma('atrasadas')} cor={soma('atrasadas') ? '#ef4444' : undefined} detalhe={`${soma('em_analise')} comprovante(s) para conferir`} />
        <Indicador rotulo="Recebido" valor={moeda(soma('recebido'))} cor="#10b981" />
      </Box>
      <Paper variant="outlined" sx={{ borderRadius: 2, overflowX: 'auto' }}>
        <Table size="small">
          <TableHead><TableRow><TableCell>Banca</TableCell><TableCell>Plano</TableCell><TableCell align="right">Em aberto</TableCell><TableCell>Pendências</TableCell><TableCell /></TableRow></TableHead>
          <TableBody>
            {lista.map(b => (
              <TableRow key={b.id} hover sx={{ cursor: 'pointer' }} onClick={() => onAbrir(b.id)}>
                <TableCell><Typography fontWeight={700} variant="body2">{b.nome}</Typography><Typography variant="caption" color="text.secondary">{b.situacao}</Typography></TableCell>
                <TableCell>{b.plano || '—'}{b.plano_vence_em ? <Typography variant="caption" color="text.secondary" display="block">até {dataBR(b.plano_vence_em)}</Typography> : null}</TableCell>
                <TableCell align="right">{moeda(b.em_aberto)}{b.atrasadas ? <Typography variant="caption" color="error" display="block">{b.atrasadas} atrasada(s)</Typography> : null}</TableCell>
                <TableCell>
                  {[b.propostas_pendentes && `${b.propostas_pendentes} proposta(s)`, b.termos_pendentes && `${b.termos_pendentes} documento(s)`,
                    b.em_analise && `${b.em_analise} comprovante(s)`].filter(Boolean).join(' · ') || '—'}
                </TableCell>
                <TableCell align="right"><Button size="small">Abrir</Button></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
};

const DetalheBanca: React.FC<{ id: number; onVoltar: () => void }> = ({ id, onVoltar }) => {
  const [d, setD] = useState<any>(null);
  const [planos, setPlanos] = useState<any[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [proposta, setProposta] = useState<any>(null);
  const [termo, setTermo] = useState<any>(null);
  const [fatura, setFatura] = useState<any>(null);
  const [devolver, setDevolver] = useState<any>(null);
  const [cancelarFat, setCancelarFat] = useState<any>(null);

  const carregar = useCallback(() => {
    api.get(`/plataforma/financeiro/bancas/${id}`).then(({ data }) => setD(data)).catch((e) => setErro(erroApi(e, 'Não foi possível carregar.')));
  }, [id]);
  useEffect(() => { carregar(); api.get('/plataforma/financeiro/planos').then(({ data }) => setPlanos(data)).catch(() => {}); }, [carregar]);
  const acao = async (fn: () => Promise<any>, ok: string) => {
    setErro(null); setMsg(null);
    try { await fn(); setMsg(ok); carregar(); } catch (e: any) { setErro(erroApi(e, 'Não foi possível concluir.')); }
  };
  const anexar = () => {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.pdf,.png,.jpg,.jpeg,.xml';
    input.onchange = () => {
      const arq = input.files?.[0];
      if (!arq) return;
      const fd = new FormData(); fd.append('arquivo', arq);
      acao(() => api.post(`/plataforma/financeiro/bancas/${id}/documentos`, fd), 'Documento anexado.');
    };
    input.click();
  };

  if (!d) return erro ? <Alert severity="error">{erro}</Alert> : <Typography>Carregando...</Typography>;
  const comprovantes = (fid: number) => d.documentos.filter((x: any) => x.tipo === 'comprovante' && x.referencia_id === fid);
  return (
    <Box>
      <Button startIcon={<ArrowBackIcon />} onClick={onVoltar} sx={{ mb: 1 }}>Bancas</Button>
      <Typography variant="h6" fontWeight={800}>{d.banca.nome}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Plano: {d.plano.plano || 'nenhum'}{d.plano.vence_em ? ` até ${dataBR(d.plano.vence_em)}` : ''} · {d.banca.responsavel || 'sem responsável'} {d.banca.email}
      </Typography>
      {erro && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErro(null)}>{erro}</Alert>}
      {msg && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMsg(null)}>{msg}</Alert>}

      <Bloco titulo="Propostas" acao={<Button size="small" variant="contained" onClick={() => setProposta({ plano_id: planos[0]?.id || '', periodicidade: 'mensal', desconto: 0, condicoes: '', validade: '', itens: '' })}>Nova proposta</Button>}>
        {d.propostas.length === 0 ? <Vazio /> : d.propostas.map((p: any) => (
          <Linha key={p.id}>
            <Box sx={{ flex: 1 }}>
              <Typography fontWeight={700}>{p.numero} v{p.versao} · {p.plano} · {p.periodicidade} · {moeda(p.valor_final)}</Typography>
              <Typography variant="caption" color="text.secondary">{p.validade ? `válida até ${dataBR(p.validade)}` : 'sem prazo'}
                {p.motivo_recusa ? ` · recusada: ${p.motivo_recusa}` : ''}{p.aceite ? ` · aceita por ${p.aceite.por} em ${dataHoraBR(p.aceite.em)} (IP ${p.aceite.ip})` : ''}</Typography>
            </Box>
            <StatusChip status={p.expirada ? 'cancelada' : p.status} />
            <IconButton size="small" onClick={() => baixar(`/plataforma/financeiro/arquivo/proposta/${p.id}`, `proposta-${p.numero}.pdf`)}><DownloadIcon fontSize="small" /></IconButton>
            {p.status === 'enviada' && <Button size="small" color="error" onClick={() => acao(() => api.post(`/plataforma/financeiro/propostas/${p.id}/cancelar`), 'Proposta cancelada.')}>Cancelar</Button>}
          </Linha>
        ))}
      </Bloco>

      <Bloco titulo="Contratos e termos" acao={<Button size="small" variant="contained" onClick={() => setTermo({ tipo: 'contrato', titulo: '', descricao: '', texto: '', arquivo: null })}>Enviar documento</Button>}>
        {d.termos.length === 0 ? <Vazio /> : d.termos.map((t: any) => (
          <Linha key={t.id}>
            <Box sx={{ flex: 1 }}>
              <Typography fontWeight={700}>{t.titulo}</Typography>
              <Typography variant="caption" color="text.secondary">{t.descricao}{t.motivo_recusa ? ` · recusado: ${t.motivo_recusa}` : ''}
                {t.aceite ? ` · aceito por ${t.aceite.por} em ${dataHoraBR(t.aceite.em)} (IP ${t.aceite.ip})` : ''}</Typography>
            </Box>
            <StatusChip status={t.status} />
            <IconButton size="small" onClick={() => baixar(`/plataforma/financeiro/arquivo/termo/${t.id}`, `${t.titulo}.pdf`)}><DownloadIcon fontSize="small" /></IconButton>
            {t.status === 'pendente' && <Button size="small" color="error" onClick={() => acao(() => api.post(`/plataforma/financeiro/termos/${t.id}/cancelar`), 'Documento cancelado.')}>Cancelar</Button>}
          </Linha>
        ))}
      </Bloco>

      <Bloco titulo="Faturas" acao={<Button size="small" variant="contained" onClick={() => setFatura({ competencia: new Date().toISOString().slice(0, 7), vencimento: '', valor: '', descricao: '', usarPlano: true })}>Emitir fatura</Button>}>
        {d.faturas.length === 0 ? <Vazio /> : d.faturas.map((f: any) => (
          <Linha key={f.id}>
            <Box sx={{ flex: 1 }}>
              <Typography fontWeight={700}>{f.numero} · {moeda(f.valor)} · {f.competencia}</Typography>
              <Typography variant="caption" color="text.secondary">{f.descricao} · vence {dataBR(f.vencimento)}{f.paga_em ? ` · paga em ${dataBR(f.paga_em)}` : ''}</Typography>
            </Box>
            <StatusChip status={f.status} />
            {comprovantes(f.id).map((x: any) => (
              <IconButton key={x.id} size="small" title="Comprovante da banca" onClick={() => baixar(`/plataforma/financeiro/arquivo/documento/${x.id}`, x.nome)}><DownloadIcon fontSize="small" /></IconButton>
            ))}
            {['em_analise', 'aberta', 'atrasada'].includes(f.status) && <Button size="small" color="success" onClick={() => acao(() => api.post(`/plataforma/financeiro/faturas/${f.id}/confirmar`), 'Pagamento confirmado.')}>Confirmar pagamento</Button>}
            {f.status === 'em_analise' && <Button size="small" onClick={() => setDevolver(f)}>Devolver</Button>}
            {f.status !== 'paga' && f.status !== 'cancelada' && <Button size="small" color="error" onClick={() => setCancelarFat(f)}>Cancelar</Button>}
          </Linha>
        ))}
      </Bloco>

      <Bloco titulo="Documentos" acao={<Button size="small" startIcon={<UploadFileIcon />} onClick={anexar}>Anexar</Button>}>
        {d.documentos.filter((x: any) => x.tipo !== 'comprovante').length === 0 ? <Vazio /> : d.documentos.filter((x: any) => x.tipo !== 'comprovante').map((x: any) => (
          <Linha key={x.id}>
            <Typography variant="body2" sx={{ flex: 1 }}>{x.nome}{x.descricao ? ` — ${x.descricao}` : ''}</Typography>
            <Typography variant="caption" color="text.secondary">{dataHoraBR(x.enviado_em)}</Typography>
            <IconButton size="small" onClick={() => baixar(`/plataforma/financeiro/arquivo/documento/${x.id}`, x.nome)}><DownloadIcon fontSize="small" /></IconButton>
          </Linha>
        ))}
      </Bloco>

      <Dialog open={!!proposta} onClose={() => setProposta(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Nova proposta para {d.banca.nome}</DialogTitle>
        <DialogContent>
          {proposta && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField select label="Plano" value={proposta.plano_id} onChange={(e) => setProposta({ ...proposta, plano_id: e.target.value })}>
                {planos.filter(p => p.ativo).map(p => <MenuItem key={p.id} value={p.id}>{p.nome} — {moeda(p.valor_mensal)}/mês · {moeda(p.valor_anual)}/ano</MenuItem>)}
              </TextField>
              <TextField select label="Periodicidade" value={proposta.periodicidade} onChange={(e) => setProposta({ ...proposta, periodicidade: e.target.value })}>
                <MenuItem value="mensal">Mensal</MenuItem><MenuItem value="anual">Anual</MenuItem>
              </TextField>
              <TextField label="Desconto (%)" type="number" value={proposta.desconto} onChange={(e) => setProposta({ ...proposta, desconto: e.target.value })} />
              <TextField label="Válida até" type="date" InputLabelProps={{ shrink: true }} value={proposta.validade} onChange={(e) => setProposta({ ...proposta, validade: e.target.value })} />
              <TextField label="O que está incluído (um item por linha)" multiline minRows={3} value={proposta.itens} onChange={(e) => setProposta({ ...proposta, itens: e.target.value })} />
              <TextField label="Condições (pagamento, reajuste, prazo...)" multiline minRows={3} value={proposta.condicoes} onChange={(e) => setProposta({ ...proposta, condicoes: e.target.value })} />
              <Typography variant="caption" color="text.secondary">Uma proposta nova substitui a anterior que ainda estava aguardando resposta.</Typography>
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setProposta(null)}>Cancelar</Button>
          <Button variant="contained" disabled={!proposta?.plano_id} onClick={() => {
            const p = proposta; setProposta(null);
            acao(() => api.post(`/plataforma/financeiro/bancas/${id}/propostas`, {
              plano_id: Number(p.plano_id), periodicidade: p.periodicidade, desconto: Number(p.desconto) || 0, condicoes: p.condicoes,
              validade: p.validade || null, itens: String(p.itens || '').split('\n').map((x: string) => x.trim()).filter(Boolean),
            }), 'Proposta enviada para a banca.');
          }}>Enviar proposta</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!termo} onClose={() => setTermo(null)} maxWidth="md" fullWidth>
        <DialogTitle>Enviar documento para aceite</DialogTitle>
        <DialogContent>
          {termo && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField select label="Tipo" value={termo.tipo} onChange={(e) => setTermo({ ...termo, tipo: e.target.value })}>
                <MenuItem value="contrato">Contrato de prestação de serviços</MenuItem><MenuItem value="termos_uso">Termos de uso</MenuItem>
                <MenuItem value="lgpd">Acordo de tratamento de dados (LGPD)</MenuItem><MenuItem value="aditivo">Aditivo contratual</MenuItem>
                <MenuItem value="outro">Outro</MenuItem>
              </TextField>
              <TextField label="Título" value={termo.titulo} onChange={(e) => setTermo({ ...termo, titulo: e.target.value })} />
              <TextField label="Descrição curta" value={termo.descricao} onChange={(e) => setTermo({ ...termo, descricao: e.target.value })} />
              <Button component="label" variant="outlined" startIcon={<UploadFileIcon />}>
                {termo.arquivo ? termo.arquivo.name : 'Enviar o PDF'}
                <input hidden type="file" accept=".pdf" onChange={(e) => setTermo({ ...termo, arquivo: e.target.files?.[0] || null })} />
              </Button>
              {!termo.arquivo && <TextField label="...ou escreva o texto (vira PDF)" multiline minRows={8} value={termo.texto} onChange={(e) => setTermo({ ...termo, texto: e.target.value })} />}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTermo(null)}>Cancelar</Button>
          <Button variant="contained" disabled={!termo?.titulo || (!termo?.arquivo && !termo?.texto?.trim())} onClick={() => {
            const t = termo; setTermo(null);
            const fd = new FormData();
            fd.append('tipo', t.tipo); fd.append('titulo', t.titulo); fd.append('descricao', t.descricao || '');
            if (t.arquivo) fd.append('arquivo', t.arquivo); else fd.append('texto', t.texto);
            acao(() => api.post(`/plataforma/financeiro/bancas/${id}/termos`, fd), 'Documento enviado para a banca aceitar.');
          }}>Enviar</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!fatura} onClose={() => setFatura(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Emitir fatura</DialogTitle>
        <DialogContent>
          {fatura && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <TextField label="Competência" type="month" InputLabelProps={{ shrink: true }} value={fatura.competencia} onChange={(e) => setFatura({ ...fatura, competencia: e.target.value })} />
              <TextField label="Vencimento" type="date" InputLabelProps={{ shrink: true }} value={fatura.vencimento} onChange={(e) => setFatura({ ...fatura, vencimento: e.target.value })} />
              <FormControlLabel control={<Checkbox checked={fatura.usarPlano} onChange={(e) => setFatura({ ...fatura, usarPlano: e.target.checked })} />} label="Valor da proposta aceita (plano contratado)" />
              {!fatura.usarPlano && <TextField label="Valor (R$)" type="number" value={fatura.valor} onChange={(e) => setFatura({ ...fatura, valor: e.target.value })} />}
              <TextField label="Descrição" value={fatura.descricao} onChange={(e) => setFatura({ ...fatura, descricao: e.target.value })} />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFatura(null)}>Cancelar</Button>
          <Button variant="contained" disabled={!fatura?.vencimento || !fatura?.competencia || (!fatura?.usarPlano && !Number(fatura?.valor))} onClick={() => {
            const f = fatura; setFatura(null);
            acao(() => api.post(`/plataforma/financeiro/bancas/${id}/faturas`, {
              competencia: f.competencia, vencimento: f.vencimento, descricao: f.descricao, valor: f.usarPlano ? null : Number(f.valor),
            }), 'Fatura emitida e enviada para a banca.');
          }}>Emitir</Button>
        </DialogActions>
      </Dialog>
      <DialogoTexto aberto={!!devolver} titulo="Devolver o comprovante" rotulo="Motivo (a banca vê)" minimo={3} botao="Devolver" onFechar={() => setDevolver(null)}
        onConfirmar={async (m) => { await api.post(`/plataforma/financeiro/faturas/${devolver.id}/devolver`, { motivo: m }); setDevolver(null); carregar(); }} />
      <DialogoTexto aberto={!!cancelarFat} titulo="Cancelar a fatura" rotulo="Motivo" minimo={3} botao="Cancelar fatura" cor="error" onFechar={() => setCancelarFat(null)}
        onConfirmar={async (m) => { await api.post(`/plataforma/financeiro/faturas/${cancelarFat.id}/cancelar`, { motivo: m }); setCancelarFat(null); carregar(); }} />
    </Box>
  );
};

const Planos: React.FC = () => {
  const [planos, setPlanos] = useState<any[] | null>(null);
  const [edit, setEdit] = useState<any>(null);
  const [erro, setErro] = useState<string | null>(null);
  const carregar = useCallback(() => { api.get('/plataforma/financeiro/planos').then(({ data }) => setPlanos(data)).catch(() => setPlanos([])); }, []);
  useEffect(() => { carregar(); }, [carregar]);
  const salvar = async () => {
    try {
      const corpo = { ...edit, valor_mensal: Number(edit.valor_mensal) || 0, valor_anual: Number(edit.valor_anual) || 0,
        limite_eventos: edit.limite_eventos === '' || edit.limite_eventos == null ? null : Number(edit.limite_eventos),
        limite_usuarios: edit.limite_usuarios === '' || edit.limite_usuarios == null ? null : Number(edit.limite_usuarios),
        limite_questoes: edit.limite_questoes === '' || edit.limite_questoes == null ? null : Number(edit.limite_questoes) };
      if (edit.id) await api.put(`/plataforma/financeiro/planos/${edit.id}`, corpo); else await api.post('/plataforma/financeiro/planos', corpo);
      setEdit(null); carregar();
    } catch (e: any) { setErro(erroApi(e, 'Não foi possível salvar.')); }
  };
  if (!planos) return <Typography>Carregando...</Typography>;
  return (
    <Box>
      <Stack direction="row" justifyContent="flex-end" sx={{ mb: 1.5 }}>
        <Button variant="contained" onClick={() => setEdit({ codigo: '', nome: '', descricao: '', valor_mensal: 0, valor_anual: 0, ativo: true })}>Novo plano</Button>
      </Stack>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, minmax(0,1fr))' }, gap: 2 }}>
        {planos.map(p => (
          <Paper key={p.id} variant="outlined" sx={{ p: 2, borderRadius: 3, opacity: p.ativo ? 1 : 0.6 }}>
            <Typography fontWeight={800}>{p.nome}</Typography>
            <Typography variant="h6">{moeda(p.valor_mensal)}<Typography component="span" variant="caption"> /mês</Typography></Typography>
            <Typography variant="body2" color="text.secondary">{moeda(p.valor_anual)} /ano</Typography>
            <Divider sx={{ my: 1 }} />
            <Typography variant="body2" sx={{ whiteSpace: 'pre-line' }}>{p.descricao || '—'}</Typography>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
              Limites: {p.limite_eventos ?? '∞'} eventos · {p.limite_usuarios ?? '∞'} usuários · {p.limite_questoes ?? '∞'} questões{p.ativo ? '' : ' · inativo'}
            </Typography>
            <Button size="small" sx={{ mt: 1 }} onClick={() => setEdit({ ...p })}>Editar</Button>
          </Paper>
        ))}
      </Box>
      <Dialog open={!!edit} onClose={() => setEdit(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{edit?.id ? 'Editar plano' : 'Novo plano'}</DialogTitle>
        <DialogContent>
          {edit && (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 1.5 }}>
                <TextField label="Código" value={edit.codigo} onChange={(e) => setEdit({ ...edit, codigo: e.target.value })} />
                <TextField label="Nome" value={edit.nome} onChange={(e) => setEdit({ ...edit, nome: e.target.value })} />
                <TextField label="Mensal (R$)" type="number" value={edit.valor_mensal} onChange={(e) => setEdit({ ...edit, valor_mensal: e.target.value })} />
                <TextField label="Anual (R$)" type="number" value={edit.valor_anual} onChange={(e) => setEdit({ ...edit, valor_anual: e.target.value })} />
              </Box>
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.5 }}>
                <TextField label="Máx. eventos" type="number" value={edit.limite_eventos ?? ''} onChange={(e) => setEdit({ ...edit, limite_eventos: e.target.value })} />
                <TextField label="Máx. usuários" type="number" value={edit.limite_usuarios ?? ''} onChange={(e) => setEdit({ ...edit, limite_usuarios: e.target.value })} />
                <TextField label="Máx. questões" type="number" value={edit.limite_questoes ?? ''} onChange={(e) => setEdit({ ...edit, limite_questoes: e.target.value })} />
              </Box>
              <TextField label="O que inclui (um item por linha)" multiline minRows={4} value={edit.descricao} onChange={(e) => setEdit({ ...edit, descricao: e.target.value })} />
              <FormControlLabel control={<Checkbox checked={!!edit.ativo} onChange={(e) => setEdit({ ...edit, ativo: e.target.checked })} />} label="Disponível para novas propostas" />
              {erro && <Alert severity="error">{erro}</Alert>}
            </Stack>
          )}
        </DialogContent>
        <DialogActions><Button onClick={() => setEdit(null)}>Cancelar</Button><Button variant="contained" onClick={salvar} disabled={!edit?.codigo || !edit?.nome}>Salvar</Button></DialogActions>
      </Dialog>
    </Box>
  );
};

const Cobranca: React.FC = () => {
  const [c, setC] = useState<any>(null);
  const [msg, setMsg] = useState<{ tipo: 'success' | 'error'; texto: string } | null>(null);
  const [inicio, setInicio] = useState('');
  const [fim, setFim] = useState('');
  useEffect(() => { api.get('/plataforma/financeiro/cobranca').then(({ data }) => setC(data)).catch(() => setC(null)); }, []);
  if (!c) return <Typography>Carregando...</Typography>;
  const salvar = async () => {
    try {
      await api.put('/config/plataforma', { financeiro: Object.fromEntries(Object.entries(c).map(([k, v]) => [k, Number(v) || 0])) });
      setMsg({ tipo: 'success', texto: 'Regras de cobrança salvas.' });
    } catch (e: any) { setMsg({ tipo: 'error', texto: erroApi(e, 'Não foi possível salvar.') }); }
  };
  const campos: [string, string, string][] = [
    ['lembrete_fatura_dias', 'Avisar a banca antes do vencimento (dias)', 'A banca recebe o aviso N dias antes de cada fatura vencer.'],
    ['aviso_atraso_cada_dias', 'Repetir o aviso de atraso a cada (dias)', 'A banca e a plataforma recebem o aviso de atraso nesse intervalo.'],
    ['suspender_apos_dias', 'Suspender a banca após atraso de (dias)', '0 = nunca suspende sozinho. Suspensa: ninguém da banca entra; os dados ficam guardados.'],
    ['lembrete_aceite_dias', 'Lembrar o professor do contrato não aceito a cada (dias)', 'Depois de 7 dias sem aceite, a banca também é avisada.'],
  ];
  return (
    <Stack spacing={2.5}>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800} sx={{ mb: 1.5 }}>Cobrança e lembretes automáticos</Typography>
        <Stack spacing={2}>
          {campos.map(([k, rot, ajuda]) => (
            <TextField key={k} type="number" label={rot} helperText={ajuda} value={c[k]} onChange={(e) => setC({ ...c, [k]: e.target.value })} sx={{ maxWidth: 520 }} />
          ))}
        </Stack>
        {msg && <Alert severity={msg.tipo} sx={{ mt: 2 }}>{msg.texto}</Alert>}
        <Button variant="contained" sx={{ mt: 2 }} onClick={salvar}>Salvar</Button>
      </Paper>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800} sx={{ mb: 1.5 }}>Receita da plataforma (abre no Excel)</Typography>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems={{ md: 'center' }}>
          <TextField size="small" type="month" label="Competência de" InputLabelProps={{ shrink: true }} value={inicio} onChange={(e) => setInicio(e.target.value)} />
          <TextField size="small" type="month" label="até" InputLabelProps={{ shrink: true }} value={fim} onChange={(e) => setFim(e.target.value)} />
          <Button variant="contained" onClick={() => {
            const q = new URLSearchParams();
            if (inicio) q.set('inicio', inicio);
            if (fim) q.set('fim', fim);
            baixar(`/plataforma/financeiro/relatorios/faturas.csv${q.toString() ? `?${q}` : ''}`, 'faturas-plataforma.csv');
          }}>Faturas (CSV)</Button>
        </Stack>
      </Paper>
    </Stack>
  );
};

const Bloco: React.FC<{ titulo: string; acao?: React.ReactNode; children: React.ReactNode }> = ({ titulo, acao, children }) => (
  <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 2 }}>
    <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
      <Typography fontWeight={800}>{titulo}</Typography>{acao}
    </Stack>
    <Stack divider={<Divider />}>{children}</Stack>
  </Paper>
);
const Linha: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Stack direction="row" spacing={1.5} alignItems="center" sx={{ py: 1, flexWrap: { xs: 'wrap', md: 'nowrap' } }}>{children}</Stack>
);
const Vazio = () => <Typography variant="body2" color="text.secondary">Nada por aqui.</Typography>;

export default FinanceiroPlataforma;
