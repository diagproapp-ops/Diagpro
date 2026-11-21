import React, { useState } from 'react';
import {
  Alert, Dialog, DialogContent, DialogTitle, List, ListItemButton, ListItemIcon, ListItemText, Typography, CircularProgress,
} from '@mui/material';
import ApartmentOutlinedIcon from '@mui/icons-material/ApartmentOutlined';
import api from '../../api';
import { ROTULO_PAPEL, mensagemDaApi } from './comum';

export type BancaDaPessoa = { tenant_id: number; nome: string; role: string };

// Depois do 2FA: quem trabalha para mais de uma banca escolhe em qual entrar. Cada banca só vê o próprio trabalho.
const EscolherBancaDialog: React.FC<{
  token2fa: string;
  bancas: BancaDaPessoa[];
  onConcluido: (dados: any) => void;
  onCancelar: (mensagem?: string) => void;
}> = ({ token2fa, bancas, onConcluido, onCancelar }) => {
  const [entrando, setEntrando] = useState<number | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const escolher = async (tenantId: number) => {
    setEntrando(tenantId);
    setErro(null);
    try {
      const { data } = await api.post('/auth/2fa/escolher-banca', { token_2fa: token2fa, tenant_id: tenantId });
      onConcluido(data);
    } catch (e: any) {
      if (e?.response?.status === 401) { onCancelar('A verificação expirou. Entre novamente.'); return; }
      setErro(mensagemDaApi(e, 'Não foi possível entrar nessa banca.'));
      setEntrando(null);
    }
  };

  return (
    <Dialog open onClose={() => onCancelar()} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 800 }}>Em qual banca você vai trabalhar?</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Você atende mais de uma banca. Cada uma vê só o trabalho feito nela. Dá para trocar depois em Minha conta.
        </Typography>
        <List>
          {bancas.map(b => (
            <ListItemButton key={b.tenant_id} disabled={entrando !== null} onClick={() => escolher(b.tenant_id)}
              sx={{ border: 1, borderColor: 'divider', borderRadius: 2, mb: 1 }}>
              <ListItemIcon>{entrando === b.tenant_id ? <CircularProgress size={22} /> : <ApartmentOutlinedIcon />}</ListItemIcon>
              <ListItemText primary={b.nome} secondary={ROTULO_PAPEL[b.role] || b.role} primaryTypographyProps={{ fontWeight: 700 }} />
            </ListItemButton>
          ))}
        </List>
        {erro && <Alert severity="error">{erro}</Alert>}
      </DialogContent>
    </Dialog>
  );
};

export default EscolherBancaDialog;
