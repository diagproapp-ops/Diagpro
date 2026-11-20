import { useState, useEffect } from "react";
import {
  Box,
  Button,
  Typography,
  Divider,
  Paper,
  Alert,
  Snackbar,
  Autocomplete,
  Chip,
  Checkbox,
  FormControlLabel,
  CircularProgress,
  TextField,
  RadioGroup,
  FormControl,
  FormLabel,
  Radio,
  FormHelperText,
} from "@mui/material";
import { useParams, useNavigate } from "react-router-dom";
import api from "../api";
import Layout from "../components/Layout";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import AssistenteIAQuestao from "../components/ia/AssistenteIAQuestao";
import { aplicarNoForm, formParaQuestaoIA, useStatusIA } from "../components/ia/iaComum";
import AvisoIA from "../components/ia/AvisoIA";
import { confirmarSeHouverParecida } from "../components/HistoricoVersoesDialog";
import CampoComEditorAvancado from "../components/CampoComEditorAvancado";
import { useAuth } from "../contexts/AuthContext";
import FileInputMui from "./FileInputMui";

const TIPO_QUESTAO = [
  { value: "MULTIPLA_ESCOLHA", label: "Múltipla Escolha" },
  { value: "DISCURSIVA", label: "Discursiva" },
  { value: "SUBJETIVA", label: "Subjetiva" },
  { value: "CERTO_ERRADO", label: "Certo/Errado" },
];
const NIVEIS_DIFICULDADE = [
  { value: "MUITO_FACIL", label: "Muito Fácil" },
  { value: "FACIL", label: "Fácil" },
  { value: "MEDIO", label: "Médio" },
  { value: "DIFICIL", label: "Difícil" },
  { value: "MUITO_DIFICIL", label: "Muito Difícil" },
];
const SUGESTAO_TAGS = ["matemática", "português", "geografia", "história", "biologia"];
const ALTERNATIVAS_PADRAO = [
  { letra: "A", texto: "", correta: true, imagem: null as File | null, texto_formatado: null },
  { letra: "B", texto: "", correta: false, imagem: null as File | null, texto_formatado: null },
  { letra: "C", texto: "", correta: false, imagem: null as File | null, texto_formatado: null },
  { letra: "D", texto: "", correta: false, imagem: null as File | null, texto_formatado: null },
  { letra: "E", texto: "", correta: false, imagem: null as File | null, texto_formatado: null },
];

interface TextoReferenciaType {
  id_texto_ref: string;
  codigo_ref: string;
  titulo: string;
}

export default function CriarQuestaoPage() {
  const { eventId, id_conteudo } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const tenantId = user?.tenant_id;

  const [form, setForm] = useState({
    tipo: "MULTIPLA_ESCOLHA",
    indicacao_conteudo: "",
    enunciado: "",
    quantidade_itens: 1,
    itens_comando: [""],
    respostas_certo_errado: [""],
    alternativas: ALTERNATIVAS_PADRAO,
    resposta_correta: "A",
    texto_referencia_vinculo: "",
    texto_referencia_direto: "",
    nivel_dificuldade: "MEDIO",
    pontuacao: 1.0,
    tags: [] as string[],
    anulada: false,
    justificativa_questao: "",
    justificativa_anulacao: "",
    palavras_chave_discursiva: "",
    num_linhas_discursiva: "",
    texto_subjetivo_orientacao: "",
    texto_subjetivo_nota_maxima: "",
    autor_elaborador: "",
  });

  // Imagem do enunciado
  const [imagemEnunciado, setImagemEnunciado] = useState<File | null>(null);
  // Imagens dos itens do comando
  const [imagensItensComando, setImagensItensComando] = useState<(File | null)[]>([]);

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: "",
    severity: "success" as "success" | "error" | "warning" | "info",
  });
  // Assistente de IA (só aparece se a plataforma e a banca ligarem)
  const statusIA = useStatusIA();
  const [iaAberto, setIaAberto] = useState(false);
  const [sending, setSending] = useState(false);

  // Tipos que a banca usa (Configurações > Regras das questões)
  const [tiposPermitidos, setTiposPermitidos] = useState<string[]>(TIPO_QUESTAO.map(t => t.value));
  useEffect(() => {
    api.get('/config/regras-questoes')
      .then(({ data }) => {
        const tipos: string[] = Array.isArray(data?.tipos_permitidos) && data.tipos_permitidos.length ? data.tipos_permitidos : TIPO_QUESTAO.map(t => t.value);
        setTiposPermitidos(tipos);
        setForm(prev => tipos.includes(prev.tipo) ? prev : { ...prev, tipo: tipos[0] });
      })
      .catch(() => {});
  }, []);
  const opcoesTipo = TIPO_QUESTAO.filter(t => tiposPermitidos.includes(t.value));

  // Textos de Referência
  const [textosReferencia, setTextosReferencia] = useState<TextoReferenciaType[]>([]);
  const [carregandoTextosReferencia, setCarregandoTextosReferencia] = useState(false);

  useEffect(() => {
    async function fetchTextosReferencia() {
      setCarregandoTextosReferencia(true);
      try {
        const res = await api.get(`/eventos/${eventId}/conteudos/${id_conteudo}/textos-referencia`);
        setTextosReferencia(res.data ?? []);
      } catch {
        setTextosReferencia([]);
      }
      setCarregandoTextosReferencia(false);
    }
    fetchTextosReferencia();
  }, [eventId, id_conteudo]);

  function handleAlternativaChange(idx: number, newData: any) {
    setForm(prev => ({
      ...prev,
      alternativas: prev.alternativas.map((alt, i) =>
        i === idx ? { ...alt, ...newData } : alt
      ),
    }));
  }
  function marcarCorreta(idx: number) {
    setForm(prev => ({
      ...prev,
      alternativas: prev.alternativas.map((alt, i) => ({ ...alt, correta: i === idx })),
      resposta_correta: ALTERNATIVAS_PADRAO[idx].letra,
    }));
  }

  function handleQuantidadeItensChange(val: number) {
    val = val < 1 ? 1 : val;
    setForm(prev => {
      let novosItens = prev.itens_comando.slice(0, val);
      let novasRespostas = prev.respostas_certo_errado.slice(0, val);
      while (novosItens.length < val) novosItens.push("");
      while (novasRespostas.length < val) novasRespostas.push("");
      return { ...prev, quantidade_itens: val, itens_comando: novosItens, respostas_certo_errado: novasRespostas };
    });
    setImagensItensComando(prev => {
      const novo = prev.slice(0, val);
      while (novo.length < val) novo.push(null);
      return novo;
    });
  }

  function stripHtml(html: string) {
    return html.replace(/<[^>]*>?/gm, '');
  }

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (!form.indicacao_conteudo.trim())
      errors.indicacao_conteudo = "Indicação do conteúdo obrigatória.";
    if (!form.enunciado.trim() || form.enunciado === "<p></p>")
      errors.enunciado = "Enunciado obrigatório.";
    if (form.tipo === "CERTO_ERRADO") {
      if (!form.quantidade_itens || form.quantidade_itens < 1)
        errors.quantidade_itens = "Informe a quantidade de itens (mínimo 1).";
      if (!form.itens_comando || form.itens_comando.length < form.quantidade_itens || form.itens_comando.some((item: string) => !item || item === "<p></p>")) {
        errors.itens_comando = "Preencha todos os itens do comando.";
      }
      if (!form.respostas_certo_errado || form.respostas_certo_errado.length < form.quantidade_itens || form.respostas_certo_errado.some((resp: string) => !resp)) {
        errors.respostas_certo_errado = "Selecione Certo ou Errado para todos os itens.";
      }
    }
    if (form.tipo === "MULTIPLA_ESCOLHA") {
      const alternativasValidas = form.alternativas.filter(alt => alt.texto.trim());
      if (alternativasValidas.length < 2) errors.alternativas = "Defina pelo menos 2 alternativas.";
      if (!form.alternativas.some(alt => alt.correta)) errors.alternativas = "Marque a alternativa correta.";
    }
    if (form.tipo === "DISCURSIVA") {
      if (!form.palavras_chave_discursiva.trim())
        errors.palavras_chave_discursiva = "Palavras-chave são obrigatórias.";
      if (!form.num_linhas_discursiva.trim())
        errors.num_linhas_discursiva = "Número de linhas obrigatório.";
    }
    if (form.tipo === "SUBJETIVA") {
      // linhas impressas abaixo do enunciado na prova diagramada
      const linhas = Number(String(form.num_linhas_discursiva ?? "").trim());
      if (!linhas || linhas < 1 || linhas > 60)
        errors.num_linhas_discursiva = "Informe de 1 a 60 linhas.";
      if (!form.texto_subjetivo_orientacao.trim())
        errors.texto_subjetivo_orientacao = "Orientação é obrigatória.";
      if (!form.texto_subjetivo_nota_maxima.trim())
        errors.texto_subjetivo_nota_maxima = "Nota máxima é obrigatória.";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSending(true);

    if (!tenantId) {
      setSnackbar({ open: true, message: "Tenant não encontrado. Faça login novamente.", severity: "error" });
      setSending(false);
      return;
    }

    if (!validate()) {
      setSending(false);
      return;
    }
    if (!(await confirmarSeHouverParecida(form.enunciado))) {
      setSending(false);
      return;
    }

    try {
      const formData = new FormData();
      formData.append("tipo", form.tipo);
      formData.append("indicacao_conteudo", form.indicacao_conteudo);
      formData.append("enunciado", form.enunciado);

      // Envia a imagem do enunciado
      if (imagemEnunciado) {
        formData.append("imagem_enunciado", imagemEnunciado);
      }

      // Envia imagens dos itens do comando
      imagensItensComando.forEach((imagem, idx) => {
        if (imagem) {
          formData.append(`item_imagem_${idx}`, imagem);
        }
      });

      // Remover o campo imagem do JSON das alternativas
      const alternativasParaEnviar = form.alternativas.map(({ imagem, ...rest }) => rest);
      formData.append("alternativas", JSON.stringify(alternativasParaEnviar));
      // Adiciona as imagens das alternativas
      form.alternativas.forEach((alt) => {
        if (alt.imagem) {
          formData.append(`alternativa_imagem_${alt.letra}`, alt.imagem);
        }
      });

      if (form.tipo === "CERTO_ERRADO") {
        const itens_vf = form.itens_comando.map((texto, idx) => ({
          afirmacao: texto,
          valor_correto: form.respostas_certo_errado[idx] === "CERTO"
        }));
        formData.append("itens_vf", JSON.stringify(itens_vf));
      }

      if (form.tipo === "DISCURSIVA" || form.tipo === "SUBJETIVA") {
        const detalhes_discursiva = {
          resposta_esperada_texto: "",
          palavras_chave_resposta: form.palavras_chave_discursiva
            .split(",")
            .map(t => t.trim())
            .filter(Boolean),
          numero_linhas_resposta: (form.tipo === "DISCURSIVA" || form.tipo === "SUBJETIVA")
            ? Number(form.num_linhas_discursiva)
            : undefined,
          texto_subjetivo_orientacao: form.tipo === "SUBJETIVA"
            ? form.texto_subjetivo_orientacao
            : undefined,
          texto_subjetivo_nota_maxima: form.tipo === "SUBJETIVA"
            ? form.texto_subjetivo_nota_maxima
            : undefined,
        };
        formData.append("detalhes_discursiva", JSON.stringify(detalhes_discursiva));
      }

      formData.append("nivel_dificuldade", form.nivel_dificuldade);
      formData.append("pontuacao", String(form.pontuacao));
      formData.append("tags", form.tags.join(","));
      if (form.tipo === "MULTIPLA_ESCOLHA" || form.tipo === "CERTO_ERRADO") {
        formData.append("anulada", form.anulada ? "true" : "false");
      }
      formData.append("justificativa_questao", form.justificativa_questao);
      formData.append("justificativa_anulacao", form.justificativa_anulacao);
      formData.append("resposta_correta", form.resposta_correta);
      formData.append("texto_referencia_vinculo", form.texto_referencia_vinculo);
      formData.append("texto_referencia_direto", form.texto_referencia_direto);
      formData.append("tenant_id", String(tenantId));

      if (user?.username) {
        formData.append("autor_elaborador", user.username);
      }

      await api.post(`/eventos/${eventId}/conteudos/${id_conteudo}/questoes`, formData);

      navigate(-1);
      setSending(false);
    } catch (err: any) {
      let msg = "Erro ao salvar questão.";
      if (err.response?.data?.detail) {
        msg = typeof err.response.data.detail === "string"
          ? err.response.data.detail
          : JSON.stringify(err.response.data.detail);
      }
      setSnackbar({ open: true, message: msg, severity: "error" });
      setSending(false);
    }
  }

  function handleAdicionarOutro() {
    setForm({
      tipo: "MULTIPLA_ESCOLHA",
      indicacao_conteudo: "",
      enunciado: "",
      quantidade_itens: 1,
      itens_comando: [""],
      respostas_certo_errado: [""],
      alternativas: ALTERNATIVAS_PADRAO,
      resposta_correta: "A",
      texto_referencia_vinculo: "",
      texto_referencia_direto: "",
      nivel_dificuldade: "MEDIO",
      pontuacao: 1.0,
      tags: [],
      anulada: false,
      justificativa_questao: "",
      justificativa_anulacao: "",
      palavras_chave_discursiva: "",
      num_linhas_discursiva: "",
      texto_subjetivo_orientacao: "",
      texto_subjetivo_nota_maxima: "",
      autor_elaborador: "",
    });
    setImagemEnunciado(null);
    setImagensItensComando([]);
  }

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
          <Typography variant="h5" fontWeight="bold" gutterBottom>
            Criar Nova Questão
          </Typography>
          <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
            {statusIA.disponivel && (
              <Button variant="contained" color="secondary" startIcon={<AutoAwesomeIcon />} onClick={() => setIaAberto(true)}>
                Assistente de IA
              </Button>
            )}
            <AvisoIA status={statusIA} />
            <Button variant="outlined" color="primary" onClick={() => navigate(-1)} tabIndex={-1}>
              Voltar
            </Button>
          </Box>
        </Box>
        <Divider sx={{ mb: 2 }} />

        {/* Tipo de Questão */}
        <Box sx={{ mb: 3, maxWidth: 320 }}>
          <Autocomplete
            options={opcoesTipo}
            getOptionLabel={opt => opt.label}
            value={TIPO_QUESTAO.find(opt => opt.value === form.tipo) || null}
            onChange={(_, newValue) =>
              setForm(prev => ({
                ...prev,
                tipo: newValue?.value ?? "MULTIPLA_ESCOLHA",
                alternativas: ALTERNATIVAS_PADRAO.map((alt, idx) => ({ ...alt, correta: idx === 0 })),
                resposta_correta: "A",
                quantidade_itens: 1,
                itens_comando: [""],
                respostas_certo_errado: [""],
              }))
            }
            renderInput={params => (
              <TextField
                {...params}
                label="Tipo de Questão *"
                required
                variant="outlined"
              />
            )}
          />
        </Box>

        {/* Indicação do conteúdo conforme edital */}
        <Box sx={{ mb: 2 }}>
          <TextField
            label="Indicação do Conteúdo conforme edital *"
            value={form.indicacao_conteudo}
            onChange={e => setForm(prev => ({ ...prev, indicacao_conteudo: e.target.value }))}
            placeholder="Ex: Interpretação de texto, Gramática, Formologia..."
            required
            fullWidth
            error={!!fieldErrors.indicacao_conteudo}
            helperText={fieldErrors.indicacao_conteudo}
          />
        </Box>

        <Box component="form" onSubmit={handleSubmit} autoComplete="off" sx={{ pointerEvents: sending ? "none" : "auto" }}>
          {/* Enunciado */}
          <CampoComEditorAvancado
            label="Enunciado *"
            value={form.enunciado}
            onChange={(val: string) => setForm(prev => ({ ...prev, enunciado: val }))}
            error={typeof fieldErrors.enunciado === 'string' ? fieldErrors.enunciado : undefined}
            required
            placeholder="Digite o comando da questão"
            height={240}
          />

          {/* Upload da Imagem do Enunciado */}
          <Box sx={{ mt: 1, mb: 2 }}>
            <FileInputMui
              label="Adicionar imagem do enunciado"
              file={imagemEnunciado}
              onChange={setImagemEnunciado}
            />
          </Box>

          {/* Só mostra a quantidade de itens se for CERTO_ERRADO */}
          {form.tipo === "CERTO_ERRADO" && (
            <TextField
              label="Quantidade de Itens do Enunciado *"
              type="number"
              value={form.quantidade_itens}
              onChange={e => {
                let val = Number(e.target.value);
                handleQuantidadeItensChange(val);
              }}
              error={!!fieldErrors.quantidade_itens}
              helperText={fieldErrors.quantidade_itens}
              fullWidth
              sx={{ mb: 2 }}
              inputProps={{ min: 1 }}
              required
            />
          )}

          {/* Itens do comando para CERTO_ERRADO */}
          {form.tipo === "CERTO_ERRADO" && form.quantidade_itens > 0 && (
            <>
              <Divider sx={{ my: 2 }}>Itens do Comando</Divider>
              {Array.from({ length: form.quantidade_itens }).map((_, idx) => (
                <Box key={idx} sx={{ mb: 2 }}>
                  <CampoComEditorAvancado
                    label={`Item ${idx + 1}`}
                    value={form.itens_comando[idx] || ""}
                    onChange={val => {
                      setForm(prev => {
                        const novosItens = [...prev.itens_comando];
                        novosItens[idx] = val;
                        return { ...prev, itens_comando: novosItens };
                      });
                    }}
                    error={
                      fieldErrors.itens_comando && (!form.itens_comando[idx] || form.itens_comando[idx] === "<p></p>")
                        ? fieldErrors.itens_comando : undefined
                    }
                    placeholder={`Descreva o item ${idx + 1} do comando`}
                    height={70}
                  />
                  <Box sx={{ my: 1 }}>
                    <FileInputMui
                      label={`Adicionar imagem do item ${idx + 1}`}
                      file={imagensItensComando[idx] || null}
                      onChange={file => {
                        setImagensItensComando(prev => {
                          const novo = [...prev];
                          novo[idx] = file;
                          return novo;
                        });
                      }}
                    />
                  </Box>
                  <FormControl
                    component="fieldset"
                    required
                    error={
                      !!fieldErrors.respostas_certo_errado &&
                      (!form.respostas_certo_errado[idx] || form.respostas_certo_errado[idx] === "")
                    }
                    sx={{ mt: 1 }}
                  >
                    <FormLabel component="legend">Resposta para o item {idx + 1}</FormLabel>
                    <RadioGroup
                      row
                      name={`resposta_item_${idx}`}
                      value={form.respostas_certo_errado[idx] || ""}
                      onChange={e => {
                        setForm(prev => {
                          const novasRespostas = [...prev.respostas_certo_errado];
                          novasRespostas[idx] = e.target.value;
                          return { ...prev, respostas_certo_errado: novasRespostas };
                        });
                      }}
                    >
                      <FormControlLabel value="CERTO" control={<Radio color="primary" />} label="Certo" />
                      <FormControlLabel value="ERRADO" control={<Radio color="error" />} label="Errado" />
                    </RadioGroup>
                    {fieldErrors.respostas_certo_errado &&
                      (!form.respostas_certo_errado[idx] || form.respostas_certo_errado[idx] === "") && (
                        <FormHelperText>{fieldErrors.respostas_certo_errado}</FormHelperText>
                      )}
                  </FormControl>
                </Box>
              ))}
            </>
          )}

          {/* Alternativas - Múltipla Escolha */}
          {form.tipo === "MULTIPLA_ESCOLHA" && (
            <>
              <Divider sx={{ my: 2 }}>Alternativas</Divider>
              {form.alternativas.map((alt, idx) => (
                <Box
                  key={alt.letra}
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 2,
                    mb: 2,
                    p: 0,
                    borderRadius: 1,
                    background: idx === 0 ? "rgba(245, 158, 11, 0.12)" : "rgba(11, 19, 37, 0.8)",
                    border: idx === 0 ? "2px solid #ff9800" : "1px solid rgba(148, 163, 184, 0.25)",
                    boxShadow: 0,
                    width: "100%",
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
                    <Checkbox
                      checked={alt.correta}
                      onChange={() => marcarCorreta(idx)}
                      color={idx === 0 ? "warning" : "primary"}
                      sx={{ mr: 1 }}
                    />
                    <Typography variant="subtitle1" fontWeight="bold">
                      Alternativa {alt.letra}
                    </Typography>
                    {idx === 0 && (
                      <Chip
                        label="Correta"
                        color="warning"
                        size="small"
                        sx={{ ml: 1, fontWeight: "bold" }}
                      />
                    )}
                  </Box>
                  <Box sx={{ width: "95%", mx: "auto" }}>
                    <CampoComEditorAvancado
                      label=""
                      value={alt.texto}
                      onChange={(val: string) => handleAlternativaChange(idx, { texto: val })}
                      error={typeof fieldErrors.alternativas === 'string' && idx === 0 ? fieldErrors.alternativas : undefined}
                      placeholder={`Texto da alternativa ${alt.letra}`}
                      height={80}
                    />
                  </Box>
                  <Box sx={{ mt: 1 }}>
                    <FileInputMui
                      label={`Adicionar imagem da alternativa ${alt.letra}`}
                      file={alt.imagem}
                      onChange={file => handleAlternativaChange(idx, { imagem: file })}
                    />
                  </Box>
                </Box>
              ))}
            </>
          )}

          {/* Discursiva: campos extras */}
          {form.tipo === "DISCURSIVA" && (
            <>
              <Divider sx={{ my: 2 }}>Campos Discursiva</Divider>
              <CampoComEditorAvancado
                label="Palavras-chave *"
                value={form.palavras_chave_discursiva}
                onChange={(val: string) => setForm(prev => ({ ...prev, palavras_chave_discursiva: val }))}
                error={typeof fieldErrors.palavras_chave_discursiva === 'string' ? fieldErrors.palavras_chave_discursiva : undefined}
                required
                placeholder="Palavras-chave separadas por vírgula"
                height={50}
              />
              <TextField
                label="Número de linhas para resposta *"
                value={form.num_linhas_discursiva}
                onChange={e => setForm(prev => ({ ...prev, num_linhas_discursiva: e.target.value }))}
                error={!!fieldErrors.num_linhas_discursiva}
                helperText={fieldErrors.num_linhas_discursiva}
                type="number"
                fullWidth
                sx={{ mb: 2 }}
              />
            </>
          )}

          {/* Subjetiva: campos extras */}
          {form.tipo === "SUBJETIVA" && (
            <>
              <Divider sx={{ my: 2 }}>Campos Subjetiva</Divider>
              <TextField
                label="Número de linhas para resposta *"
                value={form.num_linhas_discursiva}
                onChange={e => setForm(prev => ({ ...prev, num_linhas_discursiva: e.target.value }))}
                error={!!fieldErrors.num_linhas_discursiva}
                helperText={fieldErrors.num_linhas_discursiva || "Linhas impressas abaixo do enunciado na prova."}
                type="number"
                inputProps={{ min: 1, max: 60 }}
                fullWidth
                sx={{ mb: 2 }}
              />
              <CampoComEditorAvancado
                label="Orientação da Resposta *"
                value={form.texto_subjetivo_orientacao}
                onChange={(val: string) => setForm(prev => ({ ...prev, texto_subjetivo_orientacao: val }))}
                error={typeof fieldErrors.texto_subjetivo_orientacao === 'string' ? fieldErrors.texto_subjetivo_orientacao : undefined}
                required
                placeholder="Orientações para a banca ou candidato"
                height={50}
              />
              <TextField
                label="Nota Máxima *"
                value={form.texto_subjetivo_nota_maxima}
                onChange={e => setForm(prev => ({ ...prev, texto_subjetivo_nota_maxima: e.target.value }))}
                error={!!fieldErrors.texto_subjetivo_nota_maxima}
                helperText={fieldErrors.texto_subjetivo_nota_maxima}
                type="number"
                fullWidth
                sx={{ mb: 2 }}
              />
            </>
          )}

          <Divider sx={{ my: 2 }}>Justificativa da Questão</Divider>
          <CampoComEditorAvancado
            label="Justificativa da Questão"
            value={form.justificativa_questao}
            onChange={(val: string) => setForm(prev => ({ ...prev, justificativa_questao: val }))}
            placeholder="Explique o embasamento da questão, a lógica da resposta correta, etc."
            height={70}
          />

          <Divider sx={{ my: 2 }}>Texto de Referência</Divider>
          <Autocomplete
            options={textosReferencia}
            getOptionLabel={opt => `${opt.codigo_ref} - ${stripHtml(opt.titulo)}`}
            loading={carregandoTextosReferencia}
            value={textosReferencia.find(ref => ref.id_texto_ref === form.texto_referencia_vinculo) || null}
            onChange={(_, newValue) =>
              setForm(prev => ({
                ...prev,
                texto_referencia_vinculo: newValue?.id_texto_ref || ""
              }))
            }
            isOptionEqualToValue={(option, value) => option.id_texto_ref === value.id_texto_ref}
            renderInput={params => (
              <TextField
                {...params}
                label="Vincular texto de referência"
                variant="outlined"
                placeholder="Selecione o texto de referência"
                fullWidth
                sx={{ mb: 2 }}
              />
            )}
          />
          <CampoComEditorAvancado
            label="Texto de referência direto"
            value={form.texto_referencia_direto}
            onChange={(val: string) => setForm(prev => ({ ...prev, texto_referencia_direto: val }))}
            placeholder="Ou digite um texto de apoio"
            height={70}
          />

          <Divider sx={{ my: 2 }}>Metadados e Tags</Divider>
          <Autocomplete
            multiple
            freeSolo
            options={SUGESTAO_TAGS}
            value={form.tags}
            onChange={(_, newValue) => setForm(prev => ({ ...prev, tags: newValue as string[] }))}
            renderTags={(value, getTagProps) =>
              value.map((option, index) => (
                <Chip label={option} {...getTagProps({ index })} title={option} key={option} />
              ))
            }
            renderInput={params => (
              <TextField
                {...params}
                label="Tags"
                variant="outlined"
                placeholder="Adicione ou selecione tags separadas por vírgula"
              />
            )}
            sx={{ mb: 2 }}
          />

          {form.autor_elaborador && (
            <Typography variant="subtitle2" sx={{ color: "text.secondary", mb: 1 }}>
              Autor: {form.autor_elaborador}
            </Typography>
          )}

          <Divider sx={{ my: 2 }}>Outros</Divider>
          {(form.tipo === "MULTIPLA_ESCOLHA" || form.tipo === "CERTO_ERRADO") && (
            <Box sx={{ display: "flex", gap: 4, mb: 2 }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={form.anulada}
                    onChange={e => setForm(prev => ({ ...prev, anulada: e.target.checked }))}
                    color="error"
                  />
                }
                label="Marcar Questão como Anulada"
              />
            </Box>
          )}
          <CampoComEditorAvancado
            label="Justificativa Anulação / Recurso"
            value={form.justificativa_anulacao}
            onChange={(val: string) => setForm(prev => ({ ...prev, justificativa_anulacao: val }))}
            placeholder="Se a questão estiver anulada, descreva o motivo"
            height={70}
          />

          <TextField
            label="Pontuação"
            type="number"
            value={form.pontuacao}
            onChange={e => setForm(prev => ({ ...prev, pontuacao: Number(e.target.value) }))}
            sx={{ mb: 2 }}
            fullWidth
          />
          <Autocomplete
            options={NIVEIS_DIFICULDADE}
            getOptionLabel={opt => opt.label}
            value={NIVEIS_DIFICULDADE.find(opt => opt.value === form.nivel_dificuldade) || null}
            onChange={(_, newValue) =>
              setForm(prev => ({ ...prev, nivel_dificuldade: newValue?.value ?? "MEDIO" }))
            }
            renderInput={params => (
              <TextField
                {...params}
                label="Nível de Dificuldade"
                required
                variant="outlined"
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
              Salvar
            </Button>
            <Button
              variant="outlined"
              color="secondary"
              onClick={handleAdicionarOutro}
              tabIndex={16}
            >
              Adicionar Outro
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
      {iaAberto && (
        <AssistenteIAQuestao
          open={iaAberto}
          onClose={() => setIaAberto(false)}
          status={statusIA}
          questao={formParaQuestaoIA(form)}
          onAplicar={(ap, aviso) => {
            setForm((prev: any) => aplicarNoForm(prev, ap));
            setSnackbar({ open: true, message: aviso, severity: "info" });
          }}
        />
      )}
    </Layout>
  );
}