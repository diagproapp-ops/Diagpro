import { Extension, Command } from '@tiptap/core';

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    indent: {
      setIndent: (level: number) => ReturnType;
    };
  }
}

export const IndentExtension = Extension.create({
  name: 'indent',
  addCommands() {
    return {
      setIndent:
        (level: number): Command =>
        ({ state, dispatch }) => {
          const { from, to } = state.selection;
          let tr = state.tr;
          let changed = false;

          state.doc.nodesBetween(from, to, (node, pos) => {
            if (node.type.name === 'paragraph') {
              tr = tr.setNodeMarkup(pos, undefined, {
                ...node.attrs,
                class: `indent-${level}`,
              });
              changed = true;
            }
          });

          if (changed) {
            dispatch?.(tr);
            return true;
          }
          return false;
        },
    };
  },
});