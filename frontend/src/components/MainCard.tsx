import React from 'react';
import { Paper } from '@mui/material';

const MainCard: React.FC<{ children: React.ReactNode; sx?: any }> = ({ children, sx }) => (
  <Paper
    sx={{
      p: 3.5,
      borderRadius: 3.5,
      border: '1px solid rgba(56, 189, 248, 0.14)',
      boxShadow: '0 16px 40px -12px rgba(2, 6, 23, 0.75)',
      ...sx,
    }}
  >
    {children}
  </Paper>
);

export default MainCard;
