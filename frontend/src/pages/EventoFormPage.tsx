import React, { useState } from 'react';
import type { Dayjs } from 'dayjs';
import {
  Box, TextField, Button, Typography, Alert,
  Divider, MenuItem, Snackbar, Paper, Chip
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import EventIcon from '@mui/icons-material/Event';
import SaveOutlinedIcon from '@mui/icons-material/SaveOutlined';
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
    // O cliente do evento é sempre o do usuário (ou o cliente em gestão do administrador geral).
    // Nunca há cliente padrão: na visão global, é preciso escolher o cliente no topo da tela.
    const effectiveTenantId = Number(user?.tenant_id || 0);
    if (!effectiveTenantId) {
      setError('Escolha no topo da tela o cliente para o qual este evento será criado.');
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
        tenant_id: effectiveTenantId,
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
        <Paper
          sx={{
            p: { xs: 3, md: 4 },
            borderRadius: 3,
            background: 'rgba(13, 25, 43, 0.85)',
            border: '1px solid rgba(56, 189, 248, 0.14)',
            boxShadow: '0 16px 40px rgba(0, 0, 0, 0.45)',
          }}
        >
          {/* Cabeçalho no padrão Operan Pro Dark */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Box
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: 2.5,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)',
                  boxShadow: '0 6px 18px rgba(14, 165, 233, 0.35)',
                }}
              >
                <EventIcon sx={{ color: '#fff' }} />
              </Box>
              <Box>
                <Typography variant="h5" fontWeight={700} sx={{ letterSpacing: '-0.02em' }}>
                  Criar Novo Evento / Concurso
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Cadastre o certame, defina a senha de proteção do evento e configure a estrutura inicial de cargos.
                </Typography>
              </Box>
            </Box>
            <Box sx={{ display: 'flex', gap: 1.5 }}>
              <Button
                variant="outlined"
                startIcon={<ArrowBackIcon />}
                color="primary"
                onClick={() => navigate('/dashboard')}
              >
                Cancelar
              </Button>
              <Button
                type="submit"
                variant="contained"
                color="primary"
                startIcon={<SaveOutlinedIcon />}
                onClick={handleSubmit}
              >
                Salvar Evento
              </Button>
            </Box>
          </Box>
          <Divider sx={{ mb: 3 }} />
          <Box component="form" onSubmit={handleSubmit} autoComplete="off">
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
                gap: 2.5,
              }}
            >
              <Box sx={{ gridColumn: { xs: '1', md: 'span 2' } }}>
                <TextField
                  label="Nome do Evento"
                  name="nome_evento"
                  value={form.nome_evento}
                  onChange={handleChange}
                  fullWidth
                  required
                />
              </Box>
              <Box>
                <DatePicker
                  label="Data da Prova"
                  value={form.data_prova}
                  onChange={handleDateChange}
                  format="DD/MM/YYYY"
                  sx={{ width: '100%' }}
                  slotProps={{ textField: { fullWidth: true, required: true } }}
                />
              </Box>
              <Box>
                <TextField
                  label="Número do Edital"
                  name="numero_edital"
                  value={form.numero_edital}
                  onChange={handleChange}
                  fullWidth
                  placeholder="Ex: 001/2026"
                />
              </Box>
              <Box>
                <TextField
                  label="Senha do Evento"
                  name="senha_evento"
                  value={form.senha_evento}
                  onChange={handleChange}
                  type="password"
                  fullWidth
                  required
                  placeholder="Digite uma senha forte"
                />
              </Box>
              <Box>
                <TextField
                  select
                  label="Status"
                  name="status"
                  value={form.status}
                  onChange={handleChange}
                  fullWidth
                >
                  {STATUS_OPTS.map(opt => (
                    <MenuItem key={opt} value={opt}>{opt}</MenuItem>
                  ))}
                </TextField>
              </Box>
              <Box sx={{ gridColumn: { xs: '1', md: 'span 2' } }}>
                <TextField
                  label="Local da Prova"
                  name="local_prova"
                  value={form.local_prova}
                  onChange={handleChange}
                  fullWidth
                  placeholder="Ex: Brasília-DF, Escola Municipal, etc."
                />
              </Box>
              <Box>
                <TextField
                  label="Quantidade de Cargos"
                  name="qtd_cargos"
                  type="number"
                  value={form.qtd_cargos}
                  onChange={handleNumberChange}
                  fullWidth
                  inputProps={{ min: 1 }}
                  required
                />
              </Box>
              <Box sx={{ gridColumn: { xs: '1', md: 'span 3' } }}>
                <TextField
                  label="Observações"
                  name="observacoes"
                  value={form.observacoes}
                  onChange={handleChange}
                  multiline
                  rows={3}
                  fullWidth
                  placeholder="Alguma informação adicional sobre o evento."
                />
              </Box>
            </Box>
            {error && <Alert severity="error" sx={{ mt: 2.5 }}>{error}</Alert>}
          </Box>
          <Box
            sx={{
              mt: 3.5,
              p: 2.5,
              borderRadius: 2.5,
              background: 'rgba(7, 15, 29, 0.65)',
              border: '1px solid rgba(148, 163, 184, 0.14)',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
              <Typography variant="subtitle1" fontWeight={700}>
                Pré-visualização do Certame
              </Typography>
              <Chip label={form.status} size="small" color="primary" variant="outlined" />
            </Box>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
                gap: 1.5,
              }}
            >
              <Box>
                <Typography variant="caption" color="text.secondary">Nome</Typography>
                <Typography variant="body2" fontWeight={600}>{form.nome_evento || '—'}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Data da Prova</Typography>
                <Typography variant="body2" fontWeight={600}>
                  {form.data_prova ? form.data_prova.format('DD/MM/YYYY') : '—'}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Edital</Typography>
                <Typography variant="body2" fontWeight={600}>{form.numero_edital || '—'}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Local</Typography>
                <Typography variant="body2" fontWeight={600}>{form.local_prova || '—'}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Quantidade de Cargos</Typography>
                <Typography variant="body2" fontWeight={600}>{form.qtd_cargos}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Observações</Typography>
                <Typography variant="body2" fontWeight={600}>{form.observacoes || '—'}</Typography>
              </Box>
            </Box>
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
