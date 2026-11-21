import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Divider, IconButton, MenuItem, Stack, TextField,
  ToggleButton, ToggleButtonGroup, Tooltip, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import api from '../../api';
import { erroApi, moeda } from './comum';

export type Parcela = { descricao: string; percentual: number | null; valor_fixo: number | null; gatilho: string; data_prevista: string | null };
type Config = { precos: Record<string, number>; cronograma: Parcela[]; rotulos_precos: Record<string, string>; gatilhos: Record<string, string> };

const numero = (v: any) => (v === '' || v === null || v === undefined ? null : Number(v));

// Negociação do professor: começa da tabela e do cronograma padrão da banca, mas cada contrato é livre.
const ContratoEditor: React.FC<{
  aberto: boolean; onFechar: () => void; onSalvo: (id: number) => void;
  professores: { id: number; nome: string }[]; eventos: { id: string; nome: string }[];
  inicial?: any; eventoPadrao?: string; professorPadrao?: number;
}> = ({ aberto, onFechar, onSalvo, professores, eventos, inicial, eventoPadrao, professorPadrao }) => {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [f, setF] = useState<any>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!aberto) return;
    setErro(null);
    api.get('/financeiro/config').then(({ data }) => {
      setCfg(data);
      setF(inicial ? {
        professor_id: inicial.professor_id, evento_id: inicial.evento_id, modalidade: inicial.modalidade,
        precos: { ...data.precos, ...(inicial.dados?.precos || {}) }, quantidades: { ...(inicial.dados?.quantidades || {}) },
        valor_fechado: inicial.dados?.valor_fechado ?? '', prazo_entrega: inicial.dados?.prazo_entrega || '',
        observacoes: inicial.dados?.observacoes || '',
        parcelas: inicial.parcelas.map((p: any) => ({ descricao: p.descricao, percentual: p.percentual, valor_fixo: p.valor_fixo,
          gatilho: p.gatilho, data_prevista: p.data_prevista })),
      } : {
        professor_id: professorPadrao || '', evento_id: eventoPadrao || '', modalidade: 'por_questao', precos: { ...data.precos },
        quantidades: {}, valor_fechado: '', prazo_entrega: '', observacoes: '', parcelas: data.cronograma.map((p: Parcela) => ({ ...p })),
      });
    }).catch((e) => setErro(erroApi(e, 'Não foi possível carregar a configuração.')));
  }, [aberto, inicial, eventoPadrao, professorPadrao]);

  const previsto = useMemo(() => {
    if (!f || !cfg) return 0;
    if (f.modalidade === 'valor_fechado') return Number(f.valor_fechado) || 0;
    return Object.keys(cfg.rotulos_precos).reduce((s, k) => s + (Number(f.precos[k]) || 0) * (Number(f.quantidades[k]) || 0), 0);
  }, [f, cfg]);
  const somaPct = f ? f.parcelas.filter((p: Parcela) => p.valor_fixo === null || p.valor_fixo === undefined || (p.valor_fixo as any) === '')
    .reduce((s: number, p: Parcela) => s + (Number(p.percentual) || 0), 0) : 0;

  const set = (k: string, v: any) => setF((x: any) => ({ ...x, [k]: v }));
  const setParc = (i: number, k: string, v: any) => setF((x: any) => ({ ...x, parcelas: x.parcelas.map((p: any, j: number) => (j === i ? { ...p, [k]: v } : p)) }));

  const salvar = async () => {
    setSalvando(true); setErro(null);
    try {
      const corpo = {
        professor_id: Number(f.professor_id), evento_id: f.evento_id, modalidade: f.modalidade,
        precos: Object.fromEntries(Object.entries(f.precos).map(([k, v]) => [k, Number(v) || 0])),
        quantidades: Object.fromEntries(Object.entries(f.quantidades).map(([k, v]) => [k, Number(v) || 0])),
        valor_fechado: f.modalidade === 'valor_fechado' ? Number(f.valor_fechado) || 0 : null,
        prazo_entrega: f.prazo_entrega || null, observacoes: f.observacoes,
        parcelas: f.parcelas.map((p: any) => ({ descricao: p.descricao, gatilho: p.gatilho, data_prevista: p.data_prevista || null,
          percentual: numero(p.percentual), valor_fixo: numero(p.valor_fixo) })),
      };
      if (inicial) { await api.put(`/financeiro/contratos/${inicial.id}`, corpo); onSalvo(inicial.id); }
      else { const { data } = await api.post('/financeiro/contratos', corpo); onSalvo(data.id); }
    } catch (e: any) { setErro(erroApi(e, 'Não foi possível salvar o contrato.')); }
    finally { setSalvando(false); }
  };

  return (
    <Dialog open={aberto} onClose={onFechar} maxWidth="md" fullWidth>
      <DialogTitle>{inicial ? `Editar contrato ${inicial.numero}` : 'Novo contrato de elaboração'}</DialogTitle>
      <DialogContent dividers>
        {!f || !cfg ? (erro ? <Alert severity="error">{erro}</Alert> : <Typography>Carregando...</Typography>) : (
          <Stack spacing={2.25}>
            {inicial && inicial.status !== 'rascunho' && (
              <Alert severity="warning">Salvar alterações volta o contrato para rascunho: será preciso enviar de novo para o professor aceitar.</Alert>
            )}
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
              <TextField select label="Professor" value={f.professor_id} disabled={!!inicial} onChange={(e) => set('professor_id', e.target.value)}>
                {professores.map(p => <MenuItem key={p.id} value={p.id}>{p.nome}</MenuItem>)}
              </TextField>
              <TextField select label="Evento" value={f.evento_id} disabled={!!inicial} onChange={(e) => set('evento_id', e.target.value)}>
                {eventos.map(ev => <MenuItem key={ev.id} value={ev.id}>{ev.nome}</MenuItem>)}
              </TextField>
            </Box>
            <Box>
              <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 1 }}>Remuneração</Typography>
              <ToggleButtonGroup exclusive size="small" value={f.modalidade} onChange={(_, v) => v && set('modalidade', v)}>
                <ToggleButton value="por_questao">Por questão elaborada</ToggleButton>
                <ToggleButton value="valor_fechado">Valor fechado</ToggleButton>
              </ToggleButtonGroup>
            </Box>
            {f.modalidade === 'valor_fechado' ? (
              <TextField label="Valor fechado (R$)" type="number" value={f.valor_fechado} onChange={(e) => set('valor_fechado', e.target.value)} sx={{ maxWidth: 260 }} />
            ) : (
              <Box sx={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 1.25, alignItems: 'center' }}>
                <Typography variant="caption" color="text.secondary">Tipo</Typography>
                <Typography variant="caption" color="text.secondary">Preço (R$)</Typography>
                <Typography variant="caption" color="text.secondary">Quantidade</Typography>
                <Typography variant="caption" color="text.secondary" textAlign="right">Subtotal</Typography>
                {Object.entries(cfg.rotulos_precos).map(([k, rot]) => (
                  <React.Fragment key={k}>
                    <Typography variant="body2">{rot}</Typography>
                    <TextField size="small" type="number" value={f.precos[k] ?? 0} onChange={(e) => set('precos', { ...f.precos, [k]: e.target.value })} />
                    <TextField size="small" type="number" value={f.quantidades[k] ?? ''} placeholder="0"
                      onChange={(e) => set('quantidades', { ...f.quantidades, [k]: e.target.value })} />
                    <Typography variant="body2" textAlign="right">{moeda((Number(f.precos[k]) || 0) * (Number(f.quantidades[k]) || 0))}</Typography>
                  </React.Fragment>
                ))}
              </Box>
            )}
            <Typography fontWeight={800}>Total estimado: {moeda(previsto)}
              {f.modalidade === 'por_questao' && <Typography component="span" variant="caption" color="text.secondary"> — o valor final é calculado sobre as questões aprovadas</Typography>}
            </Typography>
            <TextField label="Prazo de entrega" placeholder="ex.: 15/12/2026" value={f.prazo_entrega} onChange={(e) => set('prazo_entrega', e.target.value)} sx={{ maxWidth: 260 }} />
            <Divider />
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="subtitle2" fontWeight={800}>Parcelas e condições</Typography>
              <Button size="small" startIcon={<AddIcon />} onClick={() => set('parcelas', [...f.parcelas, { descricao: '', percentual: 0, valor_fixo: null, gatilho: 'manual', data_prevista: null }])}>Parcela</Button>
            </Stack>
            {f.parcelas.map((p: any, i: number) => (
              <Box key={i} sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '2fr 0.8fr 1fr 1.6fr 1.1fr auto' }, gap: 1, alignItems: 'center' }}>
                <TextField size="small" label={`Parcela ${i + 1}`} value={p.descricao} onChange={(e) => setParc(i, 'descricao', e.target.value)} />
                <TextField size="small" label="%" type="number" value={p.percentual ?? ''} disabled={p.valor_fixo !== null && p.valor_fixo !== '' && p.valor_fixo !== undefined}
                  onChange={(e) => setParc(i, 'percentual', e.target.value)} />
                <Tooltip title="Se preencher, vale o valor em vez do percentual">
                  <TextField size="small" label="ou valor (R$)" type="number" value={p.valor_fixo ?? ''} onChange={(e) => setParc(i, 'valor_fixo', e.target.value === '' ? null : e.target.value)} />
                </Tooltip>
                <TextField size="small" select label="Libera quando" value={p.gatilho} onChange={(e) => setParc(i, 'gatilho', e.target.value)}>
                  {Object.entries(cfg.gatilhos).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
                </TextField>
                <TextField size="small" type="date" label="Data" InputLabelProps={{ shrink: true }} value={p.data_prevista || ''}
                  disabled={p.gatilho !== 'data'} onChange={(e) => setParc(i, 'data_prevista', e.target.value || null)} />
                <IconButton onClick={() => set('parcelas', f.parcelas.filter((_: any, j: number) => j !== i))}><DeleteOutlineIcon /></IconButton>
              </Box>
            ))}
            {somaPct > 0 && Math.abs(somaPct - 100) > 0.01 && (
              <Alert severity="warning">Os percentuais somam {somaPct.toLocaleString('pt-BR')}% (o normal é 100%).</Alert>
            )}
            <TextField label="Observações (entram no contrato)" multiline minRows={2} value={f.observacoes} onChange={(e) => set('observacoes', e.target.value)} />
            {erro && <Alert severity="error">{erro}</Alert>}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onFechar}>Cancelar</Button>
        <Button variant="contained" onClick={salvar} disabled={!f || salvando || !f.professor_id || !f.evento_id || !f.parcelas.length}>
          {salvando ? 'Salvando...' : 'Salvar rascunho'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ContratoEditor;
