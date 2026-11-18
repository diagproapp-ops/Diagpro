import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Typography } from '@mui/material';

type SenhaEventoModalProps = {
  open: boolean;
  onClose: () => void;
  senha: string;
  setSenha: (v: string) => void;
  error?: string | null;
  onSubmit: () => void;
};

export default function SenhaEventoModal({ open, onClose, senha, setSenha, error, onSubmit }: SenhaEventoModalProps) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Senha do Evento</DialogTitle>
      <DialogContent>
        <Typography sx={{ mb: 2 }}>
          Digite a senha para acessar os detalhes do evento.
        </Typography>
        <TextField
          type="password"
          label="Senha"
          value={senha}
          onChange={e => setSenha(e.target.value.replace(/\n/g, ""))}
          fullWidth
          autoFocus
          error={!!error}
          helperText={error}
          variant="outlined"
          margin="normal"
          size="medium"
          inputProps={{
            maxLength: 100,
            style: { height: 24, boxSizing: "border-box" },
            autoComplete: "new-password"
          }}
          sx={{
            '& .MuiInputBase-root': { minHeight: 48 },
            '& input': { minHeight: 24 }
          }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onSubmit} variant="contained">Entrar</Button>
        <Button onClick={onClose}>Cancelar</Button>
      </DialogActions>
    </Dialog>
  );
}