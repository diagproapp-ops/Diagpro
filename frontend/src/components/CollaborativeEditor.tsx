import React from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Collaboration from '@tiptap/extension-collaboration';
import * as Y from 'yjs';

// Cria o documento Yjs compartilhado
const ydoc = new Y.Doc();

export default function CollaborativeEditor() {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Collaboration.configure({ document: ydoc }),
      // Adicione outras extensões que quiser
    ],
    content: "<p>Colabore!</p>",
  });

  return (
    <div>
      <EditorContent editor={editor} />
    </div>
  );
}