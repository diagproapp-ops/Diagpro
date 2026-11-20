import { useEffect, useState } from 'react';
import api from '../../api';

export type CausaIA = { codigo: 'plataforma_desligada' | 'sem_chave' | 'sem_cliente' | 'banca_desligada' | 'perfil' | string; texto: string };
export type StatusIA = { disponivel: boolean; recursos: Record<string, boolean>; motivo: string; provedor: string; causas?: CausaIA[] };

const VAZIO: StatusIA = { disponivel: false, recursos: {}, motivo: '', provedor: '', causas: [] };
let cache: { em: number; chave: string; status: StatusIA } | null = null;

// Status da IA para quem está logado (cache de 60 s; muda de cliente = nova consulta)
export function useStatusIA(): StatusIA {
  const chave = `${localStorage.getItem('authToken') || ''}|${localStorage.getItem('clienteEmGestao') || ''}`;
  const [status, setStatus] = useState<StatusIA>(cache && cache.chave === chave ? cache.status : VAZIO);
  useEffect(() => {
    if (cache && cache.chave === chave && Date.now() - cache.em < 60000) { setStatus(cache.status); return; }
    let vivo = true;
    api.get('/ia/status')
      .then(({ data }) => { cache = { em: Date.now(), chave, status: data }; if (vivo) setStatus(data); })
      .catch(() => { if (vivo) setStatus(VAZIO); });
    return () => { vivo = false; };
  }, [chave]);
  return status;
}

export function podeUsar(status: StatusIA, recurso: string): boolean {
  return status.disponivel && !!status.recursos[recurso];
}

// Texto puro devolvido pela IA -> HTML seguro para o editor (escapa tudo; cada linha vira um parágrafo)
export function textoParaHtml(texto: string): string {
  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  return (texto || '').split(/\n+/).map(l => l.trim()).filter(Boolean).map(l => `<p>${esc(l)}</p>`).join('') || '<p></p>';
}

export function htmlParaTexto(html: string): string {
  const div = document.createElement('div');
  div.innerHTML = (html || '').replace(/<\/(p|div|li|h\d)>/gi, '\n').replace(/<br\s*\/?>/gi, '\n');
  return (div.textContent || '').replace(/\n{2,}/g, '\n').trim();
}

export function erroIA(e: any): string {
  const det = e?.response?.data?.detail;
  if (typeof det === 'string') return det;
  if (Array.isArray(det)) return 'Confira os campos enviados à IA.';
  return 'Não foi possível falar com a IA agora.';
}

// ------------------------------------------------------------------ formulário de questão <-> IA
export type QuestaoIA = {
  tipo: string; assunto: string; nivel?: string; enunciado: string;
  alternativas: { letra: string; texto: string }[]; correta: string;
  itens: { afirmacao: string; certo: boolean | null }[]; padrao_resposta: string;
};

// Mesmo formato de form das telas Criar/Editar/Revisar questão
export function formParaQuestaoIA(form: any): QuestaoIA {
  const tipo = form.tipo;
  return {
    tipo,
    assunto: (form.indicacao_conteudo || '').slice(0, 500),
    nivel: ['MUITO_FACIL', 'FACIL', 'MEDIO', 'DIFICIL', 'MUITO_DIFICIL'].includes(form.nivel_dificuldade) ? form.nivel_dificuldade : undefined,
    enunciado: form.enunciado || '',
    alternativas: tipo === 'MULTIPLA_ESCOLHA'
      ? (form.alternativas || []).map((a: any) => ({ letra: a.letra, texto: a.texto || '' })) : [],
    correta: tipo === 'MULTIPLA_ESCOLHA' ? ((form.alternativas || []).find((a: any) => a.correta)?.letra || form.resposta_correta || '') : '',
    itens: tipo === 'CERTO_ERRADO'
      ? (form.itens_comando || []).map((t: string, i: number) => ({
        afirmacao: t || '', certo: form.respostas_certo_errado?.[i] === 'CERTO' ? true : form.respostas_certo_errado?.[i] === 'ERRADO' ? false : null,
      })) : [],
    padrao_resposta: '',
  };
}

export type AplicacaoIA = {
  enunciado?: string;                                   // HTML
  alternativas?: { letra: string; texto: string }[];    // HTML
  correta?: string;
  itens?: { afirmacao: string; certo: boolean }[];      // HTML
  palavras_chave?: string[];
  justificativa?: string;                               // HTML
  nivel?: string;
  distratores?: string[];                               // HTML, vão para as alternativas erradas
};

const LETRAS = ['A', 'B', 'C', 'D', 'E', 'F'];

export function aplicarNoForm(prev: any, ap: AplicacaoIA): any {
  const novo = { ...prev };
  if (ap.enunciado !== undefined) novo.enunciado = ap.enunciado;
  if (ap.alternativas && ap.alternativas.length) {
    const correta = ap.correta || 'A';
    novo.alternativas = ap.alternativas.slice(0, LETRAS.length).map((a, i) => {
      const letra = LETRAS[i];
      const antiga = (prev.alternativas || [])[i] || {};
      return { ...antiga, letra, texto: a.texto, texto_formatado: null, correta: (a.letra || letra) === correta };
    });
    const marcada = novo.alternativas.find((a: any) => a.correta);
    novo.resposta_correta = marcada ? marcada.letra : novo.alternativas[0]?.letra;
    if (!marcada && novo.alternativas[0]) novo.alternativas[0].correta = true;
  }
  if (ap.distratores && ap.distratores.length) {
    const fila = [...ap.distratores];
    const alts = (prev.alternativas || []).map((a: any) => ({ ...a }));
    // primeiro as erradas vazias, depois as demais erradas
    const ordem = [...alts.keys()].filter(i => !alts[i].correta)
      .sort((x, y) => Number(!!htmlParaTexto(alts[x].texto)) - Number(!!htmlParaTexto(alts[y].texto)));
    for (const i of ordem) {
      if (!fila.length) break;
      alts[i].texto = fila.shift();
      alts[i].texto_formatado = null;
    }
    novo.alternativas = alts;
  }
  if (ap.itens && ap.itens.length) {
    novo.quantidade_itens = ap.itens.length;
    novo.itens_comando = ap.itens.map(i => i.afirmacao);
    novo.respostas_certo_errado = ap.itens.map(i => (i.certo ? 'CERTO' : 'ERRADO'));
  }
  if (ap.palavras_chave && ap.palavras_chave.length) novo.palavras_chave_discursiva = ap.palavras_chave.join(', ');
  if (ap.justificativa !== undefined) novo.justificativa_questao = ap.justificativa;
  if (ap.nivel) novo.nivel_dificuldade = ap.nivel;
  return novo;
}
