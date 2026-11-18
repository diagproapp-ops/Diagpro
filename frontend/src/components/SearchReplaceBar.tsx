import { useState } from "react";
import type { Editor } from "@tiptap/react";

export default function SearchReplaceBar({ editor }: { editor: Editor }) {
  const [search, setSearch] = useState("");
  const [replace, setReplace] = useState("");
  const [lastIndex, setLastIndex] = useState(0);

  function handleReplaceAll() {
    let html = editor.getHTML();
    html = html.replaceAll(search, replace);
    editor.commands.setContent(html);
  }

  function handleFindNext() {
    if (!search) return;
    const html = editor.getHTML();
    // Procura pela próxima ocorrência do termo
    const lowerHtml = html.toLowerCase();
    const lowerSearch = search.toLowerCase();
    const startIdx = lowerHtml.indexOf(lowerSearch, lastIndex + 1);

    if (startIdx !== -1) {
      // Seleciona no editor usando posição aproximada
      // Para precisão, seria necessário mapear o índice do HTML para posição do documento (complexo)
      // Aqui, tentamos apenas scrollar até o termo e dar foco
      // Solução simples: destaca temporariamente o termo usando mark
      const regex = new RegExp(`(${search})`, "gi");
      const highlighted = html.replace(regex, '<mark>$1</mark>');
      editor.commands.setContent(highlighted);
      setLastIndex(startIdx);
      // Opcional: resetar o destaque após alguns segundos
      setTimeout(() => {
        editor.commands.setContent(html);
      }, 2000);
    } else {
      setLastIndex(0); // volta ao início
    }
  }

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
      <input
        value={search}
        onChange={e => {
          setSearch(e.target.value);
          setLastIndex(0);
        }}
        placeholder="Buscar..."
        style={{ padding: 4, minWidth: 120 }}
      />
      <button onClick={handleFindNext}>Buscar</button>
      <input
        value={replace}
        onChange={e => setReplace(e.target.value)}
        placeholder="Substituir..."
        style={{ padding: 4, minWidth: 120 }}
      />
      <button onClick={handleReplaceAll}>Substituir tudo</button>
    </div>
  );
}