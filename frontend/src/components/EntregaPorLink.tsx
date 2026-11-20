import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Paper, Table,
  TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import SendOutlinedIcon from '@mui/icons-material/SendOutlined';
import api from '../api';

type Entrega = {
  id: string; situacao: string; nome_arquivo: string; destinatario: string; criado_em: string; expira_em: string;
  downloads: number; max_downloads: number; criado_por?: string; log: { em: string; ip: string }[];
};
const SITUACAO: Record<string, { rotulo: string; cor: 'success' | 'default' | 'warning' | 'error' }> = {
  ativa: { rotulo: 'Ativa', cor: 'success' }, vencida: { rotulo: 'Vencida', cor: 'default' }, esgotada: { rotulo: 'Downloads esgotados', cor: 'default' },
  revogada: { rotulo: 'Revogada', cor: 'warning' }, bloqueada: { rotulo: 'Bloqueada (códigos errados)', cor: 'error' },
};
const dataHora = (iso: string) => new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });

type Props = { eventId: string; habilitado: boolean; gabaritoMarcado: boolean; corpo: () => Record<string, any> };

// Exportação: gera o pacote e entrega por link com código (validade e limite de downloads), em vez de baixar
export default function EntregaPorLink({ eventId, habilitado, gabaritoMarcado, corpo }: Props) {
  const [aberto, setAberto] = useState(false);
  const [destinatario, setDestinatario] = useState('');
  const [horas, setHoras] = useState(24);
  const [maxDl, setMaxDl] = useState(1);
  const [gerando, setGerando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [criada, setCriada] = useState<{ link: string; codigo: string; expira_em: string } | null>(null);
  const [lista, setLista] = useState<Entrega[] | null>(null);
  const [copiado, setCopiado] = useState<string | null>(null);

  const carregar = useCallback(() => {
    api.get(`/api/export/eventos/${eventId}/entregas`).then(({ data }) => setLista(data)).catch(() => setLista([]));
  }, [eventId]);
  useEffect(() => { carregar(); }, [carregar]);

  const gerar = async () => {
    setGerando(true);
    setErro(null);
    try {
      const { data } = await api.post(`/api/export/eventos/${eventId}/cargos/gerar-arquivos-multiplos`,
        { ...corpo(), entrega: { destinatario: destinatario.trim(), horas, max_downloads: maxDl } });
      if (!data?.entrega) { setErro(data?.erro || 'Nada para gerar.'); return; }
      setCriada({ link: `${window.location.origin}/entrega/${data.entrega.id}`, codigo: data.codigo, expira_em: data.entrega.expira_em });
      carregar();
    } catch (e: any) {
      const det = e?.response?.data?.detail;
      setErro(typeof det === 'string' ? det : det?.mensagem || 'Não foi possível gerar a entrega.');
    } finally {
      setGerando(false);
    }
  };

  const revogar = async (id: string) => {
    if (!window.confirm('Revogar este link? Ele para de funcionar na hora e o arquivo é apagado.')) return;
    await api.post(`/api/export/entregas/${id}/revogar`).catch(() => {});
    carregar();
  };

  const copiar = (texto: string, qual: string) => { navigator.clipboard?.writeText(texto); setCopiado(qual); setTimeout(() => setCopiado(null), 2000); };
  const fechar = () => { setAberto(false); setCriada(null); setErro(null); };

  return (
    <Paper variant="outlined" sx={{ p: 2.5, mt: 3, borderRadius: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="subtitle1" fontWeight={700}>Entrega segura para a gráfica</Typography>
          <Typography variant="body2" color="text.secondary">
            Em vez de mandar o arquivo por e-mail ou mensagem: gera o pacote (protegido pela senha do evento) e um link
            com código de acesso, validade e limite de downloads. Cada download fica registrado e você é avisado.
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<SendOutlinedIcon />} disabled={!habilitado || gabaritoMarcado} onClick={() => setAberto(true)}>
          Entregar por link
        </Button>
      </Box>
      {gabaritoMarcado && <Alert severity="info" sx={{ mt: 1.5 }}>Pacote com gabarito marcado é de uso interno e não pode ser entregue por link.</Alert>}

      {lista === null ? <CircularProgress size={22} sx={{ mt: 2 }} /> : lista.length > 0 && (
        <Box sx={{ overflowX: 'auto', mt: 2 }}>
          <Table size="small">
            <TableHead><TableRow><TableCell>Para</TableCell><TableCell>Criada</TableCell><TableCell>Vence</TableCell><TableCell>Downloads</TableCell><TableCell>Situação</TableCell><TableCell /></TableRow></TableHead>
            <TableBody>
              {lista.map(e => (
                <TableRow key={e.id}>
                  <TableCell>{e.destinatario}<Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>{e.nome_arquivo}</Typography></TableCell>
                  <TableCell>{dataHora(e.criado_em)}{e.criado_por ? ` • ${e.criado_por}` : ''}</TableCell>
                  <TableCell>{dataHora(e.expira_em)}</TableCell>
                  <TableCell>
                    {e.downloads}/{e.max_downloads}
                    {e.log.map((l, i) => <Typography key={i} variant="caption" color="text.secondary" sx={{ display: 'block' }}>{dataHora(l.em)} • IP {l.ip}</Typography>)}
                  </TableCell>
                  <TableCell><Chip size="small" color={SITUACAO[e.situacao]?.cor || 'default'} label={SITUACAO[e.situacao]?.rotulo || e.situacao} /></TableCell>
                  <TableCell align="right">{e.situacao === 'ativa' && <Button size="small" color="warning" onClick={() => revogar(e.id)}>Revogar</Button>}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}

      <Dialog open={aberto} onClose={gerando ? undefined : fechar} maxWidth="sm" fullWidth>
        <DialogTitle>{criada ? 'Link de entrega criado' : 'Entregar por link'}</DialogTitle>
        <DialogContent dividers>
          {!criada ? (
            <>
              <TextField fullWidth label="Para quem (ex.: Gráfica XYZ)" value={destinatario} onChange={e => setDestinatario(e.target.value)} inputProps={{ maxLength: 120 }} sx={{ mb: 2 }} />
              <Box sx={{ display: 'flex', gap: 2 }}>
                <TextField select label="Vale por" value={horas} onChange={e => setHoras(Number(e.target.value))} sx={{ flex: 1 }}>
                  {[1, 6, 12, 24, 48, 72].map(h => <MenuItem key={h} value={h}>{h} hora{h > 1 ? 's' : ''}</MenuItem>)}
                </TextField>
                <TextField select label="Downloads permitidos" value={maxDl} onChange={e => setMaxDl(Number(e.target.value))} sx={{ flex: 1 }}>
                  {[1, 2, 3, 4, 5].map(n => <MenuItem key={n} value={n}>{n}</MenuItem>)}
                </TextField>
              </Box>
              <Alert severity="info" sx={{ mt: 2 }}>São usados os cargos e as opções de formatação escolhidos acima. O pacote continua protegido pela senha do evento.</Alert>
              {erro && <Alert severity="error" sx={{ mt: 2 }}>{erro}</Alert>}
            </>
          ) : (
            <>
              <Alert severity="warning" sx={{ mb: 2 }}>
                Anote o código agora: ele não aparece de novo. Mande o link e o código por canais diferentes (ex.: link por
                e-mail, código por telefone). A senha do evento, para abrir o ZIP, por um terceiro canal.
              </Alert>
              <Typography variant="caption" color="text.secondary">Link</Typography>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 2 }}>
                <TextField fullWidth size="small" value={criada.link} InputProps={{ readOnly: true }} />
                <Button onClick={() => copiar(criada.link, 'link')}>{copiado === 'link' ? 'Copiado' : 'Copiar'}</Button>
              </Box>
              <Typography variant="caption" color="text.secondary">Código de acesso</Typography>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <Typography sx={{ fontFamily: 'monospace', fontSize: 26, letterSpacing: 2, flex: 1 }}>{criada.codigo}</Typography>
                <Button onClick={() => copiar(criada.codigo, 'codigo')}>{copiado === 'codigo' ? 'Copiado' : 'Copiar'}</Button>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>Vale até {dataHora(criada.expira_em)}.</Typography>
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={fechar} disabled={gerando}>{criada ? 'Fechar' : 'Cancelar'}</Button>
          {!criada && (
            <Button variant="contained" onClick={gerar} disabled={gerando || !destinatario.trim()}>
              {gerando ? 'Gerando pacote...' : 'Gerar link'}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
