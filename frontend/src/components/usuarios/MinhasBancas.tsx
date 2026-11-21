import React, { useEffect, useState } from 'react';
import { Alert, Button, Chip, Paper, Stack, Typography } from '@mui/material';
import api from '../../api';
import { useAuth } from '../../contexts/AuthContext';
import { BancaDaPessoa } from './EscolherBancaDialog';
import { ROTULO_PAPEL, mensagemDaApi } from './comum';

// Quem atende várias bancas troca de banca sem sair: o acesso atual é encerrado e abre um só da banca escolhida.
const MinhasBancas: React.FC<{ sx?: any }> = ({ sx }) => {
  const { concluirLogin } = useAuth();
  const [dados, setDados] = useState<{ atual: number | null; bancas: BancaDaPessoa[] } | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [trocando, setTrocando] = useState<number | null>(null);

  useEffect(() => {
    api.get('/auth/bancas').then(({ data }) => setDados(data)).catch(() => setDados(null));
  }, []);

  if (!dados || dados.bancas.length < 2) return null;

  const trocar = async (tenantId: number) => {
    setTrocando(tenantId);
    setErro(null);
    try {
      const { data } = await api.post('/auth/trocar-banca', { tenant_id: tenantId });
      await concluirLogin(data);
      window.location.assign('/dashboard'); // recomeça a tela já na outra banca (nada da anterior fica na memória)
    } catch (e: any) {
      setErro(mensagemDaApi(e, 'Não foi possível trocar de banca.'));
      setTrocando(null);
    }
  };

  return (
    <Paper variant="outlined" sx={sx}>
      <Typography variant="subtitle1" fontWeight={700}>Minhas bancas</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Você trabalha para mais de uma banca. Cada banca vê só o trabalho feito nela.
      </Typography>
      <Stack spacing={1.25}>
        {dados.bancas.map(b => (
          <Stack key={b.tenant_id} direction="row" spacing={1.5} alignItems="center">
            <Typography fontWeight={700} sx={{ minWidth: 220 }}>{b.nome}</Typography>
            <Chip size="small" label={ROTULO_PAPEL[b.role] || b.role} />
            {b.tenant_id === dados.atual ? (
              <Chip size="small" color="success" variant="outlined" label="Você está nesta banca" />
            ) : (
              <Button size="small" variant="outlined" disabled={trocando !== null} onClick={() => trocar(b.tenant_id)}>
                {trocando === b.tenant_id ? 'Entrando...' : 'Entrar nesta banca'}
              </Button>
            )}
          </Stack>
        ))}
      </Stack>
      {erro && <Alert severity="error" sx={{ mt: 2 }}>{erro}</Alert>}
    </Paper>
  );
};

export default MinhasBancas;
