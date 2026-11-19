import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Stack,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import TuneIcon from '@mui/icons-material/Tune';
import SpeedIcon from '@mui/icons-material/Speed';
import PeopleAltOutlinedIcon from '@mui/icons-material/PeopleAltOutlined';
import BusinessOutlinedIcon from '@mui/icons-material/BusinessOutlined';
import PaletteOutlinedIcon from '@mui/icons-material/PaletteOutlined';
import FormatQuoteOutlinedIcon from '@mui/icons-material/FormatQuoteOutlined';
import HubOutlinedIcon from '@mui/icons-material/HubOutlined';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import UserManagementTab from './SettingsTabs/UserManagementTab';
import AppearanceTab from './SettingsTabs/AppearanceTab';
import CompanyDataTab from './SettingsTabs/CompanyDataTab';
import PhraseBankTab from './SettingsTabs/PhraseBankTab';
import AuditTab from './SettingsTabs/AuditTab';
import AdminClientsTab from './AdminClientsTab';
import PlataformaSegurancaTab from './SettingsTabs/PlataformaSegurancaTab';
import BancaConfigTab from './SettingsTabs/BancaConfigTab';
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined';
import LockClockOutlinedIcon from '@mui/icons-material/LockClockOutlined';
import ArticleOutlinedIcon from '@mui/icons-material/ArticleOutlined';
import RuleOutlinedIcon from '@mui/icons-material/RuleOutlined';
import Layout from '../components/Layout';
import { useAuth } from '../contexts/AuthContext';
import api from '../api';

type SectionKey =
  | 'overview'
  | 'users'
  | 'clients'
  | 'company'
  | 'appearance'
  | 'phrases'
  | 'audit'
  | 'plataforma_seguranca'
  | 'banca_seguranca'
  | 'banca_identidade'
  | 'banca_regras';

function SettingsPage() {
  const { user } = useAuth();
  const isAdminGeral = user?.role === 'administrador geral';

  const [section, setSection] = useState<SectionKey>('overview');
  const [counts, setCounts] = useState({
    users: 0,
    phrases: 0,
    events: 0,
    clients: isAdminGeral ? 2 : 1,
  });

  useEffect(() => {
    async function loadStats() {
      try {
        const [uRes, fRes, eRes] = await Promise.allSettled([
          api.get('/users/'),
          api.get('/frases/'),
          api.get('/eventos/'),
        ]);
        setCounts((prev) => ({
          ...prev,
          users: uRes.status === 'fulfilled' && Array.isArray(uRes.value.data) ? uRes.value.data.length : prev.users,
          phrases: fRes.status === 'fulfilled' && Array.isArray(fRes.value.data) ? fRes.value.data.length : prev.phrases,
          events: eRes.status === 'fulfilled' && Array.isArray(eRes.value.data) ? eRes.value.data.length : prev.events,
        }));
      } catch {
        // fallback silencioso
      }
    }
    loadStats();
  }, []);

  const subNavSx = (active: boolean) => ({
    borderRadius: '10px',
    mb: 0.6,
    px: 1.75,
    py: 1,
    border: active ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid transparent',
    background: active
      ? 'linear-gradient(90deg, rgba(14, 165, 233, 0.18) 0%, rgba(14, 165, 233, 0.03) 100%)'
      : 'transparent',
    color: active ? '#F8FAFC' : '#94A3B8',
    '& .MuiListItemIcon-root': {
      minWidth: 34,
      color: active ? '#38BDF8' : '#64748B',
    },
    '& .MuiListItemText-primary': {
      fontSize: '0.88rem',
      fontWeight: active ? 600 : 500,
    },
    '&:hover': {
      bgcolor: 'rgba(14, 165, 233, 0.1)',
      color: '#F8FAFC',
    },
  });

  const groupTitleSx = {
    px: 1.5,
    pt: 2.25,
    pb: 0.75,
    fontSize: '0.68rem',
    fontWeight: 700,
    letterSpacing: '0.09em',
    textTransform: 'uppercase' as const,
    color: '#475569',
  };

  const modules = [
    {
      key: 'users' as SectionKey,
      group: 'PESSOAS E ACESSO',
      title: 'Usuários e Contas',
      desc: 'Cadastro, aprovação, bloqueio e atribuição dos 5 perfis RBAC da equipe.',
      icon: <PeopleAltOutlinedIcon fontSize="small" />,
      badge: 'Em uso',
    },
    ...(isAdminGeral
      ? [
        {
          key: 'clients' as SectionKey,
          group: 'PESSOAS E ACESSO',
          title: 'Bancas & Clientes (Multi-Tenant)',
          desc: 'Governança de bancas organizadoras, planos, domínios e administradores por tenant.',
          icon: <HubOutlinedIcon fontSize="small" />,
          badge: 'Em uso',
        },
      ]
      : []),
    {
      key: 'company' as SectionKey,
      group: 'PLATAFORMA E IDENTIDADE',
      title: 'Dados da Banca',
      desc: 'Razão social, CNPJ, endereço, contatos oficiais e logotipo usado nos cadernos de prova.',
      icon: <BusinessOutlinedIcon fontSize="small" />,
      badge: 'Em uso',
    },
    {
      key: 'appearance' as SectionKey,
      group: 'PLATAFORMA E IDENTIDADE',
      title: 'Identidade Visual & Tema',
      desc: 'Paleta visual Operan Pro Dark e temas alternativos com aplicação instantânea.',
      icon: <PaletteOutlinedIcon fontSize="small" />,
      badge: 'Em uso',
    },
    {
      key: 'phrases' as SectionKey,
      group: 'OPERAÇÃO & CONCURSOS',
      title: 'Banco de Frases',
      desc: 'Frases motivacionais e de segurança para capas de provas e transcrição grafológica.',
      icon: <FormatQuoteOutlinedIcon fontSize="small" />,
      badge: 'Em uso',
    },
    {
      key: 'banca_seguranca' as SectionKey,
      group: 'BANCA',
      title: 'Segurança da banca',
      desc: 'Tempo de sessão próprio (mais curto que o da plataforma) e 2FA obrigatório.',
      icon: <LockClockOutlinedIcon fontSize="small" />,
      badge: 'Novo',
    },
    {
      key: 'banca_identidade' as SectionKey,
      group: 'BANCA',
      title: 'Identidade da prova',
      desc: 'Instruções impressas por bloco/disciplina e da prova discursiva.',
      icon: <ArticleOutlinedIcon fontSize="small" />,
      badge: 'Novo',
    },
    {
      key: 'banca_regras' as SectionKey,
      group: 'BANCA',
      title: 'Regras das questões',
      desc: 'Tipos de questão usados pela banca e revisão obrigatória para exportar.',
      icon: <RuleOutlinedIcon fontSize="small" />,
      badge: 'Novo',
    },
    ...(isAdminGeral
      ? [{
        key: 'plataforma_seguranca' as SectionKey,
        group: 'PLATAFORMA',
        title: 'Segurança da plataforma',
        desc: 'Política de senha e sessão para todas as bancas.',
        icon: <ShieldOutlinedIcon fontSize="small" />,
        badge: 'Novo',
      }]
      : []),
    {
      key: 'audit' as SectionKey,
      group: 'OPERAÇÃO & CONCURSOS',
      title: 'Auditoria de Geração',
      desc: 'Trilha de auditoria com usuário, evento, cargo, seed, IP e timestamp de geração.',
      icon: <FactCheckOutlinedIcon fontSize="small" />,
      badge: 'Ativo',
    },
  ];

  const kpiCards = [
    { label: 'Módulos de Governança', value: modules.length, sub: `${modules.length} ativos • 0 pendentes`, accent: '#F8FAFC' },
    { label: 'Usuários da Banca', value: counts.users, sub: 'Controle RBAC de 5 níveis ativo', accent: '#F8FAFC' },
    { label: 'Concursos / Eventos', value: counts.events, sub: 'Isolados por tenant via PostgreSQL RLS', accent: '#38BDF8' },
    { label: 'Banco de Frases', value: counts.phrases, sub: 'Prontas para sorteio em capas PDF', accent: '#F8FAFC' },
    { label: 'Perfis de Acesso', value: 5, sub: 'Admin Geral, Admin, Prof, Revisor, Diag', accent: '#F59E0B' },
    { label: 'Camada de Segurança', value: 'RLS', sub: 'AES-256-GCM por cliente + 2FA obrigatório', accent: '#10B981' },
  ];

  return (
    <Layout>
      {/* Page Hero Header (Operan Style) */}
      <Box sx={{ mb: 4 }}>
        <Stack direction="row" spacing={1.75} alignItems="center" sx={{ mb: 1 }}>
          <Box
            sx={{
              width: 40,
              height: 40,
              borderRadius: '11px',
              background: 'linear-gradient(135deg, #0EA5E9 0%, #0284C7 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 16px rgba(14, 165, 233, 0.35)',
            }}
          >
            <TuneIcon sx={{ color: '#FFF', fontSize: 22 }} />
          </Box>
          <Typography variant="h4" sx={{ fontWeight: 800, color: '#F8FAFC' }}>
            Configurações
          </Typography>
        </Stack>
        <Typography sx={{ color: '#94A3B8', maxWidth: 820, fontSize: '0.94rem', lineHeight: 1.6 }}>
          Central de governança da plataforma: gestão de usuários e permissões RBAC, identidade institucional da banca,
          banco de frases, clientes multi-tenant e trilha de auditoria. Toda alteração entra em vigor imediatamente.
        </Typography>
      </Box>

      {/* Two-Column Governance Workspace */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '240px 1fr' },
          gap: 3.5,
          alignItems: 'start',
        }}
      >
        {/* Left Sub-Navigation Rail */}
        <Box
          sx={{
            p: 1.5,
            borderRadius: 3,
            bgcolor: 'rgba(11, 19, 37, 0.7)',
            border: '1px solid rgba(148, 163, 184, 0.12)',
          }}
        >
          <List disablePadding>
            <ListItemButton selected={section === 'overview'} onClick={() => setSection('overview')} sx={subNavSx(section === 'overview')}>
              <ListItemIcon><SpeedIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Visão geral" />
            </ListItemButton>

            <Typography sx={groupTitleSx}>PLATAFORMA E IDENTIDADE</Typography>
            <ListItemButton selected={section === 'company'} onClick={() => setSection('company')} sx={subNavSx(section === 'company')}>
              <ListItemIcon><BusinessOutlinedIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Dados da banca" />
            </ListItemButton>
            <ListItemButton selected={section === 'appearance'} onClick={() => setSection('appearance')} sx={subNavSx(section === 'appearance')}>
              <ListItemIcon><PaletteOutlinedIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Identidade visual" />
            </ListItemButton>

            <Typography sx={groupTitleSx}>PESSOAS E ACESSO</Typography>
            <ListItemButton selected={section === 'users'} onClick={() => setSection('users')} sx={subNavSx(section === 'users')}>
              <ListItemIcon><PeopleAltOutlinedIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Usuários e contas" />
            </ListItemButton>
            {isAdminGeral && (
              <ListItemButton selected={section === 'clients'} onClick={() => setSection('clients')} sx={subNavSx(section === 'clients')}>
                <ListItemIcon><HubOutlinedIcon fontSize="small" /></ListItemIcon>
                <ListItemText primary="Bancas & Clientes" />
              </ListItemButton>
            )}

            <Typography sx={groupTitleSx}>BANCA</Typography>
            <ListItemButton selected={section === 'banca_seguranca'} onClick={() => setSection('banca_seguranca')} sx={subNavSx(section === 'banca_seguranca')}>
              <ListItemIcon><LockClockOutlinedIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Segurança da banca" />
            </ListItemButton>
            <ListItemButton selected={section === 'banca_identidade'} onClick={() => setSection('banca_identidade')} sx={subNavSx(section === 'banca_identidade')}>
              <ListItemIcon><ArticleOutlinedIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Identidade da prova" />
            </ListItemButton>
            <ListItemButton selected={section === 'banca_regras'} onClick={() => setSection('banca_regras')} sx={subNavSx(section === 'banca_regras')}>
              <ListItemIcon><RuleOutlinedIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Regras das questões" />
            </ListItemButton>

            {isAdminGeral && (
              <>
                <Typography sx={groupTitleSx}>PLATAFORMA</Typography>
                <ListItemButton selected={section === 'plataforma_seguranca'} onClick={() => setSection('plataforma_seguranca')} sx={subNavSx(section === 'plataforma_seguranca')}>
                  <ListItemIcon><ShieldOutlinedIcon fontSize="small" /></ListItemIcon>
                  <ListItemText primary="Segurança da plataforma" />
                </ListItemButton>
              </>
            )}

            <Typography sx={groupTitleSx}>OPERAÇÃO & CONCURSOS</Typography>
            <ListItemButton selected={section === 'phrases'} onClick={() => setSection('phrases')} sx={subNavSx(section === 'phrases')}>
              <ListItemIcon><FormatQuoteOutlinedIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Banco de frases" />
            </ListItemButton>
            <ListItemButton selected={section === 'audit'} onClick={() => setSection('audit')} sx={subNavSx(section === 'audit')}>
              <ListItemIcon><FactCheckOutlinedIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="Auditoria" />
            </ListItemButton>
          </List>
        </Box>

        {/* Right Content Area */}
        <Box>
          {section === 'overview' ? (
            <Box>
              {/* Status Line */}
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                <CheckCircleOutlineIcon sx={{ color: '#10B981', fontSize: 19 }} />
                <Typography sx={{ color: '#10B981', fontWeight: 600, fontSize: '0.88rem' }}>
                  Tudo em ordem • Isolamento Multi-Tenant e RBAC ativos
                </Typography>
              </Stack>

              {/* 6 KPI Cards Grid (Operan Style) */}
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' },
                  gap: 2,
                  mb: 3,
                }}
              >
                {kpiCards.map((kpi) => (
                  <Box
                    key={kpi.label}
                    sx={{
                      p: 2.5,
                      borderRadius: 3,
                      bgcolor: '#0B1325',
                      border: '1px solid rgba(56, 189, 248, 0.14)',
                      boxShadow: '0 8px 24px -8px rgba(2, 6, 23, 0.7)',
                    }}
                  >
                    <Typography sx={{ fontSize: '0.78rem', color: '#94A3B8', mb: 1 }}>{kpi.label}</Typography>
                    <Typography sx={{ fontSize: '1.9rem', fontWeight: 800, color: kpi.accent, lineHeight: 1.15, mb: 1 }}>
                      {kpi.value}
                    </Typography>
                    <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>{kpi.sub}</Typography>
                  </Box>
                ))}
              </Box>

              {/* Status Banner */}
              <Box
                sx={{
                  p: 2.5,
                  mb: 3.5,
                  borderRadius: 3,
                  bgcolor: '#0B1325',
                  border: '1px solid rgba(56, 189, 248, 0.14)',
                }}
              >
                <Typography sx={{ fontWeight: 700, fontSize: '0.95rem', color: '#F1F5F9', mb: 0.5 }}>
                  Governança e Segurança em Tempo Real
                </Typography>
                <Typography sx={{ fontSize: '0.84rem', color: '#94A3B8' }}>
                  Banco PostgreSQL com Row-Level Security (RLS) ativo, criptografia Fernet para dados sensíveis e controle RBAC por perfil.
                </Typography>
              </Box>

              {/* Todos os Assuntos Grid */}
              <Typography sx={{ fontWeight: 700, fontSize: '1.05rem', color: '#F8FAFC', mb: 2 }}>
                Todos os assuntos
              </Typography>
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' },
                  gap: 2,
                }}
              >
                {modules.map((mod) => (
                  <Box
                    key={mod.key}
                    onClick={() => setSection(mod.key)}
                    sx={{
                      p: 2.5,
                      borderRadius: 3,
                      bgcolor: '#0B1325',
                      border: '1px solid rgba(56, 189, 248, 0.14)',
                      cursor: 'pointer',
                      transition: 'all 0.18s ease',
                      '&:hover': {
                        borderColor: 'rgba(56, 189, 248, 0.45)',
                        transform: 'translateY(-2px)',
                        boxShadow: '0 12px 28px -8px rgba(14, 165, 233, 0.2)',
                      },
                    }}
                  >
                    <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.25 }}>
                      <Stack direction="row" spacing={1.25} alignItems="center">
                        <Box sx={{ color: '#38BDF8', display: 'flex' }}>{mod.icon}</Box>
                        <Typography sx={{ fontWeight: 700, fontSize: '0.96rem', color: '#F8FAFC' }}>
                          {mod.title}
                        </Typography>
                      </Stack>
                      <Box
                        sx={{
                          px: 1.2,
                          py: 0.25,
                          borderRadius: '999px',
                          bgcolor: 'rgba(16, 185, 129, 0.12)',
                          border: '1px solid rgba(16, 185, 129, 0.35)',
                          color: '#34D399',
                          fontSize: '0.72rem',
                          fontWeight: 700,
                        }}
                      >
                        {mod.badge}
                      </Box>
                    </Stack>
                    <Typography sx={{ fontSize: '0.83rem', color: '#94A3B8', lineHeight: 1.55 }}>
                      {mod.desc}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          ) : (
            <Box
              sx={{
                p: { xs: 2.5, md: 3.5 },
                borderRadius: 3.5,
                bgcolor: '#0B1325',
                border: '1px solid rgba(56, 189, 248, 0.14)',
                boxShadow: '0 16px 40px -12px rgba(2, 6, 23, 0.75)',
              }}
            >
              {section === 'users' && <UserManagementTab />}
              {section === 'clients' && isAdminGeral && <AdminClientsTab />}
              {section === 'company' && <CompanyDataTab />}
              {section === 'appearance' && <AppearanceTab />}
              {section === 'phrases' && <PhraseBankTab />}
              {section === 'audit' && <AuditTab />}
              {section === 'banca_seguranca' && <BancaConfigTab key="seg" secao="seguranca" />}
              {section === 'banca_identidade' && <BancaConfigTab key="ide" secao="identidade" />}
              {section === 'banca_regras' && <BancaConfigTab key="reg" secao="regras" />}
              {section === 'plataforma_seguranca' && isAdminGeral && <PlataformaSegurancaTab />}
            </Box>
          )}
        </Box>
      </Box>
    </Layout>
  );
}

export default SettingsPage;
