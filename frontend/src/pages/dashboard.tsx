import React, { useState, useEffect } from 'react';
import { Box, Button, Typography, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, CircularProgress, Alert, Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material';
import api from '../api';
import Layout from '../components/Layout';
import { useNavigate } from 'react-router-dom';

interface Evento {
  id_evento: string;
  nome_evento: string;
  data_prova: string | null;
  status: string | null;
}

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

function EventManagerPage() {
  const navigate = useNavigate();
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Controle do diálogo de confirmação de exclusão
  const [dialogOpen, setDialogOpen] = useState(false);
  const [eventoToDelete, setEventoToDelete] = useState<Evento | null>(null);

  useEffect(() => {
    fetchEventos();
    // eslint-disable-next-line
  }, []);

  const fetchEventos = async () => {
    try {
      setLoading(true);
      const response = await api.get<Evento[]>('/eventos/');
      setEventos(response.data);
    } catch (err) {
      setError('Falha ao buscar eventos.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (evento: Evento) => {
    setEventoToDelete(evento);
    setDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!eventoToDelete) return;
    try {
      await api.delete(`/eventos/${eventoToDelete.id_evento}`);
      setEventos((prev) => prev.filter(ev => ev.id_evento !== eventoToDelete.id_evento));
      setError(null);
    } catch (err) {
      setError('Erro ao excluir evento.');
    } finally {
      setDialogOpen(false);
      setEventoToDelete(null);
    }
  };

  const handleDeleteCancel = () => {
    setDialogOpen(false);
    setEventoToDelete(null);
  };

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1" fontWeight="bold">
            Gestão de Eventos
          </Typography>
          <Box>
            <Button
              variant="contained"
              color="primary"
              onClick={() => navigate('/eventos/novo')}
              sx={{ mr: 2 }}
            >
              Novo Evento
            </Button>
          </Box>
        </Box>

        {loading && <Box sx={{ display: 'flex', justifyContent: 'center', my: 5 }}><CircularProgress /></Box>}
        {error && <Alert severity="error" sx={{ my: 2 }}>{error}</Alert>}

        {!loading && !error && (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                  <TableCell>Nome do Evento</TableCell>
                  <TableCell>Data da Prova</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="center">Ações</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {eventos.map((evento) => (
                  <TableRow key={evento.id_evento} hover>
                    <TableCell>{evento.nome_evento}</TableCell>
                    <TableCell>
                      {formatDateBR(evento.data_prova)}
                    </TableCell>
                    <TableCell>{evento.status || 'N/D'}</TableCell>
                    <TableCell align="center">
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => navigate(`/eventos/${evento.id_evento}`)}
                        sx={{ mr: 1 }}
                      >
                        Detalhes
                      </Button>
                      <Button
                        size="small"
                        variant="contained"
                        color="error"
                        onClick={() => handleDeleteClick(evento)}
                      >
                        Excluir
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Diálogo de confirmação de exclusão */}
        <Dialog open={dialogOpen} onClose={handleDeleteCancel}>
          <DialogTitle>Confirmação</DialogTitle>
          <DialogContent>
            Tem certeza que deseja excluir o evento <b>{eventoToDelete?.nome_evento}</b>?
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDeleteCancel} color="primary">
              Cancelar
            </Button>
            <Button onClick={handleDeleteConfirm} color="error" variant="contained">
              Excluir
            </Button>
          </DialogActions>
        </Dialog>
      </Paper>
    </Layout>
  );
}

export default EventManagerPage;