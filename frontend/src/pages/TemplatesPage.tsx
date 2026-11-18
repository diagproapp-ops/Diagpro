import React, { useEffect, useState, ChangeEvent } from 'react';
import {
  Box, Typography, Paper, Divider, Button, Stack, CircularProgress,
  Snackbar, Alert, List, ListItem, ListItemText, IconButton, Tooltip, Dialog, DialogContent, DialogTitle
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';
import VisibilityIcon from '@mui/icons-material/Visibility';
import Layout from '../components/Layout';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import mammoth from 'mammoth';

type TemplateArquivo = {
  nome_arquivo: string;
  descricao?: string;
  url: string;
};

const TemplatesPage: React.FC = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();

  const [templates, setTemplates] = useState<TemplateArquivo[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean, message: string, severity: "success" | "error" | "info" }>({ open: false, message: '', severity: "success" });

  // Visualização
  const [openPreview, setOpenPreview] = useState(false);
  const [previewHtml, setPreviewHtml] = useState<string>('');
  const [previewTitle, setPreviewTitle] = useState<string>('');

  useEffect(() => {
    fetchTemplates();
    // eslint-disable-next-line
  }, [eventId]);

  const fetchTemplates = () => {
    setCarregando(true);
    api
      .get(`/api/eventos/${eventId}/templates`)
      .then(res => {
        // Sempre monta a URL no frontend usando eventId real
        const templates = res.data.map((t: TemplateArquivo) => ({
          ...t,
          url: `/api/eventos/${eventId}/templates/${t.nome_arquivo}`,
        }));
        setTemplates(templates);
      })
      .catch(() => setSnackbar({ open: true, message: "Erro ao buscar templates.", severity: "error" }))
      .finally(() => setCarregando(false));
  };

  const handleDownload = (template: TemplateArquivo) => {
    window.open(template.url, '_blank');
  };

  const handlePreview = async (template: TemplateArquivo) => {
    if (template.nome_arquivo.toLowerCase().endsWith('.docx')) {
        setPreviewTitle(template.nome_arquivo);
        setOpenPreview(true);
        setPreviewHtml('<div style="text-align:center;padding:40px 0;">Carregando visualização...</div>');
        try {
        const response = await fetch(template.url);
        console.log("Status:", response.status, "Content-Type:", response.headers.get('Content-Type'));
        if (!response.ok) {
            throw new Error(`HTTP status ${response.status}`);
        }
        const blob = await response.blob();
        console.log("Tipo do blob:", blob.type, "Tamanho:", blob.size);

        // Debug extra: mostre o conteúdo se não for docx
        if (!blob.type.includes("officedocument") && !blob.type && blob.size < 1000) {
            const text = await blob.text();
            setPreviewHtml(`
            <div style="color:red;">
                O backend retornou (preview debug):<br/>
                <pre style="white-space:pre-line;font-size:12px">${text.substring(0, 400)}</pre>
            </div>
            `);
            console.log("Conteúdo recebido:", text);
            return;
        }

        const arrayBuffer = await blob.arrayBuffer();
        const result = await mammoth.convertToHtml({ arrayBuffer });
        setPreviewHtml(result.value);
        } catch (err: any) {
        setPreviewHtml(`
            <div style="color:red;">
            Erro ao carregar o arquivo DOCX para visualização.<br/>
            <pre style="white-space:pre-line;font-size:12px">${err?.message || err}</pre>
            </div>
        `);
        }
    } else {
        setSnackbar({ open: true, message: "Visualização só disponível para arquivos .docx", severity: "info" });
    }
    };

  const handleUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      await api.post(`/api/eventos/${eventId}/templates/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSnackbar({ open: true, message: "Template enviado com sucesso!", severity: "success" });
      fetchTemplates();
    } catch {
      setSnackbar({ open: true, message: "Falha ao enviar template.", severity: "error" });
    }
    setUploading(false);
  };

  const handleDelete = async (template: TemplateArquivo) => {
    if (!window.confirm(`Excluir o template "${template.nome_arquivo}"?`)) return;
    try {
      await api.delete(`/api/eventos/${eventId}/templates/${encodeURIComponent(template.nome_arquivo)}`);
      setSnackbar({ open: true, message: "Template excluído.", severity: "success" });
      fetchTemplates();
    } catch {
      setSnackbar({ open: true, message: "Erro ao excluir template.", severity: "error" });
    }
  };

  return (
    <Layout>
      <Paper sx={{ p: { xs: 2, md: 4 }, borderRadius: 5, boxShadow: 3 }}>
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 2,
          flexWrap: 'wrap',
          gap: 2
        }}>
          <Typography variant="h5" fontWeight="bold" color="primary.dark">
            Templates de Prova
          </Typography>
          <Button
            variant="outlined"
            color="secondary"
            onClick={() => navigate(-1)}
            sx={{ borderRadius: 2, fontWeight: 'bold' }}
          >
            Voltar
          </Button>
        </Box>
        <Divider sx={{ mb: 3 }} />

        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <Button
            component="label"
            variant="contained"
            color="primary"
            startIcon={<CloudUploadIcon />}
            disabled={uploading}
            sx={{ borderRadius: 2, fontWeight: 'bold', minWidth: 180 }}
          >
            {uploading ? <CircularProgress size={20} color="inherit" /> : "Enviar Novo Template"}
            <input type="file" accept=".docx" hidden onChange={handleUpload} />
          </Button>
        </Stack>

        {carregando ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress size={32} />
          </Box>
        ) : (
          templates.length === 0 ? (
            <Typography color="text.secondary" align="center" sx={{ mt: 6 }}>
              Nenhum template disponível para este evento.
            </Typography>
          ) : (
            <List>
              {templates.map(template => (
                <ListItem
                  key={template.nome_arquivo}
                  secondaryAction={
                    <Stack direction="row" spacing={1}>
                      <Tooltip title="Visualizar">
                        <IconButton color="info" onClick={() => handlePreview(template)}>
                          <VisibilityIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Baixar">
                        <Button
                          variant="contained"
                          color="primary"
                          onClick={() => handleDownload(template)}
                          sx={{ borderRadius: 2 }}
                        >
                          Baixar
                        </Button>
                      </Tooltip>
                      <Tooltip title="Excluir">
                        <IconButton color="error" onClick={() => handleDelete(template)}>
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  }
                >
                  <ListItemText
                    primary={template.nome_arquivo}
                    secondary={template.descricao || ""}
                  />
                </ListItem>
              ))}
            </List>
          )
        )}

        <Snackbar open={snackbar.open} autoHideDuration={3500} onClose={() => setSnackbar({ ...snackbar, open: false })}>
          <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
        </Snackbar>

        {/* Dialog de preview para DOCX */}
        <Dialog open={openPreview} maxWidth="md" fullWidth onClose={() => setOpenPreview(false)}>
          <DialogTitle>
            Visualização: {previewTitle}
          </DialogTitle>
          <DialogContent sx={{ minHeight: 500 }}>
            <div dangerouslySetInnerHTML={{ __html: previewHtml }} />
          </DialogContent>
        </Dialog>
      </Paper>
    </Layout>
  );
};

export default TemplatesPage;