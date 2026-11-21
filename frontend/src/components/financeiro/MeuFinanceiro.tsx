import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Paper, Stack, Typography } from '@mui/material';
import api from '../../api';
import ContratoDetalhe from './ContratoDetalhe';
import { Indicador, erroApi, moeda } from './comum';

// Extrato do professor: contratos da banca em que está, o que já recebeu, o que está liberado e o que falta para cada parcela.
const MeuFinanceiro: React.FC = () => {
  const [d, setD] = useState<any>(null);
  const [erro, setErro] = useState<string | null>(null);
  const carregar = useCallback(() => {
    api.get('/financeiro/meu').then(({ data }) => setD(data)).catch((e) => setErro(erroApi(e, 'Não foi possível carregar.')));
  }, []);
  useEffect(() => { carregar(); }, [carregar]);
  if (!d) return erro ? <Alert severity="error">{erro}</Alert> : <Typography>Carregando...</Typography>;
  return (
    <Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, minmax(0,1fr))', md: 'repeat(4, minmax(0,1fr))' }, gap: 1.5, mb: 2.5 }}>
        <Indicador rotulo="Previsto nos contratos" valor={moeda(d.totais.previsto)} />
        <Indicador rotulo="Apurado" valor={moeda(d.totais.apurado)} />
        <Indicador rotulo="Liberado para receber" valor={moeda(d.totais.a_receber)} cor="#f59e0b" />
        <Indicador rotulo="Já recebido" valor={moeda(d.totais.pago)} cor="#10b981" />
      </Box>
      {d.pendentes_aceite > 0 && <Alert severity="warning" sx={{ mb: 2 }}>Você tem {d.pendentes_aceite} contrato(s) para ler e aceitar.</Alert>}
      {d.contratos.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
          <Typography color="text.secondary">Nenhum contrato ainda. Quando a banca enviar o seu contrato, ele aparece aqui para você aceitar.</Typography>
        </Paper>
      ) : (
        <Stack spacing={2.5}>
          {d.contratos.map((c: any) => (
            <Paper key={c.id} variant="outlined" sx={{ p: 2.5, borderRadius: 3 }}>
              <ContratoDetalhe c={c} modo="professor" onAtualizar={carregar} />
            </Paper>
          ))}
        </Stack>
      )}
    </Box>
  );
};

export default MeuFinanceiro;
