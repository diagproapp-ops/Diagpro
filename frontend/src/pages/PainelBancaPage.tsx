import React, { useEffect, useState } from 'react';
import { Alert, Box, Chip, CircularProgress, LinearProgress, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import api from '../api';
import { COR_STATUS_REVISAO, ROTULO_STATUS_REVISAO } from '../components/statusRevisao';

const TIPOS: Record<string, string> = { MULTIPLA_ESCOLHA: 'Múltipla escolha', CERTO_ERRADO: 'Certo/Errado', DISCURSIVA: 'Discursiva', SUBJETIVA: 'Subjetiva' };
const PAPEIS: Record<string, string> = { administrador: 'Administradores', professor: 'Professores', revisor: 'Revisores', diagramador: 'Diagramadores' };

const Cartao: React.FC<{ rotulo: string; valor: React.ReactNode; sub?: string; onClick?: () => void }> = ({ rotulo, valor, sub, onClick }) => (
  <Paper variant="outlined" onClick={onClick} sx={{ p: 2, borderRadius: 2, cursor: onClick ? 'pointer' : 'default', '&:hover': onClick ? { borderColor: 'primary.main' } : {} }}>
    <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em' }}>{rotulo}</Typography>
    <Typography variant="h4" fontWeight={800}>{valor}</Typography>
    {sub && <Typography variant="caption" color="text.secondary">{sub}</Typography>}
  </Paper>
);

// Painel da banca: visão rápida do andamento (só números; nenhum conteúdo de prova)
const PainelBancaPage: React.FC = () => {
  const navigate = useNavigate();
  const [p, setP] = useState<any>(null);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => {
    api.get('/painel/banca').then(({ data }) => setP(data))
      .catch(e => setErro(typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : 'Não foi possível carregar o painel.'));
  }, []);

  return (
    <Layout>
      <Typography variant="h4" fontWeight={800} sx={{ mb: 0.5 }}>Painel da banca</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>Andamento dos eventos, da elaboração e da revisão.</Typography>
      {erro && <Alert severity="warning">{erro}</Alert>}
      {!p && !erro && <CircularProgress />}
      {p && (
        <>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(6, 1fr)' }, gap: 2, mb: 3 }}>
            <Cartao rotulo="Eventos" valor={p.eventos} onClick={() => navigate('/dashboard')} />
            <Cartao rotulo="Cargos" valor={p.cargos} sub={`${p.provas_montadas} prova(s) montada(s)`} />
            <Cartao rotulo="Questões" valor={p.questoes.total} />
            <Cartao rotulo="Aguardando revisão" valor={p.fila_revisao} onClick={() => navigate('/revisao')} />
            <Cartao rotulo="Exportações (30 dias)" valor={p.exportacoes_30d} sub={`${p.entregas_ativas} entrega(s) por link ativa(s)`} />
            <Cartao rotulo="Uso da IA (30 dias)" valor={p.usos_ia_30d} />
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' }, gap: 2, mb: 3 }}>
            <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
              <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>Eventos: questões elaboradas x meta</Typography>
              {!p.por_evento.length ? <Typography color="text.secondary">Nenhum evento.</Typography> : (
                <Table size="small">
                  <TableHead><TableRow><TableCell>Evento</TableCell><TableCell>Prova</TableCell><TableCell>Conteúdos</TableCell><TableCell sx={{ width: '35%' }}>Elaboração</TableCell></TableRow></TableHead>
                  <TableBody>
                    {p.por_evento.map((e: any) => (
                      <TableRow key={e.id} hover sx={{ cursor: 'pointer' }} onClick={() => navigate(`/eventos/${e.id}/conteudo`)}>
                        <TableCell sx={{ fontWeight: 600 }}>{e.nome}</TableCell>
                        <TableCell>{e.data_prova ? new Date(e.data_prova + 'T12:00:00').toLocaleDateString('pt-BR') : '—'}</TableCell>
                        <TableCell>{e.conteudos}</TableCell>
                        <TableCell>
                          {e.progresso === null ? <Typography variant="caption" color="text.secondary">Sem meta</Typography> : (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <LinearProgress variant="determinate" value={Math.min(100, e.progresso)} sx={{ flex: 1, height: 8, borderRadius: 4 }}
                                color={e.progresso >= 100 ? 'success' : 'primary'} />
                              <Typography variant="caption">{e.questoes_feitas}/{e.questoes_meta}</Typography>
                            </Box>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Paper>
            <Box sx={{ display: 'grid', gap: 2, alignContent: 'start' }}>
              <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
                <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>Revisão</Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {Object.keys(ROTULO_STATUS_REVISAO).map(s => (
                    <Chip key={s} color={COR_STATUS_REVISAO[s]} variant={s === 'RASCUNHO' ? 'outlined' : 'filled'}
                      label={`${ROTULO_STATUS_REVISAO[s]}: ${p.questoes.por_estado[s] || 0}`} />
                  ))}
                </Box>
              </Paper>
              <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
                <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>Questões por tipo</Typography>
                {Object.entries(p.questoes.por_tipo).map(([t, n]) => (
                  <Typography key={t} variant="body2">{TIPOS[t] || t}: <b>{String(n)}</b></Typography>
                ))}
              </Paper>
              <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
                <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>Equipe ativa</Typography>
                {Object.entries(p.equipe).map(([r, n]) => (
                  <Typography key={r} variant="body2">{PAPEIS[r] || r}: <b>{String(n)}</b></Typography>
                ))}
              </Paper>
            </Box>
          </Box>
        </>
      )}
    </Layout>
  );
};

export default PainelBancaPage;
