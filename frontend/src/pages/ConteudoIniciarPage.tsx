import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Divider,
  Button,
  LinearProgress,
  Chip,
  Stack,
} from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import Layout from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';

interface ConteudoType {
  id_conteudo: string;
  identificador_conteudo?: string;
  nome_conteudo: string;
  descricao?: string;
  quantidade?: number;
  respondidas?: number;
}

interface TextoReferenciaType {
  id_texto_ref: string;
  titulo: string;
  conteudo: string;
}

interface QuestaoResumo {
  id_questao: string;
  codigo_curto_questao?: string;
  enunciado?: string;
  tipo?: string;
  status_revisao?: string;
}

// Mesmos perfis que o backend aceita na rota de revisão (PATCH .../revisao).
const PERFIS_REVISAO = ['revisor', 'administrador', 'administrador geral'];

// O enunciado vem em HTML do editor: aqui só um resumo em texto puro (nunca injetado como HTML).
// DOMParser cria um documento inerte: não executa scripts nem dispara onerror/onload de imagens.
function resumoTexto(html?: string, max = 140): string {
  const doc = new DOMParser().parseFromString(html || '', 'text/html');
  const texto = (doc.body.textContent || '').replace(/\s+/g, ' ').trim();
  return texto.length > max ? `${texto.slice(0, max)}…` : texto;
}

const ConteudoIniciarPage: React.FC = () => {
  const { eventId, id_conteudo } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const podeRevisar = PERFIS_REVISAO.includes(String(user?.role || ''));
  const [conteudo, setConteudo] = useState<ConteudoType | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [textosReferencia, setTextosReferencia] = useState<TextoReferenciaType[]>([]);
  const [questoes, setQuestoes] = useState<QuestaoResumo[]>([]);

  const base = `/eventos/${eventId}/conteudo/${id_conteudo}`;

  useEffect(() => {
    async function fetchConteudo() {
      setCarregando(true);
      try {
        const res = await api.get(`/conteudos/eventos/${eventId}/conteudos`);
        const encontrado = res.data.find((c: ConteudoType) => c.id_conteudo === id_conteudo);
        setConteudo(encontrado);
      } catch {
        setConteudo(null);
      }
      setCarregando(false);
    }
    fetchConteudo();
  }, [eventId, id_conteudo]);

  useEffect(() => {
    async function fetchTextosEQuestoes() {
      try {
        const res = await api.get(`/eventos/${eventId}/conteudos/${id_conteudo}/textos-referencia`);
        setTextosReferencia(res.data);
      } catch {
        setTextosReferencia([]);
      }
      try {
        const res = await api.get(`/eventos/${eventId}/conteudos/${id_conteudo}/questoes`);
        setQuestoes(Array.isArray(res.data) ? res.data : []);
      } catch {
        setQuestoes([]);
      }
    }
    if (conteudo) fetchTextosEQuestoes();
  }, [conteudo, eventId, id_conteudo]);

  if (carregando) return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', minHeight: 200 }}>
          <CircularProgress />
        </Box>
      </Paper>
    </Layout>
  );

  if (!conteudo) return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Typography variant="h5" color="error">Conteúdo não encontrado!</Typography>
      </Paper>
    </Layout>
  );

  const progresso = conteudo.quantidade
    ? ((conteudo.respondidas ?? 0) / conteudo.quantidade) * 100
    : 0;

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h5" fontWeight="bold" gutterBottom>
            Iniciar Trabalhos
          </Typography>
          <Button
            variant="outlined"
            color="primary"
            onClick={() => navigate(-1)}
          >
            Voltar
          </Button>
        </Box>
        <Divider sx={{ mb: 2 }} />
        <Typography variant="subtitle1" gutterBottom>
          <b>Identificador:</b> {conteudo.identificador_conteudo}
        </Typography>
        <Typography variant="subtitle1" gutterBottom>
          <b>Nome:</b> {conteudo.nome_conteudo}
        </Typography>
        <Typography variant="subtitle1" gutterBottom>
          <b>Descrição:</b>
        </Typography>
        <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: "rgba(6, 11, 25, 0.65)" }}>
          <Typography variant="body1" sx={{ whiteSpace: 'pre-line' }}>
            {conteudo.descricao || "Sem descrição cadastrada."}
          </Typography>
        </Paper>
        <Typography variant="subtitle1" gutterBottom>
          <b>Questões/Itens:</b> {conteudo.quantidade ?? 0}
        </Typography>
        <Box sx={{ minWidth: 200, mb: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            <b>Questões/Itens Criados:</b> {conteudo.respondidas ?? 0}/{conteudo.quantidade ?? 0}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={progresso}
            sx={{ height: 8, borderRadius: 2, my: 0.5 }}
          />
          <Typography variant="caption">
            {conteudo.quantidade ? progresso.toFixed(0) : '0'}%
          </Typography>
        </Box>
        <Box sx={{ mt: 3, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            color="primary"
            onClick={() => navigate(`${base}/questao/criar`)}
          >
            Criar Questão
          </Button>
          <Button
            variant="outlined"
            color="secondary"
            onClick={() => navigate(`${base}/referencia/adicionar`)}
          >
            Adicionar Texto de Referência
          </Button>
        </Box>

        <Divider sx={{ mt: 4, mb: 2 }} />
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
          Questões deste Conteúdo:
        </Typography>
        {questoes.length === 0 ? (
          <Typography variant="body2" color="text.secondary">Nenhuma questão cadastrada.</Typography>
        ) : (
          questoes.map(q => (
            <Paper key={q.id_questao} variant="outlined" sx={{ p: 2, mb: 1.5 }}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ sm: 'center' }}>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5, flexWrap: 'wrap' }}>
                    <Typography variant="subtitle2" fontWeight="bold">
                      {q.codigo_curto_questao || 'Questão'}
                    </Typography>
                    {q.tipo && <Chip size="small" label={q.tipo} />}
                    {q.status_revisao && <Chip size="small" color="info" variant="outlined" label={q.status_revisao} />}
                  </Stack>
                  <Typography variant="body2" color="text.secondary" sx={{ wordBreak: 'break-word' }}>
                    {resumoTexto(q.enunciado) || 'Sem enunciado.'}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1}>
                  <Button size="small" variant="outlined" onClick={() => navigate(`${base}/questao/${q.id_questao}/editar`)}>
                    Editar
                  </Button>
                  {podeRevisar && (
                    <Button size="small" variant="contained" color="secondary" onClick={() => navigate(`${base}/questao/${q.id_questao}/revisar`)}>
                      Revisar
                    </Button>
                  )}
                </Stack>
              </Stack>
            </Paper>
          ))
        )}

        <Divider sx={{ mt: 4, mb: 2 }} />
        <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
          Textos de Referência deste Conteúdo:
        </Typography>
        {textosReferencia.length === 0 ? (
          <Typography variant="body2" color="text.secondary">Nenhum texto de referência cadastrado.</Typography>
        ) : (
          textosReferencia.map(ref => (
            <Paper key={ref.id_texto_ref} sx={{ p: 2, mb: 2 }}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ sm: 'flex-start' }}>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography variant="subtitle2" fontWeight="bold">{ref.titulo}</Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-line', wordBreak: 'break-word' }}>
                    {resumoTexto(ref.conteudo, 400)}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={1}>
                  <Button size="small" variant="outlined" onClick={() => navigate(`${base}/referencia/${ref.id_texto_ref}/editar`)}>
                    Editar
                  </Button>
                  {podeRevisar && (
                    <Button size="small" variant="contained" color="secondary" onClick={() => navigate(`${base}/referencia/${ref.id_texto_ref}/revisar`)}>
                      Revisar
                    </Button>
                  )}
                </Stack>
              </Stack>
            </Paper>
          ))
        )}
      </Paper>
    </Layout>
  );
};

export default ConteudoIniciarPage;
