import React, { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, EditorContent, useEditorState } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Highlight from "@tiptap/extension-highlight";
import { TextStyle, FontSize } from "@tiptap/extension-text-style";
import Color from "@tiptap/extension-color";
import FontFamily from "@tiptap/extension-font-family";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import CodeBlockLowlight from "@tiptap/extension-code-block-lowlight";
import { createLowlight, common } from "lowlight";
import CharacterCount from "@tiptap/extension-character-count";
import Link from "@tiptap/extension-link";
import Typography from "@tiptap/extension-typography";
import Youtube from "@tiptap/extension-youtube";
import Subscript from "@tiptap/extension-subscript";
import Superscript from "@tiptap/extension-superscript";
import TextAlign from "@tiptap/extension-text-align";
import Underline from "@tiptap/extension-underline";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import { Alert, Box, Portal, Snackbar, Typography as Texto } from "@mui/material";
import "katex/dist/katex.min.css";
import BarraFormatacao, { estiloConteudoEditor } from "./BarraFormatacao";
import EditorEquacao, { EquacaoEmEdicao } from "./editor/EditorEquacao";
import LocalizarSubstituir from "./editor/LocalizarSubstituir";
import { FormatoParagrafo, ImagemDimensionavel, criarEquacaoEmDestaque, criarEquacaoNaLinha } from "./editor/extensoesEditor";

// lowlight v3 exige uma instância criada com as linguagens (o módulo em si não serve).
const lowlight = createLowlight(common);

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
  const [equacao, setEquacao] = useState<EquacaoEmEdicao | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [telaCheia, setTelaCheia] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  // as extensões são criadas uma vez; o clique numa equação chama sempre a versão atual desta função
  const abrirEquacaoRef = useRef<(e: EquacaoEmEdicao) => void>(() => undefined);
  abrirEquacaoRef.current = (e) => setEquacao(e);

  const editor = useEditor({
    extensions: [
      // No Tiptap v3 o StarterKit já traz Link, Underline e um bloco de código simples; desligamos
      // esses para usar as versões configuradas abaixo sem extensões duplicadas.
      StarterKit.configure({ link: false, underline: false, codeBlock: false }),
      Placeholder.configure({ placeholder }),
      Highlight.configure({ multicolor: true }),
      TextStyle,
      Color,
      FontFamily,
      FontSize,
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
      CodeBlockLowlight.configure({ lowlight }),
      CharacterCount,
      ImagemDimensionavel,
      Link,
      Typography,
      criarEquacaoNaLinha((latex, pos) => abrirEquacaoRef.current({ latex, bloco: false, pos })),
      criarEquacaoEmDestaque((latex, pos) => abrirEquacaoRef.current({ latex, bloco: true, pos })),
      Youtube,
      Subscript,
      Superscript,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Underline,
      TaskList,
      TaskItem,
      FormatoParagrafo,
    ],
    content: value ?? "<p></p>",
    onUpdate: ({ editor }) => {
      onChange && onChange(editor.getHTML());
    },
  });

  const contagem = useEditorState({
    editor,
    selector: ({ editor: e }) => (e ? { palavras: e.storage.characterCount.words(), caracteres: e.storage.characterCount.characters() } : null),
  });

  React.useEffect(() => {
    if (editor && value !== undefined && value !== editor.getHTML()) {
      editor.commands.setContent(value || "<p></p>");
    }
  }, [value, editor]);

  // Ctrl+F abre a busca do editor; Esc sai da tela cheia
  useEffect(() => {
    if (!editor) return;
    const dom = editor.view.dom;
    const tecla = (ev: KeyboardEvent) => {
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "f") {
        ev.preventDefault();
        setBuscando(true);
      }
    };
    dom.addEventListener("keydown", tecla);
    return () => dom.removeEventListener("keydown", tecla);
  }, [editor]);
  useEffect(() => {
    if (!telaCheia) return;
    const sair = (ev: KeyboardEvent) => { if (ev.key === "Escape" && !equacao) setTelaCheia(false); };
    window.addEventListener("keydown", sair);
    return () => window.removeEventListener("keydown", sair);
  }, [telaCheia, equacao]);

  const novaEquacao = useCallback((bloco: boolean) => setEquacao({ latex: "", bloco }), []);

  const confirmarEquacao = (latex: string, bloco: boolean) => {
    if (!editor || !equacao) return;
    const pos = equacao.pos;
    const cadeia = editor.chain().focus();
    if (pos === undefined) {
      (bloco ? cadeia.insertBlockMath({ latex }) : cadeia.insertInlineMath({ latex })).run();
    } else if (bloco === equacao.bloco) {
      (bloco ? cadeia.updateBlockMath({ latex, pos }) : cadeia.updateInlineMath({ latex, pos })).run();
    } else {
      // trocou entre "na linha" e "em destaque": remove a antiga e insere a nova no mesmo lugar
      (equacao.bloco ? cadeia.deleteBlockMath({ pos }) : cadeia.deleteInlineMath({ pos })).run();
      const c2 = editor.chain().focus();
      (bloco ? c2.insertBlockMath({ latex, pos }) : c2.insertInlineMath({ latex, pos })).run();
    }
    setEquacao(null);
  };

  const removerEquacao = () => {
    if (!editor || !equacao || equacao.pos === undefined) return;
    const c = editor.chain().focus();
    (equacao.bloco ? c.deleteBlockMath({ pos: equacao.pos }) : c.deleteInlineMath({ pos: equacao.pos })).run();
    setEquacao(null);
  };

  const caixa = (
    <Box
      sx={{
        border: error ? "2px solid #EF4444" : "1px solid rgba(56, 189, 248, 0.22)",
        borderRadius: telaCheia ? 0 : "10px",
        background: telaCheia ? "#0B1220" : "rgba(6, 11, 25, 0.65)",
        color: "#F1F5F9",
        p: 1.5,
        ...(telaCheia && { position: "fixed", inset: 0, zIndex: 1650, display: "flex", flexDirection: "column" }),
      }}
    >
      {telaCheia && label && <Texto variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>{label}</Texto>}
      {renderExtraButtons && (
        <div style={{ marginBottom: 8 }}>{renderExtraButtons()}</div>
      )}
      <BarraFormatacao
        editor={editor}
        onEquacao={novaEquacao}
        onLocalizar={() => setBuscando((b) => !b)}
        telaCheia={telaCheia}
        onTelaCheia={() => setTelaCheia((t) => !t)}
        onErro={setAviso}
      />
      {buscando && editor && <LocalizarSubstituir editor={editor} onFechar={() => { setBuscando(false); editor.commands.focus(); }} />}
      {/* Área do texto rola sozinha; a barra fica sempre visível acima dela */}
      <Box
        onClick={() => editor && !editor.isFocused && editor.commands.focus()}
        sx={{
          ...estiloConteudoEditor,
          minHeight: telaCheia ? 0 : Math.min(height, 360),
          maxHeight: telaCheia ? "none" : "55vh",
          flex: telaCheia ? 1 : undefined,
          overflowY: "auto", cursor: "text", px: telaCheia ? { xs: 1, md: "12%" } : 0.5,
        }}
      >
        <EditorContent editor={editor} />
      </Box>
      {contagem && (
        <Texto variant="caption" color="text.secondary" sx={{ display: "block", textAlign: "right", mt: 0.5 }}>
          {contagem.palavras} {contagem.palavras === 1 ? "palavra" : "palavras"} · {contagem.caracteres} caracteres
        </Texto>
      )}
    </Box>
  );

  return (
    <div style={{ marginBottom: 24 }}>
      {label && !telaCheia && (
        <label style={{ fontWeight: 500, display: "block", marginBottom: 8 }}>
          {label} {required ? "*" : ""}
        </label>
      )}
      {/* Na tela cheia o editor vai para o <body>: dentro da janela de edição (que usa transform) o
          "position: fixed" ficaria preso ao tamanho da janela. */}
      {telaCheia ? <Portal>{caixa}</Portal> : caixa}
      {error && (
        <div style={{ color: "#d32f2f", fontSize: 13, marginTop: 4 }}>{error}</div>
      )}
      <EditorEquacao aberta={equacao} onFechar={() => setEquacao(null)} onConfirmar={confirmarEquacao} onRemover={removerEquacao} />
      <Snackbar open={!!aviso} autoHideDuration={5000} onClose={() => setAviso(null)} sx={{ zIndex: 1900 }}>
        <Alert severity="warning" onClose={() => setAviso(null)}>{aviso}</Alert>
      </Snackbar>
    </div>
  );
}
