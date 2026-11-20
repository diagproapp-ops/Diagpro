import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Paper, Divider, Button, List, ListItem, ListItemIcon, ListItemText,
  Checkbox, Snackbar, Alert, CircularProgress, Tooltip, Stack, FormControlLabel,
  Select, MenuItem, InputLabel, FormControl, TextField, LinearProgress, Dialog, DialogTitle, DialogContent, DialogActions, IconButton,
  ToggleButton, ToggleButtonGroup
} from '@mui/material';
import AssignmentIndIcon from '@mui/icons-material/AssignmentInd';
import DescriptionIcon from '@mui/icons-material/Description';
import SettingsIcon from '@mui/icons-material/Settings';
import DownloadIcon from '@mui/icons-material/Download';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import VisibilityIcon from '@mui/icons-material/Visibility';
import PreviewIcon from '@mui/icons-material/Preview';
import SearchIcon from '@mui/icons-material/Search';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import api from '../api';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import EntregaPorLink from '../components/EntregaPorLink';

function sanitizePreviewHtml(rawHtml: string): string {
  const parser = new DOMParser();
  const doc = parser.parseFromString(rawHtml || '', 'text/html');
  doc.querySelectorAll('script, iframe, object, embed, link, meta').forEach((el) => el.remove());
  doc.querySelectorAll('*').forEach((el) => {
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase();
      const val = attr.value.trim().toLowerCase();
      if (name.startsWith('on') || /^javascript:/i.test(val)) {
        el.removeAttribute(attr.name);
      }
    }
  });
  return doc.body.innerHTML;
}

type Cargo = {
  id_cargo: string;
  nome_cargo: string;
  codigo_cargo?: string;
  selecionado: boolean;
};

type Template = {
  id: string;
  nome: string;
  descricao?: string;
  urlPreview?: string;
};

const fontes = ["Arial", "Calibri", "Courier New", "Garamond", "Georgia", "Tahoma", "Times New Roman", "Trebuchet MS", "Verdana"];
const tamanhosFonte = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30];

const ExportacaoProvaPage: React.FC = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const [cargos, setCargos] = useState<Cargo[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateSelecionado, setTemplateSelecionado] = useState<string>(''); // '' = padrão
  const [carregando, setCarregando] = useState(true);
  const [carregandoTemplates, setCarregandoTemplates] = useState(true);
  const [selecionarTodos, setSelecionarTodos] = useState(true);
  const [filtroCargo, setFiltroCargo] = useState('');
  const [previewTemplateOpen, setPreviewTemplateOpen] = useState(false);
  const [previewPartes, setPreviewPartes] = useState<{ headerHtml: string; bodyHtml: string; footerHtml: string }>({
    headerHtml: '',
    bodyHtml: '',
    footerHtml: '',
  });
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewErro, setPreviewErro] = useState<string | null>(null);
  // Imagem real da página do template (mesmo gerador da exportação). Sem ela, cai na leitura em HTML.
  const [previewImagem, setPreviewImagem] = useState<string | null>(null);

  // Preview da prova real antes da exportação
  const [previewProvaOpen, setPreviewProvaOpen] = useState(false);
  const [previewProvaCargoId, setPreviewProvaCargoId] = useState('');
  const [previewProvaLoading, setPreviewProvaLoading] = useState(false);
  const [previewProvaErro, setPreviewProvaErro] = useState<string | null>(null);
  const [previewProvaDados, setPreviewProvaDados] = useState<any | null>(null);

  // Opções de formatação e saída
  const [fonte, setFonte] = useState("Calibri");
  const [tamanhoFonte, setTamanhoFonte] = useState(12);
  const [duasColunas, setDuasColunas] = useState(false);
  const [quebraBloco, setQuebraBloco] = useState(true);
  const [manterDocx, setManterDocx] = useState(true);
  const [exibirCodigoCurto, setExibirCodigoCurto] = useState(false);
  const [exibirGabaritoMarcado, setExibirGabaritoMarcado] = useState(false);

  // Senha do evento
  const [senha, setSenha] = useState('');
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [senhaCorreta, setSenhaCorreta] = useState(false);
  const [validandoSenha, setValidandoSenha] = useState(false);
  const [erroSenha, setErroSenha] = useState<string | null>(null);

  // Barra de progresso da exportação
  const [exportando, setExportando] = useState(false);
  const [progresso, setProgresso] = useState(0);

  // Dialog de confirmação
  const [dialogConfirmar, setDialogConfirmar] = useState(false);
  // Checagem antes de exportar (bloqueios impedem; avisos permitem "exportar mesmo assim")
  type ProblemaQuestao = { questao: number | null; codigo: string; disciplina: string; problema: string };
  type VerificacaoCargo = { id_cargo: string; cargo: string; total_questoes: number; bloqueios: ProblemaQuestao[]; avisos: ProblemaQuestao[]; avisos_gerais: string[] };
  const [verificacao, setVerificacao] = useState<VerificacaoCargo[] | null>(null);
  const [verificando, setVerificando] = useState(false);
  const totalBloqueios = (verificacao || []).reduce((n, v) => n + v.bloqueios.length, 0);
  const totalAvisos = (verificacao || []).reduce((n, v) => n + v.avisos.length + v.avisos_gerais.length, 0);

  // Snackbar feedback
  const [snackbar, setSnackbar] = useState<{ open: boolean, message: string, severity: "success" | "error" | "info" | "warning" }>(
    { open: false, message: '', severity: "success" }
  );

  const validarSenhaEvento = async (senhaDigitada: string) => {
    const limpa = senhaDigitada.trim();
    if (!limpa) {
      setSenhaCorreta(false);
      setErroSenha(null);
      return;
    }
    setValidandoSenha(true);
    setErroSenha(null);
    try {
      const resp = await api.post(`/api/export/eventos/${eventId}/validar-senha`, { senha: senhaDigitada });
      const valida = Boolean(resp.data && resp.data.valida === true);
      setSenhaCorreta(valida);
      if (!valida) setErroSenha('Senha do evento incorreta.');
    } catch (err: any) {
      setSenhaCorreta(false);
      if (err?.response?.status === 429) {
        setErroSenha('Muitas tentativas seguidas. Aguarde 1 minuto antes de tentar novamente.');
      } else {
        setErroSenha('Não foi possível validar a senha.');
      }
    } finally {
      setValidandoSenha(false);
    }
  };

  const handleSenhaChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSenha(e.target.value);
    setSenhaCorreta(false);
    setErroSenha(null);
  };

  const abrirPreviewTemplate = async () => {
    setPreviewTemplateOpen(true);
    setPreviewImagem(null);
    setPreviewPartes({ headerHtml: '', bodyHtml: '', footerHtml: '' });
    setPreviewErro(null);
    if (!templateSelecionado) return;
    if (!templateSelecionado.toLowerCase().endsWith('.docx')) {
      setPreviewErro('Visualização direta disponível apenas para templates .docx.');
      return;
    }
    setPreviewLoading(true);
    try {
      const { data } = await api.get(`/api/eventos/${eventId}/templates/${encodeURIComponent(templateSelecionado)}/miniatura`,
        { responseType: 'blob', timeout: 180000 });
      setPreviewImagem(URL.createObjectURL(data as Blob));
      setPreviewLoading(false);
      return;
    } catch {
      // segue para a leitura em HTML
    }
    try {
      const res = await api.get<{ header_html?: string; body_html?: string; footer_html?: string }>(
        `/api/eventos/${eventId}/templates/${encodeURIComponent(templateSelecionado)}/preview`
      );
      setPreviewPartes({
        headerHtml: sanitizePreviewHtml(res.data?.header_html || ''),
        bodyHtml: sanitizePreviewHtml(res.data?.body_html || ''),
        footerHtml: sanitizePreviewHtml(res.data?.footer_html || ''),
      });
    } catch (err: any) {
      setPreviewErro(err?.response?.data?.detail || 'Não foi possível carregar o preview deste template.');
    } finally {
      setPreviewLoading(false);
    }
  };

  const fecharPreviewTemplate = () => {
    setPreviewTemplateOpen(false);
    if (previewImagem) URL.revokeObjectURL(previewImagem);
    setPreviewImagem(null);
  };

  // Pré-visualização = a prova gerada pelo MESMO código da exportação, com as MESMAS opções desta tela.
  const carregarPreviewProvaReal = async (cargoIdAlvo: string, variacao = 1) => {
    if (!cargoIdAlvo) return;
    setPreviewProvaCargoId(cargoIdAlvo);
    setPreviewProvaLoading(true);
    setPreviewProvaErro(null);
    setPreviewProvaDados(null);
    try {
      const res = await api.post(`/api/export/eventos/${eventId}/preview-prova`, {
        cargo_id: cargoIdAlvo,
        variacao,
        fonte,
        tamanhoFonte,
        duasColunas,
        quebraBloco,
        manterDocx,
        senha,
        template: templateSelecionado,
        exibir_codigo_curto_questao: exibirCodigoCurto,
        exibir_gabarito_marcado: exibirGabaritoMarcado,
      }, { timeout: 300000 });
      setPreviewProvaDados(res.data);
    } catch (err: any) {
      setPreviewProvaErro(err?.response?.data?.detail || 'Não foi possível carregar o preview da prova real.');
    } finally {
      setPreviewProvaLoading(false);
    }
  };

  const abrirPreviewProvaReal = () => {
    const selecionados = cargosFiltrados.filter(c => c.selecionado);
    if (!selecionados.length) {
      setSnackbar({ open: true, message: "Selecione ao menos um cargo para pré-visualizar a prova.", severity: "warning" });
      return;
    }
    if (!senhaCorreta) {
      setSnackbar({ open: true, message: "Valide a senha do evento antes de pré-visualizar a prova real.", severity: "warning" });
      return;
    }
    setPreviewProvaOpen(true);
    carregarPreviewProvaReal(selecionados[0].id_cargo);
  };
  // Carrega cargos que têm prova montada (igual tela geração)
  useEffect(() => {
    async function fetchCargos() {
      setCarregando(true);
      try {
        const res = await api.get(`/eventos/${eventId}/cargos/provas-geracao`);
        setCargos(res.data.map((cargo: any) => ({
          id_cargo: cargo.id_cargo,
          nome_cargo: cargo.nome_cargo,
          codigo_cargo: cargo.codigo_cargo || '',
          selecionado: true,
        })));
        setSelecionarTodos(true);
      } catch {
        setSnackbar({ open: true, message: "Erro ao carregar cargos", severity: "error" });
      }
      setCarregando(false);
    }
    fetchCargos();
  }, [eventId]);

  // Carrega templates
  useEffect(() => {
    async function fetchTemplates() {
      setCarregandoTemplates(true);
      try {
        const res = await api.get(`/api/eventos/${eventId}/templates`);
        setTemplates(res.data.map((t: any) => ({
          id: t.nome_arquivo ?? t.id ?? t.nome,
          nome: t.nome_arquivo ?? t.nome ?? t.id,
          descricao: t.descricao,
          url: t.url,
          urlPreview: t.urlPreview ?? t.url,
        })));
        setTemplateSelecionado('');
      } catch {
        setSnackbar({ open: true, message: "Erro ao carregar templates", severity: "error" });
      }
      setCarregandoTemplates(false);
    }
    fetchTemplates();
  }, [eventId]);

  // Padrão de exportação do evento: apenas pré-preenche; cada exportação pode mudar tudo
  useEffect(() => {
    if (carregandoTemplates) return;
    api.get(`/api/export/eventos/${eventId}/preferencias`).then(({ data }) => {
      if (!data || typeof data !== 'object') return;
      if (typeof data.fonte === 'string') setFonte(data.fonte);
      if (typeof data.tamanhoFonte === 'number') setTamanhoFonte(data.tamanhoFonte);
      if (typeof data.duasColunas === 'boolean') setDuasColunas(data.duasColunas);
      if (typeof data.quebraBloco === 'boolean') setQuebraBloco(data.quebraBloco);
      if (typeof data.manterDocx === 'boolean') setManterDocx(data.manterDocx);
      if (typeof data.exibir_codigo_curto_questao === 'boolean') setExibirCodigoCurto(data.exibir_codigo_curto_questao);
      if (typeof data.template === 'string' && templates.some(t => t.id === data.template)) setTemplateSelecionado(data.template);
    }).catch(() => { /* sem padrão salvo: mantém os valores da tela */ });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId, carregandoTemplates]);

  const salvarPadraoEvento = async () => {
    try {
      await api.put(`/api/export/eventos/${eventId}/preferencias`, {
        fonte, tamanhoFonte, duasColunas, quebraBloco, manterDocx,
        template: templateSelecionado || null, exibir_codigo_curto_questao: exibirCodigoCurto,
      });
      setSnackbar({ open: true, message: "Padrão do evento salvo. Ele só pré-preenche a tela; você pode mudar a cada exportação.", severity: "success" });
    } catch (e: any) {
      setSnackbar({ open: true, message: e?.response?.data?.detail || "Não foi possível salvar o padrão.", severity: "error" });
    }
  };

  const handleSelecionarTodos = (evt: React.ChangeEvent<HTMLInputElement>) => {
    const checked = evt.target.checked;
    setSelecionarTodos(checked);
    setCargos(cargos.map(c => ({ ...c, selecionado: checked })));
  };

  const handleCargoChange = (idx: number) => (evt: React.ChangeEvent<HTMLInputElement>) => {
    const novos = [...cargos];
    novos[idx].selecionado = evt.target.checked;
    setCargos(novos);
    setSelecionarTodos(novos.every(c => c.selecionado));
  };

  // Filtro de cargos
  const cargosFiltrados = cargos.filter(cargo =>
    cargo.nome_cargo.toLowerCase().includes(filtroCargo.toLowerCase()) ||
    (cargo.codigo_cargo || '').toLowerCase().includes(filtroCargo.toLowerCase())
  );

  // Preview do template selecionado
  const templateAtual = templates.find(t => t.id === templateSelecionado);

  // NOVO: Exportação em lote com ZIP único
  const iniciarExportacao = async () => {
  setDialogConfirmar(false);
  setExportando(true);
  setProgresso(0);

  const cargosSelecionados = cargosFiltrados.filter(c => c.selecionado);
  if (!cargosSelecionados.length) {
    setSnackbar({ open: true, message: "Nenhum cargo selecionado!", severity: "warning" });
    setExportando(false);
    return;
  }

  try {
    setProgresso(10);
    // O segredo: responseType: 'blob'
    const response = await api.post(
      `/api/export/eventos/${eventId}/cargos/gerar-arquivos-multiplos`,
      {
        cargos_id: cargosSelecionados.map(c => c.id_cargo),
        fonte,
        tamanhoFonte,
        duasColunas,
        quebraBloco,
        manterDocx,
        senha,
        template: templateSelecionado,
        exibir_codigo_curto_questao: exibirCodigoCurto,
        exibir_gabarito_marcado: exibirGabaritoMarcado,
      },
      { responseType: 'blob' }
    );
    setProgresso(100);
    setExportando(false);

    // A API responde JSON (ex.: {"erro": ...}) quando não há o que gerar: não baixar isso como ZIP
    if (String(response.headers['content-type'] || '').includes('application/json')) {
      const info = JSON.parse(await (response.data as Blob).text());
      setSnackbar({ open: true, message: `Erro na exportação: ${info.erro || info.detail || 'resposta inesperada'}`, severity: "error" });
      return;
    }

    // Força o download do ZIP
    const blob = new Blob([response.data], { type: "application/zip" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    // a versão com gabarito marcado sai com nome próprio, para nunca ser confundida com a do candidato
    a.download = exibirGabaritoMarcado ? `Provas_${eventId}_GABARITO_MARCADO.zip` : `Provas_${eventId}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);

    const falhas = Number(response.headers['x-exportacao-falhas'] || 0);
    const avisosLote = Number(response.headers['x-exportacao-avisos'] || 0);
    if (falhas > 0) {
      setSnackbar({ open: true, message: `ZIP baixado, mas ${falhas} cargo(s) não saíram completos. Veja RELATORIO_EXPORTACAO.txt dentro do ZIP.`, severity: "warning" });
    } else if (avisosLote > 0) {
      setSnackbar({ open: true, message: `Exportação concluída com ${avisosLote} aviso(s) — listados em RELATORIO_EXPORTACAO.txt no ZIP.`, severity: "info" });
    } else {
      setSnackbar({ open: true, message: "Exportação concluída! ZIP baixado.", severity: "success" });
    }
  } catch (e: any) {
    setExportando(false);
    // Com responseType 'blob', a mensagem do servidor (ex.: senha inválida, prova vazia) vem dentro de um Blob
    let detalhe = e.message;
    try {
      const corpo = e.response?.data;
      const info = corpo instanceof Blob ? JSON.parse(await corpo.text()) : corpo;
      const det = info?.detail ?? info?.erro;
      if (det && typeof det === 'object') {
        detalhe = det.mensagem || detalhe;
        if (Array.isArray(det.verificacao)) { setVerificacao(det.verificacao); setDialogConfirmar(true); }
      } else {
        detalhe = det || detalhe;
      }
    } catch { /* mantém a mensagem genérica */ }
    setSnackbar({
      open: true,
      message: `Erro na exportação: ${detalhe}`,
      severity: "error"
    });
  }
};

  // Confirmação antes de exportar
  const handleExportar = () => {
    if (!senha.trim()) {
      setSnackbar({ open: true, message: "Digite a senha do evento!", severity: "warning" });
      return;
    }
    if (cargosFiltrados.filter(c => c.selecionado).length === 0) {
      setSnackbar({ open: true, message: "Nenhum cargo selecionado para exportação!", severity: "warning" });
      return;
    }
    setVerificando(true);
    api.post(`/api/export/eventos/${eventId}/verificar`, { cargos_id: cargosFiltrados.filter(c => c.selecionado).map(c => c.id_cargo) })
      .then(({ data }) => { setVerificacao(Array.isArray(data) ? data : []); setDialogConfirmar(true); })
      .catch((e: any) => setSnackbar({ open: true, message: e?.response?.data?.detail || "Não foi possível verificar as provas.", severity: "error" }))
      .finally(() => setVerificando(false));
  };

  return (
    <Layout>
      <Paper sx={{ p: 3 }}>
        {/* Título e botão voltar - PADRÃO DASHBOARD */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h5" fontWeight="bold">
            Exportação de Provas - Cargos do Evento
          </Typography>
          <Button variant="outlined" onClick={() => navigate(-1)}>
            Voltar
          </Button>
        </Box>

        <Divider sx={{ mb: 3 }} />

        {/* Campo para senha do evento */}
        <Box sx={{ bgcolor: "background.default", border: "1px solid", borderColor: "divider", p: 2, borderRadius: 2, mb: 3 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ sm: 'flex-start' }}>
            <TextField
              label="Senha do Evento"
              type={mostrarSenha ? "text" : "password"}
              value={senha}
              onChange={handleSenhaChange}
              onBlur={() => {
                if (senha.trim() && !senhaCorreta && !validandoSenha) {
                  validarSenhaEvento(senha);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  validarSenhaEvento(senha);
                }
              }}
              required
              size="small"
              fullWidth
              InputProps={{
                endAdornment: (
                  <IconButton
                    onClick={() => setMostrarSenha(v => !v)}
                    size="small"
                    tabIndex={-1}
                    edge="end"
                    aria-label="mostrar senha"
                  >
                    {mostrarSenha ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                )
              }}
              helperText={
                erroSenha
                  ? erroSenha
                  : senhaCorreta
                    ? "Senha validada com sucesso."
                    : "Digite a senha do evento e clique em Validar (ou pressione Enter)."
              }
              error={Boolean(erroSenha)}
            />
            <Button
              variant={senhaCorreta ? "outlined" : "contained"}
              color={senhaCorreta ? "success" : "primary"}
              onClick={() => validarSenhaEvento(senha)}
              disabled={!senha.trim() || validandoSenha}
              sx={{ minWidth: 136, height: 40, flexShrink: 0 }}
            >
              {validandoSenha ? "Validando..." : senhaCorreta ? "Validada" : "Validar Senha"}
            </Button>
          </Stack>
        </Box>

        {/* 1. Seleção de Cargos */}
        <Box sx={{ bgcolor: "background.default", border: "1px solid", borderColor: "divider", p: 2, borderRadius: 2, mb: 3 }}>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <AssignmentIndIcon color="action" />
            <Typography variant="h6">1. Seleção de Cargos</Typography>
          </Box>
          <Box display="flex" alignItems="flex-end" justifyContent="space-between" flexWrap="wrap" sx={{ mb: 2 }}>
            <Tooltip title="Selecione para buscar um cargo específico">
              <TextField
                label="Buscar cargo"
                variant="outlined"
                size="small"
                sx={{ maxWidth: 260, mb: { xs: 1, sm: 0 } }}
                InputProps={{ endAdornment: <SearchIcon fontSize="small" color="disabled" /> }}
                onChange={e => setFiltroCargo(e.target.value)}
              />
            </Tooltip>
            <Tooltip title="Selecionar todos os cargos disponíveis para exportação">
              <FormControlLabel
                control={<Checkbox checked={selecionarTodos} onChange={handleSelecionarTodos} disabled={carregando || cargosFiltrados.length === 0} />}
                label="Marcar/Desmarcar Todos"
              />
            </Tooltip>
            <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
              {cargosFiltrados.filter(c => c.selecionado).length} de {cargosFiltrados.length} cargos exibidos selecionados
            </Typography>
          </Box>
          {carregando ? (
            <Box sx={{ display: "flex", justifyContent: "center", p: 2 }}>
              <CircularProgress />
            </Box>
          ) : cargosFiltrados.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
              Nenhum cargo com prova montada disponível para exportação encontrado.
            </Typography>
          ) : (
            <List dense sx={{ maxHeight: 250, overflow: 'auto', background: "rgba(6, 11, 25, 0.65)", borderRadius: 1 }}>
              {cargosFiltrados.map((cargo, idx) => (
                <ListItem key={cargo.id_cargo} disablePadding>
                  <ListItemIcon>
                    <Checkbox
                      checked={cargo.selecionado}
                      onChange={handleCargoChange(cargos.indexOf(cargo))}
                      disabled={carregando}
                    />
                  </ListItemIcon>
                  <ListItemText
                    primary={<span><b>{cargo.codigo_cargo && `${cargo.codigo_cargo} - `}{cargo.nome_cargo}</b></span>}
                  />
                </ListItem>
              ))}
            </List>
          )}
        </Box>

        {/* 2. Escolha de Template */}
        <Box sx={{ bgcolor: "background.default", border: "1px solid", borderColor: "divider", p: 2, borderRadius: 2, mb: 3 }}>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <DescriptionIcon color="secondary" />
            <Typography variant="h6">2. Template</Typography>
          </Box>
          <Stack direction="row" spacing={2} alignItems="center">
            <FormControl sx={{ minWidth: 240 }} size="small" disabled={carregandoTemplates}>
              <InputLabel id="template-label">Template</InputLabel>
              <Select
                labelId="template-label"
                value={templateSelecionado}
                label="Template"
                onChange={e => setTemplateSelecionado(e.target.value as string)}
              >
                <MenuItem value="">
                  <em>Padrão do sistema</em>
                </MenuItem>
                {templates.map(t => (
                  <MenuItem key={t.id} value={t.id}>{t.nome}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <Tooltip title={templateSelecionado === "" ? "Visualizar template padrão do sistema" : "Visualizar detalhes do template selecionado"}>
              <span>
                <Button
                  size="small"
                  startIcon={<PreviewIcon />}
                  onClick={abrirPreviewTemplate}
                  variant="outlined"
                >
                  Preview
                </Button>
              </span>
            </Tooltip>
            {templateAtual?.descricao && templateSelecionado !== "" && (
              <Tooltip title={templateAtual.descricao}>
                <InfoOutlinedIcon color="action" sx={{ ml: 1 }} />
              </Tooltip>
            )}
            {templateSelecionado === "" && (
              <Tooltip title="Template padrão do sistema será utilizado">
                <InfoOutlinedIcon color="action" sx={{ ml: 1 }} />
              </Tooltip>
            )}
          </Stack>
        </Box>

        {/* 3. Opções de Formatação e Saída */}
        <Box sx={{ bgcolor: "background.default", border: "1px solid", borderColor: "divider", p: 2, borderRadius: 2, mb: 3 }}>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <SettingsIcon color="action" />
            <Typography variant="h6">3. Opções de Formatação e Saída</Typography>
          </Box>
          <Stack spacing={2}>
            <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
              <Tooltip title="Tamanho da fonte utilizada na exportação">
                <FormControl size="small" sx={{ minWidth: 80 }}>
                  <InputLabel id="tamanho-fonte-label">Tamanho</InputLabel>
                  <Select
                    labelId="tamanho-fonte-label"
                    value={tamanhoFonte}
                    label="Tamanho"
                    onChange={e => setTamanhoFonte(Number(e.target.value))}
                  >
                    {tamanhosFonte.map(t => <MenuItem key={t} value={t}>{t}</MenuItem>)}
                  </Select>
                </FormControl>
              </Tooltip>
              <Tooltip title="Fonte utilizada na exportação">
                <FormControl size="small" sx={{ minWidth: 130 }}>
                  <InputLabel id="fonte-label">Fonte</InputLabel>
                  <Select
                    labelId="fonte-label"
                    value={fonte}
                    label="Fonte"
                    onChange={e => setFonte(e.target.value)}
                  >
                    {fontes.map(f => <MenuItem key={f} value={f}>{f}</MenuItem>)}
                  </Select>
                </FormControl>
              </Tooltip>
              <Tooltip title="Exportar as provas em duas colunas">
                <FormControlLabel
                  control={<Checkbox checked={duasColunas} onChange={e => setDuasColunas(e.target.checked)} />}
                  label="Duas Colunas"
                />
              </Tooltip>
              <Tooltip title="Separar as disciplinas em blocos distintos">
                <FormControlLabel
                  control={<Checkbox checked={quebraBloco} onChange={e => setQuebraBloco(e.target.checked)} />}
                  label="Quebra de bloco entre disciplinas"
                />
              </Tooltip>
            </Stack>
            <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
              <Tooltip title="Manter também o arquivo DOCX gerado">
                <FormControlLabel
                  control={<Checkbox checked={manterDocx} onChange={e => setManterDocx(e.target.checked)} />}
                  label="Manter arquivos DOCX"
                />
              </Tooltip>
              <Tooltip title="Exibir código curto da questão na prova">
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={exibirCodigoCurto}
                      onChange={e => setExibirCodigoCurto(e.target.checked)}
                    />
                  }
                  label="Exibir código curto da questão"
                />
              </Tooltip>
              <Tooltip title="Exibir letra do gabarito marcada ao lado da alternativa correta">
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={exibirGabaritoMarcado}
                      onChange={e => setExibirGabaritoMarcado(e.target.checked)}
                    />
                  }
                  label="Exibir gabarito marcado"
                />
              </Tooltip>
            </Stack>
          </Stack>
        </Box>

        {/* Barra de progresso da exportação */}
        {exportando && (
          <Box sx={{ mb: 2 }}>
            <LinearProgress variant="determinate" value={progresso} />
            <Typography variant="body2" color="text.secondary" align="right" sx={{ mt: 0.5 }}>
              Exportando... {Math.round(progresso)}%
            </Typography>
          </Box>
        )}

        {/* Botões de ação */}
        <Stack direction="row" spacing={2} justifyContent="flex-end" alignItems="center" flexWrap="wrap" useFlexGap>
          <Button
            variant="outlined"
            size="large"
            startIcon={<PreviewIcon />}
            onClick={abrirPreviewProvaReal}
            disabled={
              carregando ||
              !senhaCorreta ||
              cargosFiltrados.filter(c => c.selecionado).length === 0 ||
              exportando || verificando
            }
          >
            Pré-visualizar Prova Real
          </Button>
          <Button
            variant="contained"
            size="large"
            startIcon={<DownloadIcon />}
            onClick={handleExportar}
            disabled={
                carregando ||
                !senhaCorreta || // <-- só libera se senha bater!
                cargosFiltrados.filter(c => c.selecionado).length === 0 ||
                exportando || verificando
            }
            sx={{ fontWeight: "bold" }}
            >
            {verificando ? "Verificando provas..." : "Exportar Selecionados"}
            </Button>
          <Tooltip title="Guarda fonte, tamanho, colunas e template como sugestão para as próximas exportações deste evento. Tudo continua podendo ser mudado a cada exportação.">
            <span>
              <Button variant="outlined" size="large" onClick={salvarPadraoEvento} disabled={carregando || exportando}>
                Salvar como padrão do evento
              </Button>
            </span>
          </Tooltip>
          <Button
            variant="outlined"
            size="large"
            color="error"
            onClick={() => navigate(-1)}
            disabled={carregando || exportando}
          >
            Sair
          </Button>
        </Stack>

        <EntregaPorLink
          eventId={eventId || ''}
          habilitado={!carregando && senhaCorreta && !exportando && cargosFiltrados.filter(c => c.selecionado).length > 0}
          gabaritoMarcado={exibirGabaritoMarcado}
          corpo={() => ({
            cargos_id: cargosFiltrados.filter(c => c.selecionado).map(c => c.id_cargo),
            fonte, tamanhoFonte, duasColunas, quebraBloco, manterDocx, senha,
            template: templateSelecionado,
            exibir_codigo_curto_questao: exibirCodigoCurto,
            exibir_gabarito_marcado: exibirGabaritoMarcado,
          })}
        />

        {/* Snackbar feedback */}
        <Snackbar open={snackbar.open} autoHideDuration={3500} onClose={() => setSnackbar({ ...snackbar, open: false })}>
          <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
        </Snackbar>

        {/* Dialog de preview do template */}
        <Dialog open={previewTemplateOpen} onClose={fecharPreviewTemplate} maxWidth="md" fullWidth>
          <DialogTitle>
            Preview do Template — {templateSelecionado === "" ? "Padrão do Sistema" : (templateAtual?.nome || templateSelecionado)}
          </DialogTitle>
          <DialogContent dividers>
            {templateSelecionado !== "" ? (
              previewLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 260, gap: 1.5 }}>
                  <CircularProgress size={22} />
                  <Typography variant="body2" color="text.secondary">Montando a página como sai na prova...</Typography>
                </Box>
              ) : previewImagem ? (
                <Box>
                  <Box component="img" src={previewImagem} alt={`Página do template ${templateAtual?.nome || templateSelecionado} como sai na prova`}
                    draggable={false} onContextMenu={(e: React.MouseEvent) => e.preventDefault()}
                    sx={{ display: 'block', width: '100%', maxWidth: 640, mx: 'auto', bgcolor: '#fff', boxShadow: 3, borderRadius: 1 }} />
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 1.5 }}>
                    Cabeçalho e rodapé como na exportação, com valores de exemplo (nome do concurso, cargo e página).
                    Para ver com as questões, use "Pré-visualizar Prova Real".
                  </Typography>
                </Box>
              ) : previewErro ? (
                <Alert severity="warning">{previewErro}</Alert>
              ) : previewPartes.headerHtml || previewPartes.bodyHtml || previewPartes.footerHtml ? (
                <Box
                  sx={{
                    bgcolor: '#FFFFFF',
                    color: '#0F172A',
                    p: { xs: 2.5, md: 4 },
                    borderRadius: 2,
                    minHeight: 380,
                    maxHeight: 500,
                    overflowY: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: 2.5,
                    fontFamily: fonte,
                    fontSize: `${tamanhoFonte}pt`,
                    boxShadow: 'inset 0 0 0 1px rgba(15, 23, 42, 0.12)',
                  }}
                >
                  {previewPartes.headerHtml && (
                    <Box
                      sx={{
                        borderBottom: '1px dashed #CBD5E1',
                        pb: 1.5,
                        '& img': { maxWidth: '100%', height: 'auto' },
                      }}
                      dangerouslySetInnerHTML={{ __html: previewPartes.headerHtml }}
                    />
                  )}
                  <Box sx={{ flexGrow: 1 }}>
                    {previewPartes.bodyHtml ? (
                      <Box dangerouslySetInnerHTML={{ __html: previewPartes.bodyHtml }} />
                    ) : (
                      <Box sx={{ py: 2, color: '#475569', fontSize: '0.88rem' }}>
                        <Typography sx={{ fontWeight: 700, mb: 0.75, color: '#0F172A', fontSize: '0.92rem' }}>
                          [Área onde as questões da prova serão inseridas]
                        </Typography>
                        <Typography sx={{ fontSize: '0.82rem', color: '#64748B' }}>
                          Fonte: {fonte} ({tamanhoFonte} pt) • {duasColunas ? '2 Colunas' : '1 Coluna'} • {quebraBloco ? 'Quebra por disciplina' : 'Fluxo contínuo'}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                  {previewPartes.footerHtml && (
                    <Box
                      sx={{
                        borderTop: '1px dashed #CBD5E1',
                        pt: 1.5,
                        '& img': { maxWidth: '100%', height: 'auto' },
                      }}
                      dangerouslySetInnerHTML={{ __html: previewPartes.footerHtml }}
                    />
                  )}
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Este template está vazio ou não possui conteúdo textual visível no preview.
                </Typography>
              )
            ) : (
              <Box>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Prévia esquemática do layout padrão institucional com as configurações atuais:
                </Typography>
                <Box
                  sx={{
                    bgcolor: '#FFFFFF',
                    color: '#0F172A',
                    p: { xs: 2.5, md: 3.5 },
                    borderRadius: 2,
                    fontFamily: fonte,
                    fontSize: `${Math.max(11, tamanhoFonte)}px`,
                    boxShadow: 'inset 0 0 0 1px rgba(15, 23, 42, 0.12)',
                  }}
                >
                  {exibirGabaritoMarcado && (
                    <Box sx={{ bgcolor: '#FEE2E2', color: '#991B1B', px: 1.5, py: 0.6, borderRadius: 1, mb: 2, fontWeight: 700, fontSize: '0.78rem', textAlign: 'center' }}>
                      USO INTERNO — VERSÃO COM GABARITO MARCADO
                    </Box>
                  )}
                  <Box sx={{ borderBottom: '2px solid #0F172A', pb: 1.25, mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                      <Typography sx={{ fontWeight: 800, fontSize: '1rem', color: '#0F172A', fontFamily: 'inherit' }}>
                        CADERNO DE PROVA OBJETIVA
                      </Typography>
                      <Typography sx={{ fontSize: '0.78rem', color: '#475569', fontFamily: 'inherit' }}>
                        Fonte: {fonte} ({tamanhoFonte} pt) • {duasColunas ? '2 Colunas' : '1 Coluna'} • {quebraBloco ? 'Com quebra por disciplina' : 'Fluxo contínuo'}
                      </Typography>
                    </Box>
                    <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: '#334155', fontFamily: 'inherit' }}>
                      TIPO A
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      display: 'grid',
                      gridTemplateColumns: duasColunas ? '1fr 1fr' : '1fr',
                      gap: 2.5,
                    }}
                  >
                    <Box>
                      <Typography sx={{ fontWeight: 700, mb: 0.75, fontSize: 'inherit', fontFamily: 'inherit' }}>
                        BLOCO I — LÍNGUA PORTUGUESA
                      </Typography>
                      <Typography sx={{ mb: 0.75, fontSize: 'inherit', fontFamily: 'inherit' }}>
                        <b>QUESTÃO 01</b> {exibirCodigoCurto ? '[Q-LP001]' : ''} — Assinale a alternativa correta quanto à regência verbal segundo a norma-padrão.
                      </Typography>
                      <Typography sx={{ fontSize: '0.88em', color: '#334155', fontFamily: 'inherit' }}>
                        (A) Alternativa exemplo A {exibirGabaritoMarcado ? '← [GABARITO]' : ''}
                      </Typography>
                      <Typography sx={{ fontSize: '0.88em', color: '#334155', fontFamily: 'inherit' }}>
                        (B) Alternativa exemplo B
                      </Typography>
                    </Box>
                    <Box>
                      <Typography sx={{ fontWeight: 700, mb: 0.75, fontSize: 'inherit', fontFamily: 'inherit' }}>
                        {quebraBloco ? 'BLOCO II — CONHECIMENTOS ESPECÍFICOS (nova seção)' : 'QUESTÃO 02'}
                      </Typography>
                      <Typography sx={{ mb: 0.75, fontSize: 'inherit', fontFamily: 'inherit' }}>
                        <b>QUESTÃO 02</b> {exibirCodigoCurto ? '[Q-CE002]' : ''} — Julgue os itens subsequentes considerando os princípios da administração pública.
                      </Typography>
                      <Typography sx={{ fontSize: '0.88em', color: '#334155', fontFamily: 'inherit' }}>
                        (A) Alternativa exemplo A • (B) Alternativa exemplo B
                      </Typography>
                    </Box>
                  </Box>
                </Box>
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={fecharPreviewTemplate} variant="contained">
              Fechar
            </Button>
          </DialogActions>
        </Dialog>

        {/* Dialog de preview da prova real */}
        <Dialog open={previewProvaOpen} onClose={() => setPreviewProvaOpen(false)} maxWidth="lg" fullWidth>
          <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
            <Box>
              <Typography variant="h6" fontWeight={700}>
                Pré-visualização da prova real
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {previewProvaDados
                  ? `${previewProvaDados.cargo?.codigo_cargo ? previewProvaDados.cargo.codigo_cargo + ' - ' : ''}${previewProvaDados.cargo?.nome_cargo} • ${previewProvaDados.tipo} • ${previewProvaDados.total_paginas} página(s) • idêntica à exportação`
                  : `Fonte ${fonte} ${tamanhoFonte}pt • ${duasColunas ? '2 colunas' : '1 coluna'}`}
              </Typography>
            </Box>
            {previewProvaDados && previewProvaDados.num_variacoes > 1 && (
              <ToggleButtonGroup size="small" exclusive value={previewProvaDados.variacao}
                onChange={(_, v) => v && carregarPreviewProvaReal(previewProvaCargoId, v)}>
                {Array.from({ length: previewProvaDados.num_variacoes }, (_, i) => (
                  <ToggleButton key={i + 1} value={i + 1}>Tipo {String.fromCharCode(65 + i)}</ToggleButton>
                ))}
              </ToggleButtonGroup>
            )}
            {cargosFiltrados.filter(c => c.selecionado).length > 1 && (
              <FormControl size="small" sx={{ minWidth: 240 }}>
                <InputLabel id="preview-cargo-label">Cargo</InputLabel>
                <Select
                  labelId="preview-cargo-label"
                  value={previewProvaCargoId}
                  label="Cargo"
                  onChange={(e) => carregarPreviewProvaReal(String(e.target.value), 1)}
                >
                  {cargosFiltrados.filter(c => c.selecionado).map((c) => (
                    <MenuItem key={c.id_cargo} value={c.id_cargo}>
                      {c.codigo_cargo ? `${c.codigo_cargo} - ` : ''}{c.nome_cargo}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
          </DialogTitle>
          <DialogContent dividers sx={{ bgcolor: '#0B1325' }}>
            {previewProvaLoading ? (
              <Stack alignItems="center" justifyContent="center" spacing={1.5} sx={{ minHeight: 320 }}>
                <CircularProgress size={28} />
                <Typography variant="body2" color="text.secondary">Gerando a prova exatamente como na exportação…</Typography>
                <Typography variant="caption" color="text.secondary">Pode levar até 1 minuto (diagramação e PDF reais).</Typography>
              </Stack>
            ) : previewProvaErro ? (
              <Alert severity="error">{typeof previewProvaErro === 'string' ? previewProvaErro : 'Não foi possível gerar a pré-visualização.'}</Alert>
            ) : previewProvaDados ? (
              <Stack spacing={2.5} alignItems="center">
                {(previewProvaDados.bloqueios > 0 || previewProvaDados.avisos > 0) && (
                  <Alert severity={previewProvaDados.bloqueios > 0 ? 'error' : 'warning'} sx={{ width: '100%', maxWidth: 860 }}>
                    {previewProvaDados.bloqueios > 0
                      ? `A checagem encontrou ${previewProvaDados.bloqueios} problema(s) que bloqueiam a exportação. Use "Verificar" para ver quais.`
                      : `A checagem encontrou ${previewProvaDados.avisos} aviso(s). A exportação é permitida.`}
                  </Alert>
                )}
                {(previewProvaDados.paginas || []).map((src: string, i: number) => (
                  <Box key={i} sx={{ width: '100%', maxWidth: 860 }}>
                    <Box component="img" src={src} alt={`Página ${i + 1} da prova`} draggable={false}
                      onContextMenu={(e: React.MouseEvent) => e.preventDefault()}
                      sx={{ width: '100%', display: 'block', bgcolor: '#fff', boxShadow: '0 12px 40px rgba(0, 0, 0, 0.45)', userSelect: 'none' }} />
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 0.75 }}>
                      Página {i + 1} de {previewProvaDados.total_paginas}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            ) : null}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setPreviewProvaOpen(false)} variant="contained">
              Fechar
            </Button>
          </DialogActions>
        </Dialog>

        {/* Dialog de confirmação da exportação */}
        <Dialog open={dialogConfirmar} onClose={() => setDialogConfirmar(false)}>
          <DialogTitle>Confirmar Exportação</DialogTitle>
          <DialogContent dividers>
            <Typography variant="subtitle1" mb={2}>Resumo da exportação:</Typography>
            <Typography variant="body2">
              <b>Cargos selecionados:</b> {cargosFiltrados.filter(c => c.selecionado).map(c => c.nome_cargo).join(", ") || "Nenhum"}
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <b>Template:</b> {templateSelecionado === "" ? "Padrão do sistema" : (templateAtual?.nome || "Nenhum")}
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <b>Fonte:</b> {fonte}, <b>Tamanho:</b> {tamanhoFonte}
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <b>Duas Colunas:</b> {duasColunas ? "Sim" : "Não"}, <b>Quebra Bloco:</b> {quebraBloco ? "Sim" : "Não"}
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <b>Manter DOCX:</b> {manterDocx ? "Sim" : "Não"}
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              <b>Exportação:</b> sempre em ZIP (opção padrão do sistema)
            </Typography>
            {exibirGabaritoMarcado && (
              <Alert severity="error" sx={{ mt: 2 }}>
                Versão COM GABARITO MARCADO: uso interno. Os arquivos sairão identificados e com aviso no cabeçalho de todas as páginas.
              </Alert>
            )}
            {verificacao && (
              <Box sx={{ mt: 2 }}>
                {totalBloqueios === 0 && totalAvisos === 0 && (
                  <Alert severity="success">Checagem concluída: nenhum problema encontrado.</Alert>
                )}
                {totalBloqueios > 0 && (
                  <Alert severity="error" sx={{ mb: 1 }}>
                    {totalBloqueios} problema(s) deixariam a prova errada. Corrija antes de exportar.
                  </Alert>
                )}
                {totalBloqueios === 0 && totalAvisos > 0 && (
                  <Alert severity="warning" sx={{ mb: 1 }}>
                    {totalAvisos} aviso(s). A prova pode ser exportada, mas confira.
                  </Alert>
                )}
                {verificacao.filter(v => v.bloqueios.length || v.avisos.length || v.avisos_gerais.length).map(v => (
                  <Box key={v.id_cargo} sx={{ mb: 1.5 }}>
                    <Typography variant="subtitle2" fontWeight="bold">{v.cargo} — {v.total_questoes} questão(ões)</Typography>
                    {v.avisos_gerais.map((a, i) => (
                      <Typography key={`g${i}`} variant="body2" color="warning.main">• {a}</Typography>
                    ))}
                    {v.bloqueios.map((p, i) => (
                      <Typography key={`b${i}`} variant="body2" color="error.main">
                        • {p.questao ? `Questão ${p.questao} (${p.codigo})${p.disciplina ? ` — ${p.disciplina}` : ''}: ` : ''}{p.problema}
                      </Typography>
                    ))}
                    {v.avisos.map((p, i) => (
                      <Typography key={`a${i}`} variant="body2" color="warning.main">
                        • Questão {p.questao} ({p.codigo}){p.disciplina ? ` — ${p.disciplina}` : ''}: {p.problema}
                      </Typography>
                    ))}
                  </Box>
                ))}
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogConfirmar(false)}>Voltar</Button>
            <Button
              onClick={iniciarExportacao}
              variant="contained"
              color={totalAvisos > 0 ? "warning" : "primary"}
              disabled={exportando || totalBloqueios > 0}
            >
              {totalBloqueios > 0 ? "Corrija os problemas" : totalAvisos > 0 ? "Exportar mesmo assim" : "Confirmar Exportação"}
            </Button>
          </DialogActions>
        </Dialog>
      </Paper>
    </Layout>
  );
};

export default ExportacaoProvaPage;