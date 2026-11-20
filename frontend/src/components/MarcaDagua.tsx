import React, { useMemo } from 'react';
import { Box } from '@mui/material';
import { useAuth } from '../contexts/AuthContext';

// Marca d'água pessoal nas pré-visualizações de prova e gabarito: nome do usuário, data/hora e "CONFIDENCIAL"
// repetidos na diagonal. Se alguém fotografar ou capturar a tela, a imagem mostra quem estava vendo.
// Também bloqueia seleção/cópia e a impressão do navegador nessa área. (Os arquivos exportados não levam marca.)
export default function MarcaDagua({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const quem = (user as any)?.full_name || user?.username || 'usuário';
  const fundo = useMemo(() => {
    const quando = new Date().toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
    const texto = `${quem} • ${quando} • CONFIDENCIAL`.replace(/[<>&"']/g, '');
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='420' height='220'>` +
      `<text x='0' y='120' transform='rotate(-24 210 110)' fill='rgba(148,163,184,0.22)' font-size='16' font-family='Arial'>${texto}</text></svg>`;
    return `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}")`;
  }, [quem]);

  return (
    <Box
      sx={{ position: 'relative', userSelect: 'none', '@media print': { display: 'none' } }}
      onCopy={(e) => e.preventDefault()}
      onCut={(e) => e.preventDefault()}
      onContextMenu={(e) => e.preventDefault()}
      data-marca-dagua={quem}
    >
      {children}
      <Box aria-hidden sx={{ position: 'absolute', inset: 0, pointerEvents: 'none', backgroundImage: fundo, backgroundRepeat: 'repeat', zIndex: 5 }} />
    </Box>
  );
}
