import React, { useState } from 'react';
import { Box, Paper, Tabs, Tab, Typography } from '@mui/material';
import UserManagementTab from './SettingsTabs/UserManagementTab';
import AppearanceTab from './SettingsTabs/AppearanceTab';
import CompanyDataTab from './SettingsTabs/CompanyDataTab';
import PhraseBankTab from './SettingsTabs/PhraseBankTab';
import Layout from '../components/Layout';

function SettingsPage() {
  const [currentTab, setCurrentTab] = useState(0);

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3, minHeight: '80vh' }}>
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Configurações e Gerenciamento
        </Typography>
        <Tabs
          value={currentTab}
          onChange={(_, v) => setCurrentTab(v)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ mb: 3 }}
        >
          <Tab label="Gerenciar Usuários" />
          <Tab label="Aparência" />
          <Tab label="Dados da Empresa" />
          <Tab label="Banco de Frases" />
        </Tabs>
        <Box>
          {currentTab === 0 && <UserManagementTab />}
          {currentTab === 1 && <AppearanceTab />}
          {currentTab === 2 && <CompanyDataTab />}
          {currentTab === 3 && <PhraseBankTab />}
        </Box>
      </Paper>
    </Layout>
  );
}

export default SettingsPage;