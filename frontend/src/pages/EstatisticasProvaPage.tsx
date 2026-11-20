import React, { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, MenuItem, Paper, Table, TableBody, TableCell, TableHead, TableRow, TextField, Tooltip, Typography,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import { useParams } from 'react-router-dom';
import Layout from '../components/Layout';
import api from '../api';

type Item = { codigo: string; acerto: number; brancos: number; discriminacao: number; indice_d: number; dificuldade: string; alertas: string[] };
type Resultado = {
  candidatos: number; linhas_ignoradas: number; problemas: string[]; questoes: number; anuladas: string[]; media: number;
  desvio: number; minimo: number; maximo: number; kr20: number | null; itens: Item[]; cargo?: string; analisada_em?: string;
};

const corDisc = (d: number) => (d < 0 ? 'error' : d < 0.15 ? 'warning' : d < 0.3 ? 'info' : 'success');

// Estatísticas pós-prova: a banca envia as respostas (CSV) e vê a qualidade de cada questão
const EstatisticasProvaPage: React.FC = () => {
  const { eventId } = useParams();
  const [cargos, setCargos] = useState<{ id_cargo: string; nome_cargo: string; codigo_cargo?: string }[]>([]);
  const [cargo, setCargo] = useState('');
  const [senha, setSenha] = useState('');
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [res, setRes] = useState<Resultado | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.get(`/eventos/${eventId}/cargos/provas-geracao`).then(({ data }) => setCargos(data)).catch(() => setCargos([]));
  }, [eventId]);
  useEffect(() => {
    setRes(null);
    if (cargo) api.get(`/estatisticas/eventos/${eventId}/cargos/${cargo}`).then(({ data }) => setRes(data)).catch(() => {});
  }, [cargo, eventId]);

  const analisar = async () => {
    if (!arquivo) return;
    setCarregando(true);
    setErro(null);
    try {
      const fd = new FormData();
      fd.append('arquivo', arquivo);
      const { data } = await api.post(`/estatisticas/eventos/${eventId}/cargos/${cargo}/analisar`, fd, { headers: { 'X-Senha-Evento': senha } });
      setRes(data);
    } catch (e: any) {
      const det = e?.response?.data?.detail;
      setErro(typeof det === 'string' ? det : 'Não foi possível analisar o arquivo.');
    } finally {
      setCarregando(false);
    }
  };

  const baixarModelo = () => {
    const blob = new Blob(['tipo_prova;respostas\nPADRÃO;ABCDE.ABCDE\n'], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'modelo_respostas.csv';
    a.click();
  };

  const problemas = res?.itens.filter(i => i.alertas.length).length || 0;

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Typography variant="h5" fontWeight="bold">Estatísticas pós-prova</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Envie as respostas dos candidatos para ver o acerto e a discriminação de cada questão e encontrar questões com
          gabarito suspeito antes do resultado final. O arquivo é lido só em memória: inscrições e nomes são ignorados e
          nada sobre candidatos fica guardado, apenas os números por questão.
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center', mb: 2 }}>
          <TextField select size="small" label="Cargo" value={cargo} onChange={e => setCargo(e.target.value)} sx={{ minWidth: 280 }}>
            {cargos.map(c => <MenuItem key={c.id_cargo} value={c.id_cargo}>{c.codigo_cargo ? `${c.codigo_cargo} - ` : ''}{c.nome_cargo}</MenuItem>)}
          </TextField>
          <TextField size="small" type="password" label="Senha do evento" value={senha} onChange={e => setSenha(e.target.value)} autoComplete="off" />
          <Button component="label" variant="outlined" startIcon={<UploadFileIcon />}>
            {arquivo ? arquivo.name : 'Escolher CSV'}
            <input hidden type="file" accept=".csv,text/csv" onChange={e => setArquivo(e.target.files?.[0] || null)} />
          </Button>
          <Button variant="contained" disabled={!cargo || !senha || !arquivo || carregando} onClick={analisar}>
            {carregando ? 'Analisando...' : 'Analisar'}
          </Button>
          <Button size="small" onClick={baixarModelo}>Baixar modelo do CSV</Button>
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
          Formato: colunas <b>tipo_prova</b> (PADRÃO, Tipo 1, Tipo 2…) e <b>respostas</b> (uma letra por questão na ordem do
          caderno; ponto = em branco, # = mais de uma marcada). Separador ; ou ,.
        </Typography>
        {erro && <Alert severity="error" sx={{ mb: 2 }}>{erro}</Alert>}
        {carregando && <CircularProgress />}

        {res && (
          <>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(6, 1fr)' }, gap: 1.5, mb: 2 }}>
              {[['Candidatos', res.candidatos], ['Questões', res.questoes], ['Média', res.media], ['Desvio', res.desvio],
                ['Mín / máx', `${res.minimo} / ${res.maximo}`], ['Fidedignidade (KR-20)', res.kr20 ?? '—']].map(([r, v]) => (
                <Paper key={String(r)} variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                  <Typography variant="caption" color="text.secondary">{r}</Typography>
                  <Typography variant="h6" fontWeight={800}>{String(v)}</Typography>
                </Paper>
              ))}
            </Box>
            {res.analisada_em && <Typography variant="caption" color="text.secondary">Última análise: {new Date(res.analisada_em).toLocaleString('pt-BR')}</Typography>}
            {problemas > 0
              ? <Alert severity="warning" sx={{ my: 1.5 }}>{problemas} questão(ões) pedem atenção: elas aparecem primeiro na tabela.</Alert>
              : <Alert severity="success" sx={{ my: 1.5 }}>Nenhuma questão com sinal de problema.</Alert>}
            {res.linhas_ignoradas > 0 && <Alert severity="info" sx={{ mb: 1.5 }}>{res.linhas_ignoradas} linha(s) ignorada(s): {res.problemas.slice(0, 3).join(' | ')}</Alert>}
            {res.anuladas.length > 0 && <Typography variant="body2" sx={{ mb: 1 }}>Anuladas (fora da análise): {res.anuladas.join(', ')}</Typography>}
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Questão</TableCell><TableCell>Acerto</TableCell><TableCell>Em branco</TableCell>
                    <TableCell><Tooltip title="Correlação entre acertar a questão e ir bem no resto da prova. Negativa = forte sinal de gabarito errado."><span>Discriminação</span></Tooltip></TableCell>
                    <TableCell>Índice D</TableCell><TableCell>Dificuldade</TableCell><TableCell>Alertas</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {res.itens.map(i => (
                    <TableRow key={i.codigo} sx={{ bgcolor: i.discriminacao < 0 ? 'rgba(239,68,68,0.08)' : undefined }}>
                      <TableCell sx={{ fontWeight: 700 }}>{i.codigo}</TableCell>
                      <TableCell>{i.acerto}%</TableCell>
                      <TableCell>{i.brancos}%</TableCell>
                      <TableCell><Chip size="small" color={corDisc(i.discriminacao) as any} label={i.discriminacao.toFixed(2)} /></TableCell>
                      <TableCell>{i.indice_d.toFixed(2)}</TableCell>
                      <TableCell>{i.dificuldade}</TableCell>
                      <TableCell>{i.alertas.map((a, k) => <Typography key={k} variant="caption" sx={{ display: 'block' }}>{a}</Typography>)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </>
        )}
      </Paper>
    </Layout>
  );
};

export default EstatisticasProvaPage;
