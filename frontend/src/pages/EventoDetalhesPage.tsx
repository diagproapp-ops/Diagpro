import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Stack,
} from '@mui/material';
import EventIcon from '@mui/icons-material/Event';
import WorkIcon from '@mui/icons-material/Work';
import SubjectIcon from '@mui/icons-material/Subject';
import AssignmentIcon from '@mui/icons-material/Assignment';
import BuildIcon from '@mui/icons-material/Build';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import RecordVoiceOverIcon from '@mui/icons-material/RecordVoiceOver';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import api from '../api';
import Layout from '../components/Layout';
import { Evento as EventoType, Cargo } from '../types';
import { useAuth } from '../contexts/AuthContext';

function useQuery() {
  return new URLSearchParams(useLocation().search);
}

function EventoDetalhesPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const query = useQuery();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [evento, setEvento] = useState<EventoType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // `senhaDigitada` é o campo; `senha` só muda ao confirmar (Enter/Desbloquear). Antes cada tecla ia para o
  // servidor ("1", "12", "123"...) e as tentativas parciais contavam como senha errada até bloquear (429).
  const [senha, setSenha] = useState<string>(query.get('senha') || '');
  const [senhaDigitada, setSenhaDigitada] = useState<string>(senha);
  const [tentativa, setTentativa] = useState(0);
  const [senhaModalOpen, setSenhaModalOpen] = useState(!senha);
  const [senhaError, setSenhaError] = useState<string | null>(null);

  React.useEffect(() => {
    if (user && user.role === 'professor' && eventId) {
      navigate(`/eventos/${eventId}/conteudo`, { replace: true });
    }
  }, [user, eventId, navigate]);

  useEffect(() => {
    if (user && user.role === 'professor') return;

    if (eventId && senha) {
      const fetchEvento = async () => {
        try {
          setLoading(true);
          const response = await api.get<EventoType>(
            `/eventos/${eventId}/detalhes?senha=${encodeURIComponent(senha)}`
          );
          setEvento(response.data);
          setError(null);
        } catch (err: any) {
          const status = err.response?.status;
          const detalhe = err.response?.data?.detail;
          if (status === 403 || status === 429) {
            // senha errada ou bloqueio temporário: volta para a janela da senha para tentar de novo
            setEvento(null);
            setSenhaError(detalhe || (status === 429 ? 'Muitas tentativas. Aguarde alguns minutos.' : 'Senha do evento inválida.'));
            setSenhaModalOpen(true);
          } else {
            setError(detalhe || 'Falha ao buscar detalhes do evento.');
          }
        } finally {
          setLoading(false);
        }
      };
      fetchEvento();
    }
  }, [eventId, senha, tentativa, user]);

  const handleSenhaSubmit = () => {
    if (!senhaDigitada) {
      setSenhaError('Digite a senha do evento');
      return;
    }
    setSenhaModalOpen(false);
    setSenhaError(null);
    setSenha(senhaDigitada);
    setTentativa((t) => t + 1); // mesma senha de novo também confere de novo
  };

  function formatDateBR(dateStr: string | null): string {
    if (!dateStr) return 'N/D';
    try {
      const date = new Date(dateStr);
      const dia = String(date.getDate()).padStart(2, '0');
      const mes = String(date.getMonth() + 1).padStart(2, '0');
      const ano = date.getFullYear();
      return `${dia}/${mes}/${ano}`;
    } catch {
      return 'N/D';
    }
  }

  if (user && user.role === 'professor') return null;

  const eventModules = [
    {
      title: 'Cargos & Vagas',
      desc: 'Gerencie cargos, níveis, turnos, disciplinas da prova, pesos e capas em PDF.',
      path: `/eventos/${eventId}/cargo`,
      icon: <WorkIcon fontSize="small" />,
      badge: 'Estrutura',
    },
    {
      title: 'Conteúdos & Banco de Questões',
      desc: 'Conteúdos programáticos por professor, elaboração, importação DOCX e revisão de questões.',
      path: `/eventos/${eventId}/conteudo`,
      icon: <SubjectIcon fontSize="small" />,
      badge: 'Elaboração',
    },
    {
      title: 'Montagem de Provas',
      desc: 'Monte os cadernos de prova por cargo, organize blocos de disciplinas e textos de referência.',
      path: `/eventos/${eventId}/provas`,
      icon: <AssignmentIcon fontSize="small" />,
      badge: 'Diagramação',
    },
    {
      title: 'Geração & Simulações',
      desc: 'Configure variações de cadernos, embaralhamento, simulação de frases e balanceamento C/E.',
      path: `/eventos/${eventId}/geracao`,
      icon: <BuildIcon fontSize="small" />,
      badge: 'Variações',
    },
    {
      title: 'Exportação & Pacotes ZIP',
      desc: 'Gere arquivos finais DOCX, PDF com capa AcroForm preenchida e pacotes ZIP criptografados.',
      path: `/eventos/${eventId}/exportacao`,
      icon: <FileDownloadIcon fontSize="small" />,
      badge: 'Produção',
    },
    {
      title: 'Gabaritos & Variações',
      desc: 'Consulte e exporte gabaritos preliminares/definitivos e matrizes de variação por cargo.',
      path: `/eventos/${eventId}/recursos`,
      icon: <RecordVoiceOverIcon fontSize="small" />,
      badge: 'Gabarito',
    },
  ];

  return (
    <Layout>
      {/* Hero Header */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          justifyContent: 'space-between',
          alignItems: { xs: 'flex-start', sm: 'center' },
          gap: 2,
          mb: 3.5,
        }}
      >
        <Box>
          <Stack direction="row" spacing={1.75} alignItems="center" sx={{ mb: 0.75 }}>
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: '11px',
                background: 'linear-gradient(135deg, #0EA5E9 0%, #2563EB 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 16px rgba(14, 165, 233, 0.35)',
              }}
            >
              <EventIcon sx={{ color: '#FFF', fontSize: 22 }} />
            </Box>
            <Typography variant="h4" component="h1" sx={{ fontWeight: 800, color: '#F8FAFC' }}>
              {evento?.nome_evento || 'Central do Evento'}
            </Typography>
          </Stack>
          <Typography sx={{ color: '#94A3B8', fontSize: '0.92rem' }}>
            Painel operacional do concurso: acesse rapidamente cargos, questões, montagem, geração e exportação.
          </Typography>
        </Box>

        <Stack direction="row" spacing={1.5}>
          <Button
            variant="outlined"
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/dashboard')}
          >
            Concursos
          </Button>
          <Button
            variant="contained"
            startIcon={<EditOutlinedIcon />}
            onClick={() => navigate(`/eventos/${eventId}/editar`)}
          >
            Editar Evento
          </Button>
        </Stack>
      </Box>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 5 }}>
          <CircularProgress />
        </Box>
      )}
      {error && (
        <Alert severity="error" sx={{ my: 2 }}>
          {error}
        </Alert>
      )}

      {evento && (
        <>
          {/* KPI Summary Cards */}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
              gap: 2,
              mb: 3.5,
            }}
          >
            <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: '#0B1325', border: '1px solid rgba(56, 189, 248, 0.14)' }}>
              <Typography sx={{ fontSize: '0.78rem', color: '#94A3B8', mb: 0.5 }}>Identificador</Typography>
              <Typography sx={{ fontSize: '1.6rem', fontWeight: 800, color: '#38BDF8' }}>
                {evento.identificador_evento || 'N/D'}
              </Typography>
              <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>
                Edital: {evento.numero_edital || 'Não informado'}
              </Typography>
            </Box>
            <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: '#0B1325', border: '1px solid rgba(56, 189, 248, 0.14)' }}>
              <Typography sx={{ fontSize: '0.78rem', color: '#94A3B8', mb: 0.5 }}>Data da Prova</Typography>
              <Typography sx={{ fontSize: '1.6rem', fontWeight: 800, color: '#F8FAFC' }}>
                {formatDateBR(evento.data_prova)}
              </Typography>
              <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>
                Local: {evento.local_prova || 'A definir'}
              </Typography>
            </Box>
            <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: '#0B1325', border: '1px solid rgba(56, 189, 248, 0.14)' }}>
              <Typography sx={{ fontSize: '0.78rem', color: '#94A3B8', mb: 0.5 }}>Status do Concurso</Typography>
              <Typography sx={{ fontSize: '1.6rem', fontWeight: 800, color: '#10B981' }}>
                {evento.status || 'Aberto'}
              </Typography>
              <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Protegido por senha criptografada</Typography>
            </Box>
            <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: '#0B1325', border: '1px solid rgba(56, 189, 248, 0.14)' }}>
              <Typography sx={{ fontSize: '0.78rem', color: '#94A3B8', mb: 0.5 }}>Cargos Cadastrados</Typography>
              <Typography sx={{ fontSize: '1.6rem', fontWeight: 800, color: '#F8FAFC' }}>
                {evento.cargos ? evento.cargos.length : 0}
              </Typography>
              <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Prontos para estruturação</Typography>
            </Box>
          </Box>

          {/* Módulos Operacionais do Evento */}
          <Typography sx={{ fontWeight: 700, fontSize: '1.05rem', color: '#F8FAFC', mb: 2 }}>
            Módulos operacionais do concurso
          </Typography>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' },
              gap: 2,
              mb: 3.5,
            }}
          >
            {eventModules.map((mod) => (
              <Box
                key={mod.path}
                onClick={() => navigate(mod.path)}
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
                      px: 1.1,
                      py: 0.2,
                      borderRadius: '999px',
                      bgcolor: 'rgba(14, 165, 233, 0.12)',
                      border: '1px solid rgba(56, 189, 248, 0.35)',
                      color: '#38BDF8',
                      fontSize: '0.7rem',
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

          {/* Lista de Cargos do Evento */}
          <Box
            sx={{
              p: 3,
              borderRadius: 3.5,
              bgcolor: '#0B1325',
              border: '1px solid rgba(56, 189, 248, 0.14)',
            }}
          >
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
              <Typography sx={{ fontWeight: 700, fontSize: '1.02rem', color: '#F8FAFC' }}>
                Cargos vinculados ao concurso
              </Typography>
              <Button size="small" variant="outlined" onClick={() => navigate(`/eventos/${eventId}/cargo`)}>
                Gerenciar Cargos
              </Button>
            </Stack>
            {evento.cargos && evento.cargos.length > 0 ? (
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
                  gap: 1.5,
                }}
              >
                {evento.cargos.map((cargo: Cargo) => (
                  <Box
                    key={cargo.id_cargo}
                    sx={{
                      p: 1.75,
                      borderRadius: 2.5,
                      bgcolor: 'rgba(6, 11, 25, 0.65)',
                      border: '1px solid rgba(148, 163, 184, 0.14)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1.25,
                    }}
                  >
                    <WorkIcon sx={{ color: '#38BDF8', fontSize: 18 }} />
                    <Typography sx={{ fontWeight: 600, fontSize: '0.88rem', color: '#E2E8F0' }}>
                      {cargo.nome_cargo}
                    </Typography>
                  </Box>
                ))}
              </Box>
            ) : (
              <Typography sx={{ color: '#64748B', fontSize: '0.88rem' }}>
                Nenhum cargo cadastrado para este evento até o momento.
              </Typography>
            )}
          </Box>
        </>
      )}

      {/* Modal para senha */}
      <Dialog open={senhaModalOpen} onClose={() => navigate('/dashboard')} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Acesso Protegido do Evento</DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: '0.85rem', color: '#94A3B8', mb: 2 }}>
            Informe a senha de segurança do evento para desbloquear seus dados e módulos.
          </Typography>
          <TextField
            type="password"
            label="Senha do Evento"
            value={senhaDigitada}
            onChange={(e) => setSenhaDigitada(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSenhaSubmit()}
            fullWidth
            autoFocus
            error={!!senhaError}
            helperText={senhaError}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => navigate('/dashboard')} variant="outlined">
            Voltar
          </Button>
          <Button onClick={handleSenhaSubmit} variant="contained" color="primary">
            Desbloquear
          </Button>
        </DialogActions>
      </Dialog>
    </Layout>
  );
}

export default EventoDetalhesPage;
