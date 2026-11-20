import React, { useRef, useState } from "react";
import { Editor, useEditorState } from "@tiptap/react";
import { Box, Divider, IconButton, ListSubheader, Menu, MenuItem, Select, Tooltip, Typography } from "@mui/material";
import UndoIcon from "@mui/icons-material/Undo";
import RedoIcon from "@mui/icons-material/Redo";
import FormatBoldIcon from "@mui/icons-material/FormatBold";
import FormatItalicIcon from "@mui/icons-material/FormatItalic";
import FormatUnderlinedIcon from "@mui/icons-material/FormatUnderlined";
import StrikethroughSIcon from "@mui/icons-material/StrikethroughS";
import BorderColorIcon from "@mui/icons-material/BorderColor";
import FormatColorTextIcon from "@mui/icons-material/FormatColorText";
import SuperscriptIcon from "@mui/icons-material/Superscript";
import SubscriptIcon from "@mui/icons-material/Subscript";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import FormatListNumberedIcon from "@mui/icons-material/FormatListNumbered";
import FormatIndentIncreaseIcon from "@mui/icons-material/FormatIndentIncrease";
import FormatIndentDecreaseIcon from "@mui/icons-material/FormatIndentDecrease";
import KeyboardTabIcon from "@mui/icons-material/KeyboardTab";
import FormatAlignLeftIcon from "@mui/icons-material/FormatAlignLeft";
import FormatAlignCenterIcon from "@mui/icons-material/FormatAlignCenter";
import FormatAlignRightIcon from "@mui/icons-material/FormatAlignRight";
import FormatAlignJustifyIcon from "@mui/icons-material/FormatAlignJustify";
import FormatLineSpacingIcon from "@mui/icons-material/FormatLineSpacing";
import FormatQuoteIcon from "@mui/icons-material/FormatQuote";
import HorizontalRuleIcon from "@mui/icons-material/HorizontalRule";
import TableChartOutlinedIcon from "@mui/icons-material/TableChartOutlined";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import FunctionsIcon from "@mui/icons-material/Functions";
import CalculateOutlinedIcon from "@mui/icons-material/CalculateOutlined";
import EmojiSymbolsIcon from "@mui/icons-material/EmojiSymbols";
import FindReplaceIcon from "@mui/icons-material/FindReplace";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import FullscreenExitIcon from "@mui/icons-material/FullscreenExit";
import FormatClearIcon from "@mui/icons-material/FormatClear";

/**
 * Barra de formatação do editor de questões. Só oferece o que a prova diagramada (DOCX/PDF) reproduz —
 * tudo aqui é convertido por backend/app/html_to_docx.py.
 */

// Estilos do conteúdo do editor e da pré-visualização (listas, citação, tabela, marca-texto e equações no tema escuro).
export const estiloConteudoEditor = {
  "& .ProseMirror": { outline: "none", minHeight: 120 },
  "& ul, & ol": { pl: 3.5, my: 1 },
  "& ul": { listStyleType: "disc" },
  "& ol": { listStyleType: "decimal" },
  "& li > p": { my: 0.25 },
  "& h1": { fontSize: "1.6em", my: 1 }, "& h2": { fontSize: "1.35em", my: 1 }, "& h3": { fontSize: "1.15em", my: 1 },
  "& blockquote": { borderLeft: "3px solid rgba(56, 189, 248, 0.6)", pl: 2, ml: 0, my: 1, color: "inherit", opacity: 0.9 },
  "& mark": { backgroundColor: "#FDE047", color: "#111827", borderRadius: "2px", px: "1px" },
  "& hr": { border: 0, borderTop: "2px solid rgba(148, 163, 184, 0.6)", my: 2 },
  "& table": { borderCollapse: "collapse", my: 1, width: "100%", tableLayout: "fixed" },
  "& td, & th": { border: "1px solid rgba(148, 163, 184, 0.55)", p: "4px 8px", verticalAlign: "top", position: "relative" },
  "& th": { fontWeight: 700, bgcolor: "rgba(148, 163, 184, 0.12)" },
  "& .selectedCell": { bgcolor: "rgba(56, 189, 248, 0.18)" },
  "& .column-resize-handle": { position: "absolute", right: -2, top: 0, bottom: 0, width: 4, bgcolor: "#38BDF8", pointerEvents: "none" },
  "& img": { maxWidth: "100%", height: "auto" },
  "& img.ProseMirror-selectednode": { outline: "3px solid #38BDF8" },
  "& [data-type='inline-math'], & [data-type='math']": {
    cursor: "pointer", px: "2px", borderRadius: "4px", "&:hover": { bgcolor: "rgba(56, 189, 248, 0.15)" },
  },
  "& [data-type='block-math']": {
    cursor: "pointer", textAlign: "center", my: 1.5, py: 1, borderRadius: "6px", "&:hover": { bgcolor: "rgba(56, 189, 248, 0.1)" },
  },
  "& p.is-editor-empty:first-of-type::before": {
    content: "attr(data-placeholder)", color: "rgba(148, 163, 184, 0.7)", float: "left", height: 0, pointerEvents: "none",
  },
};

const FONTES = ["Arial", "Calibri", "Cambria", "Georgia", "Times New Roman", "Verdana", "Tahoma", "Courier New"];
const TAMANHOS = ["8", "9", "10", "11", "12", "14", "16", "18", "20", "24", "28", "32"];
const ALTURAS = [["1", "Simples"], ["1.15", "1,15"], ["1.5", "1,5"], ["2", "Duplo"], ["2.5", "2,5"], ["3", "Triplo"]];
const CORES_TEXTO = ["#000000", "#374151", "#B91C1C", "#C2410C", "#A16207", "#15803D", "#0E7490", "#1D4ED8", "#6D28D9", "#BE185D"];
// marca-texto: só as cores que o Word imprime como marca-texto (a prova usa a mais próxima)
const CORES_MARCA = [["#FFFF00", "Amarelo"], ["#00FF00", "Verde"], ["#00FFFF", "Azul-claro"], ["#FF00FF", "Rosa"], ["#C0C0C0", "Cinza"]];
const CARACTERES: [string, string[]][] = [
  ["Pontuação", ["“", "”", "‘", "’", "«", "»", "—", "–", "…", "•", "§", "¶", "†"]],
  ["Ordinais e medidas", ["º", "ª", "°", "′", "″", "µ", "‰", "½", "¼", "¾", "⅓", "⅔"]],
  ["Moedas e marcas", ["R$", "€", "£", "¥", "¢", "©", "®", "™"]],
  ["Matemática rápida", ["×", "÷", "±", "≠", "≈", "≤", "≥", "√", "∞", "π", "Σ", "Δ", "Ω", "α", "β", "θ", "λ"]],
  ["Setas e marcas", ["→", "←", "↑", "↓", "↔", "⇒", "⇔", "✓", "✗", "☐", "☑", "★", "♂", "♀"]],
];

type BotaoProps = { titulo: string; ativo?: boolean; desativado?: boolean; onClick: (e: React.MouseEvent<HTMLElement>) => void; children: React.ReactNode };

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

const selectSx = {
  height: 30, fontSize: 13, color: "text.primary",
  ".MuiOutlinedInput-notchedOutline": { borderColor: "rgba(148, 163, 184, 0.3)" },
  ".MuiSelect-select": { py: 0.25, pl: 1 },
};

type Props = {
  editor: Editor | null;
  onEquacao?: (bloco: boolean) => void;
  onLocalizar?: () => void;
  telaCheia?: boolean;
  onTelaCheia?: () => void;
  onErro?: (mensagem: string) => void;
};

const LIMITE_IMAGEM_MB = 3;

export default function BarraFormatacao({ editor, onEquacao, onLocalizar, telaCheia, onTelaCheia, onErro }: Props) {
  const [menu, setMenu] = useState<{ tipo: string; el: HTMLElement } | null>(null);
  const arquivoRef = useRef<HTMLInputElement>(null);

  const s = useEditorState({
    editor,
    selector: ({ editor: e }) => {
      if (!e) return null;
      const estilo = e.getAttributes("textStyle");
      const nivel = [1, 2, 3].find((n) => e.isActive("heading", { level: n }));
      return {
        negrito: e.isActive("bold"), italico: e.isActive("italic"), sublinhado: e.isActive("underline"),
        tachado: e.isActive("strike"), marca: e.isActive("highlight"), sobrescrito: e.isActive("superscript"),
        subscrito: e.isActive("subscript"), marcadores: e.isActive("bulletList"), numerada: e.isActive("orderedList"),
        citacao: e.isActive("blockquote"),
        esquerda: e.isActive({ textAlign: "left" }), centro: e.isActive({ textAlign: "center" }),
        direita: e.isActive({ textAlign: "right" }), justificado: e.isActive({ textAlign: "justify" }),
        naTabela: e.isActive("table"), imagem: e.isActive("image"),
        primeiraLinha: !!(e.getAttributes("paragraph").recuoPrimeiraLinha || e.getAttributes("heading").recuoPrimeiraLinha),
        alturaLinha: (e.getAttributes("paragraph").alturaLinha || "") as string,
        fonte: (estilo.fontFamily || "") as string,
        tamanho: ((estilo.fontSize || "") as string).replace("pt", ""),
        cor: (estilo.color || "") as string,
        paragrafo: nivel ? `h${nivel}` : "p",
        podeDesfazer: e.can().undo(), podeRefazer: e.can().redo(),
        podeMesclar: e.can().mergeCells(), podeDividir: e.can().splitCell(),
      };
    },
  });

  if (!editor || !s) return null;
  const c = () => editor.chain().focus();
  const abrir = (tipo: string) => (e: React.MouseEvent<HTMLElement>) => setMenu({ tipo, el: e.currentTarget });
  const fechar = (acao?: () => void) => { setMenu(null); acao && acao(); };
  const menuAberto = (tipo: string) => menu?.tipo === tipo;

  const escolherImagem = (ev: React.ChangeEvent<HTMLInputElement>) => {
    const arquivo = ev.target.files?.[0];
    ev.target.value = "";
    if (!arquivo) return;
    if (!/^image\/(png|jpeg|gif)$/.test(arquivo.type)) {
      onErro?.("Use imagem PNG, JPG ou GIF.");
      return;
    }
    if (arquivo.size > LIMITE_IMAGEM_MB * 1024 * 1024) {
      onErro?.(`Imagem grande demais (máximo ${LIMITE_IMAGEM_MB} MB).`);
      return;
    }
    // a imagem fica embutida no texto da questão (que é gravado criptografado); nada vai para outro servidor
    const leitor = new FileReader();
    leitor.onload = () => c().setImage({ src: String(leitor.result) }).run();
    leitor.readAsDataURL(arquivo);
  };

  return (
    <Box
      role="toolbar"
      aria-label="Formatação do texto"
      sx={{
        display: "flex", flexDirection: "column", gap: 0.25, p: 0.5, mb: 1, borderRadius: 2,
        bgcolor: "rgba(15, 23, 42, 0.92)", border: "1px solid rgba(148, 163, 184, 0.18)",
        position: "sticky", top: 0, zIndex: 2,
      }}
    >
      {/* Linha 1: texto */}
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 0.25 }}>
        <Botao titulo="Desfazer (Ctrl+Z)" desativado={!s.podeDesfazer} onClick={() => c().undo().run()}><UndoIcon fontSize="small" /></Botao>
        <Botao titulo="Refazer (Ctrl+Y)" desativado={!s.podeRefazer} onClick={() => c().redo().run()}><RedoIcon fontSize="small" /></Botao>
        <Separador />
        <Tooltip title="Estilo do parágrafo" arrow placement="top">
          <Select
            size="small" value={s.paragrafo} sx={{ ...selectSx, width: 112 }}
            inputProps={{ "aria-label": "Estilo do parágrafo" }}
            MenuProps={{ sx: { zIndex: 1800 } }}
            onChange={(e) => {
              const v = e.target.value;
              if (v === "p") c().setParagraph().run();
              else c().setHeading({ level: Number(v.slice(1)) as 1 | 2 | 3 }).run();
            }}
          >
            <MenuItem value="p">Parágrafo</MenuItem>
            <MenuItem value="h1">Título 1</MenuItem>
            <MenuItem value="h2">Título 2</MenuItem>
            <MenuItem value="h3">Título 3</MenuItem>
          </Select>
        </Tooltip>
        <Tooltip title="Fonte só deste trecho (normalmente a prova usa a fonte escolhida na exportação)" arrow placement="top">
          <Select
            size="small" displayEmpty value={FONTES.includes(s.fonte) ? s.fonte : ""} sx={{ ...selectSx, width: 132 }}
            inputProps={{ "aria-label": "Fonte" }}
            MenuProps={{ sx: { zIndex: 1800 } }}
            onChange={(e) => (e.target.value ? c().setFontFamily(e.target.value).run() : c().unsetFontFamily().run())}
          >
            <MenuItem value=""><em>Fonte da prova</em></MenuItem>
            {FONTES.map((f) => <MenuItem key={f} value={f} sx={{ fontFamily: f }}>{f}</MenuItem>)}
          </Select>
        </Tooltip>
        <Tooltip title="Tamanho só deste trecho (normalmente a prova usa o tamanho escolhido na exportação)" arrow placement="top">
          <Select
            size="small" displayEmpty value={TAMANHOS.includes(s.tamanho) ? s.tamanho : ""} sx={{ ...selectSx, width: 74 }}
            inputProps={{ "aria-label": "Tamanho da fonte" }}
            MenuProps={{ sx: { zIndex: 1800 } }}
            onChange={(e) => (e.target.value ? c().setFontSize(`${e.target.value}pt`).run() : c().unsetFontSize().run())}
          >
            <MenuItem value=""><em>Prova</em></MenuItem>
            {TAMANHOS.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
          </Select>
        </Tooltip>
        <Separador />
        <Botao titulo="Negrito (Ctrl+B)" ativo={s.negrito} onClick={() => c().toggleBold().run()}><FormatBoldIcon fontSize="small" /></Botao>
        <Botao titulo="Itálico (Ctrl+I)" ativo={s.italico} onClick={() => c().toggleItalic().run()}><FormatItalicIcon fontSize="small" /></Botao>
        <Botao titulo="Sublinhado (Ctrl+U)" ativo={s.sublinhado} onClick={() => c().toggleUnderline().run()}><FormatUnderlinedIcon fontSize="small" /></Botao>
        <Botao titulo="Tachado" ativo={s.tachado} onClick={() => c().toggleStrike().run()}><StrikethroughSIcon fontSize="small" /></Botao>
        <Botao titulo="Cor do texto" ativo={!!s.cor} onClick={abrir("cor")}>
          <FormatColorTextIcon fontSize="small" sx={{ color: s.cor || undefined }} />
        </Botao>
        <Botao titulo="Marca-texto (Ctrl+Shift+H)" ativo={s.marca} onClick={abrir("marca")}><BorderColorIcon fontSize="small" /></Botao>
        <Botao titulo="Sobrescrito (ex.: x²)" ativo={s.sobrescrito} onClick={() => c().toggleSuperscript().run()}><SuperscriptIcon fontSize="small" /></Botao>
        <Botao titulo="Subscrito (ex.: H₂O)" ativo={s.subscrito} onClick={() => c().toggleSubscript().run()}><SubscriptIcon fontSize="small" /></Botao>
        <Botao titulo="Limpar formatação" onClick={() => c().unsetAllMarks().clearNodes().run()}><FormatClearIcon fontSize="small" /></Botao>
      </Box>

      {/* Linha 2: parágrafo e inserir */}
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 0.25 }}>
        <Botao titulo="Lista com marcadores" ativo={s.marcadores} onClick={() => c().toggleBulletList().run()}><FormatListBulletedIcon fontSize="small" /></Botao>
        <Botao titulo="Lista numerada" ativo={s.numerada} onClick={() => c().toggleOrderedList().run()}><FormatListNumberedIcon fontSize="small" /></Botao>
        <Botao titulo="Diminuir recuo (Shift+Tab)" onClick={() => (s.marcadores || s.numerada ? c().liftListItem("listItem").run() : c().diminuirRecuo().run())}>
          <FormatIndentDecreaseIcon fontSize="small" />
        </Botao>
        <Botao titulo="Aumentar recuo (Tab)" onClick={() => (s.marcadores || s.numerada ? c().sinkListItem("listItem").run() : c().aumentarRecuo().run())}>
          <FormatIndentIncreaseIcon fontSize="small" />
        </Botao>
        <Botao titulo="Recuo da primeira linha" ativo={s.primeiraLinha} onClick={() => c().alternarRecuoPrimeiraLinha().run()}><KeyboardTabIcon fontSize="small" /></Botao>
        <Separador />
        <Botao titulo="Alinhar à esquerda" ativo={s.esquerda} onClick={() => c().setTextAlign("left").run()}><FormatAlignLeftIcon fontSize="small" /></Botao>
        <Botao titulo="Centralizar" ativo={s.centro} onClick={() => c().setTextAlign("center").run()}><FormatAlignCenterIcon fontSize="small" /></Botao>
        <Botao titulo="Alinhar à direita" ativo={s.direita} onClick={() => c().setTextAlign("right").run()}><FormatAlignRightIcon fontSize="small" /></Botao>
        <Botao titulo="Justificar" ativo={s.justificado} onClick={() => c().setTextAlign("justify").run()}><FormatAlignJustifyIcon fontSize="small" /></Botao>
        <Botao titulo="Espaçamento entre linhas" ativo={!!s.alturaLinha} onClick={abrir("altura")}><FormatLineSpacingIcon fontSize="small" /></Botao>
        <Separador />
        <Botao titulo="Citação / texto de apoio recuado" ativo={s.citacao} onClick={() => c().toggleBlockquote().run()}><FormatQuoteIcon fontSize="small" /></Botao>
        <Botao titulo="Linha horizontal" onClick={() => c().setHorizontalRule().run()}><HorizontalRuleIcon fontSize="small" /></Botao>
        <Botao titulo="Tabela" ativo={s.naTabela} onClick={abrir("tabela")}><TableChartOutlinedIcon fontSize="small" /></Botao>
        <Botao titulo={s.imagem ? "Tamanho da imagem" : "Inserir imagem"} ativo={s.imagem} onClick={s.imagem ? abrir("imagem") : () => arquivoRef.current?.click()}>
          <ImageOutlinedIcon fontSize="small" />
        </Botao>
        <input ref={arquivoRef} type="file" accept="image/png,image/jpeg,image/gif" hidden onChange={escolherImagem} />
        {onEquacao && (
          <>
            <Separador />
            <Botao titulo="Equação na linha do texto" onClick={() => onEquacao(false)}><FunctionsIcon fontSize="small" /></Botao>
            <Botao titulo="Equação em destaque (centralizada)" onClick={() => onEquacao(true)}><CalculateOutlinedIcon fontSize="small" /></Botao>
          </>
        )}
        <Botao titulo="Caracteres especiais" onClick={abrir("caracteres")}><EmojiSymbolsIcon fontSize="small" /></Botao>
        <Separador />
        {onLocalizar && <Botao titulo="Localizar e substituir (Ctrl+F)" onClick={onLocalizar}><FindReplaceIcon fontSize="small" /></Botao>}
        {onTelaCheia && (
          <Botao titulo={telaCheia ? "Sair da tela cheia (Esc)" : "Tela cheia"} ativo={telaCheia} onClick={onTelaCheia}>
            {telaCheia ? <FullscreenExitIcon fontSize="small" /> : <FullscreenIcon fontSize="small" />}
          </Botao>
        )}
      </Box>

      {/* Menus */}
      <Menu anchorEl={menu?.el} open={menuAberto("cor")} onClose={() => fechar()} sx={{ zIndex: 1800 }}>
        <Box sx={{ display: "grid", gridTemplateColumns: "repeat(5, 28px)", gap: 0.75, p: 1 }}>
          {CORES_TEXTO.map((cor) => (
            <Box key={cor} role="button" aria-label={`Cor ${cor}`} onClick={() => fechar(() => c().setColor(cor).run())}
              sx={{ width: 28, height: 28, borderRadius: 1, bgcolor: cor, cursor: "pointer", border: "1px solid rgba(148,163,184,.5)" }} />
          ))}
        </Box>
        <MenuItem onClick={() => fechar(() => c().unsetColor().run())}>Cor automática (preto na prova)</MenuItem>
      </Menu>
      <Menu anchorEl={menu?.el} open={menuAberto("marca")} onClose={() => fechar()} sx={{ zIndex: 1800 }}>
        {CORES_MARCA.map(([cor, nome]) => (
          <MenuItem key={cor} onClick={() => fechar(() => c().setHighlight({ color: cor }).run())}>
            <Box sx={{ width: 18, height: 18, borderRadius: 0.5, bgcolor: cor, mr: 1.5, border: "1px solid rgba(0,0,0,.2)" }} />{nome}
          </MenuItem>
        ))}
        <MenuItem onClick={() => fechar(() => c().unsetHighlight().run())}>Sem marca-texto</MenuItem>
      </Menu>
      <Menu anchorEl={menu?.el} open={menuAberto("altura")} onClose={() => fechar()} sx={{ zIndex: 1800 }}>
        {ALTURAS.map(([v, nome]) => (
          <MenuItem key={v} selected={s.alturaLinha === v} onClick={() => fechar(() => c().definirAlturaLinha(v === "1" ? null : v).run())}>{nome}</MenuItem>
        ))}
      </Menu>
      <Menu anchorEl={menu?.el} open={menuAberto("tabela")} onClose={() => fechar()} sx={{ zIndex: 1800 }}>
        <MenuItem onClick={() => fechar(() => c().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run())}>Inserir tabela 3 × 3</MenuItem>
        <MenuItem onClick={() => fechar(() => c().insertTable({ rows: 2, cols: 2, withHeaderRow: false }).run())}>Inserir tabela 2 × 2 sem cabeçalho</MenuItem>
        <Divider />
        <MenuItem disabled={!s.naTabela} onClick={() => fechar(() => c().addRowBefore().run())}>Adicionar linha acima</MenuItem>
        <MenuItem disabled={!s.naTabela} onClick={() => fechar(() => c().addRowAfter().run())}>Adicionar linha abaixo</MenuItem>
        <MenuItem disabled={!s.naTabela} onClick={() => fechar(() => c().addColumnBefore().run())}>Adicionar coluna à esquerda</MenuItem>
        <MenuItem disabled={!s.naTabela} onClick={() => fechar(() => c().addColumnAfter().run())}>Adicionar coluna à direita</MenuItem>
        <Divider />
        <MenuItem disabled={!s.podeMesclar} onClick={() => fechar(() => c().mergeCells().run())}>Mesclar células selecionadas</MenuItem>
        <MenuItem disabled={!s.podeDividir} onClick={() => fechar(() => c().splitCell().run())}>Dividir célula</MenuItem>
        <MenuItem disabled={!s.naTabela} onClick={() => fechar(() => c().toggleHeaderRow().run())}>Linha de cabeçalho (liga/desliga)</MenuItem>
        <Divider />
        <MenuItem disabled={!s.naTabela} onClick={() => fechar(() => c().deleteRow().run())}>Excluir linha</MenuItem>
        <MenuItem disabled={!s.naTabela} onClick={() => fechar(() => c().deleteColumn().run())}>Excluir coluna</MenuItem>
        <MenuItem disabled={!s.naTabela} onClick={() => fechar(() => c().deleteTable().run())} sx={{ color: "error.main" }}>Excluir tabela</MenuItem>
      </Menu>
      <Menu anchorEl={menu?.el} open={menuAberto("imagem")} onClose={() => fechar()} sx={{ zIndex: 1800 }}>
        {["25%", "50%", "75%", "100%"].map((l) => (
          <MenuItem key={l} onClick={() => fechar(() => c().definirLarguraImagem(l).run())}>Largura {l} da coluna</MenuItem>
        ))}
        <MenuItem onClick={() => fechar(() => c().definirLarguraImagem(null).run())}>Tamanho original</MenuItem>
        <Divider />
        <MenuItem onClick={() => fechar(() => c().deleteSelection().run())} sx={{ color: "error.main" }}>Remover imagem</MenuItem>
      </Menu>
      <Menu anchorEl={menu?.el} open={menuAberto("caracteres")} onClose={() => fechar()} sx={{ zIndex: 1800 }}
        MenuListProps={{ sx: { maxWidth: 360 } }}>
        {CARACTERES.flatMap(([grupo, lista]) => [
          <ListSubheader key={`g-${grupo}`} sx={{ lineHeight: "28px", bgcolor: "background.paper" }}>{grupo}</ListSubheader>,
          <Box key={`l-${grupo}`} sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, px: 1.5, pb: 1 }}>
            {lista.map((ch) => (
              <Box key={ch} role="button" aria-label={`Inserir ${ch}`} onMouseDown={(e) => e.preventDefault()}
                onClick={() => fechar(() => c().insertContent(ch).run())}
                sx={{ minWidth: 30, height: 30, display: "grid", placeItems: "center", borderRadius: 1, cursor: "pointer", fontSize: 17,
                  border: "1px solid rgba(148,163,184,.3)", "&:hover": { bgcolor: "rgba(56,189,248,.15)" } }}>
                {ch}
              </Box>
            ))}
          </Box>,
        ])}
        <Typography variant="caption" color="text.secondary" sx={{ px: 1.5, display: "block" }}>
          Para fórmulas, use o botão de equação.
        </Typography>
      </Menu>
    </Box>
  );
}
