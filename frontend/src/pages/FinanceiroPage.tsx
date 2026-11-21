import React from 'react';
import { Alert, Box, Paper, Typography } from '@mui/material';
import AccountBalanceWalletOutlinedIcon from '@mui/icons-material/AccountBalanceWalletOutlined';
import Layout from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import FinanceiroBanca from '../components/financeiro/FinanceiroBanca';
import FinanceiroPlataforma from '../components/financeiro/FinanceiroPlataforma';
import MeuFinanceiro from '../components/financeiro/MeuFinanceiro';

// Cada perfil vê só o seu lado do financeiro:
//  - administrador geral: plataforma x bancas (planos, propostas, termos, faturas) — nunca os pagamentos a professores;
//  - administrador da banca: contratos com os professores + a conta da banca na plataforma;
//  - professor: o próprio extrato e os contratos para aceitar.
const FinanceiroPage: React.FC = () => {
  const { user } = useAuth();
  const papel = user?.role;
  const titulo = papel === 'professor' ? 'Meus ganhos' : papel === 'administrador geral' ? 'Financeiro da plataforma' : 'Financeiro';
  const sub = papel === 'professor'
    ? 'Seus contratos com a banca, o que já recebeu e o que falta para liberar cada parcela.'
    : papel === 'administrador geral'
      ? 'Planos, propostas, contratos, faturas e documentos de cada banca.'
      : 'Contratos com os professores (cada um com a sua negociação), parcelas, documentos e a conta da banca na plataforma.';
  return (
    <Layout>
      <Paper sx={{ p: { xs: 2, md: 3.5 }, borderRadius: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.5 }}>
          <AccountBalanceWalletOutlinedIcon color="primary" />
          <Typography variant="h5" fontWeight={800}>{titulo}</Typography>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>{sub}</Typography>
        {papel === 'administrador geral' ? <FinanceiroPlataforma />
          : papel === 'administrador' ? <FinanceiroBanca />
            : papel === 'professor' ? <MeuFinanceiro />
              : <Alert severity="info">O financeiro é do administrador da banca e de cada professor.</Alert>}
      </Paper>
    </Layout>
  );
};

export default FinanceiroPage;
