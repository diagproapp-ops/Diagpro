import React, { useEffect, useState } from 'react';
import { Alert, Box, Button } from '@mui/material';
import api from '../api';

export const EVENTO_MANUTENCAO = 'diagpro:manutencao';

// Faixa fixa no topo quando a plataforma está em manutenção (vale também na tela de login).
const AvisoManutencao: React.FC = () => {
  const [mensagem, setMensagem] = useState<string | null>(null);

  useEffect(() => {
    api.get('/status/manutencao').then(({ data }) => setMensagem(data.ativa ? data.mensagem : null)).catch(() => {});
    const ouvir = (e: Event) => setMensagem((e as CustomEvent).detail || 'O DiagPro está em manutenção.');
    window.addEventListener(EVENTO_MANUTENCAO, ouvir);
    return () => window.removeEventListener(EVENTO_MANUTENCAO, ouvir);
  }, []);

  if (!mensagem) return null;
  return (
    <Box sx={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 2000 }}>
      <Alert severity="warning" variant="filled" sx={{ borderRadius: 0, justifyContent: 'center' }}
        action={<Button color="inherit" size="small" onClick={() => window.location.reload()}>Tentar de novo</Button>}>
        {mensagem}
      </Alert>
    </Box>
  );
};

export default AvisoManutencao;
