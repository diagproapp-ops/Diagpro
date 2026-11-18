import type { Editor } from "@tiptap/react";

export default function TableOfContents({ editor }: { editor: Editor }) {
  const html = editor.getHTML();
  const matches = Array.from(html.matchAll(/<h([1-6])[^>]*>(.*?)<\/h\1>/g));
  return (
    <ul>
      {matches.map((m, i) => (
        <li key={i} style={{ marginLeft: (parseInt(m[1]) - 1) * 20 }}>
          {m[2]}
        </li>
      ))}
    </ul>
  );
}