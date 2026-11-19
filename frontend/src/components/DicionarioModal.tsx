import React from "react";
import { Modal, Box, Typography, TextField, Button, Stack, CircularProgress } from "@mui/material";
import MenuBookIcon from "@mui/icons-material/MenuBook";

interface DicionarioModalProps {
  open: boolean;
  onClose: () => void;
  dicionarioTermo: string;
  setDicionarioTermo: (val: string) => void;
  handleBuscarDicionario: () => void;
  dicionarioDef: string;
  loadingDicio: boolean;
}

export default function DicionarioModal({
  open,
  onClose,
  dicionarioTermo,
  setDicionarioTermo,
  handleBuscarDicionario,
  dicionarioDef,
  loadingDicio,
}: DicionarioModalProps) {
  return (
    <Modal open={open} onClose={onClose} sx={{ zIndex: 1601 }}>
      <Box
        sx={{
          position: "fixed",
          top: { xs: 0, sm: 80 },
          right: 0,
          zIndex: 1601,
          bgcolor: "#0B1325",
          borderRadius: { xs: 0, sm: "18px 0 0 18px" },
          boxShadow: 8,
          width: { xs: "100vw", sm: 400, md: 420 },
          minHeight: { xs: "100vh", sm: 340 },
          maxHeight: { xs: "100vh", sm: "85vh" },
          display: "block",
          transition: "transform 0.35s cubic-bezier(.4,0,.2,1)",
          transform: open ? "translateX(0)" : "translateX(120%)",
          overflowY: "auto",
        }}
      >
        <Box sx={{ background: "linear-gradient(90deg, #0284C7 0%, #2563EB 100%)", color: "#fff", p: 2, borderRadius: { xs: 0, sm: "18px 0 0 0" }, display: "flex", alignItems: "center" }}>
          <MenuBookIcon sx={{ mr: 1 }} /> <Typography fontWeight={700} flex={1}>Dicionário</Typography>
          <Button color="inherit" onClick={onClose}>FECHAR</Button>
        </Box>
        <Stack direction="row" spacing={2} alignItems="flex-end" sx={{ p: 2 }}>
          <TextField
            label="Palavra"
            value={dicionarioTermo}
            onChange={e => setDicionarioTermo(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") handleBuscarDicionario(); }}
            disabled={loadingDicio}
            size="small"
            fullWidth
          />
          <Button onClick={handleBuscarDicionario} disabled={loadingDicio || !dicionarioTermo.trim()}>BUSCAR</Button>
        </Stack>
        {loadingDicio && <CircularProgress sx={{ m: 2 }} />}
        {dicionarioDef && (
          <Typography
            variant="body1"
            sx={{
              bgcolor: "rgba(14, 165, 233, 0.12)",
              borderRadius: 2,
              p: 2,
              m: 2,
              fontWeight: 600,
              fontSize: 16,
              whiteSpace: "pre-line",
              maxHeight: { xs: "55vh", sm: "46vh" },
              overflowY: "auto"
            }}
          >
            {dicionarioDef}
          </Typography>
        )}
      </Box>
    </Modal>
  );
}