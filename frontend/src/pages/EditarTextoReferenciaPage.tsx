import { useState, useRef, useEffect } from "react";
import {
  Box,
  Button,
  Typography,
  Divider,
  Paper,
  Alert,
  Snackbar,
  Tooltip,
  Autocomplete,
  Chip,
  Checkbox,
  FormControlLabel,
  CircularProgress,
  TextField,
} from "@mui/material";
import { useParams, useNavigate } from "react-router-dom";
import api from "../api";
import Layout from "../components/Layout";
import { useAuth } from "../contexts/AuthContext";
import CampoComEditorAvancado from "../components/CampoComEditorAvancado";
import ImagemPreview from "../components/ImagemPreview";

const TIPO_CONTEUDO = [
  { value: "texto", label: "Texto" },
  { value: "imagem", label: "Imagem" },
];

const LICENCAS = [
  { value: "", label: "Selecione" },
  { value: "livre", label: "Livre" },
  { value: "CC-BY", label: "CC-BY" },
  { value: "copyright", label: "Copyright" },
];

const SUGESTAO_TAGS = [
  "gráfico",
  "tabela",
  "mapa",
  "figura",
  "fotografia",
  "diagrama",
];

// Remove HTML tags for display
function stripHtml(html: string) {
  return html.replace(/<[^>]*>?/gm, "");
}

export default function EditarTextoReferenciaPage() {
  const { user } = useAuth();
  const tenantId = user?.tenant_id;
  const { eventId, id_conteudo, id_texto_ref } = useParams();
  const navigate = useNavigate();
  const tituloRef = useRef<any>(null);

  // Array com todas as questões reais para autocomplete
  const [todasQuestoes, setTodasQuestoes] = useState<any[]>([]);

  const [form, setForm] = useState({
    titulo: "",
    tipo_conteudo: "texto" as "texto" | "imagem",
    legenda_texto: "",
    conteudo: "",
    descricao_imagem: "",
    fonte_imagem: "",
    tags_imagem: [] as string[],
    licenca_imagem: "",
    metadados_texto_ref: "",
    imagemFile: null as File | null,
    observacoes: "",
    observacoes_imagem: "",
    ativo: true,
    publico: true,
    questoes_vinculo: [] as string[], // lista de ids
  });

  const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
  const [imagemPreview, setImagemPreview] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: "",
    severity: "success" as "success" | "error" | "warning" | "info",
  });
  const [sending, setSending] = useState(false);
  

  // Buscar todas as questões do conteúdo/evento
  useEffect(() => {
    async function fetchQuestoes() {
      try {
        const res = await api.get(
          `/eventos/${eventId}/conteudos/${id_conteudo}/questoes`
        );
        setTodasQuestoes(res.data ?? []);
      } catch {
        setTodasQuestoes([]);
      }
    }
    if (eventId && id_conteudo) fetchQuestoes();
  }, [eventId, id_conteudo]);

  // Carregar texto de referência e preencher todos os campos do form
  useEffect(() => {
    async function fetchTextoReferencia() {
      try {
        const res = await api.get(
          `/eventos/${eventId}/conteudos/${id_conteudo}/textos-referencia/${id_texto_ref}`
        );
        const texto = res.data;
        setForm({
          titulo: texto.titulo || "",
          tipo_conteudo: texto.tipo_conteudo || "texto",
          legenda_texto: texto.legenda_texto || "",
          conteudo: texto.conteudo || "",
          descricao_imagem: texto.descricao_imagem || "",
          fonte_imagem: texto.fonte_imagem || "",
          tags_imagem: texto.tags_imagem || [],
          licenca_imagem: texto.licenca_imagem || "",
          metadados_texto_ref: texto.metadados_texto_ref
            ? JSON.stringify(texto.metadados_texto_ref)
            : "",
          imagemFile: null,
          observacoes: texto.observacoes || "",
          observacoes_imagem: texto.observacoes_imagem || "",
          ativo: texto.ativo ?? true,
          publico: texto.publico ?? true,
          questoes_vinculo:
            Array.isArray(texto.questoes_vinculo)
              ? texto.questoes_vinculo
              : texto.questoes_vinculo
              ? texto.questoes_vinculo.split(",").map((id: string) => id.trim())
              : [],
        });
        if (texto.caminho_imagem_relativo) {
          setImagemPreview(`${API_BASE_URL}/${texto.caminho_imagem_relativo}`);
        }
      } catch (err) {
        setSnackbar({
          open: true,
          message: "Erro ao carregar texto de referência.",
          severity: "error",
        });
      }
    }
    fetchTextoReferencia();
  }, [eventId, id_conteudo, id_texto_ref, API_BASE_URL]);

  useEffect(() => {
    if (tituloRef.current && typeof tituloRef.current.focus === "function") {
      tituloRef.current.focus();
    }
  }, []);

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith("image/")) {
      handleImagemFile(file);
    }
  }

  function handleImagemUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleImagemFile(file);
  }

  function handleImagemFile(file: File) {
    if (file.size > 5 * 1024 * 1024) {
      setFieldErrors((prev) => ({
        ...prev,
        imagemFile: "Imagem excede 5MB.",
      }));
      return;
    }
    setFieldErrors((prev) => ({ ...prev, imagemFile: "" }));
    setForm((prev) => ({ ...prev, imagemFile: file }));
    const reader = new FileReader();
    reader.onloadend = () => setImagemPreview(reader.result as string);
    reader.readAsDataURL(file);
  }

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!form.titulo.trim() || form.titulo === "<p></p>")
      errors.titulo = "Título é obrigatório.";
    if (form.tipo_conteudo === "texto") {
      if (!form.conteudo.trim() || form.conteudo === "<p></p>")
        errors.conteudo = "Conteúdo do texto é obrigatório.";
      if (!form.legenda_texto.trim() || form.legenda_texto === "<p></p>")
        errors.legenda_texto = "Legenda é obrigatória.";
    }
    if (form.tipo_conteudo === "imagem") {
      if (!form.descricao_imagem.trim() || form.descricao_imagem === "<p></p>")
        errors.descricao_imagem = "Descrição é obrigatória.";
      if (!form.fonte_imagem.trim() || form.fonte_imagem === "<p></p>")
        errors.fonte_imagem = "Fonte é obrigatória.";
      if (!form.imagemFile && !imagemPreview)
        errors.imagemFile = "Selecione uma imagem.";
      if (form.imagemFile && form.imagemFile.size > 5 * 1024 * 1024)
        errors.imagemFile = "Imagem excede 5MB.";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSending(true);

    if (!tenantId) {
      setSnackbar({
        open: true,
        message: "Tenant não encontrado. Faça login novamente.",
        severity: "error",
      });
      setSending(false);
      return;
    }

    if (!validate()) {
      setSending(false);
      return;
    }

    let metadadosObj = undefined;
    if (form.metadados_texto_ref.trim()) {
      try {
        metadadosObj = JSON.parse(form.metadados_texto_ref);
      } catch {
        setFieldErrors((prev) => ({
          ...prev,
          metadados_texto_ref: "Metadados devem ser JSON válido.",
        }));
        setSending(false);
        return;
      }
    }

    try {
      const formData = new FormData();
      formData.append("titulo", form.titulo ?? "");
      formData.append("tipo_conteudo", form.tipo_conteudo ?? "texto");
      formData.append("tenant_id", String(tenantId ?? ""));
      formData.append("evento_id", eventId ?? "");
      formData.append("conteudo_id", id_conteudo ?? "");
      formData.append("legenda_texto", form.legenda_texto ?? "");
      formData.append("conteudo", form.conteudo ?? "");
      formData.append("descricao_imagem", form.descricao_imagem ?? "");
      formData.append("fonte_imagem", form.fonte_imagem ?? "");
      formData.append("licenca_imagem", form.licenca_imagem ?? "");
      formData.append("tags_imagem", form.tags_imagem?.join(",") ?? "");
      formData.append("observacoes", form.observacoes ?? "");
      formData.append("observacoes_imagem", form.observacoes_imagem ?? "");
      formData.append("ativo", form.ativo ? "true" : "false");
      formData.append("publico", form.publico ? "true" : "false");
      formData.append("questoes_vinculo", form.questoes_vinculo?.join(",") ?? "");
      if (metadadosObj)
        formData.append("metadados_texto_ref", JSON.stringify(metadadosObj));
      if (form.imagemFile) formData.append("imagem", form.imagemFile);

      await api.patch(
        `/eventos/${eventId}/conteudos/${id_conteudo}/textos-referencia/${id_texto_ref}`,
        formData
      );

      setSnackbar({
        open: true,
        message: "Texto de referência editado com sucesso!",
        severity: "success",
      });
      setSending(false);
      navigate(-1);
    } catch (err: any) {
      let msg = "Erro ao editar texto de referência.";
      if (err.response?.data?.detail) {
        msg =
          typeof err.response.data.detail === "string"
            ? err.response.data.detail
            : JSON.stringify(err.response.data.detail);
      }
      setSnackbar({ open: true, message: msg, severity: "error" });
      setSending(false);
    }
  }

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: 2,
          }}
        >
          <Typography variant="h5" fontWeight="bold" gutterBottom>
            Editar Texto de Referência
          </Typography>
          <Button
            variant="outlined"
            color="primary"
            onClick={() => navigate(-1)}
            tabIndex={-1}
          >
            Voltar
          </Button>
        </Box>
        <Divider sx={{ mb: 2 }} />

        {/* TIPO DE CONTEÚDO NO TOPO */}
        <Box sx={{ mb: 3, maxWidth: 320 }}>
          <Autocomplete
            options={TIPO_CONTEUDO}
            getOptionLabel={opt => opt.label}
            value={TIPO_CONTEUDO.find(opt => opt.value === form.tipo_conteudo) || null}
            onChange={(_, newValue) =>
              setForm(prev => ({
                ...prev,
                tipo_conteudo: (newValue?.value ?? "texto") as "texto" | "imagem",
                legenda_texto: "",
                conteudo: "",
                descricao_imagem: "",
                fonte_imagem: "",
                tags_imagem: [],
                licenca_imagem: "",
                imagemFile: null,
                observacoes: "",
                observacoes_imagem: ""
              }))
            }
            renderInput={params => (
              <TextField
                {...params}
                label="Tipo de Conteúdo *"
                required
                variant="outlined"
              />
            )}
          />
        </Box>

        <Box component="form" onSubmit={handleSubmit} autoComplete="off" sx={{ pointerEvents: sending ? "none" : "auto" }}>
          {/* Campos iguais ao Adicionar... */}
          <CampoComEditorAvancado
            label="Título *"
            value={form.titulo}
            onChange={(val: string) => setForm(prev => ({ ...prev, titulo: val }))}
            error={fieldErrors.titulo}
            required
            placeholder="Digite o título"
            height={70}
          />

          <Box sx={{ display: "flex", gap: 4, mb: 2 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.ativo}
                  onChange={e => setForm(prev => ({ ...prev, ativo: e.target.checked }))}
                  color="primary"
                  tabIndex={3}
                />
              }
              label="Ativo"
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.publico}
                  onChange={e => setForm(prev => ({ ...prev, publico: e.target.checked }))}
                  color="primary"
                  tabIndex={4}
                />
              }
              label="Público"
            />
          </Box>

          {form.tipo_conteudo === "texto" && (
            <>
              <Divider sx={{ my: 2 }}>Campos para Texto</Divider>
              <CampoComEditorAvancado
                label="Conteúdo do Texto *"
                value={form.conteudo}
                onChange={(val: string) => setForm(prev => ({ ...prev, conteudo: val }))}
                error={fieldErrors.conteudo}
                required
                placeholder="Digite o conteúdo principal..."
                height={350}
              />

              <CampoComEditorAvancado
                label="Legenda *"
                value={form.legenda_texto}
                onChange={(val: string) => setForm(prev => ({ ...prev, legenda_texto: val }))}
                error={fieldErrors.legenda_texto}
                required
                placeholder="Insira a legenda para o texto"
                height={70}
              />

              <CampoComEditorAvancado
                label="Observações"
                value={form.observacoes}
                onChange={(val: string) => setForm(prev => ({ ...prev, observacoes: val }))}
                error={fieldErrors.observacoes}
                placeholder="Digite observações adicionais"
                height={70}
              />
            </>
          )}

          {form.tipo_conteudo === "imagem" && (
            <>
              <Divider sx={{ my: 2 }}>Campos para Imagem</Divider>
              <CampoComEditorAvancado
                label="Descrição da Imagem *"
                value={form.descricao_imagem}
                onChange={(val: string) => setForm(prev => ({ ...prev, descricao_imagem: val }))}
                error={fieldErrors.descricao_imagem}
                required
                placeholder="Descreva a imagem para fins de referência"
                height={70}
              />

              <CampoComEditorAvancado
                label="Fonte/Autoria *"
                value={form.fonte_imagem}
                onChange={(val: string) => setForm(prev => ({ ...prev, fonte_imagem: val }))}
                error={fieldErrors.fonte_imagem}
                required
                placeholder="Ex: Banco de imagens, Autor, Link"
                height={70}
              />

              <Autocomplete
                multiple
                freeSolo
                options={SUGESTAO_TAGS}
                value={form.tags_imagem}
                onChange={(_, newValue) =>
                  setForm(prev => ({ ...prev, tags_imagem: newValue as string[] }))
                }
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => (
                    <Chip label={option} {...getTagProps({ index })} title={option} key={option} />
                  ))
                }
                renderInput={params => (
                  <TextField
                    {...params}
                    label="Tags da Imagem"
                    variant="outlined"
                    placeholder="Adicione ou selecione tags separadas por vírgula"
                  />
                )}
              />

              <Tooltip title="Selecione a licença da imagem." arrow>
                <span style={{ width: "100%" }}>
                  <Box sx={{ mt: 2 }}>
                    <Autocomplete
                      options={LICENCAS}
                      getOptionLabel={opt => opt.label}
                      value={LICENCAS.find(opt => opt.value === form.licenca_imagem) || null}
                      onChange={(_, newValue) =>
                        setForm(prev => ({ ...prev, licenca_imagem: newValue?.value ?? "" }))
                      }
                      renderInput={params => (
                        <TextField
                          {...params}
                          label="Licença"
                          variant="outlined"
                          placeholder="Escolha a licença"
                        />
                      )}
                    />
                  </Box>
                </span>
              </Tooltip>

              <Box
                sx={{
                  mb: 2,
                  border: "2px dashed #ccc",
                  p: 2,
                  textAlign: "center",
                  borderRadius: 2,
                  bgcolor: "#fafafa",
                  position: "relative",
                }}
                onDrop={handleDrop}
                onDragOver={e => e.preventDefault()}
              >
                <Tooltip title="Arraste e solte ou selecione uma imagem (até 5MB)." arrow>
                  <span>
                    <Button variant="outlined" component="label" tabIndex={11}>
                      Selecionar Imagem
                      <input type="file" accept="image/*" hidden onChange={handleImagemUpload} />
                    </Button>
                  </span>
                </Tooltip>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  ou arraste aqui
                </Typography>
                {imagemPreview && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      Pré-visualização:
                    </Typography>
                    <ImagemPreview src={imagemPreview} alt="Preview" />
                    <Typography variant="caption" color="text.secondary">
                      {form.imagemFile?.name || ""} ({(form.imagemFile?.size || 0) / 1024} KB - {form.imagemFile?.type || ""})
                    </Typography>
                  </Box>
                )}
                {!!fieldErrors.imagemFile && (
                  <Alert severity="error" sx={{ mt: 2 }}>{fieldErrors.imagemFile}</Alert>
                )}
              </Box>

              <CampoComEditorAvancado
                label="Observações sobre a Imagem"
                value={form.observacoes_imagem}
                onChange={(val: string) => setForm(prev => ({ ...prev, observacoes_imagem: val }))}
                error={fieldErrors.observacoes_imagem}
                placeholder="Digite observações adicionais sobre a imagem"
                height={70}
              />
            </>
          )}

          <Divider sx={{ my: 2 }}>Campos Gerais</Divider>

          <CampoComEditorAvancado
            label="Metadados"
            value={form.metadados_texto_ref}
            onChange={(val: string) => setForm(prev => ({ ...prev, metadados_texto_ref: val }))}
            error={fieldErrors.metadados_texto_ref}
            placeholder='Ex: {"chave": "valor"}'
            height={80}
          />

          {/* Autocomplete: Questões vinculadas */}
          <Autocomplete
            multiple
            options={todasQuestoes.map(q => ({
              id: q.id_questao,
              label: `${q.codigo_curto_questao ?? ""} - ${stripHtml(q.enunciado ?? "")}`,
            }))}
            value={form.questoes_vinculo.map(id => {
              const found = todasQuestoes.find(q => q.id_questao === id);
              return found
                ? {
                    id: found.id_questao,
                    label: `${found.codigo_curto_questao ?? ""} - ${stripHtml(found.enunciado ?? "")}`,
                  }
                : { id, label: id };
            })}
            onChange={(_, newValue) =>
              setForm(prev => ({
                ...prev,
                questoes_vinculo: newValue.map(v => v.id),
              }))
            }
            getOptionLabel={option => option.label}
            renderTags={(value, getTagProps) =>
              value.map((option, index) => (
                <Chip label={option.label} {...getTagProps({ index })} title={option.label} key={option.id} />
              ))
            }
            renderInput={params => (
              <TextField
                {...params}
                label="Questões vinculadas"
                variant="outlined"
                placeholder="Selecione ou adicione questões separadas por vírgula"
              />
            )}
          />

          <Box sx={{ display: "flex", gap: 2, mt: 2 }}>
            <Button
              type="submit"
              variant="contained"
              color="primary"
              disabled={sending}
              startIcon={sending && <CircularProgress size={20} />}
              tabIndex={15}
            >
              Salvar Edição
            </Button>
            <Button
              variant="outlined"
              color="secondary"
              onClick={() => navigate(-1)}
              tabIndex={16}
            >
              Cancelar
            </Button>
          </Box>
        </Box>
      </Paper>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Layout>
  );
}