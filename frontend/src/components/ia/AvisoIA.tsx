import React from 'react';
import { Box, Chip, Tooltip, Typography } from '@mui/material';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import { useAuth } from '../../contexts/AuthContext';
import { CausaIA, StatusIA } from './iaComum';

/**
 * Aviso discreto no lugar dos botões de IA quando ela não está disponível: diz por quê e como resolver,
 * conforme quem está vendo. O diagramador (que não usa IA) e o carregamento inicial não mostram nada.
 */
function comoResolver(c: CausaIA, papel: string): string {
  const adminGeral = papel === 'administrador geral';
  const adminBanca = papel === 'administrador' || adminGeral;
  switch (c.codigo) {
    case 'plataforma_desligada':
      return adminGeral ? 'Ligue em Configurações > Plataforma > IA.' : 'Peça ao administrador geral para ligar a IA da plataforma.';
    case 'sem_chave':
      return adminGeral
        ? 'Em Configurações > Plataforma > IA, cadastre a chave do provedor em uso ou troque para o provedor que já tem chave.'
        : 'Peça ao administrador geral para configurar a chave do provedor de IA.';
    case 'banca_desligada':
      return adminBanca ? 'Ligue em Configurações > IA da banca.' : 'Peça ao administrador da banca para ligar a IA.';
    case 'sem_cliente':
      return 'Escolha um cliente no seletor do topo da tela.';
    default:
      return '';
  }
}

export default function AvisoIA({ status, compacto }: { status: StatusIA; compacto?: boolean }) {
  const { user } = useAuth();
  const papel = user?.role || localStorage.getItem('userRole') || '';
  const causas = (status.causas || []).filter((c) => c.codigo !== 'perfil');
  if (status.disponivel || !causas.length) return null;

  const detalhe = (
    <Box sx={{ p: 0.5 }}>
      <Typography variant="body2" fontWeight={700} sx={{ mb: 0.5 }}>Por que a IA não aparece</Typography>
      {causas.map((c) => (
        <Box key={c.codigo} sx={{ mb: 0.75 }}>
          <Typography variant="body2">• {c.texto}</Typography>
          {comoResolver(c, papel) && (
            <Typography variant="caption" sx={{ display: 'block', pl: 1.5, opacity: 0.85 }}>{comoResolver(c, papel)}</Typography>
          )}
        </Box>
      ))}
    </Box>
  );

  return (
    <Tooltip title={detalhe} arrow placement="bottom-end" slotProps={{ popper: { sx: { zIndex: 1900 } } }}>
      <Chip
        role="status"
        aria-label={`IA indisponível: ${causas.map((c) => c.texto).join(' ')}`}
        icon={<AutoAwesomeOutlinedIcon fontSize="small" />}
        label={compacto ? 'IA indisponível' : 'IA indisponível — por quê?'}
        variant="outlined"
        size="small"
        sx={{ color: 'text.secondary', borderColor: 'rgba(148, 163, 184, 0.4)', borderStyle: 'dashed', cursor: 'help' }}
      />
    </Tooltip>
  );
}
