import React, { useEffect, useState } from 'react';
import { Alert, Box, Button, Chip, CircularProgress, FormControlLabel, MenuItem, Switch, TextField, Typography } from '@mui/material';
import api from '../../api';
import { Aviso, BarraSalvar, Secao, mensagemErro } from './configComum';

type Email = {
  habilitado: boolean; host: string; porta: number; seguranca: 'starttls' | 'ssl' | 'nenhuma'; usuario: string;
  remetente_nome: string; remetente_email: string; url_sistema: string; senha_definida: boolean;
};

// Servidor de e-mail dos avisos (admin geral, visão global). A senha fica cifrada e nunca volta para a tela.
const PlataformaEmailTab: React.FC = () => {
  const [original, setOriginal] = useState<Email | null>(null);
  const [em, setEm] = useState<Email | null>(null);
  const [novaSenha, setNovaSenha] = useState('');
  const [removerSenha, setRemoverSenha] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [testando, setTestando] = useState(false);
  const [msg, setMsg] = useState<{ texto: string; tipo: 'success' | 'error' } | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const aplicar = (data: any) => { setOriginal(data.email); setEm(data.email); setNovaSenha(''); setRemoverSenha(false); };
  useEffect(() => {
    api.get('/config/plataforma').then(({ data }) => aplicar(data))
      .catch(e => setErro(mensagemErro(e, 'Não foi possível carregar as configurações.')));
  }, []);

  if (erro) return <Alert severity="warning">{erro}</Alert>;
  if (!em || !original) return <CircularProgress />;

  const alterado = JSON.stringify(em) !== JSON.stringify(original) || !!novaSenha || removerSenha;

  const salvar = async () => {
    setSalvando(true);
    try {
      const { senha_definida, ...resto } = em;
      const corpo: any = { ...resto };
      if (removerSenha) corpo.senha = null; else if (novaSenha) corpo.senha = novaSenha;
      const { data } = await api.put('/config/plataforma', { email: corpo });
      aplicar(data);
      setMsg({ texto: 'Configurações de e-mail salvas.', tipo: 'success' });
    } catch (e: any) {
      setMsg({ texto: mensagemErro(e), tipo: 'error' });
    } finally {
      setSalvando(false);
    }
  };

  const testar = async () => {
    setTestando(true);
    try {
      const { data } = await api.post('/config/email/testar');
      setMsg({ texto: `E-mail de teste enviado para ${data.para}. Confira a caixa de entrada (e o spam).`, tipo: 'success' });
    } catch (e: any) {
      setMsg({ texto: mensagemErro(e, 'Falha no envio de teste.'), tipo: 'error' });
    } finally {
      setTestando(false);
    }
  };

  const campo = (k: keyof Email) => (e: React.ChangeEvent<HTMLInputElement>) => setEm({ ...em, [k]: e.target.value });

  return (
    <>
      <Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>E-mail de avisos</Typography>
      <Alert severity="info" sx={{ mb: 2.5 }}>
        Os avisos sempre aparecem no sino do sistema. Com o e-mail ligado, também são enviados para o e-mail de cada
        pessoa, conforme as preferências dela. Os e-mails nunca levam conteúdo de prova, só o aviso e o link.
      </Alert>

      <Secao titulo="Envio" descricao="Use o servidor SMTP do seu provedor de e-mail (ex.: Google Workspace, Microsoft 365, Amazon SES).">
        <FormControlLabel control={<Switch checked={em.habilitado} onChange={e => setEm({ ...em, habilitado: e.target.checked })} />}
          label={em.habilitado ? 'Envio de e-mails ligado' : 'Envio de e-mails desligado'} />
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '2fr 1fr 1fr' }, gap: 2, mt: 2 }}>
          <TextField label="Servidor SMTP" value={em.host} onChange={campo('host')} placeholder="smtp.seuprovedor.com" />
          <TextField label="Porta" type="number" value={em.porta} onChange={e => setEm({ ...em, porta: Number(e.target.value) })} />
          <TextField select label="Segurança" value={em.seguranca} onChange={e => setEm({ ...em, seguranca: e.target.value as Email['seguranca'] })}>
            <MenuItem value="starttls">STARTTLS (porta 587)</MenuItem>
            <MenuItem value="ssl">SSL/TLS (porta 465)</MenuItem>
            <MenuItem value="nenhuma">Nenhuma (só servidor local)</MenuItem>
          </TextField>
        </Box>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2, mt: 2 }}>
          <TextField label="Usuário" value={em.usuario} onChange={campo('usuario')} autoComplete="off" />
          <Box>
            <TextField fullWidth type="password" autoComplete="new-password" value={novaSenha}
              label={em.senha_definida ? 'Trocar senha' : 'Senha'}
              onChange={e => { setNovaSenha(e.target.value); setRemoverSenha(false); }} />
            <Box sx={{ mt: 0.75, display: 'flex', gap: 1, alignItems: 'center' }}>
              {removerSenha ? <Chip size="small" color="warning" label="Será removida ao salvar" />
                : em.senha_definida ? <Chip size="small" color="success" label="Senha salva" /> : <Chip size="small" label="Sem senha" />}
              {em.senha_definida && <Button size="small" color="warning" onClick={() => setRemoverSenha(!removerSenha)}>{removerSenha ? 'Manter' : 'Remover'}</Button>}
            </Box>
          </Box>
        </Box>
      </Secao>

      <Secao titulo="Remetente e links">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
          <TextField label="Nome do remetente" value={em.remetente_nome} onChange={campo('remetente_nome')} />
          <TextField label="E-mail do remetente" value={em.remetente_email} onChange={campo('remetente_email')} placeholder="avisos@suabanca.com.br" />
          <TextField label="Endereço do DiagPro" value={em.url_sistema} onChange={campo('url_sistema')}
            helperText="Usado nos links dos e-mails (ex.: https://diagpro.suabanca.com.br)" sx={{ gridColumn: { sm: '1 / 3' } }} />
        </Box>
      </Secao>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
        <Button variant="outlined" onClick={testar} disabled={testando || alterado || !em.host}>
          {testando ? 'Enviando...' : 'Enviar e-mail de teste para mim'}
        </Button>
        <BarraSalvar salvando={salvando} onSalvar={salvar} alterado={alterado} />
      </Box>
      {alterado && <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>Salve antes de enviar o teste.</Typography>}
      <Aviso msg={msg} onFechar={() => setMsg(null)} />
    </>
  );
};

export default PlataformaEmailTab;
