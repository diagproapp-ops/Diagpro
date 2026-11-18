import React, { useState } from 'react';
import { Box, Button, Typography, Paper, Dialog, DialogTitle, DialogContent, DialogActions, TextField } from '@mui/material';
import { useNavigate } from 'react-router-dom';

export default function EventManagerPage() {
  const navigate = useNavigate();

  // Exemplo de eventos (substitua pelo seu fetch real)
  const eventos = [
    { id_evento: 1, nome_evento: 'Concurso Prefeitura 2025' },
    { id_evento: 2, nome_evento: 'Vestibular ABC' },
  ];

  const [senhaModalOpen, setSenhaModalOpen] = useState(false);
  const [senha, setSenha] = useState('');
  const [eventoSelecionado, setEventoSelecionado] = useState<number | null>(null);
  const [senhaError, setSenhaError] = useState<string | null>(null);

  const handleDetalhesClick = (id_evento: number) => {
    setEventoSelecionado(id_evento);
    setSenhaModalOpen(true);
    setSenha('');
    setSenhaError(null);
  };

  const handleSenhaSubmit = () => {
    if (!senha) {
      setSenhaError('Digite a senha do evento');
      return;
    }
    // Aqui você pode validar a senha via backend, mas para navegação já pode passar a senha
    navigate(`/eventos/${eventoSelecionado}?senha=${encodeURIComponent(senha)}`);
    setSenhaModalOpen(false);
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Eventos</Typography>
        <Button
          variant="contained"
          color="success"
          onClick={() => navigate('/eventos/novo')}
        >
          + Novo Evento
        </Button>
      </Box>
      <Paper sx={{ p: 2 }}>
        {eventos.length === 0 ? (
          <Typography>Nenhum evento cadastrado.</Typography>
        ) : (
          <ul>
            {eventos.map(ev => (
              <li key={ev.id_evento}>
                <Button onClick={() => handleDetalhesClick(ev.id_evento)}>
                  {ev.nome_evento}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Paper>

      <Dialog open={senhaModalOpen} onClose={() => setSenhaModalOpen(false)} maxWidth="xs" fullWidth>
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
            error={!!senhaError}
            helperText={senhaError}
            variant="outlined"
            margin="normal"
            size="medium"
            inputProps={{
              maxLength: 100,
              style: { height: 40 }, // força altura de input normal
              autoComplete: "new-password",
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleSenhaSubmit} variant="contained">Entrar</Button>
          <Button onClick={() => setSenhaModalOpen(false)}>Cancelar</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}