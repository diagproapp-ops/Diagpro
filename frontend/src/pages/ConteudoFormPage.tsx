import React, { useState, useEffect } from 'react';
import {
  Box, TextField, Button, Typography, Alert,
  Divider, MenuItem, Snackbar, Paper
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AddCircleIcon from '@mui/icons-material/AddCircle';
import api from '../api';
import { useNavigate, useParams } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';

const NIVEL_OPTS = ["Fundamental", "Médio", "Superior", "Técnico"];
const TURNO_OPTS = ["Matutino", "Vespertino", "Noturno", "Integral"];

export default function ConteudoFormPage() {
  const navigate = useNavigate();
  const { eventId } = useParams<{ eventId: string }>();
  const { user } = useAuth();

  const [form, setForm] = useState<{
    nome_conteudo: string;
    descricao: string;
    area_conhecimento: string;
    turno: string;
    nivel: string;
    quantidade: number;
    professor_id: string;
  }>({
    nome_conteudo: '',
    descricao: '',
    area_conhecimento: '',
    turno: '',
    nivel: '',
    quantidade: 0,
    professor_id: '',
  });

  const [professores, setProfessores] = useState<{ id: number, full_name?: string, username: string }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  useEffect(() => {
    async function fetchProfessores() {
      try {
        const res = await api.get('/users/');
        setProfessores(res.data.filter((u: any) => u.role === 'professor'));
      } catch {
        // erro ao carregar professores
      }
    }
    fetchProfessores();
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  function handleNumberChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm({ ...form, quantidade: Number(e.target.value) });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    // Validações obrigatórias
    if (!form.nome_conteudo.trim()) {
      setError('Nome do conteúdo é obrigatório.');
      return;
    }
    if (!form.area_conhecimento.trim()) {
      setError('Área de conhecimento é obrigatória.');
      return;
    }
    if (!form.turno.trim()) {
      setError('Turno é obrigatório.');
      return;
    }
    if (!form.nivel.trim()) {
      setError('Nível é obrigatório.');
      return;
    }
    if (form.quantidade < 0 || form.quantidade > 100) {
      setError('A quantidade deve estar entre 0 e 100.');
      return;
    }
    if (!form.professor_id) {
      setError('Selecione o professor responsável.');
      return;
    }

    try {
      const payload = {
            ...form,
            tenant_id: user?.tenant_id,
            evento_id: eventId,
            professor_id: form.professor_id ? String(form.professor_id) : null, // <-- ALTERE AQUI!
            quantidade: form.quantidade ? Number(form.quantidade) : 0,
        };
        await api.post(`/conteudos/eventos/${eventId}/conteudos`, payload);
      setSnackbar({ open: true, message: 'Conteúdo criado com sucesso!', severity: 'success' });
      setTimeout(() => {
        navigate(`/eventos/${eventId}/conteudo`);
      }, 1200);
    } catch (err: any) {
      let detail = 'Falha ao criar conteúdo';
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
            <AddCircleIcon sx={{ color: 'primary.main', mr: 1 }} fontSize="large" />
            <Typography variant="h5" fontWeight="bold">
              Criar Novo Conteúdo
            </Typography>
          </Box>
          <Box>
            <Button
              variant="outlined"
              startIcon={<ArrowBackIcon />}
              color="primary"
              onClick={() => navigate(`/eventos/${eventId}/conteudo`)}
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
              Salvar Conteúdo
            </Button>
          </Box>
        </Box>
        <Divider sx={{ mb: 2 }} />
        <Box component="form" onSubmit={handleSubmit} autoComplete="off">
          <TextField
            label="Nome do Conteúdo"
            name="nome_conteudo"
            value={form.nome_conteudo}
            onChange={handleChange}
            fullWidth
            required
            sx={{ mb: 2 }}
          />
          <TextField
            label="Descrição"
            name="descricao"
            value={form.descricao}
            onChange={handleChange}
            fullWidth
            multiline
            rows={2}
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
            label="Quantidade de questões"
            name="quantidade"
            type="number"
            value={form.quantidade}
            onChange={handleNumberChange}
            fullWidth
            required
            sx={{ mb: 2 }}
            inputProps={{ min: 0 }}
            placeholder="Total de questões"
          />
          <TextField
            select
            label="Professor Responsável"
            name="professor_id"
            value={form.professor_id}
            onChange={handleChange}
            fullWidth
            required
            sx={{ mb: 2 }}
          >
            <MenuItem value="">Selecione</MenuItem>
            {professores.map(prof => (
              <MenuItem key={prof.id} value={prof.id}>
                {prof.full_name || prof.username}
              </MenuItem>
            ))}
          </TextField>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        </Box>
        <Box sx={{ mt: 4 }}>
          <Typography variant="h6">Pré-visualização</Typography>
          <Typography>Nome: {form.nome_conteudo}</Typography>
          <Typography>Descrição: {form.descricao}</Typography>
          <Typography>Área de Conhecimento: {form.area_conhecimento}</Typography>
          <Typography>Turno: {form.turno}</Typography>
          <Typography>Nível: {form.nivel}</Typography>
          <Typography>Quantidade: {form.quantidade}%</Typography>
          <Typography>Professor: {
            professores.find(p => String(p.id) === String(form.professor_id))?.full_name ||
            professores.find(p => String(p.id) === String(form.professor_id))?.username ||
            ""
          }</Typography>
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