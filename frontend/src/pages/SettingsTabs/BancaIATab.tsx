import React, { useEffect, useState } from 'react';
import {
  Alert, Box, Checkbox, CircularProgress, FormControlLabel, FormGroup, Switch, Table, TableBody, TableCell,
  TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import api from '../../api';
import { Aviso, BarraSalvar, Secao, mensagemErro } from './configComum';

type Recursos = Record<string, boolean>;
type IABanca = { habilitada: boolean; recursos: Recursos; orientacoes_banca: string; limite_diario_usuario: number | null };
type Uso = {
  dias: number; total: number; falhas: number; tokens_entrada: number; tokens_saida: number;
  por_recurso: Record<string, number>; por_usuario: { usuario: string; usos: number }[];
};

export const NOMES_RECURSOS: Record<string, string> = {
  gerar_questao: 'Criar rascunho de questão',
  revisar_questao: 'Revisar questão (ambiguidade, gabarito, português)',
  alternativas: 'Sugerir alternativas erradas (distratores)',
  justificativa: 'Escrever justificativa do gabarito',
  melhorar_texto: 'Melhorar texto (português, clareza, linguagem formal)',
  chat: 'Chat de apoio no editor',
  equacao: 'Criar equação a partir de uma descrição',
  equacao_imagem: 'Criar equação a partir de foto ou imagem (inclusive escrita à mão)',
};

// IA da BANCA: liga/desliga, recursos, orientações de estilo e uso dos últimos 30 dias.
const BancaIATab: React.FC = () => {
  const [original, setOriginal] = useState<IABanca | null>(null);
  const [ia, setIa] = useState<IABanca | null>(null);
  const [limites, setLimites] = useState<{ ia_liberada_pela_plataforma: boolean; ia_limite_diario_usuario_maximo: number } | null>(null);
  const [uso, setUso] = useState<Uso | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [msg, setMsg] = useState<{ texto: string; tipo: 'success' | 'error' } | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    api.get('/config/banca')
      .then(({ data }) => { setOriginal(data.ia); setIa(data.ia); setLimites(data.limites); })
      .catch(e => setErro(mensagemErro(e, 'Não foi possível carregar as configurações.')));
    api.get('/ia/uso').then(({ data }) => setUso(data)).catch(() => {});
  }, []);

  if (erro) return <Alert severity="warning">{erro}</Alert>;
  if (!ia || !limites) return <CircularProgress />;

  const salvar = async () => {
    setSalvando(true);
    try {
      const { data } = await api.put('/config/banca', { ia });
      setOriginal(data.ia); setIa(data.ia);
      setMsg({ texto: 'Configurações de IA da banca salvas.', tipo: 'success' });
    } catch (e: any) {
      setMsg({ texto: mensagemErro(e), tipo: 'error' });
    } finally {
      setSalvando(false);
    }
  };

  const proprio = ia.limite_diario_usuario !== null;

  return (
    <>
      <Typography variant="h6" fontWeight={700} sx={{ mb: 1 }}>IA da banca</Typography>
      {!limites.ia_liberada_pela_plataforma && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          A IA está desligada na plataforma. Você pode deixar tudo pronto aqui; ela passa a funcionar quando o
          administrador geral ligar.
        </Alert>
      )}
      <Alert severity="info" sx={{ mb: 2.5 }}>
        A IA recebe apenas o texto que a pessoa enviar ao clicar num botão de IA, sem imagens, sem a prova montada e
        sem gabaritos de outras questões. O texto vai para o provedor de IA contratado pela plataforma e não fica
        gravado no DiagPro. Tudo o que a IA devolve é rascunho: o professor confere antes de salvar.
      </Alert>

      <Secao titulo="Assistente de IA" descricao="Ao ligar, os botões de IA aparecem para professores, revisores e administradores desta banca.">
        <FormControlLabel
          control={<Switch checked={ia.habilitada} onChange={e => setIa({ ...ia, habilitada: e.target.checked })} />}
          label={ia.habilitada ? 'IA ligada para esta banca' : 'IA desligada para esta banca'}
        />
        <Typography variant="subtitle2" sx={{ mt: 2, mb: 0.5 }}>Recursos liberados</Typography>
        <FormGroup>
          {Object.keys(NOMES_RECURSOS).map(r => (
            <FormControlLabel key={r} label={NOMES_RECURSOS[r]}
              control={<Checkbox checked={!!ia.recursos[r]} onChange={e => setIa({ ...ia, recursos: { ...ia.recursos, [r]: e.target.checked } })} />} />
          ))}
        </FormGroup>
      </Secao>

      <Secao titulo="Orientações da banca para a IA" descricao="Estilo e regras que a IA deve seguir sempre (ex.: padrão de enunciado, número de alternativas, termos proibidos).">
        <TextField fullWidth multiline minRows={4} value={ia.orientacoes_banca}
          inputProps={{ maxLength: 3000 }} helperText={`${ia.orientacoes_banca.length}/3000`}
          placeholder="Ex.: Enunciados no imperativo; alternativas em ordem crescente de tamanho; nunca usar 'exceto' em caixa baixa..."
          onChange={e => setIa({ ...ia, orientacoes_banca: e.target.value })} />
      </Secao>

      <Secao titulo="Limite por usuário" descricao={`Máximo da plataforma: ${limites.ia_limite_diario_usuario_maximo} usos por dia.`}>
        <FormControlLabel
          control={<Switch checked={proprio} onChange={e => setIa({ ...ia, limite_diario_usuario: e.target.checked ? Math.min(30, limites.ia_limite_diario_usuario_maximo) : null })} />}
          label="Usar um limite menor nesta banca"
        />
        {proprio && (
          <TextField type="number" sx={{ mt: 1, maxWidth: 260 }} label="Usos por usuário por dia"
            value={ia.limite_diario_usuario ?? ''} inputProps={{ min: 1, max: limites.ia_limite_diario_usuario_maximo }}
            onChange={e => setIa({ ...ia, limite_diario_usuario: Number(e.target.value) })} />
        )}
      </Secao>

      <BarraSalvar salvando={salvando} onSalvar={salvar} alterado={JSON.stringify(ia) !== JSON.stringify(original)} />

      <Box sx={{ mt: 3 }}>
        <Secao titulo="Uso nos últimos 30 dias" descricao="Só contagens e tokens; nenhum texto enviado é guardado.">
          {!uso ? <Typography variant="body2" color="text.secondary">Sem dados de uso.</Typography> : (
            <>
              <Typography variant="body2" sx={{ mb: 1.5 }}>
                {uso.total} uso(s) • {uso.falhas} com falha • {(uso.tokens_entrada + uso.tokens_saida).toLocaleString('pt-BR')} tokens
                ({uso.tokens_entrada.toLocaleString('pt-BR')} enviados, {uso.tokens_saida.toLocaleString('pt-BR')} recebidos)
              </Typography>
              {uso.total > 0 && (
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
                  <Table size="small">
                    <TableHead><TableRow><TableCell>Recurso</TableCell><TableCell align="right">Usos</TableCell></TableRow></TableHead>
                    <TableBody>
                      {Object.entries(uso.por_recurso).map(([r, n]) => (
                        <TableRow key={r}><TableCell>{NOMES_RECURSOS[r] || r}</TableCell><TableCell align="right">{n}</TableCell></TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <Table size="small">
                    <TableHead><TableRow><TableCell>Pessoa</TableCell><TableCell align="right">Usos</TableCell></TableRow></TableHead>
                    <TableBody>
                      {uso.por_usuario.map(u => (
                        <TableRow key={u.usuario}><TableCell>{u.usuario}</TableCell><TableCell align="right">{u.usos}</TableCell></TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Box>
              )}
            </>
          )}
        </Secao>
      </Box>
      <Aviso msg={msg} onFechar={() => setMsg(null)} />
    </>
  );
};

export default BancaIATab;
