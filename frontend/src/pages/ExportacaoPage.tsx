import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Paper, Divider, Button, List, ListItem, ListItemIcon, ListItemText,
  Checkbox, Snackbar, Alert, CircularProgress, Tooltip, Stack, FormControlLabel,
  Select, MenuItem, InputLabel, FormControl, TextField, LinearProgress, Dialog, DialogTitle, DialogContent, DialogActions, IconButton
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
  

  // Barra de progresso da exportação
  const [exportando, setExportando] = useState(false);
  const [progresso, setProgresso] = useState(0);

  // Dialog de confirmação
  const [dialogConfirmar, setDialogConfirmar] = useState(false);

  // Snackbar feedback
  const [snackbar, setSnackbar] = useState<{ open: boolean, message: string, severity: "success" | "error" | "info" | "warning" }>(
    { open: false, message: '', severity: "success" }
  );

  
    const validarSenhaEvento = async (senhaDigitada: string) => {
        try {
            const resp = await api.post(`/api/export/eventos/${eventId}/validar-senha`, { senha: senhaDigitada });
            setSenhaCorreta(resp.data && resp.data.valida === true);
        } catch {
            setSenhaCorreta(false);
        }
        };

        const handleSenhaChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const valor = e.target.value;
        setSenha(valor);
        if (valor.length > 0) {
            await validarSenhaEvento(valor);
        } else {
            setSenhaCorreta(false);
        }
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

    // Força o download do ZIP
    const blob = new Blob([response.data], { type: "application/zip" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Provas_${eventId}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);

    setSnackbar({ open: true, message: "Exportação concluída! ZIP baixado.", severity: "success" });
  } catch (e: any) {
    setExportando(false);
    setSnackbar({
      open: true,
      message: `Erro na exportação: ${(e.response?.data?.detail || e.message)}`,
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
    setDialogConfirmar(true);
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
          <TextField
            label="Senha do Evento"
                type={mostrarSenha ? "text" : "password"}
                value={senha}
                onChange={handleSenhaChange}
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
                helperText={senha && !senhaCorreta ? "Senha incorreta!" : ""}
                error={senha.length > 0 && !senhaCorreta}
                />
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
                  onClick={() => setPreviewTemplateOpen(true)}
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
        <Stack direction="row" spacing={2} justifyContent="flex-end" alignItems="center">
          <Button
            variant="contained"
            size="large"
            startIcon={<DownloadIcon />}
            onClick={handleExportar}
            disabled={
                carregando ||
                !senhaCorreta || // <-- só libera se senha bater!
                cargosFiltrados.filter(c => c.selecionado).length === 0 ||
                exportando
            }
            sx={{ fontWeight: "bold" }}
            >
            Exportar Selecionados
            </Button>
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

        {/* Snackbar feedback */}
        <Snackbar open={snackbar.open} autoHideDuration={3500} onClose={() => setSnackbar({ ...snackbar, open: false })}>
          <Alert severity={snackbar.severity}>{snackbar.message}</Alert>
        </Snackbar>

        {/* Dialog de preview do template */}
        <Dialog open={previewTemplateOpen} onClose={() => setPreviewTemplateOpen(false)} maxWidth="md" fullWidth>
          <DialogTitle>Preview do Template</DialogTitle>
          <DialogContent dividers>
            {templateSelecionado !== "" && templateAtual?.urlPreview ? (
              <iframe
                src={templateAtual.urlPreview}
                title="Preview do Template"
                style={{ width: "100%", height: "450px", border: 0 }}
              />
            ) : (
              <Typography variant="body2">
                {templateSelecionado === ""
                  ? "O template padrão do sistema será utilizado para a exportação."
                  : "Sem preview disponível para este template."}
              </Typography>
            )}
            {templateSelecionado !== "" && templateAtual?.descricao && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                {templateAtual.descricao}
              </Typography>
            )}
            {templateSelecionado === "" && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                Template padrão do sistema: layout básico e institucional.
              </Typography>
            )}
          </DialogContent>
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
          </DialogContent>
          <DialogActions>
            <Button
              onClick={iniciarExportacao}
              variant="contained"
              color="primary"
              disabled={exportando}
            >
              Confirmar Exportação
            </Button>
          </DialogActions>
        </Dialog>
      </Paper>
    </Layout>
  );
};

export default ExportacaoProvaPage;