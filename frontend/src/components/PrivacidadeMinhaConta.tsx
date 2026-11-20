import React, { useEffect, useState } from 'react';
import { Alert, Box, Button, Link, Paper, Typography } from '@mui/material';
import api from '../api';

// Minha conta: baixar os próprios dados (LGPD) e ver o aceite dos termos
const PrivacidadeMinhaConta: React.FC<{ sx?: object }> = ({ sx }) => {
  const [status, setStatus] = useState<any>(null);
  const [baixando, setBaixando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => { api.get('/lgpd/status').then(({ data }) => setStatus(data)).catch(() => {}); }, []);

  const baixar = async () => {
    setBaixando(true);
    setErro(null);
    try {
      const { data } = await api.get('/lgpd/meus-dados', { responseType: 'blob' });
      const url = URL.createObjectURL(data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'meus-dados-diagpro.json';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setErro('Não foi possível gerar o arquivo agora. Tente de novo em alguns minutos.');
    } finally {
      setBaixando(false);
    }
  };

  return (
    <Paper variant="outlined" sx={sx}>
      <Typography variant="subtitle1" fontWeight={700}>Privacidade e seus dados (LGPD)</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Baixe uma cópia dos seus dados pessoais guardados no DiagPro (perfil, acessos, avisos e uso da IA). Senhas e
        segredos de acesso nunca entram no arquivo. Para corrigir ou eliminar dados, fale com o administrador da sua banca.
      </Typography>
      {erro && <Alert severity="error" sx={{ mb: 1.5 }}>{erro}</Alert>}
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button variant="outlined" onClick={baixar} disabled={baixando}>{baixando ? 'Gerando...' : 'Baixar meus dados'}</Button>
        <Link href="/privacidade" target="_blank" rel="noopener">Política de privacidade</Link>
        <Link href="/termos" target="_blank" rel="noopener">Termos de uso</Link>
      </Box>
      {status?.aceite && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
          Você aceitou a versão {status.aceite.versao} dos termos em {new Date(status.aceite.em).toLocaleString('pt-BR')}.
        </Typography>
      )}
    </Paper>
  );
};

export default PrivacidadeMinhaConta;
