import React, { useRef, useEffect } from "react";
import { Modal, Box, Typography, TextField, Button, Avatar, Stack, Chip, CircularProgress } from "@mui/material";
import ChatIcon from "@mui/icons-material/Chat";
import ReactMarkdown from "react-markdown";

export interface ChatMessage {
  user?: string;
  ia?: string;
}

interface ChatIAModalProps {
  open: boolean;
  onClose: () => void;
  chatHistory: ChatMessage[];
  chatInput: string;
  setChatInput: (s: string) => void;
  handleSendToChat: () => void;
  loadingChat: boolean;
}

const suggestions = [
  "Reescreva a questão de forma mais clara",
  "Sugira alternativas de resposta",
  "Explique o conceito envolvido",
  "Aponte possíveis ambiguidades"
];

export default function ChatIAModal({
  open,
  onClose,
  chatHistory,
  chatInput,
  setChatInput,
  handleSendToChat,
  loadingChat,
}: ChatIAModalProps) {
  const chatEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (chatEndRef.current) chatEndRef.current.scrollIntoView({ behavior: "smooth" }); }, [chatHistory, loadingChat]);

  return (
    <Modal open={open} onClose={onClose} sx={{ zIndex: 1700 }}>
      <Box
        sx={{
          position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)",
          bgcolor: "background.paper", borderRadius: 3, boxShadow: 8, width: { xs: "98vw", sm: 500 }, minHeight: 540,
          display: "block", zIndex: 1700
        }}>
        {/* Header */}
        <Box sx={{ background: "linear-gradient(90deg, #0284C7 0%, #2563EB 100%)", color: "#fff", p: 2, borderRadius: "12px 12px 0 0", display: "flex", alignItems: "center" }}>
          <ChatIcon sx={{ mr: 1 }} /> <Typography fontWeight={700}>Chat IA - Auxílio ao Revisor</Typography>
          <Box sx={{ flexGrow: 1 }} />
          <Button color="inherit" onClick={onClose} sx={{ ml: 2 }}>Fechar</Button>
        </Box>
        {/* History */}
        <Box sx={{ maxHeight: 330, minHeight: 260, overflowY: "auto", px: 2, py: 1 }}>
          {chatHistory.length === 0 && <Typography color="text.secondary" textAlign="center" mt={4}>Nenhuma mensagem ainda.</Typography>}
          {chatHistory.map((msg, i) => (
            <Stack key={i} direction="row" justifyContent={msg.ia ? "flex-start" : "flex-end"} alignItems="end" spacing={1} mb={2}>
              {msg.ia && <Avatar sx={{ background: "linear-gradient(90deg, #0284C7 0%, #2563EB 100%)", width: 32, height: 32 }}>IA</Avatar>}
              <Box sx={{
                bgcolor: msg.ia ? "rgba(15, 23, 42, 0.85)" : "#0284C7",
                color: "#F8FAFC",
                px: 2, py: 1, borderRadius: 2, maxWidth: 340, wordBreak: "break-word"
              }}>
                <ReactMarkdown>{String(msg.ia || msg.user || "")}</ReactMarkdown>
              </Box>
              {!msg.ia && <Avatar sx={{ bgcolor: "#cfd8dc", width: 32, height: 32 }}>Você</Avatar>}
            </Stack>
          ))}
          {loadingChat && <Typography color="text.secondary" sx={{ pl: 2 }}>IA está respondendo... <CircularProgress size={18} /></Typography>}
          <div ref={chatEndRef} />
        </Box>
        {/* Sugestões rápidas */}
        <Box sx={{ p: 1, pb: 0, display: "flex", gap: 1, flexWrap: "wrap" }}>
          {suggestions.map((s, idx) =>
            <Chip key={idx} label={s} variant="outlined" color="primary" size="small"
              onClick={() => setChatInput(s)} sx={{ cursor: "pointer", mb: 1 }} />
          )}
        </Box>
        {/* Input */}
        <Stack direction="row" spacing={1} sx={{ p: 2, pt: 1 }}>
          <TextField
            fullWidth variant="outlined" size="small" value={chatInput}
            onChange={e => setChatInput(e.target.value)}
            placeholder="Digite sua dúvida, peça uma sugestão ou revisão..."
            onKeyDown={e => { if (e.key === "Enter") handleSendToChat(); }}
          />
          <Button onClick={handleSendToChat} disabled={loadingChat || !chatInput.trim()} variant="contained">Enviar</Button>
        </Stack>
      </Box>
    </Modal>
  );
}