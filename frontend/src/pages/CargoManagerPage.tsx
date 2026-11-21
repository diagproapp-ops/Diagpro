import React, { useCallback, useEffect, useState, useRef } from "react";
import {
  Box,
  Typography,
  Paper,
  Button,
  IconButton,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Divider,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { useParams } from "react-router-dom";
import api from "../api";
import Layout from "../components/Layout";
import CargoForm from "./CargoForm";

export interface Disciplina {
  nome_disciplina: string;
  nome_disciplina_na_prova?: string; // <-- ADICIONE ESTA LINHA
  qtd_questoes: number;
  peso_por_questao: number;
  ordem_na_prova: number;
}

export interface Cargo {
  id_cargo: string;
  nome_cargo: string;
  codigo_cargo?: string;
  nivel: string;
  turno: string;
  vagas?: number | string;
  salario?: number | string;
  requisitos?: string;
  tem_discursiva?: boolean;
  letterhead_pdf_path?: string;
  cover_pdf_paths?: string;
  peso_total_prova?: number | string;
  disciplinas_prova: Disciplina[];
}

export default function CargoManagerPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const [cargos, setCargos] = useState<Cargo[]>([]);
  const [selectedCargo, setSelectedCargo] = useState<Cargo | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: "info" | "error" | "success" }>({
    open: false,
    message: "",
    severity: "info",
  });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  // Ref para input de arquivo
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchCargos = useCallback(async () => {
    try {
      const response = await api.get<Cargo[]>(`/eventos/${eventId}/cargos`);
      const ajustados = response.data.map((cargo) => ({
        ...cargo,
        cover_pdf_paths:
          Array.isArray(cargo.cover_pdf_paths)
            ? cargo.cover_pdf_paths.join(";")
            : cargo.cover_pdf_paths ?? "",
      }));
      setCargos(ajustados);
    } catch (err) {
      setSnackbar({ open: true, message: "Falha ao buscar cargos.", severity: "error" });
    }
  }, [eventId]);

  useEffect(() => {
    fetchCargos();
  }, [fetchCargos]);

  function handleEditCargo(cargo: Cargo) {
    setSelectedCargo({
      ...cargo,
      cover_pdf_paths:
        Array.isArray(cargo.cover_pdf_paths)
          ? cargo.cover_pdf_paths.join(";")
          : cargo.cover_pdf_paths ?? "",
    });
    setShowForm(true);
  }

  function handleNewCargo() {
    setSelectedCargo(null);
    setShowForm(true);
  }

  function handleFormSaved() {
    setShowForm(false);
    fetchCargos();
  }

  function handleBackToList() {
    setShowForm(false);
    setSelectedCargo(null);
  }

  function handleDeleteDialog(id: string) {
    setDeleteId(id);
    setDialogOpen(true);
  }

  async function handleDeleteCargo() {
    try {
      await api.delete(`/cargos/${deleteId}`);
      setSnackbar({ open: true, message: "Cargo excluído!", severity: "info" });
      fetchCargos();
    } catch (err) {
      setSnackbar({ open: true, message: "Erro ao excluir cargo.", severity: "error" });
    } finally {
      setDialogOpen(false);
      setDeleteId(null);
    }
  }

  // Importação CSV
  function handleImportCsvClick() {
    fileInputRef.current?.click();
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !eventId) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      // Ajuste a URL para o endpoint correto de importação CSV do seu backend!
      await api.post(`/eventos/${eventId}/cargos/import-csv`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setSnackbar({ open: true, message: "CSV importado com sucesso!", severity: "success" });
      fetchCargos();
    } catch (err: any) {
      setSnackbar({ open: true, message: "Erro ao importar CSV.", severity: "error" });
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        {showForm ? (
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h5" fontWeight="bold">
                {selectedCargo ? "Editar Cargo" : "Novo Cargo"}
              </Typography>
              <Button
                startIcon={<ArrowBackIcon />}
                variant="outlined"
                color="primary"
                onClick={handleBackToList}
              >
                Voltar para Lista
              </Button>
            </Box>
            <Divider sx={{ mb: 2 }} />
            <CargoForm
              eventId={eventId!}
              cargo={selectedCargo}
              onSaved={handleFormSaved}
              onError={(msg: string) => setSnackbar({ open: true, message: msg, severity: "error" })}
            />
          </Box>
        ) : (
          <Box>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
              <Typography variant="h5" fontWeight="bold">Cargos do Evento</Typography>
              <Box>
                <input
                  type="file"
                  accept=".csv"
                  style={{ display: "none" }}
                  ref={fileInputRef}
                  onChange={handleFileChange}
                />
                <Button
                  startIcon={<UploadFileIcon />}
                  variant="outlined"
                  color="secondary"
                  onClick={handleImportCsvClick}
                  sx={{ mr: 2 }}
                >
                  Importar CSV
                </Button>
                <Button
                  startIcon={<AddIcon />}
                  variant="contained"
                  color="primary"
                  onClick={handleNewCargo}
                >
                  Novo Cargo
                </Button>
              </Box>
            </Box>
            <Divider sx={{ mb: 2 }} />
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Código</TableCell>
                  <TableCell>Nome</TableCell>
                  <TableCell>Nível</TableCell>
                  <TableCell>Turno</TableCell>
                  <TableCell>Vagas</TableCell>
                  <TableCell>Salário</TableCell>
                  <TableCell>Discursiva</TableCell>
                  <TableCell>Disciplinas</TableCell>
                  <TableCell align="center">Ações</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {cargos.map((cargo) => (
                  <TableRow key={cargo.id_cargo} hover>
                    <TableCell>{cargo.codigo_cargo}</TableCell>
                    <TableCell>{cargo.nome_cargo}</TableCell>
                    <TableCell>{cargo.nivel}</TableCell>
                    <TableCell>{cargo.turno}</TableCell>
                    <TableCell>{cargo.vagas}</TableCell>
                    <TableCell>{cargo.salario}</TableCell>
                    <TableCell>{cargo.tem_discursiva ? "Sim" : "Não"}</TableCell>
                    <TableCell>
                      {cargo.disciplinas_prova?.map((d) => d.nome_disciplina_na_prova ?? d.nome_disciplina).join(", ")}
                    </TableCell>
                    <TableCell align="center">
                      <IconButton color="primary" onClick={() => handleEditCargo(cargo)}>
                        <AddIcon />
                      </IconButton>
                      <IconButton color="error" onClick={() => handleDeleteDialog(cargo.id_cargo)}>
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}
        <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)}>
          <DialogTitle>Confirmar Exclusão</DialogTitle>
          <DialogContent>Tem certeza que deseja excluir este cargo?</DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogOpen(false)}>Cancelar</Button>
            <Button color="error" variant="contained" onClick={handleDeleteCargo}>
              Excluir
            </Button>
          </DialogActions>
        </Dialog>
        <Snackbar
          open={snackbar.open}
          autoHideDuration={4000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          message={snackbar.message}
          anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        />
      </Paper>
    </Layout>
  );
}