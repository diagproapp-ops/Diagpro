import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Dialog, DialogContent, DialogTitle, IconButton, MenuItem, Paper, Stack, Tab, Table, TableBody,
  TableCell, TableHead, TableRow, Tabs, TextField, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import api from '../../api';
import ContratoDetalhe from './ContratoDetalhe';
import ContratoEditor, { BASES_CURTAS } from './ContratoEditor';
import PlataformaDaBanca from './PlataformaDaBanca';
import { Indicador, StatusChip, baixar, erroApi, moeda } from './comum';

// Financeiro da banca: contratos com os professores (cada um com a sua negociação), configuração e a relação com a plataforma.
const FinanceiroBanca: React.FC = () => {
  const [aba, setAba] = useState<'professores' | 'relatorios' | 'config' | 'plataforma'>('professores');
  return (
    <Box>
      <Tabs value={aba} onChange={(_, v) => setAba(v)} sx={{ mb: 2.5 }}>
        <Tab value="professores" label="Professores e contratos" />
        <Tab value="relatorios" label="Relatórios" />
        <Tab value="config" label="Tabela, parcelas e modelos" />
        <Tab value="plataforma" label="Minha conta na plataforma" />
      </Tabs>
      {aba === 'professores' && <Professores />}
      {aba === 'relatorios' && <Relatorios />}
      {aba === 'config' && <Configuracao />}
      {aba === 'plataforma' && <PlataformaDaBanca />}
    </Box>
  );
};

const Professores: React.FC = () => {
  const [evento, setEvento] = useState('');
  const [v, setV] = useState<any>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [novo, setNovo] = useState<{ professor?: number } | null>(null);
  const [aberto, setAberto] = useState<any>(null);
  const [editar, setEditar] = useState<any>(null);
  const [msgLote, setMsgLote] = useState<string | null>(null);
  const gerarLote = async () => {
    if (!evento) return;
    if (!window.confirm('Criar um rascunho de contrato para cada professor com conteúdo neste evento (quem já tem contrato fica de fora)?\n\nPreços, parcelas e bônus vêm do padrão da banca; as quantidades, dos conteúdos. Nada é enviado: revise e envie cada um.')) return;
    try {
      const { data } = await api.post('/financeiro/contratos/lote', { evento_id: evento });
      setMsgLote(data.criados ? `${data.criados} rascunho(s) criado(s)${data.ja_tinham_contrato ? `; ${data.ja_tinham_contrato} professor(es) já tinham contrato` : ''}. Revise e envie cada um.`
        : 'Nenhum contrato novo: todos os professores com conteúdo neste evento já têm contrato.');
      carregar();
    } catch (e: any) { setErro(erroApi(e, 'Não foi possível gerar os contratos.')); }
  };

  const carregar = useCallback(() => {
    api.get('/financeiro/visao', { params: evento ? { evento_id: evento } : {} }).then(({ data }) => setV(data))
      .catch((e) => setErro(erroApi(e, 'Não foi possível carregar.')));
  }, [evento]);
  useEffect(() => { carregar(); }, [carregar]);
  const abrir = useCallback(async (id: number) => {
    try { setAberto((await api.get(`/financeiro/contratos/${id}`)).data); } catch (e: any) { setErro(erroApi(e, 'Não foi possível abrir.')); }
  }, []);

  if (!v) return erro ? <Alert severity="error">{erro}</Alert> : <Typography>Carregando...</Typography>;
  return (
    <Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, minmax(0,1fr))', md: 'repeat(4, minmax(0,1fr))' }, gap: 1.5, mb: 2.5 }}>
        <Indicador rotulo="Previsto nos contratos" valor={moeda(v.totais.previsto)} />
        <Indicador rotulo="Apurado (regra de cada contrato)" valor={moeda(v.totais.apurado)} />
        <Indicador rotulo="Liberado a pagar" valor={moeda(v.totais.a_receber)} cor="#f59e0b" />
        <Indicador rotulo="Já pago" valor={moeda(v.totais.pago)} cor="#10b981" />
      </Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} justifyContent="space-between" sx={{ mb: 2 }}>
        <TextField select size="small" label="Evento" value={evento} onChange={(e) => setEvento(e.target.value)} sx={{ minWidth: 280 }}>
          <MenuItem value="">Todos os eventos</MenuItem>
          {v.eventos.map((e: any) => <MenuItem key={e.id} value={e.id}>{e.nome}</MenuItem>)}
        </TextField>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" disabled={!evento} onClick={gerarLote}>Gerar contratos do evento</Button>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setNovo({})}>Novo contrato</Button>
        </Stack>
      </Stack>
      {erro && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErro(null)}>{erro}</Alert>}
      {msgLote && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMsgLote(null)}>{msgLote}</Alert>}
      {!evento && <Alert severity="info" sx={{ mb: 2 }}>Escolha um evento para gerar de uma vez os contratos de todos os professores dele.</Alert>}
      {v.sem_contrato.length > 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Com produção neste evento e sem contrato: {v.sem_contrato.map((s: any) => (
            <Button key={s.professor_id} size="small" onClick={() => setNovo({ professor: s.professor_id })}>{s.professor} ({s.producao.total})</Button>
          ))}
        </Alert>
      )}
      <Paper variant="outlined" sx={{ borderRadius: 2, overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Contrato</TableCell><TableCell>Professor</TableCell><TableCell>Evento</TableCell><TableCell>Questões</TableCell>
              <TableCell align="right">Previsto</TableCell><TableCell align="right">Liberado</TableCell><TableCell align="right">Pago</TableCell><TableCell>Situação</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {v.contratos.length === 0 && <TableRow><TableCell colSpan={8}><Typography color="text.secondary" sx={{ py: 2 }}>Nenhum contrato ainda. Clique em "Novo contrato".</Typography></TableCell></TableRow>}
            {v.contratos.map((c: any) => (
              <TableRow key={c.id} hover sx={{ cursor: 'pointer' }} onClick={() => abrir(c.id)}>
                <TableCell><Typography fontWeight={700} variant="body2">{c.numero}</Typography></TableCell>
                <TableCell>{c.professor}</TableCell>
                <TableCell>{c.evento}</TableCell>
                <TableCell>{c.producao.aprovadas}/{c.producao.total}</TableCell>
                <TableCell align="right">{moeda(c.totais.previsto)}</TableCell>
                <TableCell align="right">{moeda(c.totais.liberado)}</TableCell>
                <TableCell align="right">{moeda(c.totais.pago)}</TableCell>
                <TableCell><StatusChip status={c.status} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      <ContratoEditor aberto={!!novo || !!editar} professores={v.professores} eventos={v.eventos} inicial={editar || undefined}
        eventoPadrao={evento} professorPadrao={novo?.professor}
        onFechar={() => { setNovo(null); setEditar(null); }}
        onSalvo={(id) => { setNovo(null); setEditar(null); carregar(); abrir(id); }} />
      <Dialog open={!!aberto} onClose={() => { setAberto(null); carregar(); }} maxWidth="lg" fullWidth>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'flex-end', py: 1 }}>
          <IconButton onClick={() => { setAberto(null); carregar(); }}><CloseIcon /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ pt: 0 }}>
          {aberto && <ContratoDetalhe c={aberto} modo="banca" onAtualizar={() => abrir(aberto.id)}
            onEditar={() => { setEditar(aberto); setAberto(null); }} />}
        </DialogContent>
      </Dialog>
    </Box>
  );
};

const Configuracao: React.FC = () => {
  const [cfg, setCfg] = useState<any>(null);
  const [msg, setMsg] = useState<{ tipo: 'success' | 'error'; texto: string } | null>(null);
  useEffect(() => { api.get('/financeiro/config').then(({ data }) => setCfg(data)).catch(() => setCfg(null)); }, []);
  if (!cfg) return <Typography>Carregando...</Typography>;
  const set = (k: string, v: any) => setCfg((x: any) => ({ ...x, [k]: v }));
  const setParc = (i: number, k: string, v: any) => set('cronograma', cfg.cronograma.map((p: any, j: number) => (j === i ? { ...p, [k]: v } : p)));
  const setFaixa = (i: number, pos: number, v: any) => set('retencoes', {
    ...cfg.retencoes, irrf_faixas: cfg.retencoes.irrf_faixas.map((x: any[], j: number) => (j === i ? x.map((y, n) => (n === pos ? v : y)) : x)),
  });
  const salvar = async () => {
    try {
      await api.put('/financeiro/config', {
        precos: Object.fromEntries(Object.entries(cfg.precos).map(([k, v]) => [k, Number(v) || 0])),
        cronograma: cfg.cronograma.map((p: any) => ({ ...p, base: p.base || null, percentual: p.percentual === '' || p.percentual === null ? null : Number(p.percentual),
          valor_fixo: p.valor_fixo === '' || p.valor_fixo === null || p.valor_fixo === undefined ? null : Number(p.valor_fixo), data_prevista: p.data_prevista || null })),
        clausulas_contrato: cfg.clausulas_contrato, clausulas_cessao: cfg.clausulas_cessao, contratante: cfg.contratante,
        observacoes_padrao: cfg.observacoes_padrao || '', tipo_pessoa_padrao: cfg.tipo_pessoa_padrao,
        base_pagamento_padrao: cfg.base_pagamento_padrao || 'aprovadas',
        bonus_padrao: { tipo: cfg.bonus_padrao?.tipo || 'nenhum', valor: Number(cfg.bonus_padrao?.valor) || 0 },
        retencoes: {
          ...cfg.retencoes,
          irrf_faixas: cfg.retencoes.irrf_faixas.map((f: any[]) => [f[0] === '' || f[0] === null ? null : Number(f[0]), Number(f[1]) || 0, Number(f[2]) || 0]),
        },
      });
      setMsg({ tipo: 'success', texto: 'Configuração salva. Vale para os próximos contratos (os já criados não mudam).' });
    } catch (e: any) { setMsg({ tipo: 'error', texto: erroApi(e, 'Não foi possível salvar.') }); }
  };
  return (
    <Stack spacing={2.5}>
      <Alert severity="info">Estes são só os padrões que preenchem um contrato novo. Cada contrato pode ter preços, quantidades, parcelas e condições próprios.</Alert>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800} sx={{ mb: 1.5 }}>Tabela de preços padrão</Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 1.5 }}>
          {Object.entries(cfg.rotulos_precos).map(([k, rot]: any) => (
            <TextField key={k} size="small" type="number" label={`${rot} (R$)`} value={cfg.precos[k] ?? 0} onChange={(e) => set('precos', { ...cfg.precos, [k]: e.target.value })} />
          ))}
        </Box>
      </Paper>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Stack direction="row" justifyContent="space-between" sx={{ mb: 1.5 }}>
          <Typography fontWeight={800}>Parcelas padrão</Typography>
          <Button size="small" startIcon={<AddIcon />} onClick={() => set('cronograma', [...cfg.cronograma, { descricao: '', percentual: 0, valor_fixo: null, gatilho: 'manual', data_prevista: null, base: '' }])}>Parcela</Button>
        </Stack>
        <TextField select size="small" label="Base do pagamento padrão" value={cfg.base_pagamento_padrao || 'aprovadas'} sx={{ mb: 1.5, minWidth: 340 }}
          onChange={(e) => set('base_pagamento_padrao', e.target.value)}
          helperText="Sobre o que o percentual das parcelas é calculado. Cada contrato e cada parcela podem mudar.">
          {Object.entries(cfg.bases || {}).map(([k, v]: any) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
        </TextField>
        <Stack spacing={1}>
          {cfg.cronograma.map((p: any, i: number) => (
            <Box key={i} sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '2fr 0.7fr 1.1fr 1.6fr auto' }, gap: 1, alignItems: 'center' }}>
              <TextField size="small" label={`Parcela ${i + 1}`} value={p.descricao} onChange={(e) => setParc(i, 'descricao', e.target.value)} />
              <TextField size="small" type="number" label="%" value={p.percentual ?? ''} onChange={(e) => setParc(i, 'percentual', e.target.value)} />
              <TextField size="small" select label="% sobre" value={p.base || ''} onChange={(e) => setParc(i, 'base', e.target.value)}
                  SelectProps={{ displayEmpty: true }} InputLabelProps={{ shrink: true }}>
                <MenuItem value="">Base padrão</MenuItem>
                {Object.entries(BASES_CURTAS).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
              </TextField>
              <TextField size="small" select label="Libera quando" value={p.gatilho} onChange={(e) => setParc(i, 'gatilho', e.target.value)}>
                {Object.entries(cfg.gatilhos).map(([k, v]: any) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
              </TextField>
              <IconButton onClick={() => set('cronograma', cfg.cronograma.filter((_: any, j: number) => j !== i))}><DeleteOutlineIcon /></IconButton>
            </Box>
          ))}
        </Stack>
      </Paper>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800} sx={{ mb: 1.5 }}>Bônus e forma de pagamento padrão</Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.4fr 0.6fr 1.4fr' }, gap: 1.5 }}>
          <TextField select size="small" label="Bônus por qualidade" value={cfg.bonus_padrao?.tipo || 'nenhum'}
            onChange={(e) => set('bonus_padrao', { ...cfg.bonus_padrao, tipo: e.target.value })}>
            {Object.entries(cfg.tipos_bonus).map(([k, v]: any) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
          </TextField>
          <TextField size="small" type="number" label={cfg.bonus_padrao?.tipo === 'percentual' ? '%' : 'R$'} disabled={(cfg.bonus_padrao?.tipo || 'nenhum') === 'nenhum'}
            value={cfg.bonus_padrao?.valor ?? 0} onChange={(e) => set('bonus_padrao', { ...cfg.bonus_padrao, valor: e.target.value })} />
          <TextField select size="small" label="Professor recebe como" value={cfg.tipo_pessoa_padrao || 'pf_rpa'} onChange={(e) => set('tipo_pessoa_padrao', e.target.value)}>
            {Object.entries(cfg.tipos_pessoa).map(([k, v]: any) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
          </TextField>
        </Box>
      </Paper>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800}>Retenções do RPA (pessoa física)</Typography>
        <Alert severity="warning" sx={{ my: 1.5 }}>
          Valores de referência (INSS de contribuinte individual, tabela mensal do IRRF e redutor de 2026). Confira com a
          contabilidade e atualize quando a lei mudar. O ISS depende do município.
        </Alert>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 1.5, mb: 2 }}>
          {[['inss_percentual', 'INSS (%)'], ['inss_teto', 'Teto do INSS (R$)'], ['iss_percentual', 'ISS (%)'], ['irrf_deducao_dependente', 'Dedução por dependente (R$)']].map(([k, rot]) => (
            <TextField key={k} size="small" type="number" label={rot} value={cfg.retencoes[k]} onChange={(e) => set('retencoes', { ...cfg.retencoes, [k]: e.target.value })} />
          ))}
        </Box>
        <Typography variant="body2" fontWeight={700} sx={{ mb: 1 }}>Tabela do IRRF (mensal)</Typography>
        {cfg.retencoes.irrf_faixas.map((f: any[], i: number) => (
          <Box key={i} sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1, mb: 1 }}>
            <TextField size="small" type="number" label={f[0] === null ? 'Acima da faixa anterior' : 'Até (R$)'} value={f[0] ?? ''}
              onChange={(e) => setFaixa(i, 0, e.target.value === '' ? null : e.target.value)} />
            <TextField size="small" type="number" label="Alíquota (%)" value={f[1]} onChange={(e) => setFaixa(i, 1, e.target.value)} />
            <TextField size="small" type="number" label="Parcela a deduzir (R$)" value={f[2]} onChange={(e) => setFaixa(i, 2, e.target.value)} />
          </Box>
        ))}
        <Typography variant="body2" fontWeight={700} sx={{ mt: 1.5, mb: 1 }}>Redutor do IRRF</Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 1.5 }}>
          {[['isento_ate', 'Isento até (R$)'], ['faixa_ate', 'Redução até (R$)'], ['a', 'Redução: valor fixo'], ['b', 'Redução: fator']].map(([k, rot]) => (
            <TextField key={k} size="small" type="number" label={rot} value={cfg.retencoes.irrf_redutor[k]}
              onChange={(e) => set('retencoes', { ...cfg.retencoes, irrf_redutor: { ...cfg.retencoes.irrf_redutor, [k]: e.target.value } })} />
          ))}
        </Box>
      </Paper>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800} sx={{ mb: 1 }}>Contratante (aparece no contrato)</Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)' }, gap: 1.5 }}>
          {[['razao_social', 'Razão social'], ['cnpj', 'CNPJ'], ['endereco', 'Endereço'], ['cidade', 'Cidade/UF']].map(([k, rot]) => (
            <TextField key={k} size="small" label={rot} value={cfg.contratante?.[k] || ''} onChange={(e) => set('contratante', { ...cfg.contratante, [k]: e.target.value })} />
          ))}
        </Box>
      </Paper>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800}>Modelos de texto</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Variáveis: {cfg.variaveis.map((x: string) => `{${x}}`).join(', ')}. Recomendamos revisar os textos com o jurídico da banca.
        </Typography>
        <Stack spacing={2}>
          <TextField label="Cláusulas do contrato" multiline minRows={8} value={cfg.clausulas_contrato} onChange={(e) => set('clausulas_contrato', e.target.value)} />
          <TextField label="Termo de cessão de direitos e sigilo" multiline minRows={8} value={cfg.clausulas_cessao} onChange={(e) => set('clausulas_cessao', e.target.value)} />
          <TextField label="Observações padrão do contrato" multiline minRows={2} value={cfg.observacoes_padrao || ''} onChange={(e) => set('observacoes_padrao', e.target.value)} />
        </Stack>
      </Paper>
      {msg && <Alert severity={msg.tipo} onClose={() => setMsg(null)}>{msg.texto}</Alert>}
      <Box><Button variant="contained" onClick={salvar}>Salvar configuração</Button></Box>
    </Stack>
  );
};

const Relatorios: React.FC = () => {
  const [linhas, setLinhas] = useState<any[] | null>(null);
  const [inicio, setInicio] = useState('');
  const [fim, setFim] = useState('');
  useEffect(() => { api.get('/financeiro/relatorios/resumo').then(({ data }) => setLinhas(data.eventos)).catch(() => setLinhas([])); }, []);
  if (!linhas) return <Typography>Carregando...</Typography>;
  const total = (k: string) => linhas.reduce((s, e) => s + (e[k] || 0), 0);
  return (
    <Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, minmax(0,1fr))', md: 'repeat(4, minmax(0,1fr))' }, gap: 1.5, mb: 2.5 }}>
        <Indicador rotulo="Custo apurado (todos os eventos)" valor={moeda(total('apurado'))} detalhe={total('bonus') ? `inclui ${moeda(total('bonus'))} de bônus` : undefined} />
        <Indicador rotulo="Pago (bruto)" valor={moeda(total('pago'))} cor="#10b981" />
        <Indicador rotulo="Retido (INSS, IRRF, ISS)" valor={moeda(total('retido'))} detalhe="a recolher pela banca" />
        <Indicador rotulo="Questões aprovadas" valor={total('aprovadas')} />
      </Box>
      <Paper variant="outlined" sx={{ borderRadius: 2, overflowX: 'auto', mb: 2.5 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Evento</TableCell><TableCell align="right">Professores</TableCell><TableCell align="right">Aprovadas</TableCell>
              <TableCell align="right">Previsto</TableCell><TableCell align="right">Apurado</TableCell><TableCell align="right">Bônus</TableCell>
              <TableCell align="right">Pago</TableCell><TableCell align="right">Retido</TableCell><TableCell align="right">Custo por questão</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {linhas.length === 0 && <TableRow><TableCell colSpan={9}><Typography color="text.secondary" sx={{ py: 2 }}>Sem contratos enviados ainda.</Typography></TableCell></TableRow>}
            {linhas.map(e => (
              <TableRow key={e.evento_id}>
                <TableCell>{e.evento}</TableCell><TableCell align="right">{e.professores}</TableCell><TableCell align="right">{e.aprovadas}</TableCell>
                <TableCell align="right">{moeda(e.previsto)}</TableCell><TableCell align="right">{moeda(e.apurado)}</TableCell>
                <TableCell align="right">{moeda(e.bonus)}</TableCell><TableCell align="right">{moeda(e.pago)}</TableCell>
                <TableCell align="right">{moeda(e.retido)}</TableCell><TableCell align="right">{e.custo_por_questao ? moeda(e.custo_por_questao) : '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography fontWeight={800} sx={{ mb: 1.5 }}>Exportar para a contabilidade (abre no Excel)</Typography>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems={{ md: 'center' }}>
          <Button variant="outlined" onClick={() => baixar('/financeiro/relatorios/contratos.csv', 'contratos-professores.csv')}>Contratos (CSV)</Button>
          <TextField size="small" type="date" label="Pagamentos de" InputLabelProps={{ shrink: true }} value={inicio} onChange={(e) => setInicio(e.target.value)} />
          <TextField size="small" type="date" label="até" InputLabelProps={{ shrink: true }} value={fim} onChange={(e) => setFim(e.target.value)} />
          <Button variant="contained" onClick={() => {
            const q = new URLSearchParams();
            if (inicio) q.set('inicio', inicio);
            if (fim) q.set('fim', fim);
            baixar(`/financeiro/relatorios/pagamentos.csv${q.toString() ? `?${q}` : ''}`, 'pagamentos-professores.csv');
          }}>Pagamentos com retenções (CSV)</Button>
        </Stack>
      </Paper>
    </Box>
  );
};

export default FinanceiroBanca;
