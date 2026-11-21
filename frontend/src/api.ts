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
  // uma chamada pode indicar outro cliente explicitamente (ex.: convite no painel de clientes)
  if (clienteEmGestao && localStorage.getItem('userRole') === 'administrador geral' && !config.headers['X-Tenant-Id']) {
    config.headers['X-Tenant-Id'] = clienteEmGestao;
  }
  return config;
});

// Sessão vencida ou recusada pelo servidor: volta ao login (exceto nas próprias telas de login/2FA)
api.interceptors.response.use(
  (resposta) => resposta,
  (erro) => {
    const url = String(erro?.config?.url || '');
    // Limite do plano: vira texto, para qualquer tela mostrar a mensagem (uso, limite e como mudar de plano)
    const det = erro?.response?.data?.detail;
    if (det && typeof det === 'object' && det.codigo === 'limite_plano' && det.mensagem) {
      erro.response.data.detail = det.mensagem;
    }
    // Modo manutenção: a faixa do topo (AvisoManutencao) mostra a mensagem
    if (erro?.response?.status === 503 && erro?.response?.data?.manutencao) {
      window.dispatchEvent(new CustomEvent('diagpro:manutencao', { detail: erro.response.data.detail }));
    }
    if (erro?.response?.status === 401 && localStorage.getItem('authToken') && !url.startsWith('/auth/')) {
      localStorage.removeItem('authToken');
      localStorage.removeItem('userRole');
      localStorage.removeItem('tenantId');
      localStorage.removeItem(CLIENTE_EM_GESTAO_KEY);
      if (!window.location.pathname.startsWith('/login')) window.location.assign('/login?sessao=expirada');
    }
    return Promise.reject(erro);
  }
);

export default api;