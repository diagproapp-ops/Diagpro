import React, { useState } from 'react';
import {
  Box, TextField, Button, Typography, Alert,
  Divider, MenuItem, Snackbar, Paper
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import SchoolIcon from '@mui/icons-material/School';
import api from '../api';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';

const NIVEL_OPTS = [
  "Fundamental", "Médio", "Superior", "Técnico"
];

const TURNO_OPTS = [
  "Manhã", "Tarde", "Noite", "Integral"
];

export default function DisciplinaFormPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<{
    nome_disciplina: string;
    area_conhecimento: string;
    nivel: string;
    turno: string;
    observacoes: string;
  }>({
    nome_disciplina: '',
    area_conhecimento: '',
    nivel: '',
    turno: '',
    observacoes: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!form.nome_disciplina.trim()) {
      setError('Nome da disciplina é obrigatório.');
      return;
    }
    if (!form.area_conhecimento.trim()) {
      setError('Área de conhecimento é obrigatória.');
      return;
    }
    if (!form.nivel.trim()) {
      setError('Nível é obrigatório.');
      return;
    }
    if (!form.turno.trim()) {
      setError('Turno é obrigatório.');
      return;
    }

    try {
      const payload = {
        ...form
      };
      await api.post('/disciplinas/', payload);
      setSnackbar({ open: true, message: 'Disciplina criada com sucesso!', severity: 'success' });
      setTimeout(() => navigate('/disciplinas'), 1200);
    } catch (err: any) {
      let detail = 'Falha ao criar disciplina';
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
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <SchoolIcon sx={{ color: 'primary.main', mr: 1 }} fontSize="large" />
            <Typography variant="h5" fontWeight="bold">
              Criar Nova Disciplina
            </Typography>
          </Box>
          <Box>
            <Button
              variant="outlined"
              startIcon={<ArrowBackIcon />}
              color="primary"
              onClick={() => navigate('/disciplinas')}
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
              Salvar Disciplina
            </Button>
          </Box>
        </Box>
        <Divider sx={{ mb: 2 }} />
        <Box component="form" onSubmit={handleSubmit} autoComplete="off">
          <TextField
            label="Nome da Disciplina"
            name="nome_disciplina"
            value={form.nome_disciplina}
            onChange={handleChange}
            fullWidth
            required
            sx={{ mb: 2 }}
          />
          <TextField
            label="Área de Conhecimento"
            name="area_conhecimento"
            value={form.area_conhecimento}
            onChange={handleChange}
            fullWidth
            required
            sx={{ mb: 2 }}
          />
          <TextField
            select
            label="Nível"
            name="nivel"
            value={form.nivel}
            onChange={handleChange}
            fullWidth
            required
            sx={{ mb: 2 }}
          >
            {NIVEL_OPTS.map(opt => (
              <MenuItem key={opt} value={opt}>{opt}</MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label="Turno"
            name="turno"
            value={form.turno}
            onChange={handleChange}
            fullWidth
            required
            sx={{ mb: 2 }}
          >
            {TURNO_OPTS.map(opt => (
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
            placeholder="Alguma informação adicional sobre a disciplina."
          />
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        </Box>
        <Box sx={{ mt: 4 }}>
          <Typography variant="h6">Pré-visualização</Typography>
          <Typography>Nome: {form.nome_disciplina}</Typography>
          <Typography>Área de Conhecimento: {form.area_conhecimento}</Typography>
          <Typography>Nível: {form.nivel}</Typography>
          <Typography>Turno: {form.turno}</Typography>
          <Typography>Observações: {form.observacoes}</Typography>
        </Box>
        <Snackbar
          open={snackbar.open}
          autoHideDuration={3000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          message={snackbar.message}
        />
      </Paper>
    </Layout>
  );
}