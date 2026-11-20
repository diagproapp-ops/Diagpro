import React, { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, FormControlLabel, MenuItem, Switch, TextField, Typography,
} from '@mui/material';
import api from '../../api';
import { Aviso, BarraSalvar, Secao, mensagemErro } from './configComum';

type Provedor = 'anthropic' | 'openai';
type InfoChave = { definida: boolean; final: string; no_ambiente: boolean };
type IA = {
  habilitada: boolean; provedor: Provedor; modelo_anthropic: string; modelo_openai: string;
  limite_diario_usuario: number; limite_diario_banca: number;
  chaves: Record<Provedor, InfoChave>;
};

const NOMES: Record<Provedor, string> = { anthropic: 'Claude (Anthropic)', openai: 'OpenAI' };

// IA da PLATAFORMA: provedor, modelo, chaves e limites. Só o administrador geral, na visão global.
const PlataformaIATab: React.FC = () => {
  const [original, setOriginal] = useState<IA | null>(null);
  const [ia, setIa] = useState<IA | null>(null);
  const [novaChave, setNovaChave] = useState<Record<Provedor, string>>({ anthropic: '', openai: '' });
  const [remover, setRemover] = useState<Record<Provedor, boolean>>({ anthropic: false, openai: false });
  const [salvando, setSalvando] = useState(false);
  const [testando, setTestando] = useState<Provedor | null>(null);
  const [msg, setMsg] = useState<{ texto: string; tipo: 'success' | 'error' } | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const aplicar = (data: any) => {
    setOriginal(data.ia); setIa(data.ia);
    setNovaChave({ anthropic: '', openai: '' }); setRemover({ anthropic: false, openai: false });
  };

  useEffect(() => {
    api.get('/config/plataforma').then(({ data }) => aplicar(data))
      .catch(e => setErro(mensagemErro(e, 'Não foi possível carregar as configurações.')));
  }, []);

  if (erro) return <Alert severity="warning">{erro}</Alert>;
  if (!ia || !original) return <CircularProgress />;

  const { chaves: _c1, ...semChaves } = ia;
  const { chaves: _c2, ...originalSemChaves } = original;
  const alterado = JSON.stringify(semChaves) !== JSON.stringify(originalSemChaves)
    || !!novaChave.anthropic || !!novaChave.openai || remover.anthropic || remover.openai;

  const salvar = async () => {
    setSalvando(true);
    try {
      const chaves: Record<string, string | null> = {};
      (['anthropic', 'openai'] as Provedor[]).forEach(p => {
        if (remover[p]) chaves[p] = null;
        else if (novaChave[p].trim()) chaves[p] = novaChave[p].trim();
      });
      const { data } = await api.put('/config/plataforma', {
        ia: { ...semChaves, ...(Object.keys(chaves).length ? { chaves } : {}) },
      });
      aplicar(data);
      setMsg({ texto: 'Configurações de IA salvas.', tipo: 'success' });
    } catch (e: any) {
      setMsg({ texto: mensagemErro(e), tipo: 'error' });
    } finally {
      setSalvando(false);
    }
  };

  const testar = async (p: Provedor) => {
    setTestando(p);
    try {
      const { data } = await api.post('/ia/testar', { provedor: p });
      setMsg({ texto: `Conexão ok com ${NOMES[p]} (modelo ${data.modelo}).`, tipo: 'success' });
    } catch (e: any) {
      setMsg({ texto: mensagemErro(e, 'Falha no teste de conexão.'), tipo: 'error' });
    } finally {
      setTestando(null);
    }
  };

  const situacaoChave = (p: Provedor) => {
    const c = ia.chaves[p];
    if (remover[p]) return <Chip size="small" color="warning" label="Será removida ao salvar" />;
    if (c.definida) return <Chip size="small" color="success" label={`Chave salva ${c.final}`} />;
    if (c.no_ambiente) return <Chip size="small" color="info" label="Usando a chave do servidor (.env)" />;
    return <Chip size="small" label="Sem chave" />;
  };

  return (
    <>
      <Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Inteligência artificial</Typography>
      <Alert severity="info" sx={{ mb: 2.5 }}>
        A IA só recebe o texto que o usuário enviar ao clicar num botão de IA (sem imagens, sem a prova montada,
        sem gabaritos e sem nomes de pessoas). Nada do que é enviado fica gravado: guardamos só quem usou, quando e
        quantos tokens. Cada banca ainda precisa ligar a IA nas configurações dela.
      </Alert>

      <Secao titulo="Assistente de IA" descricao="Liga ou desliga a IA para a plataforma inteira e escolhe o provedor.">
        <FormControlLabel
          control={<Switch checked={ia.habilitada} onChange={e => setIa({ ...ia, habilitada: e.target.checked })} />}
          label={ia.habilitada ? 'IA ligada na plataforma' : 'IA desligada na plataforma'}
        />
        {(() => {
          const temChave = (p: Provedor) => ia.chaves[p].definida || ia.chaves[p].no_ambiente;
          if (temChave(ia.provedor)) return null;
          const outro = (Object.keys(NOMES) as Provedor[]).find((p) => p !== ia.provedor && temChave(p));
          return (
            <Alert severity="warning" sx={{ mt: 1.5 }}
              action={outro ? <Button color="inherit" size="small" sx={{ whiteSpace: 'nowrap' }} onClick={() => setIa({ ...ia, provedor: outro })}>Usar {NOMES[outro]}</Button> : undefined}>
              O provedor em uso ({NOMES[ia.provedor]}) não tem chave: a IA não aparece para ninguém.
              {outro ? ` Já existe chave para ${NOMES[outro]}.` : ' Cole a chave dele abaixo.'}
            </Alert>
          );
        })()}
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2, mt: 2 }}>
          <TextField select label="Provedor em uso" value={ia.provedor}
            onChange={e => setIa({ ...ia, provedor: e.target.value as Provedor })}
            helperText="Pode trocar a qualquer momento (por exemplo, para comparar custos)">
            <MenuItem value="anthropic">{NOMES.anthropic}</MenuItem>
            <MenuItem value="openai">{NOMES.openai}</MenuItem>
          </TextField>
          <Box />
          <TextField label="Modelo Claude" value={ia.modelo_anthropic}
            onChange={e => setIa({ ...ia, modelo_anthropic: e.target.value })}
            helperText="Padrão: claude-opus-5-5" />
          <TextField label="Modelo OpenAI" value={ia.modelo_openai}
            onChange={e => setIa({ ...ia, modelo_openai: e.target.value })}
            helperText="Use o nome exato do modelo na sua conta OpenAI" />
        </Box>
      </Secao>

      <Secao titulo="Chaves de acesso" descricao="Ficam cifradas no banco e nunca voltam para a tela. Deixe em branco para manter a atual.">
        {(['anthropic', 'openai'] as Provedor[]).map(p => (
          <Box key={p} sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap' }}>
              <Typography fontWeight={600}>{NOMES[p]}</Typography>
              {situacaoChave(p)}
            </Box>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
              <TextField size="small" type="password" autoComplete="new-password" sx={{ flex: '1 1 320px' }}
                label={ia.chaves[p].definida ? 'Trocar chave' : 'Colar chave'} value={novaChave[p]}
                onChange={e => { setNovaChave({ ...novaChave, [p]: e.target.value }); setRemover({ ...remover, [p]: false }); }} />
              {ia.chaves[p].definida && (
                <Button size="small" color="warning" onClick={() => setRemover({ ...remover, [p]: !remover[p] })}>
                  {remover[p] ? 'Manter chave' : 'Remover chave'}
                </Button>
              )}
              <Button size="small" variant="outlined" disabled={!!testando || alterado || (!ia.chaves[p].definida && !ia.chaves[p].no_ambiente)}
                onClick={() => testar(p)}>
                {testando === p ? 'Testando...' : 'Testar conexão'}
              </Button>
            </Box>
          </Box>
        ))}
        {alterado && <Typography variant="body2" color="text.secondary">Salve antes de testar a conexão.</Typography>}
      </Secao>

      <Secao titulo="Limites diários" descricao="Protegem contra uso excessivo e custos inesperados. As bancas podem reduzir o limite por usuário.">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
          <TextField type="number" label="Usos por usuário por dia" value={ia.limite_diario_usuario}
            inputProps={{ min: 1, max: 1000 }} helperText="1 a 1000"
            onChange={e => setIa({ ...ia, limite_diario_usuario: Number(e.target.value) })} />
          <TextField type="number" label="Usos por banca por dia" value={ia.limite_diario_banca}
            inputProps={{ min: 1, max: 100000 }} helperText="1 a 100000"
            onChange={e => setIa({ ...ia, limite_diario_banca: Number(e.target.value) })} />
        </Box>
      </Secao>

      <BarraSalvar salvando={salvando} onSalvar={salvar} alterado={alterado} />
      <Aviso msg={msg} onFechar={() => setMsg(null)} />
    </>
  );
};

export default PlataformaIATab;
