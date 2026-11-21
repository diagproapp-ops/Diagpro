import React, { useState, useEffect } from 'react';
import {
  Box, TextField, Button, Typography, Alert, MenuItem, Snackbar, Divider, Paper
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import EditIcon from '@mui/icons-material/Edit';
import api from '../api';
import { useNavigate, useParams } from 'react-router-dom';
import dayjs, { Dayjs } from 'dayjs';
import Layout from '../components/Layout';

const STATUS_OPTS = [
  "Planejado", "Aberto", "Em Andamento", "Realizado", "Finalizado", "Cancelado"
];

type EventoFormState = {
  nome_evento: string;
  data_prova: Dayjs | null;
  status: string;
  numero_edital: string;
  local_prova: string;
  observacoes: string;
  qtd_cargos: number;
};

export default function EventoEditPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const navigate = useNavigate();
  const [form, setForm] = useState<EventoFormState>({
    nome_evento: '',
    data_prova: null,
    status: 'Planejado',
    numero_edital: '',
    local_prova: '',
    observacoes: '',
    qtd_cargos: 1,
  });
  const [error, setError] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  useEffect(() => {
    async function fetchEvento() {
      if (!eventId) return;
      try {
        const res = await api.get(`/eventos/${eventId}`);
        setForm({
          nome_evento: res.data.nome_evento || '',
          data_prova: res.data.data_prova ? dayjs(res.data.data_prova) : null,
          status: res.data.status || 'Planejado',
          numero_edital: res.data.numero_edital || '',
          local_prova: res.data.local_prova || '',
          observacoes: res.data.observacoes || '',
          qtd_cargos: res.data.qtd_cargos || 1,
        });
        setError(null);
      } catch (err: any) {
        setError(err?.response?.data?.detail || 'Falha ao carregar dados do evento.');
      }
    }
    fetchEvento();
  }, [eventId]);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  function handleNumberChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm({ ...form, [e.target.name]: Number(e.target.value) });
  }

  function handleDateChange(date: Dayjs | null) {
    setForm({ ...form, data_prova: date });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!form.nome_evento.trim()) {
      setError('Nome do evento é obrigatório.');
      return;
    }
    if (!form.data_prova) {
      setError('Data da prova é obrigatória.');
      return;
    }
    if (!form.qtd_cargos || form.qtd_cargos < 1) {
      setError('Informe a quantidade de cargos (mínimo 1).');
      return;
    }

    try {
      const payload = {
        ...form,
        data_prova: form.data_prova ? form.data_prova.format('YYYY-MM-DD') : null,
      };
      await api.put(`/eventos/${eventId}`, payload);
      setSnackbar({ open: true, message: 'Evento editado com sucesso!', severity: 'success' });
      setTimeout(() => navigate(`/eventos/${eventId}`), 1200);
    } catch (err) {
      setSnackbar({ open: true, message: 'Falha ao editar evento', severity: 'error' });
    }
  }

  return (
    <Layout>
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
          {/* Botões no topo */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <EditIcon sx={{ color: 'primary.main', mr: 1 }} fontSize="large" />
              <Typography variant="h5" fontWeight="bold">
                Editar Evento
              </Typography>
            </Box>
            <Box>
              <Button
                variant="outlined"
                startIcon={<ArrowBackIcon />}
                color="primary"
                onClick={() => navigate(`/eventos/${eventId}`)}
                sx={{ mr: 1 }}
              >
                Voltar
              </Button>
              <Button
                type="submit"
                variant="contained"
                color="primary"
                onClick={handleSubmit}
              >
                Salvar Alterações
              </Button>
            </Box>
          </Box>
          <Divider sx={{ mb: 2 }} />
          <Box component="form" onSubmit={handleSubmit} autoComplete="off">
            <TextField
              label="Nome do Evento"
              name="nome_evento"
              value={form.nome_evento}
              onChange={handleChange}
              fullWidth
              required
              sx={{ mb: 2 }}
            />
            <DatePicker
              label="Data da Prova"
              value={form.data_prova}
              onChange={handleDateChange}
              format="DD/MM/YYYY"
              sx={{ mb: 2, width: '100%' }}
              slotProps={{ textField: { fullWidth: true, required: true } }}
            />
            <TextField
              label="Número do Edital"
              name="numero_edital"
              value={form.numero_edital}
              onChange={handleChange}
              fullWidth
              sx={{ mb: 2 }}
              placeholder="Ex: 001/2025"
            />
            <TextField
              label="Local da Prova"
              name="local_prova"
              value={form.local_prova}
              onChange={handleChange}
              fullWidth
              sx={{ mb: 2 }}
              placeholder="Ex: Escola Municipal, Ginásio, etc."
            />
            <TextField
              select
              label="Status"
              name="status"
              value={form.status}
              onChange={handleChange}
              fullWidth
              sx={{ mb: 2 }}
            >
              {STATUS_OPTS.map(opt => (
                <MenuItem key={opt} value={opt}>{opt}</MenuItem>
              ))}
            </TextField>
            <TextField
              label="Observações"
              name="observacoes"
              value={form.observacoes}
              onChange={handleChange}
              multiline
              rows={3}
              fullWidth
              sx={{ mb: 2 }}
              placeholder="Alguma informação adicional sobre o evento."
            />
            <TextField
              label="Quantidade de Cargos"
              name="qtd_cargos"
              type="number"
              value={form.qtd_cargos}
              onChange={handleNumberChange}
              fullWidth
              sx={{ mb: 2 }}
              inputProps={{ min: 1 }}
              required
            />
            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          </Box>
          <Box sx={{ mt: 4 }}>
            <Typography variant="h6">Pré-visualização</Typography>
            <Typography>Nome: {form.nome_evento}</Typography>
            <Typography>
              Data da Prova: {form.data_prova ? form.data_prova.format('DD/MM/YYYY') : ''}
            </Typography>
            <Typography>Status: {form.status}</Typography>
            <Typography>Edital: {form.numero_edital}</Typography>
            <Typography>Local: {form.local_prova}</Typography>
            <Typography>Observações: {form.observacoes}</Typography>
            <Typography>Quantidade de Cargos: {form.qtd_cargos}</Typography>
          </Box>
          <Snackbar
            open={snackbar.open}
            autoHideDuration={3000}
            onClose={() => setSnackbar({ ...snackbar, open: false })}
            message={snackbar.message}
          />
        </Paper>
      </LocalizationProvider>
    </Layout>
  );
}