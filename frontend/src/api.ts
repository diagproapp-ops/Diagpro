// src/api.ts
import axios from 'axios';

export const CLIENTE_EM_GESTAO_KEY = 'clienteEmGestao';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000',
});

api.interceptors.request.use(async (config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Administrador geral: cliente escolhido no seletor do topo. Sem ele, a API usa a visão global.
  // O servidor só aceita este cabeçalho de quem é de fato administrador geral.
  const clienteEmGestao = localStorage.getItem(CLIENTE_EM_GESTAO_KEY);
  if (clienteEmGestao && localStorage.getItem('userRole') === 'administrador geral') {
    config.headers['X-Tenant-Id'] = clienteEmGestao;
  }
  return config;
});

export default api;