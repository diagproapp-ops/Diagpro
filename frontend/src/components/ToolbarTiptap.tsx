import React, { useState } from "react";
import { Editor } from "@tiptap/react";
import { Button, ButtonGroup, Menu, MenuItem, Tooltip, Modal, Box, TextField, Drawer, Typography } from "@mui/material";
import FormatBoldIcon from "@mui/icons-material/FormatBold";
import FormatItalicIcon from "@mui/icons-material/FormatItalic";
import FormatUnderlinedIcon from "@mui/icons-material/FormatUnderlined";
import StrikethroughSIcon from "@mui/icons-material/StrikethroughS";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import FormatListNumberedIcon from "@mui/icons-material/FormatListNumbered";
import FormatQuoteIcon from "@mui/icons-material/FormatQuote";
import CodeIcon from "@mui/icons-material/Code";
import TableChartIcon from "@mui/icons-material/TableChart";
import FormatColorTextIcon from "@mui/icons-material/FormatColorText";
import FontDownloadIcon from "@mui/icons-material/FontDownload";
import FormatAlignLeftIcon from "@mui/icons-material/FormatAlignLeft";
import FormatAlignCenterIcon from "@mui/icons-material/FormatAlignCenter";
import FormatAlignRightIcon from "@mui/icons-material/FormatAlignRight";
import FormatAlignJustifyIcon from "@mui/icons-material/FormatAlignJustify";
import FormatIndentIncreaseIcon from "@mui/icons-material/FormatIndentIncrease";
import ImageIcon from "@mui/icons-material/Image";
import LinkIcon from "@mui/icons-material/Link";
import UndoIcon from "@mui/icons-material/Undo";
import RedoIcon from "@mui/icons-material/Redo";
import FormatSizeIcon from "@mui/icons-material/FormatSize";
import HighlightIcon from "@mui/icons-material/Highlight";
import YoutubeIcon from "@mui/icons-material/OndemandVideo";
import FunctionsIcon from "@mui/icons-material/Functions";
import SubscriptIcon from "@mui/icons-material/Subscript";
import SuperscriptIcon from "@mui/icons-material/Superscript";
import PlaylistAddCheckIcon from "@mui/icons-material/PlaylistAddCheck";
import RemoveIcon from "@mui/icons-material/Remove";
import InsertEmoticonIcon from "@mui/icons-material/InsertEmoticon";
import PersonAddIcon from "@mui/icons-material/PersonAdd";
import MarkdownIcon from "@mui/icons-material/Code";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import AddCommentIcon from '@mui/icons-material/AddComment';
import SearchIcon from '@mui/icons-material/Search';
import ListAltIcon from '@mui/icons-material/ListAlt';
import CodeIcon2 from '@mui/icons-material/Code';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import { EditorContent } from "@tiptap/react";
import './ToolbarTiptap.css';

import html2pdf from 'html2pdf.js';

const snippets = [
  { name: "Assinatura", html: "<p>Atenciosamente,<br>Seu Nome</p>" },
  { name: "Cabeçalho padrão", html: "<h1>Título</h1>" },
  { name: "Sumário", html: "<h2>Sumário</h2><ul><li>...</li></ul>" }
];

export default function SuperToolbarTiptap({ editor }: { editor: Editor | null }) {
  const [anchorElFont, setAnchorElFont] = useState<null | HTMLElement>(null);
  const [anchorElColor, setAnchorElColor] = useState<null | HTMLElement>(null);
  const [anchorElIndent, setAnchorElIndent] = useState<null | HTMLElement>(null);
  const [anchorElSnippet, setAnchorElSnippet] = useState<null | HTMLElement>(null);

  const [openMathModal, setOpenMathModal] = useState(false);
  const [latexInput, setLatexInput] = useState("");

  const [fullscreen, setFullscreen] = useState(false);
  const [showHtml, setShowHtml] = useState(false);
  const [searchModalOpen, setSearchModalOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [replace, setReplace] = useState("");
  const [tocOpen, setTocOpen] = useState(false);

  // Busca avançada
  const [foundIndices, setFoundIndices] = useState<number[]>([]);
  const [currentFound, setCurrentFound] = useState(0);
  const [originalHtml, setOriginalHtml] = useState("");

  if (!editor) return null;

  // --- Tabela de conteúdos
  const html = editor.getHTML();
  const tocMatches = Array.from(html.matchAll(/<h([1-6])[^>]*>(.*?)<\/h\1>/g));

  // --- Recuo
  const indentLevels = [
    { label: "Sem recuo", value: 0 },
    { label: "0.25 em", value: 1 },
    { label: "0.50 em", value: 2 },
    { label: "0.75 em", value: 3 },
    { label: "1.00 em", value: 4 },
    { label: "1.25 em", value: 5 },
    { label: "1.50 em", value: 6 },
    { label: "1.75 em", value: 7 },
    { label: "2.00 em", value: 8 },
    { label: "2.25 em", value: 9 },
    { label: "2.50 em", value: 10 },
  ];
  const getActiveIndent = () => {
    const attrs = editor.getAttributes('paragraph');
    if (attrs && attrs.class) {
      const match = attrs.class.match(/indent-(\d+)/);
      if (match) return Number(match[1]);
    }
    return 0;
  };
  const activeIndentValue = getActiveIndent();

  // --- Fonte e cor
  const fonts = ["Arial", "Georgia", "Courier New", "Times New Roman", "Verdana", "Roboto", "Montserrat"];
  const colors = ["#000000", "#e91e63", "#2196f3", "#4caf50", "#ffeb3b", "#ff9800", "#fff", "#f44336", "#8bc34a", "#3f51b5"];

  // --- Upload de imagem
  const handleImageUpload = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.onchange = async (e: any) => {
      const file = e.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = () => {
          editor.chain().focus().setImage({ src: reader.result as string }).run();
        };
        reader.readAsDataURL(file);
      }
    };
    input.click();
  };

  // --- Upload de arquivo genérico
  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    editor.chain().focus().insertContent(`<a href="${url}" target="_blank">${file.name}</a>`).run();
  };

  // --- Modal de matemática
  const handleInsertMath = () => setOpenMathModal(true);
  const handleMathOk = () => {
    if (latexInput) {
      editor.chain().focus().insertContent(`<span data-type="math" data-latex="${latexInput}"></span>`).run();
    }
    setOpenMathModal(false);
    setLatexInput("");
  };

  // --- Exportação PDF
  const handleExportPDF = () => {
    html2pdf().from(editor.getHTML()).save();
  };

  // Busca/Substituição visual
  function findAllOccurrences(text: string, term: string): number[] {
    const indices: number[] = [];
    if (!term) return indices;
    let idx = text.toLowerCase().indexOf(term.toLowerCase());
    while (idx !== -1) {
      indices.push(idx);
      idx = text.toLowerCase().indexOf(term.toLowerCase(), idx + term.length);
    }
    return indices;
  }

  // Atualiza índices ao digitar e remove destaque visual
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const term = e.target.value;
    setSearch(term);
    const plainText = editor.getText();
    const indices = findAllOccurrences(plainText, term);
    setFoundIndices(indices);
    setCurrentFound(0);

    // Remove destaque se mudar a busca
    if (originalHtml) {
      editor.commands.setContent(originalHtml);
      setOriginalHtml("");
    }
  };

  // Destaca e seleciona a ocorrência atual
  const highlightOccurrence = (index: number) => {
    if (!search || foundIndices.length === 0) return;
    const idx = foundIndices[index];

    // Guarda original para poder restaurar depois
    if (!originalHtml) setOriginalHtml(editor.getHTML());

    let html = originalHtml || editor.getHTML();

    // Destaca só a ocorrência atual com <mark>
    let count = 0;
    const regex = new RegExp(search, "gi");
    html = html.replace(regex, (match) => {
      if (count === index) {
        count++;
        return `<mark>${match}</mark>`;
      }
      count++;
      return match;
    });

    editor.commands.setContent(html);

    // Seleciona o trecho no editor
    editor.commands.setTextSelection({ from: idx + 1, to: idx + search.length + 1 });
    editor.chain().focus().run();
    setCurrentFound(index);
  };

  const handleFindNext = () => {
    if (!search || foundIndices.length === 0) return;
    const next = (currentFound + 1) % foundIndices.length;
    highlightOccurrence(next);
  };

  const handleFindPrevious = () => {
    if (!search || foundIndices.length === 0) return;
    const prev = (currentFound - 1 + foundIndices.length) % foundIndices.length;
    highlightOccurrence(prev);
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      if (foundIndices.length > 0) highlightOccurrence(0);
    }
  };

  // Substituir tudo
  const handleReplaceAll = () => {
    if (!search) return;
    let html = (originalHtml || editor.getHTML()).replaceAll(search, replace);
    editor.commands.setContent(html);
    setSearchModalOpen(false);
    setSearch("");
    setReplace("");
    setFoundIndices([]);
    setCurrentFound(0);
    setOriginalHtml("");
  };

  // Substituir ocorrência atual
  const handleReplaceCurrent = () => {
    if (!search || foundIndices.length === 0) return;
    let count = 0;
    const regex = new RegExp(search, "gi");
    let html = originalHtml || editor.getHTML();
    html = html.replace(regex, (match) => {
      if (count === currentFound) {
        count++;
        return replace;
      }
      count++;
      return match;
    });

    editor.commands.setContent(html);

    // Atualiza índices e seleção e restaura original
    const newPlainText = editor.getText();
    const newIndices = findAllOccurrences(newPlainText, search);
    setFoundIndices(newIndices);
    setOriginalHtml(""); // Remove destaque antigo

    if (newIndices.length > 0) {
      const next = currentFound % newIndices.length;
      highlightOccurrence(next);
    } else {
      setCurrentFound(0);
    }
  };

  // Ao fechar o modal, restaura o HTML original (remove destaque)
  const handleCloseSearchModal = () => {
    if (originalHtml) {
      editor.commands.setContent(originalHtml);
      setOriginalHtml("");
    }
    setSearchModalOpen(false);
  };

  return (
    <>
      <div className="tiptap-toolbar">
        {/* Texto */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Negrito"><Button onClick={() => editor.chain().focus().toggleBold().run()} color={editor.isActive("bold") ? "primary" : "inherit"}><FormatBoldIcon /></Button></Tooltip>
          <Tooltip title="Itálico"><Button onClick={() => editor.chain().focus().toggleItalic().run()} color={editor.isActive("italic") ? "primary" : "inherit"}><FormatItalicIcon /></Button></Tooltip>
          <Tooltip title="Sublinhado"><Button onClick={() => editor.chain().focus().toggleUnderline().run()} color={editor.isActive("underline") ? "primary" : "inherit"}><FormatUnderlinedIcon /></Button></Tooltip>
          <Tooltip title="Riscado"><Button onClick={() => editor.chain().focus().toggleStrike().run()} color={editor.isActive("strike") ? "primary" : "inherit"}><StrikethroughSIcon /></Button></Tooltip>
          <Tooltip title="Marca texto"><Button onClick={() => editor.chain().focus().toggleHighlight().run()} color={editor.isActive("highlight") ? "primary" : "inherit"}><HighlightIcon /></Button></Tooltip>
          <Tooltip title="Subscrito"><Button onClick={() => editor.chain().focus().toggleSubscript().run()} color={editor.isActive("subscript") ? "primary" : "inherit"}><SubscriptIcon /></Button></Tooltip>
          <Tooltip title="Sobrescrito"><Button onClick={() => editor.chain().focus().toggleSuperscript().run()} color={editor.isActive("superscript") ? "primary" : "inherit"}><SuperscriptIcon /></Button></Tooltip>
        </ButtonGroup>
        {/* Listas */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Lista com marcadores"><Button onClick={() => editor.chain().focus().toggleBulletList().run()} color={editor.isActive("bulletList") ? "primary" : "inherit"}><FormatListBulletedIcon /></Button></Tooltip>
          <Tooltip title="Lista numerada"><Button onClick={() => editor.chain().focus().toggleOrderedList().run()} color={editor.isActive("orderedList") ? "primary" : "inherit"}><FormatListNumberedIcon /></Button></Tooltip>
          <Tooltip title="Checklist"><Button onClick={() => editor.chain().focus().toggleTaskList().run()} color={editor.isActive("taskList") ? "primary" : "inherit"}><PlaylistAddCheckIcon /></Button></Tooltip>
        </ButtonGroup>
        {/* Blocos */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Citação"><Button onClick={() => editor.chain().focus().toggleBlockquote().run()} color={editor.isActive("blockquote") ? "primary" : "inherit"}><FormatQuoteIcon /></Button></Tooltip>
          <Tooltip title="Código"><Button onClick={() => editor.chain().focus().toggleCodeBlock().run()} color={editor.isActive("codeBlock") ? "primary" : "inherit"}><CodeIcon /></Button></Tooltip>
          <Tooltip title="Matemática"><Button onClick={handleInsertMath}><FunctionsIcon /></Button></Tooltip>
          <Tooltip title="Linha horizontal"><Button onClick={() => editor.chain().focus().setHorizontalRule().run()}><RemoveIcon /></Button></Tooltip>
          <Tooltip title="Markdown"><Button onClick={() => { const md = prompt("Cole aqui o texto em Markdown:"); if (md) editor.commands.insertContent(md); }}><MarkdownIcon /></Button></Tooltip>
        </ButtonGroup>
        {/* Tabelas compactas */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Inserir tabela"><Button onClick={() => editor.chain().focus().insertTable({ rows: 2, cols: 2, withHeaderRow: true }).run()} color={editor.isActive("table") ? "primary" : "inherit"}><TableChartIcon /></Button></Tooltip>
          <Tooltip title="Adicionar linha">
            <span>
              <Button onClick={() => editor.chain().focus().addRowAfter().run()} disabled={!editor.can().addRowAfter()}>+L</Button>
            </span>
          </Tooltip>
          <Tooltip title="Adicionar coluna">
            <span>
              <Button onClick={() => editor.chain().focus().addColumnAfter().run()} disabled={!editor.can().addColumnAfter()}>+C</Button>
            </span>
          </Tooltip>
          <Tooltip title="Excluir linha">
            <span>
              <Button onClick={() => editor.chain().focus().deleteRow().run()} disabled={!editor.can().deleteRow()}>-L</Button>
            </span>
          </Tooltip>
          <Tooltip title="Excluir coluna">
            <span>
              <Button onClick={() => editor.chain().focus().deleteColumn().run()} disabled={!editor.can().deleteColumn()}>-C</Button>
            </span>
          </Tooltip>
          <Tooltip title="Excluir tabela">
            <span>
              <Button onClick={() => editor.chain().focus().deleteTable().run()} disabled={!editor.can().deleteTable()}>T</Button>
            </span>
          </Tooltip>
        </ButtonGroup>
        {/* Cabeçalhos */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Cabeçalho 1"><Button onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} color={editor.isActive("heading", { level: 1 }) ? "primary" : "inherit"}><FormatSizeIcon />1</Button></Tooltip>
          <Tooltip title="Cabeçalho 2"><Button onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} color={editor.isActive("heading", { level: 2 }) ? "primary" : "inherit"}><FormatSizeIcon />2</Button></Tooltip>
          <Tooltip title="Cabeçalho 3"><Button onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} color={editor.isActive("heading", { level: 3 }) ? "primary" : "inherit"}><FormatSizeIcon />3</Button></Tooltip>
          <Tooltip title="Parágrafo"><Button onClick={() => editor.chain().focus().setParagraph().run()} color={editor.isActive("paragraph") ? "primary" : "inherit"}>P</Button></Tooltip>
        </ButtonGroup>
        {/* Alinhamento */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Alinhar à esquerda"><Button onClick={() => editor.chain().focus().setTextAlign("left").run()} color={editor.isActive({ textAlign: "left" }) ? "primary" : "inherit"}><FormatAlignLeftIcon /></Button></Tooltip>
          <Tooltip title="Centralizar"><Button onClick={() => editor.chain().focus().setTextAlign("center").run()} color={editor.isActive({ textAlign: "center" }) ? "primary" : "inherit"}><FormatAlignCenterIcon /></Button></Tooltip>
          <Tooltip title="Alinhar à direita"><Button onClick={() => editor.chain().focus().setTextAlign("right").run()} color={editor.isActive({ textAlign: "right" }) ? "primary" : "inherit"}><FormatAlignRightIcon /></Button></Tooltip>
          <Tooltip title="Justificar"><Button onClick={() => editor.chain().focus().setTextAlign("justify").run()} color={editor.isActive({ textAlign: "justify" }) ? "primary" : "inherit"}><FormatAlignJustifyIcon /></Button></Tooltip>
        </ButtonGroup>
        {/* Recuo de parágrafo (padding left/right) */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Recuo à esquerda"><Button onClick={() => editor.chain().focus().setPaddingLeft(32).run()}><ArrowBackIcon /></Button></Tooltip>
          <Tooltip title="Recuo à direita"><Button onClick={() => editor.chain().focus().setPaddingRight(32).run()}><ArrowForwardIcon /></Button></Tooltip>
          <Tooltip title="Remover recuo"><Button onClick={() => editor.chain().focus().clearPadding().run()}><RemoveIcon /></Button></Tooltip>
        </ButtonGroup>
        {/* Recuo de parágrafo (classe indent) */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Recuo de parágrafo">
            <Button onClick={e => setAnchorElIndent(e.currentTarget)} color={activeIndentValue > 0 ? "primary" : "inherit"}><FormatIndentIncreaseIcon /></Button>
          </Tooltip>
          <Menu anchorEl={anchorElIndent} open={!!anchorElIndent} onClose={() => setAnchorElIndent(null)}>
            {indentLevels.map(item => (
              <MenuItem key={item.value} selected={activeIndentValue === item.value} onClick={() => {editor.chain().focus().setIndent(item.value).run(); setAnchorElIndent(null);}}>
                {item.label}
              </MenuItem>
            ))}
          </Menu>
        </ButtonGroup>
        {/* Fonte e cor */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Fonte"><Button onClick={e => setAnchorElFont(e.currentTarget)}><FontDownloadIcon /></Button></Tooltip>
          <Menu anchorEl={anchorElFont} open={!!anchorElFont} onClose={() => setAnchorElFont(null)}>
            {fonts.map((font) => (
              <MenuItem key={font} style={{ fontFamily: font }} selected={editor.isActive("fontFamily", { fontFamily: font })} onClick={() => { editor.chain().focus().setFontFamily(font).run(); setAnchorElFont(null); }}>
                {font}
              </MenuItem>
            ))}
          </Menu>
          <Tooltip title="Cor do texto"><Button onClick={e => setAnchorElColor(e.currentTarget)}><FormatColorTextIcon style={{ color: editor.getAttributes("textStyle").color || undefined }} /></Button></Tooltip>
          <Menu anchorEl={anchorElColor} open={!!anchorElColor} onClose={() => setAnchorElColor(null)}>
            {colors.map(color => (
              <MenuItem key={color} onClick={() => { editor.chain().focus().setColor(color).run(); setAnchorElColor(null); }} style={{ color, background: color === "#fff" ? "#eee" : undefined }}>
                {color}
              </MenuItem>
            ))}
          </Menu>
        </ButtonGroup>
        {/* Inserção */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Imagem"><Button onClick={handleImageUpload}><ImageIcon /></Button></Tooltip>
          <Tooltip title="Anexar arquivo">
            <span>
              <Button component="label"><AttachFileIcon /><input type="file" hidden onChange={handleFileUpload}/></Button>
            </span>
          </Tooltip>
          <Tooltip title="Link"><Button onClick={() => { const url = prompt("URL do link?"); if (url) editor.chain().focus().setLink({ href: url }).run(); }}><LinkIcon /></Button></Tooltip>
          <Tooltip title="YouTube"><Button onClick={() => { const url = prompt("URL do vídeo YouTube?"); if (url) editor.chain().focus().setYoutubeVideo({ src: url }).run(); }}><YoutubeIcon /></Button></Tooltip>
          <Tooltip title="Emoji"><Button onClick={() => { const emoji = prompt("Copie e cole o emoji ou palavra:"); if (emoji) editor.chain().focus().insertContent(emoji).run(); }}><InsertEmoticonIcon /></Button></Tooltip>
          <Tooltip title="Menção"><Button onClick={() => { const mention = prompt("Digite o nome para mencionar:"); if (mention) editor.chain().focus().insertContent(`@${mention}`).run(); }}><PersonAddIcon /></Button></Tooltip>
        </ButtonGroup>
        {/* Modelos/snippets */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Modelos"><Button onClick={e => setAnchorElSnippet(e.currentTarget)}><AddCommentIcon /></Button></Tooltip>
          <Menu anchorEl={anchorElSnippet} open={!!anchorElSnippet} onClose={() => setAnchorElSnippet(null)}>
            {snippets.map((s, i) => (
              <MenuItem key={i} onClick={() => {editor.chain().focus().insertContent(s.html).run(); setAnchorElSnippet(null);}}>{s.name}</MenuItem>
            ))}
          </Menu>
        </ButtonGroup>
        {/* Desfazer/Refazer */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Desfazer"><span>
            <Button onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()}><UndoIcon /></Button>
          </span></Tooltip>
          <Tooltip title="Refazer"><span>
            <Button onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()}><RedoIcon /></Button>
          </span></Tooltip>
        </ButtonGroup>
        {/* Exportar PDF */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Exportar PDF">
            <Button onClick={handleExportPDF}><PictureAsPdfIcon /></Button>
          </Tooltip>
        </ButtonGroup>
        {/* Contador de palavras/caracteres */}
        <ButtonGroup size="small" variant="outlined">
          <div style={{ padding: "0 8px", fontSize: 13, color: "#444", display: "flex", alignItems: "center" }}>
            <span>Palavras: {editor.storage.characterCount?.words?.()}</span>
            <span style={{ marginLeft: 8 }}>Caracteres: {editor.storage.characterCount?.characters?.()}</span>
          </div>
        </ButtonGroup>
        {/* Busca/Substituição */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Buscar/Substituir"><Button onClick={() => {
            setOriginalHtml(editor.getHTML());
            setSearchModalOpen(true);
          }}><SearchIcon /></Button></Tooltip>
        </ButtonGroup>
        {/* Sumário/Tabela de conteúdos */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Sumário"><Button onClick={() => setTocOpen(true)}><ListAltIcon /></Button></Tooltip>
        </ButtonGroup>
        {/* Visualizar HTML */}
        <ButtonGroup size="small" variant="outlined">
          <Tooltip title="Ver HTML"><Button onClick={() => setShowHtml(true)}><CodeIcon2 /></Button></Tooltip>
        </ButtonGroup>
      </div>
      {/* Modal matemática */}
      <Modal open={openMathModal} onClose={() => setOpenMathModal(false)}>
        <Box sx={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", bgcolor: "background.paper", p: 3, borderRadius: 2, minWidth: 300 }}>
          <Typography variant="subtitle1" fontWeight="bold" sx={{ mb: 2 }}>Inserir fórmula matemática</Typography>
          <TextField label="Digite a fórmula LaTeX" value={latexInput} onChange={e => setLatexInput(e.target.value)} fullWidth sx={{ mb: 2 }} />
          <Button variant="contained" color="primary" onClick={handleMathOk}>Inserir</Button>
          <Button variant="outlined" color="secondary" onClick={() => setOpenMathModal(false)} sx={{ ml: 2 }}>Cancelar</Button>
        </Box>
      </Modal>
      {/* Fullscreen */}
      <Modal open={fullscreen} onClose={() => setFullscreen(false)}>
        <Box
          sx={{
            position: "fixed",
            top: 0,
            left: 0,
            width: "100vw",
            height: "100vh",
            bgcolor: "background.paper",
            zIndex: 1300,
            p: 2,
            overflow: "auto",
            display: "flex",
            flexDirection: "column"
          }}
        >
          <Typography variant="h6" sx={{ mb: 2 }}>Modo tela cheia</Typography>
          <SuperToolbarTiptap editor={editor} />
          <div
            style={{
              flexGrow: 1,
              minHeight: "60vh",
              maxHeight: "80vh",
              border: "1px solid #ccc",
              borderRadius: 8,
              background: "#fafafa",
              padding: 12,
              overflowY: "auto",
              marginBottom: 16,
            }}
          >
            <EditorContent editor={editor} />
          </div>
          <Button
            variant="contained"
            color="primary"
            onClick={() => setFullscreen(false)}
            sx={{ mt: 2, alignSelf: "flex-end" }}
          >
            Fechar
          </Button>
        </Box>
      </Modal>
      {/* Modal busca/substituição */}
      <Modal open={searchModalOpen} onClose={handleCloseSearchModal}>
        <Box sx={{
          position: "absolute",
          top: "50%", left: "50%",
          transform: "translate(-50%, -50%)",
          bgcolor: "background.paper", p: 3,
          borderRadius: 2, minWidth: 380
        }}>
          <Typography variant="subtitle1" fontWeight="bold" sx={{ mb: 2 }}>Buscar e substituir</Typography>
          <TextField
            label="Buscar"
            value={search}
            onChange={handleSearchChange}
            onKeyDown={handleSearchKeyDown}
            fullWidth sx={{ mb: 2 }}
            autoFocus
          />
          <TextField
            label="Substituir por"
            value={replace}
            onChange={e => setReplace(e.target.value)}
            fullWidth sx={{ mb: 2 }}
          />
          <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
            <Button
              variant="outlined"
              color="primary"
              onClick={handleFindPrevious}
              disabled={!search || foundIndices.length === 0}
            >
              Anterior
            </Button>
            <Button
              variant="outlined"
              color="primary"
              onClick={handleFindNext}
              disabled={!search || foundIndices.length === 0}
            >
              Próxima
            </Button>
            <Button
              variant="contained"
              color="primary"
              onClick={handleReplaceCurrent}
              disabled={!search || foundIndices.length === 0}
            >
              Substituir atual
            </Button>
            <Button
              variant="contained"
              color="primary"
              onClick={handleReplaceAll}
              disabled={!search || foundIndices.length === 0}
            >
              Substituir tudo
            </Button>
            <Button
              variant="outlined"
              color="secondary"
              onClick={handleCloseSearchModal}
            >
              Cancelar
            </Button>
          </Box>
          <Typography variant="caption">
            {search
              ? foundIndices.length === 0
                ? `Nenhuma ocorrência de "${search}" encontrada.`
                : `Ocorrência ${foundIndices.length > 0 ? currentFound + 1 : 0} de ${foundIndices.length} para "${search}"`
              : "Digite para buscar."}
          </Typography>
        </Box>
      </Modal>
      {/* Drawer sumário/tabela de conteúdos */}
      <Drawer anchor="right" open={tocOpen} onClose={() => setTocOpen(false)}>
        <Box sx={{ width: 320, p: 2 }}>
          <Typography variant="h6" fontWeight="bold">Sumário</Typography>
          <ul>
            {tocMatches.map((m, i) => (
              <li key={i} style={{ marginLeft: (parseInt(m[1]) - 1) * 20 }}>
                {m[2]}
              </li>
            ))}
          </ul>
          <Button variant="outlined" color="secondary" onClick={() => setTocOpen(false)} sx={{ mt: 2 }}>Fechar</Button>
        </Box>
      </Drawer>
      {/* Modal HTML */}
      <Modal open={showHtml} onClose={() => setShowHtml(false)}>
        <Box sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          bgcolor: "background.paper",
          p: 3,
          borderRadius: 2,
          minWidth: 400,
          maxHeight: "80vh",
          overflowY: "auto"
        }}>
          <Typography variant="subtitle1" fontWeight="bold">HTML do editor</Typography>
          <textarea
            value={editor.getHTML()}
            readOnly
            rows={16}
            style={{
              width: "100%",
              fontFamily: "monospace",
              fontSize: 13,
              resize: "vertical",
              marginTop: 8,
              marginBottom: 8,
              background: "#f4f4f4",
              borderRadius: 4,
              border: "1px solid #ccc"
            }}
          />
          <Button variant="outlined" color="secondary" onClick={() => setShowHtml(false)} sx={{ mt: 2 }}>
            Fechar
          </Button>
        </Box>
      </Modal>
    </>
  );
}