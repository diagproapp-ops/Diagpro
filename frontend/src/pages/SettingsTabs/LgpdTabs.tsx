import React, { useEffect, useState } from 'react';
import { Alert, Box, CircularProgress, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography } from '@mui/material';
import api from '../../api';
import { Aviso, BarraSalvar, Secao, mensagemErro } from './configComum';

type Lgpd = { versao_termos: string; termos: string; politica: string; encarregado: string; retencao_dias: { notificacoes: number; sessoes: number; uso_ia: number } };

// Plataforma: textos legais com versão (mudar a versão pede novo aceite de todos) e prazos de retenção
export const PlataformaLgpdTab: React.FC = () => {
  const [original, setOriginal] = useState<Lgpd | null>(null);
  const [lg, setLg] = useState<Lgpd | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<{ texto: string; tipo: 'success' | 'error' } | null>(null);
  useEffect(() => { api.get('/config/plataforma').then(({ data }) => { setOriginal(data.lgpd); setLg(data.lgpd); }).catch(() => {}); }, []);
  if (!lg || !original) return <CircularProgress />;

  const textosMudaram = lg.termos !== original.termos || lg.politica !== original.politica;
  const salvar = async () => {
    if (textosMudaram && lg.versao_termos === original.versao_termos &&
      !window.confirm('Você mudou o texto sem mudar a versão. Quem já aceitou não verá o texto novo.\n\nSalvar assim mesmo?')) return;
    setSalvando(true);
    try {
      const { data } = await api.put('/config/plataforma', { lgpd: lg });
      setOriginal(data.lgpd); setLg(data.lgpd);
      setMsg({ texto: 'Configurações de privacidade salvas.', tipo: 'success' });
    } catch (e: any) {
      setMsg({ texto: mensagemErro(e), tipo: 'error' });
    } finally {
      setSalvando(false);
    }
  };
  const ret = (k: keyof Lgpd['retencao_dias']) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setLg({ ...lg, retencao_dias: { ...lg.retencao_dias, [k]: Number(e.target.value) } });

  return (
    <>
      <Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Privacidade (LGPD)</Typography>
      <Secao titulo="Termos de uso e política de privacidade" descricao="Aparecem nas páginas públicas /termos e /privacidade. Ao mudar a versão, todos precisam aceitar de novo no próximo acesso.">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '160px 1fr' }, gap: 2, mb: 2 }}>
          <TextField label="Versão" value={lg.versao_termos} onChange={e => setLg({ ...lg, versao_termos: e.target.value })} inputProps={{ maxLength: 20 }} />
          <TextField label="Encarregado de dados (nome e contato)" value={lg.encarregado} onChange={e => setLg({ ...lg, encarregado: e.target.value })} inputProps={{ maxLength: 300 }} />
        </Box>
        <TextField fullWidth multiline minRows={4} label="Termos de uso" value={lg.termos} sx={{ mb: 2 }} onChange={e => setLg({ ...lg, termos: e.target.value })} />
        <TextField fullWidth multiline minRows={5} label="Política de privacidade" value={lg.politica} onChange={e => setLg({ ...lg, politica: e.target.value })} />
      </Secao>
      <Secao titulo="Retenção (minimização de dados)" descricao="Depois desses prazos, os registros são apagados automaticamente.">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr 1fr' }, gap: 2 }}>
          <TextField type="number" label="Avisos (dias)" value={lg.retencao_dias.notificacoes} onChange={ret('notificacoes')} helperText="30 a 3650" />
          <TextField type="number" label="Acessos/IP (dias)" value={lg.retencao_dias.sessoes} onChange={ret('sessoes')} helperText="30 a 3650" />
          <TextField type="number" label="Uso da IA (dias)" value={lg.retencao_dias.uso_ia} onChange={ret('uso_ia')} helperText="90 a 3650" />
        </Box>
      </Secao>
      <BarraSalvar salvando={salvando} onSalvar={salvar} alterado={JSON.stringify(lg) !== JSON.stringify(original)} />
      <Aviso msg={msg} onFechar={() => setMsg(null)} />
    </>
  );
};

const ACOES: Record<string, string> = { exportacao: 'Exportou os próprios dados', anonimizacao: 'Anonimização', aceite_termos: 'Aceite dos termos', limpeza: 'Limpeza por retenção' };

// Banca: prestação de contas das operações de LGPD
export const BancaLgpdTab: React.FC = () => {
  const [itens, setItens] = useState<any[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => { api.get('/lgpd/registros').then(({ data }) => setItens(data)).catch(e => { setErro(mensagemErro(e, 'Não foi possível carregar.')); setItens([]); }); }, []);
  return (
    <>
      <Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Registros de LGPD</Typography>
      <Alert severity="info" sx={{ mb: 2 }}>
        Pedidos e operações sobre dados pessoais desta banca. Para eliminar os dados de alguém que saiu, use
        "Anonimizar" em Usuários e contas.
      </Alert>
      {erro && <Alert severity="warning" sx={{ mb: 2 }}>{erro}</Alert>}
      {!itens ? <CircularProgress /> : !itens.length ? <Typography color="text.secondary">Nenhum registro ainda.</Typography> : (
        <Table size="small">
          <TableHead><TableRow><TableCell>Quando</TableCell><TableCell>Operação</TableCell><TableCell>Titular</TableCell><TableCell>Feita por</TableCell></TableRow></TableHead>
          <TableBody>
            {itens.map((r, i) => (
              <TableRow key={i}>
                <TableCell>{new Date(r.em).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}</TableCell>
                <TableCell>{ACOES[r.acao] || r.acao}{r.acao === 'aceite_termos' && r.detalhes?.versao ? ` (versão ${r.detalhes.versao})` : ''}</TableCell>
                <TableCell>{r.titular ?? '—'}</TableCell>
                <TableCell>{r.autor ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </>
  );
};
