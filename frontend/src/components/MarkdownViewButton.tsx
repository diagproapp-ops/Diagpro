import { useState } from "react";
import markdownit from "markdown-it";
import type { Editor } from "@tiptap/react";

export default function MarkdownViewButton({ editor }: { editor: Editor }) {
  const [showMarkdown, setShowMarkdown] = useState(false);
  const md = new markdownit();
  return (
    <>
      <button onClick={() => setShowMarkdown(s => !s)}>Ver Markdown</button>
      {showMarkdown && <pre>{md.render(editor.getHTML())}</pre>}
    </>
  );
}