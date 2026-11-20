import { useState, useRef, useEffect } from "react";
import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Modal, TextField, Typography, Stack } from "@mui/material";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import api from "../api";
import { erroIA, podeUsar, textoParaHtml, useStatusIA } from "./ia/iaComum";
import EditIcon from "@mui/icons-material/Edit";
import ChatIcon from "@mui/icons-material/Chat";
import BugReportIcon from "@mui/icons-material/BugReport";
import LibraryBooksIcon from "@mui/icons-material/LibraryBooks";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import FullTiptapEditor from "./FullTiptapEditor";
import { estiloConteudoEditor } from "./BarraFormatacao";
import ChatIAModal, { ChatMessage } from "./ChatIAModal";
import PlagioModal, { PlagioResult } from "./PlagioModal";
import BibliotecaModal, { BibliotecaQuestao } from "./BibliotecaModal";
import DicionarioModal from "./DicionarioModal";
import katex from "katex";
import "katex/dist/katex.min.css";

type Props = {
  label: string;
  value: string;
  onChange: (val: string) => void;
  error?: string;
  required?: boolean;
  placeholder?: string;
  height?: number;
};

function VisualizacaoComMath({ value }: { value: string }) {
  const contentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (contentRef.current) {
      const mathSpans = contentRef.current.querySelectorAll('span[data-type="math"]');
      mathSpans.forEach((el) => {
        const latex = el.getAttribute("data-latex") || "";
        try {
          el.innerHTML = katex.renderToString(latex, { throwOnError: false, displayMode: false });
          el.classList.add("math-tiptap");
        } catch {
          el.textContent = latex;
        }
      });
    }
  }, [value]);
  return (
    <div
      ref={contentRef}
      style={{ textAlign: "justify" }}
      dangerouslySetInnerHTML={{ __html: value }}
    />
  );
}

export default function CampoComEditorAvancado({
  label,
  value,
  onChange,
  error,
  required,
  placeholder,
  height = 500,
}: Props) {
  // Assistente de IA (botões só aparecem se a plataforma e a banca ligarem)
  const statusIA = useStatusIA();
  const [openMelhorar, setOpenMelhorar] = useState(false);
  const [modoMelhorar, setModoMelhorar] = useState("revisar_portugues");
  const [melhorado, setMelhorado] = useState<{ texto: string; mudancas: string[] } | null>(null);
  const [loadingMelhorar, setLoadingMelhorar] = useState(false);
  const [erroMelhorar, setErroMelhorar] = useState<string | null>(null);

  // Editor modal states
  const [modalOpen, setModalOpen] = useState(false);
  const [editorValue, setEditorValue] = useState<string>(value);

  // Chat IA
  const [openChat, setOpenChat] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [loadingChat, setLoadingChat] = useState(false);

  // Plágio
  const [openPlagio, setOpenPlagio] = useState(false);
  const [plagioResult, setPlagioResult] = useState<PlagioResult | null>(null);
  const [loadingPlagio, setLoadingPlagio] = useState(false);

  // Biblioteca
  const [openBiblioteca, setOpenBiblioteca] = useState(false);
  const [buscaBib, setBuscaBib] = useState("");
  const [resultBib, setResultBib] = useState<BibliotecaQuestao[]>([]);
  const [loadingBib, setLoadingBib] = useState(false);

  // Dicionário
  const [openDicionario, setOpenDicionario] = useState(false);
  const [dicionarioTermo, setDicionarioTermo] = useState("");
  const [dicionarioDef, setDicionarioDef] = useState("");
  const [loadingDicio, setLoadingDicio] = useState(false);

  // Editor modal
  const handleOpen = () => {
    setEditorValue(value);
    setModalOpen(true);
  };
  const handleOk = () => {
    onChange(editorValue);
    setModalOpen(false);
  };
  const handleCancel = () => {
    setEditorValue(value);
    setModalOpen(false);
  };

  // Chat IA handler
  const handleSendToChat = async () => {
    if (!chatInput.trim()) return;
    setLoadingChat(true);
    try {
      const { data } = await api.post("/ia/chat", { mensagem: chatInput, contexto: editorValue });
      setChatHistory([
        ...chatHistory,
        { user: chatInput, ia: data.resposta ?? "Sem resposta" }
      ]);
      setChatInput("");
    } catch (err) {
      setChatHistory([...chatHistory, { user: chatInput, ia: erroIA(err) }]);
    }
    setLoadingChat(false);
  };

  // Melhorar texto com IA (o resultado substitui o texto só se o usuário confirmar)
  const handleMelhorar = async () => {
    setLoadingMelhorar(true);
    setErroMelhorar(null);
    try {
      const { data } = await api.post("/ia/texto/melhorar", { texto: editorValue, modo: modoMelhorar });
      setMelhorado(data);
    } catch (err) {
      setErroMelhorar(erroIA(err));
    }
    setLoadingMelhorar(false);
  };

  // Plágio handler
  const handleCheckPlagio = async () => {
    setLoadingPlagio(true);
    setOpenPlagio(true);
    try {
      const { data } = await api.post("/api/check-plagio", { texto: editorValue });
      setPlagioResult(data);
    } catch (err) {
      setPlagioResult({
        success: false,
        percentual: 0,
        fontes: [],
        message: "Erro na verificação."
      });
    }
    setLoadingPlagio(false);
  };

  // Biblioteca handler
  const handleBuscarBib = async () => {
    setLoadingBib(true);
    try {
      const { data } = await api.post("/api/biblioteca", { busca: buscaBib });
      setResultBib(data.questoes || []);
    } catch (err) {
      setResultBib([]);
    }
    setLoadingBib(false);
  };

  // Dicionário handler
  const handleBuscarDicionario = async () => {
    if (!dicionarioTermo.trim()) return;
    setLoadingDicio(true);
    setDicionarioDef("");
    try {
      const { data } = await api.post("/api/dicionario", { termo: dicionarioTermo });
      setDicionarioDef(data.definicao ?? "Nenhuma definição encontrada.");
    } catch (err) {
      setDicionarioDef("Erro ao buscar definição.");
    }
    setLoadingDicio(false);
  };

  // Botões auxiliares para passar para o editor e para o fullscreen
  const renderExtraButtons = () => (
    <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
      {podeUsar(statusIA, "chat") && (
        <Button size="small" startIcon={<ChatIcon />} onClick={() => setOpenChat(true)} variant="contained" color="info">
          Chat IA
        </Button>
      )}
      {podeUsar(statusIA, "melhorar_texto") && (
        <Button size="small" startIcon={<AutoFixHighIcon />} onClick={() => { setMelhorado(null); setErroMelhorar(null); setOpenMelhorar(true); }} variant="contained" color="secondary">
          Melhorar texto
        </Button>
      )}
      <Button size="small" startIcon={<BugReportIcon />} onClick={handleCheckPlagio} variant="contained" color="error">
        Plágio
      </Button>
      <Button size="small" startIcon={<LibraryBooksIcon />} onClick={() => setOpenBiblioteca(true)} variant="contained" color="success">
        Biblioteca
      </Button>
      <Button size="small" startIcon={<MenuBookIcon />} onClick={() => setOpenDicionario(true)} variant="contained" color="secondary">
        Dicionário
      </Button>
    </Stack>
  );

  return (
    <Box sx={{ mb: 3 }}>
      {/* Label apenas */}
      <Box sx={{ display: "flex", alignItems: "center", mb: 0.5 }}>
        <Typography
          variant="subtitle2"
          fontWeight={600}
          sx={{ color: "text.primary", letterSpacing: 0.2, flexGrow: 1 }}
          component="label"
        >
          {label} {required ? <span style={{ color: "#d32f2f" }}>*</span> : null}
        </Typography>
        <Button
          size="small"
          startIcon={<EditIcon />}
          onClick={handleOpen}
          variant="outlined"
          color="primary"
          sx={{ ml: 2 }}
        >
          Editar
        </Button>
      </Box>
      {/* Visualização do texto com KaTeX */}
      <Box
        sx={{
          border: error ? "2px solid #d32f2f" : "1px solid rgba(148, 163, 184, 0.25)",
          borderRadius: 2,
          p: 2,
          minHeight: 48,
          bgcolor: "background.default",
          mb: 1,
          fontSize: 16,
          color: "text.primary",
          maxHeight: 240,
          overflowY: "auto",
          overflowX: "auto",
          ...estiloConteudoEditor,
          "& img": {
            maxWidth: "100%",
            maxHeight: "180px",
            height: "auto !important",
            width: "auto !important",
            display: "block",
            margin: "12px auto",
            objectFit: "contain",
            borderRadius: "8px"
          }
        }}
      >
        <VisualizacaoComMath value={value} />
      </Box>
      {error && (
        <Typography variant="caption" color="error" sx={{ mb: 1, display: "block" }}>
          {error}
        </Typography>
      )}
      {/* Modal Editor avançado */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        disableEscapeKeyDown
        aria-labelledby="modal-edicao-avancada"
      >
        <Box
          sx={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: { xs: "98vw", sm: 750, md: 950, lg: 1200 },
            maxWidth: "98vw",
            bgcolor: "background.paper",
            borderRadius: 3,
            boxShadow: 24,
            p: 3,
            display: "flex",
            flexDirection: "column",
            minHeight: 520,
            maxHeight: "92vh",
          }}
        >
          <Typography id="modal-edicao-avancada" variant="subtitle1" fontWeight="bold" sx={{ mb: 1 }}>
            {label} (Edição Avançada)
          </Typography>

          <FullTiptapEditor
            label={label}
            value={editorValue}
            onChange={setEditorValue}
            error={error}
            required={required}
            height={height}
            placeholder={placeholder}
            renderExtraButtons={renderExtraButtons}
          />

          <Stack direction="row" spacing={2} justifyContent="flex-end">
            <Button variant="outlined" color="secondary" onClick={handleCancel} sx={{ fontWeight: 600, borderRadius: 2 }}>
              Cancelar
            </Button>
            <Button variant="contained" color="primary" onClick={handleOk} sx={{ fontWeight: 600, borderRadius: 2 }}>
              OK
            </Button>
          </Stack>
        </Box>
      </Modal>

      {/* MODAIS PREMIUM - sempre disponíveis em qualquer modo */}
      <ChatIAModal
        open={openChat}
        onClose={() => setOpenChat(false)}
        chatHistory={chatHistory}
        chatInput={chatInput}
        setChatInput={setChatInput}
        handleSendToChat={handleSendToChat}
        loadingChat={loadingChat}
      />

      <Dialog open={openMelhorar} onClose={() => setOpenMelhorar(false)} maxWidth="md" fullWidth sx={{ zIndex: 1601 }}>
        <DialogTitle>Melhorar texto com IA</DialogTitle>
        <DialogContent dividers>
          <Alert severity="info" sx={{ mb: 2 }}>
            Vai para a IA só o texto deste campo (sem imagens). Negrito, imagens e fórmulas não são mantidos no texto sugerido.
          </Alert>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
            <TextField select size="small" label="O que fazer" value={modoMelhorar} onChange={e => setModoMelhorar(e.target.value)} sx={{ minWidth: 260 }}>
              <MenuItem value="revisar_portugues">Corrigir português</MenuItem>
              <MenuItem value="clareza">Deixar mais claro</MenuItem>
              <MenuItem value="simplificar">Simplificar</MenuItem>
              <MenuItem value="formalizar">Linguagem formal de prova</MenuItem>
            </TextField>
            <Button variant="contained" onClick={handleMelhorar} disabled={loadingMelhorar || !editorValue || editorValue === "<p></p>"}>
              {melhorado ? "Gerar de novo" : "Gerar sugestão"}
            </Button>
            {loadingMelhorar && <CircularProgress size={22} />}
          </Stack>
          {erroMelhorar && <Alert severity="error" sx={{ mb: 2 }}>{erroMelhorar}</Alert>}
          {melhorado && (
            <Box>
              <Typography sx={{ whiteSpace: "pre-wrap", mb: 1.5 }}>{melhorado.texto}</Typography>
              {!!melhorado.mudancas?.length && (
                <Typography variant="body2" color="text.secondary">Mudanças: {melhorado.mudancas.join("; ")}</Typography>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenMelhorar(false)}>Fechar</Button>
          {melhorado && (
            <Button variant="contained" onClick={() => { setEditorValue(textoParaHtml(melhorado.texto)); setOpenMelhorar(false); }}>
              Substituir no editor
            </Button>
          )}
        </DialogActions>
      </Dialog>

      <PlagioModal
        open={openPlagio}
        onClose={() => setOpenPlagio(false)}
        plagioResult={plagioResult}
        loadingPlagio={loadingPlagio}
      />

      <BibliotecaModal
        open={openBiblioteca}
        onClose={() => setOpenBiblioteca(false)}
        buscaBib={buscaBib}
        setBuscaBib={setBuscaBib}
        handleBuscarBib={handleBuscarBib}
        resultBib={resultBib}
        loadingBib={loadingBib}
        usarQuestao={(q) => {
          setEditorValue(q.enunciado);
          setOpenBiblioteca(false);
        }}
      />

      <DicionarioModal
        open={openDicionario}
        onClose={() => setOpenDicionario(false)}
        dicionarioTermo={dicionarioTermo}
        setDicionarioTermo={setDicionarioTermo}
        handleBuscarDicionario={handleBuscarDicionario}
        dicionarioDef={dicionarioDef}
        loadingDicio={loadingDicio}
      />
    </Box>
  );
}