import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Button, IconButton, Snackbar, Paper, Divider,
  Table, TableHead, TableRow, TableCell, TableBody, LinearProgress,
  Alert, CircularProgress
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import api from '../api';
import Layout from '../components/Layout';
import { useParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

type ConteudoType = {
  id_conteudo: string;
  identificador_conteudo?: string;
  nome_conteudo: string;
  quantidade?: number;
  respondidas?: number;
  evento_id?: string; 
};

const ConteudoPage: React.FC = () => {
  const { eventId } = useParams<{ eventId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [conteudos, setConteudos] = useState<ConteudoType[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });

  const isProfessor = user?.role === 'professor';

  useEffect(() => {
    async function fetchConteudos() {
      setCarregando(true);
      try {
        let res;
        if (isProfessor) {
          // Busca todos os conteúdos vinculados ao professor, independente do evento
          res = await api.get('/conteudos/meus');
        } else {
          res = await api.get(`/conteudos/eventos/${eventId}/conteudos`);
        }
        setConteudos(res.data);
      } catch (err) {
        setSnackbar({ open: true, message: 'Falha ao carregar conteúdos', severity: 'error' });
      }
      setCarregando(false);
    }
    fetchConteudos();
  }, [eventId, isProfessor]);

  // Handler para deletar
  const handleDelete = async (id_conteudo: string) => {
    if (window.confirm('Deseja realmente excluir este conteúdo?')) {
      try {
        await api.delete(`/conteudos/${id_conteudo}`);
        setConteudos(prev => prev.filter(c => c.id_conteudo !== id_conteudo));
        setSnackbar({ open: true, message: 'Conteúdo excluído!', severity: 'success' });
      } catch {
        setSnackbar({ open: true, message: 'Erro ao excluir!', severity: 'error' });
      }
    }
  };

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h5" fontWeight="bold">
            {isProfessor ? 'Meus Conteúdos' : 'Conteúdos do Evento'}
          </Typography>
          {/* Só mostra botões de importar e novo conteúdo se NÃO for professor */}
          {!isProfessor && (
            <Box>
              <Button
                variant="outlined"
                color="secondary"
                startIcon={<UploadFileIcon />}
                sx={{ mr: 2 }}
              >
                Importar CSV
              </Button>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                color="primary"
                onClick={() => navigate(`/eventos/${eventId}/conteudo/criar`)}
              >
                Novo Conteúdo
              </Button>
            </Box>
          )}
        </Box>
        <Divider sx={{ mb: 2 }} />
        {carregando ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 200 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Identificador</TableCell>
                <TableCell>Nome</TableCell>
                <TableCell>Progresso</TableCell>
                {/* Só mostra coluna de ações se NÃO for professor */}
                {!isProfessor && <TableCell align="center">Ações</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {conteudos.map(conteudo => (
                <TableRow key={conteudo.id_conteudo} hover>
                  <TableCell>
                    <Typography
                      sx={{ cursor: 'pointer', color: 'primary.main', textDecoration: 'none' }}
                      component={RouterLink}
                      to={
                        isProfessor
                          ? `/eventos/${conteudo.evento_id}/conteudo/${conteudo.id_conteudo}/iniciar`
                          : `/eventos/${eventId}/conteudo/${conteudo.id_conteudo}/iniciar`
                      }
                    >
                      {conteudo.identificador_conteudo ?? conteudo.id_conteudo}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography
                      sx={{ cursor: 'pointer', color: 'primary.main', textDecoration: 'none' }}
                      component={RouterLink}
                      to={
                        isProfessor
                          ? `/eventos/${conteudo.evento_id}/conteudo/${conteudo.id_conteudo}/iniciar`
                          : `/eventos/${eventId}/conteudo/${conteudo.id_conteudo}/iniciar`
                      }
                    >
                      {conteudo.nome_conteudo}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ minWidth: 120 }}>
                      <Typography variant="caption" sx={{ fontWeight: 'bold' }}>
                        {conteudo.respondidas ?? 0}/{conteudo.quantidade ?? 0}
                      </Typography>
                      <LinearProgress
                        variant="determinate"
                        value={conteudo.quantidade ? (conteudo.respondidas ?? 0) / conteudo.quantidade * 100 : 0}
                        sx={{ height: 6, borderRadius: 2, my: 0.5 }}
                      />
                      <Typography variant="caption">
                        {conteudo.quantidade
                          ? ((conteudo.respondidas ?? 0) / conteudo.quantidade * 100).toFixed(0)
                          : '0'}%
                      </Typography>
                    </Box>
                  </TableCell>
                  {/* Só mostra botões de ação se NÃO for professor */}
                  {!isProfessor && (
                    <TableCell align="center">
                      <IconButton
                        color="primary"
                        onClick={() => navigate(`/eventos/${eventId}/conteudo/editar/${conteudo.id_conteudo}`)}
                      >
                        <EditIcon />
                      </IconButton>
                      <IconButton
                        color="error"
                        onClick={() => handleDelete(conteudo.id_conteudo)}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  )}
                </TableRow>
              ))}
              {conteudos.length === 0 && (
                <TableRow>
                  <TableCell colSpan={isProfessor ? 3 : 4} align="center">
                    Nenhum conteúdo cadastrado.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
        <Snackbar
          open={snackbar.open}
          autoHideDuration={3000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
        >
          <Alert severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Paper>
    </Layout>
  );
};

export default ConteudoPage;