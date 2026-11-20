import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Paper, Tab, Table, TableBody, TableCell, TableHead, TableRow, Tabs,
  Tooltip, Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import api from '../api';
import { COR_STATUS_REVISAO } from '../components/statusRevisao';

type Item = {
  id_questao: string; codigo: string; tipo: string; status: string; evento_id: string; evento: string | null;
  conteudo_id: string; conteudo: string | null; autor: string | null; enviada_em: string | null;
  mensagem_envio: string | null; alterada_em: string | null;
};
type Resumo = Record<string, { rotulo: string; quantidade: number }>;

const ABAS = ['ENVIADA', 'AJUSTES', 'REPROVADA', 'APROVADA', 'RASCUNHO'];
const TIPOS: Record<string, string> = { MULTIPLA_ESCOLHA: 'Múltipla escolha', CERTO_ERRADO: 'Certo/Errado', DISCURSIVA: 'Discursiva', SUBJETIVA: 'Subjetiva' };
const dataHora = (iso: string | null) => (iso ? new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '—');

// Fila de revisão da banca: o que está aguardando revisão (e os demais estados), com atalho para revisar.
const FilaRevisaoPage: React.FC = () => {
  const navigate = useNavigate();
  const [aba, setAba] = useState('ENVIADA');
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [itens, setItens] = useState<Item[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async (status: string) => {
    setItens(null);
    setErro(null);
    try {
      const [r1, r2] = await Promise.all([api.get('/revisao/resumo'), api.get('/revisao/fila', { params: { status } })]);
      setResumo(r1.data);
      setItens(r2.data.itens);
    } catch (e: any) {
      setErro(typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : 'Não foi possível carregar a fila.');
      setItens([]);
    }
  }, []);
  useEffect(() => { carregar(aba); }, [aba, carregar]);

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Typography variant="h5" fontWeight="bold">Fila de revisão</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Questões enviadas pelos professores. Ao revisar, escolha Aprovada, Solicitar ajustes ou Reprovada:
          quem elaborou recebe o aviso na hora.
        </Typography>
        <Tabs value={aba} onChange={(_, v) => setAba(v)} variant="scrollable" sx={{ mb: 2 }}>
          {ABAS.map(s => (
            <Tab key={s} value={s} label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {resumo?.[s]?.rotulo || s}
                <Chip size="small" label={resumo?.[s]?.quantidade ?? '…'} color={COR_STATUS_REVISAO[s] || 'default'} />
              </Box>} />
          ))}
        </Tabs>
        {erro && <Alert severity="warning" sx={{ mb: 2 }}>{erro}</Alert>}
        {!itens ? <CircularProgress /> : !itens.length ? (
          <Typography color="text.secondary">Nenhuma questão neste estado.</Typography>
        ) : (
          <Box sx={{ overflowX: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Questão</TableCell><TableCell>Tipo</TableCell><TableCell>Evento</TableCell>
                  <TableCell>Conteúdo</TableCell><TableCell>Autor</TableCell>
                  <TableCell>{aba === 'ENVIADA' ? 'Enviada em' : 'Alterada em'}</TableCell><TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {itens.map(i => (
                  <TableRow key={i.id_questao} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={700}>{i.codigo || '—'}</Typography>
                      {i.mensagem_envio && aba === 'ENVIADA' && (
                        <Tooltip title={i.mensagem_envio}><Typography variant="caption" color="text.secondary" noWrap sx={{ display: 'block', maxWidth: 220 }}>Recado: {i.mensagem_envio}</Typography></Tooltip>
                      )}
                    </TableCell>
                    <TableCell>{TIPOS[i.tipo] || i.tipo}</TableCell>
                    <TableCell>{i.evento || '—'}</TableCell>
                    <TableCell>{i.conteudo || '—'}</TableCell>
                    <TableCell>{i.autor || '—'}</TableCell>
                    <TableCell>{dataHora(aba === 'ENVIADA' ? i.enviada_em : i.alterada_em)}</TableCell>
                    <TableCell align="right">
                      <Button size="small" variant={aba === 'ENVIADA' ? 'contained' : 'outlined'} color="secondary"
                        onClick={() => navigate(`/eventos/${i.evento_id}/conteudo/${i.conteudo_id}/questao/${i.id_questao}/revisar`)}>
                        {aba === 'ENVIADA' ? 'Revisar' : 'Abrir'}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}
      </Paper>
    </Layout>
  );
};

export default FilaRevisaoPage;
