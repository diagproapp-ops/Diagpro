import { useEffect, useState } from "react";
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
  TextField,
  RadioGroup,
  FormControl,
  FormLabel,
  Radio,
  CircularProgress,
} from "@mui/material";
import { useParams, useNavigate } from "react-router-dom";
import api from "../api";
import Layout from "../components/Layout";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import AssistenteIAQuestao from "../components/ia/AssistenteIAQuestao";
import { aplicarNoForm, formParaQuestaoIA, useStatusIA } from "../components/ia/iaComum";
import AvisoIA from "../components/ia/AvisoIA";
import CampoComEditorAvancado from "../components/CampoComEditorAvancado";
import { useAuth } from "../contexts/AuthContext";
import FileInputMui from "./FileInputMui";

function stripHtml(html: string) {
  return html.replace(/<[^>]*>?/gm, "");
}

const TIPO_QUESTAO = [
  { value: "MULTIPLA_ESCOLHA", label: "Múltipla Escolha" },
  { value: "DISCURSIVA", label: "Discursiva" },
  { value: "SUBJETIVA", label: "Subjetiva" },
  { value: "CERTO_ERRADO", label: "Certo/Errado" },
];
const NIVEIS_DIFICULDADE = [
  { value: "FACIL", label: "Fácil" },
  { value: "MEDIO", label: "Médio" },
  { value: "DIFICIL", label: "Difícil" },
];
const SUGESTAO_TAGS = ["matemática", "português", "geografia", "história", "biologia"];
const ALTERNATIVAS_PADRAO = [
  { letra: "A", texto: "", correta: true, imagem: null as File | null, texto_formatado: null, imagem_path_opcao: "" },
  { letra: "B", texto: "", correta: false, imagem: null as File | null, texto_formatado: null, imagem_path_opcao: "" },
  { letra: "C", texto: "", correta: false, imagem: null as File | null, texto_formatado: null, imagem_path_opcao: "" },
  { letra: "D", texto: "", correta: false, imagem: null as File | null, texto_formatado: null, imagem_path_opcao: "" },
  { letra: "E", texto: "", correta: false, imagem: null as File | null, texto_formatado: null, imagem_path_opcao: "" },
];

type TextoReferenciaType = {
  id_texto_ref: string;
  codigo_ref: string;
  titulo: string;
};

type ItemVFType = {
  afirmacao: string;
  valor_correto: boolean;
  imagem_path_item?: string;
};

export default function RevisarQuestaoPage() {
  const { eventId, id_conteudo, id_questao } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const tenantId = user?.tenant_id;

  const [form, setForm] = useState({
    tipo: "MULTIPLA_ESCOLHA",
    codigo_curto_questao: "",
    indicacao_conteudo: "",
    enunciado: "",
    caminho_imagem_enunciado: "",
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
    status_revisao: "",
    observacao_revisor: "",
    itens_vf: [] as ItemVFType[],
    autor_elaborador: "",
  });

  // Uploads
  const [imagemEnunciado, setImagemEnunciado] = useState<File | null>(null);
  const [imagensItensComando, setImagensItensComando] = useState<(File | null)[]>([]);

  const [snackbar, setSnackbar] = useState({
    open: false,
    message: "",
    severity: "success" as "success" | "error" | "warning" | "info",
  });
  // Assistente de IA (só aparece se a plataforma e a banca ligarem)
  const statusIA = useStatusIA();
  const [iaAberto, setIaAberto] = useState(false);
  const [sending, setSending] = useState(false);

  // Textos de referência para autocomplete
  const [textosReferencia, setTextosReferencia] = useState<TextoReferenciaType[]>([]);
  const [carregandoTextosReferencia, setCarregandoTextosReferencia] = useState(false);
  const [textoRefSelecionado, setTextoRefSelecionado] = useState<TextoReferenciaType | null>(null);

  // Revisões
  const [totalRevisoes, setTotalRevisoes] = useState<number>(1);

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
    if (eventId && id_conteudo) fetchTextosReferencia();
  }, [eventId, id_conteudo]);

  useEffect(() => {
    async function fetchRevisoes() {
        try {
        const res = await api.get(
            `/eventos/${eventId}/conteudos/${id_conteudo}/questoes/${id_questao}/revisoes`
        );
        setTotalRevisoes(res.data?.length ?? 1);
        } catch {
        setTotalRevisoes(1);
        }
    }
    if (eventId && id_conteudo && id_questao) fetchRevisoes();
    }, [eventId, id_conteudo, id_questao]);

  useEffect(() => {
    async function fetchQuestao() {
      try {
        const { data } = await api.get(
          `/eventos/${eventId}/conteudos/${id_conteudo}/questoes/${id_questao}`
        );
        setForm(prev => ({
          ...prev,
          ...data,
          autor_elaborador: data.autor_elaborador || "",
          caminho_imagem_enunciado: data.caminho_imagem_relativo || "",
          codigo_curto_questao: data.codigo_curto_questao || "",
          alternativas: data.alternativas?.length
            ? data.alternativas.map((alt: any) => ({
                letra: alt.letra,
                texto: alt.texto_opcao ?? "",
                correta: alt.correta,
                imagem: null,
                texto_formatado: alt.texto_opcao_formatado ?? null,
                imagem_path_opcao: alt.imagem_path_opcao ?? ""
              }))
            : ALTERNATIVAS_PADRAO,
          quantidade_itens: data.itens_vf?.length ?? 1,
          itens_comando: data.itens_vf?.map((item: any) => item.afirmacao) ?? [""],
          respostas_certo_errado: data.itens_vf?.map((item: any) => item.valor_correto ? "CERTO" : "ERRADO") ?? [""],
          itens_vf: data.itens_vf || [],
          palavras_chave_discursiva: data.detalhes_discursiva?.palavras_chave_resposta?.join(", ") ?? "",
          num_linhas_discursiva: data.detalhes_discursiva?.numero_linhas_resposta ?? "",
          texto_subjetivo_orientacao: data.detalhes_discursiva?.texto_subjetivo_orientacao ?? "",
          texto_subjetivo_nota_maxima: data.detalhes_discursiva?.texto_subjetivo_nota_maxima ?? "",
          status_revisao: data.status_revisao ?? "",
          observacao_revisor: data.observacao_revisor ?? "",
        }));
        setImagensItensComando(data.itens_vf?.map(() => null) ?? []);
      } catch (err) {
        setSnackbar({ open: true, message: "Erro ao carregar questão.", severity: "error" });
      }
    }
    if (id_questao) fetchQuestao();
  }, [id_questao, eventId, id_conteudo]);

  // Sincroniza array de imagens dos itens quando quantidade muda
  useEffect(() => {
    setImagensItensComando(prev => {
      const novo = prev.slice(0, form.quantidade_itens);
      while (novo.length < form.quantidade_itens) novo.push(null);
      return novo;
    });
  }, [form.quantidade_itens]);

  useEffect(() => {
    if (!form.texto_referencia_vinculo || textosReferencia.length === 0) {
      setTextoRefSelecionado(null);
      return;
    }
    const selected = textosReferencia.find(ref => ref.id_texto_ref === form.texto_referencia_vinculo) || null;
    setTextoRefSelecionado(selected);
  }, [form.texto_referencia_vinculo, textosReferencia]);

  function handleAlternativaChange(idx: number, newData: any) {
    setForm(prev => ({
      ...prev,
      alternativas: prev.alternativas.map((alt, i) =>
        i === idx ? { ...alt, ...newData } : alt
      ),
    }));
  }

  async function handleRevisaoSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSending(true);

    if (!tenantId || !user?.username) {
        setSnackbar({ open: true, message: "Tenant ou usuário não encontrado. Faça login novamente.", severity: "error" });
        setSending(false);
        return;
    }

    try {
        const formData = new FormData();
        formData.append("status_revisao", form.status_revisao);
        formData.append("observacao_revisor", form.observacao_revisor);
        formData.append("usuario_revisor", user.username);
        formData.append("tenant_id", String(tenantId));
        formData.append("dados_revisao", JSON.stringify(form));
        if (imagemEnunciado) formData.append("imagem_enunciado", imagemEnunciado);
        imagensItensComando.forEach((imagem, idx) => {
          if (imagem) formData.append(`item_imagem_${idx}`, imagem);
        });
        form.alternativas.forEach((alt) => {
          if (alt.imagem) {
            formData.append(`alternativa_imagem_${alt.letra}`, alt.imagem);
          }
        });

        await api.patch(
        `/eventos/${eventId}/conteudos/${id_conteudo}/questoes/${id_questao}/revisao`,
        formData
        );

        setSnackbar({ open: true, message: "Revisão salva com sucesso!", severity: "success" });
        setTimeout(() => navigate(-1), 500);
        setSending(false);
    } catch (err: any) {
        let msg = "Erro ao salvar revisão.";
        if (err.response?.data?.detail) {
        msg = typeof err.response.data.detail === "string"
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
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
          <Box>
            <Typography variant="h5" fontWeight="bold" gutterBottom>
              Revisar Questão
            </Typography>
            <Typography variant="subtitle1" fontWeight="bold" sx={{ mt: 1, mb: 1, display: "flex", alignItems: "center" }}>
              Código da Questão: {form.codigo_curto_questao || ""}
              <span style={{ marginLeft: 24, color: "#38BDF8", fontWeight: 400, fontSize: 18 }}>
                Revisão {totalRevisoes}
              </span>
            </Typography>
            {form.autor_elaborador && (
            <Typography variant="subtitle2" sx={{ color: "text.secondary", mb: 1 }}>
              Autor: {form.autor_elaborador}
            </Typography>
      )}
          </Box>
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

        <Box sx={{ mb: 3, maxWidth: 320 }}>
          <Autocomplete
            options={TIPO_QUESTAO}
            getOptionLabel={opt => opt.label}
            value={TIPO_QUESTAO.find(opt => opt.value === form.tipo) || null}
            disabled
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

        <Box sx={{ mb: 2 }}>
          <TextField
            label="Indicação do Conteúdo conforme edital *"
            value={form.indicacao_conteudo}
            disabled
            placeholder="Ex: Interpretação de texto, Gramática, Formologia..."
            required
            fullWidth
          />
        </Box>

        <CampoComEditorAvancado
          label="Enunciado *"
          value={form.enunciado}
          onChange={(val: string) => setForm(prev => ({ ...prev, enunciado: val }))}
          required
          placeholder="Digite o comando da questão"
          height={240}
        />

        {form.caminho_imagem_enunciado && (
          <Box sx={{ mt: 1, mb: 2, display: "flex", flexDirection: "column", alignItems: "center" }}>
            <img
              src={`http://localhost:8000/${form.caminho_imagem_enunciado}`}
              alt="Imagem do enunciado"
              style={{ maxWidth: 300, maxHeight: 160, borderRadius: 8 }}
            />
          </Box>
        )}
        <Box sx={{ mt: 1, mb: 2 }}>
          <FileInputMui
            label="Adicionar imagem do enunciado"
            file={imagemEnunciado}
            onChange={setImagemEnunciado}
          />
        </Box>

        {form.tipo === "CERTO_ERRADO" && (
          <TextField
            label="Quantidade de Itens do Enunciado *"
            type="number"
            value={form.quantidade_itens}
            disabled
            fullWidth
            sx={{ mb: 2 }}
            inputProps={{ min: 1 }}
            required
          />
        )}
        {form.tipo === "CERTO_ERRADO" && form.quantidade_itens > 0 && (
          <>
            <Divider sx={{ my: 2 }}>Itens do Comando</Divider>
            {form.itens_vf && form.itens_vf.length > 0
              ? form.itens_vf.map((item, idx) => (
                  <Box key={idx} sx={{ mb: 2 }}>
                    <CampoComEditorAvancado
                      label={`Item ${idx + 1}`}
                      value={item.afirmacao || ""}
                      onChange={val => {
                        setForm(prev => {
                          const novosItens = [...prev.itens_comando];
                          novosItens[idx] = val;
                          return { ...prev, itens_comando: novosItens };
                        });
                      }}
                      placeholder={`Descreva o item ${idx + 1} do comando`}
                      height={70}
                    />
                    {item.imagem_path_item && (
                      <Box sx={{ my: 1, display: "flex", justifyContent: "center" }}>
                        <img
                          src={`http://localhost:8000/${item.imagem_path_item}`}
                          alt={`Imagem do item ${idx + 1}`}
                          style={{ maxWidth: 180, maxHeight: 120, borderRadius: 8 }}
                        />
                      </Box>
                    )}
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
                      sx={{ mt: 1 }}
                    >
                      <FormLabel component="legend">Resposta para o item {idx + 1}</FormLabel>
                      <RadioGroup
                        row
                        name={`resposta_item_${idx}`}
                        value={item.valor_correto ? "CERTO" : "ERRADO"}
                        onChange={() => {}}
                      >
                        <FormControlLabel value="CERTO" control={<Radio color="primary" />} label="Certo" disabled />
                        <FormControlLabel value="ERRADO" control={<Radio color="error" />} label="Errado" disabled />
                      </RadioGroup>
                    </FormControl>
                  </Box>
                ))
              : null}
          </>
        )}

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
                    disabled
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
                    onChange={val => {
                      setForm(prev => ({
                        ...prev,
                        alternativas: prev.alternativas.map((a, i) =>
                          i === idx ? { ...a, texto: val } : a
                        )
                      }));
                    }}
                    placeholder={`Texto da alternativa ${alt.letra}`}
                    height={80}
                  />
                </Box>
                {alt.imagem_path_opcao && (
                  <Box sx={{ mt: 1, display: "flex", justifyContent: "center" }}>
                    <img
                      src={`http://localhost:8000/${alt.imagem_path_opcao}`}
                      alt={`Imagem alternativa ${alt.letra}`}
                      style={{ maxWidth: 180, maxHeight: 120, borderRadius: 8 }}
                    />
                  </Box>
                )}
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

        {form.tipo === "DISCURSIVA" && (
          <>
            <Divider sx={{ my: 2 }}>Campos Discursiva</Divider>
            <CampoComEditorAvancado
              label="Palavras-chave *"
              value={form.palavras_chave_discursiva}
              onChange={(val: string) => setForm(prev => ({ ...prev, palavras_chave_discursiva: val }))}
              required
              placeholder="Palavras-chave separadas por vírgula"
              height={50}
            />
            <TextField
              label="Número de linhas para resposta *"
              value={form.num_linhas_discursiva}
              disabled
              type="number"
              fullWidth
              sx={{ mb: 2 }}
            />
          </>
        )}

        {form.tipo === "SUBJETIVA" && (
          <>
            <Divider sx={{ my: 2 }}>Campos Subjetiva</Divider>
            <TextField
              label="Número de linhas para resposta *"
              value={form.num_linhas_discursiva}
              disabled
              type="number"
              inputProps={{ min: 1, max: 60 }}
              fullWidth
              sx={{ mb: 2 }}
            />
            <CampoComEditorAvancado
              label="Orientação da Resposta *"
              value={form.texto_subjetivo_orientacao}
              onChange={(val: string) => setForm(prev => ({ ...prev, texto_subjetivo_orientacao: val }))}
              required
              placeholder="Orientações para a banca ou candidato"
              height={50}
            />
            <TextField
              label="Nota Máxima *"
              value={form.texto_subjetivo_nota_maxima}
              disabled
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
          value={textoRefSelecionado}
          disabled
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
              disabled
            />
          )}
          sx={{ mb: 2 }}
          disabled
        />

        <Divider sx={{ my: 2 }}>Outros</Divider>
        {(form.tipo === "MULTIPLA_ESCOLHA" || form.tipo === "CERTO_ERRADO") && (
          <Box sx={{ display: "flex", gap: 4, mb: 2 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.anulada}
                  disabled
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
          disabled
          sx={{ mb: 2 }}
          fullWidth
        />
        <Autocomplete
          options={NIVEIS_DIFICULDADE}
          getOptionLabel={opt => opt.label}
          value={NIVEIS_DIFICULDADE.find(opt => opt.value === form.nivel_dificuldade) || null}
          renderInput={params => (
            <TextField
              {...params}
              label="Nível de Dificuldade"
              required
              variant="outlined"
              disabled
            />
          )}
          disabled
        />

        <Divider sx={{ my: 2 }}>Revisão</Divider>
        <Box component="form" onSubmit={handleRevisaoSubmit} autoComplete="off" sx={{ pointerEvents: sending ? "none" : "auto" }}>
          <Autocomplete
            options={[
              { value: "APROVADA", label: "Aprovada" },
              { value: "REPROVADA", label: "Reprovada" },
              { value: "AJUSTES", label: "Solicitar Ajustes" },
            ]}
            getOptionLabel={opt => opt.label}
            value={[
              { value: "APROVADA", label: "Aprovada" },
              { value: "REPROVADA", label: "Reprovada" },
              { value: "AJUSTES", label: "Solicitar Ajustes" },
            ].find(opt => opt.value === form.status_revisao) || null}
            onChange={(_, newValue) =>
              setForm(prev => ({ ...prev, status_revisao: newValue?.value ?? "" }))
            }
            renderInput={params => (
              <TextField
                {...params}
                label="Status da Revisão"
                required
                variant="outlined"
              />
            )}
            sx={{ mb: 2 }}
          />
          <CampoComEditorAvancado
            label="Observação do Revisor"
            value={form.observacao_revisor}
            onChange={(val: string) => setForm(prev => ({ ...prev, observacao_revisor: val }))}
            placeholder="Observações para o elaborador ou justificativa da revisão"
            height={70}
          />
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={sending}
            sx={{ mt: 2 }}
          >
            {sending ? <CircularProgress size={20} /> : "Salvar Revisão"}
          </Button>
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
          abaInicial="revisar" permitirGerar={false} onAplicar={(ap, aviso) => {
            setForm((prev: any) => aplicarNoForm(prev, ap));
            setSnackbar({ open: true, message: aviso, severity: "info" });
          }}
        />
      )}
    </Layout>
  );
}