import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Button, Paper, Divider, Table, TableHead, TableRow, TableCell, TableBody,
  Checkbox, Snackbar, Alert, FormControlLabel, CircularProgress, TextField, MenuItem, FormControl, InputLabel, Select, SelectChangeEvent,
  Tooltip, Dialog, DialogTitle, DialogContent, DialogActions, FormGroup
} from '@mui/material';
import api from '../api';
import Layout from '../components/Layout';
import { useParams } from 'react-router-dom';
import UploadFileIcon from '@mui/icons-material/UploadFile';

type CargoProvaType = {
  id_cargo: string;
  nome_cargo: string;
  definicao_geracao?: {
    num_variacoes: number;
    geracao_individual: boolean;
    embaralhar_questoes: boolean;
    embaralhar_alternativas: boolean;
    data_hora_geracao?: string;
  };
  frases_por_tipo_prova?: { [tipo: string]: string }; // <-- Adicionado
};

type TipoGeracao = 'modelo' | 'tipo' | 'candidato';

const tipoGeracaoLabels: Record<TipoGeracao, string> = {
  modelo: 'Prova Modelo Única',
  tipo: 'Por Tipo (A, B, C...)',
  candidato: 'Por Candidato (Personalizada)'
};

function formatarDataHora(iso?: string) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString('pt-BR');
}

// Componente para visualizar frases sorteadas
type FrasesPreviewDialogProps = {
  open: boolean;
  onClose: () => void;
  frasesPorTipo: { [tipo: string]: string };
  temFraseRepetida: boolean;
};

const FrasesPreviewDialog: React.FC<FrasesPreviewDialogProps> = ({ open, onClose, frasesPorTipo, temFraseRepetida }) => (
  <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
    <DialogTitle>Frases Motivacionais Sorteadas</DialogTitle>
    <DialogContent>
      {temFraseRepetida && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Atenção: Faltam frases únicas para todas as variações, algumas serão repetidas!
        </Alert>
      )}
      <Table>
        <TableBody>
          {Object.entries(frasesPorTipo).map(([tipo, frase]) => (
            <TableRow key={tipo}>
              <TableCell><b>{tipo}</b></TableCell>
              <TableCell>{frase}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </DialogContent>
    <DialogActions>
      <Button onClick={onClose}>Fechar</Button>
    </DialogActions>
  </Dialog>
);

const ProvaGeracaoPage: React.FC = () => {
  const { eventId } = useParams<{ eventId: string }>();
  const [cargos, setCargos] = useState<CargoProvaType[]>([]);
  const [selecionados, setSelecionados] = useState<{ [id: string]: boolean }>({});
  const [tipoGeracao, setTipoGeracao] = useState<TipoGeracao>('modelo');
  const [opcoesGeracao, setOpcoesGeracao] = useState<{
    num_variacoes: number;
    embaralhar_questoes: boolean;
    embaralhar_alternativas: boolean;
  }>({
    num_variacoes: 1,
    embaralhar_questoes: true,
    embaralhar_alternativas: true,
  });
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvFileLabel, setCsvFileLabel] = useState('');
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [importandoCsv] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({ open: false, message: '', severity: 'success' });
  const [confirmDialog, setConfirmDialog] = useState(false);

  // Novos estados para preview de frases
  const [frasesPreview, setFrasesPreview] = useState<{ [tipo: string]: string }>({});
  const [frasesDialogOpen, setFrasesDialogOpen] = useState(false);
  const [temFraseRepetida, setTemFraseRepetida] = useState(false);

  // Novos checkboxes obrigatórios antes de salvar
  const [confirmDefinicoes, setConfirmDefinicoes] = useState(false);
  const [confirmProntosGerar, setConfirmProntosGerar] = useState(false);

  // Busca apenas cargos que já têm prova montada
  async function fetchCargos() {
    setCarregando(true);
    try {
      const res = await api.get(`/eventos/${eventId}/cargos/provas-geracao`);
      setCargos(res.data as CargoProvaType[]);
      setSelecionados({});
    } catch (err) {
      setSnackbar({ open: true, message: 'Falha ao carregar cargos', severity: 'error' });
    }
    setCarregando(false);
  }

  useEffect(() => {
    fetchCargos();
    // eslint-disable-next-line
  }, [eventId]);

  // Checkbox master
  const todosSelecionados = cargos.length > 0 && cargos.every(c => selecionados[c.id_cargo]);
  const algumSelecionado = cargos.some(c => selecionados[c.id_cargo]);

  const handleSelecionarTodos = (checked: boolean) => {
    const all: { [id: string]: boolean } = {};
    cargos.forEach(c => { all[c.id_cargo] = checked; });
    setSelecionados(all);
  };

  const handleSelecionar = (id: string, checked: boolean) => {
    setSelecionados(prev => ({ ...prev, [id]: checked }));
  };

  const handleChangeOpcoes = (field: string, value: any) => {
    setOpcoesGeracao(prev => ({ ...prev, [field]: value }));
  };

  const handleTipoGeracaoChange = (e: SelectChangeEvent) => {
    const value = e.target.value as TipoGeracao;
    setTipoGeracao(value);
    if (value === 'modelo') {
      setOpcoesGeracao(prev => ({ ...prev, num_variacoes: 1 }));
      setCsvFile(null);
      setCsvFileLabel('');
    }
    if (value === 'candidato') {
      setOpcoesGeracao(prev => ({ ...prev, num_variacoes: 1 }));
    }
  };

  const handleCsvChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setCsvFile(file ?? null);
    setCsvFileLabel(file ? file.name : '');
  };

  // Função para visualizar frases sorteadas para um cargo
  async function handleVisualizarFrases(cargoId: string) {
    const cargoAtual = cargos.find(c => c.id_cargo === cargoId);
    // Se já tem frases reais, mostra elas
    if (cargoAtual?.frases_por_tipo_prova) {
      setFrasesPreview(cargoAtual.frases_por_tipo_prova);
      const frases = Object.values(cargoAtual.frases_por_tipo_prova);
      setTemFraseRepetida(frases.length !== new Set(frases).size);
      setFrasesDialogOpen(true);
    } else {
      // Senão, faz simulação como antes
      const formData = new FormData();
      formData.append('tipo_geracao', tipoGeracao);
      formData.append('num_variacoes', String(opcoesGeracao.num_variacoes));
      formData.append('embaralhar_questoes', String(opcoesGeracao.embaralhar_questoes));
      formData.append('embaralhar_alternativas', String(opcoesGeracao.embaralhar_alternativas));
      try {
        const res = await api.post(`/eventos/${eventId}/simular-frases/${cargoId}`, formData);
        setFrasesPreview(res.data.frases_por_tipo_prova || {});
        setTemFraseRepetida(res.data.tem_frase_repetida);
        setFrasesDialogOpen(true);
      } catch {
        setSnackbar({ open: true, message: "Erro ao simular frases!", severity: "error" });
      }
    }
  }

  const handleSalvarDefinicoes = async () => {
    const cargosIds = Object.keys(selecionados).filter(id => selecionados[id]);
    if (cargosIds.length === 0) {
      setSnackbar({ open: true, message: 'Selecione pelo menos um cargo!', severity: 'error' });
      return;
    }
    if (tipoGeracao === 'candidato' && !csvFile) {
      setSnackbar({ open: true, message: 'Selecione um arquivo CSV de candidatos!', severity: 'error' });
      return;
    }
    setSalvando(true);
    try {
      const formData = new FormData();
      formData.append('cargos_ids', JSON.stringify(cargosIds));
      formData.append('tipo_geracao', tipoGeracao);
      formData.append('num_variacoes', String(opcoesGeracao.num_variacoes));
      formData.append('embaralhar_questoes', String(opcoesGeracao.embaralhar_questoes));
      formData.append('embaralhar_alternativas', String(opcoesGeracao.embaralhar_alternativas));
      if (tipoGeracao === 'candidato' && csvFile) {
        formData.append('csv_candidatos', csvFile);
      }
      await api.post(`/eventos/${eventId}/provas/definir-geracao`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSnackbar({ open: true, message: 'Definições de geração salvas!', severity: 'success' });
      // Atualiza os cargos após salvar para pegar frases novas
      await fetchCargos();
    } catch {
      setSnackbar({ open: true, message: 'Erro ao salvar definições!', severity: 'error' });
    }
    setSalvando(false);
    setConfirmDialog(false);
    setConfirmDefinicoes(false);
    setConfirmProntosGerar(false);
  };

  // Destacar linha selecionada
  const getRowStyle = (id: string) => (
    !!selecionados[id]
      ? { backgroundColor: 'rgba(14, 165, 233, 0.08)' }
      : {}
  );

  const podeSalvar = confirmDefinicoes && confirmProntosGerar && !salvando;

  return (
    <Layout>
      <Paper sx={{ p: 3, borderRadius: 2, boxShadow: 3 }}>
        {/* TÍTULO ALINHADO À ESQUERDA */}
        <Typography variant="h5" fontWeight="bold" sx={{ mb: 2 }}>
          Geração de Provas
        </Typography>

        {/* Divider imediatamente após o título */}
        <Divider sx={{ mb: 3 }} />

        {/* ComboBox centralizado sozinho na linha */}
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
          <Box sx={{ width: "95%", maxWidth: 650 }}>
            <FormControl fullWidth>
              <InputLabel id="tipo-geracao-label">Tipo de Geração</InputLabel>
              <Select
                labelId="tipo-geracao-label"
                value={tipoGeracao}
                label="Tipo de Geração"
                onChange={handleTipoGeracaoChange}
                size="small"
              >
                <MenuItem value="modelo">{tipoGeracaoLabels.modelo}</MenuItem>
                <MenuItem value="tipo">{tipoGeracaoLabels.tipo}</MenuItem>
                <MenuItem value="candidato">{tipoGeracaoLabels.candidato}</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Box>

        {/* Opções das variações e embaralhamentos em linha */}
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', mb: 2 }}>
          {tipoGeracao === 'tipo' && (
            <TextField
              label="Nº de Variações"
              select
              value={opcoesGeracao.num_variacoes}
              onChange={e => handleChangeOpcoes('num_variacoes', Number(e.target.value))}
              sx={{ width: 160 }}
              size="small"
            >
              {Array.from({ length: 20 }, (_, i) => i + 1).map(n => (
                <MenuItem key={n} value={n}>{n}</MenuItem>
              ))}
            </TextField>
          )}
          <FormControlLabel
            control={
              <Checkbox
                checked={opcoesGeracao.embaralhar_questoes}
                onChange={e => handleChangeOpcoes('embaralhar_questoes', e.target.checked)}
              />
            }
            label="Embaralhar questões"
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={opcoesGeracao.embaralhar_alternativas}
                onChange={e => handleChangeOpcoes('embaralhar_alternativas', e.target.checked)}
              />
            }
            label="Embaralhar alternativas"
          />
        </Box>

        {/* Upload CSV só se tipoGeracao === 'candidato' */}
        {tipoGeracao === 'candidato' && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Button
              variant="outlined"
              component="label"
              disabled={importandoCsv}
              startIcon={<UploadFileIcon />}
            >
              {csvFileLabel || 'Selecionar CSV de Candidatos'}
              <input
                type="file"
                accept=".csv"
                hidden
                onChange={handleCsvChange}
              />
            </Button>
            {csvFileLabel && (
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                {csvFileLabel}
              </Typography>
            )}
          </Box>
        )}

        {/* Tabela de Cargos */}
        {carregando ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 200 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox
                    checked={todosSelecionados}
                    indeterminate={algumSelecionado && !todosSelecionados}
                    onChange={e => handleSelecionarTodos(e.target.checked)}
                  />
                </TableCell>
                <TableCell>Cargo</TableCell>
                <TableCell align="center">Definição de Geração</TableCell>
                <TableCell align="right">Última Geração</TableCell>
                <TableCell align="center">Ações</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {cargos.map(cargo => (
                <TableRow key={cargo.id_cargo} hover style={getRowStyle(cargo.id_cargo)}>
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={!!selecionados[cargo.id_cargo]}
                      onChange={e => handleSelecionar(cargo.id_cargo, e.target.checked)}
                    />
                  </TableCell>
                  <TableCell>
                    <Typography fontWeight="bold">{cargo.nome_cargo}</Typography>
                  </TableCell>
                  <TableCell align="center">
                    {cargo.definicao_geracao ? (
                      <Typography variant="caption" display="block">
                        Tipos: {cargo.definicao_geracao.num_variacoes} |{' '}
                        {cargo.definicao_geracao.geracao_individual ? 'Individual' : 'Modelo'} |{' '}
                        {cargo.definicao_geracao.embaralhar_questoes ? 'Embaralha Q' : 'Ordem Fixa'} |{' '}
                        {cargo.definicao_geracao.embaralhar_alternativas ? 'Embaralha Alt.' : 'Alt. Fixas'}
                      </Typography>
                    ) : (
                      <Typography variant="caption" color="warning.main">
                        Não definida
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {cargo.definicao_geracao?.data_hora_geracao
                      ? (
                        <Tooltip title={cargo.definicao_geracao.data_hora_geracao}>
                          <span>
                            {formatarDataHora(cargo.definicao_geracao.data_hora_geracao)}
                          </span>
                        </Tooltip>
                      )
                      : <span style={{ opacity: 0.6, fontStyle: 'italic' }}>Nunca gerado</span>
                    }
                  </TableCell>
                  <TableCell align="center">
                    <Button
                      onClick={() => handleVisualizarFrases(cargo.id_cargo)}
                      size="small"
                      variant="outlined"
                    >
                      Visualizar frases
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {cargos.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} align="center">
                    Nenhuma prova montada disponível para geração.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}

        {/* Alerta de responsabilidade */}
        <Alert
          severity="warning"
          sx={{ mt: 3, mb: 2, fontWeight: 'bold', fontSize: 16 }}
        >
          <strong>Atenção:</strong> A geração dos tipos de prova deve ser realizada com máxima cautela. Ao prosseguir, esteja ciente de que a geração de novos tipos para cargos já marcados pode invalidar provas já impressas ou distribuídas anteriormente. Certifique-se de que todas as configurações estejam corretas e que apenas os cargos realmente prontos estejam selecionados para este processo. O responsável pela operação assume integralmente o risco de inconsistências e retrabalho em caso de divergências identificadas posteriormente.
        </Alert>

        {/* Confirmações alinhadas à esquerda e checkbox centralizado verticalmente */}
        <Box sx={{ mb: 2, mt: 2 }}>
          <FormGroup sx={{ alignItems: "flex-start" }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={confirmDefinicoes}
                  onChange={e => setConfirmDefinicoes(e.target.checked)}
                  color="primary"
                  sx={{ alignSelf: "center" }}
                />
              }
              label={
                <span>
                  Declaro, para todos os fins, que conferi atentamente as definições de geração selecionadas nesta etapa e estou ciente de que não será possível recuperar configurações anteriores após a realização deste procedimento.
                </span>
              }
              sx={{ mb: 1 }}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={confirmProntosGerar}
                  onChange={e => setConfirmProntosGerar(e.target.checked)}
                  color="primary"
                  sx={{ alignSelf: "center" }}
                />
              }
              label={
                <span>
                  Declaro, sob minha responsabilidade, que marquei apenas os cargos para os quais há certeza e ciência operacional de que as provas já podem ser geradas neste momento.
                </span>
              }
            />
          </FormGroup>
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
          <Button
            variant="contained"
            color="primary"
            onClick={() => setConfirmDialog(true)}
            disabled={!podeSalvar}
          >
            {salvando ? 'Salvando...' : 'Salvar Definições'}
          </Button>
        </Box>

        {/* Dialog de confirmação */}
        <Dialog
          open={confirmDialog}
          onClose={() => setConfirmDialog(false)}
          aria-labelledby="confirm-dialog-title"
        >
          <DialogTitle id="confirm-dialog-title">Confirmação de geração de provas</DialogTitle>
          <DialogContent>
            <Typography>
              Confirme para prosseguir com a geração das provas para os cargos selecionados.<br /><br />
              <strong>IMPORTANTE:</strong> Ao confirmar, você assume total responsabilidade por eventuais inconsistências decorrentes da alteração das definições ou seleção incorreta dos cargos.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setConfirmDialog(false)} color="inherit">
              Cancelar
            </Button>
            <Button onClick={handleSalvarDefinicoes} color="primary" variant="contained" autoFocus>
              Confirmar geração
            </Button>
          </DialogActions>
        </Dialog>

        {/* Preview das frases motivacionais */}
        <FrasesPreviewDialog
          open={frasesDialogOpen}
          onClose={() => setFrasesDialogOpen(false)}
          frasesPorTipo={frasesPreview}
          temFraseRepetida={temFraseRepetida}
        />

        <Snackbar
          open={snackbar.open}
          autoHideDuration={3000}
          onClose={() => setSnackbar({ ...snackbar, open: false })}
        >
          <Alert severity={snackbar.severity} sx={{ width: '100%' }}>
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Paper>
    </Layout>
  );
};

export default ProvaGeracaoPage;