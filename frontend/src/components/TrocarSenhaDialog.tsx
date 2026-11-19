import React, { useEffect, useMemo, useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Alert, List, ListItem,
  ListItemIcon, ListItemText, Typography,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import api from '../api';

interface Props {
  open: boolean;
  token2fa: string;
  onConcluido: (dados: any) => Promise<void> | void;
  onCancelar: (mensagem?: string) => void;
}

// Troca obrigatória logo depois do 2FA (senha provisória, vencida ou fora da política).
// O servidor é quem valida de verdade; aqui a lista só ajuda a pessoa enquanto digita.
const TrocarSenhaDialog: React.FC<Props> = ({ open, token2fa, onConcluido, onCancelar }) => {
  const [nova, setNova] = useState('');
  const [confirma, setConfirma] = useState('');
  const [erros, setErros] = useState<string[]>([]);
  const [enviando, setEnviando] = useState(false);
  const [minimo, setMinimo] = useState(12);

  useEffect(() => {
    api.get('/auth/senha/regras').then(({ data }) => setMinimo(data.tamanho_minimo || 12)).catch(() => {});
  }, []);

  const checagens = useMemo(() => {
    const tipos = [/[A-Z]/, /[a-z]/, /\d/, /[^A-Za-z0-9]/].filter(r => r.test(nova)).length;
    return [
      { ok: nova.length >= minimo, texto: `Pelo menos ${minimo} caracteres` },
      { ok: tipos >= 3, texto: '3 destes tipos: maiúscula, minúscula, número, símbolo' },
      { ok: nova.length > 0 && nova === confirma, texto: 'As duas senhas são iguais' },
    ];
  }, [nova, confirma, minimo]);

  const enviar = async () => {
    setErros([]);
    setEnviando(true);
    try {
      const { data } = await api.post('/auth/senha/trocar', { token_2fa: token2fa, nova_senha: nova });
      await onConcluido(data);
    } catch (e: any) {
      const status = e?.response?.status;
      const det = e?.response?.data?.detail;
      if (status === 401) { onCancelar('O tempo para trocar a senha acabou. Entre de novo.'); return; }
      setErros(det && typeof det === 'object' ? (det.problemas || [det.mensagem]) : [det || 'Não foi possível trocar a senha.']);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Dialog open={open} maxWidth="xs" fullWidth>
      <DialogTitle>Crie uma nova senha</DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" sx={{ mb: 2 }}>
          Sua senha é provisória, venceu ou não atende à política de segurança. Crie uma nova para continuar.
          Ela não pode conter seu usuário/e-mail, ser comum ou repetir uma das últimas senhas.
        </Typography>
        <TextField label="Nova senha" type="password" fullWidth autoFocus value={nova}
                   onChange={e => { setNova(e.target.value); setErros([]); }} autoComplete="new-password" sx={{ mb: 2 }} />
        <TextField label="Repita a nova senha" type="password" fullWidth value={confirma}
                   onChange={e => { setConfirma(e.target.value); setErros([]); }} autoComplete="new-password"
                   onKeyDown={e => { if (e.key === 'Enter' && checagens.every(c => c.ok) && !enviando) enviar(); }} />
        <List dense sx={{ mt: 1 }}>
          {checagens.map(c => (
            <ListItem key={c.texto} disableGutters>
              <ListItemIcon sx={{ minWidth: 32 }}>
                {c.ok ? <CheckCircleIcon color="success" fontSize="small" /> : <RadioButtonUncheckedIcon fontSize="small" />}
              </ListItemIcon>
              <ListItemText primary={c.texto} primaryTypographyProps={{ variant: 'body2' }} />
            </ListItem>
          ))}
        </List>
        {erros.length > 0 && <Alert severity="error">{erros.map(e => <div key={e}>{e}</div>)}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => onCancelar()}>Cancelar</Button>
        <Button variant="contained" onClick={enviar} disabled={!checagens.every(c => c.ok) || enviando}>
          {enviando ? 'Salvando...' : 'Salvar e entrar'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TrocarSenhaDialog;
