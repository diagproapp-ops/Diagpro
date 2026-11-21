import React, { useEffect, useState } from 'react';
import { Avatar, Box, Button, Stack, Typography } from '@mui/material';
import PhotoCameraOutlinedIcon from '@mui/icons-material/PhotoCameraOutlined';
import api from '../../api';

export const ROTULO_PAPEL: Record<string, string> = {
  'administrador geral': 'Administrador geral',
  administrador: 'Administrador',
  professor: 'Professor',
  revisor: 'Revisor',
  diagramador: 'Diagramador',
};

// A foto vem como link assinado e de vida curta (api/files/...): nunca fica em pasta pública.
export function urlFoto(avatarUrl?: string | null): string | undefined {
  if (!avatarUrl) return undefined;
  if (/^https?:\/\//.test(avatarUrl)) return avatarUrl;
  return `${String(api.defaults.baseURL || '').replace(/\/$/, '')}/${avatarUrl.replace(/^\//, '')}`;
}

// O servidor entrega arquivos só para o mesmo site (Cross-Origin-Resource-Policy): a tela baixa a foto pela API
// e mostra da memória (blob), liberada ao sair. O link assinado nunca vai para o HTML.
export function useFoto(avatarUrl?: string | null): string | undefined {
  const [src, setSrc] = useState<string | undefined>(undefined);
  useEffect(() => {
    const url = urlFoto(avatarUrl);
    if (!url) { setSrc(undefined); return undefined; }
    let objeto: string | undefined;
    let vivo = true;
    fetch(url, { credentials: 'omit', referrerPolicy: 'no-referrer' })
      .then((r) => (r.ok ? r.blob() : Promise.reject(r.status)))
      .then((b) => { if (vivo) { objeto = URL.createObjectURL(b); setSrc(objeto); } })
      .catch(() => { if (vivo) setSrc(undefined); });
    return () => { vivo = false; if (objeto) URL.revokeObjectURL(objeto); };
  }, [avatarUrl]);
  return src;
}

export const FotoAvatar: React.FC<{ avatarUrl?: string | null; nome: string; tamanho?: number; sx?: any; onClick?: () => void }> = (
  { avatarUrl, nome, tamanho = 40, sx, onClick },
) => {
  const src = useFoto(avatarUrl);
  return (
    <Avatar src={src} onClick={onClick} sx={{ width: tamanho, height: tamanho, ...sx }}>
      {(nome || '?').charAt(0).toUpperCase()}
    </Avatar>
  );
};

export const FOTO_TIPOS = 'image/jpeg,image/png,image/webp';
export const FOTO_MAX = 5 * 1024 * 1024;

export function validarFoto(arquivo: File | null): string | null {
  if (!arquivo) return 'A foto é obrigatória.';
  if (!FOTO_TIPOS.split(',').includes(arquivo.type)) return 'Use uma foto JPG, PNG ou WEBP.';
  if (arquivo.size > FOTO_MAX) return 'A foto precisa ter até 5 MB.';
  return null;
}

// Escolha da foto com prévia: rosto visível, sem óculos escuros/boné (o administrador confere antes de aprovar).
export const CampoFoto: React.FC<{ arquivo: File | null; onChange: (f: File | null) => void; erro?: string | null; atual?: string }> = (
  { arquivo, onChange, erro, atual },
) => {
  const [previa, setPrevia] = useState<string | undefined>(undefined);
  useEffect(() => {
    if (!arquivo) { setPrevia(undefined); return undefined; }
    const url = URL.createObjectURL(arquivo);
    setPrevia(url);
    return () => URL.revokeObjectURL(url);
  }, [arquivo]);
  return (
    <Stack direction="row" spacing={2.5} alignItems="center">
      <Avatar src={previa || atual} sx={{ width: 96, height: 96, border: '2px solid', borderColor: erro ? 'error.main' : 'divider' }} />
      <Box>
        <Button component="label" variant="outlined" startIcon={<PhotoCameraOutlinedIcon />}>
          {arquivo || atual ? 'Trocar foto' : 'Escolher foto'}
          <input hidden type="file" accept={FOTO_TIPOS} onChange={(e) => onChange(e.target.files?.[0] || null)} />
        </Button>
        <Typography variant="caption" display="block" color={erro ? 'error' : 'text.secondary'} sx={{ mt: 0.75, maxWidth: 340 }}>
          {erro || 'Obrigatória. Foto recente do rosto, de frente e com boa luz (JPG, PNG ou WEBP, até 5 MB). O administrador confere antes de liberar o acesso.'}
        </Typography>
      </Box>
    </Stack>
  );
};

export function mensagemDaApi(e: any, padrao: string): string {
  const d = e?.response?.data?.detail;
  if (typeof d === 'string') return d;
  if (d?.mensagem) return [d.mensagem, ...(d.problemas || [])].join(' ');
  if (Array.isArray(d)) return 'Preencha os campos obrigatórios.';
  return padrao;
}
