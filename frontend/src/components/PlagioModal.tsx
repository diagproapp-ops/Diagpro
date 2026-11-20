import React from "react";
import {
  Modal, Box, Typography, LinearProgress, Card, CardContent, Chip,
  Button, CircularProgress, Link, Stack
} from "@mui/material";
import BugReportIcon from "@mui/icons-material/BugReport";

export interface PlagioFonte {
  url: string;
  trecho: string;
  titulo?: string;
  score?: number;
}
export interface PlagioResult {
  success: boolean;
  percentual: number;
  message?: string;
  fontes: PlagioFonte[];
}

interface PlagioModalProps {
  open: boolean;
  onClose: () => void;
  plagioResult?: PlagioResult | null;
  loadingPlagio: boolean;
}

export default function PlagioModal({ open, onClose, plagioResult, loadingPlagio }: PlagioModalProps) {
  const riskColor = (p: number) => p > 60 ? "error" : p > 30 ? "warning" : "success";
  return (
    <Modal open={open} onClose={onClose} sx={{ zIndex: 1700 }}>
      <Box sx={{
        position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)",
        bgcolor: "#0B1325", borderRadius: 3, boxShadow: 8, width: { xs: "98vw", sm: 480 }, minHeight: 380,
        display: "block", zIndex: 1700
      }}>
        <Box sx={{ bgcolor: "#f44336", color: "#fff", p: 2, borderRadius: "12px 12px 0 0", display: "flex", alignItems: "center" }}>
          <BugReportIcon sx={{ mr: 1 }} /> <Typography fontWeight={700}>Verificação de Plágio</Typography>
          <Box sx={{ flexGrow: 1 }} />
          <Button color="inherit" onClick={onClose} sx={{ ml: 2 }}>Fechar</Button>
        </Box>
        <Box sx={{ px: 3, py: 2 }}>
          {loadingPlagio && <CircularProgress />}
          {!loadingPlagio && plagioResult && (
            <>
              <LinearProgress
                variant="determinate"
                value={plagioResult.percentual || 0}
                sx={{ height: 13, borderRadius: 2, mb: 2, bgcolor: "rgba(244, 67, 54, 0.18)" }}
                color={riskColor(plagioResult.percentual)}
              />
              <Stack direction="row" alignItems="center" mb={2}>
                <Typography fontWeight={600} mr={2}>Similaridade:</Typography>
                <Chip
                  label={plagioResult.percentual + "%"}
                  color={riskColor(plagioResult.percentual)}
                  sx={{ fontWeight: 700, fontSize: 18 }}
                />
                {plagioResult.message && (
                  <Typography ml={2} color="text.secondary">{plagioResult.message}</Typography>
                )}
              </Stack>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>Fontes encontradas:</Typography>
              {plagioResult.fontes.length === 0 && <Typography color="text.secondary">Nenhuma fonte suspeita encontrada.</Typography>}
              {plagioResult.fontes.map((fonte, i) => (
                <Card key={i} sx={{ mb: 1, bgcolor: "background.default" }}>
                  <CardContent>
                    <Typography variant="body2" gutterBottom>
                      <Link href={fonte.url} target="_blank" underline="hover" fontWeight={600}>{fonte.titulo || fonte.url}</Link>
                    </Typography>
                    <Typography variant="body2" color="text.secondary" dangerouslySetInnerHTML={{ __html: fonte.trecho }} />
                  </CardContent>
                </Card>
              ))}
            </>
          )}
        </Box>
      </Box>
    </Modal>
  );
}