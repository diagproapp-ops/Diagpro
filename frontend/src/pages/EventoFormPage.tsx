import React, { useState } from 'react';
import type { Dayjs } from 'dayjs';
import {
  Box, TextField, Button, Typography, Alert,
  Divider, MenuItem, Snackbar, Paper
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import EventIcon from '@mui/icons-material/Event';
import api from '../api';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Layout from '../components/Layout';

const STATUS_OPTS = [
  "Planejado", "Aberto", "Em Andamento", "Realizado", "Finalizado", "Cancelado"
];

export default function EventoFormPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [form, setForm] = useState<{
    nome_evento: string;
    data_prova: Dayjs | null;
    status: string;
    numero_edital: string;
    senha_evento: string;
    local_prova: string;
    observacoes: string;
    qtd_cargos: number;
  }>({
    nome_evento: '',
    data_prova: null,
    status: 'Planejado',
    numero_edital: '',
    senha_evento: '',
    local_prova: '',
    observacoes: '',
    qtd_cargos: 1,
  });
  const [error, setError] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

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
    if (!form.senha_evento.trim()) {
      setError('Senha do evento é obrigatória.');
      return;
    }
    if (!user?.tenant_id) {
      setError('Tenant não encontrado. Faça login novamente.');
      return;
    }
    if (!form.qtd_cargos || form.qtd_cargos < 1) {
      setError('Informe a quantidade de cargos (mínimo 1).');
      return;
    }

    try {
      const payload = {
        ...form,
        qtd_cargos: Number(form.qtd_cargos),
        data_prova: form.data_prova ? form.data_prova.format('YYYY-MM-DD') : null,
        tenant_id: Number(user.tenant_id),
      };
      const res = await api.post('/eventos/', payload);
      setSnackbar({ open: true, message: 'Evento criado com sucesso!', severity: 'success' });
      setTimeout(() => navigate(`/eventos/${res.data.id_evento}`), 1200);
    } catch (err: any) {
      let detail = 'Falha ao criar evento';
      if (err.response?.data?.detail) {
        if (typeof err.response.data.detail === 'string') {
          detail = err.response.data.detail;
        } else if (Array.isArray(err.response.data.detail)) {
          detail = err.response.data.detail.map((e: any) => e.msg).join('; ');
        } else if (err.response.data.detail.msg) {
          detail = err.response.data.detail.msg;
        } else {
          detail = JSON.stringify(err.response.data.detail);
        }
      }
      setSnackbar({ open: true, message: detail, severity: 'error' });
    }
  }

  return (
    <Layout>
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
          {/* Botões no topo, padronizado */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <EventIcon sx={{ color: 'primary.main', mr: 1 }} fontSize="large" />
              <Typography variant="h5" fontWeight="bold">
                Criar Novo Evento
              </Typography>
            </Box>
            <Box>
              <Button
                variant="outlined"
                startIcon={<ArrowBackIcon />}
                color="primary"
                onClick={() => navigate('/dashboard')}
                sx={{ mr: 1 }}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                variant="contained"
                color="primary"
                onClick={handleSubmit}
              >
                Salvar Evento
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
              label="Senha do Evento"
              name="senha_evento"
              value={form.senha_evento}
              onChange={handleChange}
              type="password"
              fullWidth
              required
              sx={{ mb: 2 }}
              placeholder="Digite uma senha forte"
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