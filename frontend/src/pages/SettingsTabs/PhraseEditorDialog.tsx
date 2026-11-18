import React, { useState, useEffect } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Box } from '@mui/material';

// Usaremos a mesma interface, mas o 'id' será opcional,
// pois uma nova frase ainda não tem um.
interface Phrase {
  id?: number;
  categoria: string;
  texto_frase: string;
}

// Props que o nosso diálogo irá receber
interface PhraseEditorDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (phrase: Omit<Phrase, 'id'>) => void; // A função de salvar não precisa do ID inicial
  phrase: Phrase | null; // A frase a ser editada, ou null se for para adicionar uma nova
}

export default function PhraseEditorDialog({ open, onClose, onSave, phrase }: PhraseEditorDialogProps) {
  // Determina se estamos no modo de edição
  const isEditing = phrase !== null;
  
  // Estado para controlar os dados do formulário
  const [formData, setFormData] = useState({
    categoria: '',
    texto_frase: '',
  });

  // useEffect para popular o formulário quando uma frase é passada para edição
  useEffect(() => {
    if (isEditing && open) {
      setFormData({
        categoria: phrase.categoria,
        texto_frase: phrase.texto_frase,
      });
    } else {
      // Limpa o formulário ao abrir para "Adicionar"
      setFormData({
        categoria: '',
        texto_frase: '',
      });
    }
  }, [phrase, open, isEditing]); // Re-executa quando a frase ou o estado 'open' mudam

  // Manipulador para atualizar o estado do formulário
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setFormData(prevData => ({
      ...prevData,
      [name]: value,
    }));
  };

  // Manipulador para o botão Salvar
  const handleSave = () => {
    // Validação simples (pode ser melhorada)
    if (!formData.categoria || !formData.texto_frase) {
      alert('Por favor, preencha todos os campos.');
      return;
    }
    onSave(formData);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isEditing ? 'Editar Frase' : 'Adicionar Nova Frase'}</DialogTitle>
      <DialogContent>
        <Box component="form" noValidate autoComplete="off" sx={{ mt: 1 }}>
          <TextField
            required
            fullWidth
            margin="dense"
            id="categoria"
            name="categoria"
            label="Categoria"
            value={formData.categoria}
            onChange={handleChange}
          />
          <TextField
            required
            fullWidth
            margin="dense"
            id="texto_frase"
            name="texto_frase"
            label="Texto da Frase"
            multiline
            rows={4}
            value={formData.texto_frase}
            onChange={handleChange}
          />
        </Box>
      </DialogContent>
      <DialogActions sx={{ p: '0 24px 16px' }}>
        <Button onClick={onClose} variant="outlined">Cancelar</Button>
        <Button onClick={handleSave} variant="contained">Salvar</Button>
      </DialogActions>
    </Dialog>
  );
}