import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import { Box, CircularProgress } from '@mui/material';
import LoginPage from './pages/login';
import EventManagerPage from './pages/dashboard';
import EventoDetalhesPage from './pages/EventoDetalhesPage';
import EventoFormPage from './pages/EventoFormPage';
import EventoEditPage from './pages/EventoEditPage';
import SettingsPage from './pages/SettingsPage';
import { CustomThemeProvider } from "./contexts/ThemeContext";
import AdminClientsTab from './pages/AdminClientsTab';
import CargoManagerPage from './pages/CargoManagerPage';
import ConteudoPage from './pages/ConteudoPage';
import ConteudoFormPage from './pages/ConteudoFormPage';
import ConteudoEditPage from './pages/ConteudoEditPage';
import ConteudoIniciarPage from './pages/ConteudoIniciarPage';
import AdicionarTextoReferenciaPage from './pages/AdicionarTextoReferenciaPage'; // <-- Adicione este import
import CriarQuestaoPage from './pages/CriarQuestaoPage';
import EditarQuestaoPage from './pages/EditarQuestaoPage';
import RevisarQuestaoPage from './pages/RevisarQuestaoPage';
import EditarTextoReferenciaPage from './pages/EditarTextoReferenciaPage';
import RevisaoTextoReferenciaPage from './pages/RevisaoTextoReferenciaPage';
import MontagemProvaDashboardPage from './pages/MontagemProvaDashboardPage';
import MontagemProvaPage from './pages/MontagemProvaPage';
import ProvaGeracaoPage from './pages/ProvaGeracaoPage';
import ExportacaoPage from './pages/ExportacaoPage';
import GabaritoPage from './pages/GabaritoPage';
import TemplatesPage from './pages/TemplatesPage';
import PublicRegisterPage from './pages/PublicRegisterPage';

function App() {
  const { isAuthenticated, loading, user } = useAuth();

  return (
    <CustomThemeProvider>
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
          <CircularProgress />
        </Box>
      ) : (
        <Router>
          <Routes>
            {!isAuthenticated ? (
              <>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<PublicRegisterPage />} />
                <Route path="*" element={<Navigate to="/login" replace />} />
              </>
            ) : (
              <>
                {/* Se for professor, só deixa acessar conteúdo */}
                {user && user.role === 'professor' ? (
                  <>
                    <Route path="/eventos/:eventId/conteudo" element={<ConteudoPage />} />
                    <Route path="/eventos/:eventId/conteudo/criar" element={<ConteudoFormPage />} />
                    <Route path="/eventos/:eventId/conteudo/editar/:conteudoId" element={<ConteudoEditPage />} />
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/iniciar" element={<ConteudoIniciarPage />} />
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/referencia/adicionar" element={<AdicionarTextoReferenciaPage />} /> {/* <-- NOVA ROTA */}
                    <Route path="/conteudos" element={<ConteudoPage />} />
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/questao/criar" element={<CriarQuestaoPage />} />
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/questao/:id_questao/editar" element={<EditarQuestaoPage />} />
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/referencia/:id_texto_ref/editar" element={<EditarTextoReferenciaPage />} />
                    {/* Redireciona qualquer outro caminho para "Meus Conteúdos" */}
                    <Route path="*" element={<Navigate to="/conteudos" replace />} />
                  </>
                ) : (
                  <>
                    <Route path="/dashboard" element={<EventManagerPage />} />
                    <Route path="/eventos/novo" element={<EventoFormPage />} />
                    <Route path="/eventos/:eventId/editar" element={<EventoEditPage />} />
                    <Route path="/eventos/:eventId" element={<EventoDetalhesPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/eventos/:eventId/cargo" element={<CargoManagerPage />} />
                    <Route path="/eventos/:eventId/conteudo" element={<ConteudoPage />} />
                    <Route path="/eventos/:eventId/conteudo/criar" element={<ConteudoFormPage />} />
                    <Route path="/eventos/:eventId/conteudo/editar/:conteudoId" element={<ConteudoEditPage />} />
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/iniciar" element={<ConteudoIniciarPage />} />
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/referencia/adicionar" element={<AdicionarTextoReferenciaPage />} /> {/* <-- NOVA ROTA */}
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/questao/criar" element={<CriarQuestaoPage />} />
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/questao/:id_questao/editar" element={<EditarQuestaoPage />} />
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/referencia/:id_texto_ref/editar" element={<EditarTextoReferenciaPage />} />
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/questao/:id_questao/revisar" element={<RevisarQuestaoPage />} />
                    <Route path="/eventos/:eventId/conteudo/:id_conteudo/referencia/:id_texto_ref/revisar" element={<RevisaoTextoReferenciaPage />} />
                    <Route path="/eventos/:eventId/provas" element={<MontagemProvaDashboardPage />} />
                    <Route path="/eventos/:eventId/provas/montagem" element={<MontagemProvaPage />} />
                    <Route path="/eventos/:eventId/geracao" element={<ProvaGeracaoPage />} />
                    <Route path="/eventos/:eventId/exportacao" element={<ExportacaoPage />} />
                    <Route path="/eventos/:eventId/recursos" element={<GabaritoPage />} />
                    <Route path="/eventos/:eventId/templates" element={<TemplatesPage />} />
                    <Route
                      path="/admin/clients"
                      element={
                        user && user.role === 'administrador geral'
                          ? <AdminClientsTab />
                          : <Navigate to="/dashboard" replace />
                      }
                    />
                    <Route path="*" element={<Navigate to="/dashboard" replace />} />
                  </>
                )}
              </>
            )}
          </Routes>
        </Router>
      )}
    </CustomThemeProvider>
  );
}

export default App;