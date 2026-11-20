import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Chip, Paper, Stack, Typography } from '@mui/material';
import ComputerOutlinedIcon from '@mui/icons-material/ComputerOutlined';
import PhoneIphoneOutlinedIcon from '@mui/icons-material/PhoneIphoneOutlined';
import api from '../api';

type Acesso = { id: string; atual: boolean; navegador: string; sistema: string; ip: string; criada_em: string; ultimo_uso_em: string };

const dataHora = (iso: string) => new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });

// Minha conta: onde a pessoa está conectada, com saída remota
const SessoesAtivas: React.FC<{ sx?: object }> = ({ sx }) => {
  const [itens, setItens] = useState<Acesso[] | null>(null);
  const [msg, setMsg] = useState<{ texto: string; tipo: 'success' | 'error' } | null>(null);

  const carregar = useCallback(() => {
    api.get('/auth/sessoes').then(({ data }) => setItens(data.itens)).catch(() => setItens([]));
  }, []);
  useEffect(() => { carregar(); }, [carregar]);

  const encerrar = async (a: Acesso) => {
    try {
      await api.post(`/auth/sessoes/${a.id}/encerrar`);
      setMsg({ texto: `Acesso pelo ${a.navegador} (${a.sistema}) encerrado.`, tipo: 'success' });
      carregar();
    } catch {
      setMsg({ texto: 'Não foi possível encerrar esse acesso.', tipo: 'error' });
    }
  };

  const encerrarOutros = async () => {
    try {
      const { data } = await api.post('/auth/sessoes/encerrar-outras');
      setMsg({ texto: `${data.encerradas} outro(s) acesso(s) encerrado(s).`, tipo: 'success' });
      carregar();
    } catch {
      setMsg({ texto: 'Não foi possível encerrar os outros acessos.', tipo: 'error' });
    }
  };

  const outros = (itens || []).filter(a => !a.atual).length;

  return (
    <Paper variant="outlined" sx={sx}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="subtitle1" fontWeight={700}>Acessos ativos</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Onde sua conta está conectada agora. Se não reconhecer algum, encerre e troque sua senha.
          </Typography>
        </Box>
        {outros > 0 && <Button variant="outlined" color="warning" onClick={encerrarOutros}>Encerrar todos os outros</Button>}
      </Box>
      {msg && <Alert severity={msg.tipo} sx={{ mb: 1.5 }} onClose={() => setMsg(null)}>{msg.texto}</Alert>}
      <Stack spacing={1.25}>
        {(itens || []).map(a => (
          <Box key={a.id} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, p: 1.5, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
            {['Android', 'iOS'].includes(a.sistema) ? <PhoneIphoneOutlinedIcon color="action" /> : <ComputerOutlinedIcon color="action" />}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="body2" fontWeight={600}>
                {a.navegador} no {a.sistema} {a.atual && <Chip size="small" color="success" label="Este aparelho" sx={{ ml: 1 }} />}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                IP {a.ip || 'desconhecido'} • entrou em {dataHora(a.criada_em)} • último uso {dataHora(a.ultimo_uso_em)}
              </Typography>
            </Box>
            {!a.atual && <Button size="small" color="warning" onClick={() => encerrar(a)}>Encerrar</Button>}
          </Box>
        ))}
        {itens && !itens.length && <Typography variant="body2" color="text.secondary">Nenhum acesso registrado ainda.</Typography>}
      </Stack>
    </Paper>
  );
};

export default SessoesAtivas;
