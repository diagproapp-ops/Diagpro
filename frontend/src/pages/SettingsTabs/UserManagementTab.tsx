import React, { useEffect, useState } from 'react';
import {
  Box, Button, Typography, Table, TableBody, TableCell, TableHead, TableRow, Paper, Stack, Alert,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField, MenuItem, IconButton, TableContainer
} from '@mui/material';
import { Edit, Delete } from '@mui/icons-material';
import api from '../../api';
import { Switch } from '@mui/material';
import { useAuth } from '../../contexts/AuthContext';

type UserForm = {
  id?: number;
  username: string;
  email: string;
  password?: string;
  full_name?: string;
  cpf?: string;
  phone?: string;
  department?: string;
  institution?: string;
  birth_date?: string;
  status?: string;
  notes?: string;
  address?: string;
  avatar_url?: string;
  specialty?: string;
  permissions?: string;
  pix_key?: string;
  bank_data?: string;
  role: string;
  tenant_id?: number;
};

const ROLES = [
  { value: 'administrador geral', label: 'Administrador Geral' },
  { value: 'administrador', label: 'Administrador' },
  { value: 'professor', label: 'Professor' },
  { value: 'revisor', label: 'Revisor' },
  { value: 'diagramador', label: 'Diagramador' },
];

const initialForm: UserForm = {
  username: "",
  email: "",
  password: "",
  full_name: "",
  cpf: "",
  phone: "",
  department: "",
  institution: "",
  birth_date: "",
  status: "",
  notes: "",
  address: "",
  avatar_url: "",
  specialty: "",
  permissions: "",
  pix_key: "",
  bank_data: "",
  role: "administrador"
};

export default function UserManagementTab() {
  const [users, setUsers] = useState<UserForm[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [form, setForm] = useState<UserForm>(initialForm);
  const [editUser, setEditUser] = useState<UserForm | null>(null);
  const token = localStorage.getItem('authToken');
  const [open, setOpen] = useState(false);
  const { user } = useAuth(); // <-- ALTERAÇÃO: pega o usuário do contexto

  useEffect(() => {
    setLoading(true);
    api.get('/users/', {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(res => setUsers(res.data))
      .catch(err => setError(
        typeof err?.response?.data?.detail === "string"
          ? err?.response?.data?.detail
          : "Falha ao buscar usuários."
      ))
      .finally(() => setLoading(false));
  }, [message, token, open]);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMessage(null);
    setError(null);

    let payload: UserForm = { ...form };

    // ALTERADO: tenant_id vem do contexto!
    if (user && typeof user.tenant_id !== "undefined") {
      payload.tenant_id = Number(user.tenant_id);
    } else {
      setError("Tenant ID não encontrado! Faça login novamente.");
      return;
    }

    if (editUser) {
      if (!payload.password) {
        const { password, ...rest } = payload;
        payload = rest;
      }
    }

    const url = editUser ? `/users/${editUser.id}` : '/users/';
    const method = editUser ? api.patch : api.post;

    method(url, payload, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => {
        setMessage(editUser ? 'Usuário editado com sucesso!' : 'Usuário criado com sucesso!');
        setForm(initialForm);
        setEditUser(null);
        setOpen(false);
      })
      .catch(err => {
        let detail = 'Erro ao salvar usuário.';
        if (err?.response?.data?.detail) {
          if (typeof err.response.data.detail === 'string') {
            detail = err.response.data.detail;
          } else if (Array.isArray(err.response.data.detail)) {
            detail = err.response.data.detail.map(
              (e: any) => `${e.loc?.join('.') || ''}: ${e.msg}`
            ).join('; ');
          } else if (err.response.data.detail.msg) {
            detail = err.response.data.detail.msg;
          } else {
            detail = JSON.stringify(err.response.data.detail);
          }
        }
        setError(detail);
      });
  }

  function handleEdit(user: UserForm) {
    setForm({ ...user, password: "" });
    setEditUser(user);
    setOpen(true);
  }

  function handleDelete(id?: number) {
    if (!id) return;
    if (window.confirm("Tem certeza que deseja excluir este usuário?")) {
      api.delete(`/users/${id}`, { headers: { Authorization: `Bearer ${token}` } })
        .then(() => setMessage('Usuário excluído com sucesso!'))
        .catch(err => setError(
          typeof err?.response?.data?.detail === "string"
            ? err?.response?.data?.detail
            : "Erro ao excluir usuário."
        ));
    }
  }

  function handleCreate() {
    setForm(initialForm);
    setEditUser(null);
    setOpen(true);
  }

  function handleToggleStatus(user: UserForm) {
    const newStatus = user.status === "ativo" ? "inativo" : "ativo";
    api.patch(`/users/${user.id}`, { status: newStatus }, { headers: { Authorization: `Bearer ${token}` } })
      .then(() => setMessage(`Usuário ${newStatus === "ativo" ? "ativado" : "desativado"} com sucesso!`))
      .catch(() => setError("Erro ao atualizar status do usuário."));
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Usuários do Sistema</Typography>
      {loading && <Typography>Carregando...</Typography>}
      {error && <Alert severity="error">{error}</Alert>}
      {message && <Alert severity="success">{message}</Alert>}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Status</TableCell>
              <TableCell>Nome Completo</TableCell>
              <TableCell>Username</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Função</TableCell>
              <TableCell>Departamento</TableCell>
              <TableCell>Instituição</TableCell>
              <TableCell>Ações</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.map(u => (
              <TableRow key={u.id}>
                <TableCell>
                  <Switch
                    checked={u.status === "ativo"}
                    onChange={() => handleToggleStatus(u)}
                    color="primary"
                  />
                </TableCell>
                <TableCell>{u.full_name || '-'}</TableCell>
                <TableCell>{u.username}</TableCell>
                <TableCell>{u.email}</TableCell>
                <TableCell>{u.role}</TableCell>
                <TableCell>{u.department || '-'}</TableCell>
                <TableCell>{u.institution || '-'}</TableCell>
                <TableCell>
                  <IconButton onClick={() => handleEdit(u)}><Edit /></IconButton>
                  <IconButton onClick={() => handleDelete(u.id)}><Delete /></IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
        <Button variant="contained" onClick={handleCreate}>Criar Usuário</Button>
        <Button variant="outlined" onClick={() => setForm(initialForm)}>Limpar</Button>
      </Stack>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editUser ? "Editar Usuário" : "Criar Novo Usuário"}</DialogTitle>
        <DialogContent>
          <Box component="form" onSubmit={handleSubmit} sx={{ mt: 1 }}>
            <TextField label="Nome Completo" name="full_name" value={form.full_name || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Username" name="username" value={form.username} onChange={handleChange} fullWidth margin="normal" required />
            <TextField label="Email" name="email" value={form.email} onChange={handleChange} fullWidth margin="normal" required />
            {!editUser && (
              <TextField label="Senha" name="password" type="password" value={form.password} onChange={handleChange} fullWidth margin="normal" required />
            )}
            {editUser && (
              <TextField label="Nova senha (se quiser trocar)" name="password" type="password" value={form.password} onChange={handleChange} fullWidth margin="normal" />
            )}
            <TextField label="Função" name="role" select value={form.role} onChange={handleChange} fullWidth margin="normal" required>
              {ROLES.map(r => (
                <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>
              ))}
            </TextField>
            <TextField label="CPF" name="cpf" value={form.cpf || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Telefone" name="phone" value={form.phone || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Departamento" name="department" value={form.department || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Instituição" name="institution" value={form.institution || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Data de Nascimento" name="birth_date" value={form.birth_date || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Status" name="status" value={form.status || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Observações" name="notes" value={form.notes || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Endereço" name="address" value={form.address || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="URL do Avatar" name="avatar_url" value={form.avatar_url || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Especialidade" name="specialty" value={form.specialty || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Permissões" name="permissions" value={form.permissions || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Chave Pix" name="pix_key" value={form.pix_key || ""} onChange={handleChange} fullWidth margin="normal" />
            <TextField label="Dados Bancários" name="bank_data" value={form.bank_data || ""} onChange={handleChange} fullWidth margin="normal" />
            <DialogActions>
              <Button onClick={() => setOpen(false)}>Cancelar</Button>
              <Button type="submit" variant="contained">{editUser ? "Salvar" : "Criar"}</Button>
            </DialogActions>
          </Box>
        </DialogContent>
      </Dialog>
    </Box>
  );
}