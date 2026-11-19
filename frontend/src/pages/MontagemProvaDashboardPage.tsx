import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Paper, Divider, CircularProgress, Table, TableBody, TableCell, TableHead, TableRow,
  Snackbar, Alert, Button, IconButton, Tooltip
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import VisibilityIcon from '@mui/icons-material/Visibility';
import SyncIcon from '@mui/icons-material/Sync';
import api from '../api';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import PreviewProvaDialog from './PreviewProvaDialog'; // Certifique-se de que esse arquivo existe!

const MontagemProvaDashboardPage: React.FC = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const [cargos, setCargos] = useState<any[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [snackbar, setSnackbar] = useState<{open:boolean, message:string, severity:"success"|"error"|"info"}>({open:false, message:'', severity:"success"});
  const [previewOpen, setPreviewOpen] = useState(false);
  const [provaPreview, setProvaPreview] = useState<any>(null);

  useEffect(() => {
    async function fetchCargos() {
      setCarregando(true);
      try {
        const res = await api.get(`/provas/eventos/${eventId}/cargos-com-status-prova`);
        setCargos(res.data);
      } catch {
        setSnackbar({open:true, message:"Erro ao carregar cargos", severity:"error"});
      }
      setCarregando(false);
    }
    fetchCargos();
  }, [eventId]);

  function handleMontagem() {
    navigate(`/eventos/${eventId}/provas/montagem`);
  }
  // Relê do banco as questões já escolhidas (mesmas questões, mesma ordem, mesma semente).
  // Só as que mudaram desde a montagem são trocadas; o resto da prova fica idêntico.
  async function handleAtualizarQuestoes(cargoId: string) {
    if (!window.confirm("Atualizar as questões desta montagem com a versão atual do banco?\n\nNão sorteia de novo: as questões e a ordem continuam as mesmas; só o texto/imagens das questões editadas depois da montagem é atualizado.")) return;
    try {
      const { data } = await api.post(`/provas/eventos/${eventId}/provas-montadas/${cargoId}/atualizar-questoes`);
      const n = (data.atualizadas || []).length;
      const exc = (data.excluidas_do_banco || []).length;
      setSnackbar({
        open: true,
        severity: exc ? "error" : "success",
        message: n
          ? `${n} questão(ões) atualizada(s): ${(data.atualizadas || []).join(', ')}.${exc ? ` ${exc} questão(ões) não existem mais no banco.` : ''}`
          : `Nenhuma questão mudou desde a montagem.${exc ? ` ${exc} questão(ões) não existem mais no banco.` : ''}`,
      });
    } catch (e: any) {
      setSnackbar({ open: true, message: e?.response?.data?.detail || "Erro ao atualizar as questões.", severity: "error" });
    }
  }

  async function handleExcluir(cargoId: string) {
    try {
      await api.delete(`/provas/eventos/${eventId}/provas-montadas/${cargoId}`);
      setSnackbar({open:true, message:"Montagem excluída com sucesso!", severity:"success"});
      setCargos(cargos => cargos.map(c =>
        c.id_cargo === cargoId ? { ...c, status_montagem: "Não Iniciada" } : c
      ));
    } catch {
      setSnackbar({open:true, message:"Erro ao excluir montagem", severity:"error"});
    }
  }
  async function handleVisualizar(cargoId: string) {
    try {
      const res = await api.get(`/provas/eventos/${eventId}/provas-montadas/${cargoId}`);
      setProvaPreview(res.data);      // <---- Corrigido aqui!
      setPreviewOpen(true);
    } catch {
      setSnackbar({open:true, message:"Erro ao buscar prévia", severity:"error"});
    }
  }

  function handleFinalizarMontagem() {
    setSnackbar({
      open: true,
      message: "Função de finalizar montagem ainda não implementada.",
      severity: "info"
    });
  }

  function handleExportarPrevia() {
    setSnackbar({
      open: true,
      message: "Função de exportar prévia ainda não implementada.",
      severity: "info"
    });
  }

  return (
    <Layout>
      <Paper sx={{ p: 3 }}>
        {/* Título + Botão na mesma linha */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h5" fontWeight="bold">
            Montagem de Provas - Cargos do Evento
          </Typography>
          <Button
            variant="contained"
            color="primary"
            onClick={handleMontagem}
          >
            Montar Provas
          </Button>
        </Box>
        <Divider sx={{ mb: 2 }} />
        {carregando ? (
          <Box sx={{ display: 'flex', justifyContent: 'center' }}><CircularProgress /></Box>
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Código</TableCell>
                <TableCell>Cargo</TableCell>
                <TableCell>Nível</TableCell>
                <TableCell>Turno</TableCell>
                <TableCell>Status da Montagem</TableCell>
                <TableCell align="center">Ações</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {cargos.map(cargo => (
                <TableRow key={cargo.id_cargo}>
                  <TableCell>{cargo.codigo_cargo || '-'}</TableCell>
                  <TableCell>{cargo.nome_cargo}</TableCell>
                  <TableCell>{cargo.nivel}</TableCell>
                  <TableCell>{cargo.turno}</TableCell>
                  <TableCell>
                    <Typography color={
                      cargo.status_montagem === "Concluída" ? "success.main" :
                      cargo.status_montagem === "Em Andamento" ? "warning.main" :
                      "text.secondary"
                    }>
                      {cargo.status_montagem}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="Preview da prova">
                      <span>
                        <IconButton color="secondary" onClick={() => handleVisualizar(cargo.id_cargo)}>
                          <VisibilityIcon/>
                        </IconButton>
                      </span>
                    </Tooltip>
                    <Tooltip title="Atualizar questões editadas depois da montagem (sem sortear de novo)">
                      <span>
                        <IconButton color="primary" onClick={() => handleAtualizarQuestoes(cargo.id_cargo)}
                          disabled={cargo.status_montagem === "Não Iniciada"}>
                          <SyncIcon/>
                        </IconButton>
                      </span>
                    </Tooltip>
                    <Tooltip title="Excluir montagem">
                      <span>
                        <IconButton color="error" onClick={() => handleExcluir(cargo.id_cargo)}>
                          <DeleteIcon/>
                        </IconButton>
                      </span>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar({...snackbar, open:false})}>
          <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
        </Snackbar>
        <PreviewProvaDialog
          open={previewOpen}
          onClose={() => setPreviewOpen(false)}
          prova={provaPreview}
          onFinalizar={handleFinalizarMontagem}    // implemente se quiser
          onExportar={handleExportarPrevia}
        />
      </Paper>
    </Layout>
  );
};

export default MontagemProvaDashboardPage;