// src/contexts/AuthContext.tsx
import React, { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import api, { CLIENTE_EM_GESTAO_KEY } from '../api';
import { User as UserType } from '../types';

interface AuthContextType {
  isAuthenticated: boolean;
  user: UserType | null;
  loading: boolean;
  login: (username: string, password: string, recaptchaToken: string) => Promise<ResultadoLogin>;
  concluirLogin: (dados: { access_token: string; role?: string; tenant_id?: number | null }) => Promise<void>;
  logout: () => void;
}

// Senha certa não libera acesso: o servidor pede o segundo fator (2FA obrigatório para todos).
export type ResultadoLogin =
  | { etapa: 'ok' }
  | { etapa: '2fa' | 'cadastro_2fa'; token_2fa: string };

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('authToken');
      if (token) {
        api.defaults.headers.Authorization = `Bearer ${token}`;
        try {
          const { data } = await api.get<UserType>('/users/me');
          setUser(data);
          if (data.role) localStorage.setItem('userRole', data.role);
          if ('tenant_id' in data) localStorage.setItem('tenantId', String(data.tenant_id ?? ''));
        } catch (error) {
          setUser(null);
          localStorage.removeItem('authToken');
          localStorage.removeItem('userRole');
          localStorage.removeItem('tenantId');
        }
      }
      setLoading(false);
    };
    checkAuth();
  }, []);

  const login = async (username: string, password: string, recaptchaToken: string): Promise<ResultadoLogin> => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    formData.append('recaptcha_token', recaptchaToken);
    const response = await api.post('/auth/login', formData);
    if (response.data?.etapa === '2fa' || response.data?.etapa === 'cadastro_2fa') {
      return { etapa: response.data.etapa, token_2fa: response.data.token_2fa };
    }
    await concluirLogin(response.data);
    return { etapa: 'ok' };
  };

  // Chamado depois do 2FA: grava o token de acesso e carrega o usuário
  const concluirLogin = async (dados: { access_token: string; role?: string; tenant_id?: number | null }) => {
    const { access_token, role, tenant_id } = dados;
    localStorage.removeItem(CLIENTE_EM_GESTAO_KEY); // todo login começa na visão global
    localStorage.setItem('authToken', access_token);
    api.defaults.headers.Authorization = `Bearer ${access_token}`;
    if (role) localStorage.setItem('userRole', role);
    localStorage.setItem('tenantId', String(tenant_id ?? '')); // <-- Corrigido aqui!
    const { data } = await api.get<UserType>('/users/me');
    if (data.role) localStorage.setItem('userRole', data.role);
    setUser(data);
  };

  // Sessão: X min sem uso encerra (Configurações: plataforma/banca); com uso, renova sozinha
  // (limite máximo de horas decidido pelo servidor)
  const [inatividadeMin, setInatividadeMin] = useState(30);
  useEffect(() => {
    if (!user) return;
    api.get('/config/sessao').then(({ data }) => {
      if (data?.inatividade_minutos) setInatividadeMin(Number(data.inatividade_minutos));
    }).catch(() => {});
  }, [user]);
  useEffect(() => {
    if (!user) return;
    const INATIVIDADE_MS = inatividadeMin * 60 * 1000;
    const RENOVAR_ANTES_MS = Math.min(10, Math.max(2, Math.floor(inatividadeMin / 3))) * 60 * 1000;
    let ultimaAtividade = Date.now();
    const marcar = () => { ultimaAtividade = Date.now(); };
    const eventos = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'];
    eventos.forEach(ev => window.addEventListener(ev, marcar, { passive: true }));
    const expiraEm = () => {
      try {
        const t = localStorage.getItem('authToken') || '';
        const p = JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
        return Number(p.exp) * 1000;
      } catch { return 0; }
    };
    const encerrar = (motivo: string) => {
      logout();
      window.location.assign(`/login?sessao=${motivo}`);
    };
    const verificar = async () => {
      const agora = Date.now();
      if (agora - ultimaAtividade > INATIVIDADE_MS) { encerrar('inatividade'); return; }
      const exp = expiraEm();
      if (!exp || exp <= agora) { encerrar('expirada'); return; }
      if (exp - agora < RENOVAR_ANTES_MS) {
        try {
          const { data } = await api.post('/auth/renovar');
          localStorage.setItem('authToken', data.access_token);
          api.defaults.headers.Authorization = `Bearer ${data.access_token}`;
        } catch { encerrar('expirada'); }
      }
    };
    const id = window.setInterval(verificar, 60 * 1000);
    return () => {
      window.clearInterval(id);
      eventos.forEach(ev => window.removeEventListener(ev, marcar));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, inatividadeMin]);

  const logout = () => {
    // encerra o acesso no servidor também (o token deixa de valer mesmo que tenha sido copiado)
    // (o token vai explícito: o interceptor roda depois que o localStorage já foi limpo)
    const tokenAtual = localStorage.getItem('authToken');
    if (tokenAtual) api.post('/auth/sair', {}, { headers: { Authorization: `Bearer ${tokenAtual}` } }).catch(() => {});
    setUser(null);
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('tenantId');
    localStorage.removeItem(CLIENTE_EM_GESTAO_KEY);
    delete api.defaults.headers.Authorization;
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!user, user, loading, login, concluirLogin, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) { throw new Error('useAuth deve ser usado dentro de um AuthProvider'); }
  return context;
};