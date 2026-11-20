import React, { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Typography,
} from '@mui/material';
import api from '../api';

type Docs = { versao: string; termos: string; politica: string; encarregado: string };

// Pede o aceite dos termos e da política sempre que a versão muda (bloqueia até aceitar).
const AceiteTermos: React.FC = () => {
  const [docs, setDocs] = useState<Docs | null>(null);
  const [pendente, setPendente] = useState(false);
  const [li, setLi] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.get('/lgpd/status').then(({ data }) => {
      if (!data.aceita) {
        setPendente(true);
        api.get('/lgpd/documentos').then(r => setDocs(r.data)).catch(() => {});
      }
    }).catch(() => {});
  }, []);

  if (!pendente || !docs) return null;

  const aceitar = async () => {
    try {
      await api.post('/lgpd/aceitar', { versao: docs.versao });
      setPendente(false);
    } catch (e: any) {
      setErro(typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : 'Não foi possível registrar o aceite.');
      api.get('/lgpd/documentos').then(r => setDocs(r.data)).catch(() => {});
    }
  };

  return (
    <Dialog open maxWidth="md" fullWidth disableEscapeKeyDown>
      <DialogTitle>Termos de uso e política de privacidade (versão {docs.versao})</DialogTitle>
      <DialogContent dividers>
        <Typography variant="subtitle2" fontWeight={700}>Termos de uso</Typography>
        <Typography variant="body2" sx={{ whiteSpace: 'pre-line', mb: 2 }}>{docs.termos}</Typography>
        <Typography variant="subtitle2" fontWeight={700}>Política de privacidade</Typography>
        <Typography variant="body2" sx={{ whiteSpace: 'pre-line' }}>{docs.politica}</Typography>
        {docs.encarregado && <Typography variant="body2" sx={{ mt: 1 }}><b>Encarregado de dados:</b> {docs.encarregado}</Typography>}
        {erro && <Alert severity="error" sx={{ mt: 2 }}>{erro}</Alert>}
        <Box sx={{ mt: 2 }}>
          <FormControlLabel control={<Checkbox checked={li} onChange={e => setLi(e.target.checked)} />}
            label="Li e aceito os termos de uso e a política de privacidade" />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button variant="contained" disabled={!li} onClick={aceitar}>Aceitar e continuar</Button>
      </DialogActions>
    </Dialog>
  );
};

export default AceiteTermos;
