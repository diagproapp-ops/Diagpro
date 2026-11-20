import React from 'react';
import { Chip } from '@mui/material';

// Estados do fluxo de revisão (mesmos nomes do backend: fluxo_revisao.py)
export const ROTULO_STATUS_REVISAO: Record<string, string> = {
  RASCUNHO: 'Em elaboração',
  ENVIADA: 'Aguardando revisão',
  AJUSTES: 'Devolvida com ajustes',
  REPROVADA: 'Reprovada',
  APROVADA: 'Aprovada',
};
export const COR_STATUS_REVISAO: Record<string, 'default' | 'info' | 'warning' | 'error' | 'success'> = {
  RASCUNHO: 'default',
  ENVIADA: 'info',
  AJUSTES: 'warning',
  REPROVADA: 'error',
  APROVADA: 'success',
};
export const PODE_ENVIAR_REVISAO = ['', 'RASCUNHO', 'AJUSTES', 'REPROVADA'];

export const ChipStatusRevisao: React.FC<{ status?: string | null }> = ({ status }) => {
  const s = (status || 'RASCUNHO').toUpperCase();
  return <Chip size="small" color={COR_STATUS_REVISAO[s] || 'default'} variant={s === 'RASCUNHO' ? 'outlined' : 'filled'}
    label={ROTULO_STATUS_REVISAO[s] || s} />;
};
