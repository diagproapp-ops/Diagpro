import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Divider, Paper, Snackbar, Stack, Typography } from '@mui/material';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import { useNavigate, useParams } from 'react-router-dom';
import Layout from '../components/Layout';
import BibliotecaTemplates from '../components/templates/BibliotecaTemplates';
import api from '../api';

// Template do evento: os templates ficam na biblioteca da banca (Configurações); aqui só se escolhe o padrão
// deste concurso, que já vem selecionado na exportação (e pode ser trocado lá).
const TemplatesPage: React.FC = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const [padrao, setPadrao] = useState<string | null>(null);
  const [aviso, setAviso] = useState<{ texto: string; tipo: 'success' | 'error' } | null>(null);
  const urlPrefs = `/api/export/eventos/${eventId}/preferencias`;

  useEffect(() => {
    api.get(urlPrefs).then(({ data }) => setPadrao((data && data.template) || null)).catch(() => setPadrao(null));
  }, [urlPrefs]);

  const escolherPadrao = useCallback(async (nome: string | null) => {
    try {
      // as preferências de exportação são salvas inteiras: lê as atuais e troca só o template
      const { data } = await api.get(urlPrefs);
      await api.put(urlPrefs, { ...(data || {}), template: nome });
      setPadrao(nome);
      setAviso({ texto: nome ? `"${nome}" agora é o template padrão deste evento.` : 'Este evento ficou sem template padrão.', tipo: 'success' });
    } catch (err: any) {
      setAviso({ texto: err?.response?.data?.detail || 'Não foi possível salvar o template padrão.', tipo: 'error' });
    }
  }, [urlPrefs]);

  return (
    <Layout>
      <Paper sx={{ p: { xs: 2, md: 4 }, borderRadius: 5, boxShadow: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
          <Box>
            <Typography variant="h5" fontWeight="bold" color="primary.dark">Template da prova</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 760 }}>
              Escolha o papel timbrado padrão deste concurso. Ele já vem selecionado na exportação. Os templates ficam na
              biblioteca da banca, em Configurações.
            </Typography>
          </Box>
          <Stack direction="row" spacing={1.5}>
            <Button variant="contained" startIcon={<SettingsOutlinedIcon />} onClick={() => navigate('/settings?secao=banca_templates')}
              sx={{ borderRadius: 2, fontWeight: 'bold' }}>
              Gerenciar biblioteca
            </Button>
            <Button variant="outlined" color="secondary" onClick={() => navigate(-1)} sx={{ borderRadius: 2, fontWeight: 'bold' }}>Voltar</Button>
          </Stack>
        </Box>
        <Divider sx={{ mb: 3 }} />
        {!padrao && (
          <Alert severity="info" sx={{ mb: 2.5 }}>Este evento ainda não tem template padrão: escolha um abaixo com "Usar como padrão".</Alert>
        )}
        <BibliotecaTemplates
          baseUrl={`/api/eventos/${eventId}/templates`}
          padrao={padrao}
          onEscolherPadrao={escolherPadrao}
          vazio={(
            <Button sx={{ mt: 1 }} variant="contained" startIcon={<SettingsOutlinedIcon />} onClick={() => navigate('/settings?secao=banca_templates')}>
              Enviar templates na biblioteca da banca
            </Button>
          )}
        />
        <Snackbar open={!!aviso} autoHideDuration={4000} onClose={() => setAviso(null)}>
          <Alert severity={aviso?.tipo || 'success'} onClose={() => setAviso(null)}>{aviso?.texto}</Alert>
        </Snackbar>
      </Paper>
    </Layout>
  );
};

export default TemplatesPage;
