import React from "react";
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Table, TableBody, TableCell, TableRow, Alert } from "@mui/material";

type FrasesPreviewDialogProps = {
  open: boolean;
  onClose: () => void;
  frasesPorTipo: { [tipo: string]: string };
  temFraseRepetida: boolean;
};

const FrasesPreviewDialog: React.FC<FrasesPreviewDialogProps> = ({ open, onClose, frasesPorTipo, temFraseRepetida }) => (
  <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
    <DialogTitle>Frases Motivacionais Sorteadas</DialogTitle>
    <DialogContent>
      {temFraseRepetida && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Atenção: Faltam frases únicas para todas as variações, algumas serão repetidas!
        </Alert>
      )}
      <Table>
        <TableBody>
          {Object.entries(frasesPorTipo).map(([tipo, frase]) => (
            <TableRow key={tipo}>
              <TableCell><b>{tipo}</b></TableCell>
              <TableCell>{frase}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </DialogContent>
    <DialogActions>
      <Button onClick={onClose}>Fechar</Button>
    </DialogActions>
  </Dialog>
);

export default FrasesPreviewDialog;