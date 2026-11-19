import React from "react";
import {
  Modal,
  Box,
  Typography,
  Card,
  CardHeader,
  CardContent,
  Avatar,
  CardActions,
  Button,
  CircularProgress,
  Stack,
  TextField,
  InputAdornment,
  IconButton,
  Chip,
  Tooltip,
} from "@mui/material";
import LibraryBooksIcon from "@mui/icons-material/LibraryBooks";
import SearchIcon from "@mui/icons-material/Search";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";

export type BibliotecaQuestao = {
  id: number | string;
  assunto: string;
  enunciado: string;
  comentario?: string;
  nivel?: string;
  ano?: string;
  banca?: string;
  disciplina?: string;
  alternativas?: string[];
};

interface BibliotecaModalProps {
  open: boolean;
  onClose: () => void;
  buscaBib: string;
  setBuscaBib: (val: string) => void;
  handleBuscarBib: () => void;
  resultBib: BibliotecaQuestao[];
  loadingBib: boolean;
  usarQuestao: (questao: BibliotecaQuestao) => void;
}

export default function BibliotecaModal({
  open,
  onClose,
  buscaBib,
  setBuscaBib,
  handleBuscarBib,
  resultBib,
  loadingBib,
  usarQuestao,
}: BibliotecaModalProps) {
  return (
    <Modal open={open} onClose={onClose} sx={{ zIndex: 1601 }}>
      <Box
        sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          bgcolor: "#0B1325",
          borderRadius: 3,
          boxShadow: 8,
          width: { xs: "98vw", sm: 680 },
          minHeight: 420,
          maxHeight: "92vh",
          overflowY: "auto",
          display: "block",
          zIndex: 1601,
        }}
      >
        {/* Header */}
        <Box
          sx={{
            bgcolor: "#43a047",
            color: "#fff",
            p: 2,
            borderRadius: "12px 12px 0 0",
            display: "flex",
            alignItems: "center",
          }}
        >
          <LibraryBooksIcon sx={{ mr: 1 }} />
          <Typography fontWeight={700}>Biblioteca de Questões</Typography>
          <Tooltip title="Busque por assunto, disciplina, ano, banca ou palavras do enunciado.">
            <HelpOutlineIcon sx={{ ml: 2, color: "#c8e6c9" }} />
          </Tooltip>
          <Box sx={{ flexGrow: 1 }} />
          <Button color="inherit" onClick={onClose} sx={{ ml: 2 }}>
            Fechar
          </Button>
        </Box>
        {/* Busca */}
        <Stack direction="row" spacing={2} alignItems="flex-end" sx={{ p: 2 }}>
          <TextField
            label="Buscar questão, assunto, ano, banca, palavra-chave..."
            value={buscaBib}
            autoFocus
            onChange={(e) => setBuscaBib(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleBuscarBib();
            }}
            fullWidth
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton onClick={handleBuscarBib}>
                    <SearchIcon />
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </Stack>
        {/* Loader */}
        {loadingBib && <CircularProgress sx={{ m: 2 }} />}
        {/* Cards */}
        <Box
          sx={{
            display: "flex",
            flexWrap: "wrap",
            gap: 2,
            p: 2,
            justifyContent: resultBib.length > 0 ? "flex-start" : "center",
          }}
        >
          {resultBib.length === 0 && !loadingBib && (
            <Typography color="text.secondary" m={3}>
              Nenhuma questão encontrada. Tente outras palavras ou filtre por disciplina/ano.
            </Typography>
          )}
          {resultBib.map((questao, i) => (
            <Card
              key={i}
              sx={{
                width: 330,
                minHeight: 160,
                maxWidth: "98vw",
                position: "relative",
                bgcolor: "background.default",
                border: "1px solid", borderColor: "divider",
                boxShadow: 2,
                mb: 1,
              }}
            >
              <CardHeader
                avatar={
                  <Avatar sx={{ bgcolor: "#1976d2" }}>
                    {questao.assunto?.[0] || "?"}
                  </Avatar>
                }
                title={
                  <Typography fontWeight={600} variant="subtitle1">
                    {questao.assunto}
                  </Typography>
                }
                subheader={
                  <Stack direction="row" spacing={1}>
                    {questao.nivel && (
                      <Chip size="small" label={questao.nivel} color="info" />
                    )}
                    {questao.ano && (
                      <Chip
                        size="small"
                        label={questao.ano}
                        variant="outlined"
                        color="default"
                      />
                    )}
                    {questao.banca && (
                      <Chip
                        size="small"
                        label={questao.banca}
                        variant="outlined"
                        color="secondary"
                      />
                    )}
                    {questao.disciplina && (
                      <Chip
                        size="small"
                        label={questao.disciplina}
                        variant="outlined"
                        color="success"
                      />
                    )}
                  </Stack>
                }
              />
              <CardContent sx={{ pt: 1 }}>
                <Typography
                  variant="body2"
                  sx={{
                    mb: 1,
                    minHeight: 40,
                    maxHeight: 60,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                  }}
                  dangerouslySetInnerHTML={{
                    __html:
                      questao.enunciado.length > 180
                        ? questao.enunciado.slice(0, 180) + "..."
                        : questao.enunciado,
                  }}
                />
                {questao.comentario && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontStyle: "italic", display: "block", mb: 1 }}
                  >
                    {questao.comentario}
                  </Typography>
                )}
                {/* Alternativas (opcional) */}
                {questao.alternativas && (
                  <Stack direction="column" spacing={0.5} sx={{ mt: 1 }}>
                    {questao.alternativas.map((alt, idx) => (
                      <Typography
                        key={idx}
                        variant="body2"
                        sx={{
                          background: idx === 0 ? "rgba(14, 165, 233, 0.14)" : "rgba(15, 23, 42, 0.7)",
                          px: 1.2,
                          borderRadius: 1,
                        }}
                      >
                        <b>{String.fromCharCode(65 + idx)})</b> {alt}
                      </Typography>
                    ))}
                  </Stack>
                )}
              </CardContent>
              <CardActions>
                <Button
                  size="small"
                  variant="contained"
                  onClick={() => usarQuestao(questao)}
                >
                  Usar esta questão
                </Button>
              </CardActions>
            </Card>
          ))}
        </Box>
      </Box>
    </Modal>
  );
}