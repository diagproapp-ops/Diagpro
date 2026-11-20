import React, { useEffect, useState } from 'react';
import { Box, Button, CircularProgress, Paper, Typography } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import api from '../api';

// Página pública: política de privacidade ou termos de uso vigentes (texto da plataforma).
const DocumentoLegalPage: React.FC<{ tipo: 'politica' | 'termos' }> = ({ tipo }) => {
  const navigate = useNavigate();
  const [docs, setDocs] = useState<any>(null);
  useEffect(() => { api.get('/lgpd/documentos').then(({ data }) => setDocs(data)).catch(() => setDocs({})); }, []);
  const titulo = tipo === 'politica' ? 'Política de privacidade' : 'Termos de uso';
  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', display: 'flex', justifyContent: 'center', p: { xs: 2, md: 6 } }}>
      <Paper sx={{ p: { xs: 3, md: 5 }, maxWidth: 820, width: '100%', borderRadius: 3 }}>
        <Typography variant="h4" fontWeight={800} gutterBottom>{titulo}</Typography>
        {!docs ? <CircularProgress /> : (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>Versão {docs.versao || '—'}</Typography>
            <Typography sx={{ whiteSpace: 'pre-line', lineHeight: 1.8 }}>{docs[tipo] || 'Documento indisponível no momento.'}</Typography>
            {tipo === 'politica' && docs.encarregado && (
              <Typography sx={{ mt: 3 }}><b>Encarregado pelo tratamento de dados:</b> {docs.encarregado}</Typography>
            )}
          </>
        )}
        <Button sx={{ mt: 4 }} variant="outlined" onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/'))}>Voltar</Button>
      </Paper>
    </Box>
  );
};

export default DocumentoLegalPage;
