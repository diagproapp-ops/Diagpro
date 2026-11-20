import React, { useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Divider, List,
  ListItemButton, ListItemText, Typography,
} from '@mui/material';
import api from '../api';
import { htmlParaTexto } from './ia/iaComum';

type Versao = { versao: number; criada_em: string; motivo: string; autor: string | null; resumo: string };

const MOTIVOS: Record<string, string> = { criada: 'Criada', editada: 'Editada', anterior: 'Estado anterior ao histórico' };
const rotuloMotivo = (m: string) => MOTIVOS[m] || (m.startsWith('revisada') ? `Revisão (${m.split(': ')[1] || ''})` : m);
const dataHora = (iso: string) => new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });

// Texto comparável de uma questão (enunciado, alternativas/itens, justificativa) a partir do formato da API
export function textoDaQuestao(q: any): string[] {
  if (!q) return [];
  const linhas = [`Enunciado: ${htmlParaTexto(q.enunciado || '')}`];
  (q.alternativas || []).forEach((a: any) => linhas.push(`${a.letra}) ${htmlParaTexto(a.texto_opcao ?? a.texto ?? '')}${a.correta ? '  ✓' : ''}`));
  (q.itens_vf || []).forEach((i: any, n: number) => linhas.push(`Item ${n + 1}: ${htmlParaTexto(i.afirmacao || '')} — ${i.valor_correto ? 'CERTO' : 'ERRADO'}`));
  if (q.justificativa_questao) linhas.push(`Justificativa: ${htmlParaTexto(q.justificativa_questao)}`);
  if (q.nivel_dificuldade) linhas.push(`Nível: ${q.nivel_dificuldade}`);
  return linhas;
}

type Props = {
  open: boolean; onClose: () => void; base: string; atual: any;
  onRestaurar: (questao: any, versao: number) => void;
};

// Histórico de versões de uma questão: lista, compara com o formulário atual e traz uma versão de volta
export default function HistoricoVersoesDialog({ open, onClose, base, atual, onRestaurar }: Props) {
  const [versoes, setVersoes] = useState<Versao[] | null>(null);
  const [escolhida, setEscolhida] = useState<{ versao: number; questao: any } | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setEscolhida(null);
    api.get(`${base}/versoes`).then(({ data }) => setVersoes(data)).catch(() => { setVersoes([]); setErro('Não foi possível carregar o histórico.'); });
  }, [open, base]);

  const abrir = async (v: Versao) => {
    try {
      const { data } = await api.get(`${base}/versoes/${v.versao}`);
      setEscolhida({ versao: v.versao, questao: data.questao });
    } catch {
      setErro('Não foi possível abrir essa versão.');
    }
  };

  const daVersao = textoDaQuestao(escolhida?.questao);
  const doAtual = textoDaQuestao(atual);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>Histórico de versões</DialogTitle>
      <DialogContent dividers>
        {erro && <Alert severity="error" sx={{ mb: 2 }}>{erro}</Alert>}
        {!versoes ? <CircularProgress /> : !versoes.length ? (
          <Typography color="text.secondary">Ainda não há versões salvas. A partir da próxima alteração, cada salvamento fica registrado.</Typography>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '300px 1fr' }, gap: 2 }}>
            <List dense sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, maxHeight: 460, overflowY: 'auto' }}>
              {versoes.map(v => (
                <ListItemButton key={v.versao} selected={escolhida?.versao === v.versao} onClick={() => abrir(v)}>
                  <ListItemText
                    primary={<Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}><b>Versão {v.versao}</b><Chip size="small" label={rotuloMotivo(v.motivo)} /></Box>}
                    secondary={`${dataHora(v.criada_em)}${v.autor ? ` • ${v.autor}` : ''}`} />
                </ListItemButton>
              ))}
            </List>
            <Box>
              {!escolhida ? <Typography color="text.secondary">Escolha uma versão para ver e comparar com o formulário atual.</Typography> : (
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
                  {[{ titulo: `Versão ${escolhida.versao}`, linhas: daVersao, outro: doAtual },
                    { titulo: 'Formulário atual', linhas: doAtual, outro: daVersao }].map(col => (
                    <Box key={col.titulo}>
                      <Typography variant="subtitle2" fontWeight={700}>{col.titulo}</Typography>
                      <Divider sx={{ my: 1 }} />
                      {col.linhas.map((l, i) => (
                        <Typography key={i} variant="body2" sx={{ mb: 0.75, whiteSpace: 'pre-wrap', px: 0.75, borderRadius: 1,
                          bgcolor: col.outro.includes(l) ? 'transparent' : 'rgba(245, 158, 11, 0.16)' }}>{l}</Typography>
                      ))}
                    </Box>
                  ))}
                  <Typography variant="caption" color="text.secondary" sx={{ gridColumn: { md: '1 / 3' } }}>
                    Em destaque: o que é diferente entre as duas. Imagens não entram na comparação nem na restauração.
                  </Typography>
                </Box>
              )}
            </Box>
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Fechar</Button>
        {escolhida && (
          <Button variant="contained" onClick={() => { onRestaurar(escolhida.questao, escolhida.versao); onClose(); }}>
            Trazer esta versão para o formulário
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

// Antes de salvar: avisa se já existe questão muito parecida na banca (comparação local, no servidor)
export async function confirmarSeHouverParecida(enunciado: string, excluirId?: string): Promise<boolean> {
  try {
    const { data } = await api.post('/questoes/parecidas', { enunciado, excluir_id: excluirId });
    const fortes = (data.parecidas || []).filter((p: any) => p.similaridade >= 80);
    if (!fortes.length) return true;
    const p = fortes[0];
    const qual = p.detalhes_ocultos ? 'no banco de questões da banca' : `(${p.codigo}${p.evento ? `, ${p.evento}` : ''})`;
    return window.confirm(`Já existe uma questão ${p.similaridade}% parecida ${qual}.\n\nDeseja salvar mesmo assim?`);
  } catch {
    return true;  // a checagem nunca impede de salvar
  }
}
