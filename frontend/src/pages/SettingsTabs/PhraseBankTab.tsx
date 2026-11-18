import React, { useState, useEffect, useRef } from 'react';
import PhraseEditorDialog from './PhraseEditorDialog';
import { Box, Typography, Button, Table, TableHead, TableRow, TableCell, TableBody, Stack, Paper, Alert, TextField, Checkbox } from '@mui/material';
import api from '../../api';
import { useAuth } from '../../contexts/AuthContext';

interface Phrase {
  id: number;
  id_local: number; // <- Adicionado
  categoria: string;
  texto_frase: string;
}

type PhraseFormData = Omit<Phrase, 'id' | 'id_local'>;

export default function PhraseBankTab() {
  const [phrases, setPhrases] = useState<Phrase[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filtro, setFiltro] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingPhrase, setEditingPhrase] = useState<Phrase | null>(null);
  const [selectedPhraseIds, setSelectedPhraseIds] = useState<number[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { user } = useAuth();

  const fetchPhrases = () => {
    setError(null);
    api.get('/frases/')
      .then(res => {
        setPhrases(res.data);
      })
      .catch(() => {
        setError('Erro ao carregar frases do servidor.');
      });
  };

  useEffect(() => {
    fetchPhrases();
  }, []);

  const frasesFiltradas = phrases.filter(frase =>
    frase.categoria.toLowerCase().includes(filtro.toLowerCase()) ||
    frase.texto_frase.toLowerCase().includes(filtro.toLowerCase())
  );

  const handleSelectRow = (id: number) => {
    setSelectedPhraseIds((prev) =>
      prev.includes(id)
        ? prev.filter(i => i !== id)
        : [...prev, id]
    );
  };

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      setSelectedPhraseIds(frasesFiltradas.map(frase => frase.id));
    } else {
      setSelectedPhraseIds([]);
    }
  };

  const handleOpenEditDialog = () => {
    if (selectedPhraseIds.length !== 1) {
      alert("Por favor, selecione apenas uma frase para editar.");
      return;
    }
    const phraseToEdit = phrases.find(p => p.id === selectedPhraseIds[0]);
    if (phraseToEdit) {
      setEditingPhrase(phraseToEdit);
      setIsDialogOpen(true);
    }
  };

  const handleRemovePhrase = () => {
    if (selectedPhraseIds.length === 0) {
      alert("Por favor, selecione frases para remover.");
      return;
    }
    if (window.confirm("Tem certeza que deseja remover as frases selecionadas?")) {
      Promise.all(selectedPhraseIds.map(id => api.delete(`/frases/${id}`)))
        .then(() => {
          setSelectedPhraseIds([]);
          fetchPhrases();
        })
        .catch(err => {
          console.error("Erro ao remover a frase:", err);
          setError("Não foi possível remover as frases. Verifique o console para mais detalhes.");
        });
    }
  };

  const handleOpenAddDialog = () => {
    setEditingPhrase(null);
    setIsDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setIsDialogOpen(false);
    setEditingPhrase(null);
  };

  const handleSavePhrase = (formData: PhraseFormData) => {
    if (!user || !user.tenant_id) {
      setError("Usuário não autenticado ou sem tenant_id.");
      return;
    }
    const dataToSend = { ...formData, tenant_id: user.tenant_id };

    const isEditing = editingPhrase !== null;
    const request = isEditing
      ? api.put(`/frases/${editingPhrase.id}`, dataToSend)
      : api.post('/frases/', dataToSend);

    request
      .then(() => {
        handleCloseDialog();
        fetchPhrases();
      })
      .catch(err => {
        console.error("Erro detalhado ao salvar a frase:", err.response || err);
        let errorMessage = "Não foi possível salvar a frase. Tente novamente.";
        if (err.response?.data?.detail) {
          const detail = err.response.data.detail;
          if (Array.isArray(detail)) {
            errorMessage = detail.map(e => e.msg).join(' | ');
          } else if (typeof detail === "string") {
            errorMessage = detail;
          }
        }
        setError(errorMessage);
      });
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("file", file);
    try {
      await api.post("/frases/import/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      fetchPhrases();
      setError(null);
    } catch (err: any) {
      console.error("Erro ao importar CSV:", err);
      setError(err.response?.data?.detail || "Falha ao importar CSV.");
    } finally {
      e.target.value = "";
    }
  };

  const allSelected = frasesFiltradas.length > 0 && selectedPhraseIds.length === frasesFiltradas.length;
  const someSelected = selectedPhraseIds.length > 0 && selectedPhraseIds.length < frasesFiltradas.length;

  return (
    <Box>
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        <Typography variant="h6">Banco de Frases</Typography>
        <Stack direction="row" spacing={2}>
          <Button variant="contained" onClick={handleImportClick}>Importar CSV</Button>
          <input
            type="file"
            accept=".csv"
            ref={fileInputRef}
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
          <Button variant="contained" onClick={handleOpenAddDialog}>Adicionar</Button>
          <Button
            variant="outlined"
            onClick={handleOpenEditDialog}
            disabled={selectedPhraseIds.length !== 1}
          >
            Editar
          </Button>
          <Button
            variant="outlined"
            color="error"
            onClick={handleRemovePhrase}
            disabled={selectedPhraseIds.length === 0}
          >
            Remover
          </Button>
        </Stack>
      </Box>

      <TextField
        fullWidth
        variant="outlined"
        label="Filtrar frases..."
        value={filtro}
        onChange={(e) => setFiltro(e.target.value)}
        sx={{ mb: 2 }}
      />

      {error && <Alert severity="error">{error}</Alert>}
      <Paper elevation={1} sx={{ mb:2 }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox
                  checked={allSelected}
                  indeterminate={someSelected}
                  onChange={handleSelectAll}
                  inputProps={{ 'aria-label': 'Selecionar todas as frases' }}
                />
              </TableCell>
              <TableCell>ID Local</TableCell> {/* Mostra o id_local aqui */}
              <TableCell>Categoria</TableCell>
              <TableCell>Texto da Frase</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {frasesFiltradas.map(frase => (
              <TableRow
                key={frase.id}
                hover
                onClick={() => handleSelectRow(frase.id)}
                selected={selectedPhraseIds.includes(frase.id)}
                sx={{ cursor: 'pointer' }}
              >
                <TableCell padding="checkbox">
                  <Checkbox
                    checked={selectedPhraseIds.includes(frase.id)}
                  />
                </TableCell>
                <TableCell>{frase.id_local}</TableCell> {/* Exibe o id_local */}
                <TableCell>{frase.categoria}</TableCell>
                <TableCell>{frase.texto_frase}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      <PhraseEditorDialog
        open={isDialogOpen}
        onClose={handleCloseDialog}
        onSave={handleSavePhrase}
        phrase={editingPhrase}
      />
    </Box>
  );
}