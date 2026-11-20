import React, { useState } from 'react';
import {
  Alert, Box, Button, Checkbox, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  Divider, FormControlLabel, List, ListItem, ListItemText, MenuItem, Stack, Tab, Tabs, TextField, Typography,
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import api from '../../api';
import {
  AplicacaoIA, QuestaoIA, StatusIA, erroIA, htmlParaTexto, podeUsar, textoParaHtml,
} from './iaComum';

const NIVEIS = [
  { value: 'MUITO_FACIL', label: 'Muito fácil' }, { value: 'FACIL', label: 'Fácil' }, { value: 'MEDIO', label: 'Médio' },
  { value: 'DIFICIL', label: 'Difícil' }, { value: 'MUITO_DIFICIL', label: 'Muito difícil' },
];
const NOME_NIVEL = Object.fromEntries(NIVEIS.map(n => [n.value, n.label]));
const COR_GRAVIDADE: Record<string, 'error' | 'warning' | 'info'> = { alta: 'error', media: 'warning', baixa: 'info' };
const AVALIACAO: Record<string, { rotulo: string; cor: 'success' | 'warning' | 'error' }> = {
  boa: { rotulo: 'Questão boa', cor: 'success' }, ajustar: { rotulo: 'Precisa de ajustes', cor: 'warning' },
  refazer: { rotulo: 'Recomenda refazer', cor: 'error' },
};

type Aba = 'gerar' | 'revisar' | 'alternativas' | 'justificativa';

type Props = {
  open: boolean;
  onClose: () => void;
  status: StatusIA;
  questao: QuestaoIA;
  disciplina?: string;
  onAplicar: (ap: AplicacaoIA, aviso: string) => void;
  abaInicial?: Aba;
  permitirGerar?: boolean;  // false na tela de revisão (não troca a questão inteira)
};

// Assistente de IA das telas de questão. Tudo o que a IA devolve é rascunho: o usuário escolhe o que usar.
export default function AssistenteIAQuestao({ open, onClose, status, questao, disciplina, onAplicar, abaInicial, permitirGerar = true }: Props) {
  const abas: { id: Aba; rotulo: string; recurso: string; ok: boolean }[] = [
    { id: 'gerar', rotulo: 'Criar rascunho', recurso: 'gerar_questao', ok: permitirGerar },
    { id: 'revisar', rotulo: 'Revisar', recurso: 'revisar_questao', ok: true },
    { id: 'alternativas', rotulo: 'Alternativas erradas', recurso: 'alternativas', ok: questao.tipo === 'MULTIPLA_ESCOLHA' },
    { id: 'justificativa', rotulo: 'Justificativa', recurso: 'justificativa', ok: true },
  ];
  const visiveis = abas.filter(a => a.ok && podeUsar(status, a.recurso));
  const [aba, setAba] = useState<Aba>(abaInicial && visiveis.some(v => v.id === abaInicial) ? abaInicial : (visiveis[0]?.id || 'revisar'));
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // criar rascunho
  const [assunto, setAssunto] = useState(questao.assunto);
  const [nivel, setNivel] = useState(questao.nivel || 'MEDIO');
  const [numAlternativas, setNumAlternativas] = useState(5);
  const [qtdItens, setQtdItens] = useState(Math.max(1, questao.itens.length || 3));
  const [instrucoes, setInstrucoes] = useState('');
  const [textoBase, setTextoBase] = useState('');
  const [rascunho, setRascunho] = useState<any>(null);
  // revisar / alternativas / justificativa
  const [revisao, setRevisao] = useState<any>(null);
  const [qtdDistratores, setQtdDistratores] = useState(4);
  const [distratores, setDistratores] = useState<{ texto: string; por_que_plausivel: string; usar: boolean }[]>([]);
  const [justificativa, setJustificativa] = useState<any>(null);

  const temEnunciado = !!htmlParaTexto(questao.enunciado);

  const chamar = async (fn: () => Promise<void>) => {
    setErro(null); setCarregando(true);
    try { await fn(); } catch (e: any) { setErro(erroIA(e)); } finally { setCarregando(false); }
  };

  const gerar = () => chamar(async () => {
    const { data } = await api.post('/ia/questao/gerar', {
      tipo: questao.tipo, assunto, disciplina: disciplina || '', nivel, instrucoes, texto_base: textoBase,
      num_alternativas: numAlternativas, quantidade_itens: qtdItens,
    });
    setRascunho(data);
  });
  const revisar = () => chamar(async () => {
    const { data } = await api.post('/ia/questao/revisar', questao);
    setRevisao(data);
  });
  const sugerirDistratores = () => chamar(async () => {
    const { data } = await api.post('/ia/questao/alternativas', { ...questao, quantidade: qtdDistratores });
    setDistratores((data.alternativas || []).map((a: any) => ({ ...a, usar: true })));
  });
  const justificar = () => chamar(async () => {
    const { data } = await api.post('/ia/questao/justificativa', questao);
    setJustificativa(data);
  });

  const usarRascunho = () => {
    const r = rascunho;
    const ap: AplicacaoIA = { enunciado: textoParaHtml(r.enunciado), nivel };
    if (questao.tipo === 'MULTIPLA_ESCOLHA') {
      ap.alternativas = (r.alternativas || []).map((a: any) => ({ letra: a.letra, texto: textoParaHtml(a.texto) }));
      ap.correta = r.correta;
    }
    if (questao.tipo === 'CERTO_ERRADO') ap.itens = (r.itens || []).map((i: any) => ({ afirmacao: textoParaHtml(i.afirmacao), certo: !!i.certo }));
    if (questao.tipo === 'DISCURSIVA') ap.palavras_chave = r.palavras_chave || [];
    const just = [r.justificativa, r.padrao_resposta ? `Padrão de resposta: ${r.padrao_resposta}` : ''].filter(Boolean).join('\n');
    if (just) ap.justificativa = textoParaHtml(just);
    onAplicar(ap, 'Rascunho da IA aplicado. Revise todos os campos antes de salvar.');
    onClose();
  };

  const usarJustificativa = () => {
    const linhas = [justificativa.justificativa, ...(justificativa.por_alternativa || []).map((p: any) => `${p.letra}) ${p.comentario}`)];
    onAplicar({ justificativa: textoParaHtml(linhas.filter(Boolean).join('\n')) }, 'Justificativa da IA aplicada. Confira antes de salvar.');
    onClose();
  };

  const usarDistratores = () => {
    const escolhidos = distratores.filter(d => d.usar).map(d => textoParaHtml(d.texto));
    onAplicar({ distratores: escolhidos }, 'Alternativas da IA aplicadas nas alternativas erradas. Confira antes de salvar.');
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <AutoAwesomeIcon color="primary" /> Assistente de IA
      </DialogTitle>
      <DialogContent dividers>
        {!visiveis.length ? (
          <Alert severity="info">{status.motivo || 'Nenhum recurso de IA disponível para esta questão.'}</Alert>
        ) : (
          <>
            <Tabs value={aba} onChange={(_, v) => { setAba(v); setErro(null); }} variant="scrollable" sx={{ mb: 2 }}>
              {visiveis.map(a => <Tab key={a.id} value={a.id} label={a.rotulo} />)}
            </Tabs>
            <Alert severity="info" sx={{ mb: 2 }}>
              Vai para a IA só o texto desta questão (sem imagens). O resultado é um rascunho: confira tudo antes de salvar.
            </Alert>
            {erro && <Alert severity="error" sx={{ mb: 2 }}>{erro}</Alert>}

            {aba === 'gerar' && (
              <Box>
                <Stack spacing={2}>
                  <TextField label="Conteúdo do edital / assunto *" value={assunto} onChange={e => setAssunto(e.target.value)}
                    inputProps={{ maxLength: 500 }} fullWidth />
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                    <TextField select label="Nível" value={nivel} onChange={e => setNivel(e.target.value)} sx={{ minWidth: 180 }}>
                      {NIVEIS.map(n => <MenuItem key={n.value} value={n.value}>{n.label}</MenuItem>)}
                    </TextField>
                    {questao.tipo === 'MULTIPLA_ESCOLHA' && (
                      <TextField select label="Alternativas" value={numAlternativas} onChange={e => setNumAlternativas(Number(e.target.value))} sx={{ minWidth: 140 }}>
                        {[4, 5].map(n => <MenuItem key={n} value={n}>{n}</MenuItem>)}
                      </TextField>
                    )}
                    {questao.tipo === 'CERTO_ERRADO' && (
                      <TextField type="number" label="Itens para julgar" value={qtdItens} inputProps={{ min: 1, max: 10 }}
                        onChange={e => setQtdItens(Math.max(1, Math.min(10, Number(e.target.value) || 1)))} sx={{ minWidth: 160 }} />
                    )}
                  </Stack>
                  <TextField label="O que você quer (opcional)" value={instrucoes} onChange={e => setInstrucoes(e.target.value)}
                    multiline minRows={2} inputProps={{ maxLength: 4000 }} fullWidth
                    placeholder="Ex.: cobrar o art. 37 da Constituição, com foco em princípios; situação-problema de órgão público" />
                  <TextField label="Texto-base (opcional)" value={textoBase} onChange={e => setTextoBase(e.target.value)}
                    multiline minRows={3} inputProps={{ maxLength: 60000 }} fullWidth helperText="Cole aqui um texto para a questão se basear" />
                </Stack>
                <Box sx={{ mt: 2, display: 'flex', gap: 1, alignItems: 'center' }}>
                  <Button variant="contained" onClick={gerar} disabled={carregando || assunto.trim().length < 2} startIcon={<AutoAwesomeIcon />}>
                    {rascunho ? 'Gerar outro' : 'Gerar rascunho'}
                  </Button>
                  {carregando && <CircularProgress size={22} />}
                </Box>
                {rascunho && (
                  <Box sx={{ mt: 3 }}>
                    <Divider sx={{ mb: 2 }}>Rascunho</Divider>
                    {(rascunho.avisos || []).map((a: string, i: number) => <Alert key={i} severity="warning" sx={{ mb: 1 }}>{a}</Alert>)}
                    <Typography sx={{ whiteSpace: 'pre-wrap', mb: 1.5 }}>{rascunho.enunciado}</Typography>
                    {(rascunho.alternativas || []).map((a: any) => (
                      <Typography key={a.letra} sx={{ mb: 0.5, fontWeight: a.letra === rascunho.correta ? 700 : 400, color: a.letra === rascunho.correta ? 'success.main' : undefined }}>
                        {a.letra}) {a.texto}{a.letra === rascunho.correta ? '  ✓' : ''}
                      </Typography>
                    ))}
                    {(rascunho.itens || []).map((it: any, i: number) => (
                      <Typography key={i} sx={{ mb: 0.5 }}>{i + 1}. {it.afirmacao} — <b>{it.certo ? 'CERTO' : 'ERRADO'}</b></Typography>
                    ))}
                    {!!(rascunho.palavras_chave || []).length && <Typography sx={{ mt: 1 }}><b>Palavras-chave:</b> {rascunho.palavras_chave.join(', ')}</Typography>}
                    {rascunho.padrao_resposta && <Typography sx={{ mt: 1, whiteSpace: 'pre-wrap' }}><b>Padrão de resposta:</b> {rascunho.padrao_resposta}</Typography>}
                    {rascunho.justificativa && <Typography sx={{ mt: 1, whiteSpace: 'pre-wrap' }} color="text.secondary"><b>Justificativa:</b> {rascunho.justificativa}</Typography>}
                  </Box>
                )}
              </Box>
            )}

            {aba === 'revisar' && (
              <Box>
                {!temEnunciado && <Alert severity="warning" sx={{ mb: 2 }}>Escreva o enunciado antes de pedir a revisão.</Alert>}
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  <Button variant="contained" onClick={revisar} disabled={carregando || !temEnunciado} startIcon={<AutoAwesomeIcon />}>
                    {revisao ? 'Revisar de novo' : 'Revisar esta questão'}
                  </Button>
                  {carregando && <CircularProgress size={22} />}
                </Box>
                {revisao && (
                  <Box sx={{ mt: 3 }}>
                    <Stack direction="row" spacing={1} sx={{ mb: 1.5, flexWrap: 'wrap' }}>
                      <Chip color={AVALIACAO[revisao.avaliacao]?.cor || 'warning'} label={AVALIACAO[revisao.avaliacao]?.rotulo || revisao.avaliacao} />
                      <Chip variant="outlined" color={revisao.gabarito_confere ? 'success' : 'error'}
                        label={revisao.gabarito_confere ? 'Gabarito confere' : 'Gabarito com problema'} />
                      <Chip variant="outlined" label={`Nível estimado: ${NOME_NIVEL[revisao.nivel_estimado] || revisao.nivel_estimado}`} />
                    </Stack>
                    <Typography sx={{ mb: 1, whiteSpace: 'pre-wrap' }}>{revisao.resumo}</Typography>
                    {revisao.comentario_gabarito && <Typography sx={{ mb: 1, whiteSpace: 'pre-wrap' }} color="text.secondary"><b>Gabarito:</b> {revisao.comentario_gabarito}</Typography>}
                    {!!(revisao.problemas || []).length && (
                      <List dense>
                        {revisao.problemas.map((p: any, i: number) => (
                          <ListItem key={i} alignItems="flex-start" sx={{ px: 0 }}>
                            <Chip size="small" color={COR_GRAVIDADE[p.gravidade] || 'info'} label={p.gravidade} sx={{ mr: 1.5, mt: 0.5 }} />
                            <ListItemText primary={`${p.onde ? p.onde + ': ' : ''}${p.problema}`} secondary={p.sugestao ? `Sugestão: ${p.sugestao}` : undefined} />
                          </ListItem>
                        ))}
                      </List>
                    )}
                  </Box>
                )}
              </Box>
            )}

            {aba === 'alternativas' && (
              <Box>
                {!temEnunciado && <Alert severity="warning" sx={{ mb: 2 }}>Escreva o enunciado e a alternativa correta antes.</Alert>}
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  <TextField select size="small" label="Quantas" value={qtdDistratores} onChange={e => setQtdDistratores(Number(e.target.value))} sx={{ width: 110 }}>
                    {[1, 2, 3, 4, 5].map(n => <MenuItem key={n} value={n}>{n}</MenuItem>)}
                  </TextField>
                  <Button variant="contained" onClick={sugerirDistratores} disabled={carregando || !temEnunciado} startIcon={<AutoAwesomeIcon />}>
                    Sugerir alternativas erradas
                  </Button>
                  {carregando && <CircularProgress size={22} />}
                </Box>
                {!!distratores.length && (
                  <Box sx={{ mt: 2 }}>
                    {distratores.map((d, i) => (
                      <Box key={i} sx={{ mb: 1 }}>
                        <FormControlLabel label={d.texto} control={<Checkbox checked={d.usar}
                          onChange={e => setDistratores(distratores.map((x, j) => (j === i ? { ...x, usar: e.target.checked } : x)))} />} />
                        {d.por_que_plausivel && <Typography variant="body2" color="text.secondary" sx={{ ml: 4 }}>{d.por_que_plausivel}</Typography>}
                      </Box>
                    ))}
                    <Typography variant="body2" color="text.secondary">As marcadas entram nas alternativas erradas (primeiro nas vazias). A correta não muda.</Typography>
                  </Box>
                )}
              </Box>
            )}

            {aba === 'justificativa' && (
              <Box>
                {!temEnunciado && <Alert severity="warning" sx={{ mb: 2 }}>Escreva a questão antes de pedir a justificativa.</Alert>}
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  <Button variant="contained" onClick={justificar} disabled={carregando || !temEnunciado} startIcon={<AutoAwesomeIcon />}>
                    Escrever justificativa
                  </Button>
                  {carregando && <CircularProgress size={22} />}
                </Box>
                {justificativa && (
                  <Box sx={{ mt: 2 }}>
                    <Typography sx={{ whiteSpace: 'pre-wrap', mb: 1 }}>{justificativa.justificativa}</Typography>
                    {(justificativa.por_alternativa || []).map((p: any, i: number) => (
                      <Typography key={i} variant="body2" sx={{ mb: 0.5 }}><b>{p.letra})</b> {p.comentario}</Typography>
                    ))}
                  </Box>
                )}
              </Box>
            )}
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Fechar</Button>
        {aba === 'gerar' && rascunho && (
          <Button variant="contained" onClick={usarRascunho}>Usar no formulário</Button>
        )}
        {aba === 'alternativas' && distratores.some(d => d.usar) && (
          <Button variant="contained" onClick={usarDistratores}>Usar as marcadas</Button>
        )}
        {aba === 'justificativa' && justificativa && (
          <Button variant="contained" onClick={usarJustificativa}>Usar como justificativa</Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
