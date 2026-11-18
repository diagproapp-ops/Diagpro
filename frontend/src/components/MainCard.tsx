import React from 'react';
import { Paper } from '@mui/material';

/**
 * MainCard igual ao dashboard: ocupa toda a largura do conteúdo principal,
 * sombra, borda arredondada e padding.
 */
const MainCard: React.FC<{ children: React.ReactNode; sx?: any }> = ({ children, sx }) => (
  <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3, ...sx }}>
    {children}
  </Paper>
);

export default MainCard;