import { Node, mergeAttributes } from '@tiptap/core';
import katex from 'katex';

export const MathExtension = Node.create({
  name: 'math',
  inline: true,
  group: 'inline',
  atom: true,

  addAttributes() {
    return {
      latex: {
        default: '',
        parseHTML: element => element.getAttribute('data-latex'),
        renderHTML: attributes => ({
          'data-latex': attributes.latex,
        }),
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-type="math"]',
      },
    ];
  },

  // Corrigido: sem '0' no array!
  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes({ 'data-type': 'math' }, HTMLAttributes)];
  },

  addNodeView() {
    return ({ node }) => {
      const span = document.createElement('span');
      span.setAttribute('data-type', 'math');
      span.setAttribute('data-latex', node.attrs.latex);

      try {
        span.innerHTML = katex.renderToString(node.attrs.latex, {
          throwOnError: false,
          displayMode: false,
        });
      } catch (e) {
        span.textContent = node.attrs.latex;
      }
      span.className = 'math-tiptap';

      return {
        dom: span,
      };
    };
  },
});