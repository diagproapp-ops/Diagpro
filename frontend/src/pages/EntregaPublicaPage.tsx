import React, { useEffect, useState } from 'react';
import { Alert, Box, Button, CircularProgress, Paper, TextField, Typography } from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import { useParams } from 'react-router-dom';
import api from '../api';

// Página pública de download de uma entrega (ex.: gráfica): pede o código de acesso.
const EntregaPublicaPage: React.FC = () => {
  const { id } = useParams();
  const [info, setInfo] = useState<any>(null);
  const [codigo, setCodigo] = useState('');
  const [baixando, setBaixando] = useState(false);
  const [msg, setMsg] = useState<{ texto: string; tipo: 'success' | 'error' } | null>(null);

  const carregar = () => api.get(`/entrega/${id}/info`).then(({ data }) => setInfo(data)).catch(() => setInfo({ situacao: 'invalida' }));
  useEffect(() => { carregar(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const baixar = async () => {
    setBaixando(true);
    setMsg(null);
    try {
      const { data } = await api.post(`/entrega/${id}/baixar`, { codigo }, { responseType: 'blob' });
      const url = URL.createObjectURL(data);
      const a = document.createElement('a');
      a.href = url;
      a.download = info?.nome_arquivo || 'pacote.zip';
      a.click();
      URL.revokeObjectURL(url);
      setMsg({ texto: 'Download iniciado. Para abrir o ZIP, use a senha que a banca enviou separadamente.', tipo: 'success' });
      setCodigo('');
    } catch (e: any) {
      let det = 'Não foi possível baixar.';
      try { det = JSON.parse(await e.response.data.text()).detail || det; } catch { /* mantém */ }
      setMsg({ texto: det, tipo: 'error' });
    } finally {
      setBaixando(false);
      carregar();
    }
  };

  const ativa = info?.situacao === 'ativa';
  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default', display: 'flex', alignItems: 'center', justifyContent: 'center', p: 2 }}>
      <Paper sx={{ p: 4, maxWidth: 480, width: '100%', borderRadius: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
          <LockOutlinedIcon color="primary" />
          <Typography variant="h5" fontWeight={800}>Entrega segura DiagPro</Typography>
        </Box>
        {!info ? <CircularProgress /> : !ativa ? (
          <Alert severity="warning">
            {info.situacao === 'invalida' ? 'Link inválido.' : 'Este link não está mais disponível (vencido, já usado ou revogado). Peça um novo à banca.'}
          </Alert>
        ) : (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Arquivo: <b>{info.nome_arquivo}</b><br />
              Vale até {new Date(info.expira_em).toLocaleString('pt-BR')} • {info.downloads_restantes} download(s) restante(s)
            </Typography>
            <TextField fullWidth label="Código de acesso" value={codigo} placeholder="XXXX-XXXX-XXXX" autoComplete="off"
              inputProps={{ maxLength: 20, style: { fontFamily: 'monospace', letterSpacing: 2 } }}
              onChange={e => setCodigo(e.target.value.toUpperCase())} sx={{ mb: 2 }} />
            <Button fullWidth variant="contained" size="large" onClick={baixar} disabled={baixando || codigo.replace(/[^A-Z0-9]/g, '').length < 12}>
              {baixando ? 'Baixando...' : 'Baixar pacote'}
            </Button>
          </>
        )}
        {msg && <Alert severity={msg.tipo} sx={{ mt: 2 }}>{msg.texto}</Alert>}
      </Paper>
    </Box>
  );
};

export default EntregaPublicaPage;
