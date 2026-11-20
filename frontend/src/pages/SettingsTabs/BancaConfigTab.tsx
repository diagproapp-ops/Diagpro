import React, { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Checkbox, CircularProgress, FormControlLabel, FormGroup, IconButton, Switch, TextField,
  Tooltip, Typography,
} from '@mui/material';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import AddIcon from '@mui/icons-material/Add';
import api from '../../api';
import { Aviso, BarraSalvar, Secao, mensagemErro } from './configComum';

type Regra = { contem: string; instrucoes: string[] };
type Banca = {
  seguranca: { sessao_inatividade_minutos: number | null };
  identidade_prova: { instrucoes_por_bloco: Regra[]; instrucoes_discursiva: string[] };
  regras_questoes: { tipos_permitidos: string[]; revisao_obrigatoria: boolean };
};

const TIPOS = [
  { valor: 'MULTIPLA_ESCOLHA', rotulo: 'Múltipla escolha' },
  { valor: 'CERTO_ERRADO', rotulo: 'Certo/Errado' },
  { valor: 'DISCURSIVA', rotulo: 'Discursiva' },
  { valor: 'SUBJETIVA', rotulo: 'Subjetiva' },
];

// Textos com uma instrução por linha (mais simples de editar do que uma lista de campos)
const paraLinhas = (lista: string[]) => (lista || []).join('\n');
const deLinhas = (texto: string) => texto.split('\n').map(t => t.trim()).filter(Boolean);

type Secao_ = 'seguranca' | 'identidade' | 'regras';

// Configurações da BANCA (cliente atual). O administrador geral precisa escolher o cliente no topo.
const BancaConfigTab: React.FC<{ secao: Secao_ }> = ({ secao }) => {
  const [original, setOriginal] = useState<Banca | null>(null);
  const [cfg, setCfg] = useState<Banca | null>(null);
  const [teto, setTeto] = useState(30);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<{ texto: string; tipo: 'success' | 'error' } | null>(null);
  // edição das instruções em texto (uma por linha)
  const [blocosTexto, setBlocosTexto] = useState<{ contem: string; texto: string }[]>([]);
  const [discursivaTexto, setDiscursivaTexto] = useState('');

  const carregar = (data: any) => {
    const b: Banca = { seguranca: data.seguranca, identidade_prova: data.identidade_prova, regras_questoes: data.regras_questoes };
    setOriginal(b); setCfg(b);
    setBlocosTexto(b.identidade_prova.instrucoes_por_bloco.map(r => ({ contem: r.contem, texto: paraLinhas(r.instrucoes) })));
    setDiscursivaTexto(paraLinhas(b.identidade_prova.instrucoes_discursiva));
    if (data.limites?.sessao_inatividade_minutos_maximo) setTeto(data.limites.sessao_inatividade_minutos_maximo);
  };

  useEffect(() => {
    api.get('/config/banca').then(({ data }) => carregar(data))
      .catch(e => setErro(mensagemErro(e, 'Não foi possível carregar as configurações da banca.')));
  }, []);

  if (erro) return <Alert severity="warning">{erro}</Alert>;
  if (!cfg || !original) return <CircularProgress />;

  const identidadeAtual = {
    instrucoes_por_bloco: blocosTexto.map(b => ({ contem: b.contem.trim(), instrucoes: deLinhas(b.texto) })),
    instrucoes_discursiva: deLinhas(discursivaTexto),
  };
  const payload: Partial<Banca> =
    secao === 'seguranca' ? { seguranca: cfg.seguranca }
      : secao === 'regras' ? { regras_questoes: cfg.regras_questoes }
        : { identidade_prova: identidadeAtual };
  const alterado =
    secao === 'seguranca' ? JSON.stringify(cfg.seguranca) !== JSON.stringify(original.seguranca)
      : secao === 'regras' ? JSON.stringify(cfg.regras_questoes) !== JSON.stringify(original.regras_questoes)
        : JSON.stringify(identidadeAtual) !== JSON.stringify(original.identidade_prova);

  const salvar = async () => {
    setSalvando(true);
    try {
      const { data } = await api.put('/config/banca', payload);
      carregar({ ...data, limites: { sessao_inatividade_minutos_maximo: teto } });
      setMsg({ texto: 'Configurações da banca salvas.', tipo: 'success' });
    } catch (e: any) {
      setMsg({ texto: mensagemErro(e), tipo: 'error' });
    } finally {
      setSalvando(false);
    }
  };

  return (
    <>
      {secao === 'seguranca' && (
        <>
          <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>Segurança da banca</Typography>
          <Secao titulo="Sessão" descricao={`A plataforma encerra sessões paradas por ${teto} minutos. A banca pode deixar mais curto, nunca mais longo.`}>
            <FormControlLabel
              control={<Switch checked={cfg.seguranca.sessao_inatividade_minutos !== null}
                onChange={e => setCfg({ ...cfg, seguranca: { sessao_inatividade_minutos: e.target.checked ? Math.min(15, teto) : null } })} />}
              label="Usar um tempo próprio, mais curto que o da plataforma"
            />
            {cfg.seguranca.sessao_inatividade_minutos !== null && (
              <TextField type="number" label="Minutos sem uso para encerrar" sx={{ mt: 2, maxWidth: 320 }} fullWidth
                value={cfg.seguranca.sessao_inatividade_minutos} inputProps={{ min: 5, max: teto }}
                helperText={`Entre 5 e ${teto}`}
                onChange={e => setCfg({ ...cfg, seguranca: { sessao_inatividade_minutos: Number(e.target.value) } })} />
            )}
          </Secao>
          <Alert severity="info" sx={{ mb: 2 }}>A verificação em duas etapas é obrigatória para todos os usuários da banca.</Alert>
        </>
      )}

      {secao === 'identidade' && (
        <>
          <Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Identidade da prova</Typography>
          <Alert severity="info" sx={{ mb: 2.5 }}>
            Estes textos são impressos nas provas exportadas. Enquanto não forem alterados, a prova sai exatamente como antes.
          </Alert>
          <Secao titulo="Instruções por bloco"
            descricao="Impressas no início de todo bloco cujo título contém a palavra indicada (ex.: “informática”). Uma instrução por linha.">
            {blocosTexto.map((b, i) => (
              <Box key={i} sx={{ display: 'flex', gap: 1.5, mb: 2, alignItems: 'flex-start' }}>
                <TextField label="Título do bloco contém" value={b.contem} sx={{ width: 220 }}
                  onChange={e => setBlocosTexto(blocosTexto.map((x, j) => j === i ? { ...x, contem: e.target.value } : x))} />
                <TextField label="Instruções (uma por linha)" value={b.texto} multiline minRows={2} fullWidth
                  onChange={e => setBlocosTexto(blocosTexto.map((x, j) => j === i ? { ...x, texto: e.target.value } : x))} />
                <Tooltip title="Remover esta regra">
                  <IconButton onClick={() => setBlocosTexto(blocosTexto.filter((_, j) => j !== i))}><DeleteOutlineIcon /></IconButton>
                </Tooltip>
              </Box>
            ))}
            <Button startIcon={<AddIcon />} onClick={() => setBlocosTexto([...blocosTexto, { contem: '', texto: '' }])}>
              Adicionar regra
            </Button>
          </Secao>
          <Secao titulo="Instruções da prova discursiva" descricao="Impressas no início da seção discursiva. Uma instrução por linha; deixe vazio para não imprimir.">
            <TextField value={discursivaTexto} onChange={e => setDiscursivaTexto(e.target.value)} multiline minRows={5} fullWidth />
          </Secao>
        </>
      )}

      {secao === 'regras' && (
        <>
          <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>Regras das questões</Typography>
          <Secao titulo="Tipos de questão usados pela banca" descricao="Só estes tipos aparecem na criação de questões.">
            <FormGroup row>
              {TIPOS.map(t => (
                <FormControlLabel key={t.valor} label={t.rotulo} control={
                  <Checkbox checked={cfg.regras_questoes.tipos_permitidos.includes(t.valor)}
                    onChange={e => {
                      const atual = cfg.regras_questoes.tipos_permitidos;
                      const novo = e.target.checked ? [...atual, t.valor] : atual.filter(x => x !== t.valor);
                      setCfg({ ...cfg, regras_questoes: { ...cfg.regras_questoes, tipos_permitidos: TIPOS.map(x => x.valor).filter(v => novo.includes(v)) } });
                    }} />
                } />
              ))}
            </FormGroup>
            {cfg.regras_questoes.tipos_permitidos.length === 0 && <Alert severity="error" sx={{ mt: 1 }}>Escolha pelo menos um tipo.</Alert>}
          </Secao>
          <Secao titulo="Revisão" descricao="Com a revisão obrigatória, a exportação é bloqueada enquanto houver questão da prova sem revisão aprovada.">
            <FormControlLabel
              control={<Switch checked={cfg.regras_questoes.revisao_obrigatoria}
                onChange={e => setCfg({ ...cfg, regras_questoes: { ...cfg.regras_questoes, revisao_obrigatoria: e.target.checked } })} />}
              label="Exigir revisão aprovada para exportar"
            />
          </Secao>
        </>
      )}

      <BarraSalvar salvando={salvando} onSalvar={salvar} alterado={alterado} />
      <Aviso msg={msg} onFechar={() => setMsg(null)} />
    </>
  );
};

export default BancaConfigTab;
