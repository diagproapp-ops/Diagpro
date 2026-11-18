import { useState } from "react";
import type { Editor } from "@tiptap/react";

export function useVersionHistory(editor: Editor) {
  const [history, setHistory] = useState<string[]>([]);

  const saveVersion = () => setHistory(h => [...h, editor.getHTML()]);
  const restoreVersion = (index: number) => editor.commands.setContent(history[index]);

  return { history, saveVersion, restoreVersion };
}