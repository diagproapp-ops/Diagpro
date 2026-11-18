// src/contexts/AuthContext.tsx
import React, { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import api from '../api';
import { User as UserType } from '../types';

interface AuthContextType {
  isAuthenticated: boolean;
  user: UserType | null;
  loading: boolean;
  login: (username: string, password: string, recaptchaToken: string) => Promise<void>;
  logout: () => void;
}

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

  const login = async (username: string, password: string, recaptchaToken: string) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    formData.append('recaptcha_token', recaptchaToken);
    const response = await api.post('/auth/login', formData);
    const { access_token, role, tenant_id } = response.data; // <-- Corrigido aqui!
    localStorage.setItem('authToken', access_token);
    api.defaults.headers.Authorization = `Bearer ${access_token}`;
    localStorage.setItem('userRole', role);
    localStorage.setItem('tenantId', String(tenant_id ?? '')); // <-- Corrigido aqui!
    const { data } = await api.get<UserType>('/users/me');
    setUser(data);
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('tenantId');
    delete api.defaults.headers.Authorization;
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!user, user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) { throw new Error('useAuth deve ser usado dentro de um AuthProvider'); }
  return context;
};