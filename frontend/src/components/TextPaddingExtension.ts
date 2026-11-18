import { Extension, Command } from '@tiptap/core';

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    textPadding: {
      setPaddingLeft: (px: number) => ReturnType;
      setPaddingRight: (px: number) => ReturnType;
      clearPadding: () => ReturnType;
    };
  }
}

export const TextPaddingExtension = Extension.create({
  name: 'textPadding',

  addCommands() {
    return {
      setPaddingLeft:
        (px: number): Command =>
        ({ tr, state, dispatch }) => {
          const { from, to } = state.selection;
          state.doc.nodesBetween(from, to, (node, pos) => {
            if (node.type.name === 'paragraph') {
              let style = node.attrs.style || '';
              style = style.replace(/padding-left:\s*\d+px;?/g, '');
              style = style.trim();
              if (style.length > 0 && !style.endsWith(';')) style += ';';
              style += `padding-left: ${px}px;`;
              tr.setNodeMarkup(pos, undefined, { ...node.attrs, style });
            }
          });
          if (dispatch) dispatch(tr);
          return true;
        },
      setPaddingRight:
        (px: number): Command =>
        ({ tr, state, dispatch }) => {
          const { from, to } = state.selection;
          state.doc.nodesBetween(from, to, (node, pos) => {
            if (node.type.name === 'paragraph') {
              let style = node.attrs.style || '';
              style = style.replace(/padding-right:\s*\d+px;?/g, '');
              style = style.trim();
              if (style.length > 0 && !style.endsWith(';')) style += ';';
              style += `padding-right: ${px}px;`;
              tr.setNodeMarkup(pos, undefined, { ...node.attrs, style });
            }
          });
          if (dispatch) dispatch(tr);
          return true;
        },
      clearPadding:
        (): Command =>
        ({ tr, state, dispatch }) => {
          const { from, to } = state.selection;
          state.doc.nodesBetween(from, to, (node, pos) => {
            if (node.type.name === 'paragraph') {
              let style = node.attrs.style || '';
              style = style.replace(/padding-(left|right):\s*\d+px;?/g, '');
              tr.setNodeMarkup(pos, undefined, { ...node.attrs, style: style });
            }
          });
          if (dispatch) dispatch(tr);
          return true;
        },
    };
  },
});