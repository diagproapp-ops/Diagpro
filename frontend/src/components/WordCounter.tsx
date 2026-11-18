import type { Editor } from "@tiptap/react";

export default function WordCounter({ editor }: { editor?: Editor | null }) {
  return (
    <div>
      Palavras: {editor?.storage.characterCount.words?.()} | 
      Caracteres: {editor?.storage.characterCount.characters?.()}
    </div>
  );
}