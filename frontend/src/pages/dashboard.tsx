import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
} from '@mui/material';
import EventIcon from '@mui/icons-material/Event';
import AddIcon from '@mui/icons-material/Add';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import api from '../api';
import Layout from '../components/Layout';
import { useNavigate } from 'react-router-dom';

interface Evento {
  id_evento: string;
  nome_evento: string;
  identificador_evento?: string;
  numero_edital?: string;
  local_prova?: string;
  qtd_cargos?: number;
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

  const [dialogOpen, setDialogOpen] = useState(false);
  const [eventoToDelete, setEventoToDelete] = useState<Evento | null>(null);

  useEffect(() => {
    fetchEventos();
  }, []);

  const fetchEventos = async () => {
    try {
      setLoading(true);
      const response = await api.get<Evento[]>('/eventos/');
      setEventos(response.data);
    } catch {
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
      setEventos((prev) => prev.filter((ev) => ev.id_evento !== eventoToDelete.id_evento));
      setError(null);
    } catch {
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

  const abertos = eventos.filter((e) => (e.status || '').toLowerCase().includes('aberto')).length;
  const totalCargos = eventos.reduce((acc, e) => acc + (e.qtd_cargos || 0), 0);

  const kpis = [
    { label: 'Total de Concursos', value: eventos.length, sub: 'Eventos ativos na banca', color: '#F8FAFC' },
    { label: 'Editais Abertos', value: abertos, sub: 'Em fase de elaboração/montagem', color: '#10B981' },
    { label: 'Cargos Vinculados', value: totalCargos, sub: 'Distribuídos nos eventos ativos', color: '#38BDF8' },
    { label: 'Proteção de Sigilo', value: 'Ativa', sub: 'Senhas Fernet + RLS Multi-Tenant', color: '#818CF8' },
  ];

  return (
    <Layout>
      {/* Page Hero Header */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          justifyContent: 'space-between',
          alignItems: { xs: 'flex-start', sm: 'center' },
          gap: 2,
          mb: 3.5,
        }}
      >
        <Box>
          <Stack direction="row" spacing={1.75} alignItems="center" sx={{ mb: 0.75 }}>
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: '11px',
                background: 'linear-gradient(135deg, #0EA5E9 0%, #2563EB 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 16px rgba(14, 165, 233, 0.35)',
              }}
            >
              <EventIcon sx={{ color: '#FFF', fontSize: 22 }} />
            </Box>
            <Typography variant="h4" component="h1" sx={{ fontWeight: 800, color: '#F8FAFC' }}>
              Eventos & Concursos
            </Typography>
          </Stack>
          <Typography sx={{ color: '#94A3B8', fontSize: '0.92rem' }}>
            Gerencie editais, cargos, conteúdos programáticos, banco de questões e geração de cadernos de prova.
          </Typography>
        </Box>

        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          onClick={() => navigate('/eventos/novo')}
          sx={{ px: 2.5, py: 1.2 }}
        >
          Novo Evento
        </Button>
      </Box>

      {/* Status Line */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <CheckCircleOutlineIcon sx={{ color: '#10B981', fontSize: 18 }} />
        <Typography sx={{ color: '#10B981', fontWeight: 600, fontSize: '0.86rem' }}>
          Ambiente da banca sincronizado
        </Typography>
      </Stack>

      {/* KPI Cards */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
          gap: 2,
          mb: 3.5,
        }}
      >
        {kpis.map((k) => (
          <Box
            key={k.label}
            sx={{
              p: 2.5,
              borderRadius: 3,
              bgcolor: '#0B1325',
              border: '1px solid rgba(56, 189, 248, 0.14)',
              boxShadow: '0 8px 24px -8px rgba(2, 6, 23, 0.7)',
            }}
          >
            <Typography sx={{ fontSize: '0.78rem', color: '#94A3B8', mb: 0.75 }}>{k.label}</Typography>
            <Typography sx={{ fontSize: '1.85rem', fontWeight: 800, color: k.color, lineHeight: 1.15, mb: 0.75 }}>
              {k.value}
            </Typography>
            <Typography sx={{ fontSize: '0.74rem', color: '#64748B' }}>{k.sub}</Typography>
          </Box>
        ))}
      </Box>

      {/* Events Table Container */}
      <Box
        sx={{
          p: { xs: 2, md: 3 },
          borderRadius: 3.5,
          bgcolor: '#0B1325',
          border: '1px solid rgba(56, 189, 248, 0.14)',
          boxShadow: '0 16px 40px -12px rgba(2, 6, 23, 0.75)',
        }}
      >
        <Typography sx={{ fontWeight: 700, fontSize: '1.05rem', color: '#F8FAFC', mb: 2 }}>
          Concursos cadastrados
        </Typography>

        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', my: 5 }}>
            <CircularProgress />
          </Box>
        )}
        {error && (
          <Alert severity="error" sx={{ my: 2 }}>
            {error}
          </Alert>
        )}

        {!loading && !error && (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Concurso / Evento</TableCell>
                  <TableCell>Identificador</TableCell>
                  <TableCell>Data da Prova</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Ações</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {eventos.map((evento) => {
                  const isOpen = (evento.status || '').toLowerCase().includes('aberto');
                  return (
                    <TableRow key={evento.id_evento} hover>
                      <TableCell sx={{ fontWeight: 600, color: '#F8FAFC' }}>
                        {evento.nome_evento}
                      </TableCell>
                      <TableCell>
                        <Box
                          component="span"
                          sx={{
                            px: 1.1,
                            py: 0.3,
                            borderRadius: '6px',
                            bgcolor: 'rgba(14, 165, 233, 0.12)',
                            border: '1px solid rgba(56, 189, 248, 0.3)',
                            color: '#38BDF8',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                          }}
                        >
                          {evento.identificador_evento || 'EV'}
                        </Box>
                      </TableCell>
                      <TableCell sx={{ color: '#94A3B8' }}>{formatDateBR(evento.data_prova)}</TableCell>
                      <TableCell>
                        <Box
                          component="span"
                          sx={{
                            px: 1.25,
                            py: 0.35,
                            borderRadius: '999px',
                            bgcolor: isOpen ? 'rgba(16, 185, 129, 0.12)' : 'rgba(148, 163, 184, 0.12)',
                            border: isOpen
                              ? '1px solid rgba(16, 185, 129, 0.35)'
                              : '1px solid rgba(148, 163, 184, 0.25)',
                            color: isOpen ? '#34D399' : '#94A3B8',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                          }}
                        >
                          {evento.status || 'N/D'}
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        <Stack direction="row" spacing={1} justifyContent="flex-end">
                          <Button
                            size="small"
                            variant="outlined"
                            endIcon={<ArrowForwardIcon fontSize="small" />}
                            onClick={() => navigate(`/eventos/${evento.id_evento}`)}
                          >
                            Gerenciar
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            color="error"
                            startIcon={<DeleteOutlineIcon fontSize="small" />}
                            onClick={() => handleDeleteClick(evento)}
                          >
                            Excluir
                          </Button>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  );
                })}
                {eventos.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} align="center" sx={{ py: 5, color: '#64748B' }}>
                      Nenhum evento cadastrado até o momento. Clique em "Novo Evento" para iniciar.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>

      <Dialog open={dialogOpen} onClose={handleDeleteCancel}>
        <DialogTitle sx={{ fontWeight: 700 }}>Confirmar Exclusão</DialogTitle>
        <DialogContent sx={{ color: '#94A3B8' }}>
          Tem certeza que deseja excluir o evento <b style={{ color: '#F8FAFC' }}>{eventoToDelete?.nome_evento}</b>?
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={handleDeleteCancel} variant="outlined">
            Cancelar
          </Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Excluir
          </Button>
        </DialogActions>
      </Dialog>
    </Layout>
  );
}

export default EventManagerPage;
