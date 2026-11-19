import React from 'react';
import { Alert, Box, Button, Paper, Snackbar, Typography } from '@mui/material';

// Mensagem de erro da API de configurações: {mensagem, problemas[]} ou texto
export function mensagemErro(e: any, padrao = 'Não foi possível salvar.'): string {
  const det = e?.response?.data?.detail;
  if (det && typeof det === 'object') return [det.mensagem, ...(det.problemas || [])].filter(Boolean).join(' • ');
  return typeof det === 'string' ? det : padrao;
}

export const Secao: React.FC<{ titulo: string; descricao?: string; children: React.ReactNode }> = ({ titulo, descricao, children }) => (
  <Paper variant="outlined" sx={{ p: 2.5, mb: 2.5, borderRadius: 2 }}>
    <Typography variant="subtitle1" fontWeight={700}>{titulo}</Typography>
    {descricao && <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{descricao}</Typography>}
    {children}
  </Paper>
);

export const BarraSalvar: React.FC<{ salvando: boolean; onSalvar: () => void; alterado: boolean }> = ({ salvando, onSalvar, alterado }) => (
  <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, alignItems: 'center' }}>
    {alterado && <Typography variant="body2" color="warning.main">Alterações não salvas</Typography>}
    <Button variant="contained" onClick={onSalvar} disabled={salvando || !alterado}>
      {salvando ? 'Salvando...' : 'Salvar'}
    </Button>
  </Box>
);

export const Aviso: React.FC<{ msg: { texto: string; tipo: 'success' | 'error' } | null; onFechar: () => void }> = ({ msg, onFechar }) => (
  <Snackbar open={!!msg} autoHideDuration={5000} onClose={onFechar}>
    <Alert severity={msg?.tipo || 'success'} onClose={onFechar}>{msg?.texto}</Alert>
  </Snackbar>
);
