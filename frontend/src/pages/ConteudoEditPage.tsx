import React, { useEffect, useState } from "react";
import {
  Box, TextField, Button, Typography, Alert,
  Divider, MenuItem, Snackbar, Paper
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import SaveIcon from "@mui/icons-material/Save";
import api from "../api";
import { useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import { useAuth } from "../contexts/AuthContext";

const NIVEL_OPTS = ["Fundamental", "Médio", "Superior", "Técnico"];
const TURNO_OPTS = ["Matutino", "Vespertino", "Noturno", "Integral"];

export default function ConteudoEditPage() {
  const navigate = useNavigate();
  const { conteudoId, eventId } = useParams<{ conteudoId: string; eventId: string }>();
  const { user } = useAuth();

  // Professores
  const [professores, setProfessores] = useState<{ id: number, full_name?: string, username: string }[]>([]);

  // Formulário
  const [form, setForm] = useState<any>({
    nome_conteudo: "",
    descricao: "",
    area_conhecimento: "",
    turno: "",
    nivel: "",
    quantidade: 0,
    respondidas: 0,
    professor_id: "", // <-- nunca null!
  });

  const [error, setError] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: "", severity: "success" });

  useEffect(() => {
    async function fetchConteudo() {
      if (!conteudoId) return;
      try {
        const res = await api.get(`/conteudos/eventos/${eventId}/conteudos`);
        const c = res.data.find((c: any) => c.id_conteudo === conteudoId);
        if (c) {
          setForm({
            ...form,
            ...c,
            nome_conteudo: c.nome_conteudo || "",
            descricao: c.descricao || "",
            area_conhecimento: c.area_conhecimento || "",
            turno: c.turno || "",
            nivel: c.nivel || "",
            quantidade: c.quantidade ?? 0,
            respondidas: c.respondidas ?? 0,
            professor_id: c.professor_id ? String(c.professor_id) : "",
          });
        }
      } catch {
        setSnackbar({ open: true, message: "Falha ao carregar conteúdo", severity: "error" });
      }
    }
    fetchConteudo();
    // eslint-disable-next-line
  }, [conteudoId, eventId]);

  // Busca professores
  useEffect(() => {
    async function fetchProfessores() {
      try {
        const res = await api.get('/users/');
        setProfessores(res.data.filter((u: any) => u.role === 'professor'));
      } catch {
        // Ignorar erro de professores
      }
    }
    fetchProfessores();
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm({ ...form, [e.target.name]: e.target.value ?? "" });
  }

  function handleNumberChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm({ ...form, [e.target.name]: Number(e.target.value) ?? 0 });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!form.nome_conteudo.trim() || !form.area_conhecimento.trim() ||
        !form.turno.trim() || !form.nivel.trim() || form.quantidade < 0 ||
        !form.professor_id) {
      setError("Preencha todos os campos obrigatórios.");
      return;
    }
    try {
        const payload = {
            ...form,
            tenant_id: user?.tenant_id,
            evento_id: eventId,
            professor_id: form.professor_id ? String(form.professor_id) : null, // <-- ALTERE AQUI!
            quantidade: form.quantidade ? Number(form.quantidade) : 0,
            respondidas: form.respondidas ? Number(form.respondidas) : 0,
        };
        await api.put(`/conteudos/${conteudoId}`, payload);
      setSnackbar({ open: true, message: "Conteúdo atualizado!", severity: "success" });
      setTimeout(() => navigate(`/eventos/${eventId}/conteudo`), 1200);
    } catch (err: any) {
      setSnackbar({
        open: true,
        message: "Falha ao atualizar conteúdo",
        severity: "error",
      });
    }
  }

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
          <Typography variant="h5" fontWeight="bold">Editar Conteúdo</Typography>
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
              startIcon={<SaveIcon />}
              onClick={handleSubmit}
            >
              Salvar Alterações
            </Button>
          </Box>
        </Box>
        <Divider sx={{ mb: 2 }} />
        <Box component="form" onSubmit={handleSubmit} autoComplete="off">
          <TextField
            label="Nome do Conteúdo"
            name="nome_conteudo"
            value={form.nome_conteudo ?? ""}
            onChange={handleChange}
            fullWidth required sx={{ mb: 2 }}
          />
          <TextField
            label="Descrição"
            name="descricao"
            value={form.descricao ?? ""}
            onChange={handleChange}
            fullWidth multiline rows={2} sx={{ mb: 2 }}
          />
          <TextField
            label="Área de Conhecimento"
            name="area_conhecimento"
            value={form.area_conhecimento ?? ""}
            onChange={handleChange}
            fullWidth required sx={{ mb: 2 }}
          />
          <TextField
            select
            label="Turno"
            name="turno"
            value={form.turno ?? ""}
            onChange={handleChange}
            fullWidth required sx={{ mb: 2 }}
          >{TURNO_OPTS.map(opt => <MenuItem key={opt} value={opt}>{opt}</MenuItem>)}</TextField>
          <TextField
            select
            label="Nível"
            name="nivel"
            value={form.nivel ?? ""}
            onChange={handleChange}
            fullWidth required sx={{ mb: 2 }}
          >{NIVEL_OPTS.map(opt => <MenuItem key={opt} value={opt}>{opt}</MenuItem>)}</TextField>
          <TextField
            label="Quantidade de questões"
            name="quantidade"
            type="number"
            value={form.quantidade ?? 0}
            onChange={handleNumberChange}
            fullWidth required sx={{ mb: 2 }}
            inputProps={{ min: 0 }}
          />
          <TextField
            label="Respondidas"
            name="respondidas"
            type="number"
            value={form.respondidas ?? 0}
            onChange={handleNumberChange}
            fullWidth sx={{ mb: 2 }}
            inputProps={{ min: 0, max: form.quantidade ?? 0 }}
          />
          <TextField
            select
            label="Professor Responsável"
            name="professor_id"
            value={form.professor_id ?? ""}
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