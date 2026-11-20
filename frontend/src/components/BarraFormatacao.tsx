import React, { useState } from "react";
import { Editor, useEditorState } from "@tiptap/react";
import { Box, Divider, IconButton, Menu, MenuItem, Tooltip } from "@mui/material";
import UndoIcon from "@mui/icons-material/Undo";
import RedoIcon from "@mui/icons-material/Redo";
import FormatBoldIcon from "@mui/icons-material/FormatBold";
import FormatItalicIcon from "@mui/icons-material/FormatItalic";
import FormatUnderlinedIcon from "@mui/icons-material/FormatUnderlined";
import StrikethroughSIcon from "@mui/icons-material/StrikethroughS";
import BorderColorIcon from "@mui/icons-material/BorderColor";
import SuperscriptIcon from "@mui/icons-material/Superscript";
import SubscriptIcon from "@mui/icons-material/Subscript";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import FormatListNumberedIcon from "@mui/icons-material/FormatListNumbered";
import FormatAlignLeftIcon from "@mui/icons-material/FormatAlignLeft";
import FormatAlignCenterIcon from "@mui/icons-material/FormatAlignCenter";
import FormatAlignRightIcon from "@mui/icons-material/FormatAlignRight";
import FormatAlignJustifyIcon from "@mui/icons-material/FormatAlignJustify";
import FormatQuoteIcon from "@mui/icons-material/FormatQuote";
import TableChartOutlinedIcon from "@mui/icons-material/TableChartOutlined";
import FormatClearIcon from "@mui/icons-material/FormatClear";

/**
 * Barra de formatação do editor de questões. Só oferece o que a prova diagramada (DOCX) reproduz:
 * negrito, itálico, sublinhado, tachado, marca-texto, sobrescrito/subscrito, listas, alinhamento,
 * citação e tabela.
 */

// Estilos do conteúdo do editor e da pré-visualização (listas, citação, tabela e marca-texto visíveis no tema escuro).
export const estiloConteudoEditor = {
  "& .ProseMirror": { outline: "none", minHeight: 120 },
  "& ul, & ol": { pl: 3.5, my: 1 },
  "& ul": { listStyleType: "disc" },
  "& ol": { listStyleType: "decimal" },
  "& li > p": { my: 0.25 },
  "& blockquote": { borderLeft: "3px solid rgba(56, 189, 248, 0.6)", pl: 2, ml: 0, my: 1, color: "inherit", opacity: 0.9 },
  "& mark": { backgroundColor: "#FDE047", color: "#111827", borderRadius: "2px", px: "1px" },
  "& table": { borderCollapse: "collapse", my: 1, width: "100%", tableLayout: "fixed" },
  "& td, & th": { border: "1px solid rgba(148, 163, 184, 0.55)", p: "4px 8px", verticalAlign: "top", position: "relative" },
  "& th": { fontWeight: 700, bgcolor: "rgba(148, 163, 184, 0.12)" },
  "& .selectedCell": { bgcolor: "rgba(56, 189, 248, 0.18)" },
  "& p.is-editor-empty:first-of-type::before": {
    content: "attr(data-placeholder)", color: "rgba(148, 163, 184, 0.7)", float: "left", height: 0, pointerEvents: "none",
  },
};

type BotaoProps = { titulo: string; ativo?: boolean; desativado?: boolean; onClick: () => void; children: React.ReactNode };

function Botao({ titulo, ativo, desativado, onClick, children }: BotaoProps) {
  return (
    <Tooltip title={titulo} arrow>
      <span>
        <IconButton
          size="small"
          aria-label={titulo}
          aria-pressed={ativo ?? undefined}
          disabled={desativado}
          // onMouseDown evita que o editor perca a seleção ao clicar no botão
          onMouseDown={(e) => e.preventDefault()}
          onClick={onClick}
          sx={{
            borderRadius: 1.5,
            color: ativo ? "#38BDF8" : "text.secondary",
            bgcolor: ativo ? "rgba(56, 189, 248, 0.16)" : "transparent",
            "&:hover": { bgcolor: ativo ? "rgba(56, 189, 248, 0.24)" : "rgba(148, 163, 184, 0.12)" },
          }}
        >
          {children}
        </IconButton>
      </span>
    </Tooltip>
  );
}

const Separador = () => <Divider orientation="vertical" flexItem sx={{ mx: 0.5, my: 0.5 }} />;

export default function BarraFormatacao({ editor }: { editor: Editor | null }) {
  const [menuTabela, setMenuTabela] = useState<null | HTMLElement>(null);

  const s = useEditorState({
    editor,
    selector: ({ editor: e }) => {
      if (!e) return null;
      return {
        negrito: e.isActive("bold"),
        italico: e.isActive("italic"),
        sublinhado: e.isActive("underline"),
        tachado: e.isActive("strike"),
        marca: e.isActive("highlight"),
        sobrescrito: e.isActive("superscript"),
        subscrito: e.isActive("subscript"),
        marcadores: e.isActive("bulletList"),
        numerada: e.isActive("orderedList"),
        citacao: e.isActive("blockquote"),
        esquerda: e.isActive({ textAlign: "left" }),
        centro: e.isActive({ textAlign: "center" }),
        direita: e.isActive({ textAlign: "right" }),
        justificado: e.isActive({ textAlign: "justify" }),
        naTabela: e.isActive("table"),
        podeDesfazer: e.can().undo(),
        podeRefazer: e.can().redo(),
      };
    },
  });

  if (!editor || !s) return null;
  const c = () => editor.chain().focus();
  const fecharTabela = (acao?: () => void) => { setMenuTabela(null); acao && acao(); };

  return (
    <Box
      role="toolbar"
      aria-label="Formatação do texto"
      sx={{
        display: "flex", flexWrap: "wrap", alignItems: "center", gap: 0.25,
        p: 0.5, mb: 1, borderRadius: 2,
        bgcolor: "rgba(15, 23, 42, 0.85)", border: "1px solid rgba(148, 163, 184, 0.18)",
        position: "sticky", top: 0, zIndex: 2,
      }}
    >
      <Botao titulo="Desfazer (Ctrl+Z)" desativado={!s.podeDesfazer} onClick={() => c().undo().run()}><UndoIcon fontSize="small" /></Botao>
      <Botao titulo="Refazer (Ctrl+Y)" desativado={!s.podeRefazer} onClick={() => c().redo().run()}><RedoIcon fontSize="small" /></Botao>
      <Separador />
      <Botao titulo="Negrito (Ctrl+B)" ativo={s.negrito} onClick={() => c().toggleBold().run()}><FormatBoldIcon fontSize="small" /></Botao>
      <Botao titulo="Itálico (Ctrl+I)" ativo={s.italico} onClick={() => c().toggleItalic().run()}><FormatItalicIcon fontSize="small" /></Botao>
      <Botao titulo="Sublinhado (Ctrl+U)" ativo={s.sublinhado} onClick={() => c().toggleUnderline().run()}><FormatUnderlinedIcon fontSize="small" /></Botao>
      <Botao titulo="Tachado" ativo={s.tachado} onClick={() => c().toggleStrike().run()}><StrikethroughSIcon fontSize="small" /></Botao>
      <Botao titulo="Marca-texto (Ctrl+Shift+H)" ativo={s.marca} onClick={() => c().toggleHighlight().run()}><BorderColorIcon fontSize="small" /></Botao>
      <Botao titulo="Sobrescrito (ex.: x²)" ativo={s.sobrescrito} onClick={() => c().toggleSuperscript().run()}><SuperscriptIcon fontSize="small" /></Botao>
      <Botao titulo="Subscrito (ex.: H₂O)" ativo={s.subscrito} onClick={() => c().toggleSubscript().run()}><SubscriptIcon fontSize="small" /></Botao>
      <Separador />
      <Botao titulo="Lista com marcadores" ativo={s.marcadores} onClick={() => c().toggleBulletList().run()}><FormatListBulletedIcon fontSize="small" /></Botao>
      <Botao titulo="Lista numerada" ativo={s.numerada} onClick={() => c().toggleOrderedList().run()}><FormatListNumberedIcon fontSize="small" /></Botao>
      <Botao titulo="Citação / texto de apoio recuado" ativo={s.citacao} onClick={() => c().toggleBlockquote().run()}><FormatQuoteIcon fontSize="small" /></Botao>
      <Separador />
      <Botao titulo="Alinhar à esquerda" ativo={s.esquerda} onClick={() => c().setTextAlign("left").run()}><FormatAlignLeftIcon fontSize="small" /></Botao>
      <Botao titulo="Centralizar" ativo={s.centro} onClick={() => c().setTextAlign("center").run()}><FormatAlignCenterIcon fontSize="small" /></Botao>
      <Botao titulo="Alinhar à direita" ativo={s.direita} onClick={() => c().setTextAlign("right").run()}><FormatAlignRightIcon fontSize="small" /></Botao>
      <Botao titulo="Justificar" ativo={s.justificado} onClick={() => c().setTextAlign("justify").run()}><FormatAlignJustifyIcon fontSize="small" /></Botao>
      <Separador />
      <Tooltip title="Tabela" arrow>
        <IconButton
          size="small"
          aria-label="Tabela"
          onMouseDown={(e) => e.preventDefault()}
          onClick={(e) => setMenuTabela(e.currentTarget)}
          sx={{ borderRadius: 1.5, color: s.naTabela ? "#38BDF8" : "text.secondary", bgcolor: s.naTabela ? "rgba(56, 189, 248, 0.16)" : "transparent" }}
        >
          <TableChartOutlinedIcon fontSize="small" />
        </IconButton>
      </Tooltip>
      <Menu anchorEl={menuTabela} open={!!menuTabela} onClose={() => fecharTabela()} sx={{ zIndex: 1700 }}>
        <MenuItem onClick={() => fecharTabela(() => c().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run())}>Inserir tabela 3 × 3</MenuItem>
        <MenuItem disabled={!s.naTabela} onClick={() => fecharTabela(() => c().addRowAfter().run())}>Adicionar linha abaixo</MenuItem>
        <MenuItem disabled={!s.naTabela} onClick={() => fecharTabela(() => c().addColumnAfter().run())}>Adicionar coluna à direita</MenuItem>
        <MenuItem disabled={!s.naTabela} onClick={() => fecharTabela(() => c().deleteRow().run())}>Excluir linha</MenuItem>
        <MenuItem disabled={!s.naTabela} onClick={() => fecharTabela(() => c().deleteColumn().run())}>Excluir coluna</MenuItem>
        <MenuItem disabled={!s.naTabela} onClick={() => fecharTabela(() => c().deleteTable().run())} sx={{ color: "error.main" }}>Excluir tabela</MenuItem>
      </Menu>
      <Botao titulo="Limpar formatação" onClick={() => c().unsetAllMarks().clearNodes().run()}><FormatClearIcon fontSize="small" /></Botao>
    </Box>
  );
}
