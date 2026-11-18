import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Button, Table, TableHead, TableRow, TableCell,
  TableBody, Dialog, TextField, Stack, MenuItem, Chip, Tooltip, Checkbox
} from '@mui/material';
import api from '../api';

interface ClientDashboard {
  id: number;
  name: string;
  domain: string;
  status: string;
  tenant_type: string;
  created_at?: string;
  responsible_name?: string;
  responsible_email?: string;
  responsible_phone?: string;
  plan_type?: string;
  plan_expires_at?: string;
  users_total: number;
  users_by_role: { [role: string]: number };
  questions_total: number;
  exams_total: number;
  events_total: number;
  cargos_total: number;
  frases_total: number;
  admins_total: number;
  blocked_users_total: number;
  accesses_total_month: number;
  last_access?: string;
  percent_users_active: number;
  percent_users_inactive: number;
  avg_questions_per_exam: number;
  avg_access_time_per_user: number;
  recent_activities: { type: string; user: string; timestamp: string }[];
}

export default function AdminClientsTab() {
  const [clients, setClients] = useState<ClientDashboard[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: '',
    domain: '',
    status: 'ativo',
    responsible_name: '',
    responsible_email: '',
    responsible_phone: '',
    plan_type: '',
    plan_expires_at: '',
    tenant_type: 'empresa_concurso',
  });
  const [selected, setSelected] = useState<number[]>([]);
  const [logOpen, setLogOpen] = useState(false);
  const [selectedLogs, setSelectedLogs] = useState<{ type: string; user: string; timestamp: string }[]>([]);
  const [logsClientName, setLogsClientName] = useState<string>("");

  useEffect(() => {
    api.get('/admin/clients/dashboard').then(res => setClients(res.data));
  }, [open]);

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  function handleSave() {
    if (selected.length === 1) {
      api.put(`/admin/clients/${selected[0]}`, form).then(() => {
        setOpen(false);
        setSelected([]);
      });
    } else {
      api.post('/admin/clients', form).then(() => setOpen(false));
    }
  }

  function handleSelect(id: number) {
    setSelected(selected =>
      selected.includes(id)
        ? selected.filter(sel => sel !== id)
        : [...selected, id]
    );
  }

  function handleSelectAll(event: React.ChangeEvent<HTMLInputElement>) {
    setSelected(event.target.checked ? clients.map(c => c.id) : []);
  }

  function handleEdit() {
    if (selected.length === 1) {
      const clientToEdit = clients.find(c => c.id === selected[0]);
      if (clientToEdit) {
        setForm({
          name: clientToEdit.name || '',
          domain: clientToEdit.domain || '',
          status: clientToEdit.status || 'ativo',
          responsible_name: clientToEdit.responsible_name || '',
          responsible_email: clientToEdit.responsible_email || '',
          responsible_phone: clientToEdit.responsible_phone || '',
          plan_type: clientToEdit.plan_type || '',
          plan_expires_at: clientToEdit.plan_expires_at || '',
          tenant_type: clientToEdit.tenant_type || 'empresa_concurso',
        });
        setOpen(true);
      }
    } else if (selected.length > 1) {
      alert('Só é possível editar um cliente por vez.');
    }
  }

  async function handleCreateAdmin() {
    for (const clientId of selected) {
      await api.post(`/admin/clients/${clientId}/create-admin`);
    }
    alert('Admin(s) criado(s)!');
    setSelected([]);
  }

  async function handleBlock() {
    for (const clientId of selected) {
      await api.post(`/admin/clients/${clientId}/block`);
    }
    alert('Cliente(s) bloqueado(s)!');
    setSelected([]);
  }

  async function handleShowLogs(client: ClientDashboard) {
    // Exemplo: buscar os logs completos do cliente no backend
    try {
      const res = await api.get(`/admin/clients/${client.id}/logs`);
      setSelectedLogs(res.data); // espera um array de logs detalhados
    } catch {
      // fallback: mostra todos disponíveis localmente
      setSelectedLogs(client.recent_activities);
    }
    setLogsClientName(client.name);
    setLogOpen(true);
  }

  return (
    <Box sx={{ color: '#222', background: '#fff', minHeight: '100vh' }}>
      <Typography variant="h6" gutterBottom sx={{ color: '#222' }}>Painel de Clientes</Typography>

      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <Button
          variant="contained"
          color="primary"
          sx={{ color: '#222' }}
          disabled={selected.length === 0}
          onClick={handleEdit}
        >
          EDITAR
        </Button>
        <Button
          variant="contained"
          color="secondary"
          sx={{ color: '#222', backgroundColor: '#b39ddb', '&:hover': { backgroundColor: '#9575cd' } }}
          disabled={selected.length === 0}
          onClick={handleCreateAdmin}
        >
          CRIAR ADMIN
        </Button>
        <Button
          variant="contained"
          color="error"
          sx={{ color: '#222', backgroundColor: '#ef5350', '&:hover': { backgroundColor: '#e53935' } }}
          disabled={selected.length === 0}
          onClick={handleBlock}
        >
          BLOQUEAR
        </Button>
        <Button
          variant="contained"
          sx={{
            color: '#222',
            backgroundColor: '#e0e0e0',
            '&:hover': { backgroundColor: '#bdbdbd' }
          }}
          onClick={() => {
            setForm({
              name: '',
              domain: '',
              status: 'ativo',
              responsible_name: '',
              responsible_email: '',
              responsible_phone: '',
              plan_type: '',
              plan_expires_at: '',
              tenant_type: 'empresa_concurso',
            });
            setOpen(true);
          }}
        >
          NOVO CLIENTE
        </Button>
      </Stack>

      <Table size="small" sx={{ mt: 2 }}>
        <TableHead>
          <TableRow>
            <TableCell padding="checkbox" align="center">
              <Checkbox
                indeterminate={selected.length > 0 && selected.length < clients.length}
                checked={clients.length > 0 && selected.length === clients.length}
                onChange={handleSelectAll}
                color="primary"
                sx={{
                  border: '1.5px solid #1976d2',
                  borderRadius: '4px',
                  backgroundColor: 'transparent',
                  boxSizing: 'border-box',
                  p: 0.5,
                  '&.Mui-checked': {
                    border: '1.5px solid #1976d2',
                    backgroundColor: 'transparent',
                  }
                }}
              />
            </TableCell>
            <TableCell sx={{ color: "#222" }}>Nome</TableCell>
            <TableCell sx={{ color: "#222" }}>Domínio</TableCell>
            <TableCell sx={{ color: "#222" }}>Status</TableCell>
            <TableCell sx={{ color: "#222" }}>Tipo</TableCell>
            <TableCell sx={{ color: "#222" }}>Responsável</TableCell>
            <TableCell sx={{ color: "#222" }}>Plano</TableCell>
            <TableCell sx={{ color: "#222" }}>Usuários</TableCell>
            <TableCell sx={{ color: "#222" }}>Admins</TableCell>
            <TableCell sx={{ color: "#222" }}>Bloqueados</TableCell>
            <TableCell sx={{ color: "#222" }}>Ativos (%)</TableCell>
            <TableCell sx={{ color: "#222" }}>Questões</TableCell>
            <TableCell sx={{ color: "#222" }}>Provas</TableCell>
            <TableCell sx={{ color: "#222" }}>Eventos</TableCell>
            <TableCell sx={{ color: "#222" }}>Acessos (mês)</TableCell>
            <TableCell sx={{ color: "#222" }}>Último acesso</TableCell>
            <TableCell sx={{ color: "#222" }}>Recentes</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {clients.map(client => (
            <TableRow key={client.id}>
              <TableCell padding="checkbox" align="center">
                <Checkbox
                  checked={selected.includes(client.id)}
                  onChange={() => handleSelect(client.id)}
                  color="primary"
                  sx={{
                    border: '1.5px solid #1976d2',
                    borderRadius: '4px',
                    backgroundColor: 'transparent',
                    boxSizing: 'border-box',
                    p: 0.5,
                    '&.Mui-checked': {
                      border: '1.5px solid #1976d2',
                      backgroundColor: 'transparent',
                    }
                  }}
                />
              </TableCell>
              <TableCell sx={{ color: '#222' }}>{client.name}</TableCell>
              <TableCell sx={{ color: '#222' }}>{client.domain}</TableCell>
              <TableCell>
                <Chip
                  label={client.status}
                  color={client.status === 'ativo' ? 'success' : client.status === 'bloqueado' ? 'error' : 'default'}
                />
              </TableCell>
              <TableCell sx={{ color: "#222" }}>
                {client.tenant_type === 'escola' ? 'Escola' : 'Empresa/Banca'}
              </TableCell>
              <TableCell>
                <Tooltip title={client.responsible_email || ''}>
                  <span style={{ color: '#222' }}>{client.responsible_name}</span>
                </Tooltip>
              </TableCell>
              <TableCell sx={{ color: '#222' }}>
                {client.plan_type} {client.plan_expires_at && (<span>até {new Date(client.plan_expires_at).toLocaleDateString()}</span>)}
              </TableCell>
              <TableCell sx={{ color: '#222' }}>
                {client.users_total}
                <br />
                <small>
                  {Object.entries(client.users_by_role).map(([role, num]) => (
                    <span key={role}>{role}: {num} </span>
                  ))}
                </small>
              </TableCell>
              <TableCell sx={{ color: '#222' }}>{client.admins_total}</TableCell>
              <TableCell sx={{ color: '#222' }}>{client.blocked_users_total}</TableCell>
              <TableCell sx={{ color: '#222' }}>{client.percent_users_active.toFixed(1)}%</TableCell>
              <TableCell sx={{ color: '#222' }}>{client.questions_total}</TableCell>
              <TableCell sx={{ color: '#222' }}>
                {client.exams_total}
                <br />
                <small>Q/Prova: {client.avg_questions_per_exam.toFixed(1)}</small>
              </TableCell>
              <TableCell sx={{ color: '#222' }}>{client.events_total}</TableCell>
              <TableCell sx={{ color: '#222' }}>{client.accesses_total_month}</TableCell>
              <TableCell sx={{ color: '#222' }}>{client.last_access && new Date(client.last_access).toLocaleString()}</TableCell>
              <TableCell>
                <ul style={{ paddingLeft: 12, color: '#222', margin: 0 }}>
                  {client.recent_activities.slice(0, 3).map((act, idx) => (
                    <li key={idx}>
                      {act.type} - {act.user} - {new Date(act.timestamp).toLocaleString()}
                    </li>
                  ))}
                </ul>
                {client.recent_activities.length > 3 || client.id ? (
                  <Button
                    size="small"
                    variant="outlined"
                    sx={{ mt: 1 }}
                    onClick={() => handleShowLogs(client)}
                  >
                    Ver todos os logs
                  </Button>
                ) : null}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Modal: Novo/Editar Cliente */}
      <Dialog open={open} onClose={() => setOpen(false)}>
        <Box sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom sx={{ color: '#222' }}>
            {selected.length === 1 ? 'Editar Cliente' : 'Novo Cliente'}
          </Typography>
          <Stack spacing={2}>
            <TextField label="Nome" name="name" value={form.name} onChange={handleChange} variant="outlined" />
            <TextField label="Domínio" name="domain" value={form.domain} onChange={handleChange} helperText="Ex: minhabanca" variant="outlined" />
            <TextField
              label="Status"
              name="status"
              value={form.status}
              onChange={handleChange}
              select
              variant="outlined"
              sx={{
                '& .MuiOutlinedInput-root': {
                  '& fieldset': {
                    borderColor: '#1976d2',
                    borderWidth: 2,
                  },
                  '&:hover fieldset': {
                    borderColor: '#1565c0',
                  },
                  '&.Mui-focused fieldset': {
                    borderColor: '#388e3c',
                  },
                },
              }}
            >
              <MenuItem value="ativo">Ativo</MenuItem>
              <MenuItem value="inativo">Inativo</MenuItem>
              <MenuItem value="bloqueado">Bloqueado</MenuItem>
            </TextField>
            <TextField
              label="Tipo de Cliente"
              name="tenant_type"
              value={form.tenant_type}
              onChange={handleChange}
              select
              variant="outlined"
            >
              <MenuItem value="empresa_concurso">Empresa de Concurso/Banca</MenuItem>
              <MenuItem value="escola">Escola</MenuItem>
            </TextField>
            <TextField label="Responsável" name="responsible_name" value={form.responsible_name} onChange={handleChange} variant="outlined" />
            <TextField label="Email Resp." name="responsible_email" value={form.responsible_email} onChange={handleChange} variant="outlined" />
            <TextField label="Telefone Resp." name="responsible_phone" value={form.responsible_phone} onChange={handleChange} variant="outlined" />
            <TextField label="Plano" name="plan_type" value={form.plan_type} onChange={handleChange} variant="outlined" />
            <TextField label="Expira em" name="plan_expires_at" value={form.plan_expires_at} onChange={handleChange} type="date" InputLabelProps={{ shrink: true }} variant="outlined" />
            <Button variant="contained" onClick={handleSave}>Salvar</Button>
          </Stack>
        </Box>
      </Dialog>

      {/* Modal: Logs detalhados */}
      <Dialog open={logOpen} onClose={() => setLogOpen(false)} maxWidth="md" fullWidth>
        <Box sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            Logs detalhados {logsClientName ? `de ${logsClientName}` : ''}
          </Typography>
          {selectedLogs && selectedLogs.length > 0 ? (
            <ul style={{ color: "#333", paddingLeft: 20 }}>
              {selectedLogs.map((log, idx) => (
                <li key={idx}>
                  <b>{log.type}</b> - {log.user} - {new Date(log.timestamp).toLocaleString()}
                </li>
              ))}
            </ul>
          ) : (
            <Typography color="text.secondary">Nenhum log encontrado.</Typography>
          )}
          <Button variant="contained" sx={{ mt: 2 }} onClick={() => setLogOpen(false)}>Fechar</Button>
        </Box>
      </Dialog>
    </Box>
  );
}