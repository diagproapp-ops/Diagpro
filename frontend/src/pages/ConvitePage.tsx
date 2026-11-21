import React, { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Checkbox, CircularProgress, Divider, FormControlLabel, Link, List, ListItem, ListItemText,
  Paper, Stack, TextField, Typography,
} from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';
import { CampoFoto, ROTULO_PAPEL, mensagemDaApi, validarFoto } from '../components/usuarios/comum';

type Info = {
  tipo: 'cadastro' | 'senha';
  banca: string;
  role?: string | null;
  email: string;
  nome?: string | null;
  expira_em: string;
  regras_senha: string[];
  conta_existente?: boolean;
};

// Link do convite (público, uso único): a pessoa se cadastra com os PRÓPRIOS dados, senha e foto; quem já tem
// conta em outra banca entra para aceitar; tipo 'senha' cria uma nova senha. O administrador aprova depois.
const ConvitePage: React.FC = () => {
  const { token = '' } = useParams();
  const navigate = useNavigate();
  const [info, setInfo] = useState<Info | null>(null);
  const [erroLink, setErroLink] = useState<string | null>(null);
  const [modo, setModo] = useState<'novo' | 'existente'>('novo');
  const [form, setForm] = useState({ full_name: '', username: '', password: '', confirma: '', phone: '', cpf: '',
                                     birth_date: '', institution: '', specialty: '', codigo: '' });
  const [foto, setFoto] = useState<File | null>(null);
  const [erroFoto, setErroFoto] = useState<string | null>(null);
  const [termos, setTermos] = useState({ conf: false, vaz: false });
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [pronto, setPronto] = useState<string | null>(null);

  useEffect(() => {
    api.get<Info>(`/convites/publico/${encodeURIComponent(token)}`)
      .then(({ data }) => {
        setInfo(data);
        setModo(data.conta_existente ? 'existente' : 'novo');
        if (data.nome) setForm(f => ({ ...f, full_name: data.nome || '' }));
      })
      .catch((e) => setErroLink(mensagemDaApi(e, 'Este link expirou ou já foi usado.')));
  }, [token]);

  const campo = (nome: keyof typeof form, rotulo: string, extra: any = {}) => (
    <TextField label={rotulo} value={form[nome]} fullWidth
      onChange={(e) => setForm(f => ({ ...f, [nome]: e.target.value }))} {...extra} />
  );

  const enviar = async () => {
    setErro(null);
    if (info?.tipo === 'senha') {
      if (form.password !== form.confirma) { setErro('As senhas não conferem.'); return; }
      setEnviando(true);
      try {
        const { data } = await api.post(`/convites/publico/${encodeURIComponent(token)}/senha`, { nova_senha: form.password });
        setPronto(data.mensagem);
      } catch (e: any) { setErro(mensagemDaApi(e, 'Não foi possível criar a senha.')); }
      finally { setEnviando(false); }
      return;
    }
    const fd = new FormData();
    if (modo === 'novo') {
      const problemaFoto = validarFoto(foto);
      if (problemaFoto) { setErroFoto(problemaFoto); return; }
      if (form.password !== form.confirma) { setErro('As senhas não conferem.'); return; }
      if (!termos.conf || !termos.vaz) { setErro('Aceite os dois termos para continuar.'); return; }
      ['username', 'password', 'full_name', 'phone', 'cpf', 'birth_date', 'institution', 'specialty'].forEach((k) => {
        const v = (form as any)[k];
        if (v) fd.append(k, v);
      });
      fd.append('accepted_confidentiality', 'true');
      fd.append('accepted_data_leak', 'true');
      fd.append('foto', foto as File);
    } else {
      fd.append('username', form.username);
      fd.append('password', form.password);
      if (form.codigo) fd.append('codigo', form.codigo);
      if (foto) {
        const problemaFoto = validarFoto(foto);
        if (problemaFoto) { setErroFoto(problemaFoto); return; }
        fd.append('foto', foto);
      }
    }
    setEnviando(true);
    try {
      const rota = modo === 'novo' ? 'cadastro' : 'aceitar';
      const { data } = await api.post(`/convites/publico/${encodeURIComponent(token)}/${rota}`, fd);
      setPronto(data.mensagem);
    } catch (e: any) {
      setErro(mensagemDaApi(e, 'Não foi possível concluir. Confira os dados.'));
    } finally {
      setEnviando(false);
    }
  };

  const podeEnviar = info?.tipo === 'senha'
    ? !!form.password && !!form.confirma
    : modo === 'novo'
      ? !!form.full_name.trim() && !!form.username.trim() && !!form.password && !!form.confirma && !!foto && termos.conf && termos.vaz
      : !!form.username.trim() && !!form.password;

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', p: { xs: 2, md: 5 }, bgcolor: 'background.default' }}>
      <Paper sx={{ width: '100%', maxWidth: 680, p: { xs: 3, md: 4.5 }, borderRadius: 4 }}>
        <Typography variant="h5" fontWeight={800}>DiagPro</Typography>
        {!info && !erroLink && <Stack alignItems="center" sx={{ py: 6 }}><CircularProgress /></Stack>}
        {erroLink && (
          <>
            <Alert severity="warning" sx={{ mt: 3 }}>{erroLink}</Alert>
            <Button sx={{ mt: 2 }} onClick={() => navigate('/login')}>Ir para o login</Button>
          </>
        )}
        {pronto && (
          <>
            <Alert severity="success" sx={{ mt: 3 }}>{pronto}</Alert>
            <Button sx={{ mt: 2 }} variant="contained" onClick={() => navigate('/login')}>Ir para o login</Button>
          </>
        )}
        {info && !pronto && (
          <>
            {info.tipo === 'senha' ? (
              <>
                <Typography variant="h6" fontWeight={700} sx={{ mt: 2 }}>Crie a sua nova senha</Typography>
                <Typography variant="body2" color="text.secondary">Conta {info.email}. A verificação em duas etapas continua valendo.</Typography>
              </>
            ) : (
              <>
                <Typography variant="h6" fontWeight={700} sx={{ mt: 2 }}>Convite de {info.banca}</Typography>
                <Typography variant="body2" color="text.secondary">
                  Para atuar como <b>{ROTULO_PAPEL[info.role || ''] || info.role}</b> · convite enviado para {info.email}.
                  Depois que você enviar, o administrador da banca confere e libera o acesso.
                </Typography>
                {info.role !== 'administrador geral' && (
                  <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                    <Button size="small" variant={modo === 'novo' ? 'contained' : 'outlined'} onClick={() => setModo('novo')}>Ainda não tenho conta</Button>
                    <Button size="small" variant={modo === 'existente' ? 'contained' : 'outlined'} onClick={() => setModo('existente')}>Já uso o DiagPro em outra banca</Button>
                  </Stack>
                )}
              </>
            )}
            <Divider sx={{ my: 2.5 }} />

            {info.tipo === 'cadastro' && modo === 'novo' && (
              <Stack spacing={2}>
                <CampoFoto arquivo={foto} onChange={(f) => { setFoto(f); setErroFoto(null); }} erro={erroFoto} />
                {campo('full_name', 'Nome completo *', { autoComplete: 'name' })}
                {campo('username', 'Usuário para entrar *', { autoComplete: 'username', helperText: 'É com ele que você vai entrar no DiagPro.' })}
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
                  {campo('password', 'Senha *', { type: 'password', autoComplete: 'new-password' })}
                  {campo('confirma', 'Repita a senha *', { type: 'password', autoComplete: 'new-password' })}
                  {campo('phone', 'Telefone', { autoComplete: 'tel' })}
                  {campo('cpf', 'CPF')}
                  {campo('birth_date', 'Data de nascimento', { type: 'date', InputLabelProps: { shrink: true } })}
                  {campo('institution', 'Instituição')}
                </Box>
                {campo('specialty', 'Especialidade / área')}
              </Stack>
            )}
            {info.tipo === 'cadastro' && modo === 'existente' && (
              <Stack spacing={2}>
                <Typography variant="body2" color="text.secondary">
                  Entre com a sua conta do DiagPro para aceitar. A conta precisa ser a do e-mail que recebeu o convite.
                </Typography>
                {campo('username', 'Usuário', { autoComplete: 'username' })}
                {campo('password', 'Senha', { type: 'password', autoComplete: 'current-password' })}
                <TextField label="Código do autenticador (2FA)" value={form.codigo} inputProps={{ inputMode: 'numeric', maxLength: 6 }}
                  onChange={(e) => setForm(f => ({ ...f, codigo: e.target.value.replace(/\D/g, '').slice(0, 6) }))}
                  helperText="Se você já ativou a verificação em duas etapas." />
                <Typography variant="body2" color="text.secondary">Ainda não tem foto na sua conta? Envie agora (obrigatória):</Typography>
                <CampoFoto arquivo={foto} onChange={(f) => { setFoto(f); setErroFoto(null); }} erro={erroFoto} />
              </Stack>
            )}
            {info.tipo === 'senha' && (
              <Stack spacing={2}>
                {campo('password', 'Nova senha', { type: 'password', autoComplete: 'new-password' })}
                {campo('confirma', 'Repita a nova senha', { type: 'password', autoComplete: 'new-password' })}
              </Stack>
            )}

            {(info.tipo === 'senha' || modo === 'novo') && info.regras_senha?.length > 0 && (
              <List dense sx={{ mt: 1 }}>
                {info.regras_senha.map(r => (
                  <ListItem key={r} disableGutters>
                    <ListItemText primary={`• ${r}`} primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }} />
                  </ListItem>
                ))}
              </List>
            )}
            {info.tipo === 'cadastro' && modo === 'novo' && (
              <Stack sx={{ mt: 1 }}>
                <FormControlLabel control={<Checkbox checked={termos.conf} onChange={(e) => setTermos(t => ({ ...t, conf: e.target.checked }))} />}
                  label={<Typography variant="body2">Comprometo-me a manter sigilo absoluto sobre as provas e questões a que tiver acesso.</Typography>} />
                <FormControlLabel control={<Checkbox checked={termos.vaz} onChange={(e) => setTermos(t => ({ ...t, vaz: e.target.checked }))} />}
                  label={<Typography variant="body2">Sei que vazar qualquer conteúdo gera responsabilidade civil e criminal. Li os{' '}
                    <Link href="/termos" target="_blank" rel="noopener">termos</Link> e a{' '}
                    <Link href="/privacidade" target="_blank" rel="noopener">política de privacidade</Link>.</Typography>} />
              </Stack>
            )}
            {erro && <Alert severity="error" sx={{ mt: 2 }}>{erro}</Alert>}
            <Button variant="contained" size="large" sx={{ mt: 3 }} fullWidth disabled={!podeEnviar || enviando} onClick={enviar}>
              {enviando ? 'Enviando...' : info.tipo === 'senha' ? 'Criar senha' : modo === 'novo' ? 'Enviar cadastro' : 'Aceitar convite'}
            </Button>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1.5 }}>
              Link válido até {new Date(info.expira_em).toLocaleString('pt-BR')} e uma única vez.
            </Typography>
          </>
        )}
      </Paper>
    </Box>
  );
};

export default ConvitePage;
