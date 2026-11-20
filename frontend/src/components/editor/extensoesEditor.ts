import { Extension } from '@tiptap/core';
import Image from '@tiptap/extension-image';
import { BlockMath, InlineMath } from '@tiptap/extension-mathematics';

/**
 * Extensões próprias do editor de questões. Tudo o que elas geram é reproduzido na prova (backend/app/html_to_docx.py):
 * recuo (margin-left), recuo da primeira linha (text-indent), espaçamento entre linhas (line-height) e largura de
 * imagem (width em %).
 */

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    formatoParagrafo: {
      aumentarRecuo: () => ReturnType;
      diminuirRecuo: () => ReturnType;
      alternarRecuoPrimeiraLinha: () => ReturnType;
      definirAlturaLinha: (altura: string | null) => ReturnType;
    };
    imagemDimensionavel: {
      definirLarguraImagem: (largura: string | null) => ReturnType;
    };
  }
}

const TIPOS_PARAGRAFO = ['paragraph', 'heading'];
const PASSO_RECUO_EM = 1.5;
const MAX_NIVEL_RECUO = 8;

export const FormatoParagrafo = Extension.create({
  name: 'formatoParagrafo',
  addGlobalAttributes() {
    return [
      {
        types: TIPOS_PARAGRAFO,
        attributes: {
          recuo: {
            default: 0,
            parseHTML: (el: HTMLElement) => {
              const m = /([\d.]+)em/.exec(el.style.marginLeft || '');
              return m ? Math.min(MAX_NIVEL_RECUO, Math.round(parseFloat(m[1]) / PASSO_RECUO_EM)) : 0;
            },
            renderHTML: (attrs: Record<string, any>) =>
              attrs.recuo ? { style: `margin-left: ${attrs.recuo * PASSO_RECUO_EM}em` } : {},
          },
          recuoPrimeiraLinha: {
            default: false,
            parseHTML: (el: HTMLElement) => !!el.style.textIndent && el.style.textIndent !== '0px',
            renderHTML: (attrs: Record<string, any>) => (attrs.recuoPrimeiraLinha ? { style: 'text-indent: 2em' } : {}),
          },
          alturaLinha: {
            default: null,
            parseHTML: (el: HTMLElement) => el.style.lineHeight || null,
            renderHTML: (attrs: Record<string, any>) => (attrs.alturaLinha ? { style: `line-height: ${attrs.alturaLinha}` } : {}),
          },
        },
      },
    ];
  },
  addCommands() {
    const mudar = (fn: (attrs: Record<string, any>) => Record<string, any>) => () => ({ state, tr, dispatch }: any) => {
      const { from, to } = state.selection;
      let mudou = false;
      state.doc.nodesBetween(from, to, (node: any, pos: number) => {
        if (TIPOS_PARAGRAFO.includes(node.type.name)) {
          tr.setNodeMarkup(pos, undefined, { ...node.attrs, ...fn(node.attrs) });
          mudou = true;
        }
      });
      if (mudou && dispatch) dispatch(tr);
      return mudou;
    };
    return {
      aumentarRecuo: mudar((a) => ({ recuo: Math.min(MAX_NIVEL_RECUO, (a.recuo || 0) + 1) })),
      diminuirRecuo: mudar((a) => ({ recuo: Math.max(0, (a.recuo || 0) - 1) })),
      alternarRecuoPrimeiraLinha: mudar((a) => ({ recuoPrimeiraLinha: !a.recuoPrimeiraLinha })),
      definirAlturaLinha: (altura: string | null) => mudar(() => ({ alturaLinha: altura }))(),
    };
  },
  addKeyboardShortcuts() {
    return {
      // Tab dentro de lista é usado pela própria lista (subnível); fora dela, aumenta o recuo
      Tab: () => (this.editor.isActive('listItem') ? false : this.editor.commands.aumentarRecuo()),
      'Shift-Tab': () => (this.editor.isActive('listItem') ? false : this.editor.commands.diminuirRecuo()),
    };
  },
});

/** Imagem embutida (base64) com largura escolhida em % da coluna. */
export const ImagemDimensionavel = Image.extend({
  name: 'image',
  addAttributes() {
    return {
      ...this.parent?.(),
      largura: {
        default: null,
        parseHTML: (el: HTMLElement) => (/^\d+%$/.test(el.style.width || '') ? el.style.width : null),
        renderHTML: (attrs: Record<string, any>) => (attrs.largura ? { style: `width: ${attrs.largura}` } : {}),
      },
    };
  },
  addCommands() {
    return {
      ...this.parent?.(),
      definirLarguraImagem: (largura: string | null) => ({ commands }: any) =>
        commands.updateAttributes('image', { largura }),
    };
  },
}).configure({ allowBase64: true, inline: false });

/** Equação na linha; também lê o formato antigo do editor (<span data-type="math" data-latex>). */
export const criarEquacaoNaLinha = (onClick: (latex: string, pos: number) => void) =>
  InlineMath.extend({
    parseHTML() {
      return [
        { tag: 'span[data-type="inline-math"]' },
        { tag: 'span[data-type="math"]', getAttrs: (el: HTMLElement) => ({ latex: el.getAttribute('data-latex') || '' }) },
      ];
    },
  }).configure({
    katexOptions: { throwOnError: false },
    onClick: (node: any, pos: number) => onClick(node.attrs.latex || '', pos),
  });

/** Equação em destaque (linha própria, centralizada). */
export const criarEquacaoEmDestaque = (onClick: (latex: string, pos: number) => void) =>
  BlockMath.configure({
    katexOptions: { throwOnError: false, displayMode: true },
    onClick: (node: any, pos: number) => onClick(node.attrs.latex || '', pos),
  });
