import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogContent, DialogActions, TextField, Divider } from '@mui/material';
import api from '../api';
import Layout from '../components/Layout';
import MainCard from '../components/MainCard';
import { Evento as EventoType, Cargo } from '../types';
import { useAuth } from '../contexts/AuthContext'; // IMPORTANTE!

function useQuery() {
  return new URLSearchParams(useLocation().search);
}

function EventoDetalhesPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const query = useQuery();
  const navigate = useNavigate();
  const { user } = useAuth(); // PEGUE O USUÁRIO

  const [evento, setEvento] = useState<EventoType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Estado para senha
  const [senha, setSenha] = useState<string>(query.get('senha') || '');
  const [senhaModalOpen, setSenhaModalOpen] = useState(!senha);
  const [senhaError, setSenhaError] = useState<string | null>(null);

  // SE FOR PROFESSOR, REDIRECIONA DIRETO PARA A TELA DE CONTEÚDO
  React.useEffect(() => {
    if (user && user.role === 'professor' && eventId) {
      navigate(`/eventos/${eventId}/conteudo`, { replace: true });
    }
  }, [user, eventId, navigate]);

  useEffect(() => {
    // Se for professor, não busca detalhes do evento!
    if (user && user.role === 'professor') return;

    if (eventId && senha) {
      const fetchEvento = async () => {
        try {
          setLoading(true);
          const response = await api.get<EventoType>(`/eventos/${eventId}/detalhes?senha=${encodeURIComponent(senha)}`);
          setEvento(response.data);
          setError(null);
        } catch (err: any) {
          setError(err.response?.data?.detail || 'Falha ao buscar detalhes do evento.');
        } finally {
          setLoading(false);
        }
      };
      fetchEvento();
    }
  }, [eventId, senha, user]);

  const handleSenhaSubmit = () => {
    if (!senha) {
      setSenhaError('Digite a senha do evento');
      return;
    }
    setSenhaModalOpen(false);
    setSenhaError(null);
  };

  function formatDateBR(dateStr: string | null): string {
    if (!dateStr) return 'N/D';
    try {
      const date = new Date(dateStr);
      const dia = String(date.getDate()).padStart(2, '0');
      const mes = String(date.getMonth() + 1).padStart(2, '0');
      const ano = date.getFullYear();
      return `${dia}/${mes}/${ano}`;
    } catch {
      return 'N/D';
    }
  }

  // Se for professor, não renderiza nada dessa página
  if (user && user.role === 'professor') return null;

  return (
    <Layout>
      <MainCard>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1" fontWeight="bold">
            Detalhes do Evento
          </Typography>
          <Box>
            <Button
              variant="contained"
              color="primary"
              onClick={() => navigate(`/eventos/${eventId}/editar`)}
              sx={{ mr: 2 }}
            >
              Editar Evento
            </Button>
            <Button
              variant="outlined"
              color="primary"
              onClick={() => navigate('/dashboard')}
            >
              Voltar para a Lista
            </Button>
          </Box>
        </Box>
        <Divider sx={{ mb: 2 }} />
        {loading && <Box sx={{ display: 'flex', justifyContent: 'center', my: 5 }}><CircularProgress /></Box>}
        {error && <Alert severity="error" sx={{ my: 2 }}>{error}</Alert>}
        {evento && (
          <Box>
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" fontWeight="bold">{evento.nome_evento}</Typography>
              <Typography>Identificador: <b>{evento.identificador_evento || 'N/D'}</b></Typography>
              <Typography>Status: <b>{evento.status || 'N/D'}</b></Typography>
              <Typography>Data da Prova: <b>{formatDateBR(evento.data_prova)}</b></Typography>
              {evento.numero_edital && <Typography>Edital: <b>{evento.numero_edital}</b></Typography>}
              {evento.local_prova && <Typography>Local da Prova: <b>{evento.local_prova}</b></Typography>}
              {evento.observacoes && <Typography>Observações: <b>{evento.observacoes}</b></Typography>}
            </Box>
            <Divider sx={{ mb: 2 }} />
            <Typography variant="h6" fontWeight="bold" sx={{ mb: 1 }}>Cargos do Evento</Typography>
            {evento.cargos && evento.cargos.length > 0 ? (
              <Box component="ul" sx={{ pl: 2 }}>
                {evento.cargos.map((cargo: Cargo) => (
                  <li key={cargo.id_cargo}>{cargo.nome_cargo}</li>
                ))}
              </Box>
            ) : (
              <Typography>Nenhum cargo encontrado para este evento.</Typography>
            )}
          </Box>
        )}
      </MainCard>
      {/* Modal para senha */}
      <Dialog open={senhaModalOpen} onClose={() => navigate('/dashboard')}>
        <DialogTitle>Digite a senha do evento</DialogTitle>
        <DialogContent>
          <TextField
            type="password"
            label="Senha"
            value={senha}
            onChange={e => setSenha(e.target.value)}
            fullWidth
            autoFocus
            error={!!senhaError}
            helperText={senhaError}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleSenhaSubmit} variant="contained">Entrar</Button>
          <Button onClick={() => navigate('/dashboard')}>Cancelar</Button>
        </DialogActions>
      </Dialog>
    </Layout>
  );
}

export default EventoDetalhesPage;