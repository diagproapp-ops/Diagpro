import React, { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, IconButton, MenuItem, Paper, Stack,
  Table, TableBody, TableCell, TableHead, TableRow, TextField, Tooltip, Typography,
} from '@mui/material';
import PictureAsPdfOutlinedIcon from '@mui/icons-material/PictureAsPdfOutlined';
import DownloadIcon from '@mui/icons-material/Download';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import api from '../../api';
import { DialogoAceite, DialogoTexto, Indicador, StatusChip, baixar, dataBR, dataHoraBR, erroApi, moeda } from './comum';

const AJUSTES: Record<string, string> = { desconto: 'Desconto', acrescimo: 'Acréscimo', adiantamento: 'Adiantamento' };
const TIPOS_PRECO: Record<string, string> = {
  MULTIPLA_ESCOLHA: 'Múltipla escolha', CERTO_ERRADO_ITEM: 'Itens C/E', CERTO_ERRADO_BASE: 'Questões C/E', DISCURSIVA: 'Discursiva', SUBJETIVA: 'Subjetiva',
};

// Um contrato: totais, produção, parcelas (com o que falta para liberar), ajustes e documentos.
const ContratoDetalhe: React.FC<{ c: any; modo: 'banca' | 'professor'; onAtualizar: () => void; onEditar?: () => void }> = ({ c, modo, onAtualizar, onEditar }) => {
  const [erro, setErro] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [aceite, setAceite] = useState(false);
  const [recusa, setRecusa] = useState(false);
  const [cancelar, setCancelar] = useState(false);
  const [liberar, setLiberar] = useState<any>(null);
  const [pagar, setPagar] = useState<any>(null);
  const [ajuste, setAjuste] = useState<any>(null);
  const [previa, setPrevia] = useState<any>(null);
  const banca = modo === 'banca';
  const pf = (c.dados?.tipo_pessoa || 'pf_rpa') === 'pf_rpa';

  // retenções do RPA calculadas pelo servidor enquanto o valor é digitado (pessoa física)
  useEffect(() => {
    if (!pagar || !pf || !Number(pagar.valor)) { setPrevia(null); return undefined; }
    const t = setTimeout(() => {
      api.get(`/financeiro/parcelas/${pagar.id}/retencoes`, { params: { valor: Number(pagar.valor), dependentes: Number(pagar.dependentes) || 0 } })
        .then(({ data }) => setPrevia(data.aplica ? data : null)).catch(() => setPrevia(null));
    }, 300);
    return () => clearTimeout(t);
  }, [pagar, pf]);

  const acao = async (fn: () => Promise<any>, ok: string) => {
    setErro(null); setMsg(null);
    try { await fn(); setMsg(ok); onAtualizar(); } catch (e: any) { setErro(erroApi(e, 'Não foi possível concluir.')); }
  };
  const enviarArquivo = (url: string, extra: Record<string, string>, ok: string) => {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.pdf,.png,.jpg,.jpeg,.xml';
    input.onchange = () => {
      const arq = input.files?.[0];
      if (!arq) return;
      const fd = new FormData();
      Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
      fd.append('arquivo', arq);
      acao(() => api.post(url, fd), ok);
    };
    input.click();
  };

  const t = c.totais;
  return (
    <Box>
      <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between" spacing={1.5} sx={{ mb: 2 }}>
        <Box>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="h6" fontWeight={800}>Contrato {c.numero}</Typography>
            <StatusChip status={c.status} />
          </Stack>
          <Typography variant="body2" color="text.secondary">
            {banca ? `${c.professor} · ` : ''}{c.evento} · {c.modalidade === 'valor_fechado' ? `valor fechado ${moeda(c.dados?.valor_fechado)}` : 'por questão elaborada'}
            {c.dados?.prazo_entrega ? ` · entrega até ${c.dados.prazo_entrega}` : ''}
            {` · ${pf ? 'pessoa física (RPA)' : 'nota fiscal'}`}
            {c.dados?.bonus && c.dados.bonus.tipo !== 'nenhum' ? ` · bônus ${c.dados.bonus.tipo === 'percentual' ? `${c.dados.bonus.valor}%` : moeda(c.dados.bonus.valor)} por questão aprovada de primeira` : ''}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
          {c.tem_documento && <Button size="small" variant="outlined" startIcon={<PictureAsPdfOutlinedIcon />}
            onClick={() => baixar(`/financeiro/contratos/${c.id}/pdf`, `contrato-${c.numero}.pdf`)}>Contrato (PDF)</Button>}
          {banca && ['rascunho', 'recusado'].includes(c.status) && (
            <Button size="small" variant="contained" onClick={() => acao(() => api.post(`/financeiro/contratos/${c.id}/enviar`), 'Contrato enviado ao professor.')}>Enviar para aceite</Button>
          )}
          {banca && ['rascunho', 'enviado', 'recusado'].includes(c.status) && onEditar && <Button size="small" onClick={onEditar}>Editar</Button>}
          {banca && c.status === 'aceito' && <Button size="small" onClick={() => acao(() => api.post(`/financeiro/contratos/${c.id}/encerrar`), 'Contrato encerrado.')}>Encerrar</Button>}
          {banca && !['cancelado', 'encerrado'].includes(c.status) && <Button size="small" color="error" onClick={() => setCancelar(true)}>Cancelar</Button>}
          {!banca && c.status === 'enviado' && (
            <>
              <Button size="small" variant="contained" color="success" onClick={() => setAceite(true)}>Aceitar contrato</Button>
              <Button size="small" color="error" onClick={() => setRecusa(true)}>Recusar</Button>
            </>
          )}
        </Stack>
      </Stack>
      {erro && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setErro(null)}>{erro}</Alert>}
      {msg && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMsg(null)}>{msg}</Alert>}
      {c.status === 'recusado' && c.dados?.motivo_recusa && <Alert severity="error" sx={{ mb: 2 }}>Recusado pelo professor: {c.dados.motivo_recusa}</Alert>}
      {c.aceite && (
        <Alert severity="success" icon={<CheckCircleOutlineIcon />} sx={{ mb: 2 }}>
          Aceito eletronicamente por {c.aceite.por} em {dataHoraBR(c.aceite.em)} (IP {c.aceite.ip || '—'}) · código {c.aceite.codigo}
        </Alert>
      )}

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, minmax(0,1fr))', md: 'repeat(4, minmax(0,1fr))' }, gap: 1.5, mb: 2 }}>
        <Indicador rotulo="Previsto no contrato" valor={moeda(t.previsto)} />
        <Indicador rotulo={`Apurado (${({ aprovadas: 'aprovadas', entregues: 'entregues', integral: 'integral' } as Record<string, string>)[c.base_pagamento] || 'aprovadas'})`} valor={moeda(t.apurado)} detalhe={t.bonus ? `inclui ${moeda(t.bonus)} de bônus por qualidade` : undefined} />
        <Indicador rotulo="Liberado" valor={moeda(t.liberado)} cor="#f59e0b" detalhe={t.a_receber ? `${moeda(t.a_receber)} a pagar` : undefined} />
        <Indicador rotulo="Pago" valor={moeda(t.pago)} cor="#10b981" />
      </Box>

      <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 2 }}>
        <Typography fontWeight={800} sx={{ mb: 1 }}>Produção no evento</Typography>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', rowGap: 1 }}>
          <Chip label={`${c.producao.aprovadas} aprovada(s) de ${c.producao.total}`} color={c.producao.pendentes ? 'warning' : 'success'} variant="outlined" />
          {c.producao.aprovadas > 0 && <Chip size="small" color="success" variant="outlined" label={`${c.producao.aprovadas_primeira ?? 0} aprovada(s) de primeira`} />}
          {Object.entries(c.producao.por_tipo || {}).map(([k, v]: any) => (
            <Chip key={k} size="small" variant="outlined" label={`${TIPOS_PRECO[k] || k}: ${v.aprovadas}/${v.total}`} />
          ))}
          {c.producao.itens_ce_aprovados > 0 && <Chip size="small" variant="outlined" label={`Itens C/E aprovados: ${c.producao.itens_ce_aprovados}`} />}
          <Chip size="small" variant="outlined" label={`Recursos: ${c.recursos.total - c.recursos.pendentes}/${c.recursos.total} decididos`} />
        </Stack>
        {banca && c.producao.anuladas?.length > 0 && (
          <Alert severity="warning" sx={{ mt: 1.5 }}>Questões anuladas: {c.producao.anuladas.join(', ')}. Se foi erro de elaboração, lance um desconto na parcela.</Alert>
        )}
      </Paper>

      <Typography fontWeight={800} sx={{ mb: 1 }}>Parcelas</Typography>
      <Paper variant="outlined" sx={{ borderRadius: 2, mb: 2, overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow><TableCell>#</TableCell><TableCell>Parcela</TableCell><TableCell>Condição</TableCell><TableCell align="right">Valor</TableCell><TableCell>Situação</TableCell><TableCell /></TableRow>
          </TableHead>
          <TableBody>
            {c.parcelas.map((p: any) => (
              <React.Fragment key={p.id}>
                <TableRow>
                  <TableCell>{p.ordem}</TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight={700}>{p.descricao || `Parcela ${p.ordem}`}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {p.valor_fixo !== null && p.valor_fixo !== undefined && p.valor_fixo !== '' ? 'valor fixo'
                        : `${p.percentual}% ${({ aprovadas: 'das aprovadas', entregues: 'das entregues', integral: 'do valor integral' } as Record<string, string>)[p.base || c.base_pagamento] || 'do total'}`}
                    </Typography>
                  </TableCell>
                  <TableCell sx={{ maxWidth: 320 }}>
                    <Typography variant="body2">{p.gatilho_rotulo}{p.data_prevista ? ` (${dataBR(p.data_prevista)})` : ''}</Typography>
                    {p.status === 'prevista' && <Typography variant="caption" color={p.gatilho_cumprido ? 'success.main' : 'text.secondary'}>{p.explicacao}</Typography>}
                    {p.liberacao && p.status !== 'prevista' && <Typography variant="caption" color="text.secondary" display="block">Liberada {dataBR(p.liberada_em)} — {p.liberacao}</Typography>}
                    {p.pagamento && <Typography variant="caption" color="text.secondary" display="block">Pago em {dataBR(p.pagamento.data)}{p.pagamento.forma ? ` (${p.pagamento.forma})` : ''}
                      {p.retencoes ? ` · líquido ${moeda(p.retencoes.liquido)} (INSS ${moeda(p.retencoes.inss)}, IRRF ${moeda(p.retencoes.irrf)}${p.retencoes.iss ? `, ISS ${moeda(p.retencoes.iss)}` : ''})` : ''}</Typography>}
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" fontWeight={800}>{moeda(p.a_pagar)}</Typography>
                    {p.estimado && <Typography variant="caption" color="text.secondary">estimado</Typography>}
                    {p.a_pagar !== p.valor_base && <Typography variant="caption" color="text.secondary" display="block">base {moeda(p.valor_base)}</Typography>}
                  </TableCell>
                  <TableCell><StatusChip status={p.status} /></TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                    {banca && c.status === 'aceito' && p.status === 'prevista' && <Button size="small" onClick={() => setLiberar(p)}>Liberar</Button>}
                    {banca && p.status === 'liberada' && <Button size="small" variant="contained" onClick={() => setPagar({ ...p, valor: p.a_pagar, data: new Date().toISOString().slice(0, 10), forma: 'PIX', arquivo: null })}>Registrar pagamento</Button>}
                    {banca && ['prevista', 'liberada'].includes(p.status) && c.status === 'aceito' && <Button size="small" onClick={() => setAjuste({ parcela_id: p.id, tipo: 'desconto', valor: '', motivo: '' })}>Ajuste</Button>}
                    {!banca && ['liberada', 'paga', 'confirmada'].includes(p.status) && (
                      <Tooltip title="Envie a nota fiscal ou o RPA desta parcela">
                        <Button size="small" startIcon={<UploadFileIcon />} onClick={() => enviarArquivo(`/financeiro/meu/parcelas/${p.id}/nota-fiscal`, { tipo: 'nota_fiscal' }, 'Nota fiscal enviada.')}>Nota fiscal</Button>
                      </Tooltip>
                    )}
                    {!banca && p.status === 'paga' && <Button size="small" variant="contained" color="success" onClick={() => acao(() => api.post(`/financeiro/meu/parcelas/${p.id}/confirmar`), 'Recebimento confirmado.')}>Confirmar recebimento</Button>}
                  </TableCell>
                </TableRow>
                {p.ajustes.map((a: any) => (
                  <TableRow key={`a${a.id}`} sx={{ '& td': { borderBottom: 0, py: 0.25 } }}>
                    <TableCell />
                    <TableCell colSpan={2}><Typography variant="caption" color="text.secondary">{AJUSTES[a.tipo] || a.tipo}: {a.motivo}</Typography></TableCell>
                    <TableCell align="right"><Typography variant="caption" color={a.tipo === 'acrescimo' ? 'success.main' : 'error.main'}>{a.tipo === 'acrescimo' ? '+' : '−'}{moeda(a.valor)}</Typography></TableCell>
                    <TableCell colSpan={2}>
                      {banca && ['prevista', 'liberada'].includes(p.status) && (
                        <IconButton size="small" onClick={() => acao(() => api.delete(`/financeiro/ajustes/${a.id}`), 'Ajuste removido.')}><DeleteOutlineIcon fontSize="small" /></IconButton>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </React.Fragment>
            ))}
          </TableBody>
        </Table>
      </Paper>

      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
        <Typography fontWeight={800}>Documentos</Typography>
        {banca && <Button size="small" startIcon={<UploadFileIcon />} onClick={() => enviarArquivo(`/financeiro/contratos/${c.id}/documentos`, { tipo: 'outro' }, 'Documento anexado.')}>Anexar</Button>}
      </Stack>
      {c.documentos.length === 0 ? <Typography variant="body2" color="text.secondary">Nenhum documento ainda.</Typography> : (
        <Stack divider={<Divider />}>
          {c.documentos.map((d: any) => (
            <Stack key={d.id} direction="row" spacing={1.5} alignItems="center" sx={{ py: 0.75 }}>
              <Chip size="small" label={d.tipo_rotulo} />
              <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }} noWrap>{d.nome}</Typography>
              <Typography variant="caption" color="text.secondary">{d.enviado_por} · {dataHoraBR(d.enviado_em)}</Typography>
              <IconButton size="small" onClick={() => baixar(`/financeiro/documentos/${d.id}/arquivo`, d.nome)}><DownloadIcon fontSize="small" /></IconButton>
            </Stack>
          ))}
        </Stack>
      )}

      <DialogoAceite aberto={aceite} titulo={`Aceitar o contrato ${c.numero}`} onFechar={() => setAceite(false)}
        texto={<Typography variant="body2">Leia o contrato e o termo de cessão de direitos e sigilo (botão "Contrato (PDF)") antes de aceitar.</Typography>}
        onConfirmar={async (senha) => { await api.post(`/financeiro/meu/contratos/${c.id}/aceitar`, { senha }); setAceite(false); setMsg('Contrato aceito.'); onAtualizar(); }} />
      <DialogoTexto aberto={recusa} titulo="Recusar o contrato" rotulo="Motivo (a banca vê)" botao="Recusar" cor="error"
        onFechar={() => setRecusa(false)} onConfirmar={async (m) => { await api.post(`/financeiro/meu/contratos/${c.id}/recusar`, { motivo: m }); setRecusa(false); onAtualizar(); }} />
      <DialogoTexto aberto={cancelar} titulo="Cancelar o contrato" rotulo="Motivo" botao="Cancelar contrato" cor="error"
        onFechar={() => setCancelar(false)} onConfirmar={async (m) => { await api.post(`/financeiro/contratos/${c.id}/cancelar`, { motivo: m }); setCancelar(false); onAtualizar(); }} />
      <DialogoTexto aberto={!!liberar} titulo={`Liberar a parcela ${liberar?.ordem || ''}`} rotulo="Justificativa (fica registrada)" minimo={3} botao="Liberar"
        valor={liberar ? { rotulo: 'Valor a liberar (R$)', inicial: liberar.valor_base,
          ajuda: `Calculado: ${moeda(liberar.valor_base)}. Pode liberar outro valor combinado; a justificativa fica registrada.` } : undefined}
        onFechar={() => setLiberar(null)}
        onConfirmar={async (j, v) => { await api.post(`/financeiro/parcelas/${liberar.id}/liberar`, { justificativa: j, valor: v }); setLiberar(null); onAtualizar(); }} />

      <Dialog open={!!ajuste} onClose={() => setAjuste(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Ajuste na parcela</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField select label="Tipo" value={ajuste?.tipo || 'desconto'} onChange={(e) => setAjuste({ ...ajuste, tipo: e.target.value })}>
              {Object.entries(AJUSTES).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
            <TextField label="Valor (R$)" type="number" value={ajuste?.valor || ''} onChange={(e) => setAjuste({ ...ajuste, valor: e.target.value })} />
            <TextField label="Motivo (o professor vê)" multiline minRows={2} value={ajuste?.motivo || ''} onChange={(e) => setAjuste({ ...ajuste, motivo: e.target.value })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAjuste(null)}>Cancelar</Button>
          <Button variant="contained" disabled={!Number(ajuste?.valor) || (ajuste?.motivo || '').trim().length < 3}
            onClick={() => { const a = ajuste; setAjuste(null); acao(() => api.post(`/financeiro/contratos/${c.id}/ajustes`, { ...a, valor: Number(a.valor) }), 'Ajuste lançado.'); }}>Lançar</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={!!pagar} onClose={() => setPagar(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Registrar pagamento da parcela {pagar?.ordem}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label={pf ? 'Valor bruto (R$)' : 'Valor pago (R$)'} type="number" value={pagar?.valor ?? ''} onChange={(e) => setPagar({ ...pagar, valor: e.target.value })} />
            {pf && <TextField label="Dependentes (IRRF)" type="number" value={pagar?.dependentes ?? 0} onChange={(e) => setPagar({ ...pagar, dependentes: e.target.value })} />}
            {pf && previa && (
              <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                <Typography variant="caption" color="text.secondary" fontWeight={700}>RETENÇÕES (RPA)</Typography>
                {[['INSS', previa.inss], ['IRRF', previa.irrf], ['ISS', previa.iss]].map(([r, v]: any) => (
                  <Stack key={r} direction="row" justifyContent="space-between"><Typography variant="body2">{r}</Typography><Typography variant="body2">− {moeda(v)}</Typography></Stack>
                ))}
                <Divider sx={{ my: 0.75 }} />
                <Stack direction="row" justifyContent="space-between"><Typography fontWeight={800}>Líquido ao professor</Typography><Typography fontWeight={800}>{moeda(previa.liquido)}</Typography></Stack>
              </Paper>
            )}
            <TextField label="Data do pagamento" type="date" InputLabelProps={{ shrink: true }} value={pagar?.data || ''} onChange={(e) => setPagar({ ...pagar, data: e.target.value })} />
            <TextField label="Forma (PIX, TED...)" value={pagar?.forma || ''} onChange={(e) => setPagar({ ...pagar, forma: e.target.value })} />
            <Button component="label" variant="outlined" startIcon={<UploadFileIcon />}>
              {pagar?.arquivo ? pagar.arquivo.name : 'Comprovante (opcional)'}
              <input hidden type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setPagar({ ...pagar, arquivo: e.target.files?.[0] || null })} />
            </Button>
            <Typography variant="caption" color="text.secondary">{pf ? 'O RPA e o recibo são gerados na hora' : 'O recibo é gerado na hora'} e ficam com o professor, que confirma o recebimento.</Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPagar(null)}>Cancelar</Button>
          <Button variant="contained" disabled={!Number(pagar?.valor) || !pagar?.data} onClick={() => {
            const p = pagar; setPagar(null);
            const fd = new FormData();
            fd.append('valor_pago', String(Number(p.valor))); fd.append('data_pagamento', p.data); fd.append('forma', p.forma || '');
            fd.append('dependentes', String(Number(p.dependentes) || 0));
            if (p.arquivo) fd.append('comprovante', p.arquivo);
            acao(() => api.post(`/financeiro/parcelas/${p.id}/pagar`, fd), 'Pagamento registrado e recibo gerado.');
          }}>Registrar</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ContratoDetalhe;
