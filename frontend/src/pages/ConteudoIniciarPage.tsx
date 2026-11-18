import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Divider,
  Button,
  LinearProgress,
} from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import Layout from '../components/Layout';

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

const ConteudoIniciarPage: React.FC = () => {
  const { eventId, id_conteudo } = useParams();
  const navigate = useNavigate();
  const [conteudo, setConteudo] = useState<ConteudoType | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [textosReferencia, setTextosReferencia] = useState<TextoReferenciaType[]>([]);

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
    async function fetchTextosReferencia() {
      try {
        const res = await api.get(`/eventos/${eventId}/conteudos/${id_conteudo}/textos-referencia`);
        setTextosReferencia(res.data);
      } catch {
        setTextosReferencia([]);
      }
    }
    if (conteudo) fetchTextosReferencia();
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
        <Paper variant="outlined" sx={{ p: 2, mb: 2, bgcolor: "#fafafa" }}>
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
        <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
          <Button variant="contained" color="primary">
            Criar Questão
          </Button>
          <Button
            variant="outlined"
            color="secondary"
            onClick={() => navigate(`/eventos/${eventId}/conteudo/${id_conteudo}/referencia/adicionar`)}
          >
            Adicionar Texto de Referência
          </Button>
        </Box>
        <Divider sx={{ mt: 4, mb: 2 }} />
        <Typography variant="subtitle1" fontWeight="bold">
          Textos de Referência deste Conteúdo:
        </Typography>
        {textosReferencia.length === 0 ? (
          <Typography variant="body2" color="text.secondary">Nenhum texto de referência cadastrado.</Typography>
        ) : (
          textosReferencia.map(ref => (
            <Paper key={ref.id_texto_ref} sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle2" fontWeight="bold">{ref.titulo}</Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-line' }}>{ref.conteudo}</Typography>
            </Paper>
          ))
        )}
      </Paper>
    </Layout>
  );
};

export default ConteudoIniciarPage;