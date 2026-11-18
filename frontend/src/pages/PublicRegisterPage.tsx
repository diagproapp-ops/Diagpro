import React, { useState, ChangeEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Box, TextField, Button, Typography, Alert, Checkbox, FormControlLabel, MenuItem, Paper, Stack, Avatar
} from '@mui/material';
import PhotoCamera from '@mui/icons-material/PhotoCamera';
// Importe seu logo se tiver. Exemplo: import DiagProLogo from '../assets/diagpro_logo.png';
import api from '../api';

type PublicUserForm = {
  username: string;
  email: string;
  password: string;
  full_name: string;
  cpf: string;
  phone: string;
  department: string;
  institution: string;
  birth_date: string;
  notes: string;
  address: string;
  avatar_file: File | null;
  specialty: string;
  pix_key: string;
  banco: string;
  agencia: string;
  conta_corrente: string;
  role: string;
  tenant_id: string;
  accepted_confidentiality: boolean;
  accepted_data_leak: boolean;
  accepted_legitimidade?: boolean; // NOVO CAMPO
};

const ROLES = [
  { value: 'professor', label: 'Professor' },
  { value: 'revisor', label: 'Revisor' },
  { value: 'diagramador', label: 'Diagramador' }
];

const initialForm: PublicUserForm = {
  username: "",
  email: "",
  password: "",
  full_name: "",
  cpf: "",
  phone: "",
  department: "",
  institution: "",
  birth_date: "",
  notes: "",
  address: "",
  avatar_file: null,
  specialty: "",
  pix_key: "",
  banco: "",
  agencia: "",
  conta_corrente: "",
  role: "professor",
  tenant_id: "",
  accepted_confidentiality: false,
  accepted_data_leak: false,
  accepted_legitimidade: false, // NOVO CAMPO
};

export default function PublicRegisterPage() {
  const [searchParams] = useSearchParams();
  const tenant_id = searchParams.get('tenant_id') || "";

  const [form, setForm] = useState<PublicUserForm>({ ...initialForm, tenant_id });
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Estados para liberar checkboxes
  const [confidencialidadeLido, setConfidencialidadeLido] = useState(false);
  const [vazamentoLido, setVazamentoLido] = useState(false);
  const [legitimidadeLido, setLegitimidadeLido] = useState(false); // NOVO

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const { name, value, type, checked, files } = e.target;
    if (type === "checkbox") {
      setForm((f) => ({ ...f, [name]: checked }));
    } else if (type === "file" && files) {
      setForm((f) => ({ ...f, avatar_file: files[0] }));
      setAvatarPreview(URL.createObjectURL(files[0]));
    } else {
      setForm((f) => ({ ...f, [name]: value }));
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSuccess(null); setError(null);

    if (!form.tenant_id) {
      setError("Tenant não identificado. Use o link correto enviado por sua instituição.");
      return;
    }
    if (!form.accepted_confidentiality || !form.accepted_data_leak) {
      setError("É obrigatório aceitar ambos os termos para prosseguir.");
      return;
    }
    // NOVA VALIDAÇÃO: termo de legitimidade só para professor
    if (form.role === "professor" && !form.accepted_legitimidade) {
      setError("É obrigatório aceitar o Termo de Legitimidade e Ineditismo de Questões para professores.");
      return;
    }
    for (const [key, value] of Object.entries(form)) {
      if (
        key !== "avatar_file" &&
        key !== "notes" &&
        typeof value === "string" &&
        value.trim() === ""
      ) {
        setError("Preencha todos os campos obrigatórios.");
        return;
      }
    }
    if (!form.avatar_file) {
      setError("A foto é obrigatória.");
      return;
    }

    const formData = new FormData();
    Object.entries(form).forEach(([key, value]) => {
      if (key === "avatar_file" && value) {
        formData.append("avatar_file", value as File);
      } else if (typeof value !== "object") {
        formData.append(key, String(value));
      }
    });

    try {
      await api.post('/users/register', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSuccess('Cadastro enviado! Aguarde a aprovação do administrador.');
      setForm({ ...initialForm, tenant_id }); // Limpa o formulário!
      setAvatarPreview(null); // Limpa o preview da foto
      setConfidencialidadeLido(false);
      setVazamentoLido(false);
      setLegitimidadeLido(false); // Limpa também o novo termo
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || 'Erro ao enviar cadastro.'
      );
    }
  }

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#f5f6fa', display: 'flex', alignItems: 'center' }}>
      <Paper elevation={4} sx={{ p: { xs: 2, md: 4 }, maxWidth: 520, mx: 'auto', borderRadius: 5 }}>
        {/* LOGO E NOME NO TOPO */}
        <Stack direction="column" alignItems="center" spacing={1} sx={{ mb: 2 }}>
          {/* Substitua pelo seu logo se quiser */}
          <Avatar sx={{ width: 64, height: 64, mb: 1, bgcolor: "#1976d2", fontWeight: "bold" }}>D</Avatar>
          <Typography variant="h4" fontWeight="bold" color="primary">DiagPro</Typography>
        </Stack>
        <Typography color="text.secondary" align="center" gutterBottom>
          Preencha todos os campos obrigatórios para realizar seu cadastro.
        </Typography>
        {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Box component="form" onSubmit={handleSubmit} sx={{ mt: 2 }}>
          {/* Avatar */}
          <Stack direction="column" alignItems="center" spacing={1} sx={{ mb: 2 }}>
            <Avatar
              src={avatarPreview || undefined}
              sx={{ width: 90, height: 90, fontSize: 40, bgcolor: "#e3e3e3" }}
            />
            <Button
              variant="contained"
              component="label"
              color="secondary"
              startIcon={<PhotoCamera />}
              sx={{ borderRadius: 3, fontWeight: 'bold' }}
            >
              Enviar Foto (obrigatório)
              <input
                type="file"
                accept="image/*"
                capture="user"
                style={{ display: 'none' }}
                name="avatar_file"
                onChange={handleChange}
                required
              />
            </Button>
          </Stack>
          <TextField label="Nome Completo" name="full_name" value={form.full_name} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Username" name="username" value={form.username} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Email" name="email" value={form.email} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Senha" name="password" type="password" value={form.password} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="CPF" name="cpf" value={form.cpf} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Telefone" name="phone" value={form.phone} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Departamento" name="department" value={form.department} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Instituição" name="institution" value={form.institution} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Data de Nascimento" name="birth_date" type="date" value={form.birth_date} onChange={handleChange} fullWidth margin="normal" InputLabelProps={{ shrink: true }} required />
          <TextField label="Observações" name="notes" value={form.notes} onChange={handleChange} fullWidth margin="normal" />
          <TextField label="Endereço" name="address" value={form.address} onChange={handleChange} fullWidth margin="normal" required />
          <TextField
            label="Função"
            name="role"
            select
            value={form.role}
            onChange={handleChange}
            fullWidth
            margin="normal"
            required
          >
            {ROLES.map(r => (
              <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>
            ))}
          </TextField>
          <TextField label="Especialidade" name="specialty" value={form.specialty} onChange={handleChange} fullWidth margin="normal" required />
          <TextField label="Chave Pix" name="pix_key" value={form.pix_key} onChange={handleChange} fullWidth margin="normal" required />

          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mt: 2 }}>
            <TextField label="Banco" name="banco" value={form.banco} onChange={handleChange} fullWidth required />
            <TextField label="Agência" name="agencia" value={form.agencia} onChange={handleChange} fullWidth required />
            <TextField label="Conta Corrente" name="conta_corrente" value={form.conta_corrente} onChange={handleChange} fullWidth required />
          </Stack>

          {/* Termos de Confidencialidade e Vazamento */}
          <Box sx={{ mt: 2 }}>
            <Button
              variant="text"
              color="primary"
              onClick={() => setConfidencialidadeLido(true)}
              component="a"
              href="/Termo_Confidencialidade_Plataforma_Provas.pdf"
              target="_blank"
              rel="noopener noreferrer"
            >
              Ler Termo de Confidencialidade
            </Button>
            <FormControlLabel
              control={
                <Checkbox
                  name="accepted_confidentiality"
                  checked={form.accepted_confidentiality}
                  onChange={handleChange}
                  disabled={!confidencialidadeLido}
                />
              }
              label="Li e aceito o Termo de Confidencialidade"
            />
          </Box>

          <Box>
            <Button
              variant="text"
              color="primary"
              onClick={() => setVazamentoLido(true)}
              component="a"
              href="/Termo_Responsabilidade_Ciencia_Vazamento_Dados_LGPD.pdf"
              target="_blank"
              rel="noopener noreferrer"
            >
              Ler Documento de Vazamento de Dados
            </Button>
            <FormControlLabel
              control={
                <Checkbox
                  name="accepted_data_leak"
                  checked={form.accepted_data_leak}
                  onChange={handleChange}
                  disabled={!vazamentoLido}
                />
              }
              label="Li e aceito o Documento de Vazamento de Dados"
            />
          </Box>

          {/* NOVO TERMO - só para professor */}
          {form.role === "professor" && (
            <Box>
              <Button
                variant="text"
                color="primary"
                onClick={() => setLegitimidadeLido(true)}
                component="a"
                href="/termo_legitimidade_ineditismo_eletronico.pdf"
                target="_blank"
                rel="noopener noreferrer"
              >
                Ler Termo de Legitimidade e Ineditismo de Questões
              </Button>
              <FormControlLabel
                control={
                  <Checkbox
                    name="accepted_legitimidade"
                    checked={form.accepted_legitimidade || false}
                    onChange={handleChange}
                    disabled={!legitimidadeLido}
                  />
                }
                label="Li e aceito o Termo de Legitimidade e Ineditismo de Questões"
              />
            </Box>
          )}

          <Button type="submit" variant="contained" color="primary" fullWidth sx={{ mt: 3, fontWeight: 'bold', borderRadius: 3 }}>
            Cadastrar
          </Button>
        </Box>
      </Paper>
    </Box>
  );
}