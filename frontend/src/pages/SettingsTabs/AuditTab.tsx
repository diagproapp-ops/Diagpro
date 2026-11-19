import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Button, TextField, Select, MenuItem, InputLabel, FormControl, IconButton
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DownloadIcon from '@mui/icons-material/Download';
import api from '../../api';

// Se você só tem um tenant por admin, remova o filtro tenant_id abaixo e garanta backend filtrando pelo usuário autenticado.
// Se há superadmin, inclua o filtro tenant_id na interface e backend.

const fetchAuditLogs = async (filters: any) => {
  // Remove campos vazios ( '', null ou undefined )
  const cleanFilters = Object.fromEntries(
    Object.entries(filters).filter(([_, v]) => v !== '' && v !== null && v !== undefined)
  );
  // cliente da API com o token de login (antes: axios direto, sem token -> 401 e a aba ficava vazia)
  const { data } = await api.get('/admin/logs/geracao/', { params: cleanFilters });
  return Array.isArray(data) ? data : [];
};

const AuditTab: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [selectedLog, setSelectedLog] = useState<any>(null);
  const [filters, setFilters] = useState({
    usuario: '',
    acao: '',
    evento: '',
    cargo: '',
    tenant_id: '' // só mostre se for superadmin!
  });

  // Simule lista de tenants para superadmin
  const [tenantOptions] = useState<{ id: string, nome: string }[]>([
    // Exemplo: { id: 'tenant1', nome: 'Empresa Alpha' }, ...
  ]);

  // Se quiser buscar tenants do backend para superadmin:
  // useEffect(() => {
  //   axios.get('/admin/tenants').then(res => setTenantOptions(res.data));
  // }, []);

  useEffect(() => {
    fetchAuditLogs(filters).then(setLogs).catch(() => setLogs([]));
  }, [filters]);

  const handleExport = () => {
    if (!logs.length) return;
    const csv = [
      Object.keys(logs[0]).join(';'),
      ...logs.map((row) =>
        Object.values(row).map((v) => typeof v === 'string' ? `"${v.replace(/"/g, '""')}"` : v).join(';')
      )
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'audit-log.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Box>
      <Typography variant="h5" fontWeight="bold" gutterBottom>
        Auditoria e Histórico de Geração
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mb: 2 }}>
        {/* Só exiba Tenant se for relevante para o perfil do usuário */}
        {tenantOptions.length > 0 && (
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Tenant</InputLabel>
            <Select
              value={filters.tenant_id}
              label="Tenant"
              onChange={e => setFilters(f => ({ ...f, tenant_id: e.target.value }))}
            >
              <MenuItem value="">Todos</MenuItem>
              {tenantOptions.map(t => (
                <MenuItem key={t.id} value={t.id}>{t.nome}</MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
        <TextField
          label="Usuário"
          value={filters.usuario}
          onChange={e => setFilters(f => ({ ...f, usuario: e.target.value }))}
          size="small"
        />
        <TextField
          label="Evento"
          value={filters.evento}
          onChange={e => setFilters(f => ({ ...f, evento: e.target.value }))}
          size="small"
        />
        <TextField
          label="Cargo"
          value={filters.cargo}
          onChange={e => setFilters(f => ({ ...f, cargo: e.target.value }))}
          size="small"
        />
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Ação</InputLabel>
          <Select
            value={filters.acao}
            label="Ação"
            onChange={e => setFilters(f => ({ ...f, acao: e.target.value }))}
          >
            <MenuItem value="">Todas</MenuItem>
            <MenuItem value="exportacao_provas">Exportação de provas</MenuItem>
            <MenuItem value="exportacao_gabaritos">Exportação de gabaritos</MenuItem>
            <MenuItem value="Definir Geração">Definir Geração</MenuItem>
            <MenuItem value="Exportar">Exportar</MenuItem>
            <MenuItem value="Restaurar">Restaurar</MenuItem>
            {/* ...outras ações conforme seu sistema */}
          </Select>
        </FormControl>
        <Button
          variant="outlined"
          startIcon={<DownloadIcon />}
          onClick={handleExport}
          disabled={logs.length === 0}
        >
          Exportar CSV
        </Button>
      </Box>
      <TableContainer component={Paper} sx={{ maxHeight: 500 }}>
        <Table stickyHeader>
          <TableHead>
            <TableRow>
              {tenantOptions.length > 0 && <TableCell>Tenant</TableCell>}
              <TableCell>Data/Hora</TableCell>
              <TableCell>Usuário</TableCell>
              <TableCell>Evento</TableCell>
              <TableCell>Cargo</TableCell>
              <TableCell>Ação</TableCell>
              <TableCell>Seed</TableCell>
              <TableCell>Detalhes</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {logs.map((log) => (
              <TableRow key={log.id}>
                {tenantOptions.length > 0 && <TableCell>{log.tenant_id}</TableCell>}
                <TableCell>{log.timestamp}</TableCell>
                <TableCell>{log.usuario}</TableCell>
                <TableCell>{log.evento}</TableCell>
                <TableCell>{log.cargo}</TableCell>
                <TableCell>{log.acao}</TableCell>
                <TableCell sx={{ fontFamily: 'monospace' }}>{log.seed?.slice(0, 8)}...</TableCell>
                <TableCell>
                  <IconButton onClick={() => setSelectedLog(log)}><VisibilityIcon /></IconButton>
                </TableCell>
              </TableRow>
            ))}
            {logs.length === 0 && (
              <TableRow>
                <TableCell colSpan={tenantOptions.length > 0 ? 8 : 7} align="center">
                  Nenhum registro encontrado.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      {selectedLog && (
        <Paper sx={{ mt: 3, p: 2 }}>
          <Typography variant="h6">Detalhes do Log</Typography>
          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 14 }}>
            {JSON.stringify(selectedLog, null, 2)}
          </pre>
          <Button onClick={() => setSelectedLog(null)} sx={{ mt: 1 }}>Fechar</Button>
        </Paper>
      )}
    </Box>
  );
};

export default AuditTab;