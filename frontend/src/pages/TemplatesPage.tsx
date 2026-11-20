import React, { useCallback, useEffect, useState, ChangeEvent } from 'react';
import {
  Box, Typography, Paper, Divider, Button, Stack, CircularProgress, Snackbar, Alert, IconButton, Tooltip,
  Dialog, DialogContent, DialogTitle, Chip, Skeleton,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DownloadIcon from '@mui/icons-material/Download';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import ImageNotSupportedOutlinedIcon from '@mui/icons-material/ImageNotSupportedOutlined';
import Layout from '../components/Layout';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';

type TemplateArquivo = {
  nome_arquivo: string;
  descricao?: string;
  url: string;
  enviado_em?: string | null;
  enviado_por?: string | null;
  tamanho?: number | null;
};

type Previa = { header_html?: string; body_html?: string; footer_html?: string };
type EstadoPrevia = { carregando: boolean; erro?: string; html?: string; cabecalho?: boolean; rodape?: boolean; imagens?: boolean };

// HTML montado no servidor a partir do DOCX (texto já escapado lá); aqui ainda removemos qualquer coisa ativa.
function limparHtml(raw: string): string {
  const doc = new DOMParser().parseFromString(raw || '', 'text/html');
  doc.querySelectorAll('script, iframe, object, embed, link, meta, style, form, base').forEach((el) => el.remove());
  doc.querySelectorAll('*').forEach((el) => {
    for (const attr of Array.from(el.attributes)) {
      const nome = attr.name.toLowerCase();
      const valor = attr.value.trim().toLowerCase();
      const srcPermitido = nome === 'src' && valor.startsWith('data:image/');
      if (nome.startsWith('on') || /^(javascript|vbscript):/.test(valor) || (nome === 'src' && !srcPermitido) || nome === 'href') {
        el.removeAttribute(attr.name);
      }
    }
  });
  return doc.body.innerHTML;
}

function montarPagina(p: Previa): EstadoPrevia {
  const h = limparHtml(p.header_html || '');
  const b = limparHtml(p.body_html || '');
  const f = limparHtml(p.footer_html || '');
  const html = `
    <div style="background:#ffffff;color:#0f172a;padding:40px 48px;min-height:1050px;display:flex;flex-direction:column;justify-content:space-between;gap:20px;font-family:Arial,sans-serif;">
      ${h ? `<div style="border-bottom:1px dashed #cbd5e1;padding-bottom:12px;">${h}</div>` : ''}
      <div style="flex:1;">${b || '<div style="color:#94a3b8;font-size:13px;">[Área útil da prova — recebe as questões na exportação]</div>'}</div>
      ${f ? `<div style="border-top:1px dashed #cbd5e1;padding-top:12px;">${f}</div>` : ''}
    </div>`;
  return { carregando: false, html, cabecalho: !!h, rodape: !!f, imagens: /<img\b/i.test(h + b + f) };
}

const formatarData = (iso?: string | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
};
const formatarTamanho = (bytes?: number | null) => {
  if (!bytes && bytes !== 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1).replace('.', ',')} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} MB`;
};

// Largura de referência de uma página A4 (96 dpi); a miniatura é a página inteira reduzida.
const LARGURA_A4 = 794;
const ESCALA_MINIATURA = 0.3;

function Miniatura({ previa, onAbrir }: { previa?: EstadoPrevia; onAbrir: () => void }) {
  return (
    <Box
      role="button"
      tabIndex={0}
      aria-label="Abrir pré-visualização"
      onClick={onAbrir}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onAbrir(); } }}
      sx={{
        position: 'relative', height: Math.round(1123 * ESCALA_MINIATURA), overflow: 'hidden', borderRadius: 2,
        bgcolor: '#ffffff', cursor: 'zoom-in', border: '1px solid rgba(148, 163, 184, 0.25)',
        '&:hover .lupa, &:focus-visible .lupa': { opacity: 1 },
      }}
    >
      {!previa || previa.carregando ? (
        <Box sx={{ p: 2 }}>
          <Skeleton variant="rectangular" height={34} sx={{ bgcolor: '#e2e8f0', mb: 1.5 }} />
          {[90, 75, 82, 60].map((w) => <Skeleton key={w} width={`${w}%`} sx={{ bgcolor: '#e2e8f0' }} />)}
        </Box>
      ) : previa.erro ? (
        <Stack alignItems="center" justifyContent="center" spacing={1} sx={{ height: '100%', color: '#64748b', px: 2, textAlign: 'center' }}>
          <ImageNotSupportedOutlinedIcon />
          <Typography variant="caption" sx={{ color: '#64748b' }}>{previa.erro}</Typography>
        </Stack>
      ) : (
        <Box
          aria-hidden
          sx={{ width: LARGURA_A4, transform: `scale(${ESCALA_MINIATURA})`, transformOrigin: 'top left', pointerEvents: 'none',
            position: 'absolute', left: '50%', ml: `${-(LARGURA_A4 * ESCALA_MINIATURA) / 2}px` }}
          dangerouslySetInnerHTML={{ __html: previa.html || '' }}
        />
      )}
      <Box className="lupa" sx={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', bgcolor: 'rgba(15, 23, 42, 0.35)',
        opacity: 0, transition: 'opacity .15s', color: '#fff' }}>
        <Stack direction="row" spacing={0.75} alignItems="center"><VisibilityIcon fontSize="small" /><Typography variant="body2">Ver em tamanho real</Typography></Stack>
      </Box>
    </Box>
  );
}

const TemplatesPage: React.FC = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();

  const [templates, setTemplates] = useState<TemplateArquivo[]>([]);
  const [previas, setPrevias] = useState<Record<string, EstadoPrevia>>({});
  const [carregando, setCarregando] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean, message: string, severity: "success" | "error" | "info" }>({ open: false, message: '', severity: "success" });
  const [aberto, setAberto] = useState<TemplateArquivo | null>(null);

  const urlTemplate = useCallback((nome: string) => `/api/eventos/${eventId}/templates/${encodeURIComponent(nome)}`, [eventId]);

  const carregarPrevia = useCallback(async (nome: string) => {
    if (!nome.toLowerCase().endsWith('.docx')) {
      setPrevias((p) => ({ ...p, [nome]: { carregando: false, erro: 'Pré-visualização só para .docx' } }));
      return;
    }
    setPrevias((p) => ({ ...p, [nome]: { carregando: true } }));
    try {
      const { data } = await api.get<Previa>(`${urlTemplate(nome)}/preview`);
      setPrevias((p) => ({ ...p, [nome]: montarPagina(data) }));
    } catch (err: any) {
      setPrevias((p) => ({ ...p, [nome]: { carregando: false, erro: err?.response?.data?.detail || 'Sem pré-visualização' } }));
    }
  }, [urlTemplate]);

  const fetchTemplates = useCallback(() => {
    setCarregando(true);
    api
      .get<TemplateArquivo[]>(`/api/eventos/${eventId}/templates`)
      .then((res) => {
        setTemplates(res.data);
        res.data.forEach((t) => carregarPrevia(t.nome_arquivo));
      })
      .catch(() => setSnackbar({ open: true, message: "Erro ao buscar templates.", severity: "error" }))
      .finally(() => setCarregando(false));
  }, [eventId, carregarPrevia]);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleDownload = async (template: TemplateArquivo) => {
    try {
      const response = await api.get(urlTemplate(template.nome_arquivo), { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = template.nome_arquivo;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setSnackbar({ open: true, message: "Erro ao baixar o template.", severity: "error" });
    }
  };

  const handleUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      await api.post(`/api/eventos/${eventId}/templates/upload`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setSnackbar({ open: true, message: "Template enviado com sucesso!", severity: "success" });
      fetchTemplates();
    } catch (err: any) {
      setSnackbar({ open: true, message: err?.response?.data?.detail || "Falha ao enviar template.", severity: "error" });
    }
    setUploading(false);
  };

  const handleDelete = async (template: TemplateArquivo) => {
    if (!window.confirm(`Excluir o template "${template.nome_arquivo}"? Esta ação não pode ser desfeita.`)) return;
    try {
      await api.delete(urlTemplate(template.nome_arquivo));
      setSnackbar({ open: true, message: "Template excluído.", severity: "success" });
      fetchTemplates();
    } catch {
      setSnackbar({ open: true, message: "Erro ao excluir template.", severity: "error" });
    }
  };

  const previaAberta = aberto ? previas[aberto.nome_arquivo] : undefined;

  return (
    <Layout>
      <Paper sx={{ p: { xs: 2, md: 4 }, borderRadius: 5, boxShadow: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 2 }}>
          <Box>
            <Typography variant="h5" fontWeight="bold" color="primary.dark">Templates de Prova</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 720 }}>
              Papel timbrado da prova (cabeçalho, rodapé e margens). Na exportação você escolhe qual usar; as questões entram na área útil.
            </Typography>
          </Box>
          <Stack direction="row" spacing={1.5}>
            <Button component="label" variant="contained" color="primary" startIcon={uploading ? <CircularProgress size={18} color="inherit" /> : <CloudUploadIcon />}
              disabled={uploading} sx={{ borderRadius: 2, fontWeight: 'bold' }}>
              {uploading ? 'Enviando…' : 'Enviar novo template'}
              <input type="file" accept=".docx" hidden onChange={handleUpload} />
            </Button>
            <Button variant="outlined" color="secondary" onClick={() => navigate(-1)} sx={{ borderRadius: 2, fontWeight: 'bold' }}>Voltar</Button>
          </Stack>
        </Box>
        <Divider sx={{ mb: 3 }} />

        {carregando ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}><CircularProgress size={32} /></Box>
        ) : templates.length === 0 ? (
          <Stack alignItems="center" spacing={1.5} sx={{ py: 8, color: 'text.secondary', textAlign: 'center' }}>
            <DescriptionOutlinedIcon sx={{ fontSize: 48, opacity: 0.6 }} />
            <Typography variant="h6">Nenhum template neste evento</Typography>
            <Typography variant="body2" sx={{ maxWidth: 460 }}>
              Envie um arquivo Word (.docx) com o papel timbrado da prova: logotipo, cabeçalho e rodapé. Ele fica guardado criptografado.
            </Typography>
          </Stack>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 2.5 }}>
            {templates.map((t) => {
              const previa = previas[t.nome_arquivo];
              return (
                <Paper key={t.nome_arquivo} variant="outlined" sx={{ p: 1.5, borderRadius: 3, display: 'flex', flexDirection: 'column', gap: 1.25,
                  bgcolor: 'rgba(15, 23, 42, 0.5)', borderColor: 'rgba(148, 163, 184, 0.2)', transition: 'border-color .15s',
                  '&:hover': { borderColor: 'primary.main' } }}>
                  <Miniatura previa={previa} onAbrir={() => setAberto(t)} />
                  <Box sx={{ minWidth: 0 }}>
                    <Tooltip title={t.nome_arquivo} placement="top-start">
                      <Typography fontWeight={700} noWrap>{t.nome_arquivo}</Typography>
                    </Tooltip>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {[formatarData(t.enviado_em) && `Enviado em ${formatarData(t.enviado_em)}`, t.enviado_por && `por ${t.enviado_por}`]
                        .filter(Boolean).join(' ') || 'Sem informações de envio'}
                    </Typography>
                    {formatarTamanho(t.tamanho) && (
                      <Typography variant="caption" color="text.secondary">{formatarTamanho(t.tamanho)}</Typography>
                    )}
                  </Box>
                  {previa && !previa.carregando && !previa.erro && (
                    <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
                      {previa.cabecalho && <Chip size="small" label="Cabeçalho" variant="outlined" />}
                      {previa.rodape && <Chip size="small" label="Rodapé" variant="outlined" />}
                      {previa.imagens && <Chip size="small" label="Imagens" variant="outlined" />}
                      {!previa.cabecalho && !previa.rodape && <Chip size="small" label="Sem cabeçalho/rodapé" variant="outlined" color="warning" />}
                    </Stack>
                  )}
                  <Stack direction="row" spacing={0.5} sx={{ mt: 'auto', pt: 0.5 }}>
                    <Button size="small" startIcon={<VisibilityIcon />} onClick={() => setAberto(t)}>Visualizar</Button>
                    <Button size="small" startIcon={<DownloadIcon />} onClick={() => handleDownload(t)}>Baixar</Button>
                    <Box sx={{ flex: 1 }} />
                    <Tooltip title="Excluir template">
                      <IconButton size="small" color="error" aria-label={`Excluir ${t.nome_arquivo}`} onClick={() => handleDelete(t)}>
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </Paper>
              );
            })}
          </Box>
        )}

        <Snackbar open={snackbar.open} autoHideDuration={3500} onClose={() => setSnackbar({ ...snackbar, open: false })}>
          <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
        </Snackbar>

        {/* Pré-visualização em tamanho real */}
        <Dialog open={!!aberto} maxWidth="md" fullWidth onClose={() => setAberto(null)}>
          <DialogTitle>Visualização: {aberto?.nome_arquivo}</DialogTitle>
          <DialogContent sx={{ minHeight: 500, bgcolor: '#e2e8f0', p: { xs: 1, md: 3 } }}>
            {!previaAberta || previaAberta.carregando ? (
              <Box sx={{ display: 'grid', placeItems: 'center', py: 8 }}><CircularProgress /></Box>
            ) : previaAberta.erro ? (
              <Alert severity="warning">{previaAberta.erro}</Alert>
            ) : (
              <Box sx={{ maxWidth: LARGURA_A4, mx: 'auto', boxShadow: 3 }} dangerouslySetInnerHTML={{ __html: previaAberta.html || '' }} />
            )}
          </DialogContent>
        </Dialog>
      </Paper>
    </Layout>
  );
};

export default TemplatesPage;
