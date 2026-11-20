import React from 'react';
import { Alert, Box, Typography } from '@mui/material';
import { CLIENTE_EM_GESTAO_KEY } from '../../api';
import { useAuth } from '../../contexts/AuthContext';
import BibliotecaTemplates from '../../components/templates/BibliotecaTemplates';

// Configurações > Templates de prova: biblioteca de papel timbrado da banca (usada por todos os eventos).
export default function BancaTemplatesTab() {
  const { user } = useAuth();
  const adminGeral = user?.role === 'administrador geral';
  let cliente: string | null = null;
  try { cliente = localStorage.getItem(CLIENTE_EM_GESTAO_KEY); } catch { cliente = null; }

  return (
    <Box>
      <Typography variant="h6" fontWeight={700}>Templates de prova</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5, maxWidth: 760 }}>
        Biblioteca de papel timbrado da banca (cabeçalho, rodapé e margens), usada por todos os concursos. Em cada evento,
        escolha qual é o padrão; na exportação ele já vem selecionado e pode ser trocado.
      </Typography>
      {adminGeral && !cliente ? (
        <Alert severity="info">Escolha um cliente no seletor do topo da tela para ver e gerenciar os templates dele.</Alert>
      ) : (
        <BibliotecaTemplates key={cliente || 'banca'} baseUrl="/api/banca/templates" gerenciar />
      )}
    </Box>
  );
}
