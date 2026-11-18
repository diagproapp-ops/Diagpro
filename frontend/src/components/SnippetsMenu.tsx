import type { Editor } from "@tiptap/react";

const snippets = [
  { name: "Assinatura", html: "<p>Atenciosamente,<br>Seu Nome</p>" },
  { name: "Cabeçalho padrão", html: "<h1>Título</h1>" }
];

export default function SnippetsMenu({ editor }: { editor: Editor }) {
  return (
    <select onChange={e => {
      const value = Number(e.target.value);
      if (!isNaN(value) && snippets[value]) {
        editor.chain().focus().insertContent(snippets[value].html).run();
      }
    }}>
      <option value="">Inserir snippet...</option>
      {snippets.map((s, i) => (
        <option value={i} key={s.name}>{s.name}</option>
      ))}
    </select>
  );
}