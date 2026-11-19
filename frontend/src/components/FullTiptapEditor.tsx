import React from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import BubbleMenu from "@tiptap/extension-bubble-menu";
import FloatingMenu from "@tiptap/extension-floating-menu";
import Highlight from "@tiptap/extension-highlight";
import { TextStyle } from "@tiptap/extension-text-style";
import Color from "@tiptap/extension-color";
import FontFamily from "@tiptap/extension-font-family";
import { Table } from "@tiptap/extension-table";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import CodeBlockLowlight from "@tiptap/extension-code-block-lowlight";
import * as lowlight from "lowlight";
import CharacterCount from "@tiptap/extension-character-count";
import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import Typography from "@tiptap/extension-typography";
import Mathematics from "@tiptap/extension-mathematics";
import Youtube from "@tiptap/extension-youtube";
import Subscript from "@tiptap/extension-subscript";
import Superscript from "@tiptap/extension-superscript";
import TextAlign from "@tiptap/extension-text-align";
import Underline from "@tiptap/extension-underline";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import "katex/dist/katex.min.css";

export default function FullTiptapEditor({
  value,
  onChange,
  label,
  error,
  required,
  height = 220,
  placeholder = "Digite o texto...",
  renderExtraButtons,
}: {
  value?: string;
  onChange?: (val: string) => void;
  label?: string;
  error?: string;
  required?: boolean;
  height?: number;
  placeholder?: string;
  renderExtraButtons?: () => React.ReactNode;
}) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder }),
      BubbleMenu,
      FloatingMenu,
      Highlight,
      TextStyle,
      Color,
      FontFamily,
      Table.configure({ resizable: true }),
      TableCell,
      TableHeader,
      CodeBlockLowlight.configure({ lowlight }),
      CharacterCount,
      Image,
      Link,
      Typography,
      Mathematics,
      Youtube,
      Subscript,
      Superscript,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Underline,
      TaskList,
      TaskItem,
    ],
    content: value ?? "<p></p>",
    onUpdate: ({ editor }) => {
      onChange && onChange(editor.getHTML());
    },
  });

  React.useEffect(() => {
    if (editor && value !== undefined && value !== editor.getHTML()) {
      editor.commands.setContent(value || "<p></p>");
    }
  }, [value, editor]);

  return (
    <div style={{ marginBottom: 24 }}>
      {label && (
        <label style={{ fontWeight: 500, display: "block", marginBottom: 8 }}>
          {label} {required ? "*" : ""}
        </label>
      )}
      <div
        style={{
          border: error ? "2px solid #EF4444" : "1px solid rgba(56, 189, 248, 0.22)",
          borderRadius: 10,
          background: "rgba(6, 11, 25, 0.65)",
          color: "#F1F5F9",
          minHeight: height,
          padding: 12,
        }}
      >
        {renderExtraButtons && (
          <div style={{ marginBottom: 8 }}>{renderExtraButtons()}</div>
        )}
        <EditorContent editor={editor} />
      </div>
      {error && (
        <div style={{ color: "#d32f2f", fontSize: 13, marginTop: 4 }}>{error}</div>
      )}
    </div>
  );
}
