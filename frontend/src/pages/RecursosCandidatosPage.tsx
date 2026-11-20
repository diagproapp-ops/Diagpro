import React, { useCallback, useEffect, useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, Divider, MenuItem, Paper, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useParams } from 'react-router-dom';
import Layout from '../components/Layout';
import api from '../api';

const PEDIDOS: Record<string, string> = { anulacao: 'Anulação', alteracao: 'Alteração de gabarito', outro: 'Outro' };
const DECISAO: Record<string, { rotulo: string; cor: 'default' | 'error' | 'warning' }> = {
  manter: { rotulo: 'Gabarito mantido', cor: 'default' }, anular: { rotulo: 'Anulada', cor: 'error' }, alterar: { rotulo: 'Gabarito alterado', cor: 'warning' },
};
const erroDe = (e: any, padrao: string) => (typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : padrao);

// Recursos dos candidatos: cadastrar/importar, parecer, decisão por questão e gabarito definitivo
const RecursosCandidatosPage: React.FC = () => {
  const { eventId } = useParams();
  const [senha, setSenha] = useState('');
  const [cargos, setCargos] = useState<any[]>([]);
  const [dados, setDados] = useState<any>(null);
  const [msg, setMsg] = useState<{ texto: string; tipo: 'success' | 'error' | 'info' } | null>(null);
  const [novo, setNovo] = useState({ cargo_id: '', tipo_prova: 'PADRÃO', numero_questao: 1, pedido: 'anulacao', protocolo: '', argumentacao: '' });
  const [decisoes, setDecisoes] = useState<Record<string, { decisao: string; nova_correta: string; justificativa: string }>>({});
  const [definitivo, setDefinitivo] = useState<any[] | null>(null);

  const carregar = useCallback(() => {
    api.get(`/recursos/eventos/${eventId}`).then(({ data }) => setDados(data)).catch(e => setMsg({ texto: erroDe(e, 'Não foi possível carregar.'), tipo: 'error' }));
  }, [eventId]);
  useEffect(() => {
    carregar();
    api.get(`/eventos/${eventId}/cargos/provas-geracao`).then(({ data }) => setCargos(data)).catch(() => {});
  }, [carregar, eventId]);

  const cabecalho = { headers: { 'X-Senha-Evento': senha } };
  const cadastrar = async () => {
    try {
      await api.post(`/recursos/eventos/${eventId}`, { ...novo, numero_questao: Number(novo.numero_questao) }, cabecalho);
      setMsg({ texto: 'Recurso cadastrado.', tipo: 'success' });
      setNovo({ ...novo, protocolo: '', argumentacao: '' });
      carregar();
    } catch (e) { setMsg({ texto: erroDe(e, 'Não foi possível cadastrar.'), tipo: 'error' }); }
  };
  const importar = async (f: File | undefined) => {
    if (!f) return;
    const fd = new FormData();
    fd.append('arquivo', f);
    try {
      const { data } = await api.post(`/recursos/eventos/${eventId}/importar`, fd, cabecalho);
      setMsg({ texto: `${data.importados} recurso(s) importado(s).${data.total_problemas ? ` ${data.total_problemas} linha(s) com problema: ${data.problemas.slice(0, 3).join(' | ')}` : ''}`, tipo: data.total_problemas ? 'info' : 'success' });
      carregar();
    } catch (e) { setMsg({ texto: erroDe(e, 'Não foi possível importar.'), tipo: 'error' }); }
  };
  const parecer = async (id: number) => {
    const texto = window.prompt('Parecer técnico sobre este recurso:');
    if (!texto) return;
    try { await api.put(`/recursos/${id}/parecer`, { parecer: texto }); carregar(); }
    catch (e) { setMsg({ texto: erroDe(e, 'Não foi possível salvar o parecer.'), tipo: 'error' }); }
  };
  const decidir = async (g: any) => {
    const k = `${g.id_questao}|${g.item ?? ''}`;
    const d = decisoes[k] || { decisao: 'manter', nova_correta: '', justificativa: '' };
    try {
      await api.post(`/recursos/eventos/${eventId}/questoes/${g.id_questao}/decidir`,
        { item: g.item, decisao: d.decisao, nova_correta: d.decisao === 'alterar' ? d.nova_correta : null, justificativa: d.justificativa });
      setMsg({ texto: `Decisão registrada para ${g.codigo}${g.item ? ` item ${g.item}` : ''}.`, tipo: 'success' });
      carregar();
    } catch (e) { setMsg({ texto: erroDe(e, 'Não foi possível decidir.'), tipo: 'error' }); }
  };
  const verDefinitivo = async () => {
    try { setDefinitivo((await api.get(`/recursos/eventos/${eventId}/gabarito-definitivo`, cabecalho)).data); }
    catch (e) { setMsg({ texto: erroDe(e, 'Não foi possível calcular o gabarito definitivo.'), tipo: 'error' }); }
  };
  const baixarDefinitivo = () => {
    const linhas = ['cargo;tipo_prova;questao;codigo;preliminar;definitivo'];
    (definitivo || []).forEach(c => c.questoes.forEach((q: any) => linhas.push([c.cargo, c.tipo_prova, q.numero, q.codigo, q.preliminar, q.definitivo].join(';'))));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['﻿' + linhas.join('\n')], { type: 'text/csv' }));
    a.download = 'gabarito_definitivo.csv';
    a.click();
  };
  const set = (k: string, campo: string, valor: string) =>
    setDecisoes(prev => ({ ...prev, [k]: { ...(prev[k] || { decisao: 'manter', nova_correta: '', justificativa: '' }), [campo]: valor } }));

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Typography variant="h5" fontWeight="bold">Recursos dos candidatos</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Cadastre ou importe os recursos (questão do caderno de cada tipo de prova), registre o parecer técnico e decida por
          questão. A prova aplicada nunca é alterada: o gabarito definitivo de cada caderno é calculado a partir das decisões.
          Do candidato, só ficam o protocolo e a argumentação, cifrados.
        </Typography>
        {msg && <Alert severity={msg.tipo} sx={{ mb: 2 }} onClose={() => setMsg(null)}>{msg.texto}</Alert>}

        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, mb: 2 }}>
          <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
            <TextField size="small" type="password" label="Senha do evento" value={senha} onChange={e => setSenha(e.target.value)} autoComplete="off" />
            <TextField select size="small" label="Cargo" value={novo.cargo_id} onChange={e => setNovo({ ...novo, cargo_id: e.target.value })} sx={{ minWidth: 220 }}>
              {cargos.map(c => <MenuItem key={c.id_cargo} value={c.id_cargo}>{c.codigo_cargo ? `${c.codigo_cargo} - ` : ''}{c.nome_cargo}</MenuItem>)}
            </TextField>
            <TextField size="small" label="Tipo de prova" value={novo.tipo_prova} onChange={e => setNovo({ ...novo, tipo_prova: e.target.value })} sx={{ width: 130 }} />
            <TextField size="small" type="number" label="Questão nº" value={novo.numero_questao} onChange={e => setNovo({ ...novo, numero_questao: Number(e.target.value) })} sx={{ width: 110 }} />
            <TextField select size="small" label="Pedido" value={novo.pedido} onChange={e => setNovo({ ...novo, pedido: e.target.value })} sx={{ width: 190 }}>
              {Object.entries(PEDIDOS).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
            <TextField size="small" label="Protocolo" value={novo.protocolo} onChange={e => setNovo({ ...novo, protocolo: e.target.value })} sx={{ width: 140 }} />
          </Box>
          <TextField fullWidth size="small" multiline minRows={2} sx={{ mt: 1.5 }} label="Argumentação do candidato" value={novo.argumentacao}
            onChange={e => setNovo({ ...novo, argumentacao: e.target.value })} />
          <Box sx={{ display: 'flex', gap: 1.5, mt: 1.5, flexWrap: 'wrap' }}>
            <Button variant="contained" disabled={!senha || !novo.cargo_id} onClick={cadastrar}>Cadastrar recurso</Button>
            <Button variant="outlined" component="label" disabled={!senha}>
              Importar CSV
              <input hidden type="file" accept=".csv,text/csv" onChange={e => importar(e.target.files?.[0])} />
            </Button>
            <Button variant="outlined" color="secondary" disabled={!senha} onClick={verDefinitivo}>Gabarito definitivo</Button>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            CSV: colunas cargo (código ou nome), tipo_prova, questao, pedido, protocolo, argumentacao. Nome, CPF e outras colunas são ignorados.
          </Typography>
        </Paper>

        {!dados ? <CircularProgress /> : !dados.questoes.length ? <Typography color="text.secondary">Nenhum recurso cadastrado.</Typography> : (
          <>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{dados.total_recursos} recurso(s) em {dados.questoes.length} questão(ões). Sem decisão aparecem primeiro.</Typography>
            {dados.questoes.map((g: any) => {
              const k = `${g.id_questao}|${g.item ?? ''}`;
              const d = decisoes[k] || { decisao: 'manter', nova_correta: '', justificativa: '' };
              const ce = g.tipo === 'CERTO_ERRADO';
              return (
                <Accordion key={k} disableGutters>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                      <Typography fontWeight={700}>{g.codigo}{g.item ? ` • item ${g.item}` : ''}</Typography>
                      <Chip size="small" label={`${g.recursos.length} recurso(s)`} />
                      {g.decisao ? <Chip size="small" color={DECISAO[g.decisao.decisao].cor} label={DECISAO[g.decisao.decisao].rotulo + (g.decisao.nova_correta ? ` → ${g.decisao.nova_correta}` : '')} />
                        : <Chip size="small" color="info" variant="outlined" label="Aguardando decisão" />}
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Typography variant="body2" sx={{ mb: 1 }}>{g.enunciado}</Typography>
                    {g.alternativas.map((a: any) => (
                      <Typography key={a.letra} variant="body2" sx={{ fontWeight: a.correta ? 700 : 400, color: a.correta ? 'success.main' : undefined }}>
                        {a.letra}) {a.texto}{a.correta ? '  ✓ (gabarito preliminar)' : ''}
                      </Typography>
                    ))}
                    <Divider sx={{ my: 1.5 }} />
                    {g.recursos.map((r: any) => (
                      <Box key={r.id} sx={{ mb: 1.5, pl: 1.5, borderLeft: '3px solid', borderColor: 'divider' }}>
                        <Typography variant="caption" color="text.secondary">
                          {r.tipo_prova} • questão {r.numero} • {PEDIDOS[r.pedido]} • protocolo {r.protocolo || '—'} • {r.status}
                        </Typography>
                        {r.argumentacao && <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{r.argumentacao}</Typography>}
                        {r.parecer ? <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}><b>Parecer{r.parecer_por ? ` (${r.parecer_por})` : ''}:</b> {r.parecer}</Typography> : null}
                        <Button size="small" onClick={() => parecer(r.id)}>{r.parecer ? 'Trocar parecer' : 'Dar parecer'}</Button>
                      </Box>
                    ))}
                    <Divider sx={{ my: 1.5 }} />
                    <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'flex-start' }}>
                      <TextField select size="small" label="Decisão" value={d.decisao} onChange={e => set(k, 'decisao', e.target.value)} sx={{ width: 200 }}>
                        <MenuItem value="manter">Manter gabarito (indeferir)</MenuItem>
                        <MenuItem value="anular">Anular</MenuItem>
                        <MenuItem value="alterar">Alterar gabarito</MenuItem>
                      </TextField>
                      {d.decisao === 'alterar' && (
                        <TextField select size="small" label="Nova resposta" value={d.nova_correta} onChange={e => set(k, 'nova_correta', e.target.value)} sx={{ width: 150 }}>
                          {(ce ? ['C', 'E'] : g.alternativas.map((a: any) => a.letra)).map((l: string) => <MenuItem key={l} value={l}>{ce ? (l === 'C' ? 'Certo' : 'Errado') : l}</MenuItem>)}
                        </TextField>
                      )}
                      <TextField size="small" multiline minRows={2} label="Justificativa (publicável)" value={d.justificativa}
                        onChange={e => set(k, 'justificativa', e.target.value)} sx={{ flex: 1, minWidth: 260 }} />
                      <Button variant="contained" onClick={() => decidir(g)} disabled={d.justificativa.trim().length < 5 || (d.decisao === 'alterar' && !d.nova_correta)}>
                        {g.decisao ? 'Atualizar decisão' : 'Decidir'}
                      </Button>
                    </Box>
                    {g.decisao?.justificativa && <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>Atual: {g.decisao.justificativa} ({g.decisao.por})</Typography>}
                  </AccordionDetails>
                </Accordion>
              );
            })}
          </>
        )}
      </Paper>

      <Dialog open={!!definitivo} onClose={() => setDefinitivo(null)} maxWidth="md" fullWidth>
        <DialogTitle>Gabarito definitivo</DialogTitle>
        <DialogContent dividers>
          {(definitivo || []).map(c => (
            <Box key={c.cargo_id + c.tipo_prova} sx={{ mb: 2 }}>
              <Typography fontWeight={700}>{c.cargo} • {c.tipo_prova}</Typography>
              <Table size="small">
                <TableHead><TableRow><TableCell>Questão</TableCell><TableCell>Código</TableCell><TableCell>Preliminar</TableCell><TableCell>Definitivo</TableCell></TableRow></TableHead>
                <TableBody>
                  {c.questoes.map((q: any) => (
                    <TableRow key={q.numero} sx={{ bgcolor: q.alterada ? 'rgba(245,158,11,0.15)' : undefined }}>
                      <TableCell>{q.numero}</TableCell><TableCell>{q.codigo}</TableCell><TableCell>{q.preliminar}</TableCell>
                      <TableCell sx={{ fontWeight: q.alterada ? 800 : 400 }}>{q.definitivo}{q.aviso ? ` (${q.aviso})` : ''}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          ))}
        </DialogContent>
        <DialogActions>
          <Button onClick={baixarDefinitivo}>Baixar CSV</Button>
          <Button onClick={() => setDefinitivo(null)}>Fechar</Button>
        </DialogActions>
      </Dialog>
    </Layout>
  );
};

export default RecursosCandidatosPage;
