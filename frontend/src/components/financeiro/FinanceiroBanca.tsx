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
import ContratoEditor from './ContratoEditor';
import PlataformaDaBanca from './PlataformaDaBanca';
import { Indicador, StatusChip, erroApi, moeda } from './comum';

// Financeiro da banca: contratos com os professores (cada um com a sua negociação), configuração e a relação com a plataforma.
const FinanceiroBanca: React.FC = () => {
  const [aba, setAba] = useState<'professores' | 'config' | 'plataforma'>('professores');
  return (
    <Box>
      <Tabs value={aba} onChange={(_, v) => setAba(v)} sx={{ mb: 2.5 }}>
        <Tab value="professores" label="Professores e contratos" />
        <Tab value="config" label="Tabela, parcelas e modelos" />
        <Tab value="plataforma" label="Minha conta na plataforma" />
      </Tabs>
      {aba === 'professores' && <Professores />}
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
        <Indicador rotulo="Apurado (aprovadas)" valor={moeda(v.totais.apurado)} />
        <Indicador rotulo="Liberado a pagar" valor={moeda(v.totais.a_receber)} cor="#f59e0b" />
        <Indicador rotulo="Já pago" valor={moeda(v.totais.pago)} cor="#10b981" />
      </Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} justifyContent="space-between" sx={{ mb: 2 }}>
        <TextField select size="small" label="Evento" value={evento} onChange={(e) => setEvento(e.target.value)} sx={{ minWidth: 280 }}>
          <MenuItem value="">Todos os eventos</MenuItem>
          {v.eventos.map((e: any) => <MenuItem key={e.id} value={e.id}>{e.nome}</MenuItem>)}
        </TextField>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setNovo({})}>Novo contrato</Button>
      </Stack>
      {erro && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErro(null)}>{erro}</Alert>}
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
  const salvar = async () => {
    try {
      await api.put('/financeiro/config', {
        precos: Object.fromEntries(Object.entries(cfg.precos).map(([k, v]) => [k, Number(v) || 0])),
        cronograma: cfg.cronograma.map((p: any) => ({ ...p, percentual: p.percentual === '' || p.percentual === null ? null : Number(p.percentual),
          valor_fixo: p.valor_fixo === '' || p.valor_fixo === null || p.valor_fixo === undefined ? null : Number(p.valor_fixo), data_prevista: p.data_prevista || null })),
        clausulas_contrato: cfg.clausulas_contrato, clausulas_cessao: cfg.clausulas_cessao, contratante: cfg.contratante,
        observacoes_padrao: cfg.observacoes_padrao || '',
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
          <Button size="small" startIcon={<AddIcon />} onClick={() => set('cronograma', [...cfg.cronograma, { descricao: '', percentual: 0, valor_fixo: null, gatilho: 'manual', data_prevista: null }])}>Parcela</Button>
        </Stack>
        <Stack spacing={1}>
          {cfg.cronograma.map((p: any, i: number) => (
            <Box key={i} sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '2fr 0.7fr 1.6fr auto' }, gap: 1, alignItems: 'center' }}>
              <TextField size="small" label={`Parcela ${i + 1}`} value={p.descricao} onChange={(e) => setParc(i, 'descricao', e.target.value)} />
              <TextField size="small" type="number" label="%" value={p.percentual ?? ''} onChange={(e) => setParc(i, 'percentual', e.target.value)} />
              <TextField size="small" select label="Libera quando" value={p.gatilho} onChange={(e) => setParc(i, 'gatilho', e.target.value)}>
                {Object.entries(cfg.gatilhos).map(([k, v]: any) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
              </TextField>
              <IconButton onClick={() => set('cronograma', cfg.cronograma.filter((_: any, j: number) => j !== i))}><DeleteOutlineIcon /></IconButton>
            </Box>
          ))}
        </Stack>
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

export default FinanceiroBanca;
