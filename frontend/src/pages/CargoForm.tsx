import React, { useState, useRef, useEffect } from "react";
import {
  Box, TextField, Button, Typography, Divider, MenuItem, Paper,
  Checkbox, FormControlLabel, Table, TableHead, TableRow, TableCell, TableBody, IconButton, Alert, Snackbar
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import api from "../api";
import CapaDoCargo from "../components/capa/CapaDoCargo";

const NIVEIS_VALIDOS = [
  "Nível Fundamental", "Nível Médio", "Nível Superior", "Outro"
];
const TURNOS_VALIDOS = [
  "Manhã", "Tarde", "Noite", "Integral", "Indefinido"
];

export type Disciplina = {
  nome_disciplina: string;
  nome_disciplina_na_prova?: string;
  qtd_questoes: number;
  peso_por_questao: number;
  ordem_na_prova: number;
};

export type Cargo = {
  id_cargo?: string;
  nome_cargo: string;
  codigo_cargo?: string;
  nivel: string;
  turno: string;
  vagas?: number | string;
  salario?: number | string;
  requisitos?: string;
  tem_discursiva?: boolean;
  cover_pdf_paths?: string | string[];
  peso_total_prova?: number | string;
  disciplinas_prova: Disciplina[];
};

const emptyDisciplina: Disciplina = {
  nome_disciplina: "",
  qtd_questoes: 0,
  peso_por_questao: 0,
  ordem_na_prova: 1,
};

const defaultCargo: Cargo = {
  nome_cargo: "",
  codigo_cargo: "",
  nivel: NIVEIS_VALIDOS[0],
  turno: TURNOS_VALIDOS[0],
  vagas: "",
  salario: "",
  requisitos: "",
  tem_discursiva: false,
  cover_pdf_paths: "",
  peso_total_prova: "",
  disciplinas_prova: [ { ...emptyDisciplina } ]
};

type Props = {
  eventId: string;
  cargo?: Cargo | null;
  onSaved: () => void;
  onError?: (msg: string) => void;
};

export default function CargoForm({ eventId, cargo, onSaved, onError }: Props) {
  const [form, setForm] = useState<Cargo>(cargo ? {
    ...cargo,
    vagas: cargo.vagas ?? "",
    salario: cargo.salario ?? "",
    requisitos: cargo.requisitos ?? "",
    cover_pdf_paths: typeof cargo.cover_pdf_paths === "string"
      ? cargo.cover_pdf_paths
      : (cargo.cover_pdf_paths ?? []).join(";"),
    peso_total_prova: cargo.peso_total_prova ?? "",
    disciplinas_prova: cargo.disciplinas_prova?.length
      ? cargo.disciplinas_prova
      : [ { ...emptyDisciplina } ]
  } : { ...defaultCargo });

  useEffect(() => {
    if (cargo) {
      setForm(prev => ({
        ...prev,
        cover_pdf_paths: Array.isArray(cargo.cover_pdf_paths)
          ? cargo.cover_pdf_paths.join(";")
          : (cargo.cover_pdf_paths ? cargo.cover_pdf_paths : ""),
        disciplinas_prova: cargo.disciplinas_prova?.length
          ? cargo.disciplinas_prova
          : [ { ...emptyDisciplina } ]
      }));
    }
    // eslint-disable-next-line
  }, [cargo]);

  const [error, setError] = useState<string | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: "", severity: "success" });

  const coverFileInputRef = useRef<HTMLInputElement>(null);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { name, value, type, checked } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value
    }));
  }

  function handleNumberChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: value
    }));
  }

  function handleDisciplinaChange(idx: number, field: keyof Disciplina, value: string | number) {
    setForm(prev => {
      const newDisc = [...prev.disciplinas_prova];
      newDisc[idx] = { ...newDisc[idx], [field]: value };
      return { ...prev, disciplinas_prova: newDisc };
    });
  }

  function handleAddDisciplina() {
    setForm(prev => ({
      ...prev,
      disciplinas_prova: [
        ...prev.disciplinas_prova,
        { ...emptyDisciplina, ordem_na_prova: prev.disciplinas_prova.length + 1 }
      ]
    }));
  }

  function handleRemoveDisciplina(idx: number) {
    setForm(prev => ({
      ...prev,
      disciplinas_prova: prev.disciplinas_prova.filter((_, i) => i !== idx)
    }));
  }

  function handleCoverPdfImportClick() {
    coverFileInputRef.current?.click();
  }

  async function handleCoverPdfFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !eventId) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await api.post(`/eventos/${eventId}/cargos/upload-capa-pdf`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const pdfPath = response.data?.cover_pdf_paths || response.data?.path || file.name;
      setForm(prev => ({
        ...prev,
        cover_pdf_paths: Array.isArray(pdfPath) ? pdfPath.join(";") : pdfPath,
      }));

      setSnackbar({ open: true, message: "PDF de capa importado com sucesso!", severity: "success" });
    } catch (err: any) {
      setSnackbar({ open: true, message: "Erro ao importar PDF de capa.", severity: "error" });
    } finally {
      if (coverFileInputRef.current) coverFileInputRef.current.value = "";
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!form.nome_cargo.trim()) {
      setError("Nome do cargo é obrigatório.");
      return;
    }
    if (!form.nivel) {
      setError("Selecione o nível do cargo.");
      return;
    }
    if (!form.turno) {
      setError("Selecione o turno do cargo.");
      return;
    }

    try {
      let coverPathsArr: string[];
      if (!form.cover_pdf_paths) {
        coverPathsArr = [];
      } else if (Array.isArray(form.cover_pdf_paths)) {
        coverPathsArr = form.cover_pdf_paths;
      } else if (typeof form.cover_pdf_paths === "string") {
        coverPathsArr = form.cover_pdf_paths
          .split(";")
          .map(s => s.trim())
          .filter(Boolean);
      } else {
        coverPathsArr = [];
      }
      const payload = {
        ...form,
        vagas: form.vagas ? Number(form.vagas) : null,
        salario: form.salario ? Number(form.salario) : null,
        peso_total_prova: form.peso_total_prova ? Number(form.peso_total_prova) : null,
        cover_pdf_paths: coverPathsArr,
      };

      if (cargo?.id_cargo) {
        await api.put(`/cargos/${cargo.id_cargo}`, payload);
        setSnackbar({ open: true, message: "Cargo atualizado!", severity: "success" });
      } else {
        await api.post(`/eventos/${eventId}/cargos`, payload);
        setSnackbar({ open: true, message: "Cargo criado!", severity: "success" });
      }
      onSaved();
    } catch (err: any) {
      let msg = "Erro ao salvar cargo.";
      if (err.response?.data?.detail) {
        msg = typeof err.response.data.detail === "string"
          ? err.response.data.detail
          : JSON.stringify(err.response.data.detail);
      }
      setSnackbar({ open: true, message: msg, severity: "error" });
      onError?.(msg);
    }
  }

  return (
    <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
      <Box component="form" onSubmit={handleSubmit} autoComplete="off">
        <Box sx={{ display: "flex", gap: 2 }}>
          <TextField
            label="Código do Cargo"
            name="codigo_cargo"
            value={form.codigo_cargo}
            onChange={handleChange}
            fullWidth
            sx={{ mb: 2 }}
        />
        <TextField
            label="Nome do Cargo"
            name="nome_cargo"
            value={form.nome_cargo}
            onChange={handleChange}
            required
            fullWidth
            sx={{ mb: 2 }}
        />
        </Box>
        <Box sx={{ display: "flex", gap: 2 }}>
          <TextField
            select
            label="Nível"
            name="nivel"
            value={form.nivel}
            onChange={handleChange}
            required
            fullWidth
            sx={{ mb: 2 }}
          >
            {NIVEIS_VALIDOS.map(opt => (
              <MenuItem key={opt} value={opt}>{opt}</MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label="Turno"
            name="turno"
            value={form.turno}
            onChange={handleChange}
            required
            fullWidth
            sx={{ mb: 2 }}
          >
            {TURNOS_VALIDOS.map(opt => (
              <MenuItem key={opt} value={opt}>{opt}</MenuItem>
            ))}
          </TextField>
        </Box>
        <Box sx={{ display: "flex", gap: 2 }}>
          <TextField
            label="Vagas"
            name="vagas"
            type="number"
            value={form.vagas}
            onChange={handleNumberChange}
            fullWidth
            sx={{ mb: 2 }}
          />
          <TextField
            label="Salário (R$)"
            name="salario"
            type="number"
            value={form.salario}
            onChange={handleNumberChange}
            fullWidth
            sx={{ mb: 2 }}
          />
        </Box>
        <TextField
          label="Requisitos"
          name="requisitos"
          value={form.requisitos}
          onChange={handleChange}
          multiline
          rows={2}
          fullWidth
          sx={{ mb: 2 }}
        />
        <FormControlLabel
          control={
            <Checkbox
              checked={!!form.tem_discursiva}
              onChange={handleChange}
              name="tem_discursiva"
            />
          }
          label="Possui Prova Discursiva"
          sx={{ mb: 2 }}
        />

        <Box sx={{ display: "flex", gap: 2 }}>
          <input
            type="file"
            accept=".pdf"
            style={{ display: "none" }}
            ref={coverFileInputRef}
            onChange={handleCoverPdfFileChange}
          />
        </Box>
        <CapaDoCargo
          eventId={eventId || ''}
          refCapa={(Array.isArray(form.cover_pdf_paths) ? form.cover_pdf_paths[0] : String(form.cover_pdf_paths || '').split(';')[0]) || ''}
          cargo={{ nome_cargo: form.nome_cargo, codigo_cargo: form.codigo_cargo, nivel: form.nivel, turno: form.turno }}
          onImportar={handleCoverPdfImportClick}
        />

        <TextField
          label="Peso Total da Prova"
          name="peso_total_prova"
          type="number"
          value={form.peso_total_prova}
          onChange={handleNumberChange}
          fullWidth
          sx={{ mb: 2 }}
        />

        <Divider sx={{ my: 3 }} />
        <Typography variant="subtitle1" fontWeight="bold" sx={{ mb: 1 }}>
          Disciplinas da Prova
        </Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Nome</TableCell>
              <TableCell>Qtd. Questões</TableCell>
              <TableCell>Peso/Questão</TableCell>
              <TableCell>Ordem</TableCell>
              <TableCell align="center">Ações</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {form.disciplinas_prova.map((disc, idx) => (
              <TableRow key={idx}>
                <TableCell>
                  <TextField
                    value={disc.nome_disciplina || disc.nome_disciplina_na_prova || ""}
                    onChange={e =>
                      handleDisciplinaChange(idx, "nome_disciplina", e.target.value)
                    }
                    size="small"
                    placeholder="Nome da Disciplina"
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    value={disc.qtd_questoes}
                    type="number"
                    onChange={e =>
                      handleDisciplinaChange(idx, "qtd_questoes", Number(e.target.value))
                    }
                    size="small"
                    placeholder="Qtd"
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    value={disc.peso_por_questao}
                    type="number"
                    onChange={e =>
                      handleDisciplinaChange(idx, "peso_por_questao", Number(e.target.value))
                    }
                    size="small"
                    placeholder="Peso"
                  />
                </TableCell>
                <TableCell>
                  <TextField
                    value={disc.ordem_na_prova}
                    type="number"
                    onChange={e =>
                      handleDisciplinaChange(idx, "ordem_na_prova", Number(e.target.value))
                    }
                    size="small"
                    placeholder="Ordem"
                  />
                </TableCell>
                <TableCell align="center">
                  <IconButton
                    color="error"
                    onClick={() => handleRemoveDisciplina(idx)}
                    disabled={form.disciplinas_prova.length <= 1}
                  >
                    <DeleteIcon />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Button
          startIcon={<AddIcon />}
          variant="outlined"
          sx={{ mt: 1 }}
          onClick={handleAddDisciplina}
        >
          Adicionar Disciplina
        </Button>
        <Divider sx={{ my: 3 }} />

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Box sx={{ display: "flex", gap: 2, mt: 2 }}>
          <Button variant="contained" color="success" type="submit">
            Salvar Cargo
          </Button>
        </Box>
      </Box>
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        message={snackbar.message}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      />
    </Paper>
  );
}