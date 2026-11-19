import React, { useEffect, useState } from 'react';
import { Alert, Box, CircularProgress, TextField, Typography } from '@mui/material';
import api from '../../api';
import { Aviso, BarraSalvar, Secao, mensagemErro } from './configComum';

type Seguranca = {
  senha_tamanho_minimo: number; senha_tipos_minimos: number; senha_historico: number; senha_validade_dias: number;
  sessao_inatividade_minutos: number; sessao_maxima_horas: number;
};

const CAMPOS: { chave: keyof Seguranca; rotulo: string; ajuda: string; min: number; max: number }[] = [
  { chave: 'senha_tamanho_minimo', rotulo: 'Tamanho mínimo da senha', ajuda: 'Entre 8 e 64 caracteres', min: 8, max: 64 },
  { chave: 'senha_tipos_minimos', rotulo: 'Tipos de caractere exigidos', ajuda: 'De 2 a 4: maiúscula, minúscula, número, símbolo', min: 2, max: 4 },
  { chave: 'senha_historico', rotulo: 'Senhas anteriores proibidas', ajuda: 'Não pode repetir as últimas N (1 a 24)', min: 1, max: 24 },
  { chave: 'senha_validade_dias', rotulo: 'Validade da senha (dias)', ajuda: 'Troca obrigatória depois disso (30 a 730)', min: 30, max: 730 },
  { chave: 'sessao_inatividade_minutos', rotulo: 'Sessão: minutos sem uso', ajuda: 'Encerra a sessão parada (5 a 240). As bancas podem encurtar', min: 5, max: 240 },
  { chave: 'sessao_maxima_horas', rotulo: 'Sessão: duração máxima (horas)', ajuda: 'Mesmo em uso, pede login de novo (1 a 24)', min: 1, max: 24 },
];

// Configurações da PLATAFORMA (todas as bancas): só o administrador geral, na visão global.
const PlataformaSegurancaTab: React.FC = () => {
  const [original, setOriginal] = useState<Seguranca | null>(null);
  const [valores, setValores] = useState<Seguranca | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<{ texto: string; tipo: 'success' | 'error' } | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.get('/config/plataforma')
      .then(({ data }) => { setOriginal(data.seguranca); setValores(data.seguranca); })
      .catch(e => setErro(mensagemErro(e, 'Não foi possível carregar as configurações.')));
  }, []);

  if (erro) return <Alert severity="warning">{erro}</Alert>;
  if (!valores) return <CircularProgress />;

  const salvar = async () => {
    setSalvando(true);
    try {
      const { data } = await api.put('/config/plataforma', { seguranca: valores });
      setOriginal(data.seguranca); setValores(data.seguranca);
      setMsg({ texto: 'Configurações da plataforma salvas. Valem para todas as bancas.', tipo: 'success' });
    } catch (e: any) {
      setMsg({ texto: mensagemErro(e), tipo: 'error' });
    } finally {
      setSalvando(false);
    }
  };

  return (
    <>
      <Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>Segurança da plataforma</Typography>
      <Alert severity="info" sx={{ mb: 2.5 }}>
        Valem para todas as bancas. A verificação em duas etapas é obrigatória para todos e não pode ser desligada.
      </Alert>
      <Secao titulo="Senha e sessão" descricao="Regras mínimas de senha e tempo de sessão de todos os usuários.">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
          {CAMPOS.map(c => (
              <TextField key={c.chave}
                fullWidth type="number" label={c.rotulo} helperText={c.ajuda}
                value={valores[c.chave]}
                inputProps={{ min: c.min, max: c.max }}
                onChange={e => setValores({ ...valores, [c.chave]: Number(e.target.value) })}
              />
          ))}
        </Box>
      </Secao>
      <BarraSalvar salvando={salvando} onSalvar={salvar} alterado={JSON.stringify(valores) !== JSON.stringify(original)} />
      <Aviso msg={msg} onFechar={() => setMsg(null)} />
    </>
  );
};

export default PlataformaSegurancaTab;
