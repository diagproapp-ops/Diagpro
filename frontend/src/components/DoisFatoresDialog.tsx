import React, { useEffect, useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Typography, Box, Alert,
  CircularProgress, Stack, FormControlLabel, Checkbox, Link,
} from '@mui/material';
import api from '../api';

type DadosAcesso = { access_token?: string; role?: string; tenant_id?: number | null; codigos_recuperacao_restantes?: number; etapa?: string; token_2fa?: string };

interface Props {
  open: boolean;
  etapa: '2fa' | 'cadastro_2fa';
  token2fa: string;
  onConcluido: (dados: DadosAcesso) => Promise<void> | void;
  onCancelar: (mensagem?: string) => void;
}

// Verificação em duas etapas (obrigatória para todos): cadastro do autenticador no primeiro acesso
// e código de 6 dígitos (ou código de recuperação) nos acessos seguintes.
const DoisFatoresDialog: React.FC<Props> = ({ open, etapa, token2fa, onConcluido, onCancelar }) => {
  const [qr, setQr] = useState<string>('');
  const [segredo, setSegredo] = useState<string>('');
  const [codigo, setCodigo] = useState('');
  const [usarRecuperacao, setUsarRecuperacao] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [codigosRecuperacao, setCodigosRecuperacao] = useState<string[] | null>(null);
  const [guardou, setGuardou] = useState(false);
  const [acessoPendente, setAcessoPendente] = useState<DadosAcesso | null>(null);

  const tratarErro = (e: any) => {
    const status = e?.response?.status;
    const detalhe = e?.response?.data?.detail;
    if (status === 401) {
      onCancelar('O tempo para a verificação acabou. Entre de novo com usuário e senha.');
      return;
    }
    setErro(typeof detalhe === 'string' ? detalhe : 'Não foi possível verificar o código.');
  };

  useEffect(() => {
    if (!open || etapa !== 'cadastro_2fa') return;
    setCarregando(true);
    api.post('/auth/2fa/cadastro/iniciar', { token_2fa: token2fa })
      .then(({ data }) => { setQr(data.qr_code); setSegredo(data.segredo); })
      .catch(tratarErro)
      .finally(() => setCarregando(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, etapa, token2fa]);

  const enviar = async () => {
    setErro(null);
    setCarregando(true);
    try {
      if (etapa === 'cadastro_2fa') {
        const { data } = await api.post('/auth/2fa/cadastro/confirmar', { token_2fa: token2fa, codigo });
        setCodigosRecuperacao(data.codigos_recuperacao || []);
        setAcessoPendente(data);
      } else {
        const { data } = await api.post('/auth/2fa/verificar', { token_2fa: token2fa, codigo });
        await onConcluido(data);
      }
    } catch (e: any) {
      tratarErro(e);
    } finally {
      setCarregando(false);
    }
  };

  const baixarCodigos = () => {
    const texto = `Códigos de recuperação do DiagPro\r\nCada código vale UMA vez. Guarde em local seguro.\r\n\r\n${(codigosRecuperacao || []).join('\r\n')}\r\n`;
    const url = URL.createObjectURL(new Blob([texto], { type: 'text/plain' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'diagpro-codigos-recuperacao.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const codigoValido = usarRecuperacao ? codigo.replace(/[^A-Za-z0-9]/g, '').length === 10 : /^\d{6}$/.test(codigo);

  // Tela final do cadastro: códigos de recuperação (mostrados uma única vez)
  if (codigosRecuperacao) {
    return (
      <Dialog open={open} maxWidth="sm" fullWidth>
        <DialogTitle>Guarde seus códigos de recuperação</DialogTitle>
        <DialogContent dividers>
          <Alert severity="warning" sx={{ mb: 2 }}>
            Eles são mostrados só agora. Use um deles se perder o celular. Cada código vale uma única vez.
          </Alert>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1, fontFamily: 'monospace', fontSize: 16, mb: 2 }}>
            {codigosRecuperacao.map(c => <Box key={c}>{c}</Box>)}
          </Box>
          <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
            <Button variant="outlined" onClick={() => navigator.clipboard?.writeText(codigosRecuperacao.join('\n'))}>Copiar</Button>
            <Button variant="outlined" onClick={baixarCodigos}>Baixar .txt</Button>
          </Stack>
          <FormControlLabel
            control={<Checkbox checked={guardou} onChange={e => setGuardou(e.target.checked)} />}
            label="Guardei meus códigos em local seguro"
          />
        </DialogContent>
        <DialogActions>
          <Button variant="contained" disabled={!guardou || !acessoPendente} onClick={() => acessoPendente && onConcluido(acessoPendente)}>
            Entrar no sistema
          </Button>
        </DialogActions>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} maxWidth="xs" fullWidth>
      <DialogTitle>
        {etapa === 'cadastro_2fa' ? 'Ative a verificação em duas etapas' : 'Verificação em duas etapas'}
      </DialogTitle>
      <DialogContent dividers>
        {etapa === 'cadastro_2fa' && (
          <>
            <Typography variant="body2" sx={{ mb: 1.5 }}>
              Por segurança, todo acesso ao DiagPro exige um código do celular.
              Instale um aplicativo autenticador (Google Authenticator, Microsoft Authenticator ou Authy) e leia o QR Code:
            </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 1.5, minHeight: 180 }}>
              {qr ? <Box component="img" src={qr} alt="QR Code do autenticador" sx={{ width: 200, height: 200, bgcolor: '#fff', p: 1, borderRadius: 1 }} />
                  : <CircularProgress />}
            </Box>
            {segredo && (
              <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 2, wordBreak: 'break-all' }}>
                Sem câmera? Digite esta chave no aplicativo: <b style={{ fontFamily: 'monospace' }}>{segredo}</b>
              </Typography>
            )}
            <Typography variant="body2" sx={{ mb: 1 }}>Depois, digite o código de 6 dígitos que aparece no aplicativo:</Typography>
          </>
        )}
        {etapa === '2fa' && (
          <Typography variant="body2" sx={{ mb: 1.5 }}>
            {usarRecuperacao ? 'Digite um dos seus códigos de recuperação:' : 'Digite o código de 6 dígitos do seu aplicativo autenticador:'}
          </Typography>
        )}
        <TextField
          autoFocus
          fullWidth
          value={codigo}
          onChange={e => setCodigo(usarRecuperacao ? e.target.value.toUpperCase().slice(0, 11) : e.target.value.replace(/\D/g, '').slice(0, 6))}
          onKeyDown={e => { if (e.key === 'Enter' && codigoValido && !carregando) enviar(); }}
          placeholder={usarRecuperacao ? 'XXXXX-XXXXX' : '000000'}
          inputProps={{ inputMode: usarRecuperacao ? 'text' : 'numeric', autoComplete: 'one-time-code',
                        style: { fontSize: 24, letterSpacing: 6, textAlign: 'center', fontFamily: 'monospace' } }}
        />
        {etapa === '2fa' && (
          <Link component="button" type="button" variant="body2" sx={{ mt: 1.5 }}
                onClick={() => { setUsarRecuperacao(v => !v); setCodigo(''); setErro(null); }}>
            {usarRecuperacao ? 'Usar o código do aplicativo' : 'Perdi o celular: usar código de recuperação'}
          </Link>
        )}
        {erro && <Alert severity="error" sx={{ mt: 2 }}>{erro}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => onCancelar()}>Cancelar</Button>
        <Button variant="contained" onClick={enviar} disabled={!codigoValido || carregando}>
          {carregando ? 'Verificando...' : etapa === 'cadastro_2fa' ? 'Ativar e entrar' : 'Entrar'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default DoisFatoresDialog;
