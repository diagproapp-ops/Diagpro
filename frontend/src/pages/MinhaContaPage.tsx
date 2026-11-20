import React, { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, Paper, Stack, TextField, Typography, List, ListItem, ListItemText,
} from '@mui/material';
import Layout from '../components/Layout';
import PreferenciasAvisos from '../components/PreferenciasAvisos';
import api from '../api';
import { useAuth } from '../contexts/AuthContext';
import { mensagemErro } from './SettingsTabs/configComum';

// Configurações PESSOAIS: valem só para quem está logado (qualquer perfil).
const MinhaContaPage: React.FC = () => {
  const { user } = useAuth();
  const [regras, setRegras] = useState<string[]>([]);
  const [sessao, setSessao] = useState<{ inatividade_minutos: number; sessao_maxima_horas: number } | null>(null);

  const [atual, setAtual] = useState('');
  const [nova, setNova] = useState('');
  const [confirma, setConfirma] = useState('');
  const [codigoSenha, setCodigoSenha] = useState('');
  const [msgSenha, setMsgSenha] = useState<{ tipo: 'success' | 'error'; texto: string } | null>(null);
  const [salvandoSenha, setSalvandoSenha] = useState(false);

  const [codigoRec, setCodigoRec] = useState('');
  const [novosCodigos, setNovosCodigos] = useState<string[] | null>(null);
  const [msgRec, setMsgRec] = useState<string | null>(null);

  useEffect(() => {
    api.get('/auth/senha/regras').then(({ data }) => setRegras(data.regras || [])).catch(() => {});
    api.get('/config/sessao').then(({ data }) => setSessao(data)).catch(() => {});
  }, []);

  const trocarSenha = async () => {
    setMsgSenha(null);
    if (nova !== confirma) { setMsgSenha({ tipo: 'error', texto: 'As duas senhas novas não são iguais.' }); return; }
    setSalvandoSenha(true);
    try {
      await api.post('/auth/senha/minha', { senha_atual: atual, nova_senha: nova, codigo: codigoSenha });
      setMsgSenha({ tipo: 'success', texto: 'Senha alterada. Use a nova senha no próximo login.' });
      setAtual(''); setNova(''); setConfirma(''); setCodigoSenha('');
    } catch (e: any) {
      setMsgSenha({ tipo: 'error', texto: mensagemErro(e, 'Não foi possível trocar a senha.') });
    } finally {
      setSalvandoSenha(false);
    }
  };

  const gerarCodigos = async () => {
    setMsgRec(null);
    try {
      const { data } = await api.post('/auth/2fa/codigos-recuperacao', { codigo: codigoRec });
      setNovosCodigos(data.codigos_recuperacao);
      setCodigoRec('');
    } catch (e: any) {
      setMsgRec(mensagemErro(e, 'Não foi possível gerar os códigos.'));
    }
  };

  const baixar = () => {
    const texto = `Códigos de recuperação do DiagPro\r\nCada código vale UMA vez. Guarde em local seguro.\r\n\r\n${(novosCodigos || []).join('\r\n')}\r\n`;
    const url = URL.createObjectURL(new Blob([texto], { type: 'text/plain' }));
    const a = document.createElement('a'); a.href = url; a.download = 'diagpro-codigos-recuperacao.txt'; a.click();
    URL.revokeObjectURL(url);
  };

  const card = { p: 3, mb: 3, borderRadius: 2 };
  return (
    <Layout>
      <Typography variant="h4" fontWeight={800} sx={{ mb: 3 }}>Minha conta</Typography>

      <Paper variant="outlined" sx={card}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1.5 }}>Meus dados</Typography>
        <Stack spacing={0.5}>
          <Typography><b>Nome:</b> {user?.full_name || '-'}</Typography>
          <Typography><b>Usuário:</b> {user?.username}</Typography>
          <Typography><b>E-mail:</b> {user?.email || '-'}</Typography>
          <Typography><b>Perfil:</b> {user?.role}</Typography>
          <Box><b>Verificação em duas etapas:</b>{' '}
            <Chip size="small" color={(user as any)?.totp_ativo ? 'success' : 'warning'} label={(user as any)?.totp_ativo ? 'Ativa' : 'Pendente'} />
          </Box>
          {sessao && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Sua sessão encerra após {sessao.inatividade_minutos} minutos sem uso e, mesmo em uso, depois de {sessao.sessao_maxima_horas} horas.
            </Typography>
          )}
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={card}>
        <Typography variant="subtitle1" fontWeight={700}>Trocar minha senha</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Por segurança, informe a senha atual e o código do seu aplicativo autenticador.
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2, maxWidth: 760 }}>
          <TextField type="password" label="Senha atual" value={atual} onChange={e => setAtual(e.target.value)} autoComplete="current-password" />
          <TextField label="Código do autenticador" value={codigoSenha} inputProps={{ inputMode: 'numeric', maxLength: 6 }}
            onChange={e => setCodigoSenha(e.target.value.replace(/\D/g, '').slice(0, 6))} autoComplete="one-time-code" />
          <TextField type="password" label="Nova senha" value={nova} onChange={e => setNova(e.target.value)} autoComplete="new-password" />
          <TextField type="password" label="Repita a nova senha" value={confirma} onChange={e => setConfirma(e.target.value)} autoComplete="new-password" />
        </Box>
        {regras.length > 0 && (
          <List dense sx={{ mt: 1 }}>
            {regras.map(r => <ListItem key={r} disableGutters><ListItemText primary={`• ${r}`} primaryTypographyProps={{ variant: 'body2', color: 'text.secondary' }} /></ListItem>)}
          </List>
        )}
        {msgSenha && <Alert severity={msgSenha.tipo} sx={{ my: 1.5 }}>{msgSenha.texto}</Alert>}
        <Button variant="contained" onClick={trocarSenha}
          disabled={salvandoSenha || !atual || !nova || !confirma || codigoSenha.length !== 6}>
          {salvandoSenha ? 'Salvando...' : 'Trocar senha'}
        </Button>
      </Paper>

      <Paper variant="outlined" sx={card}>
        <Typography variant="subtitle1" fontWeight={700}>Códigos de recuperação</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Gere novos códigos se usou vários ou acha que alguém viu os antigos. Os códigos antigos deixam de valer.
        </Typography>
        {novosCodigos ? (
          <>
            <Alert severity="warning" sx={{ mb: 2 }}>Guarde agora: eles não serão mostrados de novo.</Alert>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, max-content)', columnGap: 6, rowGap: 0.5, fontFamily: 'monospace', fontSize: 16, mb: 2 }}>
              {novosCodigos.map(c => <span key={c}>{c}</span>)}
            </Box>
            <Stack direction="row" spacing={1}>
              <Button variant="outlined" onClick={() => navigator.clipboard?.writeText(novosCodigos.join('\n'))}>Copiar</Button>
              <Button variant="outlined" onClick={baixar}>Baixar .txt</Button>
              <Button onClick={() => setNovosCodigos(null)}>Fechar</Button>
            </Stack>
          </>
        ) : (
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
            <TextField label="Código do autenticador" value={codigoRec} sx={{ maxWidth: 260 }}
              inputProps={{ inputMode: 'numeric', maxLength: 6 }}
              onChange={e => setCodigoRec(e.target.value.replace(/\D/g, '').slice(0, 6))} />
            <Button variant="contained" onClick={gerarCodigos} disabled={codigoRec.length !== 6}>Gerar novos códigos</Button>
          </Stack>
        )}
        {msgRec && <Alert severity="error" sx={{ mt: 2 }}>{msgRec}</Alert>}
      </Paper>

      <PreferenciasAvisos sx={card} />
    </Layout>
  );
};

export default MinhaContaPage;
