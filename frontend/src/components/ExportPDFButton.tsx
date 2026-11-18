import html2pdf from 'html2pdf.js';
import type { Editor } from "@tiptap/react";

export default function ExportPDFButton({ editor }: { editor: Editor }) {
  return (
    <button
      onClick={() => html2pdf().from(editor.getHTML()).save()}
      disabled={!editor}
    >
      Exportar PDF
    </button>
  );
}