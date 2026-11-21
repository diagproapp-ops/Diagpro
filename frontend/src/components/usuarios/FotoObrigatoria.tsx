import React, { useState } from 'react';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';
import api from '../../api';
import { useAuth } from '../../contexts/AuthContext';
import { CampoFoto, mensagemDaApi, validarFoto } from './comum';

// Foto obrigatória por segurança: quem entrou e ainda não tem foto (contas antigas) envia antes de continuar.
const FotoObrigatoria: React.FC = () => {
  const { user, logout } = useAuth();
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [enviada, setEnviada] = useState(false);

  if (!user || (user as any).tem_foto !== false || enviada) return null;

  const enviar = async () => {
    const problema = validarFoto(arquivo);
    if (problema) { setErro(problema); return; }
    setEnviando(true);
    setErro(null);
    try {
      const fd = new FormData();
      fd.append('foto', arquivo as File);
      await api.put('/users/me/foto', fd);
      setEnviada(true);
    } catch (e: any) {
      setErro(mensagemDaApi(e, 'Não foi possível enviar a foto.'));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Dialog open maxWidth="sm" fullWidth disableEscapeKeyDown>
      <DialogTitle sx={{ fontWeight: 800 }}>Envie a sua foto</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5 }}>
          Por segurança, toda conta do DiagPro precisa de uma foto: é com ela que a banca confere quem tem acesso às provas.
          A foto fica guardada cifrada e só é vista pelos administradores das bancas em que você trabalha.
        </Typography>
        <CampoFoto arquivo={arquivo} onChange={(f) => { setArquivo(f); setErro(null); }} erro={erro} />
        {erro && <Alert severity="error" sx={{ mt: 2 }}>{erro}</Alert>}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button color="inherit" onClick={() => { logout(); window.location.assign('/login'); }}>Sair</Button>
        <Button variant="contained" onClick={enviar} disabled={enviando || !arquivo}>{enviando ? 'Enviando...' : 'Enviar foto'}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default FotoObrigatoria;
